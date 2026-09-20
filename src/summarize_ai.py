import os
import logging
from anthropic import Anthropic, APIError, APIConnectionError, RateLimitError

logger = logging.getLogger(__name__)

def summarize_market_data(formatted_data: str) -> str:
    """
    Sends the formatted market data to Anthropic's Claude 3.5 Sonnet to generate a narrative summary.
    Returns the AI-generated summary or None if it fails.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY is not set. Skipping AI summarization.")
        return None
        
    client = Anthropic(api_key=api_key)
    
    prompt = f"""
    Tolong buatkan ringkasan singkat dan menarik (market brief harian) dalam Bahasa Indonesia berdasarkan data pasar saham IDX berikut ini.
    Brief ini akan dikirim ke Telegram setiap pagi. Jangan terlalu panjang, buat to the point, gunakan bullet points dan emoji yang sesuai.
    Sertakan ringkasan performa IHSG, top gainers/losers yang menarik, dan sektor yang menonjol.
    
    Data Mentah:
    {formatted_data}
    """

    try:
        logger.info("Calling Anthropic API for summarization...")
        message = client.messages.create(
            model="claude-3-5-sonnet-20240620",
            max_tokens=1000,
            temperature=0.3,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )
        logger.info("Successfully generated AI summary.")
        return message.content[0].text
    except (APIError, APIConnectionError, RateLimitError) as e:
        logger.error(f"Anthropic API Error: {str(e)}")
        return None
    except Exception as e:
        logger.exception("Unexpected error during AI summarization")
        return None
