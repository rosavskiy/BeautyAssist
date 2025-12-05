"""
YooKassa payment service for card/SBP payments
"""
import logging
from typing import Optional
from uuid import uuid4

from yookassa import Configuration, Payment
from yookassa.domain.notification import WebhookNotification

from bot.config import settings
from database.models.subscription import SubscriptionPlan, PaymentMethod
from database.models.transaction import Transaction, TransactionStatus, TransactionType
from database.repositories.subscription import SubscriptionRepository

logger = logging.getLogger(__name__)


class YooKassaService:
    """Service for YooKassa payment processing."""
    
    def __init__(self):
        """Initialize YooKassa configuration."""
        if settings.yookassa_shop_id and settings.yookassa_secret_key:
            Configuration.account_id = settings.yookassa_shop_id
            Configuration.secret_key = settings.yookassa_secret_key
            self.enabled = True
            logger.info("YooKassa configured successfully")
        else:
            self.enabled = False
            logger.warning("YooKassa not configured - missing credentials")
    
    async def create_payment(
        self,
        amount: int,
        currency: str,
        description: str,
        return_url: str,
        subscription_id: int,
        master_id: int,
        metadata: Optional[dict] = None
    ) -> Optional[dict]:
        """
        Create YooKassa payment.
        
        Args:
            amount: Amount in rubles
            currency: Currency code (RUB)
            description: Payment description
            return_url: URL to redirect after payment
            subscription_id: Subscription ID
            master_id: Master ID
            metadata: Additional metadata
            
        Returns:
            Payment data with confirmation URL
        """
        if not self.enabled:
            logger.error("YooKassa is not configured")
            return None
        
        try:
            # Prepare metadata
            payment_metadata = {
                'subscription_id': subscription_id,
                'master_id': master_id,
                **(metadata or {})
            }
            
            # Create payment
            idempotence_key = str(uuid4())
            payment = Payment.create({
                "amount": {
                    "value": f"{amount}.00",
                    "currency": currency
                },
                "confirmation": {
                    "type": "redirect",
                    "return_url": return_url
                },
                "capture": True,  # Auto-capture payment
                "description": description,
                "metadata": payment_metadata
            }, idempotence_key)
            
            logger.info(
                f"YooKassa payment created: {payment.id} "
                f"for subscription {subscription_id}"
            )
            
            return {
                'payment_id': payment.id,
                'status': payment.status,
                'confirmation_url': payment.confirmation.confirmation_url,
                'amount': amount,
                'currency': currency,
                'created_at': payment.created_at
            }
            
        except Exception as e:
            logger.error(f"Failed to create YooKassa payment: {e}", exc_info=True)
            return None
    
    async def check_payment_status(self, payment_id: str) -> Optional[dict]:
        """
        Check payment status.
        
        Args:
            payment_id: YooKassa payment ID
            
        Returns:
            Payment status data
        """
        if not self.enabled:
            return None
        
        try:
            payment = Payment.find_one(payment_id)
            
            return {
                'payment_id': payment.id,
                'status': payment.status,
                'paid': payment.paid,
                'amount': float(payment.amount.value),
                'currency': payment.amount.currency,
                'metadata': payment.metadata
            }
            
        except Exception as e:
            logger.error(f"Failed to check payment status: {e}", exc_info=True)
            return None
    
    async def process_webhook(
        self,
        webhook_data: dict,
        subscription_repo: SubscriptionRepository
    ) -> bool:
        """
        Process YooKassa webhook notification.
        
        Args:
            webhook_data: Webhook JSON data
            subscription_repo: Subscription repository
            
        Returns:
            True if processed successfully
        """
        if not self.enabled:
            return False
        
        try:
            # Parse webhook notification
            notification = WebhookNotification(webhook_data)
            payment = notification.object
            
            logger.info(f"Processing YooKassa webhook for payment {payment.id}")
            
            # Extract metadata
            metadata = payment.metadata or {}
            subscription_id = metadata.get('subscription_id')
            master_id = metadata.get('master_id')
            
            if not subscription_id or not master_id:
                logger.error(f"Missing metadata in payment {payment.id}")
                return False
            
            # Get subscription
            subscription = await subscription_repo.get_by_id(int(subscription_id))
            if not subscription:
                logger.error(f"Subscription {subscription_id} not found")
                return False
            
            # Process based on payment status
            if payment.status == 'succeeded' and payment.paid:
                # Payment successful - activate subscription
                logger.info(f"Payment {payment.id} succeeded, activating subscription")
                
                await subscription_repo.activate_subscription(subscription.id)
                
                # Create transaction record
                transaction = Transaction(
                    master_id=int(master_id),
                    subscription_id=subscription.id,
                    type=TransactionType.SUBSCRIPTION,
                    status=TransactionStatus.SUCCEEDED,
                    amount=int(float(payment.amount.value)),
                    currency=payment.amount.currency,
                    payment_method='yookassa',
                    provider_payment_id=payment.id,
                    description=payment.description
                )
                subscription_repo.session.add(transaction)
                await subscription_repo.session.commit()
                
                logger.info(f"Subscription {subscription_id} activated successfully")
                return True
                
            elif payment.status == 'canceled':
                # Payment canceled
                logger.info(f"Payment {payment.id} was canceled")
                
                transaction = Transaction(
                    master_id=int(master_id),
                    subscription_id=subscription.id,
                    type=TransactionType.SUBSCRIPTION,
                    status=TransactionStatus.CANCELLED,
                    amount=int(float(payment.amount.value)),
                    currency=payment.amount.currency,
                    payment_method='yookassa',
                    provider_payment_id=payment.id,
                    error_message='Payment canceled by user',
                    description=payment.description
                )
                subscription_repo.session.add(transaction)
                await subscription_repo.session.commit()
                return True
                
            elif payment.status == 'waiting_for_capture':
                # Payment is waiting for capture (shouldn't happen with auto-capture)
                logger.warning(f"Payment {payment.id} waiting for capture")
                return True
                
            else:
                logger.warning(f"Unknown payment status: {payment.status}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to process webhook: {e}", exc_info=True)
            return False
    
    async def refund_payment(
        self,
        payment_id: str,
        amount: Optional[int] = None,
        reason: Optional[str] = None
    ) -> Optional[dict]:
        """
        Refund payment.
        
        Args:
            payment_id: YooKassa payment ID
            amount: Refund amount (if partial refund)
            reason: Refund reason
            
        Returns:
            Refund data
        """
        if not self.enabled:
            return None
        
        try:
            from yookassa import Refund
            
            refund_data = {
                "payment_id": payment_id
            }
            
            if amount:
                refund_data["amount"] = {
                    "value": f"{amount}.00",
                    "currency": "RUB"
                }
            
            if reason:
                refund_data["description"] = reason
            
            idempotence_key = str(uuid4())
            refund = Refund.create(refund_data, idempotence_key)
            
            logger.info(f"Refund created: {refund.id} for payment {payment_id}")
            
            return {
                'refund_id': refund.id,
                'status': refund.status,
                'amount': float(refund.amount.value) if refund.amount else None,
                'created_at': refund.created_at
            }
            
        except Exception as e:
            logger.error(f"Failed to create refund: {e}", exc_info=True)
            return None


# Global instance
yookassa_service = YooKassaService()
