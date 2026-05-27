"""
═══════════════════════════════════════════════════════════════════════════════
  ███████╗██████╗  ██████╗ ████████╗
  ██╔════╝██╔══██╗██╔═══██╗╚══██╔══╝
  ███████╗██████╔╝██║   ██║   ██║
  ╚════██║██╔═══╝ ██║   ██║   ██║
  ███████║██║     ╚██████╔╝   ██║
  ╚══════╝╚═╝      ╚═════╝    ╚═╝

  SPOT — Discord Protection, Organization & Tools
  A Bleed-inspired all-in-one bot with fake permissions, antinuke,
  voicemaster, levels, snipe, autoresponders, starboard, counters,
  giveaways, bump reminders, and server access control.

  Prefix: ,
  Railway-ready | Single-file deployment
═══════════════════════════════════════════════════════════════════════════════
"""

import discord
from discord.ext import commands, tasks
from discord import app_commands
from discord.ui import View, Button, Modal, TextInput
import os
import asyncio
import json
import random
import aiohttp
import re
import logging
import math
from datetime import datetime, timedelta
from collections import defaultdict, deque
from typing import Optional, Dict, List, Set

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger("spot")

# ─── Data Persistence ─────────────────────────────────────────────────────────
DATA_DIR = os.environ.get("DATA_DIR", "/data")
os.makedirs(DATA_DIR, exist_ok=True)

FILES = {
    "warnings": os.path.join(DATA_DIR, "warnings.json"),
    "antinuke": os.path.join(DATA_DIR, "antinuke.json"),
    "fakeperms": os.path.join(DATA_DIR, "fakeperms.json"),
    "levels": os.path.join(DATA_DIR, "levels.json"),
    "autoresponders": os.path.join(DATA_DIR, "autoresponders.json"),
    "starboard": os.path.join(DATA_DIR, "starboard.json"),
    "counters": os.path.join(DATA_DIR, "counters.json"),
    "giveaways": os.path.join(DATA_DIR, "giveaways.json"),
    "bump": os.path.join(DATA_DIR, "bump.json"),
    "voicemaster": os.path.join(DATA_DIR, "voicemaster.json"),
    "snipe": os.path.join(DATA_DIR, "snipe.json"),
    "servers": os.path.join(DATA_DIR, "servers.json"),
    "reaction_triggers": os.path.join(DATA_DIR, "reaction_triggers.json"),
    "lockdown": os.path.join(DATA_DIR, "lockdown.json"),
}

def load_json(path: str, default=None):
    if default is None:
        default = {}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default

def save_json(path: str, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)

# ─── SPOT Color Theme ─────────────────────────────────────────────────────────
SPOT_BLACK = 0x0A0A0A
SPOT_DARK = 0x1A1A1A
SPOT_ACCENT = 0x5865F2
SPOT_RED = 0xED4245
SPOT_GREEN = 0x57F287
SPOT_GOLD = 0xFEE75C
SPOT_ORANGE = 0xFAA61A

def spot_embed(title: str = None, description: str = None, color: int = SPOT_BLACK) -> discord.Embed:
    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=datetime.utcnow()
    )
    embed.set_footer(text="SPOT — Protection, Organization & Tools", icon_url="https://cdn.discordapp.com/embed/avatars/0.png")
    return embed

# ═══════════════════════════════════════════════════════════════════════════════
#  SERVER ACCESS CONTROL
# ═══════════════════════════════════════════════════════════════════════════════
class ServerAccess:
    def __init__(self):
        self.data = load_json(FILES["servers"])
        self.mode = self.data.get("mode", "blacklist")
        self.blacklist: Set[int] = set(self.data.get("blacklist", []))
        self.whitelist: Set[int] = set(self.data.get("whitelist", []))
        self.owner_id = self.data.get("owner_id")

    def save(self):
        self.data["mode"] = self.mode
        self.data["blacklist"] = list(self.blacklist)
        self.data["whitelist"] = list(self.whitelist)
        self.data["owner_id"] = self.owner_id
        save_json(FILES["servers"], self.data)

    def is_allowed(self, guild_id: int) -> bool:
        if self.mode == "whitelist":
            return guild_id in self.whitelist
        return guild_id not in self.blacklist

    def add_blacklist(self, guild_id: int):
        self.blacklist.add(guild_id)
        self.whitelist.discard(guild_id)
        self.save()

    def remove_blacklist(self, guild_id: int):
        self.blacklist.discard(guild_id)
        self.save()

    def add_whitelist(self, guild_id: int):
        self.whitelist.add(guild_id)
        self.blacklist.discard(guild_id)
        self.save()

    def remove_whitelist(self, guild_id: int):
        self.whitelist.discard(guild_id)
        self.save()

server_access = ServerAccess()

# ═══════════════════════════════════════════════════════════════════════════════
#  FAKE PERMISSIONS SYSTEM (Bleed-inspired)
# ═══════════════════════════════════════════════════════════════════════════════
class FakePermissions:
    def __init__(self):
        self.data = load_json(FILES["fakeperms"])
        self.perms: Dict[str, Dict[str, List[str]]] = self.data.get("perms", {})

    def save(self):
        save_json(FILES["fakeperms"], {"perms": self.perms})

    def has_fake_perm(self, guild_id: int, member: discord.Member, perm: str) -> bool:
        gid = str(guild_id)
        if gid not in self.perms:
            return False
        if member.id == member.guild.owner_id:
            return True
        for role in member.roles:
            rid = str(role.id)
            if rid in self.perms[gid]:
                if "administrator" in self.perms[gid][rid]:
                    return True
                if perm in self.perms[gid][rid]:
                    return True
        return False

    def grant(self, guild_id: int, role_id: int, perms: List[str]):
        gid, rid = str(guild_id), str(role_id)
        self.perms.setdefault(gid, {}).setdefault(rid, [])
        for p in perms:
            if p not in self.perms[gid][rid]:
                self.perms[gid][rid].append(p)
        self.save()

    def revoke(self, guild_id: int, role_id: int, perms: List[str]):
        gid, rid = str(guild_id), str(role_id)
        if gid in self.perms and rid in self.perms[gid]:
            self.perms[gid][rid] = [p for p in self.perms[gid][rid] if p not in perms]
            if not self.perms[gid][rid]:
                del self.perms[gid][rid]
        self.save()

    def reset(self, guild_id: int):
        self.perms.pop(str(guild_id), None)
        self.save()

    def list_perms(self, guild_id: int, role_id: int = None) -> dict:
        gid = str(guild_id)
        if gid not in self.perms:
            return {}
        if role_id:
            return {str(role_id): self.perms[gid].get(str(role_id), [])}
        return self.perms[gid]

fake_permissions = FakePermissions()

VALID_FAKE_PERMS = [
    "administrator", "ban_members", "kick_members", "manage_messages",
    "moderate_members", "manage_nicknames", "manage_roles", "manage_channels",
    "purge", "warn", "mute", "lockdown", "nuke"
]

def check_fake_perm(perm: str):
    async def predicate(ctx):
        if ctx.author.id == ctx.guild.owner_id:
            return True
        if fake_permissions.has_fake_perm(ctx.guild.id, ctx.author, perm):
            return True
        real_perm_map = {
            "ban_members": "ban_members",
            "kick_members": "kick_members",
            "manage_messages": "manage_messages",
            "moderate_members": "moderate_members",
            "manage_nicknames": "manage_nicknames",
            "manage_roles": "manage_roles",
            "manage_channels": "manage_channels",
        }
        if perm in real_perm_map and getattr(ctx.author.guild_permissions, real_perm_map[perm], False):
            return True
        raise commands.MissingPermissions([perm])
    return commands.check(predicate)

# ═══════════════════════════════════════════════════════════════════════════════
#  SNIPE SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════
class SnipeSystem:
    def __init__(self):
        self.deleted: Dict[int, deque] = defaultdict(lambda: deque(maxlen=10))
        self.edited: Dict[int, deque] = defaultdict(lambda: deque(maxlen=10))

    def add_deleted(self, message: discord.Message):
        if message.author.bot:
            return
        self.deleted[message.channel.id].append({
            "content": message.content,
            "author": message.author,
            "avatar": message.author.display_avatar.url,
            "time": datetime.utcnow(),
            "attachments": [a.url for a in message.attachments],
            "embeds": len(message.embeds) > 0
        })

    def add_edited(self, before: discord.Message, after: discord.Message):
        if before.author.bot:
            return
        self.edited[before.channel.id].append({
            "before": before.content,
            "after": after.content,
            "author": before.author,
            "avatar": before.author.display_avatar.url,
            "time": datetime.utcnow()
        })

    def get_deleted(self, channel_id: int, index: int = 0):
        msgs = list(self.deleted.get(channel_id, []))
        if 0 <= index < len(msgs):
            return msgs[index]
        return None

    def get_edited(self, channel_id: int, index: int = 0):
        msgs = list(self.edited.get(channel_id, []))
        if 0 <= index < len(msgs):
            return msgs[index]
        return None

snipe_system = SnipeSystem()

# ═══════════════════════════════════════════════════════════════════════════════
#  ANTINUKE
# ═══════════════════════════════════════════════════════════════════════════════
class AntiNukeConfig:
    def __init__(self, guild_id: int):
        self.guild_id = guild_id
        self.max_bans = 3
        self.max_kicks = 3
        self.max_channel_deletes = 2
        self.max_role_deletes = 2
        self.max_role_creates = 5
        self.time_window = 10
        self.whitelist = set()
        self.enabled = True
        self.log_channel_id = None

    def to_dict(self):
        return {
            "max_bans": self.max_bans, "max_kicks": self.max_kicks,
            "max_channel_deletes": self.max_channel_deletes,
            "max_role_deletes": self.max_role_deletes,
            "max_role_creates": self.max_role_creates,
            "time_window": self.time_window,
            "whitelist": list(self.whitelist),
            "enabled": self.enabled,
            "log_channel_id": self.log_channel_id,
        }

    @classmethod
    def from_dict(cls, guild_id: int, data: dict):
        cfg = cls(guild_id)
        for k, v in data.items():
            if k == "whitelist":
                cfg.whitelist = set(v)
            elif hasattr(cfg, k):
                setattr(cfg, k, v)
        return cfg

    def is_whitelisted(self, user_id: int) -> bool:
        return user_id in self.whitelist

