import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer, TestClient

from bot.main import build_app

@pytest.mark.asyncio
async def test_slots_basic():
    app = await build_app()
    server = TestServer(app)
    await server.start_server()
    try:
        client = TestClient(server)
        await client.start_server()
        resp = await client.get('/api/slots')
        assert resp.status == 400
        data = await resp.json()
        assert 'error' in data
    finally:
        await server.close()

@pytest.mark.asyncio
async def test_health():
    app = await build_app()
    server = TestServer(app)
    await server.start_server()
    try:
        client = TestClient(server)
        await client.start_server()
        resp = await client.get('/health')
        assert resp.status == 200
        body = await resp.json()
        assert body.get('status') == 'ok'
    finally:
        await server.close()
