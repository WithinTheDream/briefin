import os
import sys
import json
import time
import logging
import subprocess
import requests
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("telegram_bot")

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
WEB_URL = os.getenv("BRIEFIN_WEB_URL", "https://withinthedream.github.io/briefin-web")

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SUBSCRIBERS_FILE = os.path.join(PROJECT_ROOT, "wa-gateway", "subscribers.json")
MAIN_PY_PATH = os.path.join(PROJECT_ROOT, "src", "main.py")

DEFAULT_PREFERENCES = ["ihsg", "gainers", "losers", "sektor", "asing", "makro", "ipo", "watchlist", "berita"]
TOPIC_NAMES = {
    "1": "ihsg",
    "2": "gainers",
    "3": "losers",
    "4": "sektor",
    "5": "asing",
    "6": "makro",
    "7": "ipo",
    "8": "watchlist",
    "9": "berita"
}

CARD_NAMES = {
    "1": "Versi 1 (Standard Movers)",
    "2": "Versi 2 (Sector & Macro Radar)",
    "3": "Versi 3 (Executive All-in-One)"
}

# --- Local & Supabase Persistence Helpers (Aligned with wa-gateway/db.js) ---

def read_local_subscribers():
    if not os.path.exists(SUBSCRIBERS_FILE):
        return []
    try:
        with open(SUBSCRIBERS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception as e:
        logger.error(f"Error reading {SUBSCRIBERS_FILE}: {e}")
        return []

def save_local_subscribers(subs_list):
    try:
        os.makedirs(os.path.dirname(SUBSCRIBERS_FILE), exist_ok=True)
        # Deduplicate by jid
        seen = {}
        for s in subs_list:
            if isinstance(s, dict) and s.get("jid"):
                jid = str(s["jid"])
                if "card_style" not in s:
                    s["card_style"] = "1"
                seen[jid] = s
        with open(SUBSCRIBERS_FILE, "w", encoding="utf-8") as f:
            json.dump(list(seen.values()), f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error saving {SUBSCRIBERS_FILE}: {e}")
        return False

def get_tg_jid(chat_id):
    return f"{chat_id}@tg"

def get_subscriber(chat_id):
    jid = get_tg_jid(chat_id)
    subs = read_local_subscribers()
    for s in subs:
        if str(s.get("jid")) in (jid, str(chat_id)):
            return s
    return None

def is_subscribed(chat_id):
    sub = get_subscriber(chat_id)
    return sub is not None

def add_subscriber(chat_id, username=None):
    jid = get_tg_jid(chat_id)
    subs = read_local_subscribers()
    existing = False
    for s in subs:
        if str(s.get("jid")) in (jid, str(chat_id)):
            existing = True
            break
    if not existing:
        subs.append({
            "jid": jid,
            "phone": username or "telegram",
            "preferences": ["ihsg", "gainers", "losers", "berita"],
            "card_style": "1"
        })
        save_local_subscribers(subs)

    # Sync to Supabase
    if SUPABASE_URL and SUPABASE_KEY:
        try:
            headers = {
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "resolution=merge-duplicates"
            }
            payload = {
                "jid": jid,
                "phone": username or f"tg:{chat_id}",
                "is_active": True
            }
            url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/subscribers"
            requests.post(url, headers=headers, json=payload, timeout=5)
        except Exception as e:
            logger.warning(f"Failed to upsert subscriber to Supabase: {e}")
    return True

def remove_subscriber(chat_id):
    jid = get_tg_jid(chat_id)
    subs = read_local_subscribers()
    updated = [s for s in subs if str(s.get("jid")) not in (jid, str(chat_id))]
    save_local_subscribers(updated)

    if SUPABASE_URL and SUPABASE_KEY:
        try:
            headers = {
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json"
            }
            url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/subscribers?jid=eq.{jid}"
            requests.patch(url, headers=headers, json={"is_active": False}, timeout=5)
        except Exception as e:
            logger.warning(f"Failed to deactivate subscriber in Supabase: {e}")
    return True

def update_preferences(chat_id, preferences):
    jid = get_tg_jid(chat_id)
    subs = read_local_subscribers()
    found = False
    for s in subs:
        if str(s.get("jid")) in (jid, str(chat_id)):
            s["preferences"] = preferences
            found = True
            break
    if not found:
        subs.append({
            "jid": jid,
            "phone": "telegram",
            "preferences": preferences,
            "card_style": "1"
        })
    save_local_subscribers(subs)

    if SUPABASE_URL and SUPABASE_KEY:
        try:
            headers = {
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json"
            }
            url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/subscribers?jid=eq.{jid}"
            requests.patch(url, headers=headers, json={"preferences": preferences}, timeout=5)
        except Exception as e:
            logger.warning(f"Failed to sync preferences to Supabase: {e}")
    return True

def update_card_style(chat_id, card_style):
    jid = get_tg_jid(chat_id)
    subs = read_local_subscribers()
    found = False
    for s in subs:
        if str(s.get("jid")) in (jid, str(chat_id)):
            s["card_style"] = str(card_style)
            found = True
            break
    if not found:
        subs.append({
            "jid": jid,
            "phone": "telegram",
            "preferences": DEFAULT_PREFERENCES,
            "card_style": str(card_style)
        })
    save_local_subscribers(subs)
    return True

# --- Telegram API Interaction ---

def send_message(chat_id, text, reply_markup=None):
    if not BOT_TOKEN:
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        resp = requests.post(url, json=payload, timeout=15)
        if resp.status_code != 200:
            logger.error(f"Failed to send Telegram message: {resp.text}")
    except Exception as e:
        logger.error(f"Exception sending message: {e}")

def get_topics_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "1. IHSG", "callback_data": "pref_ihsg"}, {"text": "2. Top Gainers", "callback_data": "pref_gainers"}],
            [{"text": "3. Top Losers", "callback_data": "pref_losers"}, {"text": "4. Sektor IDX", "callback_data": "pref_sektor"}],
            [{"text": "5. Dana Asing", "callback_data": "pref_asing"}, {"text": "6. Komoditas", "callback_data": "pref_makro"}],
            [{"text": "7. IPO & RUPS", "callback_data": "pref_ipo"}, {"text": "8. Watchlist", "callback_data": "pref_watchlist"}],
            [{"text": "9. Berita & Tips", "callback_data": "pref_berita"}, {"text": "✅ Pilih Semua (9)", "callback_data": "pref_all"}],
            [{"text": "🌐 Baca Semua di Web", "url": f"{WEB_URL}/today.html"}]
        ]
    }

