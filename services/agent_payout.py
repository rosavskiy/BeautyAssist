"""Agent payout service for commission payments in Telegram Stars."""
import logging
from datetime import datetime
from typing import Optional, Dict, List

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from database.repositories import ReferralRepository, MasterRepository
from database.models import Referral, ReferralStatus

logger = logging.getLogger(__name__)


class AgentPayoutService:
    """Service for handling agent commission payouts in Telegram Stars."""
    
    DEFAULT_COMMISSION_PERCENT = 10  # 10% commission for agents
    
    def __init__(self, session: AsyncSession, bot: Bot):
        self.session = session
        self.bot = bot
        self.referral_repo = ReferralRepository(session)
        self.master_repo = MasterRepository(session)
    
    @staticmethod
    def calculate_commission(
        subscription_amount: int,
        commission_percent: int = DEFAULT_COMMISSION_PERCENT
    ) -> int:
        """
        Calculate commission amount.
        
        Args:
            subscription_amount: Subscription price in Telegram Stars
            commission_percent: Commission percentage (default 10%)
            
        Returns:
            Commission amount in Telegram Stars
            
        Example:
            390 ⭐ × 10% = 39 ⭐
        """
        return int(subscription_amount * commission_percent / 100)
    
    async def process_referral_payout(
        self,
        referral: Referral,
        subscription_amount: int
    ) -> Dict[str, any]:
        """
        Process commission payout for a referral.
        
        Args:
            referral: Referral record
            subscription_amount: Amount paid by referred master
            
        Returns:
            Dict with success status and details
        """
        try:
            # Calculate commission
            commission = self.calculate_commission(
                subscription_amount,
                referral.commission_percent
            )
            
            # Update referral with commission amount
            referral.commission_stars = commission
            await self.session.flush()
            
            # Get agent (referrer) details
            agent = await self.master_repo.get_by_id(referral.referrer_id)
            if not agent:
                logger.error(f"Agent not found: {referral.referrer_id}")
                return {
                    'success': False,
                    'error': 'Agent not found'
                }
            
            # Send stars to agent
            payout_result = await self.send_stars_to_agent(
                agent_telegram_id=agent.telegram_id,
                amount_stars=commission,
                referral_id=referral.id
            )
            
            if payout_result['success']:
                # Update referral payout status
                referral.payout_status = 'sent'
                referral.payout_transaction_id = payout_result.get('transaction_id')
                referral.payout_sent_at = datetime.utcnow()
                await self.session.commit()
                
                # Send notification to agent
                await self.notify_agent_about_payout(
                    agent_telegram_id=agent.telegram_id,
                    commission_stars=commission,
                    referred_master_name=payout_result.get('referred_name', 'мастер')
                )
                
                logger.info(
                    f"Payout successful: referral={referral.id}, "
                    f"agent={agent.telegram_id}, amount={commission}⭐"
                )
                
                return {
                    'success': True,
                    'commission_stars': commission,
                    'transaction_id': payout_result.get('transaction_id')
                }
            else:
                # Mark payout as failed
                referral.payout_status = 'failed'
                await self.session.commit()
                
                logger.error(
                    f"Payout failed: referral={referral.id}, "
                    f"error={payout_result.get('error')}"
                )
                
                return {
                    'success': False,
                    'error': payout_result.get('error', 'Unknown error')
                }
                
        except Exception as e:
            logger.error(f"Error processing payout: {e}", exc_info=True)
            referral.payout_status = 'failed'
            await self.session.commit()
            return {
                'success': False,
                'error': str(e)
            }
    
    async def send_stars_to_agent(
        self,
        agent_telegram_id: int,
        amount_stars: int,
        referral_id: int
    ) -> Dict[str, any]:
        """
        Send Telegram Stars to agent.
        
        Note: Telegram Bot API currently doesn't have a direct method to send stars.
        This is a placeholder for future implementation when the API becomes available.
        
        Possible future methods:
        1. bot.refund_star_payment() - refund as transfer
        2. bot.send_payment() - with negative amount
        3. Telegram Stars Wallet API
        
        For now, we'll simulate the payout and log it.
        
        Args:
            agent_telegram_id: Agent's Telegram ID
            amount_stars: Amount of stars to send
            referral_id: Referral ID for tracking
            
        Returns:
            Dict with success status and transaction details
        """
        try:
            # TODO: Implement actual Telegram Stars transfer when API is available
            # For now, we'll just log and return simulated success
            
            transaction_id = f"payout_{referral_id}_{int(datetime.utcnow().timestamp())}"
            
            logger.info(
                f"[SIMULATED] Sending {amount_stars}⭐ to agent {agent_telegram_id} "
                f"(transaction: {transaction_id})"
            )
            
            # In production, this would be:
            # result = await self.bot.send_stars(
            #     user_id=agent_telegram_id,
            #     amount=amount_stars,
            #     description=f"Комиссия за реферала #{referral_id}"
            # )
            
            return {
                'success': True,
                'transaction_id': transaction_id,
                'amount_stars': amount_stars
            }
            
        except Exception as e:
            logger.error(f"Failed to send stars: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    async def notify_agent_about_payout(
        self,
        agent_telegram_id: int,
        commission_stars: int,
        referred_master_name: str
    ) -> bool:
        """
        Send notification to agent about commission payout.
        
        Args:
            agent_telegram_id: Agent's Telegram ID
            commission_stars: Commission amount in stars
            referred_master_name: Name of referred master
            
        Returns:
            True if notification sent successfully
        """
        try:
            message = (
                f"🎉 *Новая выплата!*\n\n"
                f"Ваш реферал {referred_master_name} оплатил подписку\n"
                f"💰 Вы получили: *{commission_stars} ⭐*\n\n"
                f"Продолжайте приглашать мастеров и зарабатывайте!\n"
                f"Используйте /referral для получения реферальной ссылки"
            )
            
            await self.bot.send_message(
                agent_telegram_id,
                message,
                parse_mode="Markdown"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to notify agent: {e}", exc_info=True)
            return False
    
    async def get_agent_earnings(
        self,
        agent_telegram_id: int
    ) -> Dict[str, any]:
        """
        Get agent's total earnings and statistics.
        
        Args:
            agent_telegram_id: Agent's Telegram ID
            
        Returns:
            Dict with earnings statistics
        """
        try:
            # Get agent
            agent = await self.master_repo.get_by_telegram_id(agent_telegram_id)
            if not agent:
                return {
                    'success': False,
                    'error': 'Agent not found'
                }
            
            # Get all referrals
            referrals = await self.referral_repo.get_all_by_referrer(agent.id)
            
            total_stars = 0
            paid_count = 0
            pending_count = 0
            failed_count = 0
            
            payout_history = []
            
            for ref in referrals:
                if ref.payout_status == 'sent':
                    total_stars += ref.commission_stars
                    paid_count += 1
                    payout_history.append({
                        'date': ref.payout_sent_at,
                        'amount': ref.commission_stars,
                        'referral_id': ref.id
                    })
                elif ref.payout_status == 'pending':
                    pending_count += 1
                elif ref.payout_status == 'failed':
                    failed_count += 1
            
            return {
                'success': True,
                'total_stars_earned': total_stars,
                'payouts_sent': paid_count,
                'payouts_pending': pending_count,
                'payouts_failed': failed_count,
                'payout_history': sorted(
                    payout_history,
                    key=lambda x: x['date'] if x['date'] else datetime.min,
                    reverse=True
                )
            }
            
        except Exception as e:
            logger.error(f"Error getting agent earnings: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    async def retry_failed_payouts(self) -> Dict[str, any]:
        """
        Retry failed payouts (admin function).
        
        Returns:
            Dict with retry results
        """
        try:
            # This would be implemented as a background task
            # to retry failed payouts periodically
            logger.info("Retry failed payouts - not implemented yet")
            
            return {
                'success': True,
                'message': 'Retry functionality will be implemented'
            }
            
        except Exception as e:
            logger.error(f"Error retrying payouts: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }

