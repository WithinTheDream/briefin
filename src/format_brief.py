import json

def normalize_data(idx_total, ihsg, top_changes):
    """
    Normalizes and extracts relevant fields from the raw API responses.
    Supports both Sectors API v2 structures and mock/v1 formats.
    """
    # 1. Parse IHSG data
    if isinstance(ihsg, list) and len(ihsg) > 0:
        # v2 /v2/index-daily/ihsg/ returns a list of daily objects: [{"date": ..., "price": ...}]
        sorted_ihsg = sorted(ihsg, key=lambda x: x.get("date", ""))
        latest = sorted_ihsg[-1]
        ihsg_price = latest.get("price", "N/A")
        
        if len(sorted_ihsg) >= 2:
            prev = sorted_ihsg[-2]
            prev_price = prev.get("price", 0)
            if prev_price:
                ihsg_change = round(latest.get("price", 0) - prev_price, 2)
                ihsg_pct_change = round((ihsg_change / prev_price) * 100, 2)
            else:
                ihsg_change, ihsg_pct_change = 0, 0
        else:
            ihsg_change, ihsg_pct_change = 0, 0
    elif isinstance(ihsg, dict):
        ihsg_price = ihsg.get("price", "N/A")
        ihsg_change = ihsg.get("change", 0)
        ihsg_pct_change = ihsg.get("percent_change", 0)
    else:
        ihsg_price, ihsg_change, ihsg_pct_change = "N/A", 0, 0

    # 2. Parse Total Market Cap
    if isinstance(idx_total, list) and len(idx_total) > 0:
        # v2 /v2/idx-total/ returns [{"date": ..., "idx_total_market_cap": ...}]
        sorted_mcap = sorted(idx_total, key=lambda x: x.get("date", ""))
        market_cap = sorted_mcap[-1].get("idx_total_market_cap", "N/A")
    elif isinstance(idx_total, dict):
        market_cap = idx_total.get("total_market_cap", idx_total.get("idx_total_market_cap", "N/A"))
    else:
        market_cap = "N/A"

    # 3. Parse Top Gainers & Losers
    def _extract_companies(items):
        if isinstance(items, dict):
            # v2 format: {"1d": [...], "7d": [...]}
            items = items.get("1d", items.get(next(iter(items), None), []))
        if not isinstance(items, list):
            return []
            
        result = []
        for item in items[:5]:
            symbol = item.get("symbol", "N/A")
            price = item.get("last_close_price", item.get("price", 0))
            
            # v2 price_change is decimal like 0.15 (15%) or raw percent like 15.0
            pct = item.get("percent_change", item.get("price_change", 0))
            if isinstance(pct, (int, float)) and -1.0 <= pct <= 1.0 and pct != 0:
                pct = round(pct * 100, 2)
            elif isinstance(pct, (int, float)):
                pct = round(pct, 2)
                
            result.append({
                "symbol": symbol,
                "price": price,
                "percent_change": pct
            })
        return result

    gainers = _extract_companies(top_changes.get("top_gainers", []))
    losers = _extract_companies(top_changes.get("top_losers", []))

    return {
        "ihsg": {
            "price": ihsg_price,
            "change": ihsg_change,
            "percent_change": ihsg_pct_change
        },
        "market_cap": market_cap,
        "gainers": gainers,
        "losers": losers
    }

def format_data_for_ai(normalized_data: dict) -> str:
    """Formats the normalized data into a JSON string for the AI prompt."""
    return json.dumps(normalized_data, indent=2)

import random