def get_card_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "🖼️ Versi 1 (Standard Movers)", "callback_data": "card_1"}],
            [{"text": "📊 Versi 2 (Sector & Macro Radar)", "callback_data": "card_2"}],
            [{"text": "💎 Versi 3 (Executive All-in-One)", "callback_data": "card_3"}],
            [{"text": "🌐 Preview 3 Kartu di Web", "url": f"{WEB_URL}#gaya-kartu"}]
        ]
    }

def trigger_manual_brief(chat_id):
    sub = get_subscriber(chat_id)
    card_style = sub.get("card_style", "1") if sub else "1"
    
    send_message(
        chat_id,
        "⏳ *Sedang menyiapkan Briefin harian untukmu...*\n_Mohon tunggu sebentar, data pasar & kartu infografis sedang diracik..._"
    )
    
    tg_target = f"{chat_id}@tg"
    py_bin = sys.executable or "python3"
    cmd = [py_bin, MAIN_PY_PATH, "--target", tg_target, "--card", str(card_style)]
    
    logger.info(f"Triggering brief for Telegram: {' '.join(cmd)}")
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=PROJECT_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
    except Exception as e:
        logger.error(f"Failed to launch main.py subprocess: {e}")
        send_message(chat_id, "⚠️ Gagal menghasilkan brief. Silakan coba lagi beberapa saat lagi.")

# --- Dispatch Message Handlers ---

