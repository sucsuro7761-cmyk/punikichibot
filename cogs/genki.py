import asyncio
import os
from datetime import datetime, timedelta

import discord
from discord import app_commands
from discord.ext import commands

GENKI_REGEN_MINUTES = float(os.getenv("GENKI_REGEN_MINUTES", "5"))
GENKI_MAX = int(os.getenv("GENKI_MAX", "50"))


class GenkiCog(commands.Cog):
    """ゲンキ回復通知機能"""

    genki_group = app_commands.Group(name="genki", description="ゲンキ回復通知")

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.timers: dict[int, dict] = {}

    def _cancel_existing(self, user_id: int) -> None:
        existing = self.timers.pop(user_id, None)
        if existing:
            existing["task"].cancel()

    @genki_group.command(name="set", description=f"現在値からゲンキ全回復までの通知を予約します(最大値は{GENKI_MAX}固定)")
    @app_commands.describe(current="現在のゲンキ")
    async def set_timer(self, interaction: discord.Interaction, current: int):
        if current < 0 or current > GENKI_MAX:
            await interaction.response.send_message(
                f"入力値が正しくありません。0 〜 {GENKI_MAX} の範囲で指定してください。",
                ephemeral=True,
            )
            return

        missing = GENKI_MAX - current
        if missing == 0:
            await interaction.response.send_message("すでに全回復しています！", ephemeral=True)
            return

        minutes = missing * GENKI_REGEN_MINUTES
        ready_at = datetime.now() + timedelta(minutes=minutes)

        self._cancel_existing(interaction.user.id)

        task = asyncio.create_task(
            self._notify_when_ready(
                user_id=interaction.user.id,
                channel_id=interaction.channel_id,
                delay_seconds=minutes * 60,
                max_value=GENKI_MAX,
            )
        )
        self.timers[interaction.user.id] = {"task": task, "ready_at": ready_at, "max": GENKI_MAX}

        await interaction.response.send_message(
            f"ゲンキ全回復まで約 {minutes:.0f} 分です。"
            f"（{ready_at.strftime('%H:%M')} 頃に通知します）"
        )

    @genki_group.command(name="check", description="設定中のゲンキ回復タイマーを確認します")
    async def check_timer(self, interaction: discord.Interaction):
        timer = self.timers.get(interaction.user.id)
        if not timer:
            await interaction.response.send_message("設定中のタイマーはありません。", ephemeral=True)
            return

        remaining = timer["ready_at"] - datetime.now()
        if remaining.total_seconds() <= 0:
            await interaction.response.send_message("まもなく通知します。", ephemeral=True)
            return

        minutes, seconds = divmod(int(remaining.total_seconds()), 60)
        await interaction.response.send_message(
            f"ゲンキ全回復まで残り {minutes}分{seconds}秒です。", ephemeral=True
        )

    @genki_group.command(name="cancel", description="設定中のゲンキ回復タイマーを取り消します")
    async def cancel_timer(self, interaction: discord.Interaction):
        if interaction.user.id not in self.timers:
            await interaction.response.send_message("設定中のタイマーはありません。", ephemeral=True)
            return

        self._cancel_existing(interaction.user.id)
        await interaction.response.send_message("タイマーを取り消しました。", ephemeral=True)

    async def _notify_when_ready(
        self, user_id: int, channel_id: int, delay_seconds: float, max_value: int
    ):
        try:
            await asyncio.sleep(delay_seconds)
        except asyncio.CancelledError:
            return

        self.timers.pop(user_id, None)
        channel = self.bot.get_channel(channel_id)
        if channel is None:
            return

        await channel.send(f"<@{user_id}> ゲンキが全回復しました！（{max_value}/{max_value}）")


async def setup(bot: commands.Bot):
    await bot.add_cog(GenkiCog(bot))
