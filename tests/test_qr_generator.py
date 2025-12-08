"""Tests for QR code generation utilities."""
import io
import pytest
from unittest.mock import patch, MagicMock

from bot.utils.qr_generator import (
    generate_qr_code,
    generate_webapp_qr,
    generate_referral_qr,
)


def test_generate_qr_code_basic():
    """Test basic QR code generation."""
    data = "https://example.com"
    
    qr_buffer = generate_qr_code(data)
    
    # Check return type
    assert isinstance(qr_buffer, io.BytesIO)
    
    # Check buffer has content
    qr_buffer.seek(0)
    content = qr_buffer.read()
    assert len(content) > 0
    
    # Check PNG signature (first 8 bytes)
    qr_buffer.seek(0)
    signature = qr_buffer.read(8)
    assert signature == b'\x89PNG\r\n\x1a\n', "Generated file is not a valid PNG"


def test_generate_qr_code_with_params():
    """Test QR code generation with custom parameters."""
    data = "TEST_DATA_123"
    box_size = 15
    border = 3
    
    qr_buffer = generate_qr_code(data, box_size=box_size, border=border)
    
    assert isinstance(qr_buffer, io.BytesIO)
    qr_buffer.seek(0)
    content = qr_buffer.read()
    assert len(content) > 0


def test_generate_qr_code_long_data():
    """Test QR code with longer data."""
    data = "https://example.com/very/long/path?" + "x" * 200
    
    qr_buffer = generate_qr_code(data)
    
    assert isinstance(qr_buffer, io.BytesIO)
    qr_buffer.seek(0)
    assert len(qr_buffer.read()) > 0


def test_generate_qr_code_cyrillic():
    """Test QR code with cyrillic characters."""
    data = "https://t.me/bot?start=привет_мир"
    
    qr_buffer = generate_qr_code(data)
    
    assert isinstance(qr_buffer, io.BytesIO)
    qr_buffer.seek(0)
    assert len(qr_buffer.read()) > 0


def test_generate_webapp_qr():
    """Test WebApp QR code generation."""
    bot_username = "test_bot"
    referral_code = "ABC123XY"
    
    qr_buffer = generate_webapp_qr(bot_username, referral_code)
    
    assert isinstance(qr_buffer, io.BytesIO)
    qr_buffer.seek(0)
    content = qr_buffer.read()
    assert len(content) > 0
    
    # Verify PNG signature
    qr_buffer.seek(0)
    signature = qr_buffer.read(8)
    assert signature == b'\x89PNG\r\n\x1a\n'


def test_generate_webapp_qr_url_format():
    """Test that WebApp QR contains correct URL format."""
    bot_username = "beautyassist_bot"
    referral_code = "03FITDVW"
    
    with patch('bot.utils.qr_generator.generate_qr_code') as mock_generate:
        mock_generate.return_value = io.BytesIO(b"fake_qr")
        
        generate_webapp_qr(bot_username, referral_code)
        
        # Check that generate_qr_code was called with correct URL
        expected_url = f"https://t.me/{bot_username}?start={referral_code}"
        mock_generate.assert_called_once()
        actual_url = mock_generate.call_args[0][0]
        assert actual_url == expected_url


def test_generate_webapp_qr_with_box_size():
    """Test WebApp QR with custom box size."""
    bot_username = "test_bot"
    referral_code = "XYZ789AB"
    box_size = 20
    
    qr_buffer = generate_webapp_qr(bot_username, referral_code, box_size=box_size)
    
    assert isinstance(qr_buffer, io.BytesIO)
    qr_buffer.seek(0)
    assert len(qr_buffer.read()) > 0


def test_generate_referral_qr():
    """Test referral QR code generation."""
    bot_username = "test_bot"
    referral_code = "ABC123XYZ"
    
    qr_buffer = generate_referral_qr(bot_username, referral_code)
    
    assert isinstance(qr_buffer, io.BytesIO)
    qr_buffer.seek(0)
    content = qr_buffer.read()
    assert len(content) > 0


def test_generate_referral_qr_url_format():
    """Test that referral QR contains correct URL format."""
    bot_username = "beautyassist_bot"
    referral_code = "REF_CODE_123"
    
    with patch('bot.utils.qr_generator.generate_qr_code') as mock_generate:
        mock_generate.return_value = io.BytesIO(b"fake_qr")
        
        generate_referral_qr(bot_username, referral_code)
        
        # Check URL format
        expected_url = f"https://t.me/{bot_username}?start=ref_{referral_code}"
        mock_generate.assert_called_once()
        actual_url = mock_generate.call_args[0][0]
        assert actual_url == expected_url


def test_generate_qr_code_error_handling():
    """Test error handling in QR code generation."""
    with patch('bot.utils.qr_generator.qrcode.QRCode') as mock_qrcode:
        mock_qrcode.side_effect = Exception("QR generation failed")
        
        with pytest.raises(Exception) as exc_info:
            generate_qr_code("test_data")
        
        assert "QR generation failed" in str(exc_info.value)


def test_qr_code_buffer_position():
    """Test that buffer is positioned at start after generation."""
    data = "https://test.com"
    
    qr_buffer = generate_qr_code(data)
    
    # Buffer should be at position 0 for immediate use
    assert qr_buffer.tell() == 0


def test_multiple_qr_generations():
    """Test generating multiple QR codes in sequence."""
    urls = [
        "https://example1.com",
        "https://example2.com",
        "https://example3.com",
    ]
    
    buffers = [generate_qr_code(url) for url in urls]
    
    # All should be valid
    assert len(buffers) == 3
    for buf in buffers:
        assert isinstance(buf, io.BytesIO)
        buf.seek(0)
        assert len(buf.read()) > 0


def test_webapp_qr_different_masters():
    """Test QR codes for different masters are different."""
    bot_username = "test_bot"
    
    qr1 = generate_webapp_qr(bot_username, referral_code="CODE001")
    qr2 = generate_webapp_qr(bot_username, referral_code="CODE002")
    
    # Buffers should contain different data
    qr1.seek(0)
    qr2.seek(0)
    content1 = qr1.read()
    content2 = qr2.read()
    
    assert content1 != content2, "QR codes for different masters should be different"
