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

def dispatch_brief(message_text: str, image_path: str = None):
    """
    Sends the brief to configured channels (Telegram and/or WhatsApp via Fonnte) with optional image card.
    """
    telegram_ready = bool(os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"))
    whatsapp_ready = bool(os.getenv("FONNTE_TOKEN") and os.getenv("WHATSAPP_TARGET"))
    
    if not telegram_ready and not whatsapp_ready:
        raise ValueError("No notification channels configured! Provide Telegram or WhatsApp (Fonnte) credentials.")
        
    delivery_success = False
    
    if telegram_ready:
        try:
            logger.info("Sending brief to Telegram...")
            send_telegram_message(message_text, image_path=image_path)
            delivery_success = True
        except Exception as e:
            logger.error(f"Failed to send to Telegram: {e}")
            
    if whatsapp_ready:
        try:
            logger.info("Sending brief to WhatsApp via Fonnte...")
            send_whatsapp_message(message_text, image_path=image_path)
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
    whatsapp_ready = bool(os.getenv("FONNTE_TOKEN") and os.getenv("WHATSAPP_TARGET"))
    
    if telegram_ready:
        try:
            send_telegram_message(error_msg)
        except Exception:
            pass
            
    if whatsapp_ready:
        try:
            send_whatsapp_message(error_msg)
        except Exception:
            pass

def main():
    # Load env vars for local development (will be ignored in GitHub Actions if not present)
    load_dotenv()
    
    logger.info("Starting Briefin workflow...")
    
    try:
        # Step 1: Fetch Data
        logger.info("Fetching data from Sectors API...")
        idx_total = get_idx_total()
        ihsg = get_ihsg()
        top_changes = get_top_changes()
        
        # Step 2: Normalize Data
        normalized = normalize_data(idx_total, ihsg, top_changes)
        
        # Step 3: Generate Market Infographic Card
        logger.info("Generating market infographic card...")
        image_path = generate_market_card(normalized, "logs/market_card.png")
        
        # Step 4: Summarize via AI
        formatted_for_ai = format_data_for_ai(normalized)
        ai_summary = summarize_market_data(formatted_for_ai)
        
        # Step 5: Formatting Message
        if ai_summary:
            logger.info("Using AI-generated summary.")
            final_message = f"📊 **BRIEFIN • DAILY MARKET BRIEF**\n\n{ai_summary.strip()}\n\n_Automated by Briefin_"
        else:
            logger.warning("AI summary failed or was not configured. Using fallback template.")
            final_message = generate_fallback_message(normalized)
            
        # Step 6: Dispatch to Telegram & WhatsApp
        dispatch_brief(final_message, image_path=image_path)
        
        logger.info("Workflow completed successfully.")
        
    except Exception as e:
        logger.exception("A critical error occurred in the workflow.")
        # Attempt to send error alert
        error_msg = f"⚠️ **Briefin Alert**\n\nFailed to run morning brief workflow.\n\nError: `{str(e)}`"
        dispatch_error_alert(error_msg)
        sys.exit(1)

if __name__ == "__main__":
    main()