class ActionTracker:
    def __init__(self, time_window: int):
        self.time_window = time_window
        self.actions = defaultdict(list)

    def add_action(self, user_id: int, action_type: str):
        now = datetime.utcnow()
        self.actions[(user_id, action_type)].append(now)
        self._cleanup(user_id, action_type, now)

    def _cleanup(self, user_id: int, action_type: str, now: datetime):
        cutoff = now - timedelta(seconds=self.time_window)
        self.actions[(user_id, action_type)] = [t for t in self.actions[(user_id, action_type)] if t > cutoff]

    def get_count(self, user_id: int, action_type: str) -> int:
        now = datetime.utcnow()
        self._cleanup(user_id, action_type, now)
        return len(self.actions[(user_id, action_type)])

    def reset_user(self, user_id: int):
        for k in list(self.actions.keys()):
            if k[0] == user_id:
                del self.actions[k]

class AntiNuke(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.configs = {}
        self.trackers = {}
        self._load()

    def _load(self):
        raw = load_json(FILES["antinuke"])
        for gid, data in raw.items():
            self.configs[int(gid)] = AntiNukeConfig.from_dict(int(gid), data)

    def _save(self):
        save_json(FILES["antinuke"], {str(gid): cfg.to_dict() for gid, cfg in self.configs.items()})

    def get_cfg(self, gid: int) -> AntiNukeConfig:
        if gid not in self.configs:
            self.configs[gid] = AntiNukeConfig(gid)
            self._save()
        return self.configs[gid]

    def get_tracker(self, gid: int) -> ActionTracker:
        cfg = self.get_cfg(gid)
        if gid not in self.trackers:
            self.trackers[gid] = ActionTracker(cfg.time_window)
        return self.trackers[gid]

    async def log(self, guild: discord.Guild, msg: str, severity: str = "WARNING"):
        cfg = self.get_cfg(guild.id)
        if cfg.log_channel_id:
            ch = guild.get_channel(cfg.log_channel_id)
            if ch:
                color = SPOT_RED if severity == "CRITICAL" else SPOT_ORANGE
                embed = spot_embed(title=f"🛡️ AntiNuke {severity}", description=msg, color=color)
                try:
                    await ch.send(embed=embed)
                except Exception:
                    pass

    async def punish(self, guild: discord.Guild, user_id: int, reason: str):
        try:
            member = guild.get_member(user_id)
            if not member:
                return
            roles = [r for r in member.roles if r != guild.default_role]
            if roles:
                await member.remove_roles(*roles, reason=f"SPOT AntiNuke: {reason}")
            await self.log(guild, f"**User Punished:** {member.mention} ({member.id})\n**Reason:** {reason}\n**Action:** Removed all roles", "CRITICAL")
        except discord.Forbidden:
            await self.log(guild, f"Failed to punish {user_id}: Missing permissions", "ERROR")
        except Exception as e:
            await self.log(guild, f"Error punishing {user_id}: {e}", "ERROR")

    async def check(self, guild: discord.Guild, user_id: int, action_type: str, threshold: int):
        cfg = self.get_cfg(guild.id)
        if not cfg.enabled or cfg.is_whitelisted(user_id) or user_id == guild.owner_id:
            return False
        tracker = self.get_tracker(guild.id)
        tracker.add_action(user_id, action_type)
        count = tracker.get_count(user_id, action_type)
        if count >= threshold:
            reason = f"Exceeded {action_type} limit ({count}/{threshold} in {cfg.time_window}s)"
            await self.punish(guild, user_id, reason)
            tracker.reset_user(user_id)
            return True
        return False

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        try:
            await asyncio.sleep(0.5)
            async for entry in guild.audit_logs(action=discord.AuditLogAction.ban, limit=5):
                if entry.target.id == user.id and (datetime.utcnow() - entry.created_at).total_seconds() < 10:
                    cfg = self.get_cfg(guild.id)
                    if await self.check(guild, entry.user.id, "ban", cfg.max_bans):
                        try:
                            await guild.unban(user, reason="SPOT AntiNuke: Mass ban detected")
                            await self.log(guild, f"Reversed ban for {user.mention}")
                        except Exception:
                            pass
                    break
        except Exception as e:
            logger.error(f"AntiNuke ban error: {e}")

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        try:
            await asyncio.sleep(0.5)
            async for entry in member.guild.audit_logs(action=discord.AuditLogAction.kick, limit=5):
                if entry.target.id == member.id and (datetime.utcnow() - entry.created_at).total_seconds() < 10:
                    cfg = self.get_cfg(member.guild.id)
                    await self.check(member.guild, entry.user.id, "kick", cfg.max_kicks)
                    break
        except Exception as e:
            logger.error(f"AntiNuke kick error: {e}")

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        try:
            await asyncio.sleep(0.5)
            async for entry in channel.guild.audit_logs(action=discord.AuditLogAction.channel_delete, limit=5):
                if entry.target.id == channel.id and (datetime.utcnow() - entry.created_at).total_seconds() < 10:
                    cfg = self.get_cfg(channel.guild.id)
                    await self.check(channel.guild, entry.user.id, "channel_delete", cfg.max_channel_deletes)
                    break
        except Exception as e:
            logger.error(f"AntiNuke channel delete error: {e}")

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        try:
            await asyncio.sleep(0.5)
            async for entry in role.guild.audit_logs(action=discord.AuditLogAction.role_delete, limit=5):
                if entry.target.id == role.id and (datetime.utcnow() - entry.created_at).total_seconds() < 10:
                    cfg = self.get_cfg(role.guild.id)
                    await self.check(role.guild, entry.user.id, "role_delete", cfg.max_role_deletes)
                    break
        except Exception as e:
            logger.error(f"AntiNuke role delete error: {e}")

    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        try:
            await asyncio.sleep(0.5)
            async for entry in role.guild.audit_logs(action=discord.AuditLogAction.role_create, limit=5):
                if entry.target.id == role.id and (datetime.utcnow() - entry.created_at).total_seconds() < 10:
                    cfg = self.get_cfg(role.guild.id)
                    if await self.check(role.guild, entry.user.id, "role_create", cfg.max_role_creates):
                        try:
                            await role.delete(reason="SPOT AntiNuke: Mass role creation")
                        except Exception:
                            pass
                    break
        except Exception as e:
            logger.error(f"AntiNuke role create error: {e}")

    @commands.Cog.listener()
    async def on_guild_role_update(self, before, after):
        try:
            dangerous = ["administrator", "ban_members", "kick_members", "manage_guild", "manage_roles", "manage_channels"]
            new_perms = [p for p, v in after.permissions if v and not getattr(before.permissions, p) and p in dangerous]
            if new_perms:
                await asyncio.sleep(0.5)
                async for entry in after.guild.audit_logs(action=discord.AuditLogAction.role_update, limit=5):
                    if entry.target.id == after.id and (datetime.utcnow() - entry.created_at).total_seconds() < 10:
                        cfg = self.get_cfg(after.guild.id)
                        if not cfg.is_whitelisted(entry.user.id) and entry.user.id != after.guild.owner_id:
                            await self.log(after.guild, f"**Suspicious Role Update**\nRole: {after.mention}\nExecutor: <@{entry.user.id}>\nNew: {', '.join(new_perms)}", "WARNING")
                        break
        except Exception as e:
            logger.error(f"AntiNuke role update error: {e}")

    @commands.group(name="antinuke", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def antinuke(self, ctx):
        cfg = self.get_cfg(ctx.guild.id)
        embed = spot_embed(title="🛡️ SPOT AntiNuke", description="Protection against malicious mass actions")
        embed.add_field(name="Status", value="🟢 Enabled" if cfg.enabled else "🔴 Disabled", inline=False)
        embed.add_field(name="Max Bans", value=cfg.max_bans, inline=True)
        embed.add_field(name="Max Kicks", value=cfg.max_kicks, inline=True)
        embed.add_field(name="Max Channel Deletes", value=cfg.max_channel_deletes, inline=True)
        embed.add_field(name="Max Role Deletes", value=cfg.max_role_deletes, inline=True)
        embed.add_field(name="Max Role Creates", value=cfg.max_role_creates, inline=True)
        embed.add_field(name="Time Window", value=f"{cfg.time_window}s", inline=True)
        embed.add_field(name="Whitelisted", value=len(cfg.whitelist), inline=True)
        log_ch = ctx.guild.get_channel(cfg.log_channel_id) if cfg.log_channel_id else None
        embed.add_field(name="Log Channel", value=log_ch.mention if log_ch else "Not set", inline=True)
        await ctx.send(embed=embed)

    @antinuke.command(name="toggle")
    @commands.has_permissions(administrator=True)
    async def toggle(self, ctx):
        cfg = self.get_cfg(ctx.guild.id)
        cfg.enabled = not cfg.enabled
        self._save()
        await ctx.send(embed=spot_embed(description=f"{'🟢' if cfg.enabled else '🔴'} AntiNuke {'enabled' if cfg.enabled else 'disabled'}", color=SPOT_GREEN if cfg.enabled else SPOT_RED))

    @antinuke.command(name="whitelist")
    @commands.has_permissions(administrator=True)
    async def whitelist_cmd(self, ctx, user: discord.Member):
        cfg = self.get_cfg(ctx.guild.id)
        cfg.whitelist.add(user.id)
        self._save()
        await ctx.send(embed=spot_embed(description=f"✅ Added {user.mention} to whitelist", color=SPOT_GREEN))

    @antinuke.command(name="unwhitelist")
    @commands.has_permissions(administrator=True)
    async def unwhitelist(self, ctx, user: discord.Member):
        cfg = self.get_cfg(ctx.guild.id)
        cfg.whitelist.discard(user.id)
        self._save()
        await ctx.send(embed=spot_embed(description=f"✅ Removed {user.mention} from whitelist", color=SPOT_ORANGE))

    @antinuke.command(name="setlog")
    @commands.has_permissions(administrator=True)
    async def setlog(self, ctx, channel: discord.TextChannel):
        cfg = self.get_cfg(ctx.guild.id)
        cfg.log_channel_id = channel.id
        self._save()
        await ctx.send(embed=spot_embed(description=f"✅ Log channel set to {channel.mention}", color=SPOT_GREEN))

    @antinuke.command(name="set")
    @commands.has_permissions(administrator=True)
    async def set_threshold(self, ctx, setting: str, value: int):
        valid = ["max_bans", "max_kicks", "max_channel_deletes", "max_role_deletes", "max_role_creates", "time_window"]
        if setting not in valid:
            return await ctx.send(embed=spot_embed(description=f"❌ Valid settings: {', '.join(valid)}", color=SPOT_RED))
        cfg = self.get_cfg(ctx.guild.id)
        setattr(cfg, setting, value)
        self._save()
        await ctx.send(embed=spot_embed(description=f"✅ `{setting}` set to `{value}`", color=SPOT_GREEN))

# ═══════════════════════════════════════════════════════════════════════════════
#  MODERATION
# ═══════════════════════════════════════════════════════════════════════════════
class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.warnings = load_json(FILES["warnings"])

    def _save_warnings(self):
        save_json(FILES["warnings"], self.warnings)

    async def log_action(self, ctx, action: str, target: discord.Member, reason: str = None):
        embed = spot_embed(title=f"🔨 {action}", color=SPOT_RED)
        embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
        embed.add_field(name="Target", value=target.mention, inline=True)
        embed.add_field(name="Reason", value=reason or "No reason", inline=False)
        log_ch = discord.utils.get(ctx.guild.channels, name="mod-logs")
        if log_ch:
            try:
                await log_ch.send(embed=embed)
            except Exception:
                pass
        logger.info(f"{action} | {ctx.author} -> {target} | {reason}")

    @commands.command(name="ban")
    @check_fake_perm("ban_members")
    @commands.bot_has_permissions(ban_members=True)
    async def ban(self, ctx, member: discord.Member, *, reason: str = None):
        if member.top_role >= ctx.author.top_role:
            return await ctx.send(embed=spot_embed(description="❌ You can't ban someone equal or higher.", color=SPOT_RED), delete_after=5)
        if member.top_role >= ctx.guild.me.top_role:
            return await ctx.send(embed=spot_embed(description="❌ I can't ban someone equal or higher.", color=SPOT_RED), delete_after=5)
        try:
            await member.send(f"You were banned from **{ctx.guild.name}**.\nReason: {reason or 'No reason'}")
        except Exception:
            pass
        await member.ban(reason=reason)
        await ctx.send(embed=spot_embed(description=f"✅ **{member}** banned. Reason: {reason or 'No reason'}", color=SPOT_GREEN))
        await self.log_action(ctx, "BAN", member, reason)

    @commands.command(name="kick")
    @check_fake_perm("kick_members")
    @commands.bot_has_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member, *, reason: str = None):
        if member.top_role >= ctx.author.top_role:
            return await ctx.send(embed=spot_embed(description="❌ You can't kick someone equal or higher.", color=SPOT_RED), delete_after=5)
        if member.top_role >= ctx.guild.me.top_role:
            return await ctx.send(embed=spot_embed(description="❌ I can't kick someone equal or higher.", color=SPOT_RED), delete_after=5)
        try:
            await member.send(f"You were kicked from **{ctx.guild.name}**.\nReason: {reason or 'No reason'}")
        except Exception:
            pass
        await member.kick(reason=reason)
        await ctx.send(embed=spot_embed(description=f"✅ **{member}** kicked. Reason: {reason or 'No reason'}", color=SPOT_GREEN))
        await self.log_action(ctx, "KICK", member, reason)

    @commands.command(name="timeout")
    @check_fake_perm("moderate_members")
    @commands.bot_has_permissions(moderate_members=True)
    async def timeout(self, ctx, member: discord.Member, duration: int, unit: str = "m", *, reason: str = None):
        if member.top_role >= ctx.author.top_role:
            return await ctx.send(embed=spot_embed(description="❌ You can't timeout someone equal or higher.", color=SPOT_RED), delete_after=5)
        units = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}
        if unit not in units:
            return await ctx.send(embed=spot_embed(description="❌ Use: s, m, h, d", color=SPOT_RED), delete_after=5)
        seconds = duration * units[unit]
        if seconds > 2419200:
            return await ctx.send(embed=spot_embed(description="❌ Max 28 days.", color=SPOT_RED), delete_after=5)
        try:
            await member.timeout(timedelta(seconds=seconds), reason=reason)
            await ctx.send(embed=spot_embed(description=f"✅ **{member}** timed out for {duration}{unit}.", color=SPOT_GREEN))
            await self.log_action(ctx, f"TIMEOUT ({duration}{unit})", member, reason)
        except discord.Forbidden:
            await ctx.send(embed=spot_embed(description="❌ Missing permissions.", color=SPOT_RED), delete_after=5)

    @commands.command(name="mute")
    @check_fake_perm("mute")
    @commands.bot_has_permissions(manage_roles=True)
    async def mute(self, ctx, member: discord.Member, *, reason: str = None):
        if member.top_role >= ctx.author.top_role:
            return await ctx.send(embed=spot_embed(description="❌ You can't mute someone equal or higher.", color=SPOT_RED), delete_after=5)
        muted = discord.utils.get(ctx.guild.roles, name="Muted")
        if not muted:
            muted = await ctx.guild.create_role(name="Muted", reason="SPOT mute role")
            for ch in ctx.guild.channels:
                await ch.set_permissions(muted, send_messages=False, speak=False, add_reactions=False)
        await member.add_roles(muted, reason=reason)
        await ctx.send(embed=spot_embed(description=f"✅ **{member}** muted.", color=SPOT_GREEN))
        await self.log_action(ctx, "MUTE", member, reason)

    @commands.command(name="unmute")
    @check_fake_perm("mute")
    @commands.bot_has_permissions(manage_roles=True)
    async def unmute(self, ctx, member: discord.Member):
        muted = discord.utils.get(ctx.guild.roles, name="Muted")
        if not muted or muted not in member.roles:
            return await ctx.send(embed=spot_embed(description="❌ Not muted.", color=SPOT_RED), delete_after=5)
        await member.remove_roles(muted, reason=f"Unmuted by {ctx.author}")
        await ctx.send(embed=spot_embed(description=f"✅ **{member}** unmuted.", color=SPOT_GREEN))
        await self.log_action(ctx, "UNMUTE", member)

    @commands.command(name="warn")
    @check_fake_perm("warn")
    async def warn(self, ctx, member: discord.Member, *, reason: str = None):
        if not reason:
            return await ctx.send(embed=spot_embed(description="❌ Provide a reason.", color=SPOT_RED), delete_after=5)
        gid, uid = str(ctx.guild.id), str(member.id)
        self.warnings.setdefault(gid, {}).setdefault(uid, [])
        self.warnings[gid][uid].append(reason)
        self._save_warnings()
        count = len(self.warnings[gid][uid])
        try:
            await member.send(f"⚠️ Warned in **{ctx.guild.name}**.\nReason: {reason}\nTotal: {count}")
        except Exception:
            pass
        await ctx.send(embed=spot_embed(description=f"✅ **{member}** warned. Total: {count}", color=SPOT_GREEN))
        await self.log_action(ctx, f"WARN (#{count})", member, reason)

    @commands.command(name="warnings")
    @check_fake_perm("warn")
    async def warnings_cmd(self, ctx, member: discord.Member):
        gid, uid = str(ctx.guild.id), str(member.id)
        if gid not in self.warnings or uid not in self.warnings[gid] or not self.warnings[gid][uid]:
            return await ctx.send(embed=spot_embed(description=f"**{member}** has no warnings.", color=SPOT_ORANGE))
        warns = self.warnings[gid][uid]
        embed = spot_embed(title=f"⚠️ Warnings for {member}", description=f"Total: {len(warns)}", color=SPOT_ORANGE)
        for i, w in enumerate(warns, 1):
            embed.add_field(name=f"#{i}", value=w, inline=False)
        await ctx.send(embed=embed)

    @commands.command(name="clearwarns")
    @check_fake_perm("warn")
    async def clearwarns(self, ctx, member: discord.Member):
        gid, uid = str(ctx.guild.id), str(member.id)
        if gid in self.warnings and uid in self.warnings[gid]:
            self.warnings[gid][uid] = []
            self._save_warnings()
        await ctx.send(embed=spot_embed(description=f"✅ Cleared warnings for **{member}**.", color=SPOT_GREEN))
        await self.log_action(ctx, "CLEARWARNS", member)

    @commands.command(name="purge")
    @check_fake_perm("purge")
    @commands.bot_has_permissions(manage_messages=True)
    async def purge(self, ctx, amount: int):
        if amount < 1 or amount > 100:
            return await ctx.send(embed=spot_embed(description="❌ 1-100 only.", color=SPOT_RED), delete_after=5)
        deleted = await ctx.channel.purge(limit=amount + 1)
        msg = await ctx.send(embed=spot_embed(description=f"✅ Deleted {len(deleted)-1} messages.", color=SPOT_GREEN))
        await asyncio.sleep(3)
        await msg.delete()

    @commands.command(name="nuke")
    @check_fake_perm("nuke")
    @commands.bot_has_permissions(manage_channels=True)
    async def nuke(self, ctx):
        ch = ctx.channel
        pos = ch.position
        confirm = await ctx.send(embed=spot_embed(description="⚠️ React ✅ to confirm nuke.", color=SPOT_ORANGE))
        await confirm.add_reaction("✅")
        def check(r, u):
            return u == ctx.author and str(r.emoji) == "✅" and r.message.id == confirm.id
        try:
            await self.bot.wait_for('reaction_add', timeout=15.0, check=check)
        except asyncio.TimeoutError:
            await confirm.delete()
            return await ctx.send(embed=spot_embed(description="❌ Cancelled.", color=SPOT_RED), delete_after=5)
        new = await ch.clone(reason=f"Nuked by {ctx.author}")
        await new.edit(position=pos)
        await ch.delete()
        await new.send(embed=spot_embed(title="💥 Channel Nuked", description=f"By {ctx.author.mention}", color=SPOT_RED))

    @commands.command(name="slowmode")
    @check_fake_perm("manage_channels")
    @commands.bot_has_permissions(manage_channels=True)
    async def slowmode(self, ctx, seconds: int):
        if seconds < 0 or seconds > 21600:
            return await ctx.send(embed=spot_embed(description="❌ 0-21600 seconds.", color=SPOT_RED), delete_after=5)
        await ctx.channel.edit(slowmode_delay=seconds)
        await ctx.send(embed=spot_embed(description=f"✅ Slowmode set to {seconds}s.", color=SPOT_GREEN))

    @commands.command(name="lockdown")
    @check_fake_perm("lockdown")
    @commands.bot_has_permissions(manage_channels=True)
    async def lockdown(self, ctx, role: discord.Role = None):
        target = role or ctx.guild.default_role
        overwrite = ctx.channel.overwrites_for(target)
        overwrite.send_messages = False
        await ctx.channel.set_permissions(target, overwrite=overwrite)
        await ctx.send(embed=spot_embed(title="🔒 Lockdown", description=f"Channel locked for {target.mention}", color=SPOT_RED))

    @commands.command(name="unlock")
    @check_fake_perm("lockdown")
    @commands.bot_has_permissions(manage_channels=True)
    async def unlock(self, ctx, role: discord.Role = None):
        target = role or ctx.guild.default_role
        overwrite = ctx.channel.overwrites_for(target)
        overwrite.send_messages = None
        await ctx.channel.set_permissions(target, overwrite=overwrite)
        await ctx.send(embed=spot_embed(title="🔓 Unlock", description=f"Channel unlocked for {target.mention}", color=SPOT_GREEN))

    @ban.error
    @kick.error
    @timeout.error
    @mute.error
    @unmute.error
    @warn.error
    @purge.error
    @nuke.error
    @lockdown.error
    @unlock.error
    async def mod_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send(embed=spot_embed(description="❌ Missing permissions.", color=SPOT_RED), delete_after=5)
        elif isinstance(error, commands.BotMissingPermissions):
            await ctx.send(embed=spot_embed(description="❌ I lack permissions.", color=SPOT_RED), delete_after=5)
        elif isinstance(error, commands.MemberNotFound):
            await ctx.send(embed=spot_embed(description="❌ Member not found.", color=SPOT_RED), delete_after=5)
        elif isinstance(error, commands.BadArgument):
            await ctx.send(embed=spot_embed(description="❌ Invalid argument.", color=SPOT_RED), delete_after=5)
        else:
            logger.error(f"Mod error: {error}")
            await ctx.send(embed=spot_embed(description=f"❌ Error: {error}", color=SPOT_RED), delete_after=5)

