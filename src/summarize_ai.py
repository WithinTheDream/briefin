import os
import logging
import requests
from anthropic import Anthropic, APIError, APIConnectionError, RateLimitError

logger = logging.getLogger(__name__)

def _summarize_with_gemini(api_key: str, prompt: str) -> str:
    """Summarize using Google Gemini API with support for modern flash models."""
    models_to_try = [
        "gemini-3.6-flash",
        "gemini-3.5-flash",
        "gemini-3.5-flash-lite"
    ]
    
    for model_name in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key.strip()}"
        
        # Try first with thinkingBudget: 0 to maximize output speed and save token quota for text
        for include_thinking_config in [True, False]:
            gen_config = {
                "temperature": 0.7,
                "maxOutputTokens": 3000
            }
            if include_thinking_config:
                gen_config["thinkingConfig"] = {"thinkingBudget": 0}

            payload = {
                "contents": [
                    {
                        "parts": [{"text": prompt}]
                    }
                ],
                "generationConfig": gen_config
            }
            try:
                response = requests.post(url, json=payload, timeout=30)
                if response.status_code == 200:
                    data = response.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        finish_reason = candidates[0].get("finishReason")
                        parts = candidates[0].get("content", {}).get("parts", [])
                        texts = [p.get("text", "") for p in parts if not p.get("thought", False) and "text" in p]
                        text = "".join(texts).strip()
                        if text:
                            logger.info(f"Successfully generated summary using {model_name} (finishReason: {finish_reason})")
                            return text
                elif response.status_code == 400 and include_thinking_config:
                    # Model might not support thinkingConfig, retry without it
                    continue
                logger.warning(f"Gemini API warning with {model_name} (thinkingConfig={include_thinking_config}): {response.status_code} - {response.text}")
            except Exception as e:
                logger.warning(f"Gemini request exception for {model_name}: {e}")
                
            # If standard request without thinkingConfig also failed, proceed to next model
            if not include_thinking_config:
                break

def _summarize_with_anthropic(api_key: str, prompt: str) -> str:
    """Summarize using Anthropic Claude 3.5 Sonnet."""
    client = Anthropic(api_key=api_key.strip())
    message = client.messages.create(
        model="claude-3-5-sonnet-20240620",
        max_tokens=1000,
        temperature=0.7,
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
    Returns a dynamic, engaging morning market narrative.
    Returns None if neither is set or if both fail.
    """
    gemini_key = os.getenv("GEMINI_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")

    if not gemini_key and not anthropic_key:
        logger.warning("Neither GEMINI_API_KEY nor ANTHROPIC_API_KEY is set. Skipping AI summarization.")
        return None

    prompt = f"""
Anda adalah analis pasar modal handal dan kurator konten finansial profesional.
Tugas Anda: Buat pesan NARASI MORNING MARKET BRIEF harian untuk bursa saham Indonesia (IHSG / IDX) berdasarkan data di bawah ini.

PENTING - Konteks Pesan & Infografis:
- Pesan teks ini akan dikirim bersama KARTU INFOGRAFIS GAMBAR yang sudah menampilkan tabel lengkap Top 5 Gainers dan Top 5 Losers.
- Oleh karena itu, pesan teks ini BUKAN tabel angka mentah, melainkan MURNI NARASI PASAR (cerita, sentimen, dan strategi).
- Narasi HARUS bervariasi, dinamis, segar, cerdas, dan tidak terdengar seperti template bot yang kaku.

Susunan Narasi Pesan:
1. ☀️ **Sapaan Pagi & Narasi Sentimen**:
   - Sapaan pagi yang hangat, inspiratif, dan bervariasi setiap hari.
   - Narasi mendalam mengenai suasana/mood IHSG (apakah pasar sedang konsolidasi, tertekan aksi profit taking, optimis, atau wait-and-see sentimen makro).
2. 📊 **Ulasan IHSG & Penggerak Pasar**:
   - Tuliskan pergerakan IHSG kemarin (poin & persentase) dalam kalimat mengalir.
   - Singgung secara naratif 1 atau 2 saham/sektor yang paling menarik perhatian (misal yang memimpin reli atau yang mengalami tekanan paling dalam) tanpa mengetik ulang seluruh daftar tabel.
3. 💡 **Catatan Strategi & Tips Cuan Hari Ini**:
   - Berikan 1-2 kalimat tips taktis yang aplikatif (misal: disiplin money management, amankan modal, cermati saham pullback di support, atau batasi transaksi di saham berfrekuensi tinggi).
4. 📌 **Call to Action Singkat**:
   - 1 baris singkat ramah (misal: "Detail daftar Top 5 Gainers & Losers lengkap dapat disimak pada infografis di atas!").

Format Tampilan:
- Gunakan Bahasa Indonesia yang santai tapi berbobot, luwes, dan enak dibaca.
- Gunakan bullet points bila perlu, baris spasi yang rapi, dan emoji yang relevan.
- Panjang sekitar 150-250 kata (padat, menarik, dan pas di layar ponsel).

Data Pasar IDX:
{formatted_data}
"""

    # 1. Try Gemini if configured
    if gemini_key:
        try:
            logger.info("Calling Google Gemini API for summarization...")
            summary = _summarize_with_gemini(gemini_key, prompt)
            if summary:
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
