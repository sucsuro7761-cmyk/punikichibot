import asyncio
import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands

CATEGORY_CHOICES = [
    app_commands.Choice(name="通常", value="normal"),
    app_commands.Choice(name="乱入（LV1〜4）", value="intrusion_1_4"),
    app_commands.Choice(name="乱入（LV5〜8）", value="intrusion_5_8"),
    app_commands.Choice(name="乱入（LV9〜）", value="intrusion_9_plus"),
]

CATEGORY_CHANNEL_NAMES = {
    "normal": "おたすけ-通常",
    "intrusion_1_4": "おたすけ-乱入lv1-4",
    "intrusion_5_8": "おたすけ-乱入lv5-8",
    "intrusion_9_plus": "おたすけ-乱入lv9",
}

SYNC_CATEGORY_NAME = "おたすけ募集"

RESERVE_CATEGORY_CHOICES = [
    app_commands.Choice(name="通常", value="通常"),
    app_commands.Choice(name="乱入", value="乱入"),
]

CHARACTER_CODE_LENGTH = 8
CHARACTER_CODE_PATTERN = re.compile(rf"^[a-z0-9]{{{CHARACTER_CODE_LENGTH}}}$")
TIME_ONLY_PATTERN = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")
DATETIME_PATTERN = re.compile(r"^(\d{1,2})/(\d{1,2})\s+([01]?\d|2[0-3]):([0-5]\d)$")

JST = ZoneInfo("Asia/Tokyo")

DATA_PATH = Path(os.getenv("OTASUKE_DATA_PATH", "data/otasuke_state.json"))


def _parse_reserve_time(raw: str, now: datetime) -> datetime | None:
    raw = raw.strip()

    match = TIME_ONLY_PATTERN.fullmatch(raw)
    if match:
        hour, minute = int(match.group(1)), int(match.group(2))
        candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= now:
            candidate += timedelta(days=1)
        return candidate

    match = DATETIME_PATTERN.fullmatch(raw)
    if match:
        month, day, hour, minute = (int(g) for g in match.groups())
        try:
            candidate = now.replace(
                month=month, day=day, hour=hour, minute=minute, second=0, microsecond=0
            )
        except ValueError:
            return None
        if candidate <= now:
            try:
                candidate = candidate.replace(year=candidate.year + 1)
            except ValueError:
                return None
        return candidate

    return None


