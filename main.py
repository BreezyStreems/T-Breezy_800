import discord
import os
import sys
import random
import sqlite3
import time
import json
import datetime
import asyncio
import traceback
import math

from discord.ext import commands
from dotenv import load_dotenv
from google import genai
from curl_cffi import requests
from functools import partial

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
dev_server = None # set in on ready
dev_channel = None # set in on ready
animeinv_max = 50
starttime = 0
accepting_commands = False
task_queue = asyncio.Queue()

# ------------------ GEMINI VARIABLES

if GEMINI_API_KEY: client = genai.Client(api_key=GEMINI_API_KEY)

# ------------------ DISCORD EVENTS
@bot.event
async def on_ready():

    global dev_channel
    global dev_server
    global starttime
    global accepting_commands

    print(f'skynet initialized: {bot.user}')

    dev_server = bot.get_guild(1345760072776679495)

    if dev_server is None:
        for guild in bot.guilds:
            if guild.id == 1345760072776679495:
                dev_server = guild

    dev_channel = dev_server.get_channel(1347697748518113360)

    if dev_channel is None:
        for channel in dev_server.channels:
            if channel.name == 'general3':
                dev_channel = channel

    print(f'skynet dev server connection established: {dev_server} -> {dev_channel}')
    starttime = time.time()
    print(f'starttime : {starttime:0.2f}')
    accepting_commands = True

@bot.event
async def on_message(ctx):
    if ctx.author.bot and ctx.author.id != bot.user.id or not accepting_commands: return

    if ctx.author.id in user_command_timers:
        if time.time() - user_command_timers[ctx.author.id] < 5:
            return
        else:
            user_command_timers[ctx.author.id] = 0

    user_command_timers[ctx.author.id] = time.time()

    if ctx.author.id in waiting_for_input:
        if ctx.content.startswith('B '):
            await accept_user_input(ctx, ctx.content[2:])
        elif ctx.content.startswith('B| '):
            await ctx.channel.send('terminate last process before starting a new command')

    if ctx.content.startswith('B| '):
        if ctx.content.endswith('animeroll'):
            await task_queue.put(partial(animeroll, ctx))
        elif ctx.content.endswith('status'):
            await task_queue.put(partial(status, ctx))
        elif ctx.content.startswith('B| animeinv'):
            command_args = ctx.content.split('|')
            for i in range(len(command_args)): command_args[i] = command_args[i].strip()
            if len(command_args) > 2: await task_queue.put(partial(animeinv, ctx, args=command_args))
            else: await task_queue.put(partial(animeinv, ctx))
        elif ctx.content.startswith('B| appraisechar '):
            await task_queue.put(partial(appraisechar, ctx, ctx.content[16:]))

        # BREEZY COMMANDS
        if ctx.author.id in trusted_users:
            if ctx.content[:7] == 'B| info':
                if len(ctx.mentions) == 1:
                    user = ctx.mentions[0]
                    await info(ctx, user)

# ------------------ FUNCTIONS

async def status(ctx):
    anime_roll_status = True
    response = requests.get("https://kitsu.io/api/edge/characters", params={"page[limit]": 20, "page[offset]": 21}, headers={"Accept": "application/vnd.api+json"}, timeout=10)
    if not response.status_code == 200:
        anime_roll_status = False

    await ctx.channel.send('skynet: ONLINE')
    if anime_roll_status: await ctx.channel.send('skynet - animeroll: ONLINE')
    else: await ctx.channel.send('skynet - animeroll: OFFLINE')
    

async def animeroll(ctx):
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
            timeout=5
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
            description=f'[LINK]({character["links"]["self"]})',
            color=discord.Color.blue()
        )
        embed.set_image(url=character["attributes"]["image"]["original"])
        await message.edit(content='ROLLED!', embed=embed)
        return True, character

    ardb_cursor.execute("""
        SELECT * FROM characters WHERE id = ?
    """, (ctx.author.id,))
    animeinv_status = ardb_cursor.fetchall()

    if animeinv_status == 50:
        await ctx.channel.send('skynet: WARNING - inventory full!! - NEGLIGIBLE')
        return

    message = await ctx.channel.send('ROLLING...')
    status, character = await roll_anime(message)
    if not status:
        print('skynet: ERROR - roll failed - WARNING')
        return

    ardb_cursor.execute("""
        SELECT * FROM characters WHERE id = ? AND character = ?
    """, (ctx.author.id, character['attributes']['name']))
    characters = ardb_cursor.fetchone()
    if characters:
        await message.edit(content=f'CHARACTER ALREADY EXISTS - do you wish to overwrite a character with '
                                    f'{characters[2]} power? [B y/ B n]')
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

