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

    def remove_song_from_queue(self, guild_id, song):
        if guild_id in self.queue:
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

    async def setup_hook(self) -> None:
        # start the task to run in the background
        self.play_queue.start()

    @tasks.loop(seconds=5)
    async def play_queue(self):
        # Check if we should play something from the queue and update activity with the audio we are playing
        # voice_clients = self.voice_clients
        for guild_id, guild_queue in self.queue.items():
            # sorted_guild_queue = sorted(list(self.queue[guild_id].values()), key=lambda _audio: _audio['position'])
            for song in guild_queue:
                channel = self.get_channel(song["voice_channel_id"])
                playing_in_channel = self.is_playing_in_channel(channel)
                if not playing_in_channel:
                    audio_to_play = song["audio"]
                    voice_client = self.get_voice_client_for_channel(channel)
                    self.current_song_title = song["title"]
                    voice_client.play(audio_to_play, after=self.remove_song_from_queue(guild_id, song))

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
        else:
            return

        channel_id_user = message.author.voice.channel.id

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

                audio_id = f"{song_info['title']}-{song_info['id']}"
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

                # TODO if download is True in ydl.extract_info(), this might be a more stable way to play the audio, but might be an issue with larger files
                # song_path = str(song_info['title']) + "-" + str(song_info['id'] + ".mp3")
                # voice.play(discord.FFmpegPCMAudio(song_path), after=lambda x: end_song(path))
                # voice.source = discord.PCMVolumeTransformer(voice.source, 1)
                
                num_in_queue = len(self.queue[guild_id])  # logger.info(f"Added {'song_info["title"]}' to queue")
                self.queue[guild_id].append({"url": url_to_play,
                                             "id": audio_id,
                                             "audio": audio,
                                             "voice_channel_id": channel_id_user,
                                             "title": song_info["title"],
                                             "position": num_in_queue})
                await self.play_queue()
                
                # if voice_client.is_playing():
                #     logger.info(f"Already playing audio, adding requested audio to queue...")
                #     if audio_id and url_to_play:
                #         position = len(self.queue)
                #         # position = num_in_queue + 1
                #         self.queue[guild_id][audio_id] = {"url": url_to_play,
                #                                           "title": song_info["title"],
                #                                           "position": position}
                # else:
                #     self.queue[guild_id][audio_id] = {"url": url_to_play,
                #                                       "title": song_info["title"],
                #                                       "position": 0}
                #     
                #     self.current_song_title = song_info["title"]
                #     voice_client.play(audio, after=self.remove_song_from_queue(audio_id))

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

if __name__ == '__main__':
    bot = HansBot(command_prefix='!H', intents=discord.Intents.all())
    bot.run(token, log_handler=handler, log_level=logging.INFO)

