import asyncio
import os
import logging
import aiohttp
import discord
import youtube_dl

from discord.ext import commands

# Set up logging
logger = logging.getLogger(__name__)
handler = logging.StreamHandler()

log_level = os.getenv('LOG_LEVEL')
level = logging.getLevelName(log_level.upper()) if log_level is not None else None

if not isinstance(level, int):
    logger.warning("Unsupported value or no LOG_LEVEL provided. Hence, setting default log level to INFO.")
    level = logging.INFO

formatter = logging.Formatter('[%(asctime)s] %(threadName)s - %(levelname)s: %(message)s',
                              "%Y-%m-%d %H:%M:%S")
handler.setFormatter(formatter)

logger.addHandler(handler)
logger.setLevel(level)

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!H', intents=intents)

guild_id = os.getenv('GUILD_ID')
token = os.getenv('DISCORD_TOKEN')


class MyLogger(object):
    def debug(self, msg):
        pass

    def warning(self, msg):
        pass

    def error(self, msg):
        print(msg)


class FilenameCollectorPP(youtube_dl.postprocessor.common.PostProcessor):
    def __init__(self):
        super(FilenameCollectorPP, self).__init__(None)
        self.filenames = []

    def run(self, information):
        self.filenames.append(information["filepath"])
        return [], information


def my_hook(d):
    if d['status'] == 'finished':
        print('Done downloading, now converting ...')


ydl_opts = {
    'format': 'bestaudio/best',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
    'logger': logger,
    'progress_hooks': [my_hook],
    'outtmpl': 'audio_files/%(title)s.%(ext)s',
}

ffmpeg_opts = {
        'options': '-vn'
    }


@bot.event
async def on_ready():
    await bot.change_presence(status=discord.Status.online)
    logger.info(f'Logged on as {bot.user}!')


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    msg = message.content
    channel_id_posted_in = message.channel.id
    channel_id_user = message.author.voice.channel.id

    if msg.startswith('!plæy') and channel_id_posted_in == 251107903291916290:  # our music channel id :)
        _split = msg.split()
        if len(_split) > 0:
            url = _split[1]
        else:
            logger.error(f"Could not parse url from message '{msg}'")
            return

        try:
            _ydl = youtube_dl.YoutubeDL(ydl_opts)
            filename_collector = FilenameCollectorPP()
            _ydl.add_post_processor(filename_collector)
            with _ydl as ydl:
                song_info = ydl.extract_info(url, download=False)
                logger.debug(song_info)

            # filenames = filename_collector.filenames
            # audio = discord.FFmpegPCMAudio(filename)

            audio = discord.FFmpegPCMAudio(song_info["formats"][0]["url"])

        except BaseException as e:
            logger.error(f"Failed downloading from url '{url}': {e}")
            return

        try:
            # Join voice channel and play the downloaded audio, indicate song title in the bot's activity
            channel = bot.get_channel(channel_id_user)
            voice = await channel.connect(timeout=300)

            activity = discord.Activity(type=discord.ActivityType.playing, name=song_info["title"])
            await bot.change_presence(activity=activity)

            voice.play(audio)

        except BaseException as e:
            logger.exception(f"Failed joining channel and/or playing audio: {e}")


@bot.event
async def on_typing(channel, member, when):
    logger.info(f"{member} is typing in channel '{channel}'")


# @bot.command(pass_context=True)
# async def join(ctx):
#     try:
#         if ctx.author.voice:
#             channel = ctx.message.author.voice.channel
#             await channel.connect()
#         else:
#             await ctx.send("You are not in a voice channel. Must be in a voice channel to run this command.")
#         # voice_client = await channel.connect()
#         # Do something with the voice_client
#
#     except BaseException as e:
#         print(f'An error occurred while joining the voice channel: {e}')
#
#
# @bot.command()
# async def leave(ctx):
#     voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)
#     if voice_client:
#         await voice_client.disconnect()


bot.run(token, log_handler=handler, log_level=logging.INFO)

