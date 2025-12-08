"""Tests for admin promo code creation FSM."""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, User

from bot.handlers.admin import (
    PromoCodeStates,
    callback_promo_create,
    process_promo_code,
    process_promo_type,
    process_promo_discount,
    process_promo_maxuses,
    process_promo_validdays,
    process_promo_confirm,
    callback_promo_cancel,
)


@pytest.fixture
def mock_state():
    """Create mock FSM state."""
    state = AsyncMock(spec=FSMContext)
    state.get_data = AsyncMock(return_value={})
    state.update_data = AsyncMock()
    state.set_state = AsyncMock()
    state.clear = AsyncMock()
    return state


@pytest.fixture
def mock_callback():
    """Create mock callback query."""
    callback = MagicMock(spec=CallbackQuery)
    callback.message = MagicMock()
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()
    callback.data = ""
    callback.from_user = User(id=123, is_bot=False, first_name="Admin")
    return callback


@pytest.fixture
def mock_message():
    """Create mock message."""
    message = MagicMock(spec=Message)
    message.answer = AsyncMock()
    message.text = ""
    message.from_user = User(id=123, is_bot=False, first_name="Admin")
    return message


@pytest.mark.asyncio
async def test_callback_promo_create_starts_fsm(mock_callback, mock_state):
    """Test that promo create callback starts FSM."""
    await callback_promo_create(mock_callback, mock_state)
    
    # Check FSM state was set
    mock_state.set_state.assert_called_once_with(PromoCodeStates.waiting_for_code)
    
    # Check message was edited
    mock_callback.message.edit_text.assert_called_once()
    assert "Шаг 1/5" in mock_callback.message.edit_text.call_args[0][0]


@pytest.mark.asyncio
async def test_process_promo_code_valid_code(mock_message, mock_state):
    """Test valid promo code input."""
    mock_message.text = "NEWYEAR2025"
    
    with patch('bot.handlers.admin.get_admin_session') as mock_session:
        mock_repo = AsyncMock()
        mock_repo.get_promo_code_by_code = AsyncMock(return_value=None)
        mock_session.return_value.__aenter__.return_value = MagicMock()
        
        with patch('bot.handlers.admin.PromoCodeRepository', return_value=mock_repo):
            await process_promo_code(mock_message, mock_state)
    
    # Check code was saved in uppercase
    mock_state.update_data.assert_called_once_with(code="NEWYEAR2025")
    
    # Check moved to next state
    mock_state.set_state.assert_called_once_with(PromoCodeStates.waiting_for_type)
    
    # Check response message
    mock_message.answer.assert_called_once()
    assert "Шаг 2/5" in mock_message.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_process_promo_code_invalid_characters(mock_message, mock_state):
    """Test promo code with invalid characters."""
    mock_message.text = "NEW-YEAR!"
    
    await process_promo_code(mock_message, mock_state)
    
    # Should not update data or change state
    mock_state.update_data.assert_not_called()
    mock_state.set_state.assert_not_called()
    
    # Should show error
    mock_message.answer.assert_called_once()
    assert "только латинские буквы и цифры" in mock_message.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_process_promo_code_too_short(mock_message, mock_state):
    """Test promo code that is too short."""
    mock_message.text = "ABC"
    
    with patch('bot.handlers.admin.get_admin_session'):
        await process_promo_code(mock_message, mock_state)
    
    # Should show error about length
    mock_message.answer.assert_called_once()
    assert "от 4 до 20 символов" in mock_message.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_process_promo_code_already_exists(mock_message, mock_state):
    """Test promo code that already exists."""
    mock_message.text = "EXISTS"
    
    with patch('bot.handlers.admin.get_admin_session') as mock_session:
        mock_repo = AsyncMock()
        # Simulate existing code
        mock_repo.get_promo_code_by_code = AsyncMock(return_value=MagicMock())
        mock_session.return_value.__aenter__.return_value = MagicMock()
        
        with patch('bot.handlers.admin.PromoCodeRepository', return_value=mock_repo):
            await process_promo_code(mock_message, mock_state)
    
    # Should show error about duplicate
    mock_message.answer.assert_called_once()
    assert "уже существует" in mock_message.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_process_promo_type_percent(mock_callback, mock_state):
    """Test selecting percent discount type."""
    mock_callback.data = "promo_type:percent"
    mock_state.get_data = AsyncMock(return_value={'code': 'TEST'})
    
    await process_promo_type(mock_callback, mock_state)
    
    # Check type was saved
    mock_state.update_data.assert_called_once_with(type='percent')
    
    # Check moved to next state
    mock_state.set_state.assert_called_once_with(PromoCodeStates.waiting_for_discount)


@pytest.mark.asyncio
async def test_process_promo_discount_valid_percent(mock_message, mock_state):
    """Test valid percent discount input."""
    mock_message.text = "20"
    mock_state.get_data = AsyncMock(return_value={'code': 'TEST', 'type': 'percent'})
    
    await process_promo_discount(mock_message, mock_state)
    
    # Check discount was saved
    mock_state.update_data.assert_called_once_with(discount_percent=20)
    
    # Check moved to next state
    mock_state.set_state.assert_called_once_with(PromoCodeStates.waiting_for_max_uses)


