"""Tests for agent payout system."""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch

from services.agent_payout import AgentPayoutService
from database.models import Referral, ReferralStatus, Master


class TestAgentPayoutService:
    """Test AgentPayoutService functionality."""
    
    def test_calculate_commission(self):
        """Test commission calculation."""
        # Test default 10% commission
        assert AgentPayoutService.calculate_commission(390) == 39  # 390 × 10% = 39
        assert AgentPayoutService.calculate_commission(995) == 99  # 995 × 10% ≈ 100
        assert AgentPayoutService.calculate_commission(3276) == 327  # 3276 × 10% ≈ 328
        
        # Test custom commission percentage
        assert AgentPayoutService.calculate_commission(390, 15) == 58  # 390 × 15%
        assert AgentPayoutService.calculate_commission(1000, 5) == 50
        assert AgentPayoutService.calculate_commission(1000, 20) == 200
    
    @pytest.mark.asyncio
    async def test_process_referral_payout_success(self):
        """Test successful payout processing."""
        # Mock session and bot
        mock_session = AsyncMock()
        mock_bot = AsyncMock()
        
        # Create mock referral
        referral = Mock(spec=Referral)
        referral.id = 1
        referral.referrer_id = 100
        referral.referred_id = 200
        referral.commission_percent = 10
        referral.commission_stars = 0
        referral.payout_status = 'pending'
        
        # Create mock agent (referrer)
        agent = Mock(spec=Master)
        agent.id = 100
        agent.telegram_id = 123456789
        agent.name = "Test Agent"
        
        # Create service
        service = AgentPayoutService(mock_session, mock_bot)
        
        # Mock repository methods
        service.master_repo = AsyncMock()
        service.master_repo.get_by_id = AsyncMock(return_value=agent)
        
        # Mock send_stars_to_agent
        with patch.object(service, 'send_stars_to_agent', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = {
                'success': True,
                'transaction_id': 'tx_123',
                'amount_stars': 39  # 390 × 10%
            }
            
            # Mock notify_agent_about_payout
            with patch.object(service, 'notify_agent_about_payout', new_callable=AsyncMock) as mock_notify:
                mock_notify.return_value = True
                
                # Process payout
                result = await service.process_referral_payout(
                    referral=referral,
                    subscription_amount=390
                )
        
        # Assertions
        assert result['success'] is True
        assert result['commission_stars'] == 39  # 390 × 10%
        assert referral.commission_stars == 39
        assert referral.payout_status == 'sent'
        assert referral.payout_transaction_id == 'tx_123'
        mock_session.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_process_referral_payout_agent_not_found(self):
        """Test payout when agent is not found."""
        mock_session = AsyncMock()
        mock_bot = AsyncMock()
        
        referral = Mock(spec=Referral)
        referral.id = 1
        referral.referrer_id = 100
        referral.commission_percent = 10
        
        service = AgentPayoutService(mock_session, mock_bot)
        service.master_repo = AsyncMock()
        service.master_repo.get_by_id = AsyncMock(return_value=None)
        
        result = await service.process_referral_payout(
            referral=referral,
            subscription_amount=390
        )
        
        assert result['success'] is False
        assert 'error' in result
        assert result['error'] == 'Agent not found'
    
    @pytest.mark.asyncio
    async def test_process_referral_payout_send_failed(self):
        """Test payout when sending stars fails."""
        mock_session = AsyncMock()
        mock_bot = AsyncMock()
        
        referral = Mock(spec=Referral)
        referral.id = 1
        referral.referrer_id = 100
        referral.commission_percent = 10
        referral.commission_stars = 0
        referral.payout_status = 'pending'
        
        agent = Mock(spec=Master)
        agent.id = 100
        agent.telegram_id = 123456789
        
        service = AgentPayoutService(mock_session, mock_bot)
        service.master_repo = AsyncMock()
        service.master_repo.get_by_id = AsyncMock(return_value=agent)
        
        with patch.object(service, 'send_stars_to_agent', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = {
                'success': False,
                'error': 'API error'
            }
            
            result = await service.process_referral_payout(
                referral=referral,
                subscription_amount=390
            )
        
        assert result['success'] is False
        assert referral.payout_status == 'failed'
        assert 'error' in result
        mock_session.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_agent_earnings(self):
        """Test getting agent earnings statistics."""
        mock_session = AsyncMock()
        mock_bot = AsyncMock()
        
        # Create mock agent
        agent = Mock(spec=Master)
        agent.id = 100
        agent.telegram_id = 123456789
        
        # Create mock referrals
        referral1 = Mock(spec=Referral)
        referral1.id = 1
        referral1.payout_status = 'sent'
        referral1.commission_stars = 39
        referral1.payout_sent_at = datetime.now() - timedelta(days=5)
        
        referral2 = Mock(spec=Referral)
        referral2.id = 2
        referral2.payout_status = 'sent'
        referral2.commission_stars = 39
        referral2.payout_sent_at = datetime.now() - timedelta(days=10)
        
        referral3 = Mock(spec=Referral)
        referral3.id = 3
        referral3.payout_status = 'pending'
        referral3.commission_stars = 0
        referral3.payout_sent_at = None
        
        referral4 = Mock(spec=Referral)
        referral4.id = 4
        referral4.payout_status = 'failed'
        referral4.commission_stars = 39
        referral4.payout_sent_at = None
        
        service = AgentPayoutService(mock_session, mock_bot)
        service.master_repo = AsyncMock()
        service.master_repo.get_by_telegram_id = AsyncMock(return_value=agent)
        
        service.referral_repo = AsyncMock()
        service.referral_repo.get_all_by_referrer = AsyncMock(
            return_value=[referral1, referral2, referral3, referral4]
        )
        
        # Get earnings
        result = await service.get_agent_earnings(123456789)
        
        # Assertions
        assert result['success'] is True
        assert result['total_stars_earned'] == 78  # 39 + 39
        assert result['payouts_sent'] == 2
        assert result['payouts_pending'] == 1
        assert result['payouts_failed'] == 1
        assert len(result['payout_history']) == 2
    
    @pytest.mark.asyncio
    async def test_get_agent_earnings_no_payouts(self):
        """Test getting earnings when agent has no payouts."""
        mock_session = AsyncMock()
        mock_bot = AsyncMock()
        
        agent = Mock(spec=Master)
        agent.id = 100
        agent.telegram_id = 123456789
        
        service = AgentPayoutService(mock_session, mock_bot)
        service.master_repo = AsyncMock()
        service.master_repo.get_by_telegram_id = AsyncMock(return_value=agent)
        service.referral_repo = AsyncMock()
        service.referral_repo.get_all_by_referrer = AsyncMock(return_value=[])
        
        result = await service.get_agent_earnings(123456789)
        
        assert result['success'] is True
        assert result['total_stars_earned'] == 0
        assert result['payouts_sent'] == 0
        assert result['payouts_pending'] == 0
        assert len(result['payout_history']) == 0
    
    @pytest.mark.asyncio
    async def test_send_stars_to_agent(self):
        """Test sending stars to agent (simulated for now)."""
        mock_session = AsyncMock()
        mock_bot = AsyncMock()
        
        service = AgentPayoutService(mock_session, mock_bot)
        
        result = await service.send_stars_to_agent(
            agent_telegram_id=123456789,
            amount_stars=99,
            referral_id=1
        )
        
        # Should succeed (simulated)
        assert result['success'] is True
        assert 'transaction_id' in result
        assert result['amount_stars'] == 99
    
    @pytest.mark.asyncio
    async def test_notify_agent_about_payout(self):
        """Test agent notification about payout."""
        mock_session = AsyncMock()
        mock_bot = AsyncMock()
        
        service = AgentPayoutService(mock_session, mock_bot)
        
        result = await service.notify_agent_about_payout(
            agent_telegram_id=123456789,
            commission_stars=39,
            referred_master_name="Мария К."
        )
        
        assert result is True
        mock_bot.send_message.assert_called_once()
        
        # Check message content
        call_args = mock_bot.send_message.call_args
        assert call_args[0][0] == 123456789  # telegram_id
        assert "39 ⭐" in call_args[0][1]  # message contains stars amount
        assert "Мария К." in call_args[0][1]  # message contains name


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

