"""Broadcast service for mass messaging."""
import asyncio
import logging
from typing import Any

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest, TelegramRetryAfter

from database.repositories.admin import AdminRepository

logger = logging.getLogger(__name__)


class BroadcastService:
    """Service for sending mass messages to users."""
    
    def __init__(self, bot: Bot, admin_repo: AdminRepository):
        """Initialize broadcast service.
        
        Args:
            bot: Telegram Bot instance
            admin_repo: Admin repository for tracking progress
        """
        self.bot = bot
        self.admin_repo = admin_repo
    
    async def send_broadcast(
        self, 
        broadcast_id: int,
        content: str, 
        recipient_ids: list[int],
        delay_between_messages: float = 0.05
    ) -> dict[str, Any]:
        """Send broadcast message to all recipients.
        
        Args:
            broadcast_id: Broadcast record ID for tracking
            content: Message text to send
            recipient_ids: List of telegram IDs to send to
            delay_between_messages: Delay in seconds between messages (default 50ms)
        
        Returns:
            dict: Statistics including sent_count, failed_count, errors
        """
        sent_count = 0
        failed_count = 0
        errors = []
        
        logger.info(f"Starting broadcast {broadcast_id} to {len(recipient_ids)} recipients")
        
        for i, telegram_id in enumerate(recipient_ids, start=1):
            try:
                await self.bot.send_message(
                    chat_id=telegram_id,
                    text=content,
                    parse_mode="HTML"
                )
                sent_count += 1
                
                # Update progress every 10 messages
                if i % 10 == 0:
                    await self.admin_repo.update_broadcast_progress(
                        broadcast_id=broadcast_id,
                        sent_count=sent_count,
                        failed_count=failed_count,
                        is_completed=False
                    )
                    logger.info(f"Broadcast {broadcast_id}: {sent_count}/{len(recipient_ids)} sent")
                
            except TelegramForbiddenError:
                # User blocked the bot
                failed_count += 1
                errors.append({"telegram_id": telegram_id, "error": "User blocked bot"})
                logger.warning(f"User {telegram_id} blocked the bot")
                
            except TelegramBadRequest as e:
                # Invalid user or chat
                failed_count += 1
                errors.append({"telegram_id": telegram_id, "error": f"Bad request: {str(e)}"})
                logger.warning(f"Bad request for user {telegram_id}: {e}")
                
            except TelegramRetryAfter as e:
                # Rate limit hit, wait and retry
                logger.warning(f"Rate limit hit, waiting {e.retry_after} seconds")
                await asyncio.sleep(e.retry_after)
                
                try:
                    await self.bot.send_message(
                        chat_id=telegram_id,
                        text=content,
                        parse_mode="HTML"
                    )
                    sent_count += 1
                except Exception as retry_error:
                    failed_count += 1
                    errors.append({"telegram_id": telegram_id, "error": f"Retry failed: {str(retry_error)}"})
                    logger.error(f"Retry failed for user {telegram_id}: {retry_error}")
            
            except Exception as e:
                # Unexpected error
                failed_count += 1
                errors.append({"telegram_id": telegram_id, "error": f"Unexpected: {str(e)}"})
                logger.error(f"Unexpected error sending to {telegram_id}: {e}", exc_info=True)
            
            # Delay between messages to avoid rate limits
            await asyncio.sleep(delay_between_messages)
        
        # Mark broadcast as completed
        await self.admin_repo.update_broadcast_progress(
            broadcast_id=broadcast_id,
            sent_count=sent_count,
            failed_count=failed_count,
            is_completed=True
        )
        
        logger.info(
            f"Broadcast {broadcast_id} completed: {sent_count} sent, {failed_count} failed"
        )
        
        return {
            "broadcast_id": broadcast_id,
            "total": len(recipient_ids),
            "sent": sent_count,
            "failed": failed_count,
            "errors": errors[:10]  # Return only first 10 errors
        }