async def animeinv(ctx, args=None):
    message = await ctx.channel.send('FETCHING...')
    ardb_cursor.execute("""
        SELECT * FROM characters WHERE id = ?
    """, (ctx.author.id,))
    characters = ardb_cursor.fetchall()

    strongest_character = [None, None, 0]
    if characters:
        character_list = ''
        deleted_character_count = 0
        if args == None:
            for character in characters:
                if character[2] > strongest_character[2]: strongest_character = character
                character_list += str(character[1]) + ' -> ' + str(character[2]) + '\n'
        elif args[2] == 'sort':
            if args[3] == 'strongestasc':
                characters.sort(key=lambda x: x[2], reverse=True)
                for character in characters:
                    if character[2] > strongest_character[2]: strongest_character = character
                    character_list += str(character[1]) + ' -> ' + str(character[2]) + '\n'
            elif args[3] == 'strongestdesc':
                characters.sort(key=lambda x: x[2])
                for character in characters:
                    if character[2] > strongest_character[2]: strongest_character = character
                    character_list += str(character[1]) + ' -> ' + str(character[2]) + '\n'
        elif args[2] == 'delete':
            if args[3] == 'powerbased':
                if not args[4].isdigit():
                    return

                for character in characters:
                    if character[2] <= int(args[4]):
                        ardb_cursor.execute("""
                            DELETE FROM characters WHERE id = ? AND character = ?
                        """, (ctx.author.id, character[1]))
                        deleted_character_count += 1
                    else: character_list += str(character[1]) + ' -> ' + str(character[2]) + '\n'

                anime_roll_db_connection.commit()

        else:
            print('skynet: ERROR - invalid args - NEGLIGIBLE')
            await message.edit(content='skynet: ERROR - invalid args - NEGLIGIBLE')
            return

        if character_list: await message.edit(content=f'{character_list}\n'
                                   f'Strongest Character : {strongest_character[1]} -> {strongest_character[2]}\n'
                                   f'Characters : {len(characters) - deleted_character_count}')
        else: await message.edit(content='EMPTY INVENTORY\n'
                                         'ROLL A CHARACTER USING : "B| animeroll"')
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

    if user_id is None or user_name is None or user_avatar is None or user_creation_date is None:
        print('skynet: ERROR - info failed - WARNING')

    ardb_cursor.execute("""
                SELECT * FROM characters WHERE id = ?
            """, (user_id,))
    characters = ardb_cursor.fetchall()
    if characters:
        character_list = ''
        for character in characters:
            character_list += str(character[1]) + '\n'

    embed = discord.Embed(title=f'{user_name}\n{user_id}\n{user_creation_date}', color=discord.Color.red())
    embed.set_image(url=user_avatar)

    await message.edit(content=None, embed=embed)

async def appraisechar(ctx, character):
    message = await ctx.channel.send('APPRAISING...')
    ardb_cursor.execute("""
            SELECT * FROM characters WHERE id = ? AND character = ? AND power = ?
        """, (ctx.author.id, character, 0))
    character = ardb_cursor.fetchone()

    if character:
        response = requests.get("https://kitsu.io/api/edge/characters", params={"filter[name]": character[1],
            "page[limit]": 10}, headers={"Accept": "application/vnd.api+json"},
            timeout=5)

        if not response.status_code == 200:
            print('skynet: ERROR - appraisechar failed | kitsu request - WARNING')
            await message.edit(content='skynet: ERROR - appraisechar failed | kitsu request - WARNING')
            return

        result = response.json()["data"][0]

        media_response = requests.get(f"https://kitsu.io/api/edge/characters/{result['id']}/relationships/primary-media",
            timeout=5)

        if not media_response.status_code == 200:
            print('skynet: ERROR - appraisechar failed - kitsu media request - WARNING')
            await message.edit(content='skynet: ERROR - appraisechar failed - kitsu media request - WARNING')
            return

        if 'manga' in media_response.json()['data']['type']:
            media_response = requests.get(f"https://kitsu.io/api/edge/manga/{media_response.json()['data']['id']}",
                headers={"Accept": "application/vnd.api+json"}, timeout=5)
        elif 'anime' in media_response.json()['data']['type']:
            media_response = requests.get(f"https://kitsu.io/api/edge/anime/{media_response.json()['data']['id']}",
                headers={"Accept": "application/vnd.api+json"}, timeout=5)

        if not media_response.status_code == 200:
            print('skynet: ERROR - appraisechar failed - kitsu media request - WARNING')
            await message.edit(content='skynet: ERROR - appraisechar failed - kitsu media request - WARNING')
            return

        anime_title = media_response.json()["data"]["attributes"]["titles"]['en']

        prompt = ('ANIME CHARACTER APPRAISING | APPRAISE THIS CHARACTER BY GIVING IT A NUMBER OF ITS POWER\n'
                  'you will give a character a number based on its power level in their strongest form.\n'
                  'the scale is as so: 0 - they can break a stick all the way to 10000 - they can destroy the '
                  'multiverse\n'
                  f'CHARACTER NAME: {character[1]}\n'
                  f'CHARACTER ANIME(S)/MANGA(S): {anime_title}\n'
                  f'IMPORTANT - respond with only the number, nothing else.')

        response = client.models.generate_content(
            model='gemini-3.5-flash-lite',
            contents=prompt,
        )

        if response.text == '' or response.text is None:
            print('skynet: ERROR - appraisechar failed | genai content - WARNING')
            await message.edit(content='skynet: ERROR - appraisechar failed | genai content - WARNING')
            return

        power = response.text.strip()

        if not power.isdigit():
            print('skynet: ERROR - appraisechar failed - genai content | contained somethign other than numbers - '
                  'WARNING')
            await message.edit(content='skynet: ERROR - appraisechar failed - genai content | contained somethign other than numbers - '
                  'WARNING')
            return

        ardb_cursor.execute("""
            UPDATE characters
            SET power = ?
            WHERE id = ? AND character = ?
        """, (int(power), ctx.author.id, character[1]))
        anime_roll_db_connection.commit()

        await message.edit(content='APPRAISED!!\n'
                                   f'{character[1]} aquired power: {power} - {await check_rarity(int(power))}')

    else:
        print('skynet: ERROR character not found or already appraised - NEGLIGIBLE')
        await message.edit(content='skynet: ERROR character not found or already appraised - NEGLIBLE')

