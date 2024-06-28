import os
import time

import asyncpraw
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv(".env")
TOKEN = os.getenv("TOKEN")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")
GUILD_ID = os.getenv("GUILD_ID")
MODCHANNEL_ID = os.getenv("MODCHANNEL_ID")


class PhoenixWatchBot(commands.Bot):
    reddit: asyncpraw.Reddit
    mod_guild: discord.Guild
    modqueue_channel: discord.TextChannel


bot = PhoenixWatchBot(
    command_prefix="!", intents=discord.Intents.all(), help_command=None
)


async def connect_reddit():
    bot.reddit = asyncpraw.Reddit(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        username=USERNAME,
        password=PASSWORD,
        user_agent="Moderation bot for r/phoenixsc",
    )


@bot.event
async def on_ready():
    await connect_reddit()
    bot.mod_guild = await bot.fetch_guild(GUILD_ID)
    bot.modqueue_channel = await bot.mod_guild.fetch_channel(MODCHANNEL_ID)
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


@bot.tree.command(name="hug", description="Give someone a big squeeze")
async def hug(interaction: discord.Interaction, user: discord.User):
    if interaction.user == user:
        embed = discord.Embed(description=f"{user.display_name} hugged themselves")
    else:
        embed = discord.Embed(
            description=f"{interaction.user.display_name} 🫂 {user.display_name}"
        )
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="ping", description="Shows the latency the bot is experiencing")
async def ping(interaction: discord.Interaction):
    before = time.perf_counter()
    await interaction.response.send_message("testing...")
    await interaction.edit_original_response(
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


bot.run(TOKEN)
