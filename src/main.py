import os
import sys
import logging
from dotenv import load_dotenv

from fetch_sectors import get_idx_total, get_ihsg, get_top_changes
from format_brief import normalize_data, format_data_for_ai, generate_fallback_message
from summarize_ai import summarize_market_data
from generate_card import generate_market_card
from send_telegram import send_telegram_message
from send_whatsapp import send_whatsapp_message

# Ensure logs directory exists if running locally (ignored by git)
os.makedirs("logs", exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/daily_brief.log", encoding="utf-8")
    ]
)

logger = logging.getLogger(__name__)

import json
import argparse
import time

def dispatch_brief(message_dict: dict, image_path: str = None, target: str = None):
    """
    Sends the brief to configured channels (Telegram and/or WhatsApp via Gateway / Fonnte) with optional image card.
    If target is provided, sends only to that specific target.
    """
    telegram_ready = bool(os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"))
    whatsapp_ready = bool(os.getenv("WA_GATEWAY_URL") or (os.getenv("FONNTE_TOKEN") and os.getenv("WHATSAPP_TARGET")))
    
    if not telegram_ready and not whatsapp_ready:
        raise ValueError("No notification channels configured! Provide Telegram or WhatsApp credentials.")
        
    delivery_success = False
    
    # If target is specified and looks like a WhatsApp number/JID
    is_wa_target = target and (target.endswith("@s.whatsapp.net") or target.endswith("@g.us") or target.endswith("@lid") or target.replace("+", "").isdigit())
    is_tg_target = target and not is_wa_target

    if telegram_ready and (not target or is_tg_target):
        try:
            logger.info("Sending brief to Telegram...")
            send_telegram_message(message_dict, image_path=image_path)
            delivery_success = True
        except Exception as e:
            logger.error(f"Failed to send to Telegram: {e}")
            
    if whatsapp_ready and (not target or is_wa_target):
        try:
            channel = "Self-Hosted Gateway" if os.getenv("WA_GATEWAY_URL") else "Fonnte"
            logger.info(f"Sending brief to WhatsApp ({target or 'All Subscribers'}) via {channel}...")
            send_whatsapp_message(message_dict, target=target, image_path=image_path)
            delivery_success = True
        except Exception as e:
            logger.error(f"Failed to send to WhatsApp: {e}")
            
    if not delivery_success:
        raise RuntimeError("Failed to deliver message to all configured channels.")

def dispatch_error_alert(error_msg: str):
    """
    Sends failure alerts to configured channels if possible.
    """
    telegram_ready = bool(os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"))
    whatsapp_ready = bool(os.getenv("WA_GATEWAY_URL") or (os.getenv("FONNTE_TOKEN") and os.getenv("WHATSAPP_TARGET")))
    
    err_dict = {"ihsg": error_msg}
    if telegram_ready:
        try:
            send_telegram_message(err_dict)
        except Exception:
            pass
            
    if whatsapp_ready:
        try:
            send_whatsapp_message(err_dict)
        except Exception:
            pass

def save_daily_brief_to_supabase(normalized: dict, message_dict: dict):
    """
    Saves the latest daily brief to Supabase table `daily_briefs`.
    Allows the frontend (briefin-web) to load and render Today's Market Brief dynamically.
    """
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    if not supabase_url or not supabase_key:
        logger.info("Supabase not configured for daily brief storage. Skipping database sync.")
        return False

    try:
        import requests
        from datetime import datetime
        
        today_date = datetime.now().strftime("%Y-%m-%d")
        headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
        }
        
        payload = {
            "brief_date": today_date,
            "ihsg": normalized.get("ihsg", {}),
            "summary": message_dict,
            "normalized": normalized
        }
        
        url = f"{supabase_url.rstrip('/')}/rest/v1/daily_briefs"
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        if resp.status_code in (200, 201, 204):
            logger.info("✅ Successfully synced Today's Brief to Supabase `daily_briefs`.")
            return True
        else:
            logger.warning(f"Failed to sync brief to Supabase [{resp.status_code}]: {resp.text}")
            return False
    except Exception as err:
        logger.warning(f"Error while saving daily brief to Supabase: {err}")
        return False

CACHE_DATA_FILE = "logs/cached_normalized.json"
CACHE_SUMMARY_FILE = "logs/cached_summary.json"

def main():
    load_dotenv()
    
    parser = argparse.ArgumentParser(description="Briefin Automated Stock Brief")
    parser.add_argument("--target", type=str, default=None, help="Specific target JID or phone number (e.g. 62812... or group JID)")
    parser.add_argument("--card", type=str, default="1", help="Infographic card style (1: Standard, 2: Sector/Macro, 3: Executive)")
    parser.add_argument("--force", action="store_true", help="Force fresh API fetch without using cache")
    args = parser.parse_args()
    
    logger.info(f"Starting Briefin workflow (target: {args.target}, card: {args.card})...")
    
    try:
        normalized = None
        message_dict = None
        card_output = f"logs/market_card_v{args.card}.png"
        
        # Check cache if manual trigger (--target) to save API credits & enable instant response
        now = time.time()
        use_cache = not args.force and args.target and os.path.exists(CACHE_DATA_FILE) and os.path.exists(CACHE_SUMMARY_FILE)
        
        if use_cache:
            file_age = now - os.path.getmtime(CACHE_DATA_FILE)
            if file_age < 14400:  # Cache valid for 4 hours
                try:
                    with open(CACHE_DATA_FILE, "r", encoding="utf-8") as f:
                        normalized = json.load(f)
                    with open(CACHE_SUMMARY_FILE, "r", encoding="utf-8") as f:
                        message_dict = json.load(f)
                    logger.info("⚡ Reusing cached market data & AI summary for instant briefin response.")
                except Exception as cache_err:
                    logger.warning(f"Failed to read cache: {cache_err}")
                    normalized, message_dict = None, None

        if not normalized or not message_dict:
            # Step 1: Fetch Data from Sectors API
            logger.info("Fetching fresh data from Sectors API...")
            idx_total = get_idx_total()
            ihsg = get_ihsg()
            top_changes = get_top_changes()
            
            # Step 2: Normalize Data
            normalized = normalize_data(idx_total, ihsg, top_changes)
            with open(CACHE_DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(normalized, f)
            
            # Step 3: Summarize via AI
            formatted_for_ai = format_data_for_ai(normalized)
            ai_summary = summarize_market_data(formatted_for_ai)
            
            if ai_summary:
                try:
                    clean = ai_summary.strip()
                    if clean.startswith("```json"):
                        clean = clean[7:]
                    if clean.startswith("```"):
                        clean = clean[3:]
                    if clean.endswith("```"):
                        clean = clean[:-3]
                    message_dict = json.loads(clean.strip())
                    logger.info("Successfully parsed AI summary JSON.")
                except Exception as e:
                    logger.warning(f"Failed to parse AI output as JSON: {e}. Falling back to template.")
                    message_dict = None

            if not message_dict:
                logger.warning("Using fallback template dictionary.")
                message_dict = generate_fallback_message(normalized)
                
            with open(CACHE_SUMMARY_FILE, "w", encoding="utf-8") as f:
                json.dump(message_dict, f)
        
        # Step 4: Sync to Supabase for Web Hub (Today's Brief)
        save_daily_brief_to_supabase(normalized, message_dict)

        # Step 5: Generate Market Infographic Card (using requested style)
        logger.info(f"Generating market infographic card style {args.card}...")
        image_path = generate_market_card(normalized, card_output, card_style=args.card)
        
        # Step 6: Dispatch to Telegram & WhatsApp
        dispatch_brief(message_dict, image_path=image_path, target=args.target)
        logger.info("Workflow completed successfully.")
        
    except Exception as e:
        logger.exception("A critical error occurred in the workflow.")
        error_msg = f"⚠️ *Briefin Alert*\n\nFailed to run morning brief workflow.\n\nError: `{str(e)}`"
        dispatch_error_alert(error_msg)
        sys.exit(1)

if __name__ == "__main__":
    main()
