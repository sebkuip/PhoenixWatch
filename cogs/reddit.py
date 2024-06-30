from __future__ import annotations

import asyncio
import typing
from datetime import datetime

import asyncpraw
import asyncpraw.models
import discord
from discord import app_commands
from discord.ext import commands, tasks

from PhoenixWatch import PhoenixWatchBot


class RemovalModal(discord.ui.Modal, title="Reason to remove"):
    def __init__(self, entry, reason, modqueue, message):
        self.entry = entry
        self.reason = reason
        self.modqueue = modqueue
        self.original_message = message

        super().__init__()

        self.removal_text = discord.ui.TextInput(
            label="What text to comment for removal:",
            style=discord.TextStyle.long,
            default=self.reason.message,
            required=False,
            max_length=500,
        )
        self.add_item(self.removal_text)

    async def on_submit(self, interaction: discord.Interaction):
        if len(self.removal_text.value) != 0:
            mod_comment = await self.entry.reply(self.removal_text.value)
            await mod_comment.mod.distinguish(how="yes", sticky=True)
            await mod_comment.mod.lock()
        await self.entry.mod.remove()
        del self.modqueue[self.entry]
        await self.original_message.delete()
        await interaction.response.send_message("removed entry", ephemeral=True)


class RemovalDropdown(discord.ui.Select):
    def __init__(self, entry, reasons, modqueue, message):
        self.entry = entry
        self.reasons = reasons
        self.modqueue = modqueue
        self.original_message = message
        options = [
            discord.SelectOption(label=reason.title, value=i)
            for i, reason in enumerate(reasons)
        ]

        super().__init__(
            placeholder="Select removal reason",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(
            RemovalModal(
                self.entry,
                self.reasons[int(self.values[0])],
                self.modqueue,
                self.original_message,
            )
        )


class RemovalDropdownView(discord.ui.View):
    def __init__(self, entry, reasons, modqueue, message):
        super().__init__()

        self.add_item(RemovalDropdown(entry, reasons, modqueue, message))


# If we ever make the messages not delete
# class ApproveButton(discord.ui.DynamicItem[discord.ui.Button], template=r'approve:(?P<post>t3_[a-z0-9]+)'):
class ModqueueView(discord.ui.View):
    def __init__(self, modqueue, entry):
        self.modqueue = modqueue
        self.entry = entry
        super().__init__(timeout=None)

    @discord.ui.button(label="approve", style=discord.ButtonStyle.green)
    async def approve(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self.entry.mod.approve()
        del self.modqueue[self.entry]
        await interaction.message.delete()
        await interaction.response.send_message(
            "approved message", ephemeral=True, delete_after=10
        )

    @discord.ui.button(label="quick remove", style=discord.ButtonStyle.red)
    async def quick_remove(self, interaction: discord.Interaction, _):
        await self.entry.mod.remove()
        del self.modqueue[self.entry]
        await interaction.message.delete()
        await interaction.response.send_message(
            "removed entry without removal reason", ephemeral=True, delete_after=10
        )


class Reddit(commands.Cog):
    def __init__(self, bot: PhoenixWatchBot):
        self.bot = bot
        self.get_config.start()
        self.get_modqueue.start()
        self.get_modmail.start()

        self.modqueue: dict[
            typing.Union[asyncpraw.models.Submission, asyncpraw.models.Comment],
            discord.Message,
        ] = {}

        self.approve_ctx_menu = app_commands.ContextMenu(
            name="Approve a modqueue entry", callback=self.approve_entry
        )
        self.bot.tree.add_command(self.approve_ctx_menu)
        self.remove_ctx_menu = app_commands.ContextMenu(
            name="Remove a modqueue entry", callback=self.remove_entry
        )
        self.bot.tree.add_command(self.remove_ctx_menu)

    async def cog_load(self):
        self.subreddit = await self.bot.reddit.subreddit("PhoenixSC")
        await self.bot.modqueue_channel.purge(limit=5000)
        await self.bot.important_modqueue_channel.purge(limit=1000)

    @tasks.loop(minutes=10)
    async def get_config(self):
        self.removal_reasons = [
            reason async for reason in self.subreddit.mod.removal_reasons
        ]

    @get_config.error
    async def get_config_error(self):
        await asyncio.sleep(60)
        self.get_config.start()

    def create_modqueue_item_embed(
        self, entry: typing.Union[asyncpraw.models.Submission, asyncpraw.models.Comment]
    ) -> discord.Embed:
        if isinstance(entry, asyncpraw.models.Submission):
            embed = discord.Embed(
                color=discord.Color.dark_red(),
                title=entry.title,
                url=f"https://www.reddit.com{entry.permalink}",
                description=entry.selftext[:4000],
                timestamp=datetime.fromtimestamp(entry.created_utc),
            )
            if not entry.is_self:
                if entry.url.find("i.redd.it") == -1:
                    embed.add_field(name="link", value=entry.url, inline=False)
                else:
                    embed.set_image(url=entry.url)
        else:
            embed = discord.Embed(
                color=discord.Color.dark_gold(),
                title=f'Comment on post "{entry.link_title}"',
                url=f"https://www.reddit.com{entry.permalink}",
                description=entry.body[:4000],
                timestamp=datetime.fromtimestamp(entry.created_utc),
            )
        if entry.author:
            embed.set_author(name=f"/u/{entry.author.name}")
        else:
            embed.set_author(name="deleted user")

        embed.add_field(
            name="Reports",
            value="\n".join(
                (
                    f" • {report[0]}"
                    for report in (*entry.user_reports, *entry.mod_reports)
                )
            )[:1024]
            or "No reports",
        )
        return embed

    def is_entry_urgent(self, entry):
        return len(entry.user_reports) > 0

    @tasks.loop(minutes=1)
    async def get_modqueue(self):
        items = [item async for item in self.subreddit.mod.modqueue(limit=None)]

        for entry in self.modqueue.keys() - items:
            await self.modqueue[entry].delete()
            del self.modqueue[entry]

        for entry in items - self.modqueue.keys():
            channel = (
                self.bot.modqueue_channel
                if not self.is_entry_urgent(entry)
                else self.bot.important_modqueue_channel
            )

            embed = self.create_modqueue_item_embed(entry)
            view = ModqueueView(self.modqueue, entry)

            message = await channel.send(embed=embed, view=view)
            self.modqueue[entry] = message

    @get_modqueue.error
    async def get_modqueue_error(self, err):
        print("modqueue error", err)
        await asyncio.sleep(60)
        self.get_modqueue.start()

    async def approve_entry(
        self, interaction: discord.Interaction, message: discord.Message
    ):
        if message.channel.id not in (
            self.bot.modqueue_channel.id,
            self.bot.important_modqueue_channel.id,
        ):
            await interaction.response.send_message(
                "You can only use this in the modqueue channel", ephemeral=True
            )
            return

        entry = list(self.modqueue.keys())[list(self.modqueue.values()).index(message)]
        await entry.mod.approve()
        del self.modqueue[entry]
        await message.delete()
        await interaction.response.send_message(
            "approved message", ephemeral=True, delete_after=10
        )

    async def remove_entry(
        self, interaction: discord.Interaction, message: discord.Message
    ):
        if message.channel.id not in (
            self.bot.modqueue_channel.id,
            self.bot.important_modqueue_channel.id,
        ):
            await interaction.response.send_message(
                "You can only use this in the modqueue channel", ephemeral=True
            )
            return

        entry = list(self.modqueue.keys())[list(self.modqueue.values()).index(message)]
        await interaction.response.send_message(
            "please select the removal reason",
            view=RemovalDropdownView(
                entry, self.removal_reasons, self.modqueue, message
            ),
            ephemeral=True,
        )

    async def create_modmail_embed(
        self, modmail: asyncpraw.models.ModmailConversation
    ) -> discord.Embed:
        await modmail.load()
        author_found = False
        try:
            await modmail.participant.load()
            author_found = True
        except Exception:
            pass
        if modmail.num_messages == 1:
            embed = discord.Embed(
                title=f"new modmail: {modmail.subject[:100]}",
                description=modmail.messages[-1].body_markdown[:4000],
                url=f"https://mod.reddit.com/mail/all/{modmail.id}/",
                color=discord.Color.blurple(),
            )
        else:
            embed = discord.Embed(
                title=f"new reply: {modmail.subject[:100]}",
                description=modmail.messages[-1].body_markdown[:4000],
                url=f"https://mod.reddit.com/mail/all/{modmail.id}/",
                color=discord.Color.gold(),
            )
        if author_found:
            embed.set_author(
                name=modmail.participant.name, icon_url=modmail.participant.icon_img
            )
        else:
            embed.set_author(name="Deleted user")
        return embed

    @tasks.loop(minutes=1)
    async def get_modmail(self):
        new_conversations: typing.AsyncIterator[
            asyncpraw.models.ModmailConversation
        ] = self.subreddit.modmail.conversations(sort="unread", state="all")

        async for conv in new_conversations:
            if conv.last_unread is None:
                break
            embed = await self.create_modmail_embed(conv)
            await self.bot.modmail_channel.send(embed=embed)
            await conv.read()

        appeals_conversations: typing.AsyncIterator[
            asyncpraw.models.ModmailConversation
        ] = self.subreddit.modmail.conversations(sort="unread", state="appeals")
        async for conv in appeals_conversations:
            if conv.last_unread is None:
                break
            embed = await self.create_modmail_embed(conv)
            await self.bot.modmail_channel.send(embed=embed)
            await conv.read()

    @get_modmail.error
    async def get_modqueue_error(self, err):
        print("modmail error", err)
        await asyncio.sleep(60)
        self.get_modmail.start()


async def setup(bot):
    await bot.add_cog(Reddit(bot))