def handle_text_message(chat_id, raw_text, username=None):
    text = raw_text.strip().lower()
    registered = is_subscribed(chat_id)

    # 1. DAFTAR / START / SUBSCRIBE
    if text in ["/start", "!daftar", "daftar", "/daftar", "!regist", "regist", "!subscribe", "subscribe"]:
        if not registered:
            add_subscriber(chat_id, username)
            logger.info(f"[TG-BOT] ➕ Subscriber baru terdaftar: {chat_id}")
        
        welcome_text = (
            "📈 *Selamat datang di Briefin! • IDX Market Assistant*\n\n"
            "Akun Telegram kamu berhasil terdaftar. Kamu akan otomatis menerima analisis harian pasar saham IDX (IHSG, top movers, market cap) & kartu infografis setiap pagi hari bursa (Senin–Jumat pukul 06:30 WIB).\n\n"
            "• Ketik */briefin* untuk kirim ulasan hari ini sekarang\n"
            "• Ketik */topik* untuk atur preferensi 9 topik pasar\n"
            "• Ketik */kartu* untuk pilih desain infografis\n"
            "• Ketik */web* untuk link portal web & live brief\n"
            "• Ketik */info* untuk cek status langganan\n"
            "• Ketik */batal* untuk berhenti berlangganan\n\n"
            f"🌐 *Portal Web & Today's Brief:*\n[{WEB_URL}/today.html]({WEB_URL}/today.html)"
        )
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "⚡ Kirim Briefin Sekarang", "callback_data": "cmd_briefin"},
                    {"text": "⚙️ Atur Topik", "callback_data": "cmd_topik"}
                ],
                [
                    {"text": "🖼️ Pilih Gaya Kartu", "callback_data": "cmd_kartu"},
                    {"text": "🌐 Today's Brief Live", "url": f"{WEB_URL}/today.html"}
                ]
            ]
        }
        send_message(chat_id, welcome_text, keyboard)

    # 2. BATAL / STOP / UNSUBSCRIBE
    elif text in ["/batal", "!batal", "batal", "/stop", "!stop", "!unsub", "unsub", "!unsubscribe"]:
        if registered:
            remove_subscriber(chat_id)
            logger.info(f"[TG-BOT] ➖ Subscriber berhenti: {chat_id}")
        
        bye_text = (
            "👋 *Berhenti Berlangganan*\n\n"
            "Kamu telah berhenti berlangganan Briefin. Kamu tidak akan menerima brief harian otomatis lagi.\n\n"
            "Ketik */daftar* atau *daftar* kapan saja jika ingin bergabung kembali!\n"
            f"Kamu juga tetap bisa membaca ulasan pasar harian di:\n[{WEB_URL}/today.html]({WEB_URL}/today.html)"
        )
        send_message(chat_id, bye_text)

    # 3. BRIEFIN (Instant Manual Trigger)
    elif text in ["/briefin", "!briefin", "briefin"]:
        if not registered:
            add_subscriber(chat_id, username)
        trigger_manual_brief(chat_id)

    # 4. KARTU MENU & SET
    elif text in ["/kartu", "!kartu", "kartu", "/card", "!card", "card"]:
        menu_card = (
            "🖼️ *Pilihan Desain Infografis Briefin:*\n\n"
            "*1. Versi 1 (Standard)*: IHSG Composite Pulse + Top 5 Gainers & Losers\n"
            "*2. Versi 2 (Sector & Macro)*: IDX Sector Heatmap + Global Macro & Technical Watchlist\n"
            "*3. Versi 3 (Executive All-in-One)*: Dashboard Lengkap (IHSG, Gainers/Losers, Sektor, & Watchlist)\n\n"
            "Pilih tombol di bawah atau ketik */kartu 1*, */kartu 2*, atau */kartu 3*!\n\n"
            f"🌐 *Lihat perbandingan preview 3 kartu di web:*\n[{WEB_URL}#gaya-kartu]({WEB_URL}#gaya-kartu)"
        )
        send_message(chat_id, menu_card, get_card_keyboard())

    elif text.startswith("/kartu ") or text.startswith("!kartu ") or text.startswith("kartu ") or \
         text.startswith("/card ") or text.startswith("!card ") or text.startswith("card "):
        import re
        arg = re.sub(r"^(!|/)?(kartu|card)\s+", "", text).strip()
        if arg not in ["1", "2", "3"]:
            send_message(chat_id, "❌ Pilihan kartu tidak valid. Pilih angka 1, 2, atau 3. Contoh: `/kartu 3`")
        else:
            update_card_style(chat_id, arg)
            card_title = CARD_NAMES.get(arg, f"Versi {arg}")
            send_message(
                chat_id,
                f"✅ Gaya kartu berhasil diubah ke: *{card_title}*!\nKetik */briefin* untuk melihat hasilnya sekarang.\n\n🌐 Cek Today's Brief di web: [{WEB_URL}/today.html]({WEB_URL}/today.html)"
            )

    # 5. TOPIK MENU & SET
    elif text in ["/topik", "!topik", "topik", "/topic", "!topic", "topic"]:
        menu_topik = (
            "📝 *Pengaturan 9 Topik Briefin:*\n\n"
            "Pilih topik melalui tombol di bawah, atau balas angka topik (pisahkan dengan koma):\n"
            "1. *IHSG* (Pergerakan & Sentimen Indeks)\n"
            "2. *Top Gainers* (Saham Pendorong Pasar)\n"
            "3. *Top Losers* (Saham Terkoreksi)\n"
            "4. *Performa Sektor* (Sektor Penggerak Reli IDX)\n"
            "5. *Arus Dana Asing* (Net Foreign Flow)\n"
            "6. *Komoditas & Makro* (Minyak, Emas, CPO, USD/IDR)\n"
            "7. *IPO & Aksi Korporasi* (RUPS, Dividen, e-IPO)\n"
            "8. *Watchlist Saham* (2-3 Rekomendasi Teknikal)\n"
            "9. *Tips & Strategi* (Money Management)\n\n"
            "Contoh ketik: `/topik 1,4,8` untuk memilih IHSG, Sektor, dan Watchlist.\n"
            "Ketik `/topik all` untuk memilih semua topik.\n\n"
            f"🌐 *Baca semua 9 topik lengkap di web:*\n[{WEB_URL}/today.html]({WEB_URL}/today.html)"
        )
        send_message(chat_id, menu_topik, get_topics_keyboard())

    elif text.startswith("/topik ") or text.startswith("!topik ") or text.startswith("topik ") or \
         text.startswith("/topic ") or text.startswith("!topic ") or text.startswith("topic "):
        import re
        arg = re.sub(r"^(!|/)?(topik|topic)\s+", "", text).strip()
        if not registered:
            add_subscriber(chat_id, username)
        
        if arg in ["all", "semua"]:
            update_preferences(chat_id, DEFAULT_PREFERENCES)
            send_message(
                chat_id,
                f"✅ Preferensi disimpan! Kamu akan menerima seluruh 9 topik pasar.\nKetik */briefin* untuk melihat hasilnya sekarang.\n\n🌐 Cek live web: [{WEB_URL}/today.html]({WEB_URL}/today.html)"
            )
        else:
            raw_choices = re.split(r"[,;\s]+", arg)
            choices = [TOPIC_NAMES[c] for c in raw_choices if c in TOPIC_NAMES]
            if not choices:
                send_message(chat_id, "❌ Format salah. Contoh: `/topik 1,4,8` atau `/topik all`")
            else:
                unique_prefs = list(dict.fromkeys(choices))
                update_preferences(chat_id, unique_prefs)
                send_message(
                    chat_id,
                    f"✅ Preferensi topik berhasil disimpan: *{', '.join(unique_prefs)}*!\nKetik */briefin* untuk melihat hasilnya sekarang.\n\n🌐 Baca selengkapnya di web: [{WEB_URL}/today.html]({WEB_URL}/today.html)"
                )

    # 6. WEB / PORTAL
    elif text in ["/web", "!web", "web", "/portal", "!portal", "portal", "website"]:
        web_text = (
            "🌐 *Briefin Web Portal & Live Intelligence*\n\n"
            f"• *Beranda & Pusat Info:* \n[{WEB_URL}]({WEB_URL})\n\n"
            f"• *Today's Market Brief (9 Topik & 3 Infografis):* \n[{WEB_URL}/today.html]({WEB_URL}/today.html)\n\n"
            "Akses ringkasan IHSG, top movers, dan unduh infografis bursa resolusi tinggi langsung di browsermu!"
        )
        keyboard = {
            "inline_keyboard": [
                [{"text": "🚀 Buka Today's Brief", "url": f"{WEB_URL}/today.html"}],
                [{"text": "🏠 Beranda Briefin", "url": WEB_URL}]
            ]
        }
        send_message(chat_id, web_text, keyboard)

    # 7. INFO / STATUS / MENU / HELP
    elif text in ["/info", "!info", "info", "/help", "!help", "help", "/menu", "!menu", "menu"]:
        status_text = "✅ Terdaftar (Aktif)" if registered else "❌ Belum Terdaftar"
        sub = get_subscriber(chat_id)
        cur_prefs = ", ".join(sub.get("preferences", [])) if sub and sub.get("preferences") else "Semua (Default)"
        cur_card = sub.get("card_style", "1") if sub else "1"

        info_text = (
            f"📊 *Briefin • Market Assistant*\n\n"
            f"Status: *{status_text}*\n"
            f"Topik Aktif: *{cur_prefs}*\n"
            f"Gaya Kartu: *Versi {cur_card}*\n\n"
            f"*Perintah yang tersedia:*\n"
            f"• */briefin* - ⚡ Kirim market brief hari ini sekarang juga\n"
            f"• */topik* - Atur preferensi 9 topik pasar\n"
            f"• */kartu* - Pilih desain visual infografis (1, 2, atau 3)\n"
            f"• */web* - Link portal web & Today's Brief live\n"
            f"• */daftar* - Berlangganan otomatis pagi hari (06:30 WIB)\n"
            f"• */info* - Cek status akun kamu\n"
            f"• */batal* - Berhenti berlangganan\n\n"
            f"🌐 *Portal Web:* [{WEB_URL}/today.html]({WEB_URL}/today.html)"
        )
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "⚡ Kirim Briefin", "callback_data": "cmd_briefin"},
                    {"text": "⚙️ Atur Topik", "callback_data": "cmd_topik"}
                ],
                [
                    {"text": "🖼️ Pilih Kartu", "callback_data": "cmd_kartu"},
                    {"text": "🌐 Today's Brief Web", "url": f"{WEB_URL}/today.html"}
                ]
            ]
        }
        send_message(chat_id, info_text, keyboard)

