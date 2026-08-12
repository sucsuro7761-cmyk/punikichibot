import discord
from discord import app_commands
from discord.ext import commands

CATEGORY_CHOICES = [
    app_commands.Choice(name="通常", value="normal"),
    app_commands.Choice(name="乱入（LV1〜6）", value="intrusion_low"),
    app_commands.Choice(name="乱入（LV7〜）", value="intrusion_high"),
]

CATEGORY_LABELS = {
    "normal": "通常",
    "intrusion_low": "乱入（LV1〜6）",
    "intrusion_high": "乱入（LV7〜）",
}

INTRUSION_LOW_MAX_LEVEL = 6


class OtasukeModal(discord.ui.Modal):
    def __init__(self, cog: "OtasukeCog", battle_type: str, include_level: bool):
        super().__init__(title=f"おたすけ募集（{battle_type}）")
        self.cog = cog
        self.battle_type = battle_type
        self.include_level = include_level

        self.level: discord.ui.TextInput | None = None
        if include_level:
            self.level = discord.ui.TextInput(
                label="ボスのレベル",
                placeholder="例: 12",
                required=True,
                max_length=3,
            )
            self.add_item(self.level)

        self.character_code = discord.ui.TextInput(
            label="キャラクターコード",
            placeholder="例: ABCD1234",
            required=True,
            max_length=50,
        )
        self.details = discord.ui.TextInput(
            label="詳細情報",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=500,
        )
        self.add_item(self.character_code)
        self.add_item(self.details)

    async def on_submit(self, interaction: discord.Interaction):
        level_value = None
        if self.level is not None:
            raw = str(self.level.value).strip()
            if not raw.isdigit() or int(raw) < 1:
                await interaction.response.send_message(
                    "レベルは1以上の数字で入力してください。", ephemeral=True
                )
                return
            level_value = int(raw)

        await self.cog.post_recruitment(
            interaction=interaction,
            battle_type=self.battle_type,
            level=level_value,
            character_code=str(self.character_code.value),
            details=str(self.details.value) if self.details.value else None,
        )


class OtasukePanelView(discord.ui.View):
    def __init__(self, cog: "OtasukeCog"):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label="通常で募集", style=discord.ButtonStyle.primary, custom_id="otasuke_normal_button"
    )
    async def normal_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(OtasukeModal(self.cog, "通常", include_level=False))

    @discord.ui.button(
        label="乱入で募集", style=discord.ButtonStyle.danger, custom_id="otasuke_intrusion_button"
    )
    async def intrusion_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(OtasukeModal(self.cog, "乱入", include_level=True))


class OtasukeCog(commands.Cog):
    """おたすけ募集機能"""

    otasuke_group = app_commands.Group(name="otasuke", description="おたすけ募集")

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.role_ids: dict[int, dict[str, int]] = {}
        self.channel_ids: dict[int, dict[str, int]] = {}

    @staticmethod
    def _category_key(battle_type: str, level: int | None) -> str:
        if battle_type == "通常":
            return "normal"
        if level is not None and level <= INTRUSION_LOW_MAX_LEVEL:
            return "intrusion_low"
        return "intrusion_high"

    @otasuke_group.command(name="panel", description="おたすけ募集パネルを設置します")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def panel(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🆘 おたすけ募集",
            description="ボタンを押して募集内容を入力してください。",
            color=discord.Color.blue(),
        )
        await interaction.response.send_message(embed=embed, view=OtasukePanelView(self))

    @otasuke_group.command(name="setrole", description="種別ごとに募集時のメンションロールを設定します")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(category="設定する種別", role="メンションするロール")
    @app_commands.choices(category=CATEGORY_CHOICES)
    async def setrole(
        self, interaction: discord.Interaction, category: app_commands.Choice[str], role: discord.Role
    ):
        self.role_ids.setdefault(interaction.guild_id, {})[category.value] = role.id
        await interaction.response.send_message(
            f"「{category.name}」の募集時に {role.mention} にメンションするよう設定しました。",
            ephemeral=True,
        )

    @otasuke_group.command(name="setchannel", description="種別ごとに募集の投稿先チャンネルを設定します")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(category="設定する種別", channel="投稿先チャンネル")
    @app_commands.choices(category=CATEGORY_CHOICES)
    async def setchannel(
        self,
        interaction: discord.Interaction,
        category: app_commands.Choice[str],
        channel: discord.TextChannel,
    ):
        self.channel_ids.setdefault(interaction.guild_id, {})[category.value] = channel.id
        await interaction.response.send_message(
            f"「{category.name}」の募集の投稿先を {channel.mention} に設定しました。",
            ephemeral=True,
        )

    async def post_recruitment(
        self,
        interaction: discord.Interaction,
        battle_type: str,
        level: int | None,
        character_code: str,
        details: str | None,
    ):
        guild_id = interaction.guild_id
        category_key = self._category_key(battle_type, level)
        category_label = CATEGORY_LABELS[category_key]

        channel_id = self.channel_ids.get(guild_id, {}).get(category_key)
        channel = self.bot.get_channel(channel_id) if channel_id else interaction.channel

        if channel is None:
            await interaction.response.send_message(
                "投稿先チャンネルが見つかりません。`/otasuke setchannel` で設定してください。",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="🆘 おたすけ募集",
            color=discord.Color.orange() if battle_type == "乱入" else discord.Color.blue(),
        )
        embed.add_field(name="種別", value=category_label, inline=True)
        if level is not None:
            embed.add_field(name="レベル", value=f"LV{level}", inline=True)
        embed.add_field(name="キャラクターコード", value=character_code, inline=True)
        embed.add_field(name="詳細情報", value=details or "-", inline=False)
        embed.set_footer(text=f"募集者: {interaction.user.display_name}")

        role_id = self.role_ids.get(guild_id, {}).get(category_key)
        content = None
        if role_id and interaction.guild is not None:
            role = interaction.guild.get_role(role_id)
            if role:
                content = role.mention

        await channel.send(content=content, embed=embed)
        await interaction.response.send_message("募集を投稿しました！", ephemeral=True)


async def setup(bot: commands.Bot):
    cog = OtasukeCog(bot)
    await bot.add_cog(cog)
    bot.add_view(OtasukePanelView(cog))
