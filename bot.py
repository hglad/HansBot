import asyncio
import os
import logging
import aiohttp
import discord
import youtube_dl

from discord.ext import commands, tasks

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

guild_id = os.getenv('GUILD_ID')
token = os.getenv('DISCORD_TOKEN')


class MyLogger(object):
    def debug(self, msg):
        pass

    def warning(self, msg):
        pass

    def error(self, msg):
        print(msg)


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
        'options': '-vn',
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
    }


class HansBot(commands.Bot):
    def __init__(self, command_prefix, intents, **options):
        super().__init__(command_prefix=command_prefix, intents=intents, **options)
        self.current_song_title = None

    async def setup_hook(self) -> None:
        # start the task to run in the background
        self.update_presence.start()

    @tasks.loop(seconds=10)
    async def update_presence(self):
        idle_activity = discord.Activity(type=discord.ActivityType.playing, name="nothing at the moment")
        if self.current_song_title:
            voice_clients = self.voice_clients
            if not voice_clients:
                await bot.change_presence(activity=idle_activity)
            else:
                for voice in voice_clients:
                    if voice.is_playing():
                        activity = discord.Activity(type=discord.ActivityType.playing, name=self.current_song_title)
                        await bot.change_presence(activity=activity)
                        return

                await bot.change_presence(activity=idle_activity)
        else:
            idle_activity = discord.Activity(type=discord.ActivityType.playing, name="nothing at the moment")
            await bot.change_presence(activity=idle_activity)

    @update_presence.before_loop
    async def before_my_task(self):
        await self.wait_until_ready()  # wait until the bot logs in

    async def on_ready(self):
        await bot.change_presence(status=discord.Status.online)
        logger.info(f'Logged on as {bot.user}!')

    async def on_message(self, message):
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
                with _ydl as ydl:
                    song_info = ydl.extract_info(url, download=False)
                    logger.debug(song_info)

                audio = discord.FFmpegPCMAudio(song_info["formats"][0]["url"], **ffmpeg_opts)

            except BaseException as e:
                logger.error(f"Failed downloading from url '{url}': {e}")
                return

            try:
                # Join voice channel and play the downloaded audio, indicate song title in the bot's activity
                channel = bot.get_channel(channel_id_user)
                voice = await channel.connect(timeout=300)

                self.current_song_title = song_info["title"]
                voice.play(audio)

            except BaseException as e:
                logger.exception(f"Failed joining channel and/or playing audio: {e}")

    async def on_typing(self, channel, member, when):
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

if __name__ == '__main__':
    bot = HansBot(command_prefix='!H', intents=discord.Intents.all())
    bot.run(token, log_handler=handler, log_level=logging.INFO)

