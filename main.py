import discord
import os
import sys
import requests
import random

from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('TOKEN')
anime_roll_url_one = "https://api.jikan.moe/v4/characters/1"
anime_roll_url_two = """
query {
    Character(id: $id) {
        id
        name {
            full
        }
        image {
            large
            medium
        }
        siteUrl
    }
}
"""

if not TOKEN:
    print('skynet: ERROR - no token - FATAL')
    sys.exit()

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='B| ', intents=intents)

@bot.event
async def on_ready():
    print(f'skynet initialized: {bot.user}')

@bot.command()
async def status(ctx):
    if not ctx.author.bot:
        anime_roll_status = True
        response = requests.get(anime_roll_url_one)
        if not response.status_code == 200:
            anime_roll_status = False
        if not anime_roll_status:
            anime_roll_status = True
            response = requests.post("https://graphql.anilist.co", json={"query":
            anime_roll_url_two}, )
            if not response.status_code == 200:
                anime_roll_status = False

        await ctx.send('skynet: ONLINE')
        if anime_roll_status: await ctx.send('skynet - animeroll: ONLINE')
        else: await ctx.send('skynet - animeroll: OFFLINE')


@bot.command()
async def animeroll(ctx):
    if not ctx.author.bot:

        async def roll_anime_one(message):
            response = requests.get(anime_roll_url_one)

            if response.status_code != 200:
                print('skynet: ERROR - no character found - WARNING')
                await message.edit(content='skynet: ERROR - no character found - WARNING')
                return False

            response = response.json()

            if 'data' not in response:
                print('skynet: ERROR - no data content found - WARNING')
                await message.edit(content='skynet: ERROR - no data content found - WARNING')
                return False

            character = response['data']

            await message.edit(content=f'ROLLED!\n'
                                       f'{character['name']}\n'
                                       f'{character['url']}\n'
                                       f'{character['images']['jpg']['image_url']}')
            return True

        async def roll_anime_two(message):
            response = requests.post('https://graphql.anilist.co', json={'query': anime_roll_url_two, 'variables':
                variables}, timeout=5)

            if not response.status_code == 200:
                print('skynet: ERROR - no character found - WARNING')
                await message.edit(content='skynet: ERROR - no character found - WARNING')
                return

            result = response.json().get('data', {}).get('Character')

            if not result['data']['Character']:
                print('skynet: ERROR - no character found - WARNING')
                await message.edit(content='skynet: ERROR - no character found - WARNING')
                return

            character = result['data']['Character']

            embed = discord.Embed(
                title=character['name']['full'],
                description=f'[IMAGE]({character['siteUrl']})',
                color=discord.Color.blue()
            )
            embed.set_image(url=character['image']['large'])
            await message.edit(content='ROLLED!', embed=embed)

        variables = {'id': random.randint(1, 120000)}
        message = await ctx.send('ROLLING...')
        status = await roll_anime_one(message)
        if status: return
        print('skynet: ERROR - first roll failed - WARNING')
        await message.edit(content=f'skynet: ERROR - first roll failed - WARNING')
        if not status: await roll_anime_two(message)

bot.run(TOKEN)