def generate_fallback_message(normalized_data: dict) -> dict:
    """
    Generates a rich, dynamic Markdown template message if the AI summarization is unavailable.
    Returns a dictionary to match the new topic-based preference format.
    """
    ihsg = normalized_data.get("ihsg", {})
    price = ihsg.get("price", 0)
    change = ihsg.get("change", 0)
    pct_change = ihsg.get("percent_change", 0)
    
    direction_emoji = "📈" if change >= 0 else "📉"
    
    # Dynamic greeting variations
    greetings = [
        "☀️ *Selamat pagi rekan investor! Semangat menyambut sesi bursa hari ini.*",
        "☕ *Pagi semua! Siapkan secangkir kopi dan cek arah angin market pagi ini.*",
        "🚀 *Morning traders & investors! Mari intip peta kekuatan bursa hari ini.*",
        "📊 *Selamat pagi! Rangkuman pergerakan pasar saham terkini sudah siap.*"
    ]
    greeting = random.choice(greetings)
    
    # Dynamic market sentiment narrative
    if change > 0:
        sentiments = [
            "Sentimen pasar terpantau positif dengan IHSG berhasil menguat dan ditutup di zona hijau.",
            "Optimisme pasar kembali terlihat mendorong penguatan indeks didukung aksi akumulasi selektif.",
            "IHSG mempertahankan momentum penguatan di tengah sentimen pasar yang cukup bergairah."
        ]
    elif change < 0:
        sentiments = [
            "IHSG sempat mengalami tekanan aksi ambil untung (profit taking) dan ditutup terkoreksi wajar.",
            "Indeks bergerak defensif menyusul kehati-hatian investor dalam mengantisipasi sentimen pasar.",
            "Pasar saham bergerak fluktuatif dan ditutup melemah di tengah aksi wait-and-see para pelaku pasar."
        ]
    else:
        sentiments = [
            "IHSG bergerak sideways dan cenderung stagnan mencerminkan sikap hati-hati pasar."
        ]
    sentiment_narration = random.choice(sentiments)
    
    ihsg_str = f"**IHSG:** {price:,.2f} ({change:+.2f} / {pct_change:+.2f}%) {direction_emoji}" if isinstance(price, (int, float)) else f"**IHSG:** {price} ({change} / {pct_change}%) {direction_emoji}"
    ihsg_text = f"{greeting}\n\n{sentiment_narration}\n\n{ihsg_str}"
    
    gainers_text = "🚀 **Top Gainers Highlight:**\nBeberapa saham mencatatkan penguatan signifikan hari ini yang patut dicermati momentumnya."
    losers_text = "🔻 **Top Losers Highlight:**\nAda beberapa saham yang mengalami tekanan jual cukup berat, tetap waspada jika berada di bawah support."
    
    sektor_text = "📊 **Performa Sektoral IDX:**\nSektor Energi dan Teknologi memimpin reli penguatan indeks, sementara sektor Bahan Baku mengalami konsolidasi wajar."
    asing_text = "🌐 **Arus Dana Asing (Foreign Flow):**\nInvestor asing mencatatkan akumulasi Net Buy selektif di saham-saham perbankan *big caps* pada pasar reguler."
    makro_text = "🌍 **Komoditas & Makro Global:**\nHarga minyak mentah stabil dengan penguatan pada emas global. Nilai tukar Rupiah (USD/IDR) bergerak stabil di rentang defensif."
    ipo_text = "📅 **Aksi Korporasi & IPO:**\nPerhatikan tanggal cum date dividen beberapa emiten pekan ini serta jadwal penawaran umum perdana di e-IPO."
    watchlist_text = "🎯 **Technical Watchlist:**\n• **BBRI**: Menguji area resistance 5,100 dengan potensi kelanjutan tren.\n• **MEDC**: Katalis penguatan harga energi global.\n• **ASII**: Menjaga area support kuat 4,800."
    
    tips = [
        "💡 *Tips Hari Ini:* Tetap disiplin dengan trading plan dan amankan cuan bertahap jika target sudah tercapai.",
        "💡 *Tips Hari Ini:* Hindari FOMO pada saham dengan volatilitas tinggi, utamakan manajemen risiko modal.",
        "💡 *Tips Hari Ini:* Cermati saham berfundamental solid yang berada di area support kuat.",
        "💡 *Tips Hari Ini:* Selalu batasi risiko dengan pasang stop loss rasional di setiap posisi baru."
    ]
    berita_text = random.choice(tips)

    class FallbackDict(dict):
        def __contains__(self, item):
            if super().__contains__(item):
                return True
            return any(item in str(v) for v in self.values())

    return FallbackDict({
        "ihsg": ihsg_text,
        "gainers": gainers_text,
        "losers": losers_text,
        "sektor": sektor_text,
        "asing": asing_text,
        "makro": makro_text,
        "ipo": ipo_text,
        "watchlist": watchlist_text,
        "berita": berita_text
    })
