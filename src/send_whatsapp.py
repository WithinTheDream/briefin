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

def normalize_target_jid(target: str) -> str:
    """
    Normalizes a destination phone number or JID to standard WhatsApp JID format.
    Ensures uniform comparison between e.g. '089681560551' and '6289681560551@s.whatsapp.net'.
    Supports @s.whatsapp.net, @lid, and @g.us.
    """
    if not target:
        return ""
    clean = str(target).strip()
    if clean.endswith("@g.us") or clean.endswith("@s.whatsapp.net") or clean.endswith("@lid"):
        return clean
    digits = re.sub(r'[^0-9]', '', clean)
    if digits.startswith("0"):
        digits = "62" + digits[1:]
    elif digits.startswith("8"):
        digits = "62" + digits
    if len(digits) >= 7:
        return f"{digits}@s.whatsapp.net"
    return clean

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

class SubscriberJid(str):
    def __new__(cls, jid, preferences=None, card_style="1"):
        instance = super().__new__(cls, str(jid))
        instance.jid = str(jid)
        instance.preferences = preferences if (preferences and isinstance(preferences, list)) else DEFAULT_TOPICS
        instance.card_style = str(card_style) if card_style else "1"
        return instance

    def get(self, key, default=None):
        if key == "jid": return self.jid
        if key == "preferences": return self.preferences
        if key == "card_style": return self.card_style
        return default

    def __getitem__(self, key):
        if key == "jid": return self.jid
        if key == "preferences": return self.preferences
        if key == "card_style": return self.card_style
        return super().__getitem__(key)

def get_subscribers_from_supabase() -> list:
    """
    Fetches active subscribers directly from Supabase REST API.
    Works in both local development and cloud/GitHub Actions without wa-gateway running.
    """
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    if not supabase_url or not supabase_key:
        return []

    try:
        url = f"{supabase_url.rstrip('/')}/rest/v1/subscribers?select=jid,phone,preferences,card_style&is_active=eq.true"
        headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}"
        }
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            subs = []
            for item in data:
                jid = item.get("jid") or item.get("phone")
                if jid:
                    subs.append(SubscriberJid(jid, preferences=item.get("preferences"), card_style=item.get("card_style")))
            logger.info(f"Retrieved {len(subs)} active subscriber(s) directly from Supabase.")
            return subs
        logger.warning(f"Supabase returned status {resp.status_code}: {resp.text}")
    except Exception as err:
        logger.warning(f"Could not fetch subscribers directly from Supabase: {err}")
    return []

def get_registered_subscribers(gateway_url: str = None) -> list:
    """
    Fetches the list of active subscribers with their preferences.
    Prioritizes Supabase Cloud, with fallback to WhatsApp Gateway endpoint.
    """
    # 1. Try Supabase Cloud first
    supabase_subs = get_subscribers_from_supabase()
    if supabase_subs:
        return supabase_subs

    # 2. Fallback to local Gateway /subscribers endpoint
    if gateway_url:
        try:
            url = f"{gateway_url.rstrip('/')}/subscribers"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                raw_subs = data.get("subscribers", [])
                formatted_subs = []
                for s in raw_subs:
                    if isinstance(s, dict):
                        jid = s.get("jid") or s.get("phone")
                        if jid:
                            formatted_subs.append(SubscriberJid(jid, preferences=s.get("preferences"), card_style=s.get("card_style")))
                    elif isinstance(s, str):
                        formatted_subs.append(SubscriberJid(s, preferences=DEFAULT_TOPICS, card_style="1"))
                return formatted_subs
        except Exception as err:
            logger.warning(f"Could not fetch subscribers from gateway: {err}")
    return []

DEFAULT_TOPICS = ["ihsg", "gainers", "losers", "sektor", "asing", "makro", "ipo", "watchlist", "berita"]

