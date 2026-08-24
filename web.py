import os
import uuid
import json
import datetime
import aiohttp
from aiohttp import web
import bot as bot_module

def web_log(user_id, username, guild_id, action):
    try:
        with open("dashboard_logs.json", "r") as f: logs = json.load(f)
    except: logs = []
    logs.insert(0, {"time": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"), "user_id": user_id, "username": username, "guild_id": guild_id, "action": action})
    logs = logs[:1000]
    with open("dashboard_logs.json", "w") as f: json.dump(logs, f)

SESSIONS = {}

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")

async def login(request):
    if not CLIENT_ID:
        session_id = str(uuid.uuid4())
        SESSIONS[session_id] = {"user_id": bot_module.OWNER_ID, "username": "LocalAdmin"}
        resp = web.HTTPFound('/')
        resp.set_cookie('dash_session', session_id)
        return resp
        
    host = request.headers.get('Host', '')
    proto = request.headers.get('X-Forwarded-Proto', 'http')
    redirect_uri = f"{proto}://{host}/callback"
    oauth_url = f"https://discord.com/api/oauth2/authorize?client_id={CLIENT_ID}&redirect_uri={redirect_uri}&response_type=code&scope=identify"
    return web.HTTPFound(oauth_url)

async def callback(request):
    code = request.query.get('code')
    if not code: return web.Response(text="Missing code", status=400)
    
    host = request.headers.get('Host', '')
    proto = request.headers.get('X-Forwarded-Proto', 'http')
    redirect_uri = f"{proto}://{host}/callback"
    
    async with aiohttp.ClientSession() as session:
        data = {
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': redirect_uri
        }
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        async with session.post('https://discord.com/api/oauth2/token', data=data, headers=headers) as resp:
            if resp.status != 200: return web.Response(text=f"OAuth error: {await resp.text()}", status=400)
            token_data = await resp.json()
            
        access_token = token_data['access_token']
        headers = {'Authorization': f'Bearer {access_token}'}
        async with session.get('https://discord.com/api/users/@me', headers=headers) as resp:
            user_data = await resp.json()
            
    user_id = int(user_data['id'])
    is_trusted = (user_id == bot_module.OWNER_ID)
    if not is_trusted:
        for gid, s in bot_module.SETTINGS.items():
            if user_id in s.whitelisted_users:
                is_trusted = True
                break
                
    if not is_trusted:
        return web.Response(text="Access Denied. You are not the owner or a whitelisted admin.", status=403)
        
    session_id = str(uuid.uuid4())
    SESSIONS[session_id] = {"user_id": user_id, "username": user_data['username']}
    resp = web.HTTPFound('/')
    resp.set_cookie('dash_session', session_id)
    return resp

def get_session(request):
    session_id = request.cookies.get('dash_session')
    return SESSIONS.get(session_id)

async def index(request):
    return web.FileResponse('website/index.html')

async def api_status(request):
    user = get_session(request)
    if not user: return web.json_response({"error": "Unauthorized"}, status=401)
    
    bot = request.app['bot']
    
    shared_guilds = []
    for g in bot.guilds:
        if user["user_id"] == bot_module.OWNER_ID or user["user_id"] in bot_module.settings_for(g.id).whitelisted_users:
            shared_guilds.append({"id": str(g.id), "name": g.name})
            
    if not shared_guilds:
        return web.json_response({"error": "Bot is not in any shared servers where you are an admin."})
        
    req_guild_id = request.query.get("guild_id")
    guild = None
    if req_guild_id:
        guild = bot.get_guild(int(req_guild_id))
    if not guild:
        guild = bot.get_guild(int(shared_guilds[0]["id"]))
    
    s = bot_module.settings_for(guild.id)
    data = {
        "user": {"username": user["username"], "is_owner": user["user_id"] == bot_module.OWNER_ID},
        "guild": {"id": str(guild.id), "name": guild.name, "member_count": guild.member_count},
        "shared_guilds": shared_guilds,
        "settings": {
            "raiding": s.raiding,
            "spam_detection": s.spam_detection,
            "antilink": s.antilink,
            "badwords_filter": s.badwords_filter,
            "antibot": s.antibot,
            "channel_raid_protection": s.channel_raid_protection,
            "spam_count": s.spam_count,
            "spam_window": s.spam_window,
            "spam_mute_minutes": s.spam_mute_minutes,
            "spam_ban_offenses": s.spam_ban_offenses,
            "raid_slowmode": s.raid_slowmode,
            "room_inactive_days": s.room_inactive_days,
            "raid_auto_unlock": s.raid_auto_unlock,
            "raid_ban_new_accounts": s.raid_ban_new_accounts,
        },
        "stats": dict(bot_module.MESSAGE_STATS),
    }
    return web.json_response(data)

async def api_action(request):
    user = get_session(request)
    if not user: return web.json_response({"error": "Unauthorized"}, status=401)
        
    try:
        data = await request.json()
    except:
        return web.json_response({"error": "Invalid JSON"}, status=400)
        
    action = data.get("action")
    bot = request.app['bot']
    
    req_guild_id = data.get("guild_id")`r`n    guild = None`r`n    if req_guild_id:`r`n        guild = bot.get_guild(int(req_guild_id))`r`n    else:`r`n        guild = bot.guilds[0] if bot.guilds else None`r`n`r`n    if not guild: return web.json_response({"error": "No guild selected"})`r`n    `r`n    if user["user_id"] != bot_module.OWNER_ID and user["user_id"] not in bot_module.settings_for(guild.id).whitelisted_users:`r`n        return web.json_response({"error": "Access Denied for this server"}, status=403)
    s = bot_module.settings_for(guild.id)
    
    if action == "toggle_setting":
        key = data.get("key")
        val = data.get("value")
        if hasattr(s, key):
            setattr(s, key, val)
            bot_module.save_config(guild.id)
            return web.json_response({"success": True})
            
    elif action == "update_thresholds":
        s.spam_count = int(data.get("spam_count", s.spam_count))
        s.spam_window = int(data.get("spam_window", s.spam_window))
        s.spam_mute_minutes = int(data.get("spam_mute_minutes", s.spam_mute_minutes))
        s.spam_ban_offenses = int(data.get("spam_ban_offenses", s.spam_ban_offenses))
        s.raid_slowmode = int(data.get("raid_slowmode", s.raid_slowmode))
        s.room_inactive_days = int(data.get("room_inactive_days", s.room_inactive_days))
        bot_module.save_config(guild.id)
        return web.json_response({"success": True})
        
    elif action == "ai_chat":
        prompt = data.get("message")
        chat_type = data.get("type", "aichat")
        
        if not bot_module.AI_API_KEY:
            return web.json_response({"reply": "Error: AI_API_KEY is not set in the bot's environment!"})
            
        sys_prompt = "You are a helpful discord bot assistant. Please provide concise answers."
        tools = None
        if chat_type == "aiadmin":
            sys_prompt = bot_module.ADMIN_SYSTEM
            tools = bot_module.ADMIN_TOOLS
        elif chat_type == "aijuiced":
            sys_prompt = bot_module.JUICED_SYSTEM
            tools = bot_module.ADMIN_TOOLS
            
        web_log(user["user_id"], user["username"], str(guild.id), f"Used {chat_type} AI: {prompt[:100]}")`n        messages = [{"role": "system", "content": sys_prompt}]
        messages.append({"role": "user", "content": prompt})
        
        try:
            while True:
                resp_data = await bot_module.ai_call(messages, tools=tools)
                if isinstance(resp_data, str):
                    return web.json_response({"reply": resp_data})
                
                if resp_data.get("tool_calls"):
                    messages.append({"role": "assistant", "content": resp_data.get("content") or "", "tool_calls": resp_data["tool_calls"]})
                    for tc in resp_data["tool_calls"]:
                        fname = tc["function"]["name"]
                        try:
                            targs = json.loads(tc["function"]["arguments"] or "{}")
                        except json.JSONDecodeError:
                            targs = {}
                        try:
                            res = await bot_module.run_admin_tool(guild, fname, targs)
                            if not isinstance(res, str): res = json.dumps(res)
                        except Exception as e:
                            res = f"Error: {e}"
                        messages.append({"role": "tool", "tool_call_id": tc["id"], "content": res})
                else:
                    reply_str = resp_data.get("content") if isinstance(resp_data, dict) else str(resp_data)
                    return web.json_response({"reply": reply_str})
        except Exception as e:
            return web.json_response({"reply": f"AI backend error: {e}"})
            
    return web.json_response({"error": "Unknown action"}, status=400)

async def api_logs(request):
    user = get_session(request)
    if not user or user["user_id"] != bot_module.OWNER_ID: return web.json_response({"error": "Unauthorized"}, status=403)
    try:
        with open("dashboard_logs.json", "r") as f: logs = json.load(f)
    except: logs = []
    return web.json_response({"logs": logs})

async def start_server(bot):
    app = web.Application()
    app['bot'] = bot
    app.router.add_get('/', index)
    app.router.add_get('/login', login)
    app.router.add_get('/callback', callback)
    app.router.add_get('/api/status', api_status)
    app.router.add_post('/api/action', api_action)
    app.router.add_get('/api/logs', api_logs)
    app.router.add_static('/', 'website')
    
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 5000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"Web dashboard started on port {port}")






