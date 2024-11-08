import asyncio
import json
import os
import logging
import discord
import yt_dlp
import threading

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

token = os.getenv('DISCORD_TOKEN')
TASK_INTERVAL = 3


def my_hook(d):
    if d['status'] == 'finished':
        print('Done downloading, now converting ...')


ydl_opts = {
    'format': 'm4a/bestaudio/best',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'm4a'
    }],
    'logger': logger,
    'progress_hooks': [my_hook],
    'extract_flat': True,
    'rm_cachedir': True
}

ydl_opts_playlist = {
    'format': 'm4a/bestaudio/best',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'm4a'
    }],
    'logger': logger,
    'progress_hooks': [my_hook],
    'rm_cachedir': True
}


ffmpeg_opts = {
        'options': '-vn -http_persistent 0',
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
    }


class HansBot(commands.Bot):
    def __init__(self, command_prefix, intents, **options):
        super().__init__(command_prefix=command_prefix, intents=intents, **options)
        self.current_song = {}
        self.queue = {}
        self.music_channels = {}
        self.idle_time = {}
        self.task_interval = TASK_INTERVAL
        # self.play_lock = asyncio.Lock()  # Prevent attempting to play the same song twice, leading to an exception
        # self.play_lock = threading.Lock()

    async def on_ready(self):
        default_activity = discord.Activity(type=discord.ActivityType.playing, name="music with !plæy")
        await self.change_presence(activity=default_activity)
        for guild in self.guilds:
            self.queue[guild.id] = []
            self.idle_time[guild.id] = 0
            for channel in guild.channels:
                if isinstance(channel, discord.TextChannel) and channel.topic and 'music' in channel.topic.lower():
                    self.music_channels[guild.id] = channel.id
                    break

        logger.info(f'Logged on as {bot.user}!')

    async def add_song_to_queue(self, guild_id, song):
        num_in_queue = len(self.queue[guild_id])
        title = song['title']

        self.queue[guild_id].append(song)
        logger.info(f"> Added '{title}' to queue")
        msg = f"> Added **{title}** to the queue (number #{num_in_queue + 1} in queue)"
        music_channel = self.get_channel(song['music_channel_id'])
        await music_channel.send(msg)

        if self.play_queue.is_running() is False:
            self.play_queue.start()

    async def add_playlist_to_queue(self, guild_id, playlist):
        songs = playlist['songs']
        for song in songs:
            title = song['title']
            duration = song.get('duration')
            audio_id = f"{title}-{song['id']}"
            url_to_play = song["url"]

            audio_source = discord.FFmpegPCMAudio(url_to_play, **ffmpeg_opts)

            audio = {"url": url_to_play,
                     "id": audio_id,
                     "audio": audio_source,
                     "voice_channel_id": playlist['voice_channel_id'],
                     "music_channel_id": playlist['music_channel_id'],
                     "title": title,
                     "duration": duration,
                     "requested_by": playlist['requested_by']}

            await self.add_song_to_queue(guild_id, audio)

    async def remove_song_from_queue(self, guild_id, song):
        audio_id = song["id"]
        if guild_id in self.queue:
            for song in self.queue[guild_id]:
                if song['id'] == audio_id:
                    self.queue[guild_id].remove(song)

    async def clear_queue(self, guild_id):
        self.queue[guild_id] = []
        self.current_song[guild_id] = None

    def get_queue(self, guild_id):
        return self.queue.get(guild_id)

    def get_user_voice_channel(self, message):
        if message.author.voice:
            voice_channel_user = message.author.voice.channel
            if not voice_channel_user:
                return None
            else:
                return voice_channel_user
        else:
            return None

    def get_voice_client_for_channel(self, channel_id):
        if channel_id is None:
            logger.warning(f"Got channel id 'None' in get_voice_client_for_channel()")
            return None
        for voice_client in self.voice_clients:
            if voice_client.channel.id == channel_id:
                return voice_client
        return None

    def get_voice_client_for_guild(self, guild_id):
        if guild_id is None:
            logger.warning(f"Got guild id 'None' in get_voice_client_for_guild()")
            return None
        for voice_client in self.voice_clients:
            if voice_client.guild.id == guild_id:
                return voice_client
        return None

    def get_music_channel_for_guild(self, guild_id):
        music_channel_id = self.music_channels.get(guild_id)
        music_channel = self.get_channel(music_channel_id)
        return music_channel

    def is_playing_in_channel(self, channel_id):
        for connected_voice in self.voice_clients:
            if connected_voice.is_playing() and connected_voice.channel.id == channel_id:
                return True
        return False

    def is_in_guild_channel(self, guild_id):
        # Is the bot in any voice channels of the given guild?
        for connected_voice in self.voice_clients:
            if connected_voice.channel.guild == guild_id:
                return True
        return False

    def is_audio_playing_or_paused(self, voice_client):
        if not voice_client:
            return False
        else:
            if voice_client.is_playing() or voice_client.is_paused():
                return True
            else:
                return False

    def is_voice_channel_empty(self, channel):
        # Return True if the voice channel is empty (not including the bot itself)
        users_in_channel = [user.id for user in channel.members]
        if self.user.id in users_in_channel:
            users_in_channel.remove(self.user.id)

        if len(users_in_channel) == 0:
            return True
        else:
            return False

    def is_user_in_correct_voice_channel(self, message):
        msg_guild = message.guild
        if message.author.voice:
            voice_channel_id_user = message.author.voice.channel.id
            if not voice_channel_id_user:
                return False

            # Check if the bot is in the same voice channel, or if this is a channel that the bot needs to join
            bot_voice_channel = bot.get_voice_client_for_channel(voice_channel_id_user)

            # The user is not in the same voice channel
            if not bot_voice_channel:
                if not bot.is_in_guild_channel(msg_guild.id):
                    # The bot is not in any voice channels for the given guild
                    return True
                else:
                    logger.warning(f"I'm already in a voice channel.")
                    return False
            else:
                return True
        else:
            return False

    def is_message_in_music_channel(self, message):
        channel_posted_in = message.channel
        if channel_posted_in.id == self.music_channels.get(message.guild.id):
            return True
        else:
            return False

    def seconds_to_mm_ss(self, duration_seconds):
        minutes = duration_seconds // 60
        seconds = duration_seconds % 60
        return f"{minutes:>02}:{seconds:>02}"

    # async def setup_hook(self) -> None:
        # start the task to run in the background
        # self.play_queue.start()

    @tasks.loop(seconds=TASK_INTERVAL)
    async def play_queue(self, set_presence=False):
        # Check if we should play something from the queue and update activity with the audio we are playing
        try:
            for guild_id, guild_queue in self.queue.items():
                if not guild_queue:
                    voice_client = self.get_voice_client_for_guild(guild_id)
                    if not self.is_audio_playing_or_paused(voice_client):
                        self.current_song[guild_id] = None

                # for song in guild_queue:
                if len(guild_queue) > 0:
                    song = guild_queue[0]
                    channel_song_id = song["voice_channel_id"]
                    channel_song = self.get_channel(channel_song_id)
                    voice_client_song = self.get_voice_client_for_channel(channel_song_id)
                    voice_client_guild = self.get_voice_client_for_guild(channel_song.guild.id)

                    if voice_client_guild:
                        # Switch voice channel if the voice channel we are using in the guild is not playing anything
                        # and if there is no voice client for the current song
                        if not self.is_audio_playing_or_paused(voice_client_guild) and not voice_client_song:
                            music_channel = self.get_music_channel_for_guild(channel_song.guild.id)
                            msg = f"> Switching to voice channel '{channel_song.name}'"
                            await music_channel.send(msg)
                            await voice_client_guild.disconnect()
                            voice_client = await channel_song.connect(timeout=60)
                        else:
                            # Keep using the same voice client
                            voice_client = voice_client_guild
                    else:
                        voice_client = voice_client_song

                    if not voice_client:
                        voice_client = await channel_song.connect(timeout=60)

                    if not self.is_audio_playing_or_paused(voice_client_guild):
                        audio_to_play = song["audio"]
                        title = song["title"]

                        # Play the audio and post a helpful message
                        music_channel = self.get_channel(song["music_channel_id"])
                        msg = f"> ## **Now playing:**\n"
                        if song.get('duration'):
                            duration_fmt = self.seconds_to_mm_ss(song["duration"])
                            msg += f"> # {title} _({duration_fmt})_\n"
                        else:
                            msg += f"> # {title})\n"

                        msg += f"> _requested by {song['requested_by']}_\n"

                        self.current_song[guild_id] = song
                        self.idle_time[guild_id] = 0
                        await music_channel.send(msg)
                        voice_client.play(audio_to_play, after=await self.remove_song_from_queue(guild_id, song))

        except BaseException as e:
            logger.exception(f"Failed joining voice channel or playing audio: {e}")

        # Add to idle timer if we are connected but not playing anything
        # TODO rough estimate, should use an actual timer instead of the task loop interval
        guild_ids = list(self.music_channels.keys())
        for guild_id in guild_ids:
            guild = self.get_guild(guild_id)
            voice_client = self.get_voice_client_for_guild(guild.id)

            if voice_client:  # if there is no voice client, we are not connected, so it doesn't make sense to add time
                is_playing = self.is_audio_playing_or_paused(voice_client)
                if not is_playing:
                    self.idle_time[guild_id] += self.task_interval
                    # logger.debug(f"({guild.name}) Idle for {self.idle_time[guild_id]} seconds")

        # We should leave the voice channel if no-one else is in the channel and there is nothing to play,
        # or if we have been idle for a certain amount of time
        for connected_voice in self.voice_clients:
            guild_id = connected_voice.guild.id
            channel = connected_voice.channel
            is_channel_empty = self.is_voice_channel_empty(channel)
            is_playing = self.is_audio_playing_or_paused(connected_voice)
            is_queue_empty = True if not self.queue[guild_id] else False

            if not is_playing and is_queue_empty:
                music_channel_id = self.music_channels.get(guild_id)
                music_channel = self.get_channel(music_channel_id)

                if self.idle_time[guild_id] > 600:
                    await music_channel.send(f"> Disconnecting due to inactivity.")
                    await connected_voice.disconnect()
                    self.idle_time[guild_id] = 0   # reset timer

                elif is_channel_empty:
                    await music_channel.send(f"> All users have left and the queue is empty, disconnecting now.")
                    await connected_voice.disconnect()

        if set_presence:
            try:
                idle_activity = discord.Activity(type=discord.ActivityType.playing, name="nothing at the moment")
                if self.current_song:
                    voice_clients = self.voice_clients
                    if not voice_clients:
                        await bot.change_presence(activity=idle_activity)
                    else:
                        for voice in voice_clients:
                            if voice.is_playing():
                                activity = discord.Activity(type=discord.ActivityType.playing,
                                                            name=self.current_song['title'])
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

    async def on_typing(self, channel, member, when):
        logger.info(f"{member} is typing in channel '{channel}' ({channel.guild.name})")


