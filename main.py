import discord
import os
import sys
import requests
import random
import sqlite3

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

anime_roll_db_connection = sqlite3.connect('anime_roll.db')
ardb_cursor = anime_roll_db_connection.cursor()
ardb_cursor.execute("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY,
            rolls INTEGER DEFAULT 0
        )
        """)
anime_roll_db_connection.commit()
ardb_cursor.execute("""
        CREATE TABLE IF NOT EXISTS characters(
            id INTEGER,
            character TEXT,
            power INTEGER,
        )
        """)
anime_roll_db_connection.commit()

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
                return False, None

            result = response.json().get('data', {}).get('Character')

            if not result:
                print('skynet: ERROR - no character found - WARNING')
                await message.edit(content='skynet: ERROR - no character found - WARNING')
                return False, None

            character = result

            embed = discord.Embed(
                title=character['name']['full'],
                description=f'[IMAGE]({character['siteUrl']})',
                color=discord.Color.blue()
            )
            embed.set_image(url=character['image']['large'])
            await message.edit(content='ROLLED!', embed=embed)
            return True, character

        variables = {'id': random.randint(1, 300000)}
        message = await ctx.send('ROLLING...')
        status, character = await roll_anime_two(message, variables)
        if not status:
            print('skynet: ERROR - roll failed. aborting command - WARNING')
            return

        ardb_cursor.execute("""
        INSERT OR IGNORE INTO users (id)
        VALUES (?)
        """, (ctx.author.id,))

        ardb_cursor.execute("""
        UPDATE users
        SET rolls = rolls + 1
        WHERE id = ?
        """, (ctx.author.id,))

        ardb_cursor.execute("""
        INSERT INTO characters (id, character)
        VALUES (?, ?)
        """, (ctx.author.id, character['name']['full']))
        anime_roll_db_connection.commit()


bot.run(TOKEN)