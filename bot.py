import asyncio
import datetime
import json
import os
import re
import time
from collections import defaultdict, deque
from typing import Union

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

def load_token():
    token = os.getenv("DISCORD_TOKEN", "").strip()
    if token:
        return token
    env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_file):
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    if key.strip() == "DISCORD_TOKEN":
                        return value.strip().strip('"').strip("'")
    return ""


TOKEN = load_token()
if not TOKEN:
    raise SystemExit("DISCORD_TOKEN environment variable is not set and no .env file found. See .env.example")

OWNER_ID = 847669208296063016

AI_API_KEY = os.getenv("AI_API_KEY", "").strip()
DEFAULT_AI_MODELS = [
    "google/gemma-4-31b-it:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "openai/gpt-oss-20b:free",
    "google/gemma-4-26b-a4b-it:free",
    "cohere/north-mini-code:free",
]
AI_MODELS_FROM_ENV = bool(os.getenv("AI_MODELS"))
AI_MODELS = [m.strip() for m in os.getenv("AI_MODELS", ",".join(DEFAULT_AI_MODELS)).split(",") if m.strip()]
AI_MODEL_INDEX = 0
AI_EXCLUDE = ("content-safety", "clip", "lyria", "embed", "rerank", "whisper", "tts", "image", "safety")
AI_ENABLED = bool(AI_API_KEY)
AI_CHANNEL_ID = None
AI_MEMORY = {}

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

RAID_JOIN_WINDOW = 10
RAID_JOIN_COUNT = 6
JOIN_LOG = deque(maxlen=200)
RAID_JOIN_BUFFER = 60

CHANNEL_CREATE_WINDOW = 3
CHANNEL_CREATE_COUNT = 4
CHANNEL_CREATE_LOG = deque(maxlen=100)

SPAM_WINDOW = 5
SPAM_COUNT = 5
MESSAGE_LOG = defaultdict(lambda: deque(maxlen=100))

INVITE_RE = re.compile(r"(?:discord\.(?:gg|io|me|li)|discordapp\.com/invite)/[\w-]+")
LINK_RE = re.compile(r"https?://[^\s]+", re.IGNORECASE)

BAD_WORDS = [
    "nigger", "nigga", "nga", "nig", "niqqa", "negro", "coon", "spic", "chink", "kike", "wetback", "gook",
    "faggot", "fag", "cunt", "whore", "slut", "bitch",
    "fuck", "fucking", "fucker", "fuckface", "fuckstick", "motherfucker", "motherfucking",
    "asshole", "dick", "dickhead", "dickface", "pussy", "twat",
    "retard", "retarded", "bastard", "cock", "cocksucker", "wanker", "dumbass", "jackass",
    "bitchass", "cuntface", "cum", "cumshot", "blowjob",
    "rape", "raped", "raping", "rapist", "porn", "porno", "pornhub", "porntube", "xvideos",
    "hentai", "onlyfans", "sex", "sexy", "sexting", "naked", "nude", "nudes", "boobs",
    "tits", "titty", "dickpic", "nudity", "kill yourself", "kill urself", "kys", "die",
    "kms", "suicide", "suicidal", "self harm", "self-harm", "neck yourself", "unlive", "self delete",
    "fuck you", "shut the fuck up",
]
LEET_CHARS = {
    "i": "1!|i",
    "o": "0o",
    "e": "3e",
    "a": "4@a",
    "s": "5$s",
    "t": "7+t",
    "b": "8b",
    "g": "96g",
    "l": "1|l",
}


def build_word_pattern(word):
    groups = []
    for ch in word:
        chars = LEET_CHARS.get(ch, re.escape(ch))
        groups.append(f"[{chars}]{{1,3}}")
    return r"[\s.\-_,*|]*".join(groups)


BAD_WORD_RE = re.compile(r"\b(" + "|".join(build_word_pattern(w) for w in BAD_WORDS) + r")\b", re.IGNORECASE)

WATCHER_PERMS = dict(
    view_channel=True,
    read_message_history=True,
    create_instant_invite=True,
    add_reactions=True,
    send_messages=False,
)

WHITELIST_USER_IDS = set()
WHITELIST_ROLE_IDS = set()
WELCOME_ROLE_ID = None
AUTO_RESPONSES = {}
LINK_WHITELIST = set()

DEFAULT_LINK_WHITELIST = {
    "gofile.io", "tenor.com", "giphy.com", "clipy.com", "gfycat.com",
    "imgur.com", "cdn.discordapp.com",
}

TICKET_CONFIG = {}
TICKET_MEMBER_PERMS = dict(
    view_channel=True, read_message_history=True, send_messages=True,
    attach_files=True, embed_links=True, add_reactions=True,
    use_external_emojis=True, use_external_stickers=True,
    use_application_commands=True, create_public_threads=True,
    create_private_threads=True, send_messages_in_threads=True,
    mention_everyone=False, manage_webhooks=False,
)

AUDIT_CHANNEL_NAME = "bot-logs"
BACKUP_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot-backup.json")
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot-config.json")
ROOM_INACTIVE_DAYS = 14
CLEANUP_INTERVAL = 12 * 3600

raiding = False
locked_channels = []
channel_raid_protection = True
spam_detection = True
invite_filter = True
antibot = True
badwords_filter = True
antilink = True
audit_channel_id = None


def is_trusted():
    async def predicate(interaction: discord.Interaction):
        return (
            interaction.user.id == OWNER_ID
            or interaction.user.guild_permissions.administrator
            or interaction.user.id in WHITELIST_USER_IDS
            or any(r.id in WHITELIST_ROLE_IDS for r in interaction.user.roles)
        )

    return app_commands.check(predicate)


def is_whitelisted(member):
    if member.id == OWNER_ID or member.id in WHITELIST_USER_IDS:
        return True
    if member.guild_permissions.administrator:
        return True
    return any(r.id in WHITELIST_ROLE_IDS for r in member.roles)


def fit(text, limit=1900):
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def save_config():
    data = {
        "channel_raid_protection": channel_raid_protection,
        "spam_detection": spam_detection,
        "invite_filter": invite_filter,
        "antibot": antibot,
        "badwords_filter": badwords_filter,
        "antilink": antilink,
        "welcome_role_id": WELCOME_ROLE_ID,
        "auto_responses": AUTO_RESPONSES,
        "link_whitelist": sorted(LINK_WHITELIST),
        "whitelist_users": sorted(WHITELIST_USER_IDS),
        "whitelist_roles": sorted(WHITELIST_ROLE_IDS),
        "room_inactive_days": ROOM_INACTIVE_DAYS,
        "audit_channel_id": audit_channel_id,
        "ai_channel_id": AI_CHANNEL_ID,
    }
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_config():
    global channel_raid_protection, spam_detection, invite_filter, antibot, badwords_filter, antilink
    global WELCOME_ROLE_ID, AUTO_RESPONSES, LINK_WHITELIST, WHITELIST_USER_IDS, WHITELIST_ROLE_IDS
    global ROOM_INACTIVE_DAYS, audit_channel_id, AI_CHANNEL_ID
    if not os.path.exists(CONFIG_FILE):
        return False
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    channel_raid_protection = data.get("channel_raid_protection", True)
    spam_detection = data.get("spam_detection", True)
    invite_filter = data.get("invite_filter", True)
    antibot = data.get("antibot", True)
    badwords_filter = data.get("badwords_filter", True)
    antilink = data.get("antilink", True)
    WELCOME_ROLE_ID = data.get("welcome_role_id")
    AUTO_RESPONSES = dict(data.get("auto_responses", {}))
    LINK_WHITELIST = set(data.get("link_whitelist", []))
    WHITELIST_USER_IDS = set(data.get("whitelist_users", []))
    WHITELIST_ROLE_IDS = set(data.get("whitelist_roles", []))
    ROOM_INACTIVE_DAYS = data.get("room_inactive_days", 14)
    audit_channel_id = data.get("audit_channel_id")
    AI_CHANNEL_ID = data.get("ai_channel_id")
    return True


