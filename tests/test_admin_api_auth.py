"""Tests for admin API authentication middleware."""
import pytest
from unittest.mock import Mock, patch
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop

from bot.middlewares.admin_api import (
    verify_telegram_webapp_data, 
    admin_api_auth_middleware
)
from bot.config import settings


class TestTelegramWebAppAuth(AioHTTPTestCase):
    """Test Telegram WebApp authentication."""
    
    async def get_application(self):
        """Create test application with admin middleware."""
        app = web.Application(middlewares=[admin_api_auth_middleware])
        
        # Mock admin endpoint
        async def admin_handler(request):
            return web.json_response({"status": "ok"})
        
        # Mock public endpoint
        async def public_handler(request):
            return web.json_response({"status": "public"})
        
        app.router.add_get('/api/admin/test', admin_handler)
        app.router.add_get('/api/public/test', public_handler)
        
        return app
    
    @unittest_run_loop
    async def test_verify_valid_initdata(self):
        """Test valid initData verification."""
        # This is a mock - in real scenario you'd use actual Telegram-signed data
        init_data = 'user={"id":123,"first_name":"Test"}&hash=abcdef123456'
        
        with patch('bot.middlewares.admin_api.hmac.compare_digest', return_value=True):
            user = verify_telegram_webapp_data(init_data, 'test_token')
            assert user is not None
            assert user['id'] == 123
    
    @unittest_run_loop
    async def test_verify_invalid_hash(self):
        """Test initData with invalid hash."""
        init_data = 'user={"id":123,"first_name":"Test"}&hash=invalid'
        
        with patch('bot.middlewares.admin_api.hmac.compare_digest', return_value=False):
            user = verify_telegram_webapp_data(init_data, 'test_token')
            assert user is None
    
    @unittest_run_loop
    async def test_verify_no_hash(self):
        """Test initData without hash."""
        init_data = 'user={"id":123,"first_name":"Test"}'
        user = verify_telegram_webapp_data(init_data, 'test_token')
        assert user is None
    
    @unittest_run_loop
    async def test_public_endpoint_no_auth(self):
        """Test that public endpoints don't require auth."""
        resp = await self.client.get('/api/public/test')
        assert resp.status == 200
        data = await resp.json()
        assert data['status'] == 'public'
    
    @unittest_run_loop
    async def test_admin_endpoint_no_auth(self):
        """Test that admin endpoints block access without auth."""
        resp = await self.client.get('/api/admin/test')
        assert resp.status == 401
        data = await resp.json()
        assert 'error' in data
        assert 'Authentication required' in data['error']
    
    @unittest_run_loop
    async def test_admin_endpoint_invalid_auth(self):
        """Test that admin endpoints reject invalid auth."""
        headers = {'X-Telegram-Init-Data': 'invalid_data'}
        resp = await self.client.get('/api/admin/test', headers=headers)
        assert resp.status == 401
        data = await resp.json()
        assert 'error' in data
    
    @unittest_run_loop
    async def test_admin_endpoint_non_admin_user(self):
        """Test that non-admin users are blocked."""
        init_data = 'user={"id":999,"first_name":"Hacker"}&hash=valid'
        
        with patch('bot.middlewares.admin_api.verify_telegram_webapp_data') as mock_verify:
            mock_verify.return_value = {'id': 999, 'first_name': 'Hacker'}
            
            # Temporarily save original admin IDs
            original_admins = settings.admin_telegram_ids
            settings.admin_telegram_ids = [123, 456]  # 999 is not admin
            
            try:
                headers = {'X-Telegram-Init-Data': init_data}
                resp = await self.client.get('/api/admin/test', headers=headers)
                assert resp.status == 403
                data = await resp.json()
                assert 'Admin access required' in data['error']
            finally:
                settings.admin_telegram_ids = original_admins
    
    @unittest_run_loop
    async def test_admin_endpoint_valid_admin(self):
        """Test that valid admin users can access."""
        init_data = 'user={"id":123,"first_name":"Admin"}&hash=valid'
        
        with patch('bot.middlewares.admin_api.verify_telegram_webapp_data') as mock_verify:
            mock_verify.return_value = {'id': 123, 'first_name': 'Admin'}
            
            # Temporarily save original admin IDs
            original_admins = settings.admin_telegram_ids
            settings.admin_telegram_ids = [123, 456]
            
            try:
                headers = {'X-Telegram-Init-Data': init_data}
                resp = await self.client.get('/api/admin/test', headers=headers)
                assert resp.status == 200
                data = await resp.json()
                assert data['status'] == 'ok'
            finally:
                settings.admin_telegram_ids = original_admins


def test_verify_webapp_data_structure():
    """Test the structure of verified webapp data."""
    # Test with properly formatted data
    init_data = 'auth_date=1234567890&user={"id":123,"first_name":"Test","username":"testuser"}&hash=abc123'
    
    with patch('bot.middlewares.admin_api.hmac.compare_digest', return_value=True):
        user = verify_telegram_webapp_data(init_data, 'token')
        assert user is not None
        assert 'id' in user
        assert 'first_name' in user


def test_verify_webapp_data_malformed():
    """Test handling of malformed initData."""
    # Invalid JSON in user field
    init_data = 'user={invalid_json}&hash=abc123'
    user = verify_telegram_webapp_data(init_data, 'token')
    assert user is None
