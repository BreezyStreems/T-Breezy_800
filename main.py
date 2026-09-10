import discord
import os
import sys
import random
import sqlite3
import time
import json
import datetime
import asyncio

from discord.ext import commands
from dotenv import load_dotenv
from google import genai
from curl_cffi import requests

# ------------------ ENV VARIABLES

load_dotenv()
TOKEN = os.getenv('TOKEN')
trusted_users = json.loads(os.getenv('TRUSTED_USERS', '[]'))
GEMINI_API_KEY = os.getenv('GEMINI_API')
if not TOKEN:
    print('skynet: ERROR - no token - FATAL')
    sys.exit()
if not trusted_users:
    print('skynet: ERROR - no trusted users - CRITICAL')
    trusted_to_add = input('input a trusted user: ')
    trusted_users = []
    trusted_users.append(trusted_to_add)
if not GEMINI_API_KEY:
    print('skynet: ERROR - no GEMINI API key - CRITICAL')
    user_resp = input('continue? [y/n]')
    if not user_resp == 'y':
        sys.exit()

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
            power INTEGER DEFAULT 0
        )
        """)
anime_roll_db_connection.commit()

# ------------------ IMPORTANT VARIABLES

user_command_timers = {}
waiting_for_input = {}

# ------------------ GEMINI VARIABLES

client = genai.Client(api_key=GEMINI_API_KEY)

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

    if ctx.author.id in waiting_for_input:
        if ctx.content.startswith('B '):
            await accept_user_input(ctx, ctx.content[2:])
        elif ctx.content.startswith('B| '):
            ctx.channel.send('terminate last process before starting a new command')

    if ctx.content.startswith('B| '):
        if ctx.content.endswith('animeroll'):
            await animeroll(ctx)
        elif ctx.content.endswith('status'):
            await status(ctx)
        elif ctx.content.endswith('animeinv'):
            await animeinv(ctx)
        elif ctx.content.startswith('B| appraisechar'):
            await appraisechar(ctx, ctx.content[15:])

        # BREEZY COMMANDS
        if ctx.author.id in trusted_users:
            if ctx.content[:7] == 'B| info':
                if len(ctx.mentions) == 1:
                    user = ctx.mentions[0]
                    await info(ctx, user)

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
        async def roll_anime(message):
            offset = random.randint(0, 10000)
            response = requests.get(
                "https://kitsu.io/api/edge/characters",
                params={
                    "page[limit]": 20,
                    "page[offset]": offset
                },
                headers={
                    "Accept": "application/vnd.api+json"
                },
                timeout=10
            )

            if response.status_code != 200:
                print(f'skynet: ERROR - roll failed | status code {response.status_code} - WARNING')
                await message.edit(content=f'skynet: ERROR - no character found | status code {response.status_code} - '
                                           f'WARNING')
                return False, None

            result = response.json()['data']
            result = random.choice(result)

            if not result:
                print('skynet: ERROR - no character found - WARNING')
                await message.edit(content='skynet: ERROR - no character found - WARNING')
                return False, None

            character = result

            embed = discord.Embed(
                title=character["attributes"]["name"],
                description=f'[LINK]({character["attributes"]["url"]})',
                color=discord.Color.blue()
            )
            embed.set_image(url=character["attributes"]["image"]["large"])
            await message.edit(content='ROLLED!', embed=embed)
            return True, character

        message = await ctx.channel.send('ROLLING...')
        status, character = await roll_anime(message)
        if not status:
            print('skynet: ERROR - roll failed - WARNING')
            return

        ardb_cursor.execute("""
            SELECT * FROM characters WHERE id = ? AND character = ?
        """, (ctx.author.id, character['name']['full']))
        characters = ardb_cursor.fetchone()
        if characters:
            await message.edit(content=f'CHARACTER ALREADY EXISTS - do you wish to overwrite a character with '
                                       f'{characters['power']} power? [B y/ B n]')
            waiting_for_input[ctx.author.id] = ['replace char', character]
        else:
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
        """, (ctx.author.id, character["attributes"]["name"]))
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

async def info(ctx, user):
    def get_creation_date(user_id: int):
        timestamp = ((user_id >> 22) + 1420070400000) / 1000
        return datetime.datetime.fromtimestamp(timestamp, tz=datetime.timezone.utc)

    message = await ctx.channel.send('SCRAPING DATA...')

    user_id = str(user.id)
    user_name = str(user.name)
    user_avatar = user.display_avatar.url
    user_creation_date = get_creation_date(user.id)

    ardb_cursor.execute("""
                SELECT * FROM characters WHERE id = ?
            """, (ctx.author.id,))
    characters = ardb_cursor.fetchall()
    if characters:
        character_list = ''
        for character in characters:
            character_list += str(character[1]) + '\n'

    embed = discord.Embed(title=f'{user_name}\n{user_id}\n{user_creation_date}', color=discord.Color.red())
    embed.set_image(url=user_avatar)

    await message.edit(content=None, embed=embed)

async def appraisechar(ctx, character):
    pass

async def accept_user_input(ctx, user_input):
    if user_input == 'y':
        if waiting_for_input[ctx.author.id][0] == 'replace char':
            ardb_cursor.execute("""
                REPLACE INTO characters (id, character)
                VALUES (?, ?)
            """, (ctx.author.id, waiting_for_input[ctx.author.id][1]['attributes']['name']))

# ------------------ DEVELOPMENT CONSOLE

async def development_console():
    while not bot.is_closed():
        command = await asyncio.to_thread(input, 'skynet>\n')

        if command == 'status':
            anime_roll_status = True
            response = requests.get(
                "https://kitsu.io/api/edge/characters",
                params={
                    "page[limit]": 20,
                    "page[offset]": 21
                },
                headers={
                    "Accept": "application/vnd.api+json"
                },
                timeout=10
            )
            if not response.status_code == 200:
                anime_roll_status = False
                print(response.status_code)
    
            print('skynet: ONLINE')
            if anime_roll_status: print('skynet - animeroll: ONLINE')
            else: print('skynet - animeroll: OFFLINE')

async def main():
    await asyncio.gather(
        bot.start(TOKEN),
        development_console()
    )


asyncio.run(main())