ROOM_PREFIX = "room-"
MARKET_PREFIX = "examples-marketplace-"


def is_private_room(channel):
    return (
        channel is not None
        and channel.category is not None
        and (channel.name.startswith(ROOM_PREFIX) or channel.name.startswith(MARKET_PREFIX))
    )


async def announce(guild, text):
    channel = guild.system_channel
    if channel is None or not channel.permissions_for(guild.me).send_messages:
        for ch in guild.text_channels:
            if ch.permissions_for(guild.me).send_messages:
                channel = ch
                break
    if channel is not None:
        try:
            await channel.send(text)
        except discord.HTTPException:
            pass


async def audit(guild, text):
    global audit_channel_id
    channel = guild.get_channel(audit_channel_id) if audit_channel_id else None
    if channel is None:
        channel = discord.utils.get(guild.text_channels, name=AUDIT_CHANNEL_NAME)
        if channel is None and guild.me.guild_permissions.manage_channels:
            try:
                channel = await guild.create_text_channel(AUDIT_CHANNEL_NAME, reason="Audit log")
            except discord.HTTPException:
                channel = None
        audit_channel_id = channel.id if channel else None
    if channel is not None and channel.permissions_for(guild.me).send_messages:
        try:
            await channel.send(f"`{datetime.datetime.now(datetime.timezone.utc).strftime('%H:%M')}` {text}")
        except discord.HTTPException:
            pass


async def lockdown_guild(guild):
    global locked_channels
    locked_channels = []
    default_role = guild.default_role
    tasks = []
    for channel in guild.channels:
        if not isinstance(channel, discord.TextChannel) and not isinstance(channel, discord.VoiceChannel):
            continue
        if not channel.permissions_for(guild.me).manage_channels:
            continue
        original = channel.overwrites_for(default_role)
        tasks.append(
            channel.set_permissions(
                default_role, send_messages=False, connect=False, reason="Raid lockdown"
            )
        )
        locked_channels.append((channel.id, original))
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    try:
        await guild.edit(verification_level=discord.VerificationLevel.high, reason="Raid lockdown")
    except discord.HTTPException:
        pass


async def unlock_guild(guild):
    global locked_channels
    default_role = guild.default_role
    tasks = []
    for channel_id, original in locked_channels:
        channel = guild.get_channel(channel_id)
        if channel is None:
            continue
        if not channel.permissions_for(guild.me).manage_channels:
            continue
        overwrite = original if not original.is_empty() else None
        tasks.append(
            channel.set_permissions(default_role, overwrite=overwrite, reason="Raid lockdown lifted")
        )
    locked_channels = []
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    try:
        await guild.edit(verification_level=discord.VerificationLevel.low, reason="Raid lockdown lifted")
    except discord.HTTPException:
        pass


async def trigger_raid(guild, reason):
    global raiding
    raiding = True
    await announce(guild, f":rotating_light: **RAID DETECTED** ({reason}). Locking down the server. New joins will be kicked until it is safe.")
    await audit(guild, f":rotating_light: RAID triggered: {reason}")
    await lockdown_guild(guild)


def serialize_overwrites(channel):
    out = []
    for target, overwrite in channel.overwrites.items():
        allow, deny = overwrite.pair()
        out.append(
            {
                "id": str(target.id),
                "type": "role" if isinstance(target, discord.Role) else "member",
                "allow": allow.value,
                "deny": deny.value,
            }
        )
    return out


def serialize_guild(guild):
    data = {"roles": [], "channels": []}
    for role in guild.roles:
        if role.is_default() or role.is_bot_managed():
            continue
        data["roles"].append(
            {
                "id": str(role.id),
                "name": role.name,
                "color": role.color.value,
                "hoist": role.hoist,
                "mentionable": role.mentionable,
                "permissions": role.permissions.value,
            }
        )
    for channel in guild.channels:
        if isinstance(channel, discord.CategoryChannel):
            data["channels"].append({"type": "category", "name": channel.name, "overwrites": serialize_overwrites(channel)})
        elif isinstance(channel, discord.TextChannel):
            data["channels"].append(
                {
                    "type": "text",
                    "name": channel.name,
                    "category": channel.category.name if channel.category else None,
                    "topic": channel.topic,
                    "slowmode": channel.slowmode_delay,
                    "overwrites": serialize_overwrites(channel),
                }
            )
        elif isinstance(channel, discord.VoiceChannel):
            data["channels"].append(
                {
                    "type": "voice",
                    "name": channel.name,
                    "category": channel.category.name if channel.category else None,
                    "bitrate": channel.bitrate,
                    "overwrites": serialize_overwrites(channel),
                }
            )
    return data


async def apply_overwrites(channel, entry, guild, role_map):
    for ov in entry.get("overwrites", []):
        target = None
        if ov["type"] == "role":
            target = role_map.get(ov["id"])
            if target is None:
                try:
                    target = guild.get_role(int(ov["id"]))
                except (ValueError, OverflowError):
                    target = None
        else:
            try:
                target = guild.get_member(int(ov["id"]))
            except (ValueError, OverflowError):
                target = None
        if target is None:
            continue
        try:
            await channel.set_permissions(
                target,
                overwrite=discord.PermissionOverwrite.from_pair(discord.Permissions(ov["allow"]), discord.Permissions(ov["deny"])),
                reason="Restore",
            )
        except discord.HTTPException:
            pass


async def restore_guild(guild, data):
    role_map = {}
    for r in data.get("roles", []):
        existing = discord.utils.get(guild.roles, name=r["name"])
        if existing:
            role_map[r["id"]] = existing
            continue
        try:
            new = await guild.create_role(
                name=r["name"],
                color=discord.Color(r["color"]),
                hoist=r.get("hoist", False),
                mentionable=r.get("mentionable", False),
                reason="Restore",
            )
            try:
                await new.edit(permissions=discord.Permissions(r["permissions"]), reason="Restore")
            except discord.HTTPException:
                pass
            role_map[r["id"]] = new
        except discord.HTTPException:
            pass

    created_categories = []
    for c in data.get("channels", []):
        try:
            if c["type"] == "category":
                category = discord.utils.get(guild.categories, name=c["name"])
                if category is None:
                    category = await guild.create_category(c["name"], reason="Restore")
                    created_categories.append(category.name)
                await apply_overwrites(category, c, guild, role_map)
            elif c["type"] == "text":
                category = discord.utils.get(guild.categories, name=c["category"]) if c.get("category") else None
                if c.get("category") and category is None:
                    category = await guild.create_category(c["category"], reason="Restore")
                existing = discord.utils.get(guild.text_channels, name=c["name"])
                if existing is None:
                    channel = await guild.create_text_channel(
                        c["name"],
                        category=category,
                        topic=c.get("topic"),
                        slowmode_delay=c.get("slowmode", 0),
                        reason="Restore",
                    )
                    await apply_overwrites(channel, c, guild, role_map)
            elif c["type"] == "voice":
                category = discord.utils.get(guild.categories, name=c["category"]) if c.get("category") else None
                if c.get("category") and category is None:
                    category = await guild.create_category(c["category"], reason="Restore")
                existing = discord.utils.get(guild.voice_channels, name=c["name"])
                if existing is None:
                    channel = await guild.create_voice_channel(c["name"], category=category, reason="Restore")
                    await apply_overwrites(channel, c, guild, role_map)
        except discord.HTTPException:
            continue
    return len(data.get("roles", [])), len(data.get("channels", []))


