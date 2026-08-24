import os
import uuid
import aiohttp
from aiohttp import web
import bot as bot_module

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
    guild = bot.guilds[0] if bot.guilds else None
    if not guild: return web.json_response({"error": "Bot is not in any servers"})
    
    s = bot_module.settings_for(guild.id)
    data = {
        "user": user,
        "guild": {"name": guild.name, "member_count": guild.member_count},
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
        }
    }
    return web.json_response(data)

async def start_server(bot):
    app = web.Application()
    app['bot'] = bot
    app.router.add_get('/', index)
    app.router.add_get('/login', login)
    app.router.add_get('/callback', callback)
    app.router.add_get('/api/status', api_status)
    app.router.add_static('/', 'website')
    
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 5000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"Web dashboard started on port {port}")
