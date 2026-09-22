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

def upload_image_to_host(image_path: str) -> str:
    """
    Uploads the image to Catbox to obtain a direct, permanent public URL.
    Fonnte requires a direct public URL to reliably send media to WhatsApp.
    Returns None on failure.
    """
    try:
        with open(image_path, "rb") as f:
            resp = requests.post(
                "https://catbox.moe/user/api.php",
                data={"reqtype": "fileupload"},
                files={"fileToUpload": ("market_card.png", f, "image/png")},
                timeout=20
            )
            if resp.status_code == 200 and resp.text.startswith("http"):
                public_url = resp.text.strip()
                logger.info(f"Successfully uploaded card to public URL: {public_url}")
                return public_url
            logger.warning(f"Failed uploading image to Catbox: {resp.status_code} - {resp.text}")
    except Exception as e:
        logger.warning(f"Exception during image upload to Catbox: {e}")
    return None

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((requests.RequestException, WhatsAppError)),
    reraise=True
)
def send_whatsapp_message(message_text: str, target: str = None, image_path: str = None) -> dict:
    """
    Sends a WhatsApp message via Fonnte API, with optional image attachment.
    
    :param message_text: Text message to send (used as caption if image is attached).
    :param target: Optional destination phone number or group ID. 
                   If not provided, uses WHATSAPP_TARGET from env.
    :param image_path: Optional path to an image file to attach.
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
    
    if image_path and os.path.exists(image_path):
        # 1. First attempt: upload to public host so Fonnte can download via 'url'
        public_url = upload_image_to_host(image_path)
        if public_url:
            payload["url"] = public_url
            payload["filename"] = "market_card.png"
            logger.info(f"Sending image via public URL with caption to WhatsApp target {whatsapp_target} via Fonnte...")
            response = requests.post(FONNTE_API_URL, headers=headers, data=payload, timeout=20)
        else:
            # 2. Fallback: local file upload with explicit filename tuple
            logger.info(f"Sending local image file to WhatsApp target {whatsapp_target} via Fonnte...")
            with open(image_path, "rb") as f:
                files = {"file": ("market_card.png", f, "image/png")}
                payload["filename"] = "market_card.png"
                response = requests.post(FONNTE_API_URL, headers=headers, data=payload, files=files, timeout=30)
    else:
        logger.info(f"Sending message to WhatsApp target {whatsapp_target} via Fonnte...")
        response = requests.post(FONNTE_API_URL, headers=headers, data=payload, timeout=15)
    
    logger.info(f"Fonnte response [{response.status_code}]: {response.text}")
    
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