async def cleanup_rooms():
    for guild in bot.guilds:
        if ROOM_INACTIVE_DAYS <= 0:
            continue
        for ch in guild.text_channels:
            if not (ch.name.startswith(ROOM_PREFIX) or ch.name.startswith(MARKET_PREFIX)):
                continue
            try:
                last = None
                async for m in ch.history(limit=1):
                    last = m
                ref = last.created_at if last else ch.created_at
                if (discord.utils.utcnow() - ref).days >= ROOM_INACTIVE_DAYS:
                    await ch.delete(reason="Inactive room cleanup")
                    await audit(guild, f":broom: Deleted inactive room **{ch.name}** (no messages in {ROOM_INACTIVE_DAYS} days)")
            except discord.HTTPException:
                continue


async def create_private_channel(guild, creator, members, role, category, prefix, default_category_name):
    if category is None:
        category = discord.utils.get(guild.categories, name=default_category_name)
        if category is None:
            category = await guild.create_category(default_category_name)
        await category.set_permissions(guild.default_role, view_channel=False, reason="Private channel")
    name = (prefix + "-".join(m.name.lower() for m in members[:3]))[:100].rstrip("-")
    channel = await guild.create_text_channel(name, category=category)
    await channel.set_permissions(guild.default_role, view_channel=False, reason="Private channel")
    for m in members:
        await channel.set_permissions(m, view_channel=True, send_messages=True, reason="Private channel")
    if role is not None:
        await channel.set_permissions(role, **WATCHER_PERMS, reason="Watcher role")
    await channel.set_permissions(creator, view_channel=True, send_messages=True, reason="Private channel")
    await channel.set_permissions(guild.me, view_channel=True, send_messages=True, reason="Private channel")
    return channel


class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Open Ticket", style=discord.ButtonStyle.primary, custom_id="ticket_open", emoji="\U0001f3ab")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        cfg = TICKET_CONFIG
        if not cfg or cfg.get("guild_id") != guild.id:
            await interaction.response.send_message("Tickets aren't set up yet. Ask an admin to run /ticketsetup.", ephemeral=True)
            return
        open_category = guild.get_channel(cfg.get("open_category_id"))
        if not isinstance(open_category, discord.CategoryChannel):
            await interaction.response.send_message("The open-ticket category is missing.", ephemeral=True)
            return
        name = f"ticket-{interaction.user.name.lower()}"
        if discord.utils.get(open_category.text_channels, name=name):
            await interaction.response.send_message("You already have an open ticket.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        channel = await guild.create_text_channel(name, category=open_category, topic=str(interaction.user.id))
        await channel.set_permissions(guild.default_role, view_channel=False, send_messages=False, reason="Ticket")
        await channel.set_permissions(interaction.user, **TICKET_MEMBER_PERMS, reason="Ticket")
        support_role = guild.get_role(cfg.get("support_role_id"))
        if support_role is not None:
            await channel.set_permissions(support_role, **TICKET_MEMBER_PERMS, reason="Ticket support")
            await channel.send(f"{support_role.mention} {interaction.user.mention} opened a ticket and needs support.")
        await channel.send(
            f"Ticket opened by {interaction.user.mention}. Support will help you shortly.",
            view=CloseTicketView(),
        )
        await interaction.followup.send(f"Ticket opened: {channel.name}", ephemeral=True)


class CloseTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, custom_id="ticket_close")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        cfg = TICKET_CONFIG
        if not cfg or cfg.get("guild_id") != guild.id:
            await interaction.response.send_message("Tickets aren't set up.", ephemeral=True)
            return
        closed_category = guild.get_channel(cfg.get("closed_category_id"))
        if not isinstance(closed_category, discord.CategoryChannel):
            await interaction.response.send_message("The closed-ticket category is missing.", ephemeral=True)
            return
        channel = interaction.channel
        if channel.category == closed_category:
            await interaction.response.send_message("This ticket is already closed.", ephemeral=True)
            return
        await interaction.response.defer()
        opener_id = None
        try:
            opener_id = int(channel.topic) if channel.topic else None
        except (ValueError, TypeError):
            opener_id = None
        if opener_id:
            opener = guild.get_member(opener_id)
            if opener is not None:
                await channel.set_permissions(opener, view_channel=True, send_messages=False, reason="Ticket closed")
        await channel.edit(category=closed_category, reason="Ticket closed")
        await channel.send(f":lock: Ticket closed by {interaction.user.mention}. Openers can no longer reply.")


SYSTEM_PROMPT = "You are a helpful assistant in a Discord server. Be concise, friendly, and use plain text. Keep replies reasonably short."


async def ai_generate(prompt, channel_id):
    global AI_MODEL_INDEX
    history = AI_MEMORY.get(channel_id, deque(maxlen=10))
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages += [{"role": r, "content": t} for r, t in history]
    messages.append({"role": "user", "content": prompt})
    errors = []
    for i in range(len(AI_MODELS)):
        model = AI_MODELS[(AI_MODEL_INDEX + i) % len(AI_MODELS)]
        payload = {"model": model, "messages": messages}
        headers = {"Authorization": f"Bearer {AI_API_KEY}"}
        try:
            async with bot.ai_session.post(
                "https://openrouter.ai/api/v1/chat/completions",
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=45),
            ) as resp:
                data = await resp.json()
                if resp.status != 200:
                    msg = data.get("error", {}).get("message", f"HTTP {resp.status}")
                    errors.append(f"{model}: {msg[:80]}")
                    continue
                text = data["choices"][0]["message"]["content"]
        except Exception as e:
            errors.append(f"{model}: {str(e)[:80]}")
            continue
        AI_MODEL_INDEX = (AI_MODEL_INDEX + i + 1) % len(AI_MODELS)
        AI_MEMORY[channel_id] = deque(list(history) + [("user", prompt), ("assistant", text)], maxlen=10)
        return text, None
    return None, "; ".join(errors)


async def refresh_free_models():
    global AI_MODELS
    try:
        async with bot.ai_session.get(
            "https://openrouter.ai/api/v1/models", timeout=aiohttp.ClientTimeout(total=20)
        ) as resp:
            if resp.status != 200:
                return False
            data = await resp.json()
        models = sorted(
            m["id"]
            for m in data.get("data", [])
            if m.get("pricing", {}).get("prompt") == "0"
            and m.get("pricing", {}).get("completion") == "0"
            and m["id"].endswith(":free")
            and not any(bad in m["id"].lower() for bad in AI_EXCLUDE)
        )
        if not models:
            return False
        AI_MODELS = models
        return True
    except Exception:
        return False


async def model_refresh_loop():
    await bot.wait_until_ready()
    while not bot.is_closed():
        await asyncio.sleep(24 * 3600)
        try:
            if await refresh_free_models():
                print(f"Refreshed free AI model list: {len(AI_MODELS)} models")
        except Exception as e:
            print(e)


async def room_cleanup_loop():
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            await cleanup_rooms()
        except Exception as e:
            print(e)
        await asyncio.sleep(CLEANUP_INTERVAL)