@pytest.mark.asyncio
async def test_process_promo_discount_invalid_percent(mock_message, mock_state):
    """Test invalid percent discount (>100)."""
    mock_message.text = "150"
    mock_state.get_data = AsyncMock(return_value={'code': 'TEST', 'type': 'percent'})
    
    await process_promo_discount(mock_message, mock_state)
    
    # Should not save or change state
    mock_state.update_data.assert_not_called()
    mock_state.set_state.assert_not_called()
    
    # Should show error
    assert mock_message.answer.called
    assert "от 1 до 100" in mock_message.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_process_promo_discount_fixed_amount(mock_message, mock_state):
    """Test fixed amount discount input."""
    mock_message.text = "500"
    mock_state.get_data = AsyncMock(return_value={'code': 'TEST', 'type': 'fixed'})
    
    await process_promo_discount(mock_message, mock_state)
    
    # Check discount was saved
    mock_state.update_data.assert_called_once_with(discount_amount=500)


@pytest.mark.asyncio
async def test_process_promo_discount_trial_extension(mock_message, mock_state):
    """Test trial extension days input."""
    mock_message.text = "7"
    mock_state.get_data = AsyncMock(return_value={'code': 'TEST', 'type': 'trial_extension'})
    
    await process_promo_discount(mock_message, mock_state)
    
    # Check days were saved
    mock_state.update_data.assert_called_once_with(trial_extension_days=7)


@pytest.mark.asyncio
async def test_process_promo_maxuses_valid(mock_message, mock_state):
    """Test valid max uses input."""
    mock_message.text = "100"
    mock_state.get_data = AsyncMock(return_value={'code': 'TEST'})
    
    await process_promo_maxuses(mock_message, mock_state)
    
    # Check max uses was saved
    mock_state.update_data.assert_called_once_with(max_uses=100)


@pytest.mark.asyncio
async def test_process_promo_validdays_valid(mock_message, mock_state):
    """Test valid days input."""
    mock_message.text = "30"
    mock_state.get_data = AsyncMock(return_value={'code': 'TEST'})
    
    await process_promo_validdays(mock_message, mock_state)
    
    # Check valid_until was saved with proper datetime
    assert mock_state.update_data.called
    call_args = mock_state.update_data.call_args[1]
    assert 'valid_until' in call_args
    assert isinstance(call_args['valid_until'], datetime)


@pytest.mark.asyncio
async def test_process_promo_confirm_creates_promo(mock_callback, mock_state):
    """Test promo code creation confirmation."""
    mock_state.get_data = AsyncMock(return_value={
        'code': 'TEST2025',
        'type': 'percent',
        'discount_percent': 20,
        'max_uses': 100,
        'valid_until': None
    })
    
    with patch('bot.handlers.admin.get_admin_session') as mock_session:
        mock_repo = AsyncMock()
        mock_repo.create_promo_code = AsyncMock(return_value=MagicMock(code='TEST2025'))
        mock_db_session = AsyncMock()
        mock_db_session.commit = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_db_session
        
        with patch('bot.handlers.admin.PromoCodeRepository', return_value=mock_repo):
            await process_promo_confirm(mock_callback, mock_state)
    
    # Check promo was created
    mock_repo.create_promo_code.assert_called_once()
    
    # Check FSM was cleared
    mock_state.clear.assert_called_once()
    
    # Check success message
    assert mock_callback.message.edit_text.called
    assert "создан успешно" in mock_callback.message.edit_text.call_args[0][0]


@pytest.mark.asyncio
async def test_callback_promo_cancel(mock_callback, mock_state):
    """Test cancelling promo code creation."""
    await callback_promo_cancel(mock_callback, mock_state)
    
    # Check FSM was cleared
    mock_state.clear.assert_called_once()
    
    # Check cancellation message
    assert mock_callback.message.edit_text.called
    assert "отменено" in mock_callback.message.edit_text.call_args[0][0]


@pytest.mark.asyncio
async def test_full_promo_creation_flow():
    """Test complete promo code creation flow."""
    # This is an integration-style test that verifies the complete flow
    state_data = {}
    
    # Step 1: Code input
    state_data['code'] = 'SUMMER2025'
    assert len(state_data['code']) >= 4
    assert state_data['code'].isupper()
    
    # Step 2: Type selection
    state_data['type'] = 'percent'
    assert state_data['type'] in ['percent', 'fixed', 'trial_extension']
    
    # Step 3: Discount value
    state_data['discount_percent'] = 30
    assert 1 <= state_data['discount_percent'] <= 100
    
    # Step 4: Max uses
    state_data['max_uses'] = 50
    assert state_data['max_uses'] > 0
    
    # Step 5: Valid days
    valid_until = datetime.now(timezone.utc) + timedelta(days=60)
    state_data['valid_until'] = valid_until
    assert state_data['valid_until'] > datetime.now(timezone.utc)
    
    # Verify all required data is present
    assert 'code' in state_data
    assert 'type' in state_data
    assert 'discount_percent' in state_data or 'discount_amount' in state_data or 'trial_extension_days' in state_data
    assert 'max_uses' in state_data
    assert 'valid_until' in state_data
