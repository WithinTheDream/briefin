import os
import requests
import time
import logging
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

def update_supabase_preferences(chat_id, preferences):
    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.warning("Supabase credentials not found. Cannot save preferences.")
        return False
    try:
        # First ensure user exists in subscribers
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates"
        }
        payload = {
            "jid": str(chat_id),
            "phone": "telegram",
            "is_active": True,
            "preferences": preferences
        }
        url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/subscribers"
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        if resp.status_code in (200, 201, 204):
            return True
        else:
            logger.error(f"Supabase error: {resp.text}")
            return False
    except Exception as e:
        logger.error(f"Exception updating preferences: {e}")
        return False

WEB_URL = os.getenv("BRIEFIN_WEB_URL", "https://withinthedream.github.io/briefin-web")

def send_message(chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    requests.post(url, json=payload)

def handle_updates(updates):
    for update in updates:
        if "message" in update:
            msg = update["message"]
            chat_id = msg["chat"]["id"]
            text = msg.get("text", "").strip()
            
            if text in ["/start", "/help", "!help", "!menu"]:
                welcome_text = (
                    "📊 *Selamat Datang di Briefin • IDX Market Assistant*\n\n"
                    "Dapatkan update analisis harian pasar bursa Indonesia setiap pagi hari bursa (06:30 WIB) langsung ke Telegram & WhatsApp.\n\n"
                    "*Perintah yang tersedia:*\n"
                    "• `/topik` - Atur topik pasar harian kamu\n"
                    "• `/info` - Cek status langganan & informasi bot\n"
                    "• `/web` - Buka portal web & Today's Brief\n\n"
                    f"🌐 *Kunjungi Website & Live Brief:*\n"
                    f"[{WEB_URL}]({WEB_URL})\n"
                    f"Lihat ringkasan 9 topik & infografis di [{WEB_URL}/today.html]({WEB_URL}/today.html)"
                )
                keyboard = {
                    "inline_keyboard": [
                        [
                            {"text": "🌐 Buka Portal Web", "url": WEB_URL},
                            {"text": "📊 Today's Brief Live", "url": f"{WEB_URL}/today.html"}
                        ],
                        [
                            {"text": "⚙️ Atur Topik", "callback_data": "cmd_topik"}
                        ]
                    ]
                }
                send_message(chat_id, welcome_text, keyboard)

            elif text in ["/web", "!web", "/portal", "!portal"]:
                web_text = (
                    "🌐 *Briefin Web Portal & Live Intelligence*\n\n"
                    f"• Beranda: [{WEB_URL}]({WEB_URL})\n"
                    f"• Today's Market Brief (9 Topik & 3 Infografis): [{WEB_URL}/today.html]({WEB_URL}/today.html)\n\n"
                    "Akses data pasar, gainers/losers harian, dan infografis HD langsung dari browsermu!"
                )
                keyboard = {
                    "inline_keyboard": [
                        [{"text": "🚀 Buka Today's Brief", "url": f"{WEB_URL}/today.html"}],
                        [{"text": "🏠 Beranda Briefin", "url": WEB_URL}]
                    ]
                }
                send_message(chat_id, web_text, keyboard)

            elif text in ["/info", "!info"]:
                info_text = (
                    "ℹ️ *Informasi Briefin Market Bot*\n\n"
                    "Briefin menyajikan intelijen pasar saham BEI secara otonom setiap pagi sebelum jam bursa buka.\n\n"
                    f"🌐 *Web Portal*: [{WEB_URL}]({WEB_URL})\n"
                    f"📈 *Today's Brief*: [{WEB_URL}/today.html]({WEB_URL}/today.html)\n\n"
                    "Ketik `/topik` untuk menyesuaikan topik yang ingin kamu terima!"
                )
                send_message(chat_id, info_text)

            elif text == "/topik":
                keyboard = {
                    "inline_keyboard": [
                        [{"text": "IHSG", "callback_data": "pref_ihsg"}, {"text": "Top Gainers", "callback_data": "pref_gainers"}],
                        [{"text": "Top Losers", "callback_data": "pref_losers"}, {"text": "Berita & Tips", "callback_data": "pref_berita"}],
                        [{"text": "✅ Simpan Semua", "callback_data": "pref_all"}],
                        [{"text": "🌐 Baca Semua 9 Topik di Web", "url": f"{WEB_URL}/today.html"}]
                    ]
                }
                send_message(chat_id, "Pilih topik harianmu dengan menekan tombol di bawah ini (Pilih satu per satu atau Simpan Semua):", keyboard)
        
        elif "callback_query" in update:
            query = update["callback_query"]
            chat_id = query["message"]["chat"]["id"]
            data = query["data"]
            
            if data == "cmd_topik":
                keyboard = {
                    "inline_keyboard": [
                        [{"text": "IHSG", "callback_data": "pref_ihsg"}, {"text": "Top Gainers", "callback_data": "pref_gainers"}],
                        [{"text": "Top Losers", "callback_data": "pref_losers"}, {"text": "Berita & Tips", "callback_data": "pref_berita"}],
                        [{"text": "✅ Simpan Semua", "callback_data": "pref_all"}],
                        [{"text": "🌐 Baca Semua 9 Topik di Web", "url": f"{WEB_URL}/today.html"}]
                    ]
                }
                send_message(chat_id, "Pilih topik harianmu dengan menekan tombol di bawah ini:", keyboard)
                requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery?callback_query_id={query['id']}")
            elif data.startswith("pref_"):
                topic = data.split("_")[1]
                if topic == "all":
                    prefs = ["ihsg", "gainers", "losers", "berita"]
                    msg_text = "Semua topik berhasil dipilih."
                else:
                    prefs = ["ihsg", topic] if topic != "ihsg" else ["ihsg"]
                    msg_text = f"Topik disetel ke IHSG & {topic}."
                
                if update_supabase_preferences(chat_id, prefs):
                    send_message(chat_id, f"✅ Preferensi berhasil disimpan! {msg_text}\n\n🌐 Cek ulasan lengkap di [{WEB_URL}/today.html]({WEB_URL}/today.html)")
                else:
                    send_message(chat_id, "❌ Gagal menyimpan preferensi ke database.")
                
                # Answer callback
                requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery?callback_query_id={query['id']}")

def main():
    if not BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is missing!")
        return

    logger.info("Starting Telegram Bot Polling...")
    offset = None
    while True:
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
            params = {"timeout": 100, "offset": offset}
            resp = requests.get(url, params=params, timeout=110)
            if resp.status_code == 200:
                data = resp.json()
                updates = data.get("result", [])
                if updates:
                    handle_updates(updates)
                    offset = updates[-1]["update_id"] + 1
            else:
                logger.error(f"Telegram API Error: {resp.text}")
                time.sleep(5)
        except Exception as e:
            logger.error(f"Polling error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
