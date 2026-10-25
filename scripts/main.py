import discord
import os
import sys
import time
import json
import asyncio

from discord.ext import commands
from dotenv import load_dotenv
from curl_cffi import requests
from PIL import Image, ImageDraw, ImageFont

from onready import onready
from onmessage import onmessage

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

# ------------------ DISCORD VARIABLES

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='B| ', intents=intents)

# ------------------ SQLITE3 VARIABLES & ACTIONS

# ------------------ IMPORTANT VARIABLES

animeinv_max = 50
starttime = 0

onready = onready(bot)
task_queue = None
dev_server = None # set in on ready
dev_channel = None # set in on ready
welc_channel = None # set in on ready

onmessage = onmessage(bot, GEMINI_API_KEY)

home_dir = os.path.dirname(os.path.dirname(__file__))

# ------------------ GEMINI VARIABLES
# ------------------ DISCORD EVENTS

@bot.event
async def on_ready():
    global task_queue

    await onready.onreadyfunc()
    task_queue = onready.task_queue
    onmessage.accepting_commands = True

@bot.event
async def on_message(ctx):
    await onmessage.B_on_message(task_queue, ctx, trusted_users)

@bot.event
async def on_member_join(ctx):
    await B_on_member_join(ctx)

# ------------------ EVENT FUNCTIONS

async def B_on_member_join(ctx, trigger=None, name=None):

    global welc_channel

    if not trigger is None:
        await welc_channel.send(f'haiiii ≽^-⩊-^≼ - welcome to the server {name}\n'
                                f'grab some roles, read the rules, and get settled into our den!!')
        return

    await welc_channel.send(f'haiiii ≽^-⩊-^≼ - welcome to the server {ctx.name}\n'
                            f'grab some roles, read the rules, and get settled into our den!!')

# ------------------ FUNCTIONS
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
        elif command.startswith('queue'):
            print('QUEUE \n' \
            '-----------------------')
            if task_queue.empty():
                print('No Tasks')
                return
            for task in task_queue:
                print(task)
        elif command.startswith('trigger '):
            command_args = command.split(' ')
            trigger = command_args[1]
            if trigger == 'join':
                name = command_args[2]
                await B_on_member_join(None, trigger=True, name=name)

        # CRITICAL COMMANDS
        elif command.startswith('shutdown'):
            print('skynet: shutting down...')

            accepting_commands = False

            print('skynet: finishing tasks...')
            await task_queue.join()

            uptime = time.time() - starttime
            days = int(uptime // 86400)
            hours  = int((uptime % 86400) // 3600)
            minutes = int((uptime % 3600) // 60)
            seconds = int((uptime % 60))
            
            print(f'uptime: {days}d {hours}h {minutes}m {seconds}s')
            await bot.close()

# ------------------ HELPER FUNCTIONS

async def create_image(wh, type, args=None):
    if type == 'animeroll character':
        img = Image.new('RGB', (wh[0], wh[1]), 'black')
        border = Image.open(os.path.join(home_dir, 'assets', 'character_card_background'))
        draw = ImageDraw.Draw(img)
    elif type == 'appraisechar character':
        pass

# ------------------ MAIN FUNCTION START

async def main():
    await asyncio.gather(
        bot.start(TOKEN),
        development_console(),
    )

asyncio.run(main())