bot = HansBot(command_prefix='!', intents=discord.Intents.all())


@bot.command()
async def plæy(ctx):
    message = ctx.message
    if message.author == bot.user:
        return

    if not command_is_valid(ctx):
        return

    msg = message.content
    guild_id = message.guild.id

    music_channel_id = bot.music_channels.get(guild_id)
    voice_channel_id_user = message.author.voice.channel.id

    _split = msg.split()
    if len(_split) > 0:
        url = _split[1]
    else:
        logger.error(f"Could not parse url from message '{msg}'")
        return

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            song_info = ydl.extract_info(url, download=False)

        _type = song_info.get('_type')
        if _type == 'playlist':
            playlist_title = song_info['title']
            num_songs = len(song_info['entries'])
            msg = f"> Adding {num_songs} songs from playlist **{playlist_title}** to queue"
            music_channel = bot.get_channel(music_channel_id)
            await music_channel.send(msg)

            voice_client = bot.get_voice_client_for_guild(guild_id)
            if not voice_client:
                channel = bot.get_channel(voice_channel_id_user)
                await channel.connect(timeout=60)

            # We need to extract info again, with options that fetch all videos in the playlist
            with yt_dlp.YoutubeDL(ydl_opts_playlist) as ydl:
                song_info = ydl.extract_info(url, download=False)

            playlist = {'title': playlist_title,
                        'songs': song_info['entries'],
                        'voice_channel_id': voice_channel_id_user,
                        'music_channel_id': music_channel_id,
                        "requested_by": message.author}
            await bot.add_playlist_to_queue(guild_id, playlist)

        else:  # just one song
            song = song_info
            title = song['title']
            duration = song.get('duration')
            audio_id = f"{title}-{song['id']}"
            url_to_play = song["url"]

            audio_source = discord.FFmpegPCMAudio(url_to_play, **ffmpeg_opts)

            audio = {"url": url_to_play,
                     "id": audio_id,
                     "audio": audio_source,
                     "voice_channel_id": voice_channel_id_user,
                     "music_channel_id": music_channel_id,
                     "title": title,
                     "duration": duration,
                     "requested_by": message.author}

            await bot.add_song_to_queue(guild_id, audio)

    except BaseException as e:
        logger.exception(f"Failed downloading or adding to queue using url '{url}': {e}")
        return