# ═══════════════════════════════════════════════════════════════════════════════
#  FAKE PERMISSIONS COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════
class FakePermsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.group(name="fakepermissions", aliases=["fakeperms", "fp"], invoke_without_command=True)
    @commands.is_owner()
    async def fakeperms(self, ctx):
        embed = spot_embed(title="🔐 Fake Permissions", description="Grant bot-only moderation powers without dangerous Discord perms.")
        embed.add_field(name="Available Perms", value="`" + "`, `".join(VALID_FAKE_PERMS) + "`", inline=False)
        embed.add_field(name="Usage", value="`,fakeperms add @Role ban_members,kick_members`\n`,fakeperms remove @Role ban_members`\n`,fakeperms list [@Role]`\n`,fakeperms reset`", inline=False)
        await ctx.send(embed=embed)

    @fakeperms.command(name="add", aliases=["grant"])
    @commands.is_owner()
    async def fp_add(self, ctx, role: discord.Role, *, perms: str):
        perms_list = [p.strip().lower() for p in perms.split(",")]
        invalid = [p for p in perms_list if p not in VALID_FAKE_PERMS]
        if invalid:
            return await ctx.send(embed=spot_embed(description=f"❌ Invalid: {', '.join(invalid)}", color=SPOT_RED), delete_after=5)
        fake_permissions.grant(ctx.guild.id, role.id, perms_list)
        await ctx.send(embed=spot_embed(description=f"✅ Granted `{', '.join(perms_list)}` to {role.mention}", color=SPOT_GREEN))

    @fakeperms.command(name="remove", aliases=["revoke"])
    @commands.is_owner()
    async def fp_remove(self, ctx, role: discord.Role, *, perms: str):
        perms_list = [p.strip().lower() for p in perms.split(",")]
        fake_permissions.revoke(ctx.guild.id, role.id, perms_list)
        await ctx.send(embed=spot_embed(description=f"✅ Revoked `{', '.join(perms_list)}` from {role.mention}", color=SPOT_ORANGE))

    @fakeperms.command(name="list")
    @commands.is_owner()
    async def fp_list(self, ctx, role: discord.Role = None):
        perms = fake_permissions.list_perms(ctx.guild.id, role.id if role else None)
        if not perms:
            return await ctx.send(embed=spot_embed(description="No fake permissions set.", color=SPOT_ORANGE))
        embed = spot_embed(title="🔐 Fake Permissions List")
        for rid, plist in perms.items():
            r = ctx.guild.get_role(int(rid))
            name = r.mention if r else f"Role {rid}"
            embed.add_field(name=name, value="`" + "`, `".join(plist) + "`" or "None", inline=False)
        await ctx.send(embed=embed)

    @fakeperms.command(name="reset")
    @commands.is_owner()
    async def fp_reset(self, ctx):
        fake_permissions.reset(ctx.guild.id)
        await ctx.send(embed=spot_embed(description="✅ All fake permissions reset.", color=SPOT_GREEN))

