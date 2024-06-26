from discord.ext import commands, tasks
from discord import app_commands
import discord
import asyncio

class Reddit(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.get_config.start()

    async def cog_load(self):
        self.subreddit = await self.bot.reddit.subreddit("PhoenixSC")

    @tasks.loop(minutes=10)
    async def get_config(self):
        self.removal_reasons = []
        async for reason in self.subreddit.mod.removal_reasons:
            self.removal_reasons += reason
        print(self.removal_reasons)

    @get_config.error
    async def get_config_error(self):
        await asyncio.sleep(60)
        self.get_config.start()

async def setup(bot):
    await bot.add_cog(Reddit(bot))