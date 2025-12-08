"""QR code generation utilities for BeautyAssist bot."""
import io
import logging
from typing import BinaryIO

import qrcode
from qrcode.image.pil import PilImage

logger = logging.getLogger(__name__)


def generate_qr_code(data: str, box_size: int = 10, border: int = 2) -> io.BytesIO:
    """
    Generate QR code image from data.
    
    Args:
        data: String data to encode (URL, text, etc.)
        box_size: Size of each box in pixels (default: 10)
        border: Border size in boxes (default: 2)
    
    Returns:
        BytesIO object containing PNG image data
    
    Example:
        >>> qr_buffer = generate_qr_code("https://t.me/mybot/app")
        >>> # Send qr_buffer as photo to Telegram
    """
    try:
        # Create QR code instance
        qr = qrcode.QRCode(
            version=1,  # Auto-adjust size
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=box_size,
            border=border,
        )
        
        # Add data and optimize
        qr.add_data(data)
        qr.make(fit=True)
        
        # Create image
        img = qr.make_image(fill_color="black", back_color="white", image_factory=PilImage)
        
        # Save to BytesIO buffer
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        logger.info(f"Generated QR code for data length: {len(data)} chars")
        return buffer
        
    except Exception as e:
        logger.error(f"Failed to generate QR code: {e}", exc_info=True)
        raise


def generate_webapp_qr(bot_username: str, master_id: int, box_size: int = 10) -> io.BytesIO:
    """
    Generate QR code with link to master's booking WebApp.
    
    Args:
        bot_username: Telegram bot username (without @)
        master_id: Master's ID for booking
        box_size: QR code box size in pixels
    
    Returns:
        BytesIO object containing QR code PNG image
    
    Example:
        >>> qr = generate_webapp_qr("beautyassist_bot", master_id=123)
        >>> await message.answer_photo(BufferedInputFile(qr.getvalue(), filename="qr.png"))
    """
    # Construct WebApp URL
    webapp_url = f"https://t.me/{bot_username}/app?startapp=book_master_{master_id}"
    
    logger.info(f"Generating WebApp QR code for master {master_id}")
    return generate_qr_code(webapp_url, box_size=box_size, border=2)


def generate_referral_qr(bot_username: str, referral_code: str, box_size: int = 10) -> io.BytesIO:
    """
    Generate QR code with referral link.
    
    Args:
        bot_username: Telegram bot username (without @)
        referral_code: Unique referral code
        box_size: QR code box size in pixels
    
    Returns:
        BytesIO object containing QR code PNG image
    """
    referral_url = f"https://t.me/{bot_username}?start=ref_{referral_code}"
    
    logger.info(f"Generating referral QR code for code: {referral_code}")
    return generate_qr_code(referral_url, box_size=box_size, border=2)
