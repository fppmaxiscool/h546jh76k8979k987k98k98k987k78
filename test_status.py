import asyncio
import json
import bot
import web
from aiohttp.test_utils import make_mocked_request
from unittest.mock import MagicMock

async def test():
    bot.SETTINGS = {123: bot.GuildSettings()}
    bot.OWNER_ID = 1
    web.SESSIONS = {"abc": {"user_id": 1, "username": "Admin"}}
    
    mock_bot = MagicMock()
    mock_guild = MagicMock()
    mock_guild.id = 123
    mock_guild.name = "Test"
    mock_guild.member_count = 10
    
    async def mock_audit(*args, **kwargs):
        return []
    mock_guild.audit_logs = mock_audit
    
    mock_bot.guilds = [mock_guild]
    mock_bot.get_guild = lambda x: mock_guild
    
    req = make_mocked_request('GET', '/api/status', headers={'Cookie': 'dash_session=abc'}, app={'bot': mock_bot})
    
    try:
        resp = await web.api_status(req)
        print("STATUS OK:", resp.text)
    except Exception as e:
        print("CRASH:", type(e), e)

asyncio.run(test())
