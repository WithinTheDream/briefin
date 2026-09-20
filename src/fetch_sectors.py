import os
import requests
import logging
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

# Sectors API v2 (v1 was discontinued on 2026-05-11)
SECTORS_API_BASE_URL = "https://api.sectors.app/v2"

class SectorsAPIError(Exception):
    """Custom exception for Sectors API errors."""
    pass

def get_headers():
    api_key = os.getenv("SECTORS_API_KEY")
    if not api_key:
        raise ValueError("SECTORS_API_KEY is not set in environment variables.")
    # Sectors API expects raw key in Authorization header
    auth_header = api_key.strip()
    return {
        "Authorization": auth_header,
        "Accept": "application/json"
    }

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((requests.RequestException, SectorsAPIError)),
    reraise=True
)
def fetch_endpoint(endpoint: str, params: dict = None):
    url = f"{SECTORS_API_BASE_URL}{endpoint}"
    logger.info(f"Fetching data from {url}")
    
    response = requests.get(url, headers=get_headers(), params=params, timeout=10)
    
    if response.status_code != 200:
        logger.error(f"Error fetching {endpoint}: {response.status_code} - {response.text}")
        raise SectorsAPIError(f"Failed to fetch {endpoint}: Status {response.status_code}")
        
    return response.json()

def get_idx_total():
    """Fetch total IDX market cap summary."""
    return fetch_endpoint("/idx-total/")

def get_ihsg():
    """Fetch IHSG daily index records."""
    return fetch_endpoint("/index-daily/ihsg/")

def get_top_changes():
    """Fetch top gainers and losers for 1-day period."""
    return fetch_endpoint("/companies/top-changes/", params={"periods": "1d"})

def get_subsectors():
    """Fetch list of subsectors."""
    return fetch_endpoint("/subsectors/")
