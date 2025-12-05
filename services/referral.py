"""Referral service for business logic."""
import base64
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict

from sqlalchemy.ext.asyncio import AsyncSession
from aiogram import Bot

from database.repositories import ReferralRepository, MasterRepository, SubscriptionRepository
from database.models import ReferralStatus
from bot.config import BOT_USERNAME

logger = logging.getLogger(__name__)


class ReferralService:
    """Service for referral program operations."""
    
    REWARD_DAYS = 7  # Days added to subscription for each activated referral
    EXPIRATION_DAYS = 30  # Days until pending referral expires
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.referral_repo = ReferralRepository(session)
        self.master_repo = MasterRepository(session)
        self.subscription_repo = SubscriptionRepository(session)
    
    @staticmethod
    def generate_referral_link(master_id: int) -> str:
        """Generate referral link for master."""
        # Encode master_id to base64
        encoded = base64.urlsafe_b64encode(str(master_id).encode()).decode().rstrip('=')
        return f"https://t.me/{BOT_USERNAME}?start=ref_{encoded}"
    
    @staticmethod
    def decode_referral_code(code: str) -> Optional[int]:
        """Decode referral code to master_id."""
        try:
            # Remove 'ref_' prefix if present
            if code.startswith('ref_'):
                code = code[4:]
            
            # Add padding if needed
            padding = 4 - len(code) % 4
            if padding != 4:
                code += '=' * padding
            
            decoded = base64.urlsafe_b64decode(code).decode()
            return int(decoded)
        except Exception as e:
            logger.error(f"Failed to decode referral code '{code}': {e}")
            return None
    
    async def create_referral(
        self,
        referrer_id: int,
        referred_id: int
    ) -> Optional[Dict[str, any]]:
        """
        Create new referral record.
        
        Returns:
            Dict with success status and message, or None on error
        """
        # Check if referrer exists
        referrer = await self.master_repo.get_by_id(referrer_id)
        if not referrer:
            return {
                'success': False,
                'message': 'Referrer not found'
            }
        
        # Check if referred exists
        referred = await self.master_repo.get_by_id(referred_id)
        if not referred:
            return {
                'success': False,
                'message': 'Referred master not found'
            }
        
        # Check if self-referral
        if referrer_id == referred_id:
            return {
                'success': False,
                'message': 'Cannot refer yourself'
            }
        
        # Check for duplicates
        duplicate = await self.referral_repo.check_duplicate(referrer_id, referred_id)
        if duplicate:
            return {
                'success': False,
                'message': 'Referral already exists'
            }
        
        # Create referral
        referral = await self.referral_repo.create(
            referrer_id=referrer_id,
            referred_id=referred_id,
            reward_days=self.REWARD_DAYS
        )
        
        logger.info(f"Created referral: {referrer_id} → {referred_id} (id={referral.id})")
        
        return {
            'success': True,
            'message': 'Referral created',
            'referral_id': referral.id
        }
    
    async def activate_referral(
        self,
        referred_id: int,
        bot: Optional[Bot] = None
    ) -> Optional[Dict[str, any]]:
        """
        Activate referral and reward referrer when referred master pays.
        
        Args:
            referred_id: ID of master who just paid
            bot: Bot instance for sending notifications
        
        Returns:
            Dict with result info
        """
        # Find referral record
        referral = await self.referral_repo.get_by_referred_id(referred_id)
        if not referral:
            logger.info(f"No referral found for master {referred_id}")
            return {
                'success': False,
                'message': 'No referral record found'
            }
        
        # Check if already activated
        if referral.status == ReferralStatus.ACTIVATED.value:
            logger.info(f"Referral {referral.id} already activated")
            return {
                'success': False,
                'message': 'Referral already activated'
            }
        
        # Check if expired
        if referral.status == ReferralStatus.EXPIRED.value:
            logger.warning(f"Referral {referral.id} is expired")
            return {
                'success': False,
                'message': 'Referral expired'
            }
        
        # Activate referral
        await self.referral_repo.activate(referral.id)
        
        # Add reward days to referrer's subscription
        referrer_id = referral.referrer_id
        reward_days = referral.reward_days
        
        try:
            subscription = await self.subscription_repo.get_active_subscription(referrer_id)
            if subscription:
                # Extend existing subscription
                new_expires = subscription.expires_at + timedelta(days=reward_days)
                await self.subscription_repo.extend_subscription(
                    subscription.id,
                    new_expires
                )
                logger.info(f"Extended subscription for master {referrer_id} by {reward_days} days")
            else:
                # No active subscription - could activate trial or do nothing
                # For now, just log it
                logger.warning(f"Master {referrer_id} has no active subscription to extend")
        
            # Send notification to referrer
            if bot:
                try:
                    referrer = await self.master_repo.get_by_id(referrer_id)
                    if referrer:
                        text = (
                            f"🎉 <b>Реферальное вознаграждение!</b>\n\n"
                            f"Ваш реферал активировал подписку!\n"
                            f"Вам начислено <b>+{reward_days} дней</b> подписки.\n\n"
                            f"Продолжайте приглашать друзей! 🚀"
                        )
                        await bot.send_message(
                            chat_id=referrer.telegram_id,
                            text=text,
                            parse_mode="HTML"
                        )
                except Exception as e:
                    logger.error(f"Failed to send referral notification: {e}")
        
            return {
                'success': True,
                'message': f'Referral activated, {reward_days} days added',
                'referrer_id': referrer_id,
                'reward_days': reward_days
            }
        
        except Exception as e:
            logger.error(f"Error activating referral {referral.id}: {e}")
            return {
                'success': False,
                'message': f'Error: {str(e)}'
            }
    
    async def get_statistics(self, master_id: int) -> Dict[str, any]:
        """Get referral statistics for master."""
        stats = await self.referral_repo.get_statistics(master_id)
        
        # Calculate total referrals
        total = stats['pending'] + stats['activated'] + stats['expired']
        
        return {
            'total': total,
            'pending': stats['pending'],
            'activated': stats['activated'],
            'expired': stats['expired'],
            'total_reward_days': stats['total_reward_days']
        }
    
    async def expire_old_referrals(self) -> int:
        """Expire referrals older than EXPIRATION_DAYS."""
        count = await self.referral_repo.expire_old_referrals(days=self.EXPIRATION_DAYS)
        if count > 0:
            logger.info(f"Expired {count} old referrals")
        return count