@bot.event
async def on_ready():
    bot.ai_session = aiohttp.ClientSession()
    if not AI_MODELS_FROM_ENV:
        try:
            if await refresh_free_models():
                print(f"Loaded {len(AI_MODELS)} free AI models")
        except Exception as e:
            print(e)
    if load_config():
        print("Loaded config from bot-config.json")
    for gid in (1536762391851696199, 1521614024587083908):
        guild = discord.Object(id=gid)
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)
    bot.tree.clear_commands(guild=None)
    await bot.tree.sync()
    bot.loop.create_task(room_cleanup_loop())
    bot.loop.create_task(model_refresh_loop())
    print(f"Logged in as {bot.user} ({bot.user.id}) - slash commands synced")


@bot.event
async def on_close():
    session = getattr(bot, "ai_session", None)
    if session is not None:
        await session.close()


@bot.event
async def on_member_join(member):
    if member.bot:
        if antibot and member.id != bot.user.id:
            try:
                await member.kick(reason="Unapproved bot join")
                await announce(member.guild, f":robot: Kicked unapproved bot **{member.name}**.")
                await audit(member.guild, f":robot: Kicked unapproved bot **{member.name}**")
            except discord.HTTPException:
                pass
        return

    if WELCOME_ROLE_ID:
        role = member.guild.get_role(WELCOME_ROLE_ID)
        if role is not None:
            try:
                await member.add_roles(role, reason="Welcome role")
            except discord.HTTPException:
                pass

    if raiding:
        try:
            await member.kick(reason="Join during raid lockdown")
        except discord.HTTPException:
            pass
        return

    now = time.monotonic()
    JOIN_LOG.append((now, member))
    recent = [m for t, m in JOIN_LOG if now - t <= RAID_JOIN_BUFFER]
    fresh = [m for t, m in recent if (now - t) <= RAID_JOIN_WINDOW]
    if len(fresh) >= RAID_JOIN_COUNT:
        await trigger_raid(member.guild, f"{len(fresh)} joins in {RAID_JOIN_WINDOW}s")


@bot.event
async def on_guild_channel_create(channel):
    if not channel_raid_protection:
        return
    guild = channel.guild
    now = time.monotonic()
    CHANNEL_CREATE_LOG.append((now, channel))
    fresh = [c for t, c in CHANNEL_CREATE_LOG if now - t <= CHANNEL_CREATE_WINDOW]
    if len(fresh) > CHANNEL_CREATE_COUNT:
        await announce(
            guild,
            f":rotating_light: **CHANNEL RAID DETECTED** - {len(fresh)} channels created in {CHANNEL_CREATE_WINDOW}s. Deleting them...",
        )
        await audit(guild, f":rotating_light: Channel raid: {len(fresh)} channels created in {CHANNEL_CREATE_WINDOW}s")
        deleted = 0
        for c in fresh:
            try:
                await c.delete(reason="Channel creation raid")
                deleted += 1
            except discord.HTTPException:
                pass
        await announce(guild, f":wastebasket: Deleted **{deleted}** channels created during the raid.")
        await audit(guild, f":wastebasket: Deleted {deleted} raided channels")


@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    content = message.content

    if not is_whitelisted(message.author):
        if invite_filter and INVITE_RE.search(content):
            try:
                await message.delete()
                await message.channel.send(f"{message.author.mention}, invites are not allowed here.", delete_after=5)
            except discord.HTTPException:
                pass

        if badwords_filter and BAD_WORD_RE.search(content):
            try:
                await message.delete()
                await message.channel.send(f"{message.author.mention}, that word isn't allowed here.", delete_after=5)
                await audit(message.guild, f":mute: Bad word from **{message.author}** deleted in #{message.channel.name}")
            except discord.HTTPException:
                pass

        if antilink:
            links = LINK_RE.findall(content)
            allowed = LINK_WHITELIST | DEFAULT_LINK_WHITELIST
            bad = [l for l in links if not any(d in l.lower() for d in allowed)]
            if bad:
                try:
                    await message.delete()
                    await message.channel.send(f"{message.author.mention}, links aren't allowed here.", delete_after=5)
                except discord.HTTPException:
                    pass

        if spam_detection:
            now = time.monotonic()
            log = MESSAGE_LOG[message.author.id]
            log.append(now)
            fresh = [t for t in log if now - t <= SPAM_WINDOW]
            MESSAGE_LOG[message.author.id] = deque(fresh, maxlen=100)
            if len(fresh) >= SPAM_COUNT and message.guild.me.guild_permissions.moderate_members:
                try:
                    await message.author.timeout(
                        discord.utils.utcnow() + datetime.timedelta(minutes=10),
                        reason="Spam detection",
                    )
                    await message.channel.send(f":mute: **{message.author}** muted for spamming.")
                except discord.HTTPException:
                    pass

    for trigger, response in AUTO_RESPONSES.items():
        if trigger in content.lower():
            await message.channel.send(response)
            break

    if AI_ENABLED and AI_CHANNEL_ID and message.channel.id == AI_CHANNEL_ID:
        async with message.channel.typing():
            text, err = await ai_generate(content, message.channel.id)
        if err:
            await message.channel.send(f":warning: AI error: {fit(err, 300)}")
        else:
            await message.channel.send(fit(text))


