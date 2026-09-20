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

def generate_fallback_message(normalized_data: dict) -> str:
    """
    Generates a Markdown template message if the AI summarization fails.
    """
    ihsg = normalized_data.get("ihsg", {})
    price = ihsg.get("price", 0)
    change = ihsg.get("change", 0)
    pct_change = ihsg.get("percent_change", 0)
    
    direction_emoji = "📈" if change >= 0 else "📉"
    
    msg = f"📊 **Sectors Daily Market Brief**\n\n"
    if isinstance(price, (int, float)):
        msg += f"**IHSG:** {price:,.2f} ({change:+.2f} / {pct_change:+.2f}%) {direction_emoji}\n\n"
    else:
        msg += f"**IHSG:** {price} ({change} / {pct_change}%) {direction_emoji}\n\n"
    
    msg += "🚀 **Top Gainers:**\n"
    if normalized_data.get("gainers"):
        for g in normalized_data.get("gainers", []):
            msg += f"- {g.get('symbol', 'N/A')}: {g.get('price', 0)} ({g.get('percent_change', 0):+.2f}%)\n"
    else:
        msg += "- Tidak ada data gainers\n"
        
    msg += "\n🔻 **Top Losers:**\n"
    if normalized_data.get("losers"):
        for l in normalized_data.get("losers", []):
            msg += f"- {l.get('symbol', 'N/A')}: {l.get('price', 0)} ({l.get('percent_change', 0):+.2f}%)\n"
    else:
        msg += "- Tidak ada data losers\n"
        
    msg += "\n_Automated by Sectors Daily Brief_"
    return msg
