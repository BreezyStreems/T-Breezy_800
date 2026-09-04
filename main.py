import discord

from discord import commands

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='B| ', intents=intents)

@bot.event
async def on_ready():
    print(f'skynet initialized: {bot.user}')

@bot.command()
async def status(ctx):
    await ctx.send('skynet: ONLINE')