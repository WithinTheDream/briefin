import os
import requests
import logging
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

class TelegramError(Exception):
    pass

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((requests.RequestException, TelegramError)),
    reraise=True
)
def send_telegram_message(message_text: str):
    """
    Sends a message to the configured Telegram chat.
    Uses Markdown parsing mode.
    """
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if not bot_token or not chat_id:
        logger.error("Telegram credentials missing (TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID).")
        raise ValueError("Missing Telegram credentials.")
        
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message_text,
        "parse_mode": "Markdown"
    }
    
    logger.info(f"Sending message to Telegram chat {chat_id}...")
    response = requests.post(url, json=payload, timeout=10)
    
    if response.status_code != 200:
        logger.error(f"Telegram API Error: {response.status_code} - {response.text}")
        raise TelegramError(f"Failed to send message: {response.text}")
        
    logger.info("Message successfully sent to Telegram.")
    return response.json()