async def accept_user_input(ctx, user_input):
    if user_input == 'y':
        if waiting_for_input[ctx.author.id][0] == 'replace char':
            ardb_cursor.execute("""
                UPDATE characters
                SET power = 0
                WHERE id = ? AND character = ?
                VALUES (?, ?)
            """, (ctx.author.id, waiting_for_input[ctx.author.id][1]['attributes']['name']))
            anime_roll_db_connection.commit()
    elif user_input == 'n':
        if waiting_for_input[ctx.author.id][0] == 'replace char':
            waiting_for_input[ctx.author.id] = None

async def check_rarity(power):
    if power >= 9750:
        tier = '2-A | Multiverse level+'
    elif power >= 9500:
        tier = '2-B | Multiverse level'
    elif power >= 9000:
        tier = '2-C | Low Multiverse level'
    elif power >= 8650:
        tier = 'Low 2-C | Universe level+'
    elif power >= 8000:
        tier = '3-A | Universe level'
    elif power >= 7500:
        tier = 'High 3-A | High Universe level'
    elif power >= 7000:
        tier = '3-B | Multi-Galaxy level'
    elif power >= 6500:
        tier = '3-C | Galaxy level'
    elif power >= 6000:
        tier = '4-A | Multi-Solar System level'
    elif power >= 5500:
        tier = '4-B | Solar System level'
    elif power >= 5000:
        tier = '4-C | Star level'
    elif power >= 4500:
        tier = 'High 4-C | Large Star level'
    elif power >= 4000:
        tier = '5-A | Large Planet level'
    elif power >= 3500:
        tier = '5-B | Planet level'
    elif power >= 3000:
        tier = 'Low 5-B | Small Planet level'
    elif power >= 2500:
        tier = '5-C | Moon level'
    elif power >= 2000:
        tier = '6-A | Continent level'
    elif power >= 1500:
        tier = '6-B | Country level'
    elif power >= 1000:
        tier = '7-A | Mountain level'
    elif power >= 750:
        tier = '7-B | City level'
    elif power >= 500:
        tier = '8-B | City Block level'
    elif power >= 250:
        tier = '8-C | Building level'
    elif power >= 100:
        tier = '9-A | Small Building level'
    elif power >= 50:
        tier = '9-B | Wall level'
    elif power >= 25:
        tier = '9-C | Street level'
    elif power >= 10:
        tier = '10-A | Athlete level'
    elif power >= 1:
        tier = '10-B | Human level'
    else:
        tier = '10-C | Below Average Human level'

    return tier

async def task_worker():
    while accepting_commands:
        task = await task_queue.get()

        try:
            await task()
        except Exception as e:
            print('skynet: ERROR - task failed - CRITICAL')
            traceback.print_exc()
        finally:
            task_queue.task_done()

# ------------------ DEVELOPMENT CONSOLE

async def development_console():

    global accepting_commands

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
        elif command.startswith('send_message '):
            message_to_send = command[13:]
            print(message_to_send)
            await dev_channel.send(message_to_send)
        elif command.startswith('check_perms'):
            guild_id = input('guild id >')
            perms = bot.get_guild(int(guild_id)).me.guild_permissions
            perms = [perm_name for perm_name, enabled in perms if enabled]
            print(perms)
        elif command.startswith('server_list'):
            for server in bot.guilds:
                print(server.name)
        elif command.startswith('bot_info'):
            print(bot.user.id)
            print(bot.user)
            print(bot.latency * 1000, 'ms')

        # CRITICAL COMMANDS
        elif command.startswith('shutdown'):
            print('skynet: shutting down...')

            accepting_commands = False

            print('skynet: finishing tasks...')
            await task_queue.join()

            uptime = time.time() - starttime
            print(uptime)
            days = int(uptime // 86400)
            hours  = int((uptime % 86400) // 3600)
            minutes = int((uptime % 3600) // 60)
            seconds = int((uptime % 60))
            
            print(f'uptime: {days}d {hours}h {minutes}m {seconds}s')
            await bot.close()



# ------------------ MAIN FUNCTION START

async def main():
    await asyncio.gather(
        bot.start(TOKEN),
        development_console(),
        task_worker()
    )

asyncio.run(main())