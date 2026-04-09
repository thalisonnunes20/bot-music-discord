import discord
discord.opus.load_opus('libopus.so.0')
from discord.ext import commands
import logging
import os
from dotenv import load_dotenv
import asyncio

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
MUSIC_CHANNEL_ID = int(os.getenv('MUSIC_CHANNEL_ID', 0))

# --- LOGGING ---
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)


@bot.event
async def on_ready():
    logging.info(f'✅ Bot conectado como {bot.user}')

    activity = discord.Activity(
        type=discord.ActivityType.playing,
        name='Use Chat 🔫∫comandos'
    )
    await bot.change_presence(status=discord.Status.online, activity=activity)

    channel = bot.get_channel(MUSIC_CHANNEL_ID)
    if channel:
        logging.info(f'🎵 Canal de música: #{channel.name} ({MUSIC_CHANNEL_ID})')
    else:
        logging.warning(f'⚠️ Canal {MUSIC_CHANNEL_ID} não encontrado! Verifique o .env')


@bot.event
async def on_message(message: discord.Message):
    """Intercepta mensagens no canal de música e envia para o player."""
    if message.author.bot:
        return

    if message.channel.id != MUSIC_CHANNEL_ID:
        await bot.process_commands(message)
        return

    music_cog = bot.cogs.get('Music')
    if music_cog:
        await music_cog.handle_song_request(message)


async def main():
    await bot.load_extension('cogs.music')
    await bot.start(TOKEN)


if __name__ == '__main__':
    asyncio.run(main())
