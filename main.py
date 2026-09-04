import discord
import os
import sys

from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('TOKEN')

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
    await ctx.send('skynet: ONLINE')

bot.run(TOKEN)