def command_is_valid(ctx):
    # Determine if this was posted in the guild's music channel and if user is in voice
    user_is_in_voice = bot.is_user_in_correct_voice_channel(message=ctx)
    msg_in_music_channel = bot.is_message_in_music_channel(message=ctx)

    if not user_is_in_voice:
        logger.info(f"User is not in the correct voice channel.")
        return False

    if not msg_in_music_channel:
        logger.info(f"Command was not posted in a music channel.")
        return False

    return True


@bot.command()
async def skip(ctx):
    if not command_is_valid(ctx):
        return

    user_voice_channel = ctx.author.voice.channel

    bot_voice_client = bot.get_voice_client_for_channel(user_voice_channel.id)
    if bot_voice_client:
        bot_voice_client.stop()
    else:
        music_channel = bot.get_music_channel_for_guild(ctx.guild.id)
        msg = f"> I'm not playing anything in voice channel '{user_voice_channel}'."
        await music_channel.send(msg)


@bot.command()
async def stop(ctx):
    if not command_is_valid(ctx):
        return

    # Clear the queue and stop playing audio
    user_voice_channel = bot.get_user_voice_channel(message=ctx)
    is_playing = bot.is_playing_in_channel(user_voice_channel.id)
    music_channel = bot.get_music_channel_for_guild(ctx.guild.id)

    if is_playing and bot.is_message_in_music_channel(message=ctx):
        await bot.clear_queue(ctx.guild.id)
        await skip(ctx)
        msg = f"> Cleared queue and stopped playing music."
        await music_channel.send(msg)


