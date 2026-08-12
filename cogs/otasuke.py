import discord
from discord import app_commands
from discord.ext import commands


class OtasukeModal(discord.ui.Modal):
    def __init__(self, cog: "OtasukeCog", battle_type: str):
        super().__init__(title=f"おたすけ募集（{battle_type}）")
        self.cog = cog
        self.battle_type = battle_type
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
        await self.cog.post_recruitment(
            interaction=interaction,
            battle_type=self.battle_type,
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
        await interaction.response.send_modal(OtasukeModal(self.cog, "通常"))

    @discord.ui.button(
        label="乱入で募集", style=discord.ButtonStyle.danger, custom_id="otasuke_intrusion_button"
    )
    async def intrusion_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(OtasukeModal(self.cog, "乱入"))


class OtasukeCog(commands.Cog):
    """おたすけ募集機能"""

    otasuke_group = app_commands.Group(name="otasuke", description="おたすけ募集")

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.role_ids: dict[int, int] = {}
        self.channel_ids: dict[int, int] = {}

    @otasuke_group.command(name="panel", description="おたすけ募集パネルを設置します")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def panel(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🆘 おたすけ募集",
            description="ボタンを押して募集内容を入力してください。",
            color=discord.Color.blue(),
        )
        await interaction.response.send_message(embed=embed, view=OtasukePanelView(self))

    @otasuke_group.command(name="setrole", description="募集時にメンションするロールを設定します")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(role="メンションするロール")
    async def setrole(self, interaction: discord.Interaction, role: discord.Role):
        self.role_ids[interaction.guild_id] = role.id
        await interaction.response.send_message(
            f"募集時に {role.mention} にメンションするよう設定しました。", ephemeral=True
        )

    @otasuke_group.command(name="setchannel", description="募集の投稿先チャンネルを設定します")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(channel="投稿先チャンネル")
    async def setchannel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        self.channel_ids[interaction.guild_id] = channel.id
        await interaction.response.send_message(
            f"募集の投稿先を {channel.mention} に設定しました。", ephemeral=True
        )

    async def post_recruitment(
        self,
        interaction: discord.Interaction,
        battle_type: str,
        character_code: str,
        details: str | None,
    ):
        guild_id = interaction.guild_id
        channel_id = self.channel_ids.get(guild_id)
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
        embed.add_field(name="種別", value=battle_type, inline=True)
        embed.add_field(name="キャラクターコード", value=character_code, inline=True)
        embed.add_field(name="詳細情報", value=details or "-", inline=False)
        embed.set_footer(text=f"募集者: {interaction.user.display_name}")

        role_id = self.role_ids.get(guild_id)
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
