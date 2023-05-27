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

# guild_id = os.getenv('GUILD_ID')
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
    'outtmpl': 'audio_files/%(title)s-%(id)s.%(ext)s',
}

ffmpeg_opts = {
        'options': '-vn',
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 60'
    }


class HansBot(commands.Bot):
    def __init__(self, command_prefix, intents, **options):
        super().__init__(command_prefix=command_prefix, intents=intents, **options)
        self.current_song_title = None
        self.queue = {}
        self.music_channels = {}
        # self.play_lock = asyncio.Lock()  # Prevent attempting to play the same song twice, leading to an exception

    def remove_song_from_queue(self, guild_id, song):
        audio_id = song["id"]
        if guild_id in self.queue:
            for song in self.queue[guild_id]:
                if song['id'] == audio_id:
                    self.queue[guild_id].remove(song)

    def is_playing_in_channel(self, channel):
        for connected_voice in self.voice_clients:
            if connected_voice.is_playing() and connected_voice.channel.id == channel.id:
                return True
        return False

    def get_voice_client_for_channel(self, channel):
        for voice_client in self.voice_clients:
            if voice_client.channel.id == channel.id:
                return voice_client
        return None

    def seconds_to_mm_ss(self, duration_seconds):
        minutes = duration_seconds // 60
        seconds = duration_seconds % 60
        return f"{minutes:>02}:{seconds:>02}"

    async def setup_hook(self) -> None:
        # start the task to run in the background
        self.play_queue.start()

    @tasks.loop(seconds=5)
    async def play_queue(self):
        # Check if we should play something from the queue and update activity with the audio we are playing
        try:
            for guild_id, guild_queue in self.queue.items():
                for song in guild_queue:
                    channel = self.get_channel(song["voice_channel_id"])
                    voice_client = self.get_voice_client_for_channel(channel)
                    if not voice_client.is_playing():
                        audio_to_play = song["audio"]
                        voice_client = self.get_voice_client_for_channel(channel)
                        title = song["title"]
                        duration_fmt = self.seconds_to_mm_ss(song["duration"])

                        # Play the audio and post a helpful message
                        self.current_song_title = title
                        music_channel = self.get_channel(song["music_channel_id"])
                        msg = f"> ## **Now playing**\n" \
                              f"> # {title} _({duration_fmt})_\n" \
                              f"> _requested by {song['requested_by']}_\n" \
                              f"> _Queue length: {len(guild_queue)-1}_"

                        await music_channel.send(msg)
                        voice_client.play(audio_to_play, after=self.remove_song_from_queue(guild_id, song))

        except BaseException as e:
            logger.exception(f"Failed joining voice channel or playing audio: {e}")

        try:
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
                await bot.change_presence(activity=idle_activity)

        except BaseException as e:
            logger.exception(f"Failed setting activity: {e}")

    @play_queue.before_loop
    async def before_my_task(self):
        await self.wait_until_ready()  # wait until the bot logs in

    async def on_ready(self):
        await bot.change_presence(status=discord.Status.online)
        logger.info(f'Logged on as {bot.user}!')

    async def on_message(self, message):
        if message.author == self.user:
            return
        
        guild_id = message.guild.id 
        if message.guild.id not in self.queue:
            self.queue[guild_id] = []
            
        voice_client = None
        msg = message.content

        # Determine if this is a music channel
        channel_posted_in = message.channel
        if 'music' in channel_posted_in.topic.lower():
            music_channel_id = message.channel.id
            self.music_channels[guild_id] = music_channel_id
        else:
            return

        if message.author.voice:  # check if user is in a voice channel
            channel_id_user = message.author.voice.channel.id
        else:
            return

        if msg.startswith('!plæy') and music_channel_id:
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

                title = song_info['title']
                duration = song_info['duration']
                audio_id = f"{title}-{song_info['id']}"
                url_to_play = song_info["formats"][0]["url"]

                audio = discord.FFmpegPCMAudio(url_to_play, **ffmpeg_opts)

            except BaseException as e:
                logger.exception(f"Failed downloading from url '{url}': {e}")
                return

            try:
                # Join voice channel and play the downloaded audio
                channel = self.get_channel(channel_id_user)
                if not self.voice_clients:
                    voice_client = await channel.connect(timeout=300)
                else:
                    # When the bot is in multiple voice channels, use the channel that is in the same guild as
                    # the guild that the message was sent form
                    for connected_voice in self.voice_clients:
                        if connected_voice.guild.id == message.guild.id:
                            voice_client = connected_voice
                            break

                if not voice_client:
                    logger.error(f"Unable to fetch voice client.")
                    return
                
                num_in_queue = len(self.queue[guild_id])
                self.queue[guild_id].append({"url": url_to_play,
                                             "id": audio_id,
                                             "audio": audio,
                                             "voice_channel_id": channel_id_user,
                                             "music_channel_id": music_channel_id,
                                             "title": title,
                                             "duration": duration,
                                             "requested_by": message.author,
                                             "position": num_in_queue})

                logger.info(f"> Added '{title}' to queue")

                msg = f"> Added **{title}** to the queue (number #{num_in_queue+1} in queue)"
                music_channel = self.get_channel(music_channel_id)
                await music_channel.send(msg)
                await self.play_queue()

            except BaseException as e:
                logger.exception(f"Failed joining channel or playing audio: {e}")

    async def on_voice_state_update(self, member, before, after):
        # We should leave the voice channel if no-one else is in the channel
        if after.channel is not None:
            channel_with_update = after.channel
        else:
            channel_with_update = before.channel

        if self.voice_clients and channel_with_update:
            for connected_voice in self.voice_clients:
                # This is an update to a channel that we are currently playing audio in
                if channel_with_update.id == connected_voice.channel.id:
                    users_in_channel = [user.id for user in channel_with_update.members]
                    users_in_channel.remove(self.user.id)
                    if len(users_in_channel) == 0:
                        logger.info(f"Disconnecting from channel '{channel_with_update.name}' since all "
                                    f"users have left.")
                        guild_id = channel_with_update.guild.id
                        music_channel_id = self.music_channels.get(guild_id)
                        music_channel = self.get_channel(music_channel_id)
                        await music_channel.send(f"> All users have left, disconnecting now.")
                        await connected_voice.disconnect()

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

# TODO if download is True in ydl.extract_info(), this might be a more stable way to play the audio, but might be an issue with larger files
# song_path = str(song_info['title']) + "-" + str(song_info['id'] + ".mp3")
# voice.play(discord.FFmpegPCMAudio(song_path), after=lambda x: end_song(path))
# voice.source = discord.PCMVolumeTransformer(voice.source, 1)

if __name__ == '__main__':
    bot = HansBot(command_prefix='!H', intents=discord.Intents.all())
    bot.run(token, log_handler=handler, log_level=logging.INFO)


