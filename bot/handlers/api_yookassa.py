"""
API endpoint for YooKassa webhooks
"""
import logging
from aiohttp import web

from database.base import get_db
from database.repositories.subscription import SubscriptionRepository
from services.yookassa_service import yookassa_service

logger = logging.getLogger(__name__)


async def yookassa_webhook_handler(request: web.Request) -> web.Response:
    """
    Handle YooKassa webhook notifications.
    
    Endpoint: POST /api/yookassa/webhook
    """
    try:
        # Get webhook data
        webhook_data = await request.json()
        
        logger.info(f"Received YooKassa webhook: {webhook_data.get('event')}")
        
        # Process webhook
        async with get_db() as session:
            sub_repo = SubscriptionRepository(session)
            success = await yookassa_service.process_webhook(
                webhook_data,
                sub_repo
            )
        
        if success:
            return web.Response(status=200)
        else:
            return web.Response(status=400, text="Failed to process webhook")
            
    except Exception as e:
        logger.error(f"Error handling YooKassa webhook: {e}", exc_info=True)
        return web.Response(status=500, text="Internal server error")


def setup_yookassa_routes(app: web.Application):
    """Setup YooKassa webhook routes."""
    app.router.add_post('/api/yookassa/webhook', yookassa_webhook_handler)
    logger.info("YooKassa webhook route registered: POST /api/yookassa/webhook")
