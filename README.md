# sectors-daily-brief

Brief pasar saham IDX harian otomatis — mengambil data IHSG, top gainers/losers, dan performa sektor dari Sectors API, lalu mengirim ringkasan ke **WhatsApp (via Fonnte)** dan/atau **Telegram** setiap pagi hari bursa tanpa campur tangan manual.

Disiapkan untuk **Sectors Hackathon 2026, Track 02 — Automation & Workflows**.

## 🚀 Fitur

- **Fully Autonomous**: Dijalankan secara otomatis melalui cron job di GitHub Actions setiap hari Senin–Jumat pukul 06:30 WIB.
- **Sectors API Integration**: Mengambil data komprehensif pasar saham Indonesia (IHSG, top changes, total market cap).
- **Multi-Channel Delivery**: Mendukung pengiriman ke **WhatsApp** (Fonnte API) dan **Telegram** (bisa salah satu atau keduanya sekaligus).
- **AI Summarization**: Opsional merangkum data menjadi narasi Bahasa Indonesia yang mudah dipahami menggunakan Anthropic (Claude 3.5 Sonnet).
- **Robustness**: Dilengkapi dengan *retry mechanism* (menggunakan `tenacity`) untuk menangani kegagalan API, serta *fallback system* jika AI gagal agar brief tetap terkirim.

## 🛠️ Tech Stack

- **Language**: Python 3.11+
- **APIs**: Sectors API, Fonnte API (WhatsApp), Telegram Bot API, Anthropic API
- **Automation**: GitHub Actions
- **Libraries**: `requests`, `anthropic`, `tenacity`, `python-dotenv`, `pytest`

## ⚙️ Cara Menjalankan Secara Lokal

1. Clone repositori ini.
2. Buat file `.env` berdasarkan `.env.example` dan isi token serta API key Anda:
   ```env
   SECTORS_API_KEY=your_sectors_api_key
   FONNTE_TOKEN=your_fonnte_token
   WHATSAPP_TARGET=0812xxxxxxxx
   # Opsional:
   TELEGRAM_BOT_TOKEN=...
   TELEGRAM_CHAT_ID=...
   ANTHROPIC_API_KEY=...
   ```
3. Install dependensi:
   ```bash
   pip install -r requirements.txt
   ```
4. Jalankan script utama:
   ```bash
   python src/main.py
   ```

## 🔄 Konfigurasi GitHub Actions

Untuk deploy otomatisasi ke GitHub Actions:
1. Masukkan API keys sebagai **Repository Secrets** di GitHub (`Settings` > `Secrets and variables` > `Actions`):
   - `SECTORS_API_KEY` (Wajib)
   - `FONNTE_TOKEN` (Untuk WhatsApp)
   - `WHATSAPP_TARGET` (Nomor tujuan WhatsApp)
   - `TELEGRAM_BOT_TOKEN` (Untuk Telegram)
   - `TELEGRAM_CHAT_ID` (ID Telegram)
   - `ANTHROPIC_API_KEY` (Opsional untuk AI Claude)
2. Workflow akan otomatis berjalan setiap pukul 23:30 UTC (06:30 WIB) dari Senin hingga Jumat.
3. Anda juga dapat menjalankan workflow secara manual via tab **Actions** > **Daily Market Brief** > **Run workflow**.

## 🧪 Testing

Jalankan unit test menggunakan pytest:
```bash
pytest tests/
```
