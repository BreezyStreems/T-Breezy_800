import discord
import os
import sys
import requests
import random

from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('TOKEN')
anime_roll_url = """
query ($id: Int) {
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
        response = requests.post("https://graphql.anilist.co", json={"query": anime_roll_url, 'variables': {'id': 1}}, )
        if not response.status_code == 200:
            anime_roll_status = False

        await ctx.send('skynet: ONLINE')
        if anime_roll_status: await ctx.send('skynet - animeroll: ONLINE')
        else: await ctx.send('skynet - animeroll: OFFLINE')


@bot.command()
async def animeroll(ctx):
    if not ctx.author.bot:
        async def roll_anime_two(message, variables):
            response = requests.post('https://graphql.anilist.co', json={'query': anime_roll_url, 'variables':
                variables}, timeout=5)

            if response.status_code != 200:
                print('skynet: ERROR - no character found - WARNING')
                await message.edit(content=f'skynet: ERROR - no character found | status code {response.status_code} - '
                                           f'WARNING')
                return

            result = response.json().get('data', {}).get('Character')

            if not result:
                print('skynet: ERROR - no character found - WARNING')
                await message.edit(content='skynet: ERROR - no character found - WARNING')
                return

            character = result

            embed = discord.Embed(
                title=character['name']['full'],
                description=f'[IMAGE]({character['siteUrl']})',
                color=discord.Color.blue()
            )
            embed.set_image(url=character['image']['large'])
            await message.edit(content='ROLLED!', embed=embed)

        variables = {'id': random.randint(1, 300000)}
        message = await ctx.send('ROLLING...')
        await roll_anime_two(message, variables)

bot.run(TOKEN)