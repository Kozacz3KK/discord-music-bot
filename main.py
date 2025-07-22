import os
import discord
from discord.ext import commands

intents = discord.Intents.default()
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'Zalogowano jako {bot.user}')

token = os.getenv('DISCORD_TOKEN')
if not token:
    print("ERROR: Brak tokena w zmiennych środowiskowych!")
    exit(1)

bot.run(token)