@bot.tree.command(name="room", description="Create a private channel only for specific people")
@app_commands.describe(
    member="Who the channel is for",
    member2="Optional second person",
    member3="Optional third person",
    role="Optional role that can only WATCH (view, read history, invites, reactions)",
    category="Optional category to create the channel in",
)
@is_trusted()
async def room(interaction: discord.Interaction, member: discord.Member, member2: discord.Member = None, member3: discord.Member = None, role: discord.Role = None, category: discord.CategoryChannel = None):
    members = [m for m in (member, member2, member3) if m is not None]
    if not interaction.guild.me.guild_permissions.manage_channels:
        await interaction.response.send_message("I need the **Manage Channels** permission for this.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)

    channel = await create_private_channel(interaction.guild, interaction.user, members, role, category, ROOM_PREFIX, "Private Rooms")

    names = ", ".join(m.mention for m in members)
    await channel.send(f"Private channel for {names} created by {interaction.user.mention}.")
    await audit(interaction.guild, f":house: Room **{channel.name}** created by {interaction.user} for {', '.join(m.name for m in members)}")
    await interaction.followup.send(f"Done. {channel.mention}")


@bot.tree.command(name="marketplacecreate", description="Create a marketplace channel (same as a private room)")
@app_commands.describe(
    member="Who the channel is for",
    member2="Optional second person",
    member3="Optional third person",
    role="Optional role that can only WATCH (view, read history, invites, reactions)",
    category="Optional category to create the channel in",
)
@is_trusted()
async def marketplacecreate(interaction: discord.Interaction, member: discord.Member, member2: discord.Member = None, member3: discord.Member = None, role: discord.Role = None, category: discord.CategoryChannel = None):
    members = [m for m in (member, member2, member3) if m is not None]
    if not interaction.guild.me.guild_permissions.manage_channels:
        await interaction.response.send_message("I need the **Manage Channels** permission for this.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    channel = await create_private_channel(interaction.guild, interaction.user, members, role, category, MARKET_PREFIX, "Marketplace")
    names = ", ".join(m.mention for m in members)
    await channel.send(f"Marketplace channel for {names} created by {interaction.user.mention}.")
    await audit(interaction.guild, f":shopping_cart: Marketplace **{channel.name}** created by {interaction.user} for {', '.join(m.name for m in members)}")
    await interaction.followup.send(f"Done. {channel.mention}")


@bot.tree.command(name="roomadd", description="Add a user to your private room")
@app_commands.describe(member="User to add", channel="Room (defaults to current channel)")
@is_trusted()
async def roomadd(interaction: discord.Interaction, member: discord.Member, channel: discord.TextChannel = None):
    channel = channel or interaction.channel
    if not is_private_room(channel) or not channel.permissions_for(interaction.user).view_channel:
        await interaction.response.send_message("This isn't your private room.", ephemeral=True)
        return
    await channel.set_permissions(member, view_channel=True, send_messages=True, reason="Room add")
    await interaction.response.send_message(f"Added {member.mention} to {channel.mention}.", ephemeral=True)


@bot.tree.command(name="roomremove", description="Remove a user from your private room")
@app_commands.describe(member="User to remove", channel="Room (defaults to current channel)")
@is_trusted()
async def roomremove(interaction: discord.Interaction, member: discord.Member, channel: discord.TextChannel = None):
    channel = channel or interaction.channel
    if not is_private_room(channel) or not channel.permissions_for(interaction.user).view_channel:
        await interaction.response.send_message("This isn't your private room.", ephemeral=True)
        return
    await channel.set_permissions(member, overwrite=None, reason="Room remove")
    await interaction.response.send_message(f"Removed {member.mention} from {channel.mention}.", ephemeral=True)


@bot.tree.command(name="roomclose", description="Close and delete your private room")
@app_commands.describe(channel="Room (defaults to current channel)")
@is_trusted()
async def roomclose(interaction: discord.Interaction, channel: discord.TextChannel = None):
    channel = channel or interaction.channel
    if not is_private_room(channel) or not channel.permissions_for(interaction.user).manage_channels:
        await interaction.response.send_message("This isn't your private room.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    await audit(interaction.guild, f":house: Room **{channel.name}** closed by {interaction.user}")
    await channel.delete(reason="Room closed")
    await interaction.followup.send("Room deleted.")


@bot.tree.command(name="roomlist", description="Show who has access to a private room")
@app_commands.describe(channel="Room (defaults to current channel)")
@is_trusted()
async def roomlist(interaction: discord.Interaction, channel: discord.TextChannel = None):
    channel = channel or interaction.channel
    if not is_private_room(channel) or not channel.permissions_for(interaction.user).view_channel:
        await interaction.response.send_message("This isn't your private room.", ephemeral=True)
        return
    members = []
    roles = []
    for target, overwrite in channel.overwrites.items():
        if overwrite.view_channel:
            if isinstance(target, discord.Member):
                members.append(target.mention)
            elif isinstance(target, discord.Role):
                roles.append(target.mention)
    await interaction.response.send_message(
        f"**{channel.name}**\nMembers: {', '.join(members) if members else 'none'}\nRoles: {', '.join(roles) if roles else 'none'}",
        ephemeral=True,
    )


@bot.tree.command(name="watcheradd", description="Give a role watch-only access to a channel")
@app_commands.describe(role="Role to give watch-only access", channel="Channel (defaults to current channel)")
@is_trusted()
async def watcheradd(interaction: discord.Interaction, role: discord.Role, channel: discord.TextChannel = None):
    channel = channel or interaction.channel
    await channel.set_permissions(role, **WATCHER_PERMS, reason="Watcher role")
    await interaction.response.send_message(f"{role.mention} can now watch {channel.mention} but not type.", ephemeral=True)


@bot.tree.command(name="watcherremove", description="Remove watch-only access from a role")
@app_commands.describe(role="Role to remove", channel="Channel (defaults to current channel)")
@is_trusted()
async def watcherremove(interaction: discord.Interaction, role: discord.Role, channel: discord.TextChannel = None):
    channel = channel or interaction.channel
    await channel.set_permissions(role, overwrite=None, reason="Watcher role removed")
    await interaction.response.send_message(f"Removed watch-only access for {role.mention} on {channel.mention}.", ephemeral=True)


@bot.tree.command(name="ban", description="Ban a member")
@app_commands.describe(member="User to ban", reason="Ban reason")
@is_trusted()
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = None):
    if not interaction.guild.me.guild_permissions.ban_members:
        await interaction.response.send_message("I need the **Ban Members** permission for this.", ephemeral=True)
        return
    await member.ban(reason=reason or "Banned via command")
    await announce(interaction.guild, f":hammer: **{member}** banned by {interaction.user.mention}" + (f" - {reason}" if reason else ""))
    await audit(interaction.guild, f":hammer: **{member}** banned by {interaction.user}" + (f" - {reason}" if reason else ""))


@bot.tree.command(name="unban", description="Unban a user by ID")
@app_commands.describe(user_id="The user ID to unban", reason="Reason")
@is_trusted()
async def unban(interaction: discord.Interaction, user_id: str, reason: str = None):
    if not interaction.guild.me.guild_permissions.ban_members:
        await interaction.response.send_message("I need the **Ban Members** permission for this.", ephemeral=True)
        return
    try:
        user = await bot.fetch_user(int(user_id))
    except (discord.NotFound, discord.HTTPException, ValueError):
        await interaction.response.send_message("That doesn't look like a valid user ID.", ephemeral=True)
        return
    try:
        await interaction.guild.unban(user, reason=reason or "Unbanned via command")
        await audit(interaction.guild, f":hammer: **{user}** unbanned by {interaction.user}")
        await interaction.response.send_message(f"Unbanned {user}.", ephemeral=True)
    except discord.HTTPException:
        await interaction.response.send_message("Could not unban that user.", ephemeral=True)


@bot.tree.command(name="kick", description="Kick a member")
@app_commands.describe(member="User to kick", reason="Kick reason")
@is_trusted()
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = None):
    if not interaction.guild.me.guild_permissions.kick_members:
        await interaction.response.send_message("I need the **Kick Members** permission for this.", ephemeral=True)
        return
    await member.kick(reason=reason or "Kicked via command")
    await announce(interaction.guild, f":boot: **{member}** kicked by {interaction.user.mention}" + (f" - {reason}" if reason else ""))
    await audit(interaction.guild, f":boot: **{member}** kicked by {interaction.user}" + (f" - {reason}" if reason else ""))


@bot.tree.command(name="purge", description="Delete a number of messages in a channel")
@app_commands.describe(count="How many messages to delete (max 100)", channel="Channel (defaults to current channel)")
@is_trusted()
async def purge(interaction: discord.Interaction, count: int, channel: discord.TextChannel = None):
    channel = channel or interaction.channel
    count = max(1, min(count, 100))
    await interaction.response.defer(ephemeral=True)
    deleted = await channel.purge(limit=count)
    await interaction.followup.send(f"Deleted {len(deleted)} messages in {channel.mention}.")


@bot.tree.command(name="lockchannel", description="Lock a channel so no one can type")
@app_commands.describe(channel="Channel (defaults to current channel)")
@is_trusted()
async def lockchannel(interaction: discord.Interaction, channel: discord.TextChannel = None):
    channel = channel or interaction.channel
    await channel.set_permissions(interaction.guild.default_role, send_messages=False, reason="Channel lock")
    await interaction.response.send_message(f":lock: {channel.mention} locked.", ephemeral=True)


@bot.tree.command(name="unlockchannel", description="Unlock a channel")
@app_commands.describe(channel="Channel (defaults to current channel)")
@is_trusted()
async def unlockchannel(interaction: discord.Interaction, channel: discord.TextChannel = None):
    channel = channel or interaction.channel
    await channel.set_permissions(interaction.guild.default_role, overwrite=None, reason="Channel unlock")
    await interaction.response.send_message(f":unlock: {channel.mention} unlocked.", ephemeral=True)


@bot.tree.command(name="slowmode", description="Set slowmode on a channel")
@app_commands.describe(seconds="Seconds between messages (0 to disable)", channel="Channel (defaults to current channel)")
@is_trusted()
async def slowmode(interaction: discord.Interaction, seconds: int, channel: discord.TextChannel = None):
    channel = channel or interaction.channel
    seconds = max(0, min(seconds, 21600))
    await channel.edit(slowmode_delay=seconds)
    await interaction.response.send_message(
        f"Slowmode on {channel.mention}: {seconds}s" if seconds else f"Slowmode disabled on {channel.mention}.",
        ephemeral=True,
    )


@bot.tree.command(name="lock", description="Lock down the whole server (blocks sending everywhere)")
@is_trusted()
async def lock(interaction: discord.Interaction):
    if not interaction.guild.me.guild_permissions.manage_channels:
        await interaction.response.send_message("I need the **Manage Channels** permission for this.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    await lockdown_guild(interaction.guild)
    await announce(interaction.guild, ":lock: **Server locked down** manually by " + interaction.user.mention)
    await audit(interaction.guild, f":lock: Server locked down by {interaction.user}")
    await interaction.followup.send("Server locked down.")


@bot.tree.command(name="unlock", description="Lift the lockdown")
@is_trusted()
async def unlock(interaction: discord.Interaction):
    global raiding
    await interaction.response.defer(ephemeral=True)
    await unlock_guild(interaction.guild)
    raiding = False
    await announce(interaction.guild, ":unlock: **Lockdown lifted** by " + interaction.user.mention)
    await audit(interaction.guild, f":unlock: Lockdown lifted by {interaction.user}")
    await interaction.followup.send("Lockdown lifted.")


@bot.tree.command(name="endraid", description="End an active raid lockdown and unblock the server")
@is_trusted()
async def endraid(interaction: discord.Interaction):
    global raiding
    await interaction.response.defer(ephemeral=True)
    await unlock_guild(interaction.guild)
    raiding = False
    await announce(interaction.guild, ":white_check_mark: **Raid lockdown lifted** by " + interaction.user.mention)
    await audit(interaction.guild, f":white_check_mark: Raid lockdown lifted by {interaction.user}")
    await interaction.followup.send("Raid lockdown lifted.")


@bot.tree.command(name="raidprotection", description="Turn ON automatic channel-creation raid detection")
@is_trusted()
async def raidprotection_cmd(interaction: discord.Interaction):
    global channel_raid_protection
    channel_raid_protection = True
    await interaction.response.send_message(
        f"Channel raid protection **ON** - if more than {CHANNEL_CREATE_COUNT} channels are created within {CHANNEL_CREATE_WINDOW}s, they will be auto-deleted.",
        ephemeral=True,
    )


@bot.tree.command(name="raidprotectionoff", description="Turn OFF automatic channel-creation raid detection")
@is_trusted()
async def raidprotectionoff_cmd(interaction: discord.Interaction):
    global channel_raid_protection
    channel_raid_protection = False
    await interaction.response.send_message("Channel raid protection **OFF** - channels will no longer be auto-deleted.", ephemeral=True)


@bot.tree.command(name="spamdetect", description="Turn ON auto-mute for spammers")
@is_trusted()
async def spamdetect_cmd(interaction: discord.Interaction):
    global spam_detection
    spam_detection = True
    await interaction.response.send_message("Spam detection **ON** - users sending 5+ messages in 5s get a 10min mute.", ephemeral=True)


@bot.tree.command(name="spamdetectoff", description="Turn OFF auto-mute for spammers")
@is_trusted()
async def spamdetectoff_cmd(interaction: discord.Interaction):
    global spam_detection
    spam_detection = False
    await interaction.response.send_message("Spam detection **OFF**.", ephemeral=True)


@bot.tree.command(name="invitefilter", description="Turn ON auto-delete of Discord invites by non-admins")
@is_trusted()
async def invitefilter_cmd(interaction: discord.Interaction):
    global invite_filter
    invite_filter = True
    await interaction.response.send_message("Invite filter **ON** - Discord invites posted by non-admins will be deleted.", ephemeral=True)


@bot.tree.command(name="invitefilteroff", description="Turn OFF auto-delete of Discord invites")
@is_trusted()
async def invitefilteroff_cmd(interaction: discord.Interaction):
    global invite_filter
    invite_filter = False
    await interaction.response.send_message("Invite filter **OFF**.", ephemeral=True)


@bot.tree.command(name="antibot", description="Turn ON auto-kick of bots that join unapproved")
@is_trusted()
async def antibot_cmd(interaction: discord.Interaction):
    global antibot
    antibot = True
    await interaction.response.send_message("Anti-bot **ON** - any bot joining will be kicked.", ephemeral=True)


@bot.tree.command(name="antibotoff", description="Turn OFF auto-kick of bots")
@is_trusted()
async def antibotoff_cmd(interaction: discord.Interaction):
    global antibot
    antibot = False
    await interaction.response.send_message("Anti-bot **OFF**.", ephemeral=True)


@bot.tree.command(name="welcomerole", description="Auto-assign a role to new members (no role = off)")
@app_commands.describe(role="Role to assign on join")
@is_trusted()
async def welcomerole(interaction: discord.Interaction, role: discord.Role = None):
    global WELCOME_ROLE_ID
    WELCOME_ROLE_ID = role.id if role else None
    await interaction.response.send_message(
        f"Welcome role set to {role.mention}." if role else "Welcome role disabled.",
        ephemeral=True,
    )


@bot.tree.command(name="autoresponse", description="Add an auto-response (word triggers a reply)")
@app_commands.describe(trigger="Word or phrase to trigger on", response="What the bot replies")
@is_trusted()
async def autoresponse(interaction: discord.Interaction, trigger: str, response: str):
    AUTO_RESPONSES[trigger.lower()] = response
    await interaction.response.send_message(f"Auto-response added: `{trigger}` -> {response}", ephemeral=True)


@bot.tree.command(name="autoresponseremove", description="Remove an auto-response")
@app_commands.describe(trigger="The trigger word to remove")
@is_trusted()
async def autoresponseremove(interaction: discord.Interaction, trigger: str):
    removed = AUTO_RESPONSES.pop(trigger.lower(), None)
    await interaction.response.send_message(
        f"Removed `{trigger}`." if removed else f"`{trigger}` isn't an auto-response.",
        ephemeral=True,
    )


@bot.tree.command(name="autoresponselist", description="List all auto-responses")
@is_trusted()
async def autoresponselist(interaction: discord.Interaction):
    if not AUTO_RESPONSES:
        await interaction.response.send_message("No auto-responses set.", ephemeral=True)
        return
    lines = "\n".join(f"`{k}` -> {v}" for k, v in AUTO_RESPONSES.items())
    await interaction.response.send_message(f"**Auto-responses:**\n{lines}", ephemeral=True)


@bot.tree.command(name="badwords", description="Turn ON bad word filter (deletes messages with profanity)")
@is_trusted()
async def badwords_cmd(interaction: discord.Interaction):
    global badwords_filter
    badwords_filter = True
    await interaction.response.send_message("Bad word filter **ON** - profanity gets deleted.", ephemeral=True)


@bot.tree.command(name="badwordsoff", description="Turn OFF bad word filter")
@is_trusted()
async def badwordsoff_cmd(interaction: discord.Interaction):
    global badwords_filter
    badwords_filter = False
    await interaction.response.send_message("Bad word filter **OFF**.", ephemeral=True)


@bot.tree.command(name="antilink", description="Turn ON link blocking (all links blocked unless whitelisted)")
@is_trusted()
async def antilink_cmd(interaction: discord.Interaction):
    global antilink
    antilink = True
    await interaction.response.send_message("Anti-link **ON** - links posted by non-whitelisted users get deleted.", ephemeral=True)


@bot.tree.command(name="antilinkoff", description="Turn OFF link blocking")
@is_trusted()
async def antilinkoff_cmd(interaction: discord.Interaction):
    global antilink
    antilink = False
    await interaction.response.send_message("Anti-link **OFF**.", ephemeral=True)


@bot.tree.command(name="linkwhitelist", description="Allow a domain through the link filter (e.g. youtube.com)")
@app_commands.describe(domain="Domain to allow")
@is_trusted()
async def linkwhitelist(interaction: discord.Interaction, domain: str):
    LINK_WHITELIST.add(domain.lower())
    await interaction.response.send_message(
        f"`{domain.lower()}` added to link whitelist. Current: {', '.join(sorted(LINK_WHITELIST)) if LINK_WHITELIST else 'none'}",
        ephemeral=True,
    )


@bot.tree.command(name="linkwhitelistremove", description="Remove a domain from the link whitelist")
@app_commands.describe(domain="Domain to remove")
@is_trusted()
async def linkwhitelistremove(interaction: discord.Interaction, domain: str):
    LINK_WHITELIST.discard(domain.lower())
    await interaction.response.send_message(
        f"`{domain.lower()}` removed. Current: {', '.join(sorted(LINK_WHITELIST)) if LINK_WHITELIST else 'none'}",
        ephemeral=True,
    )


@bot.tree.command(name="whitelist", description="Exempt a user or role from message protections (links, bad words, spam, invites)")
@app_commands.describe(target="User or role to exempt")
@is_trusted()
async def whitelist(interaction: discord.Interaction, target: Union[discord.Member, discord.Role]):
    if isinstance(target, discord.Role):
        WHITELIST_ROLE_IDS.add(target.id)
        await interaction.response.send_message(f"{target.mention} role is now whitelisted.", ephemeral=True)
    else:
        WHITELIST_USER_IDS.add(target.id)
        await interaction.response.send_message(f"{target.mention} is now whitelisted.", ephemeral=True)


@bot.tree.command(name="whitelistremove", description="Remove a user or role from the whitelist")
@app_commands.describe(target="User or role to un-exempt")
@is_trusted()
async def whitelistremove(interaction: discord.Interaction, target: Union[discord.Member, discord.Role]):
    if isinstance(target, discord.Role):
        WHITELIST_ROLE_IDS.discard(target.id)
        await interaction.response.send_message(f"{target.mention} role is no longer whitelisted.", ephemeral=True)
    else:
        WHITELIST_USER_IDS.discard(target.id)
        await interaction.response.send_message(f"{target.mention} is no longer whitelisted.", ephemeral=True)


config_group = app_commands.Group(name="config", description="Save, load or delete bot settings")


@config_group.command(name="create", description="Save all current settings to a config file")
@is_trusted()
async def config_create(interaction: discord.Interaction):
    save_config()
    await audit(interaction.guild, f":floppy_disk: Config saved by {interaction.user}")
    await interaction.response.send_message(
        f"Config saved to `{CONFIG_FILE}` - toggles, whitelists, welcome role, auto-responses, link whitelist and cleanup days.",
        ephemeral=True,
    )


@config_group.command(name="load", description="Load settings from the saved config file")
@is_trusted()
async def config_load(interaction: discord.Interaction):
    if load_config():
        await audit(interaction.guild, f":arrows_counterclockwise: Config loaded by {interaction.user}")
        await interaction.response.send_message("Config loaded - all settings restored.", ephemeral=True)
    else:
        await interaction.response.send_message("No config file found. Use `/config create` first.", ephemeral=True)


@config_group.command(name="delete", description="Delete the saved config file")
@is_trusted()
async def config_delete(interaction: discord.Interaction):
    if os.path.exists(CONFIG_FILE):
        os.remove(CONFIG_FILE)
        await interaction.response.send_message("Config file deleted.", ephemeral=True)
    else:
        await interaction.response.send_message("No config file found.", ephemeral=True)


bot.tree.add_command(config_group)


@bot.tree.command(name="ticketadd", description="Add a user to the current ticket")
@app_commands.describe(member="User to add to the ticket")
@is_trusted()
async def ticketadd(interaction: discord.Interaction, member: discord.Member):
    channel = interaction.channel
    if not channel.name.startswith("ticket-"):
        await interaction.response.send_message("Use this inside a ticket channel.", ephemeral=True)
        return
    guild = interaction.guild
    cfg = TICKET_CONFIG
    opener_id = None
    try:
        opener_id = int(channel.topic) if channel.topic else None
    except (ValueError, TypeError):
        opener_id = None
    support_role = guild.get_role(cfg.get("support_role_id")) if cfg else None
    is_support = support_role is not None and support_role in interaction.user.roles
    if not (
        interaction.user.id == OWNER_ID
        or interaction.user.guild_permissions.administrator
        or interaction.user.id == opener_id
        or is_support
    ):
        await interaction.response.send_message("Only the ticket owner or support can add people.", ephemeral=True)
        return
    await channel.set_permissions(member, **TICKET_MEMBER_PERMS, reason="Ticket add")
    await channel.send(f"{member.mention} was added to the ticket by {interaction.user.mention}.")
    await interaction.response.send_message(f"Added {member.mention} to the ticket.", ephemeral=True)


@bot.tree.command(name="ticketsetup", description="Set up the ticket system (categories, support role, panel location)")
@app_commands.describe(
    open_category="Category where opened tickets appear",
    closed_category="Category where closed tickets are moved to",
    support_role="Role that handles tickets",
    panel_channel="Channel where the Open Ticket button is posted",
)
@is_trusted()
async def ticketsetup(interaction: discord.Interaction, open_category: discord.CategoryChannel, closed_category: discord.CategoryChannel, support_role: discord.Role, panel_channel: discord.TextChannel):
    global TICKET_CONFIG
    old_panel = TICKET_CONFIG.get("panel_message_id")
    if old_panel:
        try:
            old_channel = interaction.guild.get_channel(TICKET_CONFIG.get("panel_channel_id"))
            if old_channel is not None:
                msg = await old_channel.fetch_message(old_panel)
                await msg.delete()
        except discord.HTTPException:
            pass
    TICKET_CONFIG = {
        "guild_id": interaction.guild.id,
        "open_category_id": open_category.id,
        "closed_category_id": closed_category.id,
        "support_role_id": support_role.id,
        "panel_channel_id": panel_channel.id,
        "panel_message_id": None,
    }
    msg = await panel_channel.send("\U0001f3ab **Need help?** Click the button below to open a ticket.", view=TicketView())
    TICKET_CONFIG["panel_message_id"] = msg.id
    await audit(interaction.guild, f"\U0001f3ab Ticket system set up by {interaction.user}")
    await interaction.response.send_message(
        f"Ticket system set up. Panel posted in {panel_channel.mention}.\n"
        f"Opened tickets: **{open_category.name}** | Closed tickets: **{closed_category.name}** | Support: **{support_role.name}**",
        ephemeral=True,
    )


@bot.tree.command(name="ticketpanel", description="Repost the Open Ticket button panel (uses existing setup)")
@is_trusted()
async def ticketpanel(interaction: discord.Interaction):
    cfg = TICKET_CONFIG
    if not cfg or cfg.get("guild_id") != interaction.guild.id:
        await interaction.response.send_message("Tickets aren't set up yet. Run /ticketsetup first.", ephemeral=True)
        return
    channel = interaction.guild.get_channel(cfg.get("panel_channel_id"))
    if not isinstance(channel, discord.TextChannel):
        await interaction.response.send_message("The panel channel is missing. Run /ticketsetup again.", ephemeral=True)
        return
    old_panel = cfg.get("panel_message_id")
    if old_panel:
        try:
            msg = await channel.fetch_message(old_panel)
            await msg.delete()
        except discord.HTTPException:
            pass
    msg = await channel.send("\U0001f3ab **Need help?** Click the button below to open a ticket.", view=TicketView())
    cfg["panel_message_id"] = msg.id
    await interaction.response.send_message(f"Panel reposted in {channel.mention}.", ephemeral=True)


@bot.tree.command(name="ai", description="Ask the AI assistant")
@app_commands.describe(message="Your question or prompt")
async def ai(interaction: discord.Interaction, message: str):
    if not AI_ENABLED:
        await interaction.response.send_message("AI isn't enabled. Ask an admin to set the AI_API_KEY variable.", ephemeral=True)
        return
    await interaction.response.defer()
    text, err = await ai_generate(message, interaction.channel_id)
    if err:
        await interaction.followup.send(f":warning: AI error: {fit(err, 300)}")
    else:
        await interaction.followup.send(fit(text))


@bot.tree.command(name="aimodels", description="Show the AI model rotation list")
async def aimodels(interaction: discord.Interaction):
    lines = "\n".join(f"{'->' if i == AI_MODEL_INDEX else '  '} `{m}`" for i, m in enumerate(AI_MODELS))
    await interaction.response.send_message(f"**AI model rotation:**\n{lines}", ephemeral=True)


@bot.tree.command(name="aichat", description="Make the AI reply to every message in a channel (run with no channel = off)")
@app_commands.describe(channel="Channel for AI chat")
@is_trusted()
async def aichat(interaction: discord.Interaction, channel: discord.TextChannel = None):
    global AI_CHANNEL_ID
    if channel is None:
        AI_CHANNEL_ID = None
        await interaction.response.send_message("AI chat mode **OFF**.", ephemeral=True)
        return
    if not AI_ENABLED:
        await interaction.response.send_message("AI isn't enabled. Set the AI_API_KEY variable first.", ephemeral=True)
        return
    AI_CHANNEL_ID = channel.id
    await interaction.response.send_message(f"AI chat enabled in {channel.mention} - it will reply to every message there.", ephemeral=True)


@bot.tree.command(name="auditlog", description="Set which channel receives the bot's audit log")
@app_commands.describe(channel="Channel for logs")
@is_trusted()
async def auditlog(interaction: discord.Interaction, channel: discord.TextChannel):
    global audit_channel_id
    audit_channel_id = channel.id
    await interaction.response.send_message(f"Audit log set to {channel.mention}.", ephemeral=True)


@bot.tree.command(name="backup", description="Save the server's channels and roles to a backup file")
@is_trusted()
async def backup(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    data = serialize_guild(interaction.guild)
    with open(BACKUP_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    await audit(interaction.guild, f":floppy_disk: Backup saved by {interaction.user} ({len(data['roles'])} roles, {len(data['channels'])} channels)")
    await interaction.followup.send(f"Backup saved: {len(data['roles'])} roles, {len(data['channels'])} channels -> `{BACKUP_FILE}`")


@bot.tree.command(name="restore", description="Recreate missing channels and roles from the last backup")
@is_trusted()
async def restore(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    if not os.path.exists(BACKUP_FILE):
        await interaction.followup.send("No backup file found. Run `/backup` first.", ephemeral=True)
        return
    try:
        with open(BACKUP_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        await interaction.followup.send(f"Could not read backup: {e}", ephemeral=True)
        return
    roles, channels = await restore_guild(interaction.guild, data)
    await audit(interaction.guild, f":arrows_counterclockwise: Restore run by {interaction.user}")
    await interaction.followup.send(f"Restore done. Missing items recreated: {roles} roles, {channels} channel entries. Existing channels were left alone.")


@bot.tree.command(name="cleanupdays", description="Set how many days a private room can be inactive before auto-delete (0 = off)")
@app_commands.describe(days="Days (0 disables auto-cleanup)")
@is_trusted()
async def cleanupdays(interaction: discord.Interaction, days: int):
    global ROOM_INACTIVE_DAYS
    ROOM_INACTIVE_DAYS = max(0, min(days, 365))
    await interaction.response.send_message(
        f"Room auto-cleanup: rooms inactive for **{ROOM_INACTIVE_DAYS}** days get deleted (checked every 12h)." if ROOM_INACTIVE_DAYS else "Room auto-cleanup **OFF**.",
        ephemeral=True,
    )


@bot.tree.command(name="cleanuprooms", description="Run the inactive-room cleanup right now")
@is_trusted()
async def cleanuprooms(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    before = {ch.id for ch in interaction.guild.text_channels if ch.name.startswith(ROOM_PREFIX) or ch.name.startswith(MARKET_PREFIX)}
    await cleanup_rooms()
    after = {ch.id for ch in interaction.guild.text_channels if ch.name.startswith(ROOM_PREFIX) or ch.name.startswith(MARKET_PREFIX)}
    removed = len(before - after)
    await interaction.followup.send(f"Cleanup done. Deleted **{removed}** inactive room(s).")


@bot.tree.command(name="raidstatus", description="Show all protection settings")
@is_trusted()
async def raidstatus(interaction: discord.Interaction):
    await interaction.response.send_message(
        f"Raid mode: {'**ACTIVE** - server locked' if raiding else 'off'}\n"
        f"Channel raid protection: {'**ON**' if channel_raid_protection else '**OFF**'}\n"
        f"Spam detection: {'**ON**' if spam_detection else '**OFF**'}\n"
        f"Invite filter: {'**ON**' if invite_filter else '**OFF**'}\n"
        f"Anti-bot: {'**ON**' if antibot else '**OFF**'}\n"
        f"Bad word filter: {'**ON**' if badwords_filter else '**OFF**'}\n"
        f"Anti-link: {'**ON**' if antilink else '**OFF**'}\n"
        f"Welcome role: {'**set**' if WELCOME_ROLE_ID else 'off'}\n"
        f"Whitelisted: {len(WHITELIST_USER_IDS)} users, {len(WHITELIST_ROLE_IDS)} roles\n"
        f"Auto-responses: {len(AUTO_RESPONSES)}\n"
        f"Room auto-cleanup: {'**ON** (' + str(ROOM_INACTIVE_DAYS) + ' days)' if ROOM_INACTIVE_DAYS else '**OFF**'}\n"
        f"Join trigger: {RAID_JOIN_COUNT}+ joins in {RAID_JOIN_WINDOW}s | Channel trigger: {CHANNEL_CREATE_COUNT}+ channels in {CHANNEL_CREATE_WINDOW}s",
        ephemeral=True,
    )


@bot.tree.error
async def on_app_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CheckFailure):
        await interaction.response.send_message("You don't have permission to use this.", ephemeral=True)
    else:
        print(error)


if __name__ == "__main__":
    bot.run(TOKEN)