# ═══════════════════════════════════════════════════════════════════════════════
#  SNIPE COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════
class SnipeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if not message.guild:
            return
        snipe_system.add_deleted(message)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if not before.guild or before.content == after.content:
            return
        snipe_system.add_edited(before, after)

    @commands.command(name="snipe")
    async def snipe(self, ctx, index: int = 0):
        msg = snipe_system.get_deleted(ctx.channel.id, index)
        if not msg:
            return await ctx.send(embed=spot_embed(description="❌ Nothing to snipe.", color=SPOT_RED), delete_after=5)
        embed = spot_embed(title="🎯 Snipe — Deleted Message", color=SPOT_DARK)
        embed.set_author(name=str(msg["author"]), icon_url=msg["avatar"])
        embed.add_field(name="Content", value=msg["content"] or "*(empty)*", inline=False)
        if msg["attachments"]:
            embed.add_field(name="Attachments", value="\n".join(msg["attachments"]), inline=False)
        embed.set_footer(text=f"Deleted {msg['time'].strftime('%H:%M:%S')} UTC")
        await ctx.send(embed=embed)

    @commands.command(name="esnipe", aliases=["editsnipe"])
    async def esnipe(self, ctx, index: int = 0):
        msg = snipe_system.get_edited(ctx.channel.id, index)
        if not msg:
            return await ctx.send(embed=spot_embed(description="❌ Nothing to esnipe.", color=SPOT_RED), delete_after=5)
        embed = spot_embed(title="📝 Edit Snipe", color=SPOT_DARK)
        embed.set_author(name=str(msg["author"]), icon_url=msg["avatar"])
        embed.add_field(name="Before", value=msg["before"] or "*(empty)*", inline=False)
        embed.add_field(name="After", value=msg["after"] or "*(empty)*", inline=False)
        embed.set_footer(text=f"Edited {msg['time'].strftime('%H:%M:%S')} UTC")
        await ctx.send(embed=embed)

# ═══════════════════════════════════════════════════════════════════════════════
#  VOICE MASTER
# ═══════════════════════════════════════════════════════════════════════════════
class VoiceMasterCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data = load_json(FILES["voicemaster"])
        self.vm = self.data.get("vm", {})

    def save(self):
        save_json(FILES["voicemaster"], {"vm": self.vm})

    def get_guild_vm(self, guild_id: int):
        return self.vm.setdefault(str(guild_id), {"interface_ch": None, "category": None, "channels": {}, "jtc": None})

    @commands.group(name="voicemaster", aliases=["vm"], invoke_without_command=True)
    @commands.has_permissions(manage_channels=True)
    async def voicemaster(self, ctx):
        vm = self.get_guild_vm(ctx.guild.id)
        embed = spot_embed(title="🔊 VoiceMaster")
        embed.add_field(name="Status", value="✅ Active" if vm["interface_ch"] else "❌ Not setup", inline=False)
        if vm["interface_ch"]:
            ch = ctx.guild.get_channel(vm["interface_ch"])
            embed.add_field(name="Interface", value=ch.mention if ch else "Missing", inline=True)
        if vm["category"]:
            cat = ctx.guild.get_channel(vm["category"])
            embed.add_field(name="Category", value=cat.name if cat else "Missing", inline=True)
        if vm["jtc"]:
            jtc = ctx.guild.get_channel(vm["jtc"])
            embed.add_field(name="JTC Channel", value=jtc.mention if jtc else "Missing", inline=True)
        embed.add_field(name="Active Channels", value=len(vm["channels"]), inline=True)
        await ctx.send(embed=embed)

    @voicemaster.command(name="setup")
    @commands.has_permissions(manage_channels=True)
    async def vm_setup(self, ctx, category: discord.CategoryChannel = None):
        vm = self.get_guild_vm(ctx.guild.id)
        if not category:
            category = await ctx.guild.create_category_channel(name="VoiceMaster")
        interface = await ctx.guild.create_text_channel(name="vc-interface", category=category)
        jtc = await ctx.guild.create_voice_channel(name="Join to Create", category=category)
        embed = spot_embed(title="🔊 VoiceMaster", description="Join a voice channel to create your own!\n\n**Controls:**\n🔒 Lock | 🔓 Unlock\n👻 Ghost | 👁️ Unghost\n✏️ Rename | 👥 Limit\n🎵 Music | 👑 Claim")
        msg = await interface.send(embed=embed)
        for emoji in ["🔒", "🔓", "👻", "👁️", "✏️", "👥", "🎵", "👑"]:
            await msg.add_reaction(emoji)
        vm["interface_ch"] = interface.id
        vm["category"] = category.id
        vm["msg_id"] = msg.id
        vm["jtc"] = jtc.id
        self.save()
        await ctx.send(embed=spot_embed(description=f"✅ VoiceMaster setup in {interface.mention}", color=SPOT_GREEN))

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if not member.guild:
            return
        vm = self.get_guild_vm(member.guild.id)
        if not vm.get("category"):
            return
        # Joined JTC
        if after.channel and not before.channel:
            if after.channel.id == vm.get("jtc"):
                cat = member.guild.get_channel(vm["category"])
                if cat:
                    vc = await member.guild.create_voice_channel(
                        name=f"{member.display_name}'s VC",
                        category=cat,
                        reason="VoiceMaster auto-create"
                    )
                    await member.move_to(vc)
                    vm["channels"][str(vc.id)] = member.id
                    self.save()
        # Left a VM channel
        if before.channel and not after.channel:
            cid = str(before.channel.id)
            if cid in vm["channels"]:
                if len(before.channel.members) == 0:
                    await before.channel.delete(reason="VoiceMaster auto-delete")
                    del vm["channels"][cid]
                    self.save()
                else:
                    # Owner left, allow claim
                    pass

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.user_id == self.bot.user.id:
            return
        vm = self.get_guild_vm(payload.guild_id)
        if not vm.get("msg_id") or payload.message_id != vm["msg_id"]:
            return
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        member = guild.get_member(payload.user_id)
        if not member or not member.voice or not member.voice.channel:
            return
        vc = member.voice.channel
        cid = str(vc.id)
        owner_id = vm["channels"].get(cid)
        emoji = str(payload.emoji)
        try:
            if emoji == "🔒":
                await vc.set_permissions(guild.default_role, connect=False)
            elif emoji == "🔓":
                await vc.set_permissions(guild.default_role, connect=True)
            elif emoji == "👻":
                await vc.set_permissions(guild.default_role, view_channel=False)
            elif emoji == "👁️":
                await vc.set_permissions(guild.default_role, view_channel=True)
            elif emoji == "🎵":
                await vc.set_permissions(guild.default_role, speak=False)
            elif emoji == "👑" and not owner_id:
                vm["channels"][cid] = member.id
                self.save()
                await member.send("✅ You claimed ownership of the voice channel!")
        except Exception:
            pass

