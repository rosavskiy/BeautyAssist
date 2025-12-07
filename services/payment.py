"""Payment service for Telegram Stars integration."""
import logging
from datetime import datetime, timedelta

from aiogram import Bot
from aiogram.types import LabeledPrice, PreCheckoutQuery, SuccessfulPayment
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.subscription import SubscriptionPlan, SubscriptionStatus, PaymentMethod
from database.models.transaction import TransactionStatus, TransactionType
from database.repositories.subscription import SubscriptionRepository
from database.repositories.master import MasterRepository
from bot.subscription_plans import get_plan_config
from services.referral import ReferralService
from services.agent_payout import AgentPayoutService

logger = logging.getLogger(__name__)


class PaymentService:
    """Service for handling payments through Telegram Stars."""
    
    def __init__(self, bot: Bot):
        self.bot = bot
    
    async def send_invoice(
        self,
        chat_id: int,
        plan: SubscriptionPlan,
        session: AsyncSession,
    ) -> None:
        """Send payment invoice to user."""
        plan_config = get_plan_config(plan)
        
        # Create pending subscription and transaction
        repo = SubscriptionRepository(session)
        master_repo = MasterRepository(session)
        
        master = await master_repo.get_by_telegram_id(chat_id)
        if not master:
            raise ValueError("Master not found")
        
        # Calculate dates
        start_date = datetime.now()
        end_date = start_date + plan_config.duration
        
        # Create subscription
        subscription = await repo.create_subscription(
            master_id=master.id,
            plan=plan,
            start_date=start_date,
            end_date=end_date,
            amount=plan_config.price_stars,
            currency="XTR",  # Telegram Stars currency code
            payment_method=PaymentMethod.TELEGRAM_STARS,
            auto_renew=False,
        )
        
        # Create transaction
        transaction = await repo.create_transaction(
            master_id=master.id,
            subscription_id=subscription.id,
            type=TransactionType.SUBSCRIPTION,
            amount=plan_config.price_stars,
            currency="XTR",
            payment_method=PaymentMethod.TELEGRAM_STARS,
            description=f"Подписка {plan_config.name}",
        )
        
        await session.commit()
        
        # Send invoice
        prices = [LabeledPrice(label=plan_config.name, amount=plan_config.price_stars)]
        
        await self.bot.send_invoice(
            chat_id=chat_id,
            title=f"BeautyAssist - {plan_config.name}",
            description=plan_config.description,
            payload=f"subscription:{subscription.id}:{transaction.id}",
            currency="XTR",  # Telegram Stars
            prices=prices,
            provider_token="",  # Empty for Stars
        )
        
        logger.info(
            f"Sent invoice to {chat_id} for {plan.value} "
            f"(subscription_id={subscription.id}, transaction_id={transaction.id})"
        )
    
    async def handle_pre_checkout(
        self,
        pre_checkout_query: PreCheckoutQuery,
        session: AsyncSession,
    ) -> bool:
        """Handle pre-checkout query (validation before payment)."""
        try:
            # Parse payload: subscription:{subscription_id}:{transaction_id}
            parts = pre_checkout_query.invoice_payload.split(":")
            if len(parts) != 3 or parts[0] != "subscription":
                logger.error(f"Invalid payload: {pre_checkout_query.invoice_payload}")
                await pre_checkout_query.answer(
                    ok=False,
                    error_message="Ошибка обработки платежа. Попробуйте позже."
                )
                return False
            
            subscription_id = int(parts[1])
            transaction_id = int(parts[2])
            
            # Verify subscription and transaction exist
            repo = SubscriptionRepository(session)
            subscription = await repo.get_subscription_by_id(subscription_id)
            
            if not subscription or subscription.status != SubscriptionStatus.PENDING.value:
                logger.error(f"Invalid subscription: {subscription_id}")
                await pre_checkout_query.answer(
                    ok=False,
                    error_message="Подписка не найдена или уже оплачена."
                )
                return False
            
            # All checks passed
            await pre_checkout_query.answer(ok=True)
            logger.info(f"Pre-checkout approved for subscription {subscription_id}")
            return True
            
        except Exception as e:
            logger.error(f"Pre-checkout error: {e}", exc_info=True)
            await pre_checkout_query.answer(
                ok=False,
                error_message="Произошла ошибка. Попробуйте позже."
            )
            return False
    
    async def handle_successful_payment(
        self,
        payment: SuccessfulPayment,
        user_telegram_id: int,
        session: AsyncSession,
    ) -> bool:
        """Handle successful payment."""
        try:
            # Parse payload
            parts = payment.invoice_payload.split(":")
            if len(parts) != 3 or parts[0] != "subscription":
                logger.error(f"Invalid payload in successful payment: {payment.invoice_payload}")
                return False
            
            subscription_id = int(parts[1])
            transaction_id = int(parts[2])
            
            repo = SubscriptionRepository(session)
            master_repo = MasterRepository(session)
            
            # Update transaction
            transaction = await repo.update_transaction_status(
                transaction_id=transaction_id,
                status=TransactionStatus.SUCCEEDED,
                provider_data={
                    "telegram_payment_charge_id": payment.telegram_payment_charge_id,
                    "provider_payment_charge_id": payment.provider_payment_charge_id,
                    "total_amount": payment.total_amount,
                    "currency": payment.currency,
                },
            )
            
            # Activate subscription
            subscription = await repo.activate_subscription(subscription_id)
            
            # Update master premium status
            master = await master_repo.get_by_telegram_id(user_telegram_id)
            if master:
                master.is_premium = True
                master.premium_until = subscription.end_date
                await session.flush()
            
            # ✨ NEW: Process agent commission if this is a referral
            try:
                referral_service = ReferralService(session)
                payout_service = AgentPayoutService(session, self.bot)
                
                # Check if this master was referred
                referral = await referral_service.get_by_referred_id(master.id)
                
                if referral and referral.status == 'pending':
                    # Activate referral
                    await referral_service.activate_referral(
                        referral_id=referral.id,
                        referred_telegram_id=user_telegram_id
                    )
                    
                    # Process commission payout to agent
                    payout_result = await payout_service.process_referral_payout(
                        referral=referral,
                        subscription_amount=payment.total_amount
                    )
                    
                    if payout_result['success']:
                        logger.info(
                            f"Agent commission paid: {payout_result['commission_stars']}⭐ "
                            f"for referral {referral.id}"
                        )
                    else:
                        logger.error(
                            f"Agent commission failed for referral {referral.id}: "
                            f"{payout_result.get('error')}"
                        )
                        
            except Exception as e:
                # Don't fail the whole payment if payout fails
                logger.error(f"Error processing agent payout: {e}", exc_info=True)
            
            await session.commit()
            
            logger.info(
                f"Payment successful: subscription={subscription_id}, "
                f"transaction={transaction_id}, user={user_telegram_id}"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error handling successful payment: {e}", exc_info=True)
            await session.rollback()
            return False
    
    async def activate_trial(
        self,
        master_id: int,
        telegram_id: int,
        session: AsyncSession,
    ) -> bool:
        """Activate trial subscription for master."""
        try:
            repo = SubscriptionRepository(session)
            master_repo = MasterRepository(session)
            
            # Check if trial is available
            if not await repo.is_trial_available(master_id):
                logger.warning(f"Trial not available for master {master_id}")
                return False
            
            plan_config = get_plan_config(SubscriptionPlan.TRIAL)
            
            # Calculate dates
            start_date = datetime.now()
            end_date = start_date + plan_config.duration
            
            # Create trial subscription
            subscription = await repo.create_subscription(
                master_id=master_id,
                plan=SubscriptionPlan.TRIAL,
                start_date=start_date,
                end_date=end_date,
                amount=0,
                currency="RUB",
                payment_method=PaymentMethod.MANUAL,
                auto_renew=False,
            )
            
            # Activate immediately
            await repo.activate_subscription(subscription.id)
            
            # Update master
            master = await master_repo.get_by_id(master_id)
            if master:
                master.is_premium = True
                master.premium_until = end_date
                await session.flush()
            
            await session.commit()
            
            logger.info(f"Trial activated for master {master_id} (subscription {subscription.id})")
            return True
            
        except Exception as e:
            logger.error(f"Error activating trial: {e}", exc_info=True)
            await session.rollback()
            return False
