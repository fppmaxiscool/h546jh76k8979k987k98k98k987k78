import asyncio
import web
from unittest.mock import MagicMock
bot = MagicMock()
async def test():
    await web.start_server(bot)
asyncio.run(test())
