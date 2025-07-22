import os

token = os.getenv("DISCORD_TOKEN")
print("Token:", token)

if not token:
    print("Brak tokena! Sprawdź .env lub zmienne środowiskowe.")
    exit()

import os
import discord
from discord.ext import commands
import youtube_dl
import asyncio

intents = discord.Intents.default()
intents.message_content = True  # ważne dla czytania treści wiadomości w nowej wersji discord.py
bot = commands.Bot(command_prefix='!', intents=intents)

# Konfiguracja youtube_dl
ytdl_format_options = {
    'format': 'bestaudio/best',
    'quiet': True,
    'noplaylist': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'  # bind to ipv4 since ipv6 might cause issues
}

ffmpeg_options = {
    'options': '-vn'
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')
    
    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        
        if 'entries' in data:
            # We take first item from a playlist
            data = data['entries'][0]
        
        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

# Kolejka muzyczna per guild (serwer)
queues = {}

def get_queue(guild_id):
    return queues.setdefault(guild_id, [])

@bot.event
async def on_ready():
    print(f'Zalogowano jako {bot.user}')

# Komenda dołączenia bota do kanału głosowego
@bot.command(name='join')
async def join(ctx):
    if ctx.author.voice is None:
        await ctx.send("Musisz być na kanale głosowym, żeby mnie zaprosić!")
        return
    channel = ctx.author.voice.channel
    if ctx.voice_client is not None:
        await ctx.voice_client.move_to(channel)
    else:
        await channel.connect()
    await ctx.send(f'Dołączyłem do {channel}')

# Komenda rozłączenia bota
@bot.command(name='leave')
async def leave(ctx):
    if ctx.voice_client is not None:
        await ctx.voice_client.disconnect()
        await ctx.send("Rozłączyłem się")
    else:
        await ctx.send("Nie jestem połączony z żadnym kanałem głosowym.")

# Komenda play — dodaje do kolejki lub odtwarza od razu
@bot.command(name='play')
async def play(ctx, *, search: str):
    if ctx.author.voice is None:
        await ctx.send("Musisz być na kanale głosowym, żeby odtwarzać muzykę!")
        return

    voice = ctx.voice_client
    if voice is None:
        channel = ctx.author.voice.channel
        voice = await channel.connect()

    guild_id = ctx.guild.id
    queue = get_queue(guild_id)

    async with ctx.typing():
        player = await YTDLSource.from_url(search, loop=bot.loop, stream=True)
        queue.append(player)
        await ctx.send(f'Dodano do kolejki: {player.title}')

        if not voice.is_playing() and not voice.is_paused():
            await play_next(ctx)

async def play_next(ctx):
    guild_id = ctx.guild.id
    queue = get_queue(guild_id)
    voice = ctx.voice_client

    if len(queue) == 0:
        await ctx.send("Kolejka jest pusta, kończę odtwarzanie.")
        await voice.disconnect()
        return

    player = queue.pop(0)
    voice.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop))
    await ctx.send(f'Teraz leci: {player.title}')

# Komenda skip
@bot.command(name='skip')
async def skip(ctx):
    voice = ctx.voice_client
    if voice is None or not voice.is_playing():
        await ctx.send("Nic nie jest aktualnie odtwarzane.")
        return
    voice.stop()
    await ctx.send("Pominięto piosenkę.")

# Komenda pause
@bot.command(name='pause')
async def pause(ctx):
    voice = ctx.voice_client
    if voice is None or not voice.is_playing():
        await ctx.send("Nic nie jest aktualnie odtwarzane.")
        return
    voice.pause()
    await ctx.send("Zatrzymano odtwarzanie.")

# Komenda resume
@bot.command(name='resume')
async def resume(ctx):
    voice = ctx.voice_client
    if voice is None or not voice.is_paused():
        await ctx.send("Nic nie jest zatrzymane.")
        return
    voice.resume()
    await ctx.send("Wznowiono odtwarzanie.")

# Komenda stop
@bot.command(name='stop')
async def stop(ctx):
    voice = ctx.voice_client
    guild_id = ctx.guild.id
    queues[guild_id] = []
    if voice is None:
        await ctx.send("Nie jestem połączony z kanałem głosowym.")
        return
    voice.stop()
    await voice.disconnect()
    await ctx.send("Zatrzymano muzykę i rozłączono.")

# Komenda volume (ustawianie głośności 0.0 - 2.0)
@bot.command(name='volume')
async def volume(ctx, volume: float):
    voice = ctx.voice_client
    if voice is None or not voice.is_playing():
        await ctx.send("Nic nie jest aktualnie odtwarzane.")
        return
    if volume < 0 or volume > 2:
        await ctx.send("Podaj głośność w zakresie 0.0 - 2.0")
        return
    voice.source.volume = volume
    await ctx.send(f'Głośność ustawiona na {volume * 100:.0f}%')

# Komenda show queue (pokazuje kolejkę)
@bot.command(name='queue')
async def show_queue(ctx):
    guild_id = ctx.guild.id
    queue = get_queue(guild_id)
    if not queue:
        await ctx.send("Kolejka jest pusta.")
        return
    msg = "**Kolejka:**\n"
    for i, song in enumerate(queue, start=1):
        msg += f"{i}. {song.title}\n"
    await ctx.send(msg)

if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        print("Brak tokena! Sprawdź .env lub zmienne środowiskowe.")
        exit(1)
    bot.run(TOKEN)
