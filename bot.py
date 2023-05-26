import os
import discord

from discord.ext import commands

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!H', intents=intents)

# client = discord.Client(intents=intents)
guild_id = os.getenv('GUILD_ID')
token = os.getenv('DISCORD_TOKEN')

@bot.event
async def on_ready():
    await bot.change_presence(status=discord.Status.online)
    print(f'Logged on as {bot.user}!')


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if message.content.startswith('$'):
        reversed_message = message.content[1:][::-1]
        # await message.channel.send(reversed_message)


@bot.event
async def on_typing(channel, member, when):
    # message = discord.Message(channel=channel)
    await channel.send(f"Trykk Enter {member} :)")
    # await message.channel.send(f"Trykk Enter {member}")
    # await bot.close()  # close the client to stop the client blocking code
    # bot.send_message(channel, message)


# @bot.command(name='join')
# async def
# bot = MyClient(intents=intents, command_prefix='!H')


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
#
#


bot.run(token)