@bot.command()
async def pause(ctx):
    if not command_is_valid(ctx):
        return

    music_channel = bot.get_music_channel_for_guild(ctx.guild.id)
    voice_client = bot.get_voice_client_for_guild(ctx.guild.id)
    if voice_client and voice_client.is_playing():
        voice_client.pause()
        msg = f"> Paused playback, use **!resume** to resume playback."
        await music_channel.send(msg)
    else:
        logger.info(f"I'm not playing anything right now.")


@bot.command()
async def resume(ctx):
    if not command_is_valid(ctx):
        return

    music_channel = bot.get_music_channel_for_guild(ctx.guild.id)
    voice_client = bot.get_voice_client_for_guild(ctx.guild.id)
    if not voice_client:
        return

    if voice_client and not voice_client.is_playing():
        audio_source = voice_client.source
        if audio_source:
            voice_client.resume()
            msg = f"> Resumed playback."
            await music_channel.send(msg)
        else:
            msg = f"> There is nothing to play."
            await music_channel.send(msg)
    else:
        msg = f"> I'm already playing something."
        await music_channel.send(msg)


@bot.command()
async def disconnect(ctx):
    if not command_is_valid(ctx):
        return

    voice_client = bot.get_voice_client_for_guild(ctx.guild.id)
    if voice_client:
        await voice_client.disconnect()
        await bot.clear_queue(ctx.guild.id)


