import asyncio
import logging
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

logging.basicConfig(level=logging.INFO)

intents = discord.Intents.default()

bot = commands.Bot(command_prefix="!", intents=intents)


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
