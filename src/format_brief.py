import json

def normalize_data(idx_total, ihsg, top_changes):
    """
    Normalizes and extracts relevant fields from the raw API responses.
    """
    # Defensive parsing depending on the exact structure of Sectors API
    # Assuming generic structures for the hackathon
    
    # Extract IHSG data
    ihsg_price = ihsg.get("price", "N/A")
    ihsg_change = ihsg.get("change", 0)
    ihsg_pct_change = ihsg.get("percent_change", 0)
    
    # Extract Top Changes
    gainers = top_changes.get("top_gainers", [])[:5]  # Top 5
    losers = top_changes.get("top_losers", [])[:5]    # Top 5
    
    # Extract total market cap
    market_cap = idx_total.get("total_market_cap", "N/A")
    
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
    msg += f"**IHSG:** {price} ({change:+.2f} / {pct_change:+.2f}%) {direction_emoji}\n\n"
    
    msg += "🚀 **Top Gainers:**\n"
    for g in normalized_data.get("gainers", []):
        msg += f"- {g.get('symbol', 'N/A')}: {g.get('price', 0)} ({g.get('percent_change', 0):+.2f}%)\n"
        
    msg += "\n🔻 **Top Losers:**\n"
    for l in normalized_data.get("losers", []):
        msg += f"- {l.get('symbol', 'N/A')}: {l.get('price', 0)} ({l.get('percent_change', 0):+.2f}%)\n"
        
    msg += "\n_Automated by Sectors Daily Brief_"
    return msg
