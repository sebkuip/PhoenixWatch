import os
import time

import asyncpraw
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv(".env", override=True)
TOKEN = os.getenv("TOKEN")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDDIT_USERNAME = os.getenv("REDDIT_USERNAME")
REDDIT_PASSWORD = os.getenv("REDDIT_PASSWORD")
GUILD_ID = os.getenv("GUILD_ID")
MODCHANNEL_ID = os.getenv("MODCHANNEL_ID")
MODMAIL_CHANNEL_ID = os.getenv("MODMAIL_CHANNEL_ID")
IMPORTANT_QUEUE_CHANNEL_ID = os.getenv("IMPORTANT_QUEUE_CHANNEL_ID")


class PhoenixWatchBot(commands.Bot):
    reddit: asyncpraw.Reddit
    mod_guild: discord.Guild
    modqueue_channel: discord.TextChannel
    modmail_channel: discord.TextChannel
    important_modqueue_channel: discord.TextChannel


bot = PhoenixWatchBot(
    command_prefix="!", intents=discord.Intents.all(), help_command=None
)


async def connect_reddit():
    bot.reddit = asyncpraw.Reddit(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        username=REDDIT_USERNAME,
        password=REDDIT_PASSWORD,
        user_agent="Moderation bot for r/phoenixsc",
    )


@bot.event
async def on_ready():
    await connect_reddit()
    bot.mod_guild = await bot.fetch_guild(GUILD_ID)
    bot.modqueue_channel = await bot.mod_guild.fetch_channel(MODCHANNEL_ID)
    bot.modmail_channel = await bot.mod_guild.fetch_channel(MODMAIL_CHANNEL_ID)
    bot.important_modqueue_channel = await bot.mod_guild.fetch_channel(
        IMPORTANT_QUEUE_CHANNEL_ID
    )

    assert bot.mod_guild
    assert bot.modqueue_channel
    assert bot.modmail_channel
    assert bot.important_modqueue_channel

    print(f"{bot.user} has connected to Discord!")
    print(f"Username is {bot.user.name}")
    print(f"ID is {bot.user.id}")
    print(f"reddit account is {await bot.reddit.user.me()}")
    print(f"Keep this window open to keep the bot running.")

    await load_extensions()


@bot.command(name="sync", help="sync the command tree")
@commands.is_owner()
async def sync(ctx: commands.Context):
    await bot.tree.sync()
    await ctx.send(
        embed=discord.Embed(
            description="command tree synced", color=discord.Color.blurple()
        )
    )


@bot.hybrid_command(name="hug", description="Give someone a big squeeze")
async def hug(ctx: commands.Context, user: discord.User):
    if ctx.user == user:
        embed = discord.Embed(description=f"{user.display_name} hugged themselves")
    else:
        embed = discord.Embed(
            description=f"{ctx.user.display_name} 🫂 {user.display_name}"
        )
    await ctx.reply(embed=embed)


@bot.hybrid_command(
    name="ping", description="Shows the latency the bot is experiencing"
)
async def ping(ctx: commands.Context):
    before = time.perf_counter()
    msg = await ctx.reply("testing...")
    await msg.edit(
        content=f"pong!\nbot latency: {round((time.perf_counter() - before) * 1000)}ms\nwebsocket latency: {round(bot.latency * 1000)}ms"
    )


async def load_extensions():
    if __name__ == "__main__":
        status = {}
        for extension in os.listdir("./cogs"):
            if extension.endswith(".py"):
                status[extension] = "X"
        errors = []

        for extension in status:
            if extension.endswith(".py"):
                try:
                    await bot.load_extension(f"cogs.{extension[:-3]}")
                    status[extension] = "L"
                except Exception as e:
                    errors.append(e)

        maxlen = max(len(str(extension)) for extension in status)
        for extension in status:
            print(f" {extension.ljust(maxlen)} | {status[extension]}")
        print(errors) if errors else print("no errors during loading")
        await bot.load_extension("jishaku")


if __name__ == "__main__":
    bot.run(TOKEN)