def build_message_from_dict(message_dict: dict, preferences: list) -> str:
    """Constructs the final text based on user preferences with clean styling."""
    if not preferences:
        preferences = DEFAULT_TOPICS
    
    parts = ["📊 *BRIEFIN • DAILY MARKET BRIEF*"]
    
    topic_order = [
        "ihsg", "gainers", "losers", "sektor", "asing", "makro", "ipo", "watchlist", "berita"
    ]
    
    for key in topic_order:
        if key in preferences and key in message_dict and message_dict[key]:
            parts.append(str(message_dict[key]).strip())
    
    parts.append("_Automated by Briefin_")
    return "\n\n".join(parts)

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((requests.RequestException, WhatsAppError)),
    reraise=True
)
def send_whatsapp_message(message_data, target: str = None, image_path: str = None) -> dict:
    """
    Sends WhatsApp messages dynamically based on preferences.
    Supports either formatted dict (for customized topics) or raw string.
    """
    gateway_url = os.getenv("WA_GATEWAY_URL")
    fonnte_token = os.getenv("FONNTE_TOKEN")
    admin_target = os.getenv("WHATSAPP_TARGET")
    
    if not gateway_url and not fonnte_token:
        logger.error("No WhatsApp provider configured.")
        raise ValueError("Missing WhatsApp credentials.")

    # 1. Plain String Mode (e.g. Unit Tests or Direct Text)
    if isinstance(message_data, str):
        if gateway_url:
            targets_to_send = []
            if target:
                targets_to_send.append(target)
            else:
                subscribers = get_registered_subscribers(gateway_url)
                for sub in subscribers:
                    norm = normalize_target_jid(sub)
                    if norm and norm not in [normalize_target_jid(t) for t in targets_to_send]:
                        targets_to_send.append(sub)
                if admin_target:
                    norm_admin = normalize_target_jid(admin_target)
                    if norm_admin and norm_admin not in [normalize_target_jid(t) for t in targets_to_send]:
                        targets_to_send.append(admin_target)
            if not targets_to_send:
                raise ValueError("Missing WhatsApp credentials: No recipients available.")
            return _send_via_gateway(gateway_url, targets_to_send, message_data, image_path)
        else:
            targets_to_send = []
            if target:
                targets_to_send.append(target)
            else:
                subscribers = get_registered_subscribers()
                for sub in subscribers:
                    clean = sub.split('@')[0] if '@' in sub else sub
                    if clean and clean not in targets_to_send:
                        targets_to_send.append(clean)
                if admin_target and admin_target not in targets_to_send:
                    targets_to_send.append(admin_target)
            destination = ",".join(targets_to_send) if targets_to_send else admin_target
            if not destination:
                raise ValueError("Missing WhatsApp credentials: WHATSAPP_TARGET not configured.")
            return _send_via_fonnte(fonnte_token, destination, message_data, image_path)

    # 2. Dictionary Mode (Topic-Based Custom Preferences)
    registered_list = get_registered_subscribers(gateway_url)
    subscribers = []

    if target:
        norm_target = normalize_target_jid(target)
        existing = next((s for s in registered_list if normalize_target_jid(s) == norm_target), None)
        target_prefs = getattr(existing, "preferences", DEFAULT_TOPICS) if existing else DEFAULT_TOPICS
        subscribers.append(SubscriberJid(target, preferences=target_prefs))
    else:
        for s in registered_list:
            subscribers.append(s)
        if admin_target:
            norm_admin = normalize_target_jid(admin_target)
            if not any(normalize_target_jid(s) == norm_admin for s in subscribers):
                subscribers.append(SubscriberJid(admin_target, preferences=DEFAULT_TOPICS))

    if not subscribers:
        logger.error("No WhatsApp recipients found.")
        raise ValueError("Missing WhatsApp recipients.")

    grouped_messages = {}
    for sub in subscribers:
        prefs = getattr(sub, "preferences", DEFAULT_TOPICS)
        final_text = build_message_from_dict(message_data, prefs)
        grouped_messages.setdefault(final_text, []).append(str(sub))

    last_res = {"status": True}
    for msg_text, jids in grouped_messages.items():
        if gateway_url:
            logger.info(f"Dispatching grouped WA message to {len(jids)} recipient(s)...")
            last_res = _send_via_gateway(gateway_url, jids, msg_text, image_path)
        else:
            for j in jids:
                clean_phone = j.split('@')[0] if '@' in j else j
                last_res = _send_via_fonnte(fonnte_token, clean_phone, msg_text, image_path)

    return last_res

