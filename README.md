# sectors-daily-brief

Brief pasar saham IDX harian otomatis — mengambil data IHSG, top gainers/losers, dan performa sektor dari Sectors API, lalu mengirim ringkasan ke Telegram setiap pagi hari bursa tanpa campur tangan manual.

Disiapkan untuk **Sectors Hackathon 2026, Track 02 — Automation & Workflows**.

## 🚀 Fitur

- **Fully Autonomous**: Dijalankan secara otomatis melalui cron job di GitHub Actions setiap hari Senin–Jumat pukul 06:30 WIB.
- **Sectors API Integration**: Mengambil data komprehensif pasar saham Indonesia.
- **AI Summarization**: Opsional merangkum data menjadi narasi Bahasa Indonesia yang mudah dipahami menggunakan Anthropic (Claude 3.5 Sonnet).
- **Robustness**: Dilengkapi dengan *retry mechanism* (menggunakan `tenacity`) untuk menangani kegagalan API, serta *fallback system* jika AI gagal agar brief tetap terkirim.

## 🛠️ Tech Stack

- **Language**: Python 3.11+
- **APIs**: Sectors API, Telegram Bot API, Anthropic API
- **Automation**: GitHub Actions
- **Libraries**: `requests`, `anthropic`, `tenacity`, `python-dotenv`

## ⚙️ Cara Menjalankan Secara Lokal

1. Clone repositori ini.
2. Buat file `.env` berdasarkan `.env.example` dan isi token serta API key Anda.
3. Install dependensi:
   ```bash
   pip install -r requirements.txt
   ```
4. Jalankan script utama:
   ```bash
   python src/main.py
   ```

## 🔄 Konfigurasi GitHub Actions

Untuk deploy ke GitHub Actions:
1. Masukkan API keys sebagai **Repository Secrets** di GitHub:
   - `SECTORS_API_KEY`
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
   - `ANTHROPIC_API_KEY`
2. Workflow akan otomatis berjalan setiap pukul 23:30 UTC (06:30 WIB) dari Senin hingga Jumat.
3. Anda juga dapat menjalankan workflow secara manual via tab **Actions** > **Daily Market Brief** > **Run workflow**.

## 🧪 Testing

Jalankan unit test menggunakan pytest:
```bash
pytest tests/
```