class OtasukeModal(discord.ui.Modal):
    def __init__(self, cog: "OtasukeCog", battle_type: str, include_level: bool, character_code: str):
        super().__init__(title=f"おたすけ募集（{battle_type}）")
        self.cog = cog
        self.battle_type = battle_type
        self.character_code = character_code

        self.level: discord.ui.TextInput | None = None
        if include_level:
            self.level = discord.ui.TextInput(
                label="ボスのレベル",
                placeholder="例: 12",
                required=True,
                max_length=3,
            )
            self.add_item(self.level)

        self.details = discord.ui.TextInput(
            label="詳細情報",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=500,
        )
        self.add_item(self.details)

    async def on_submit(self, interaction: discord.Interaction):
        level_value = None
        if self.level is not None:
            raw_level = str(self.level.value).strip()
            if not raw_level.isdigit() or int(raw_level) < 1:
                await interaction.response.send_message(
                    "レベルは1以上の数字で入力してください。", ephemeral=True
                )
                return
            level_value = int(raw_level)

        await self.cog.post_recruitment(
            interaction=interaction,
            battle_type=self.battle_type,
            level=level_value,
            character_code=self.character_code,
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
        await self._open_modal(interaction, "通常", include_level=False)

    @discord.ui.button(
        label="乱入で募集", style=discord.ButtonStyle.danger, custom_id="otasuke_intrusion_button"
    )
    async def intrusion_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._open_modal(interaction, "乱入", include_level=True)

    async def _open_modal(self, interaction: discord.Interaction, battle_type: str, include_level: bool):
        code = self.cog.character_codes.get(interaction.user.id)
        if code is None:
            await interaction.response.send_message(
                "キャラクターコードが未登録です。`/otasuke registercode` で登録してください。",
                ephemeral=True,
            )
            return

        await interaction.response.send_modal(
            OtasukeModal(self.cog, battle_type, include_level=include_level, character_code=code)
        )


class CodeChangeApprovalView(discord.ui.View):
    def __init__(self, cog: "OtasukeCog", request_id: int):
        super().__init__(timeout=None)
        self.cog = cog
        self.request_id = request_id

        approve = discord.ui.Button(
            label="承認",
            style=discord.ButtonStyle.success,
            custom_id=f"otasuke_code_approve_{request_id}",
        )
        approve.callback = self._approve
        self.add_item(approve)

        reject = discord.ui.Button(
            label="却下",
            style=discord.ButtonStyle.danger,
            custom_id=f"otasuke_code_reject_{request_id}",
        )
        reject.callback = self._reject
        self.add_item(reject)

    async def _approve(self, interaction: discord.Interaction):
        await self.cog.resolve_code_change(interaction, self.request_id, approve=True)

    async def _reject(self, interaction: discord.Interaction):
        await self.cog.resolve_code_change(interaction, self.request_id, approve=False)


class OtasukeCog(commands.Cog):
    """おたすけ募集機能"""

    otasuke_group = app_commands.Group(name="otasuke", description="おたすけ募集")

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.role_ids: dict[int, dict[str, int]] = {}
        self.channel_ids: dict[int, dict[str, int]] = {}
        self.character_codes: dict[int, str] = {}
        self.approval_role_ids: dict[int, int] = {}
        self.approval_channel_ids: dict[int, int] = {}
        self.pending_code_changes: dict[int, dict] = {}
        self.reservations: dict[int, dict] = {}
        self._next_reservation_id = 1
        self._next_request_id = 1

    async def cog_load(self):
        self._load_state()

        now = datetime.now(JST)
        for reservation_id, data in list(self.reservations.items()):
            delay_seconds = max((data["scheduled_at"] - now).total_seconds(), 0)
            data["task"] = asyncio.create_task(
                self._fire_reservation(reservation_id, delay_seconds)
            )

        for request_id, data in self.pending_code_changes.items():
            self.bot.add_view(
                CodeChangeApprovalView(self, request_id), message_id=data["message_id"]
            )

    def _save_state(self) -> None:
        state = {
            "role_ids": {str(gid): roles for gid, roles in self.role_ids.items()},
            "channel_ids": {str(gid): chans for gid, chans in self.channel_ids.items()},
            "character_codes": {str(uid): code for uid, code in self.character_codes.items()},
            "approval_role_ids": {str(gid): rid for gid, rid in self.approval_role_ids.items()},
            "approval_channel_ids": {
                str(gid): cid for gid, cid in self.approval_channel_ids.items()
            },
            "pending_code_changes": {
                str(rid): data for rid, data in self.pending_code_changes.items()
            },
            "reservations": {
                str(rid): {
                    "user_id": data["user_id"],
                    "guild_id": data["guild_id"],
                    "channel_id": data["channel_id"],
                    "battle_type": data["battle_type"],
                    "level": data["level"],
                    "character_code": data["character_code"],
                    "details": data["details"],
                    "scheduled_at": data["scheduled_at"].isoformat(),
                }
                for rid, data in self.reservations.items()
            },
            "next_reservation_id": self._next_reservation_id,
            "next_request_id": self._next_request_id,
        }

        DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = DATA_PATH.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_path.replace(DATA_PATH)

    def _load_state(self) -> None:
        if not DATA_PATH.exists():
            return

        try:
            state = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return

        self.role_ids = {
            int(gid): dict(roles) for gid, roles in state.get("role_ids", {}).items()
        }
        self.channel_ids = {
            int(gid): dict(chans) for gid, chans in state.get("channel_ids", {}).items()
        }
        self.character_codes = {
            int(uid): code for uid, code in state.get("character_codes", {}).items()
        }
        self.approval_role_ids = {
            int(gid): rid for gid, rid in state.get("approval_role_ids", {}).items()
        }
        self.approval_channel_ids = {
            int(gid): cid for gid, cid in state.get("approval_channel_ids", {}).items()
        }
        self.pending_code_changes = {
            int(rid): data for rid, data in state.get("pending_code_changes", {}).items()
        }
        self.reservations = {
            int(rid): {
                "user_id": data["user_id"],
                "guild_id": data["guild_id"],
                "channel_id": data["channel_id"],
                "battle_type": data["battle_type"],
                "level": data["level"],
                "character_code": data["character_code"],
                "details": data["details"],
                "scheduled_at": datetime.fromisoformat(data["scheduled_at"]),
            }
            for rid, data in state.get("reservations", {}).items()
        }
        self._next_reservation_id = state.get("next_reservation_id", 1)
        self._next_request_id = state.get("next_request_id", 1)

    @staticmethod
    def _category_key(battle_type: str, level: int | None) -> str:
        if battle_type == "通常":
            return "normal"
        if level is not None and level <= 4:
            return "intrusion_1_4"
        if level is not None and level <= 8:
            return "intrusion_5_8"
        return "intrusion_9_plus"

    @otasuke_group.command(
        name="registercode", description="おたすけ募集で使うキャラクターコードを登録します"
    )
    @app_commands.describe(
        code=f"キャラクターコード(半角数字・小文字英字 {CHARACTER_CODE_LENGTH}文字)",
        reason="変更理由(2回目以降の変更時は必須)",
    )
    async def register_code(
        self, interaction: discord.Interaction, code: str, reason: str | None = None
    ):
        if interaction.guild is None:
            await interaction.response.send_message("サーバー内で実行してください。", ephemeral=True)
            return

        code_value = code.strip()
        if not CHARACTER_CODE_PATTERN.fullmatch(code_value):
            await interaction.response.send_message(
                f"キャラクターコードは半角数字・小文字アルファベットのみの{CHARACTER_CODE_LENGTH}文字で入力してください。",
                ephemeral=True,
            )
            return

        existing_code = self.character_codes.get(interaction.user.id)

        if existing_code is None:
            self.character_codes[interaction.user.id] = code_value
            self._save_state()
            await interaction.response.send_message(
                f"キャラクターコードを `{code_value}` として登録しました。", ephemeral=True
            )
            return

        if existing_code == code_value:
            await interaction.response.send_message(
                "すでに同じキャラクターコードが登録されています。", ephemeral=True
            )
            return

        reason_value = reason.strip() if reason else ""
        if not reason_value:
            await interaction.response.send_message(
                "キャラクターコードの変更には理由の入力が必要です。`reason` を指定してください。",
                ephemeral=True,
            )
            return

        await self._request_code_change(interaction, existing_code, code_value, reason_value)

    @otasuke_group.command(
        name="setapprovalrole",
        description="キャラクターコードの変更申請を承認できるロールを設定します",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(role="承認ロール")
    async def set_approval_role(self, interaction: discord.Interaction, role: discord.Role):
        self.approval_role_ids[interaction.guild_id] = role.id
        self._save_state()
        await interaction.response.send_message(
            f"キャラクターコードの変更申請の承認ロールを {role.mention} に設定しました。",
            ephemeral=True,
        )

    @otasuke_group.command(
        name="setapprovalchannel",
        description="キャラクターコードの変更申請の送信先チャンネルを設定します",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(channel="送信先チャンネル")
    async def set_approval_channel(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ):
        self.approval_channel_ids[interaction.guild_id] = channel.id
        self._save_state()
        await interaction.response.send_message(
            f"キャラクターコードの変更申請の送信先を {channel.mention} に設定しました。",
            ephemeral=True,
        )

    async def _request_code_change(
        self, interaction: discord.Interaction, old_code: str, new_code: str, reason: str
    ):
        guild = interaction.guild
        role_id = self.approval_role_ids.get(guild.id)
        role = guild.get_role(role_id) if role_id else None
        if role is None:
            await interaction.response.send_message(
                "キャラクターコードの変更申請を受け付ける承認ロールが未設定です。"
                "管理者に `/otasuke setapprovalrole` の設定を依頼してください。",
                ephemeral=True,
            )
            return

        channel_id = self.approval_channel_ids.get(guild.id)
        channel = self.bot.get_channel(channel_id) if channel_id else interaction.channel
        if channel is None:
            await interaction.response.send_message(
                "変更申請の送信先チャンネルが見つかりません。"
                "管理者に `/otasuke setapprovalchannel` の設定を依頼してください。",
                ephemeral=True,
            )
            return

        await self._cancel_pending_requests_for_user(interaction.user.id)

        request_id = self._next_request_id
        self._next_request_id += 1

        embed = discord.Embed(
            title="📝 キャラクターコード変更申請",
            color=discord.Color.gold(),
        )
        embed.add_field(name="申請者", value=interaction.user.mention, inline=True)
        embed.add_field(name="現在のコード", value=f"`{old_code}`", inline=True)
        embed.add_field(name="変更後のコード", value=f"`{new_code}`", inline=True)
        embed.add_field(name="変更理由", value=reason, inline=False)

        message = await channel.send(
            content=role.mention,
            embed=embed,
            view=CodeChangeApprovalView(self, request_id),
        )

        self.pending_code_changes[request_id] = {
            "user_id": interaction.user.id,
            "guild_id": guild.id,
            "channel_id": channel.id,
            "message_id": message.id,
            "old_code": old_code,
            "new_code": new_code,
            "reason": reason,
        }
        self._save_state()

        await interaction.response.send_message(
            f"キャラクターコードの変更申請を {channel.mention} に送信しました。承認されるまでお待ちください。",
            ephemeral=True,
        )

    async def _cancel_pending_requests_for_user(self, user_id: int) -> None:
        stale_ids = [
            rid for rid, data in self.pending_code_changes.items() if data["user_id"] == user_id
        ]
        for rid in stale_ids:
            data = self.pending_code_changes.pop(rid, None)
            if data is None:
                continue
            channel = self.bot.get_channel(data["channel_id"])
            if channel is None:
                continue
            try:
                message = await channel.fetch_message(data["message_id"])
                await message.edit(
                    content="この変更申請は新しい申請により自動的にキャンセルされました。",
                    embed=None,
                    view=None,
                )
            except discord.HTTPException:
                pass

    async def resolve_code_change(
        self, interaction: discord.Interaction, request_id: int, approve: bool
    ):
        request = self.pending_code_changes.get(request_id)
        if request is None:
            await interaction.response.send_message(
                "この申請はすでに処理済みか、見つかりませんでした。", ephemeral=True
            )
            return

        guild = interaction.guild
        if guild is None or guild.id != request["guild_id"]:
            await interaction.response.send_message("サーバー内で実行してください。", ephemeral=True)
            return

        role_id = self.approval_role_ids.get(guild.id)
        member = interaction.user
        has_permission = isinstance(member, discord.Member) and (
            member.guild_permissions.manage_guild
            or (role_id is not None and any(r.id == role_id for r in member.roles))
        )
        if not has_permission:
            await interaction.response.send_message("この操作を行う権限がありません。", ephemeral=True)
            return

        self.pending_code_changes.pop(request_id, None)

        if approve:
            self.character_codes[request["user_id"]] = request["new_code"]

        self._save_state()

        result_text = "✅ 承認されました" if approve else "❌ 却下されました"
        embed = discord.Embed(
            title="📝 キャラクターコード変更申請",
            color=discord.Color.green() if approve else discord.Color.red(),
        )
        embed.add_field(name="申請者", value=f"<@{request['user_id']}>", inline=True)
        embed.add_field(name="現在のコード", value=f"`{request['old_code']}`", inline=True)
        embed.add_field(name="変更後のコード", value=f"`{request['new_code']}`", inline=True)
        embed.add_field(name="変更理由", value=request.get("reason") or "-", inline=False)
        embed.add_field(
            name="結果", value=f"{result_text}（対応者: {interaction.user.mention}）", inline=False
        )

        await interaction.response.edit_message(embed=embed, view=None)

        requester = guild.get_member(request["user_id"])
        try:
            if requester is None:
                requester = await self.bot.fetch_user(request["user_id"])
            if approve:
                await requester.send(
                    f"キャラクターコードの変更申請が承認され、`{request['new_code']}` に更新されました。"
                )
            else:
                await requester.send("キャラクターコードの変更申請は却下されました。")
        except (discord.Forbidden, discord.HTTPException):
            pass

    @otasuke_group.command(name="mycode", description="登録済みのキャラクターコードを確認します")
    async def my_code(self, interaction: discord.Interaction):
        code = self.character_codes.get(interaction.user.id)
        if code is None:
            await interaction.response.send_message(
                "キャラクターコードが未登録です。`/otasuke registercode` で登録してください。",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(f"登録中のキャラクターコード: `{code}`", ephemeral=True)

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
        self._save_state()
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
        self._save_state()
        await interaction.response.send_message(
            f"「{category.name}」の募集の投稿先を {channel.mention} に設定しました。",
            ephemeral=True,
        )

    @otasuke_group.command(
        name="sync", description="おたすけ募集用のチャンネルをカテゴリごと自動作成・設定します"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def sync(self, interaction: discord.Interaction):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("サーバー内で実行してください。", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        category = discord.utils.get(guild.categories, name=SYNC_CATEGORY_NAME)
        try:
            if category is None:
                category = await guild.create_category(SYNC_CATEGORY_NAME)

            guild_channel_ids = self.channel_ids.setdefault(guild.id, {})
            created = []
            reused = []

            for key, channel_name in CATEGORY_CHANNEL_NAMES.items():
                channel = discord.utils.get(category.text_channels, name=channel_name)
                if channel is None:
                    channel = await guild.create_text_channel(channel_name, category=category)
                    created.append(channel.mention)
                else:
                    reused.append(channel.mention)
                guild_channel_ids[key] = channel.id
        except discord.Forbidden:
            await interaction.followup.send(
                "チャンネルの作成に失敗しました。botに「チャンネルの管理」権限があるか確認してください。",
                ephemeral=True,
            )
            return

        self._save_state()

        lines = [f"カテゴリ「{category.name}」にチャンネルを同期しました。"]
        if created:
            lines.append("作成: " + ", ".join(created))
        if reused:
            lines.append("既存を再利用: " + ", ".join(reused))

        await interaction.followup.send("\n".join(lines), ephemeral=True)

    @otasuke_group.command(name="reserve", description="指定した日時に自動でおたすけ募集を投稿します")
    @app_commands.describe(
        category="種別(通常/乱入)",
        time="投稿する時刻。「21:00」または「10/05 21:00」の形式（日本時間）",
        level="ボスのレベル(乱入の場合は必須)",
        details="詳細情報(任意)",
    )
    @app_commands.choices(category=RESERVE_CATEGORY_CHOICES)
    async def reserve(
        self,
        interaction: discord.Interaction,
        category: app_commands.Choice[str],
        time: str,
        level: int | None = None,
        details: str | None = None,
    ):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("サーバー内で実行してください。", ephemeral=True)
            return

        code_value = self.character_codes.get(interaction.user.id)
        if code_value is None:
            await interaction.response.send_message(
                "キャラクターコードが未登録です。`/otasuke registercode` で登録してください。",
                ephemeral=True,
            )
            return

        battle_type = category.value

        if battle_type == "乱入" and level is None:
            await interaction.response.send_message(
                "乱入の場合はレベルを指定してください。", ephemeral=True
            )
            return

        if level is not None and level < 1:
            await interaction.response.send_message(
                "レベルは1以上の数字で指定してください。", ephemeral=True
            )
            return

        now = datetime.now(JST)
        scheduled_at = _parse_reserve_time(time, now)
        if scheduled_at is None:
            await interaction.response.send_message(
                "時刻の形式が正しくありません。「21:00」または「10/05 21:00」の形式で指定してください。",
                ephemeral=True,
            )
            return

        delay_seconds = (scheduled_at - now).total_seconds()

        reservation_id = self._next_reservation_id
        self._next_reservation_id += 1

        self.reservations[reservation_id] = {
            "user_id": interaction.user.id,
            "guild_id": guild.id,
            "channel_id": interaction.channel_id,
            "battle_type": battle_type,
            "level": level if battle_type == "乱入" else None,
            "character_code": code_value,
            "details": details,
            "scheduled_at": scheduled_at,
        }
        self.reservations[reservation_id]["task"] = asyncio.create_task(
            self._fire_reservation(reservation_id, delay_seconds)
        )
        self._save_state()

        await interaction.response.send_message(
            f"予約を受け付けました（ID: {reservation_id}）。"
            f"{scheduled_at.strftime('%m/%d %H:%M')} 頃に自動投稿します（日本時間）。",
            ephemeral=True,
        )

    @otasuke_group.command(name="reservations", description="自分が予約したおたすけ募集の一覧を確認します")
    async def list_reservations(self, interaction: discord.Interaction):
        mine = [
            (rid, r) for rid, r in self.reservations.items() if r["user_id"] == interaction.user.id
        ]
        if not mine:
            await interaction.response.send_message("予約中の募集はありません。", ephemeral=True)
            return

        mine.sort(key=lambda item: item[1]["scheduled_at"])
        lines = []
        for rid, item in mine:
            level_part = f"（LV{item['level']}）" if item["level"] is not None else ""
            lines.append(
                f"- ID {rid}: {item['battle_type']}{level_part} / "
                f"{item['scheduled_at'].strftime('%m/%d %H:%M')}"
            )

        await interaction.response.send_message("\n".join(lines), ephemeral=True)

    @otasuke_group.command(name="cancelreserve", description="予約したおたすけ募集を取り消します")
    @app_commands.describe(reservation_id="取り消す予約のID(/otasuke reservations で確認できます)")
    async def cancel_reserve(self, interaction: discord.Interaction, reservation_id: int):
        reservation = self.reservations.get(reservation_id)
        if reservation is None or reservation["user_id"] != interaction.user.id:
            await interaction.response.send_message(
                "指定されたIDの予約が見つかりません。", ephemeral=True
            )
            return

        reservation["task"].cancel()
        self.reservations.pop(reservation_id, None)
        self._save_state()
        await interaction.response.send_message(
            f"予約（ID: {reservation_id}）を取り消しました。", ephemeral=True
        )

    async def _fire_reservation(self, reservation_id: int, delay_seconds: float):
        try:
            await asyncio.sleep(delay_seconds)
        except asyncio.CancelledError:
            return

        data = self.reservations.pop(reservation_id, None)
        self._save_state()
        if data is None:
            return

        guild = self.bot.get_guild(data["guild_id"])
        if guild is None:
            return

        fallback_channel = self.bot.get_channel(data["channel_id"])
        sent = await self._send_recruitment(
            guild=guild,
            author_mention=f"<@{data['user_id']}>",
            battle_type=data["battle_type"],
            level=data["level"],
            character_code=data["character_code"],
            details=data["details"],
            fallback_channel=fallback_channel,
        )
        if not sent and fallback_channel is not None:
            try:
                await fallback_channel.send(
                    f"<@{data['user_id']}> 予約投稿に失敗しました。投稿先チャンネルの設定を確認してください。"
                )
            except discord.HTTPException:
                pass

    async def _send_recruitment(
        self,
        guild: discord.Guild,
        author_mention: str,
        battle_type: str,
        level: int | None,
        character_code: str,
        details: str | None,
        fallback_channel: discord.abc.Messageable | None,
    ) -> bool:
        category_key = self._category_key(battle_type, level)

        channel_id = self.channel_ids.get(guild.id, {}).get(category_key)
        channel = self.bot.get_channel(channel_id) if channel_id else fallback_channel

        if channel is None:
            return False

        embed = discord.Embed(
            title="🆘 おたすけ募集",
            color=discord.Color.orange() if battle_type == "乱入" else discord.Color.blue(),
        )
        if level is not None:
            embed.add_field(name="レベル", value=f"LV{level}", inline=True)
        embed.add_field(name="キャラクターコード", value=f"`{character_code}`", inline=True)
        embed.add_field(name="募集者", value=author_mention, inline=True)
        embed.add_field(name="詳細情報", value=details or "-", inline=False)

        role_id = self.role_ids.get(guild.id, {}).get(category_key)
        content = None
        if role_id:
            role = guild.get_role(role_id)
            if role:
                content = role.mention

        await channel.send(content=content, embed=embed)
        return True

    async def post_recruitment(
        self,
        interaction: discord.Interaction,
        battle_type: str,
        level: int | None,
        character_code: str,
        details: str | None,
    ):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("サーバー内で実行してください。", ephemeral=True)
            return

        sent = await self._send_recruitment(
            guild=guild,
            author_mention=interaction.user.mention,
            battle_type=battle_type,
            level=level,
            character_code=character_code,
            details=details,
            fallback_channel=interaction.channel,
        )

        if not sent:
            await interaction.response.send_message(
                "投稿先チャンネルが見つかりません。`/otasuke setchannel` または `/otasuke sync` で設定してください。",
                ephemeral=True,
            )
            return

        await interaction.response.send_message("募集を投稿しました！", ephemeral=True)


async def setup(bot: commands.Bot):
    cog = OtasukeCog(bot)
    await bot.add_cog(cog)
    bot.add_view(OtasukePanelView(cog))