@bot.command()
async def queue(ctx):
    guild_queue = bot.get_queue(ctx.guild.id)
    readable_queue = []
    music_channel = bot.get_music_channel_for_guild(ctx.guild.id)
    current_audio = bot.current_song.get(ctx.guild.id)
    if current_audio:
        title = current_audio["title"]
        requested_by = current_audio['requested_by']
        playing_element = f"## **Currently playing:**\n "
        if current_audio.get('duration'):
            duration_fmt = bot.seconds_to_mm_ss(current_audio["duration"])
            playing_element += f"**{title}** _({duration_fmt})_\n" \
                               f"    _requested by {requested_by}_\n"
        else:
            playing_element += f"**{title}**_\n" \
                               f"    _requested by {requested_by}_\n"

        readable_queue.append(playing_element)

    readable_queue.append(f"## **Queue:**\n")

    for i, audio in enumerate(guild_queue):
        pos = i + 1
        if audio.get('duration'):
            duration_fmt = bot.seconds_to_mm_ss(audio['duration'])
            queue_element = f"**{pos}.** **{audio['title']}** _({duration_fmt})_\n" \
                            f"    _requested by {audio['requested_by']}_\n"
        else:
            queue_element = f"**{pos}. {audio['title']}**\n" \
                            f"    _requested by {audio['requested_by']}_"

        readable_queue.append(queue_element)

    if not readable_queue:
        msg = f"> The queue is empty."
    else:
        msg = ">>> %s" % '\n'.join(readable_queue)

    try:
        await music_channel.send(msg)
    except discord.errors.HTTPException:
        # The message is too long, truncate it to show first 5 and last 5 songs in the queue
        truncated_queue = readable_queue[0:7] + ['......\n'] + readable_queue[-5:]
        msg = ">>> %s" % '\n'.join(truncated_queue)
        await music_channel.send(msg)


@bot.command()
async def playing(ctx):
    music_channel = bot.get_music_channel_for_guild(ctx.guild.id)
    current_audio = bot.current_song.get(ctx.guild.id)
    if current_audio:
        title = current_audio["title"]
        requested_by = current_audio['requested_by']
        playing_element = f"## **Currently playing:**\n "
        if current_audio.get('duration'):
            duration_fmt = bot.seconds_to_mm_ss(current_audio["duration"])
            playing_element += f"**{title}** _({duration_fmt})_\n" \
                               f"    _requested by {requested_by}_"
        else:
            playing_element += f"**{title}**_\n" \
                               f"    _requested by {requested_by}_"

        msg = f"> {playing_element}"
    else:
        msg = f"> I'm not playing anything currently."

    await music_channel.send(msg)


@bot.command()
async def whomst(ctx):
    music_channel = bot.get_music_channel_for_guild(ctx.guild.id)
    if not bot.is_message_in_music_channel(message=ctx):
        return

    where = os.environ.get('WHERE', 'unknown')
    await music_channel.send(f'> {where}')


if __name__ == '__main__':
    bot.run(token, log_handler=handler, log_level=logging.INFO)


