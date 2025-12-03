import pytest
from aiohttp.test_utils import TestServer, TestClient
from bot.main import build_app

@pytest.mark.asyncio
async def test_reschedule_requires_fields():
    app = await build_app()
    server = TestServer(app)
    await server.start_server()
    try:
        client = TestClient(server)
        await client.start_server()
        resp = await client.post('/api/master/appointment/reschedule', json={})
        assert resp.status == 400
        data = await resp.json()
        assert 'error' in data
    finally:
        await server.close()