# ═══════════════════════════════════════════════════════════════════════════════
#  LEVELS SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════
class LevelsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data = load_json(FILES["levels"])
        self.levels = self.data.get("levels", {})
        self.cooldowns = {}

    def save(self):
        save_json(FILES["levels"], {"levels": self.levels})

    def get_user(self, guild_id: int, user_id: int):
        gid, uid = str(guild_id), str(user_id)
        self.levels.setdefault(gid, {}).setdefault(uid, {"xp": 0, "level": 0, "last_msg": 0})
        return self.levels[gid][uid]

    def xp_for_level(self, level: int) -> int:
        return 5 * (level ** 2) + 50 * level + 100

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return
        key = (message.guild.id, message.author.id)
        now = datetime.utcnow().timestamp()
        if key in self.cooldowns and now - self.cooldowns[key] < 60:
            return
        self.cooldowns[key] = now
        user = self.get_user(message.guild.id, message.author.id)
        xp_gain = random.randint(15, 25)
        user["xp"] += xp_gain
        needed = self.xp_for_level(user["level"])
        if user["xp"] >= needed:
            user["level"] += 1
            user["xp"] = 0
            self.save()
            embed = spot_embed(title="🎉 Level Up!", description=f"{message.author.mention} reached level **{user['level']}**!", color=SPOT_GOLD)
            try:
                await message.channel.send(embed=embed)
            except Exception:
                pass
        else:
            self.save()

    @commands.command(name="rank")
    async def rank(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        user = self.get_user(ctx.guild.id, member.id)
        needed = self.xp_for_level(user["level"])
        embed = spot_embed(title=f"📊 {member.display_name}'s Rank")
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Level", value=user["level"], inline=True)
        embed.add_field(name="XP", value=f"{user['xp']}/{needed}", inline=True)
        progress = int((user["xp"] / needed) * 20)
        bar = "█" * progress + "░" * (20 - progress)
        embed.add_field(name="Progress", value=f"`{bar}`", inline=False)
        await ctx.send(embed=embed)

    @commands.command(name="leaderboard", aliases=["lb"])
    async def leaderboard(self, ctx):
        gid = str(ctx.guild.id)
        if gid not in self.levels or not self.levels[gid]:
            return await ctx.send(embed=spot_embed(description="No data yet.", color=SPOT_ORANGE))
        sorted_users = sorted(self.levels[gid].items(), key=lambda x: (x[1]["level"], x[1]["xp"]), reverse=True)[:10]
        embed = spot_embed(title=f"🏆 Leaderboard — {ctx.guild.name}")
        for i, (uid, data) in enumerate(sorted_users, 1):
            member = ctx.guild.get_member(int(uid))
            name = member.mention if member else f"User {uid}"
            embed.add_field(name=f"#{i} {name}", value=f"Level {data['level']} | {data['xp']} XP", inline=False)
        await ctx.send(embed=embed)

# ═══════════════════════════════════════════════════════════════════════════════
#  AUTO RESPONDERS
# ═══════════════════════════════════════════════════════════════════════════════
class AutoResponderCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data = load_json(FILES["autoresponders"])
        self.responders = self.data.get("responders", {})

    def save(self):
        save_json(FILES["autoresponders"], {"responders": self.responders})

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return
        gid = str(message.guild.id)
        if gid not in self.responders:
            return
        content = message.content.lower()
        for trigger, response in self.responders[gid].items():
            if trigger in content:
                try:
                    await message.channel.send(response)
                except Exception:
                    pass
                break

    @commands.group(name="autoresponder", aliases=["ar"], invoke_without_command=True)
    @commands.has_permissions(manage_messages=True)
    async def autoresponder(self, ctx):
        gid = str(ctx.guild.id)
        ars = self.responders.get(gid, {})
        embed = spot_embed(title="💬 Auto Responders")
        if ars:
            for trigger, response in list(ars.items())[:10]:
                embed.add_field(name=f"Trigger: `{trigger}`", value=f"Response: {response[:100]}", inline=False)
        else:
            embed.description = "No auto responders set."
        await ctx.send(embed=embed)

    @autoresponder.command(name="add")
    @commands.has_permissions(manage_messages=True)
    async def ar_add(self, ctx, trigger: str, *, response: str):
        gid = str(ctx.guild.id)
        self.responders.setdefault(gid, {})[trigger.lower()] = response
        self.save()
        await ctx.send(embed=spot_embed(description=f"✅ Added responder: `{trigger}`", color=SPOT_GREEN))

    @autoresponder.command(name="remove")
    @commands.has_permissions(manage_messages=True)
    async def ar_remove(self, ctx, trigger: str):
        gid = str(ctx.guild.id)
        if gid in self.responders and trigger.lower() in self.responders[gid]:
            del self.responders[gid][trigger.lower()]
            self.save()
        await ctx.send(embed=spot_embed(description=f"✅ Removed responder: `{trigger}`", color=SPOT_GREEN))

# ═══════════════════════════════════════════════════════════════════════════════
#  STARBOARD
# ═══════════════════════════════════════════════════════════════════════════════
class StarboardCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data = load_json(FILES["starboard"])
        self.starboards = self.data.get("starboards", {})

    def save(self):
        save_json(FILES["starboard"], {"starboards": self.starboards})

    def get_sb(self, guild_id: int):
        return self.starboards.setdefault(str(guild_id), {"channel": None, "threshold": 3, "messages": {}})

    @commands.group(name="starboard", aliases=["sb"], invoke_without_command=True)
    @commands.has_permissions(manage_channels=True)
    async def starboard(self, ctx):
        sb = self.get_sb(ctx.guild.id)
        ch = ctx.guild.get_channel(sb["channel"]) if sb["channel"] else None
        embed = spot_embed(title="⭐ Starboard")
        embed.add_field(name="Channel", value=ch.mention if ch else "Not set", inline=True)
        embed.add_field(name="Threshold", value=sb["threshold"], inline=True)
        embed.add_field(name="Starred", value=len(sb["messages"]), inline=True)
        await ctx.send(embed=embed)

    @starboard.command(name="channel")
    @commands.has_permissions(manage_channels=True)
    async def sb_channel(self, ctx, channel: discord.TextChannel):
        sb = self.get_sb(ctx.guild.id)
        sb["channel"] = channel.id
        self.save()
        await ctx.send(embed=spot_embed(description=f"✅ Starboard set to {channel.mention}", color=SPOT_GREEN))

    @starboard.command(name="threshold")
    @commands.has_permissions(manage_channels=True)
    async def sb_threshold(self, ctx, threshold: int):
        sb = self.get_sb(ctx.guild.id)
        sb["threshold"] = max(1, threshold)
        self.save()
        await ctx.send(embed=spot_embed(description=f"✅ Threshold set to {threshold}", color=SPOT_GREEN))

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if str(payload.emoji) != "⭐":
            return
        sb = self.get_sb(payload.guild_id)
        if not sb["channel"]:
            return
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        channel = guild.get_channel(payload.channel_id)
        if not channel:
            return
        try:
            message = await channel.fetch_message(payload.message_id)
        except Exception:
            return
        star_count = sum(1 for r in message.reactions if str(r.emoji) == "⭐")
        if star_count < sb["threshold"]:
            return
        sb_ch = guild.get_channel(sb["channel"])
        if not sb_ch:
            return
        mid = str(message.id)
        if mid in sb["messages"]:
            try:
                sb_msg = await sb_ch.fetch_message(sb["messages"][mid])
                embed = sb_msg.embeds[0]
                embed.set_footer(text=f"⭐ {star_count} | #{channel.name}")
                await sb_msg.edit(embed=embed)
            except Exception:
                pass
        else:
            embed = spot_embed(title="⭐ Starred Message", description=message.content or "*No content*", color=SPOT_GOLD)
            embed.set_author(name=str(message.author), icon_url=message.author.display_avatar.url)
            embed.add_field(name="Source", value=f"[Jump]({message.jump_url})", inline=False)
            embed.set_footer(text=f"⭐ {star_count} | #{channel.name}")
            if message.attachments:
                embed.set_image(url=message.attachments[0].url)
            try:
                sb_msg = await sb_ch.send(embed=embed)
                sb["messages"][mid] = sb_msg.id
                self.save()
            except Exception:
                pass

# ═══════════════════════════════════════════════════════════════════════════════
#  COUNTERS
# ═══════════════════════════════════════════════════════════════════════════════
class CountersCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data = load_json(FILES["counters"])
        self.counters = self.data.get("counters", {})

    def save(self):
        save_json(FILES["counters"], {"counters": self.counters})

    def get_guild_counters(self, guild_id: int):
        return self.counters.setdefault(str(guild_id), {})

    async def update_counters(self, guild: discord.Guild):
        gc = self.get_guild_counters(guild.id)
        for cid, cfg in gc.items():
            ch = guild.get_channel(int(cid))
            if not ch:
                continue
            ctype = cfg.get("type", "members")
            if ctype == "members":
                count = guild.member_count
            elif ctype == "bots":
                count = len([m for m in guild.members if m.bot])
            elif ctype == "humans":
                count = len([m for m in guild.members if not m.bot])
            elif ctype == "online":
                count = len([m for m in guild.members if m.status != discord.Status.offline])
            else:
                continue
            fmt = cfg.get("format", "Members: {count}")
            try:
                await ch.edit(name=fmt.format(count=count))
            except Exception:
                pass

    @commands.Cog.listener()
    async def on_member_join(self, member):
        await self.update_counters(member.guild)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        await self.update_counters(member.guild)

    @commands.group(name="counter", invoke_without_command=True)
    @commands.has_permissions(manage_channels=True)
    async def counter(self, ctx):
        gc = self.get_guild_counters(ctx.guild.id)
        embed = spot_embed(title="📊 Counters")
        if gc:
            for cid, cfg in gc.items():
                ch = ctx.guild.get_channel(int(cid))
                embed.add_field(name=ch.name if ch else f"Channel {cid}", value=f"Type: `{cfg['type']}` | Format: `{cfg['format']}`", inline=False)
        else:
            embed.description = "No counters set."
        await ctx.send(embed=embed)

    @counter.command(name="add")
    @commands.has_permissions(manage_channels=True)
    async def counter_add(self, ctx, channel: discord.VoiceChannel, ctype: str, *, fmt: str = "{count} members"):
        if ctype not in ("members", "bots", "humans", "online"):
            return await ctx.send(embed=spot_embed(description="❌ Types: members, bots, humans, online", color=SPOT_RED), delete_after=5)
        gc = self.get_guild_counters(ctx.guild.id)
        gc[str(channel.id)] = {"type": ctype, "format": fmt}
        self.save()
        await self.update_counters(ctx.guild)
        await ctx.send(embed=spot_embed(description=f"✅ Counter added to {channel.mention}", color=SPOT_GREEN))

    @counter.command(name="remove")
    @commands.has_permissions(manage_channels=True)
    async def counter_remove(self, ctx, channel: discord.VoiceChannel):
        gc = self.get_guild_counters(ctx.guild.id)
        if str(channel.id) in gc:
            del gc[str(channel.id)]
            self.save()
        await ctx.send(embed=spot_embed(description=f"✅ Counter removed from {channel.mention}", color=SPOT_GREEN))

# ═══════════════════════════════════════════════════════════════════════════════
#  GIVEAWAYS
# ═══════════════════════════════════════════════════════════════════════════════
class GiveawayCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data = load_json(FILES["giveaways"])
        self.giveaways = self.data.get("giveaways", {})
        self.check_giveaways.start()

    def save(self):
        save_json(FILES["giveaways"], {"giveaways": self.giveaways})

    def cog_unload(self):
        self.check_giveaways.cancel()

    @tasks.loop(seconds=30)
    async def check_giveaways(self):
        now = datetime.utcnow().timestamp()
        for gid, gws in list(self.giveaways.items()):
            for mid, gw in list(gws.items()):
                if now >= gw["end_time"]:
                    guild = self.bot.get_guild(int(gid))
                    if not guild:
                        del gws[mid]
                        continue
                    ch = guild.get_channel(gw["channel"])
                    if not ch:
                        del gws[mid]
                        continue
                    entries = gw["entries"]
                    if entries:
                        winner_id = random.choice(entries)
                        winner = guild.get_member(winner_id)
                        winner_mention = winner.mention if winner else f"<@{winner_id}>"
                        embed = spot_embed(title="🎉 Giveaway Ended!", description=f"**Prize:** {gw['prize']}\n**Winner:** {winner_mention}", color=SPOT_GOLD)
                    else:
                        embed = spot_embed(title="🎉 Giveaway Ended", description=f"**Prize:** {gw['prize']}\nNo entries.", color=SPOT_ORANGE)
                        winner_mention = "No one"
                    try:
                        msg = await ch.fetch_message(int(mid))
                        await msg.edit(embed=embed)
                        if entries:
                            await ch.send(f"🎉 Congratulations {winner_mention}! You won **{gw['prize']}**!")
                    except Exception:
                        pass
                    del gws[mid]
            self.save()

    @commands.command(name="giveaway", aliases=["gstart"])
    @commands.has_permissions(manage_guild=True)
    async def giveaway(self, ctx, duration: str, *, prize: str):
        match = re.match(r"^(\d+)([smhd])$", duration.lower())
        if not match:
            return await ctx.send(embed=spot_embed(description="❌ Format: `1h`, `30m`, `1d`", color=SPOT_RED), delete_after=5)
        val, unit = int(match.group(1)), match.group(2)
        multipliers = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}
        seconds = val * multipliers[unit]
        end_time = datetime.utcnow().timestamp() + seconds
        embed = spot_embed(title="🎉 Giveaway!", description=f"**Prize:** {prize}\nReact with 🎉 to enter!\nEnds <t:{int(end_time)}:R>", color=SPOT_GOLD)
        msg = await ctx.send(embed=embed)
        await msg.add_reaction("🎉")
        self.giveaways.setdefault(str(ctx.guild.id), {})[str(msg.id)] = {
            "prize": prize, "end_time": end_time, "channel": ctx.channel.id, "entries": []
        }
        self.save()

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if str(payload.emoji) != "🎉":
            return
        gid = str(payload.guild_id)
        if gid not in self.giveaways:
            return
        mid = str(payload.message_id)
        if mid not in self.giveaways[gid]:
            return
        if payload.user_id == self.bot.user.id:
            return
        if payload.user_id not in self.giveaways[gid][mid]["entries"]:
            self.giveaways[gid][mid]["entries"].append(payload.user_id)
            self.save()