def handle_updates(updates):
    for update in updates:
        # Handle regular messages
        if "message" in update:
            msg = update["message"]
            chat_id = msg["chat"]["id"]
            user_info = msg.get("from", {})
            username = user_info.get("username") or user_info.get("first_name")
            text = msg.get("text", "").strip()
            if text:
                logger.info(f"[TG-BOT] 📩 Pesan masuk [{chat_id}] ({username}): '{text}'")
                try:
                    handle_text_message(chat_id, text, username=username)
                except Exception as e:
                    logger.error(f"[TG-BOT] Error handling message: {e}")

        # Handle button callbacks
        elif "callback_query" in update:
            query = update["callback_query"]
            chat_id = query["message"]["chat"]["id"]
            data = query.get("data", "")
            query_id = query.get("id")

            try:
                # Answer callback quickly
                requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery?callback_query_id={query_id}")

                if data == "cmd_briefin":
                    if not is_subscribed(chat_id):
                        add_subscriber(chat_id)
                    trigger_manual_brief(chat_id)

                elif data == "cmd_topik":
                    handle_text_message(chat_id, "/topik")

                elif data == "cmd_kartu":
                    handle_text_message(chat_id, "/kartu")

                elif data.startswith("card_"):
                    card_num = data.replace("card_", "")
                    handle_text_message(chat_id, f"/kartu {card_num}")

                elif data.startswith("pref_"):
                    topic_key = data.replace("pref_", "")
                    if topic_key == "all":
                        handle_text_message(chat_id, "/topik all")
                    else:
                        sub = get_subscriber(chat_id)
                        cur_prefs = list(sub.get("preferences", [])) if sub and sub.get("preferences") else ["ihsg"]
                        if topic_key in cur_prefs:
                            cur_prefs.remove(topic_key)
                        else:
                            cur_prefs.append(topic_key)
                        if not cur_prefs:
                            cur_prefs = ["ihsg"]
                        update_preferences(chat_id, cur_prefs)
                        send_message(
                            chat_id,
                            f"✅ Preferensi topik diupdate: *{', '.join(cur_prefs)}*!\nKetik */briefin* untuk melihat hasilnya.\n\n🌐 Cek di web: [{WEB_URL}/today.html]({WEB_URL}/today.html)"
                        )
            except Exception as e:
                logger.error(f"[TG-BOT] Error handling callback: {e}")

def main():
    if not BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is missing from environment variables!")
        return

    logger.info("Starting Briefin Telegram Bot Polling (Aligned with WhatsApp Gateway)...")
    offset = None
    while True:
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
            params = {"timeout": 60, "offset": offset}
            resp = requests.get(url, params=params, timeout=70)
            if resp.status_code == 200:
                data = resp.json()
                updates = data.get("result", [])
                if updates:
                    handle_updates(updates)
                    offset = updates[-1]["update_id"] + 1
            else:
                logger.error(f"Telegram API Error: {resp.text}")
                time.sleep(3)
        except Exception as e:
            logger.error(f"Telegram polling error: {e}")
            time.sleep(3)

if __name__ == "__main__":
    main()
