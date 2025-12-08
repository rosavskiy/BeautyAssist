"""Admin API middleware for aiohttp - validates Telegram WebApp auth."""
import hmac
import hashlib
import logging
from urllib.parse import parse_qsl
from typing import Callable
from aiohttp import web

from bot.config import settings

logger = logging.getLogger(__name__)


def verify_telegram_webapp_data(init_data: str, bot_token: str) -> dict | None:
    """Verify Telegram WebApp initData signature.
    
    Args:
        init_data: Raw initData string from Telegram WebApp
        bot_token: Bot token for HMAC verification
        
    Returns:
        dict: Parsed user data if valid, None otherwise
    """
    try:
        # Parse init_data
        parsed_data = dict(parse_qsl(init_data))
        
        # Extract hash
        received_hash = parsed_data.pop('hash', None)
        if not received_hash:
            logger.warning("No hash in initData")
            return None
        
        # Sort keys and create data_check_string
        data_check_arr = [f"{k}={v}" for k, v in sorted(parsed_data.items())]
        data_check_string = '\n'.join(data_check_arr)
        
        # Calculate secret key
        secret_key = hmac.new(
            key=b"WebAppData",
            msg=bot_token.encode(),
            digestmod=hashlib.sha256
        ).digest()
        
        # Calculate hash
        calculated_hash = hmac.new(
            key=secret_key,
            msg=data_check_string.encode(),
            digestmod=hashlib.sha256
        ).hexdigest()
        
        # Verify hash
        if not hmac.compare_digest(calculated_hash, received_hash):
            logger.warning("Invalid initData hash")
            return None
        
        # Parse user data
        user_data = parsed_data.get('user')
        if not user_data:
            logger.warning("No user data in initData")
            return None
        
        import json
        user = json.loads(user_data)
        return user
        
    except Exception as e:
        logger.error(f"Error verifying initData: {e}", exc_info=True)
        return None


@web.middleware
async def admin_api_auth_middleware(request: web.Request, handler: Callable):
    """Middleware to protect /api/admin/* endpoints.
    
    Validates Telegram WebApp initData and checks if user is admin.
    """
    # Only protect /api/admin/* paths
    if not request.path.startswith('/api/admin/'):
        return await handler(request)
    
    # Get initData from header or query parameter
    init_data = request.headers.get('X-Telegram-Init-Data') or request.query.get('_auth')
    
    if not init_data:
        logger.warning(f"Admin API access without auth: {request.path}")
        return web.json_response(
            {"error": "Authentication required. Access via Telegram WebApp only."},
            status=401
        )
    
    # Verify initData
    user = verify_telegram_webapp_data(init_data, settings.bot_token)
    
    if not user:
        logger.warning(f"Invalid initData for admin API: {request.path}")
        return web.json_response(
            {"error": "Invalid authentication data"},
            status=401
        )
    
    # Check if user is admin
    user_id = user.get('id')
    if not user_id or user_id not in settings.admin_telegram_ids:
        logger.warning(f"Non-admin access attempt to {request.path} by user {user_id}")
        return web.json_response(
            {"error": "Admin access required"},
            status=403
        )
    
    # User is admin, allow access
    logger.info(f"Admin API access granted to user {user_id} for {request.path}")
    request['admin_user'] = user
    return await handler(request)