# ═══════════════════════════════════════════════════════════════════════════════
#  BUMP REMINDER
# ═══════════════════════════════════════════════════════════════════════════════
class BumpCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data = load_json(FILES["bump"])
        self.bumps = self.data.get("bumps", {})
        self.check_bumps.start()

    def save(self):
        save_json(FILES["bump"], {"bumps": self.bumps})

    def cog_unload(self):
        self.check_bumps.cancel()

    @tasks.loop(minutes=1)
    async def check_bumps(self):
        now = datetime.utcnow().timestamp()
        for gid, cfg in list(self.bumps.items()):
            if cfg.get("remind_time") and now >= cfg["remind_time"]:
                guild = self.bot.get_guild(int(gid))
                if not guild:
                    continue
                ch = guild.get_channel(cfg["channel"]) if cfg.get("channel") else None
                if ch:
                    embed = spot_embed(title="⏰ Bump Reminder", description="It's time to `/bump` your server on Disboard!", color=SPOT_GOLD)
                    try:
                        await ch.send(embed=embed)
                    except Exception:
                        pass
                cfg["remind_time"] = now + 7200  # 2 hours
                self.save()

    @commands.group(name="bumpreminder", aliases=["bump"], invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def bumpreminder(self, ctx):
        cfg = self.bumps.get(str(ctx.guild.id), {})
        ch = ctx.guild.get_channel(cfg["channel"]) if cfg.get("channel") else None
        embed = spot_embed(title="⏰ Bump Reminder")
        embed.add_field(name="Status", value="✅ Active" if cfg.get("channel") else "❌ Not set", inline=True)
        embed.add_field(name="Channel", value=ch.mention if ch else "Not set", inline=True)
        await ctx.send(embed=embed)

    @bumpreminder.command(name="channel")
    @commands.has_permissions(manage_guild=True)
    async def bump_channel(self, ctx, channel: discord.TextChannel):
        gid = str(ctx.guild.id)
        self.bumps.setdefault(gid, {})["channel"] = channel.id
        self.bumps[gid]["remind_time"] = datetime.utcnow().timestamp() + 7200
        self.save()
        await ctx.send(embed=spot_embed(description=f"✅ Bump reminders set to {channel.mention}", color=SPOT_GREEN))

    @bumpreminder.command(name="disable")
    @commands.has_permissions(manage_guild=True)
    async def bump_disable(self, ctx):
        self.bumps.pop(str(ctx.guild.id), None)
        self.save()
        await ctx.send(embed=spot_embed(description="✅ Bump reminders disabled.", color=SPOT_GREEN))

# ═══════════════════════════════════════════════════════════════════════════════
#  UTILITY
# ═══════════════════════════════════════════════════════════════════════════════
class Utility(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='avatar', aliases=['av', 'pfp'])
    async def avatar(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        embed = spot_embed(title=f"{member.name}'s Avatar")
        embed.set_image(url=member.display_avatar.url)
        embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.command(name='userinfo', aliases=['ui', 'whois'])
    async def userinfo(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        roles = [r.mention for r in member.roles if r.name != "@everyone"]
        roles_display = ", ".join(roles) if roles else "None"
        status_emoji = {discord.Status.online: "🟢", discord.Status.idle: "🟡", discord.Status.dnd: "🔴", discord.Status.offline: "⚫"}
        embed = spot_embed(title="User Information")
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Name", value=member.name, inline=True)
        embed.add_field(name="Nickname", value=member.nick or "None", inline=True)
        embed.add_field(name="ID", value=member.id, inline=True)
        embed.add_field(name="Status", value=f"{status_emoji.get(member.status, '⚫')} {str(member.status).title()}", inline=True)
        embed.add_field(name="Bot", value="Yes" if member.bot else "No", inline=True)
        embed.add_field(name="Top Role", value=member.top_role.mention, inline=True)
        embed.add_field(name="Account Created", value=f"<t:{int(member.created_at.timestamp())}:R>", inline=True)
        embed.add_field(name="Joined Server", value=f"<t:{int(member.joined_at.timestamp())}:R>", inline=True)
        embed.add_field(name="Role Count", value=len(member.roles) - 1, inline=True)
        embed.add_field(name=f"Roles [{len(roles)}]", value=roles_display[:1024], inline=False)
        embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.command(name='serverinfo', aliases=['si', 'guildinfo'])
    async def serverinfo(self, ctx):
        guild = ctx.guild
        online = len([m for m in guild.members if m.status == discord.Status.online])
        idle = len([m for m in guild.members if m.status == discord.Status.idle])
        dnd = len([m for m in guild.members if m.status == discord.Status.dnd])
        offline = len([m for m in guild.members if m.status == discord.Status.offline])
        text_channels = len(guild.text_channels)
        voice_channels = len(guild.voice_channels)
        categories = len(guild.categories)
        bots = len([m for m in guild.members if m.bot])
        humans = guild.member_count - bots
        embed = spot_embed(title=f"{guild.name} Server Information")
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.add_field(name="Server ID", value=guild.id, inline=True)
        embed.add_field(name="Owner", value=guild.owner.mention, inline=True)
        embed.add_field(name="Created", value=f"<t:{int(guild.created_at.timestamp())}:R>", inline=True)
        embed.add_field(name=f"Members [{guild.member_count}]", value=f"👥 Humans: {humans}\n🤖 Bots: {bots}", inline=True)
        embed.add_field(name="Member Status", value=f"🟢 {online} | 🟡 {idle} | 🔴 {dnd} | ⚫ {offline}", inline=True)
        embed.add_field(name="Roles", value=len(guild.roles), inline=True)
        embed.add_field(name=f"Channels [{len(guild.channels)}]", value=f"📝 Text: {text_channels}\n🔊 Voice: {voice_channels}\n📁 Categories: {categories}", inline=True)
        embed.add_field(name="Emojis", value=len(guild.emojis), inline=True)
        embed.add_field(name="Boost Level", value=f"Level {guild.premium_tier}", inline=True)
        embed.add_field(name="Verification Level", value=str(guild.verification_level).title(), inline=True)
        embed.add_field(name="Boosts", value=guild.premium_subscription_count, inline=True)
        if guild.banner:
            embed.set_image(url=guild.banner.url)
        embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.command(name='roles')
    async def roles(self, ctx):
        guild = ctx.guild
        roles = sorted(guild.roles, key=lambda r: r.position, reverse=True)
        roles = [r for r in roles if r.name != "@everyone"]
        embed = spot_embed(title=f"Roles in {guild.name}", description=f"Total: {len(roles)} roles")
        roles_text = [f"{i}. {r.mention} - {len(r.members)} members" for i, r in enumerate(roles, 1)]
        roles_str = "\n".join(roles_text)
        if len(roles_str) > 4096:
            chunks = [roles_text[i:i+20] for i in range(0, len(roles_text), 20)]
            for chunk in chunks[:5]:
                chunk_embed = spot_embed(title=f"Roles in {guild.name}", description="\n".join(chunk))
                await ctx.send(embed=chunk_embed)
        else:
            embed.description = roles_str
            await ctx.send(embed=embed)

    @commands.command(name='ping')
    async def ping(self, ctx):
        api_latency = round(self.bot.latency * 1000, 2)
        embed = spot_embed(title="🏓 Pong!", color=SPOT_GREEN)
        embed.add_field(name="API Latency", value=f"`{api_latency}ms`", inline=True)
        status = "🟢 Excellent" if api_latency < 100 else "🟡 Good" if api_latency < 200 else "🟠 Fair" if api_latency < 300 else "🔴 Poor"
        embed.add_field(name="Status", value=status, inline=True)
        await ctx.send(embed=embed)

    @commands.command(name="steal")
    @commands.has_permissions(manage_emojis=True)
    async def steal(self, ctx, name: str, emoji: str = None):
        """Steal an emoji from another server or URL"""
        if emoji and emoji.startswith("<"):
            # Custom emoji
            match = re.match(r"<a?:(\w+):(\d+)>", emoji)
            if match:
                emoji_id = match.group(2)
                animated = emoji.startswith("<a")
                url = f"https://cdn.discordapp.com/emojis/{emoji_id}.{'gif' if animated else 'png'}"
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as resp:
                        if resp.status == 200:
                            data = await resp.read()
                            new_emoji = await ctx.guild.create_custom_emoji(name=name, image=data)
                            return await ctx.send(embed=spot_embed(description=f"✅ Stolen emoji: {new_emoji}", color=SPOT_GREEN))
        elif ctx.message.attachments:
            attachment = ctx.message.attachments[0]
            data = await attachment.read()
            new_emoji = await ctx.guild.create_custom_emoji(name=name, image=data)
            return await ctx.send(embed=spot_embed(description=f"✅ Created emoji: {new_emoji}", color=SPOT_GREEN))
        await ctx.send(embed=spot_embed(description="❌ Provide an emoji or image attachment.", color=SPOT_RED), delete_after=5)

# ═══════════════════════════════════════════════════════════════════════════════
#  FUN
# ═══════════════════════════════════════════════════════════════════════════════
class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.eight_ball_responses = [
            "It is certain.", "It is decidedly so.", "Without a doubt.", "Yes - definitely.", "You may rely on it.",
            "As I see it, yes.", "Most likely.", "Outlook good.", "Yes.", "Signs point to yes.",
            "Reply hazy, try again.", "Ask again later.", "Better not tell you now.", "Cannot predict now.", "Concentrate and ask again.",
            "Don't count on it.", "My reply is no.", "My sources say no.", "Outlook not so good.", "Very doubtful."
        ]

    @commands.command(name='8ball', aliases=['eightball', 'ask'])
    async def eight_ball(self, ctx, *, question: str = None):
        if not question:
            return await ctx.send(embed=spot_embed(description="❓ Ask a question! `,8ball <question>`", color=SPOT_RED), delete_after=5)
        response = random.choice(self.eight_ball_responses)
        embed = spot_embed(title="🎱 Magic 8-Ball", color=0x9B59B6)
        embed.add_field(name="Question", value=question, inline=False)
        embed.add_field(name="Answer", value=f"*{response}*", inline=False)
        embed.set_footer(text=f"Asked by {ctx.author}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.command(name='dice', aliases=['roll', 'd'])
    async def dice(self, ctx, dice_notation: str = "1d6"):
        match = re.match(r'^(\d+)?d(\d+)$', dice_notation.lower())
        if not match:
            return await ctx.send(embed=spot_embed(description="❌ Format: `1d6`, `2d20`", color=SPOT_RED), delete_after=5)
        num_dice = int(match.group(1)) if match.group(1) else 1
        num_sides = int(match.group(2))
        if num_dice < 1 or num_dice > 100:
            return await ctx.send(embed=spot_embed(description="❌ 1-100 dice.", color=SPOT_RED), delete_after=5)
        if num_sides < 2 or num_sides > 1000:
            return await ctx.send(embed=spot_embed(description="❌ 2-1000 sides.", color=SPOT_RED), delete_after=5)
        rolls = [random.randint(1, num_sides) for _ in range(num_dice)]
        total = sum(rolls)
        embed = spot_embed(title=f"🎲 Rolling {dice_notation}", color=SPOT_GOLD)
        if num_dice == 1:
            embed.add_field(name="Result", value=f"**{rolls[0]}**", inline=False)
        else:
            rolls_display = ", ".join(map(str, rolls)) if num_dice <= 20 else f"{', '.join(map(str, rolls[:20]))}... ({num_dice - 20} more)"
            embed.add_field(name="Rolls", value=rolls_display, inline=False)
            embed.add_field(name="Total", value=f"**{total}**", inline=False)
        embed.set_footer(text=f"Rolled by {ctx.author}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.command(name='coinflip', aliases=['flip', 'coin'])
    async def coinflip(self, ctx):
        result = random.choice(["Heads", "Tails"])
        embed = spot_embed(title="🪙 Coin Flip", description=f"The coin landed on: **{result}**!", color=SPOT_GOLD)
        embed.set_footer(text=f"Flipped by {ctx.author}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.command(name='meme')
    async def meme(self, ctx):
        subreddits = ['memes', 'dankmemes', 'wholesomememes', 'me_irl']
        subreddit = random.choice(subreddits)
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(f'https://meme-api.com/gimme/{subreddit}') as resp:
                    if resp.status != 200:
                        return await ctx.send(embed=spot_embed(description="❌ Couldn't fetch meme.", color=SPOT_RED), delete_after=5)
                    data = await resp.json()
                    if data.get("nsfw"):
                        return await ctx.send(embed=spot_embed(description="❌ NSFW meme returned.", color=SPOT_RED), delete_after=5)
                    embed = spot_embed(title=data["title"], color=SPOT_ORANGE)
                    embed.set_image(url=data["url"])
                    embed.set_footer(text=f"👍 {data['ups']} | r/{subreddit}")
                    await ctx.send(embed=embed)
            except Exception as e:
                await ctx.send(embed=spot_embed(description=f"❌ Error: {e}", color=SPOT_RED), delete_after=5)

    @commands.command(name="coin", aliases=["balance", "bal"])
    async def coin(self, ctx):
        """Check your SPOT coins"""
        await ctx.send(embed=spot_embed(description=f"🪙 {ctx.author.mention} has **{random.randint(100, 9999)}** SPOT coins.", color=SPOT_GOLD))

# ═══════════════════════════════════════════════════════════════════════════════
#  SERVER ACCESS CONTROL COMMANDS (Owner-only)
# ═══════════════════════════════════════════════════════════════════════════════
class ServerControlCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.group(name="serveraccess", aliases=["sa"], invoke_without_command=True)
    @commands.is_owner()
    async def serveraccess(self, ctx):
        embed = spot_embed(title="🌐 Server Access Control")
        embed.add_field(name="Mode", value=f"`{server_access.mode}`", inline=True)
        embed.add_field(name="Blacklisted", value=len(server_access.blacklist), inline=True)
        embed.add_field(name="Whitelisted", value=len(server_access.whitelist), inline=True)
        await ctx.send(embed=embed)

    @serveraccess.command(name="mode")
    @commands.is_owner()
    async def sa_mode(self, ctx, mode: str):
        if mode not in ("blacklist", "whitelist"):
            return await ctx.send(embed=spot_embed(description="❌ Modes: `blacklist`, `whitelist`", color=SPOT_RED))
        server_access.mode = mode
        server_access.save()
        await ctx.send(embed=spot_embed(description=f"✅ Mode set to `{mode}`", color=SPOT_GREEN))

    @serveraccess.command(name="blacklist")
    @commands.is_owner()
    async def sa_blacklist(self, ctx, guild_id: int):
        server_access.add_blacklist(guild_id)
        guild = self.bot.get_guild(guild_id)
        if guild:
            try:
                await guild.leave()
            except Exception:
                pass
        await ctx.send(embed=spot_embed(description=f"✅ Blacklisted guild `{guild_id}`. Left if present.", color=SPOT_GREEN))

    @serveraccess.command(name="unblacklist")
    @commands.is_owner()
    async def sa_unblacklist(self, ctx, guild_id: int):
        server_access.remove_blacklist(guild_id)
        await ctx.send(embed=spot_embed(description=f"✅ Removed `{guild_id}` from blacklist.", color=SPOT_GREEN))

    @serveraccess.command(name="whitelist")
    @commands.is_owner()
    async def sa_whitelist(self, ctx, guild_id: int):
        server_access.add_whitelist(guild_id)
        await ctx.send(embed=spot_embed(description=f"✅ Whitelisted guild `{guild_id}`.", color=SPOT_GREEN))

    @serveraccess.command(name="unwhitelist")
    @commands.is_owner()
    async def sa_unwhitelist(self, ctx, guild_id: int):
        server_access.remove_whitelist(guild_id)
        await ctx.send(embed=spot_embed(description=f"✅ Removed `{guild_id}` from whitelist.", color=SPOT_ORANGE))

    @serveraccess.command(name="list")
    @commands.is_owner()
    async def sa_list(self, ctx):
        embed = spot_embed(title="🌐 Server Access List")
        embed.add_field(name="Blacklisted", value="\n".join([f"`{g}`" for g in server_access.blacklist]) or "None", inline=False)
        embed.add_field(name="Whitelisted", value="\n".join([f"`{g}`" for g in server_access.whitelist]) or "None", inline=False)
        await ctx.send(embed=embed)

# ═══════════════════════════════════════════════════════════════════════════════
#  HELP COMMAND
# ═══════════════════════════════════════════════════════════════════════════════
class CustomHelp(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="help")
    async def help_cmd(self, ctx, category: str = None):
        if not category:
            embed = spot_embed(title="📖 SPOT Help", description="Prefix: `,` | All embeds use the SPOT dark theme.")
            embed.add_field(name="🛡️ AntiNuke", value="`,antinuke` — View & configure", inline=True)
            embed.add_field(name="🔐 Fake Perms", value="`,fakeperms` — Bot-only moderation powers", inline=True)
            embed.add_field(name="🔨 Moderation", value="`,help moderation` — Ban, kick, mute, etc.", inline=True)
            embed.add_field(name="🎯 Snipe", value="`,snipe` | `,esnipe` — Deleted/edited msgs", inline=True)
            embed.add_field(name="🔊 VoiceMaster", value="`,voicemaster` — Temp voice channels", inline=True)
            embed.add_field(name="📊 Levels", value="`,rank` | `,lb` — XP system", inline=True)
            embed.add_field(name="💬 AutoResponder", value="`,autoresponder` — Auto replies", inline=True)
            embed.add_field(name="⭐ Starboard", value="`,starboard` — Star messages", inline=True)
            embed.add_field(name="📊 Counters", value="`,counter` — Server stats channels", inline=True)
            embed.add_field(name="🎉 Giveaways", value="`,giveaway` — Host giveaways", inline=True)
            embed.add_field(name="⏰ Bump", value="`,bumpreminder` — Disboard reminders", inline=True)
            embed.add_field(name="🔧 Utility", value="`,help utility` — Info commands", inline=True)
            embed.add_field(name="🎉 Fun", value="`,help fun` — Games & entertainment", inline=True)
            embed.add_field(name="🌐 Server Access", value="`,serveraccess` — Control bot servers (owner)", inline=True)
            await ctx.send(embed=embed)
        elif category.lower() == "moderation":
            embed = spot_embed(title="🔨 Moderation Commands")
            embed.add_field(name="Commands", value="`,ban @user [reason]`\n`,kick @user [reason]`\n`,timeout @user <duration> <unit> [reason]` (s/m/h/d)\n`,mute @user [reason]` | `,unmute @user`\n`,warn @user <reason>` | `,warnings @user` | `,clearwarns @user`\n`,purge <amount>` (1-100) | `,nuke`\n`,slowmode <seconds>` | `,lockdown [role]` | `,unlock [role]`", inline=False)
            embed.add_field(name="Fake Perms", value="All moderation commands work with fake permissions! Server owners can grant `,fakeperms` to roles without giving dangerous Discord permissions.", inline=False)
            await ctx.send(embed=embed)
        elif category.lower() == "utility":
            embed = spot_embed(title="🔧 Utility Commands")
            embed.add_field(name="Commands", value="`,avatar [@user]` | `,userinfo [@user]` | `,serverinfo`\n`,roles` | `,ping` | `,steal <name> <emoji/attachment>`", inline=False)
            await ctx.send(embed=embed)
        elif category.lower() == "fun":
            embed = spot_embed(title="🎉 Fun Commands")
            embed.add_field(name="Commands", value="`,8ball <question>` | `,dice [notation]` (e.g. 2d6)\n`,coinflip` | `,meme` | `,coin`", inline=False)
            await ctx.send(embed=embed)
        else:
            await ctx.send(embed=spot_embed(description="❌ Categories: `moderation`, `utility`, `fun`", color=SPOT_RED), delete_after=5)

# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN BOT CLASS
# ═══════════════════════════════════════════════════════════════════════════════
class SpotBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True
        intents.bans = True
        intents.moderation = True
        intents.emojis_and_stickers = True
        intents.integrations = True
        intents.webhooks = True
        intents.invites = True
        intents.voice_states = True
        intents.presences = True
        intents.reactions = True
        intents.message_content = True

        super().__init__(
            command_prefix=',',
            intents=intents,
            help_command=None,
            case_insensitive=True
        )

    async def setup_hook(self):
        print("Loading SPOT cogs...")
        cogs = [
            AntiNuke, Moderation, FakePermsCog, SnipeCog,
            VoiceMasterCog, LevelsCog, AutoResponderCog,
            StarboardCog, CountersCog, GiveawayCog, BumpCog,
            Utility, Fun, ServerControlCog, CustomHelp
        ]
        for cog in cogs:
            try:
                await self.add_cog(cog(self))
                print(f"  ✓ {cog.__name__}")
            except Exception as e:
                print(f"  ✗ {cog.__name__}: {e}")
        print("SPOT loaded!")

    async def on_ready(self):
        print("═" * 50)
        print(f"  SPOT is online")
        print(f"  Logged in as: {self.user.name}")
        print(f"  ID: {self.user.id}")
        print(f"  Discord.py: {discord.__version__}")
        print(f"  Guilds: {len(self.guilds)}")
        print("═" * 50)
        await self.change_presence(
            activity=discord.Activity(type=discord.ActivityType.watching, name="for threats | ,help"),
            status=discord.Status.online
        )

    async def on_guild_join(self, guild):
        if not server_access.is_allowed(guild.id):
            logger.warning(f"Blocked guild {guild.id} ({guild.name}) — not in access list")
            try:
                owner = await self.fetch_user(guild.owner_id)
                if owner:
                    await owner.send(f"⚠️ **SPOT** has left your server **{guild.name}** because it is not authorized to join.")
            except Exception:
                pass
            await guild.leave()
            return
        logger.info(f"Joined guild: {guild.name} ({guild.id})")

    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            return
        elif isinstance(error, commands.MissingPermissions):
            await ctx.send(embed=spot_embed(description="❌ You don't have permission.", color=SPOT_RED), delete_after=5)
        elif isinstance(error, commands.BotMissingPermissions):
            await ctx.send(embed=spot_embed(description="❌ I lack permissions.", color=SPOT_RED), delete_after=5)
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(embed=spot_embed(description=f"❌ Missing: `{error.param.name}`", color=SPOT_RED), delete_after=5)
        elif isinstance(error, commands.BadArgument):
            await ctx.send(embed=spot_embed(description="❌ Invalid argument.", color=SPOT_RED), delete_after=5)
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.send(embed=spot_embed(description=f"⏰ Cooldown: {error.retry_after:.1f}s", color=SPOT_ORANGE), delete_after=5)
        elif isinstance(error, commands.NotOwner):
            await ctx.send(embed=spot_embed(description="❌ Owner only.", color=SPOT_RED), delete_after=5)
        else:
            logger.error(f"Error in {ctx.command}: {error}")
            await ctx.send(embed=spot_embed(description=f"❌ Error: {error}", color=SPOT_RED), delete_after=5)

# ═══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════
async def main():
    bot = SpotBot()
    token = os.environ.get("DISCORD_BOT_TOKEN")
    if not token:
        print("ERROR: DISCORD_BOT_TOKEN not set!")
        print("Set it in Railway Variables or .env for local dev.")
        return
    # Set owner ID from env if provided
    owner_id = os.environ.get("BOT_OWNER_ID")
    if owner_id:
        server_access.owner_id = int(owner_id)
        server_access.save()
    async with bot:
        await bot.start(token)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nSPOT shutdown. Goodbye!")
