import asyncio
import logging
import os

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

intents = discord.Intents.default()

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
):
    if isinstance(error, app_commands.MissingPermissions):
        message = "このコマンドを実行するには「サーバー管理」権限が必要です。"
    else:
        message = "コマンドの実行中にエラーが発生しました。"
        logger.exception("Unhandled app command error", exc_info=error)

    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)


@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")


async def main():
    if not TOKEN:
        raise RuntimeError("DISCORD_TOKEN が設定されていません。.env を確認してください。")
    async with bot:
        await bot.load_extension("cogs.genki")
        await bot.load_extension("cogs.otasuke")
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
