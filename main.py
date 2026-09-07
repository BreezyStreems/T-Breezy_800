import discord
import os
import sys
import requests
import random
import sqlite3
import time

from discord.ext import commands
from dotenv import load_dotenv

# ------------------ ENV VARIABLES

load_dotenv()
TOKEN = os.getenv('TOKEN')

# ------------------ ANIME ROLL VARIABLES

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
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Content-Type': 'application/json',
    'Accept': 'application/json'
}

if not TOKEN:
    print('skynet: ERROR - no token - FATAL')
    sys.exit()

# ------------------ DISCORD VARIABLES

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='B| ', intents=intents)

# ------------------ SQLITE3 VARIABLES & ACTIONS

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
            power INTEGER
        )
        """)
anime_roll_db_connection.commit()

# ------------------ IMPORTANT VARIABLES

user_command_timers = {}

# ------------------ DISCORD EVENTS
@bot.event
async def on_ready():
    print(f'skynet initialized: {bot.user}')

@bot.event
async def on_message(ctx):
    if ctx.author == bot.user:
        return

    if ctx.author.id in user_command_timers:
        if time.time() - user_command_timers[ctx.author.id] < 1.5:
            return
        else:
            user_command_timers[ctx.author.id] = 0

    user_command_timers[ctx.author.id] = time.time()

    if ctx.content.startswith('B| '):
        if ctx.content.endswith('animeroll'):
            await animeroll(ctx)
        elif ctx.content.endswith('status'):
            await status(ctx)
        elif ctx.content.endswith('animeinv'):
            await animeinv(ctx)

# ------------------ FUNCTIONS

async def status(ctx):
    if not ctx.author.bot:
        anime_roll_status = True
        response = requests.post("https://graphql.anilist.co", json={"query": anime_roll_url, 'variables': {'id': 1}}, )
        if not response.status_code == 200:
            anime_roll_status = False

        await ctx.channel.send('skynet: ONLINE')
        if anime_roll_status: await ctx.channel.send('skynet - animeroll: ONLINE')
        else: await ctx.channel.send('skynet - animeroll: OFFLINE')

async def animeroll(ctx):
    if not ctx.author.bot:
        async def roll_anime_two(message, variables):
            response = requests.post('https://graphql.anilist.co', json={'query': anime_roll_url, 'variables':
                variables}, headers=headers, timeout=5)

            if response.status_code != 200:
                print(f'skynet: ERROR - no character found | status code {response.status_code} - WARNING')
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
        message = await ctx.channel.send('ROLLING...')
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

async def animeinv(ctx):
    if not ctx.author.bot:
        message = await ctx.channel.send('FETCHING...')
        ardb_cursor.execute("""
            SELECT * FROM characters WHERE id = ?
        """, (ctx.author.id,))
        characters = ardb_cursor.fetchall()

        if characters:
            character_list = ''
            for character in characters:
                character_list += str(character[1]) + '\n'
            await message.edit(content=character_list)
        else:
            await message.edit(content='No characters in inventory')

bot.run(TOKEN)