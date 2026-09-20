import os
import logging
import requests
from anthropic import Anthropic, APIError, APIConnectionError, RateLimitError

logger = logging.getLogger(__name__)

def _summarize_with_gemini(api_key: str, prompt: str) -> str:
    """Summarize using Google Gemini API."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key.strip()}"
    payload = {
        "contents": [
            {
                "parts": [{"text": prompt}]
            }
        ],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 1000
        }
    }
    response = requests.post(url, json=payload, timeout=20)
    if response.status_code == 200:
        data = response.json()
        candidates = data.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            if parts:
                return parts[0].get("text")
    logger.error(f"Gemini API Error: {response.status_code} - {response.text}")
    return None

def _summarize_with_anthropic(api_key: str, prompt: str) -> str:
    """Summarize using Anthropic Claude 3.5 Sonnet."""
    client = Anthropic(api_key=api_key.strip())
    message = client.messages.create(
        model="claude-3-5-sonnet-20240620",
        max_tokens=1000,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )
    return message.content[0].text

def summarize_market_data(formatted_data: str) -> str:
    """
    Summarizes market data using either Gemini or Anthropic (whichever API key is available).
    Returns None if neither is set or if both fail.
    """
    gemini_key = os.getenv("GEMINI_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")

    if not gemini_key and not anthropic_key:
        logger.warning("Neither GEMINI_API_KEY nor ANTHROPIC_API_KEY is set. Skipping AI summarization.")
        return None

    prompt = f"""
    Tolong buatkan ringkasan singkat dan menarik (market brief harian) dalam Bahasa Indonesia berdasarkan data pasar saham IDX berikut ini.
    Brief ini akan dikirim ke Telegram dan WhatsApp setiap pagi. Jangan terlalu panjang, buat to the point, gunakan bullet points dan emoji yang sesuai.
    Sertakan ringkasan performa IHSG, top gainers/losers yang menarik, dan sektor yang menonjol.
    
    Data Mentah:
    {formatted_data}
    """

    # 1. Try Gemini if configured
    if gemini_key:
        try:
            logger.info("Calling Google Gemini API for summarization...")
            summary = _summarize_with_gemini(gemini_key, prompt)
            if summary:
                logger.info("Successfully generated AI summary via Gemini.")
                return summary
        except Exception as e:
            logger.error(f"Error during Gemini summarization: {e}")

    # 2. Try Anthropic if configured (or fallback from Gemini)
    if anthropic_key:
        try:
            logger.info("Calling Anthropic API for summarization...")
            summary = _summarize_with_anthropic(anthropic_key, prompt)
            if summary:
                logger.info("Successfully generated AI summary via Anthropic.")
                return summary
        except (APIError, APIConnectionError, RateLimitError) as e:
            logger.error(f"Anthropic API Error: {str(e)}")
        except Exception as e:
            logger.exception("Unexpected error during Anthropic summarization")

    return None
