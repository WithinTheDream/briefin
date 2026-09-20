import os
import re
import requests
import logging
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

FONNTE_API_URL = "https://api.fonnte.com/send"

class WhatsAppError(Exception):
    """Custom exception for WhatsApp / Fonnte errors."""
    pass

def format_for_whatsapp(text: str) -> str:
    """
    Converts standard Markdown formatting into WhatsApp-compatible formatting.
    E.g. changes double asterisks **bold** to single asterisk *bold*.
    """
    if not text:
        return ""
    # Replace **text** with *text*
    formatted = re.sub(r'\*\*(.*?)\*\*', r'*\1*', text)
    return formatted

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((requests.RequestException, WhatsAppError)),
    reraise=True
)
def send_whatsapp_message(message_text: str, target: str = None) -> dict:
    """
    Sends a WhatsApp message via Fonnte API.
    
    :param message_text: Text message to send.
    :param target: Optional destination phone number or group ID. 
                   If not provided, uses WHATSAPP_TARGET from env.
    :return: Response JSON from Fonnte.
    """
    fonnte_token = os.getenv("FONNTE_TOKEN")
    whatsapp_target = target or os.getenv("WHATSAPP_TARGET")
    
    if not fonnte_token or not whatsapp_target:
        logger.error("WhatsApp credentials missing (FONNTE_TOKEN or WHATSAPP_TARGET).")
        raise ValueError("Missing WhatsApp credentials.")
        
    headers = {
        "Authorization": fonnte_token.strip()
    }
    
    # Format message for WhatsApp compatibility
    wa_message = format_for_whatsapp(message_text)
    
    payload = {
        "target": whatsapp_target.strip(),
        "message": wa_message,
        "countryCode": "62"
    }
    
    logger.info(f"Sending message to WhatsApp target {whatsapp_target} via Fonnte...")
    response = requests.post(FONNTE_API_URL, headers=headers, data=payload, timeout=15)
    
    if response.status_code != 200:
        logger.error(f"Fonnte API Error: {response.status_code} - {response.text}")
        raise WhatsAppError(f"Failed to send WhatsApp message: {response.text}")
        
    try:
        data = response.json()
    except Exception:
        data = {"status": True, "raw_response": response.text}
        
    # Check if Fonnte indicated a failure in their JSON response
    if isinstance(data, dict) and data.get("status") is False:
        reason = data.get("reason", "Unknown Fonnte error")
        logger.error(f"Fonnte delivery failed: {reason}")
        raise WhatsAppError(f"Fonnte error: {reason}")
        
    logger.info("Message successfully sent to WhatsApp.")
    return data
