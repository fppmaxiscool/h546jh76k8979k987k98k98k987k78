import os
import uuid
import json
import datetime
import aiohttp
from aiohttp import web
import discord
import bot as bot_module

SESSIONS = {}
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")

def web_log(user_id, username, guild_id, action):
    try:
        with open("dashboard_logs.json", "r") as f: logs = json.load(f)
    except Exception: logs = []
    logs.insert(0, {"time": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"), "user_id": user_id, "username": username, "guild_id": guild_id, "action": action})
    logs = logs[:1000]
    with open("dashboard_logs.json", "w") as f: json.dump(logs, f)

def get_session(request):
    return SESSIONS.get(request.cookies.get("dash_session"))

def resolve_guild(source, bot, user):
    guild_id = source.get("guild_id") if isinstance(source, dict) else source.query.get("guild_id")
    guild = bot.get_guild(int(guild_id)) if guild_id else (bot.guilds[0] if bot.guilds else None)
    if not guild: return None, web.json_response({"error": "No guild found"}, status=404)
    if user["user_id"] != bot_module.OWNER_ID:
        if user["user_id"] not in bot_module.settings_for(guild.id).whitelisted_users:
            return None, web.json_response({"error": "Access Denied"}, status=403)
    return guild, None

async def login(request):
    if not CLIENT_ID:
        sid = str(uuid.uuid4())
        SESSIONS[sid] = {"user_id": bot_module.OWNER_ID, "username": "LocalAdmin"}
        resp = web.HTTPFound("/"); resp.set_cookie("dash_session", sid, max_age=86400, path="/"); return resp
    host = request.headers.get("Host", "")
    proto = request.headers.get("X-Forwarded-Proto", "http")
    redirect_uri = f"{proto}://{host}/callback"
    return web.HTTPFound(f"https://discord.com/api/oauth2/authorize?client_id={CLIENT_ID}&redirect_uri={redirect_uri}&response_type=code&scope=identify")

async def callback(request):
    code = request.query.get("code")
    if not code: return web.Response(text="Missing code", status=400)
    host = request.headers.get("Host", ""); proto = request.headers.get("X-Forwarded-Proto", "http")
    redirect_uri = f"{proto}://{host}/callback"
    async with aiohttp.ClientSession() as session:
        async with session.post("https://discord.com/api/oauth2/token", data={"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET, "grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri}, headers={"Content-Type": "application/x-www-form-urlencoded"}) as r:
            if r.status != 200: return web.Response(text=f"OAuth error: {await r.text()}", status=400)
            tok = await r.json()
        async with session.get("https://discord.com/api/users/@me", headers={"Authorization": "Bearer " + tok["access_token"]}) as r:
            u = await r.json()
    uid = int(u["id"])
    trusted = uid == bot_module.OWNER_ID or any(uid in s.whitelisted_users for s in bot_module.SETTINGS.values())
    if not trusted: return web.Response(text="Access Denied.", status=403)
    sid = str(uuid.uuid4()); SESSIONS[sid] = {"user_id": uid, "username": u["username"]}
    resp = web.HTTPFound("/"); resp.set_cookie("dash_session", sid, max_age=86400, path="/"); return resp

async def index(request): return web.FileResponse("website/index.html")

async def api_status(request):
    user = get_session(request)
    if not user: return web.json_response({"error": "Unauthorized"}, status=401)
    bot = request.app["bot"]
    shared = [{"id": str(g.id), "name": g.name} for g in bot.guilds if user["user_id"] == bot_module.OWNER_ID or user["user_id"] in bot_module.settings_for(g.id).whitelisted_users]
    if not shared: return web.json_response({"error": "No shared servers."})
    guild, err = resolve_guild(request, bot, user)
    if err: guild = bot.get_guild(int(shared[0]["id"]))
    s = bot_module.settings_for(guild.id)
    audit_entries = []
    try:
        async for e in guild.audit_logs(limit=10):
            audit_entries.append({"time": e.created_at.strftime("%H:%M"), "actor": e.user.name if e.user else "?", "action": str(e.action).replace("AuditLogAction.", ""), "target": getattr(e.target, "name", str(getattr(e.target, "id", "?")))})
    except Exception: pass
    return web.json_response({"user": {"username": user["username"], "is_owner": user["user_id"] == bot_module.OWNER_ID}, "guild": {"id": str(guild.id), "name": guild.name, "member_count": guild.member_count}, "shared_guilds": shared, "audit_log": audit_entries, "settings": {"raiding": s.raiding, "spam_detection": s.spam_detection, "antilink": s.antilink, "badwords_filter": s.badwords_filter, "antibot": s.antibot, "channel_raid_protection": s.channel_raid_protection, "spam_count": s.spam_count, "spam_window": s.spam_window, "spam_mute_minutes": s.spam_mute_minutes, "spam_ban_offenses": s.spam_ban_offenses, "raid_slowmode": s.raid_slowmode, "room_inactive_days": s.room_inactive_days, "raid_auto_unlock": s.raid_auto_unlock, "raid_ban_new_accounts": s.raid_ban_new_accounts}, "stats": dict(bot_module.MESSAGE_STATS)})

async def api_timed_out(request):
    user = get_session(request)
    if not user: return web.json_response({"error": "Unauthorized"}, status=401)
    guild, err = resolve_guild(request, request.app["bot"], user)
    if err: return err
    return web.json_response({"members": [{"id": str(m.id), "name": m.display_name, "until": m.timed_out_until.strftime("%Y-%m-%d %H:%M UTC")} for m in guild.members if m.timed_out_until]})

async def api_whitelist_get(request):
    user = get_session(request)
    if not user: return web.json_response({"error": "Unauthorized"}, status=401)
    guild, err = resolve_guild(request, request.app["bot"], user)
    if err: return err
    s = bot_module.settings_for(guild.id)
    users = [{"id": str(uid), "name": (guild.get_member(uid).display_name if guild.get_member(uid) else str(uid))} for uid in s.whitelisted_users]
    roles = [{"id": str(rid), "name": (guild.get_role(rid).name if guild.get_role(rid) else str(rid))} for rid in s.whitelisted_roles]
    links = [{"domain": d} for d in sorted(s.link_whitelist)]
    return web.json_response({"users": users, "roles": roles, "links": links})

async def api_whitelist_post(request):
    user = get_session(request)
    if not user: return web.json_response({"error": "Unauthorized"}, status=401)
    try: data = await request.json()
    except Exception: return web.json_response({"error": "Invalid JSON"}, status=400)
    guild, err = resolve_guild(data, request.app["bot"], user)
    if err: return err
    s = bot_module.settings_for(guild.id)
    action = data.get("action"); value = str(data.get("value", "")).strip()
    try:
        if action == "add_user":
            uid = int(value); s.whitelisted_users.add(uid); bot_module.save_config(guild.id)
            web_log(user["user_id"], user["username"], str(guild.id), f"WL added user {uid}")
            m = guild.get_member(uid); return web.json_response({"id": str(uid), "name": m.display_name if m else str(uid)})
        elif action == "remove_user":
            s.whitelisted_users.discard(int(value)); bot_module.save_config(guild.id)
            web_log(user["user_id"], user["username"], str(guild.id), f"WL removed user {value}")
            return web.json_response({"success": True})
        elif action == "add_role":
            rid = int(value); s.whitelisted_roles.add(rid); bot_module.save_config(guild.id)
            web_log(user["user_id"], user["username"], str(guild.id), f"WL added role {rid}")
            r = guild.get_role(rid); return web.json_response({"id": str(rid), "name": r.name if r else str(rid)})
        elif action == "remove_role":
            s.whitelisted_roles.discard(int(value)); bot_module.save_config(guild.id)
            web_log(user["user_id"], user["username"], str(guild.id), f"WL removed role {value}")
            return web.json_response({"success": True})
        elif action == "add_link":
            domain = value.lower().replace("https://","").replace("http://","").split("/")[0]
            s.link_whitelist.add(domain); bot_module.save_config(guild.id)
            web_log(user["user_id"], user["username"], str(guild.id), f"WL added link {domain}")
            return web.json_response({"domain": domain})
        elif action == "remove_link":
            s.link_whitelist.discard(value); bot_module.save_config(guild.id)
            web_log(user["user_id"], user["username"], str(guild.id), f"WL removed link {value}")
            return web.json_response({"success": True})
    except Exception as e: return web.json_response({"error": str(e)}, status=400)
    return web.json_response({"error": "Unknown action"}, status=400)

async def api_ar_get(request):
    user = get_session(request)
    if not user: return web.json_response({"error": "Unauthorized"}, status=401)
    guild, err = resolve_guild(request, request.app["bot"], user)
    if err: return err
    s = bot_module.settings_for(guild.id)
    return web.json_response({"items": [{"trigger": k, "response": v} for k, v in s.auto_responses.items()]})

async def api_ar_post(request):
    user = get_session(request)
    if not user: return web.json_response({"error": "Unauthorized"}, status=401)
    try: data = await request.json()
    except Exception: return web.json_response({"error": "Invalid JSON"}, status=400)
    guild, err = resolve_guild(data, request.app["bot"], user)
    if err: return err
    s = bot_module.settings_for(guild.id)
    action = data.get("action")
    if action == "add":
        t = str(data.get("trigger","")).strip().lower(); r = str(data.get("response","")).strip()
        if not t or not r: return web.json_response({"error": "trigger and response required"}, status=400)
        s.auto_responses[t] = r; bot_module.save_config(guild.id)
        web_log(user["user_id"], user["username"], str(guild.id), f"AR added: {t}")
        return web.json_response({"trigger": t, "response": r})
    elif action == "remove":
        t = str(data.get("trigger","")).strip().lower()
        s.auto_responses.pop(t, None); bot_module.save_config(guild.id)
        web_log(user["user_id"], user["username"], str(guild.id), f"AR removed: {t}")
        return web.json_response({"success": True})
    return web.json_response({"error": "Unknown action"}, status=400)

async def api_tickets(request):
    user = get_session(request)
    if not user: return web.json_response({"error": "Unauthorized"}, status=401)
    guild, err = resolve_guild(request, request.app["bot"], user)
    if err: return err
    cfg = bot_module.TICKET_CONFIG.get(guild.id, {})
    open_cat_id = cfg.get("open_category_id")
    tickets = []
    if open_cat_id:
        cat = guild.get_channel(open_cat_id)
        if cat and isinstance(cat, discord.CategoryChannel):
            for ch in cat.text_channels:
                if ch.name.startswith("ticket-"):
                    try: m = guild.get_member(int(ch.topic)); opener = m.display_name if m else ch.topic
                    except Exception: opener = ch.topic or "?"
                    tickets.append({"channel_id": str(ch.id), "name": ch.name, "opener": opener, "url": f"https://discord.com/channels/{guild.id}/{ch.id}"})
    return web.json_response({"tickets": tickets})

async def api_moderation(request):
    user = get_session(request)
    if not user: return web.json_response({"error": "Unauthorized"}, status=401)
    try: data = await request.json()
    except Exception: return web.json_response({"error": "Invalid JSON"}, status=400)
    guild, err = resolve_guild(data, request.app["bot"], user)
    if err: return err
    action = data.get("action"); target_str = str(data.get("target","")).strip(); reason = (str(data.get("reason","Dashboard action")).strip() or "Dashboard action")[:300]
    if not target_str: return web.json_response({"error": "Target required"}, status=400)
    web_log(user["user_id"], user["username"], str(guild.id), f"Dashboard mod: {action} on {target_str}")
    try:
        if action == "unban":
            await guild.unban(discord.Object(id=int(target_str)), reason=f"[Dashboard] {reason}")
            await bot_module.audit(guild, f"🔓 Dashboard unbanned {target_str} — {reason}")
            return web.json_response({"success": True, "message": f"Unbanned {target_str}"})
        member = bot_module.admin_resolve_member(guild, target_str, target_str)
        if member == "AMBIGUOUS": return web.json_response({"error": "Multiple matches — use exact User ID"}, status=400)
        if member is None: return web.json_response({"error": "Member not found"}, status=404)
        if bot_module.admin_protected(member): return web.json_response({"error": f"{member.display_name} is protected"}, status=403)
        if action == "ban":
            await member.ban(reason=f"[Dashboard] {reason}", delete_message_days=0)
            await bot_module.audit(guild, f"🔨 Dashboard banned **{member}** — {reason}")
            return web.json_response({"success": True, "message": f"Banned {member.display_name}"})
        elif action == "kick":
            await member.kick(reason=f"[Dashboard] {reason}")
            await bot_module.audit(guild, f"👢 Dashboard kicked **{member}** — {reason}")
            return web.json_response({"success": True, "message": f"Kicked {member.display_name}"})
        elif action == "timeout":
            mins = max(1, min(int(data.get("minutes", 10)), 10080))
            await member.timeout(discord.utils.utcnow() + datetime.timedelta(minutes=mins), reason=f"[Dashboard] {reason}")
            await bot_module.audit(guild, f"🔇 Dashboard timed out **{member}** for {mins}min — {reason}")
            return web.json_response({"success": True, "message": f"Timed out {member.display_name} for {mins} min"})
        elif action == "purge":
            count = max(1, min(int(data.get("count",10)), 100))
            ch = guild.text_channels[0] if guild.text_channels else None
            if not ch: return web.json_response({"error": "No text channel found"}, status=404)
            deleted = await ch.purge(limit=count, check=lambda m: m.author == member)
            await bot_module.audit(guild, f"🗑️ Dashboard purged {len(deleted)} msgs from {member} in #{ch.name}")
            return web.json_response({"success": True, "message": f"Purged {len(deleted)} messages"})
    except discord.Forbidden: return web.json_response({"error": "Bot lacks permission"}, status=403)
    except Exception as e: return web.json_response({"error": str(e)}, status=500)
    return web.json_response({"error": "Unknown action"}, status=400)

async def api_action(request):
    user = get_session(request)
    if not user: return web.json_response({"error": "Unauthorized"}, status=401)
    try: data = await request.json()
    except Exception: return web.json_response({"error": "Invalid JSON"}, status=400)
    guild, err = resolve_guild(data, request.app["bot"], user)
    if err: return err
    s = bot_module.settings_for(guild.id)
    action = data.get("action")
    if action == "toggle_setting":
        key = data.get("key"); val = data.get("value")
        if hasattr(s, key):
            setattr(s, key, val); bot_module.save_config(guild.id)
            web_log(user["user_id"], user["username"], str(guild.id), f"Toggled {key}={val}")
            return web.json_response({"success": True})
        return web.json_response({"error": "Unknown setting"}, status=400)
    elif action == "update_thresholds":
        s.spam_count = int(data.get("spam_count", s.spam_count)); s.spam_window = int(data.get("spam_window", s.spam_window))
        s.spam_mute_minutes = int(data.get("spam_mute_minutes", s.spam_mute_minutes)); s.spam_ban_offenses = int(data.get("spam_ban_offenses", s.spam_ban_offenses))
        s.raid_slowmode = int(data.get("raid_slowmode", s.raid_slowmode)); s.room_inactive_days = int(data.get("room_inactive_days", s.room_inactive_days))
        bot_module.save_config(guild.id); web_log(user["user_id"], user["username"], str(guild.id), "Updated thresholds")
        return web.json_response({"success": True})
    elif action == "ai_chat":
        prompt = data.get("message", ""); chat_type = data.get("type", "aichat")
        if not bot_module.AI_API_KEY: return web.json_response({"reply": "Error: AI_API_KEY not set!"})
        sys_prompt = bot_module.ADMIN_SYSTEM if chat_type == "aiadmin" else (bot_module.JUICED_SYSTEM if chat_type == "aijuiced" else "You are a helpful Discord bot assistant.")
        tools = bot_module.ADMIN_TOOLS if chat_type in ("aiadmin", "aijuiced") else None
        messages = [{"role": "system", "content": sys_prompt}, {"role": "user", "content": prompt}]
        web_log(user["user_id"], user["username"], str(guild.id), f"{chat_type} AI: {prompt[:80]}")
        try:
            while True:
                rd = await bot_module.ai_call(messages, tools=tools)
                if isinstance(rd, str): return web.json_response({"reply": rd})
                if rd.get("tool_calls"):
                    messages.append({"role": "assistant", "content": rd.get("content") or "", "tool_calls": rd["tool_calls"]})
                    for tc in rd["tool_calls"]:
                        fname = tc["function"]["name"]
                        try: targs = json.loads(tc["function"]["arguments"] or "{}")
                        except Exception: targs = {}
                        try: res = await bot_module.run_admin_tool(guild, fname, targs); res = res if isinstance(res, str) else json.dumps(res)
                        except Exception as e: res = f"Error: {e}"
                        messages.append({"role": "tool", "tool_call_id": tc["id"], "content": res})
                else:
                    return web.json_response({"reply": rd.get("content") if isinstance(rd, dict) else str(rd)})
        except Exception as e: return web.json_response({"reply": f"AI error: {e}"})
    return web.json_response({"error": "Unknown action"}, status=400)

async def api_debug(request):
    user = get_session(request)
    if not user or user["user_id"] != bot_module.OWNER_ID:
        return web.json_response({"error": "Unauthorized"}, status=403)
    bot = request.app["bot"]
    guilds = [{"id": str(g.id), "name": g.name} for g in bot.guilds]
    guild = bot.guilds[0] if bot.guilds else None
    settings = {}
    if guild:
        s = bot_module.settings_for(guild.id)
        settings = {k: getattr(s, k) for k in ["spam_detection","antilink","badwords_filter","antibot","channel_raid_protection","raid_auto_unlock","raid_ban_new_accounts","spam_count","spam_window","spam_mute_minutes","spam_ban_offenses","raid_slowmode","room_inactive_days"] if hasattr(s, k)}
    return web.json_response({"user": user, "guilds": guilds, "settings": settings})
async def api_logs(request):
    user = get_session(request)
    if not user or user["user_id"] != bot_module.OWNER_ID: return web.json_response({"error": "Unauthorized"}, status=403)
    try:
        with open("dashboard_logs.json") as f: logs = json.load(f)
    except Exception: logs = []
    return web.json_response({"logs": logs})

async def start_server(bot):
    app = web.Application()
    app["bot"] = bot
    app.router.add_get("/", index)
    app.router.add_get("/login", login)
    app.router.add_get("/callback", callback)
    app.router.add_get("/api/status", api_status)
    app.router.add_get("/api/timed_out", api_timed_out)
    app.router.add_get("/api/whitelist", api_whitelist_get)
    app.router.add_post("/api/whitelist", api_whitelist_post)
    app.router.add_get("/api/autoresponse", api_ar_get)
    app.router.add_post("/api/autoresponse", api_ar_post)
    app.router.add_get("/api/tickets", api_tickets)
    app.router.add_post("/api/moderation", api_moderation)
    app.router.add_post("/api/action", api_action)
    app.router.add_get("/api/logs", api_logs)
    app.router.add_static("/", "website")
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 5000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"Web dashboard started on port {port}")




