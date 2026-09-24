import os
import re
import requests
import logging
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

FONNTE_API_URL = "https://api.fonnte.com/send"

class WhatsAppError(Exception):
    """Custom exception for WhatsApp / Gateway / Fonnte errors."""
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
    Uploads the image to a high-speed public CDN (freeimage.host / catbox)
    to obtain a direct, public image URL required by Fonnte to deliver media to WhatsApp.
    """
    # 1. Try freeimage.host (Fast global CDN iili.io)
    try:
        with open(image_path, "rb") as f:
            resp = requests.post(
                "https://freeimage.host/api/1/upload",
                data={
                    "key": "6d207e02198a847aa98d0a2a901485a5",
                    "action": "upload",
                    "format": "json"
                },
                files={"source": ("market_card.png", f, "image/png")},
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
                timeout=20
            )
            if resp.status_code == 200:
                data = resp.json()
                img_url = data.get("image", {}).get("url")
                if img_url:
                    logger.info(f"Successfully uploaded card to freeimage.host: {img_url}")
                    return img_url
            logger.warning(f"freeimage.host error: {resp.status_code} - {resp.text}")
    except Exception as e:
        logger.warning(f"Exception during freeimage.host upload: {e}")

    # 2. Try Catbox with browser User-Agent
    try:
        with open(image_path, "rb") as f:
            resp = requests.post(
                "https://catbox.moe/user/api.php",
                data={"reqtype": "fileupload"},
                files={"fileToUpload": ("market_card.png", f, "image/png")},
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
                timeout=20
            )
            if resp.status_code == 200 and resp.text.startswith("http"):
                catbox_url = resp.text.strip()
                logger.info(f"Successfully uploaded card to Catbox: {catbox_url}")
                return catbox_url
            logger.warning(f"Catbox upload error: {resp.status_code} - {resp.text}")
    except Exception as e:
        logger.warning(f"Exception during Catbox upload: {e}")

    return None

def _send_via_gateway(gateway_url: str, target, message_text: str, image_path: str = None) -> dict:
    """
    Sends message + image to the local or self-hosted Baileys WhatsApp Gateway.
    Supports single target or list of targets, and sends HD local images without CDN dependency.
    """
    url = f"{gateway_url.rstrip('/')}/send"
    wa_message = format_for_whatsapp(message_text)
    
    if isinstance(target, list):
        if len(target) == 1:
            target_payload = str(target[0]).strip()
        else:
            target_payload = [str(t).strip() for t in target if t]
    else:
        target_payload = str(target).strip()

    payload = {
        "target": target_payload,
        "message": wa_message
    }
    if image_path and os.path.exists(image_path):
        payload["image_path"] = os.path.abspath(image_path)
        logger.info(f"Sending image + message to WhatsApp target {target_payload} via Gateway ({url})...")
    else:
        logger.info(f"Sending message to WhatsApp target {target_payload} via Gateway ({url})...")

    try:
        response = requests.post(url, json=payload, timeout=60)
    except requests.RequestException as e:
        logger.error(f"Failed to connect to WhatsApp Gateway at {url}: {e}")
        raise WhatsAppError(f"WhatsApp Gateway connection failed: {e}")

    if response.status_code != 200:
        logger.error(f"WhatsApp Gateway Error [{response.status_code}]: {response.text}")
        raise WhatsAppError(f"WhatsApp Gateway error ({response.status_code}): {response.text}")

    try:
        data = response.json()
    except Exception:
        data = {"status": True, "raw_response": response.text}

    if isinstance(data, dict) and data.get("status") is False:
        err = data.get("error", "Unknown gateway error")
        logger.error(f"WhatsApp Gateway delivery failed: {err}")
        raise WhatsAppError(f"WhatsApp Gateway error: {err}")

    logger.info("Message successfully sent via WhatsApp Gateway.")
    return data

def _send_via_fonnte(fonnte_token: str, target: str, message_text: str, image_path: str = None) -> dict:
    """
    Fallback method: Sends WhatsApp message via Fonnte API.
    """
    headers = {
        "Authorization": fonnte_token.strip()
    }
    wa_message = format_for_whatsapp(message_text)
    payload = {
        "target": target.strip(),
        "message": wa_message,
        "countryCode": "62"
    }

    if image_path and os.path.exists(image_path):
        public_url = upload_image_to_host(image_path)
        if public_url:
            payload["url"] = public_url
            payload["filename"] = "market_card.png"
            logger.info(f"Sending image via public URL to WhatsApp target {target} via Fonnte...")
            response = requests.post(FONNTE_API_URL, headers=headers, data=payload, timeout=20)
        else:
            logger.info(f"Sending local image file to WhatsApp target {target} via Fonnte...")
            with open(image_path, "rb") as f:
                files = {"file": ("market_card.png", f, "image/png")}
                payload["filename"] = "market_card.png"
                response = requests.post(FONNTE_API_URL, headers=headers, data=payload, files=files, timeout=30)
    else:
        logger.info(f"Sending message to WhatsApp target {target} via Fonnte...")
        response = requests.post(FONNTE_API_URL, headers=headers, data=payload, timeout=15)

    logger.info(f"Fonnte response [{response.status_code}]: {response.text}")

    if response.status_code != 200:
        logger.error(f"Fonnte API Error: {response.status_code} - {response.text}")
        raise WhatsAppError(f"Failed to send WhatsApp message: {response.text}")

    try:
        data = response.json()
    except Exception:
        data = {"status": True, "raw_response": response.text}

    if isinstance(data, dict) and data.get("status") is False:
        reason = data.get("reason", "Unknown Fonnte error")
        logger.error(f"Fonnte delivery failed: {reason}")
        raise WhatsAppError(f"Fonnte error: {reason}")

    logger.info("Message successfully sent to WhatsApp via Fonnte.")
    return data

def get_registered_subscribers(gateway_url: str) -> list[str]:
    """
    Fetches the list of active subscribers registered via WhatsApp Gateway.
    Returns empty list if gateway is unreachable or no subscribers exist.
    """
    try:
        url = f"{gateway_url.rstrip('/')}/subscribers"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data.get("subscribers", [])
    except Exception as err:
        logger.warning(f"Could not fetch subscribers from gateway: {err}")
    return []

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((requests.RequestException, WhatsAppError)),
    reraise=True
)
def send_whatsapp_message(message_text: str, target: str = None, image_path: str = None) -> dict:
    """
    Sends a WhatsApp message via Self-Hosted Baileys Gateway (if WA_GATEWAY_URL is set)
    or via Fonnte API (if FONNTE_TOKEN is set), with optional image attachment.
    
    If target is not specified and using Baileys Gateway, it broadcasts to all 
    registered subscribers (from GET /subscribers) plus WHATSAPP_TARGET from .env.
    
    :param message_text: Text message to send (used as caption if image is attached).
    :param target: Optional destination phone number or group ID. 
                   If not provided, broadcasts to all registered subscribers.
    :param image_path: Optional path to an image file to attach.
    :return: Response JSON from Gateway or Fonnte.
    """
    gateway_url = os.getenv("WA_GATEWAY_URL")
    fonnte_token = os.getenv("FONNTE_TOKEN")
    admin_target = os.getenv("WHATSAPP_TARGET")
    
    if not gateway_url and not fonnte_token:
        logger.error("No WhatsApp provider configured (set WA_GATEWAY_URL or FONNTE_TOKEN).")
        raise ValueError("Missing WhatsApp credentials. Provide WA_GATEWAY_URL or FONNTE_TOKEN.")
        
    if gateway_url:
        targets_to_send = []
        if target:
            targets_to_send.append(target)
        else:
            # Broadcast to all registered subscribers + default admin target
            subscribers = get_registered_subscribers(gateway_url)
            for sub in subscribers:
                if sub and sub not in targets_to_send:
                    targets_to_send.append(sub)
                    
            if admin_target and admin_target not in targets_to_send:
                targets_to_send.append(admin_target)

        if not targets_to_send:
            logger.error("No WhatsApp recipients found (no subscribers and WHATSAPP_TARGET empty).")
            raise ValueError("Missing WhatsApp credentials: No recipients available.")

        logger.info(f"Dispatching WhatsApp message to {len(targets_to_send)} recipient(s): {targets_to_send}")
        return _send_via_gateway(gateway_url, targets_to_send, message_text, image_path)
    else:
        destination = target or admin_target
        if not destination:
            raise ValueError("Missing WhatsApp credentials: WHATSAPP_TARGET not configured.")
        return _send_via_fonnte(fonnte_token, destination, message_text, image_path)
