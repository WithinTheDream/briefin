import pytest
from unittest.mock import patch, MagicMock

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from fetch_sectors import get_ihsg, SectorsAPIError
from format_brief import normalize_data, generate_fallback_message

@patch('fetch_sectors.requests.get')
def test_fetch_ihsg_success(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {"date": "2026-09-17", "price": 7450},
        {"date": "2026-09-18", "price": 7500}
    ]
    mock_get.return_value = mock_response
    
    with patch.dict(os.environ, {"SECTORS_API_KEY": "test_key"}):
        result = get_ihsg()
        
    assert len(result) == 2
    assert result[1]["price"] == 7500

@patch('fetch_sectors.requests.get')
def test_fetch_endpoint_retry_logic(mock_get):
    # Setup mock to fail twice, then succeed
    fail_response = MagicMock()
    fail_response.status_code = 500
    
    success_response = MagicMock()
    success_response.status_code = 200
    success_response.json.return_value = {"status": "ok"}
    
    mock_get.side_effect = [fail_response, fail_response, success_response]
    
    with patch.dict(os.environ, {"SECTORS_API_KEY": "test_key"}):
        result = get_ihsg()
        
    assert result == {"status": "ok"}
    assert mock_get.call_count == 3

def test_normalize_data_v1_format():
    idx_total = {"total_market_cap": 12000000}
    ihsg = {"price": 7500, "change": 10, "percent_change": 0.13}
    top_changes = {
        "top_gainers": [{"symbol": "BBCA", "price": 10000, "percent_change": 2.5}],
        "top_losers": [{"symbol": "GOTO", "price": 50, "percent_change": -5.0}]
    }
    
    norm = normalize_data(idx_total, ihsg, top_changes)
    
    assert norm["ihsg"]["price"] == 7500
    assert norm["market_cap"] == 12000000
    assert len(norm["gainers"]) == 1
    assert norm["gainers"][0]["symbol"] == "BBCA"

def test_normalize_data_v2_format():
    idx_total = [
        {"date": "2026-09-17", "idx_total_market_cap": 11000000},
        {"date": "2026-09-18", "idx_total_market_cap": 12000000}
    ]
    ihsg = [
        {"date": "2026-09-17", "price": 7450},
        {"date": "2026-09-18", "price": 7500}
    ]
    top_changes = {
        "top_gainers": {
            "1d": [{"symbol": "BBCA.JK", "last_close_price": 10000, "price_change": 0.025}]
        },
        "top_losers": {
            "1d": [{"symbol": "GOTO.JK", "last_close_price": 50, "price_change": -0.05}]
        }
    }
    
    norm = normalize_data(idx_total, ihsg, top_changes)
    
    assert norm["ihsg"]["price"] == 7500
    assert norm["ihsg"]["change"] == 50
    assert norm["ihsg"]["percent_change"] == 0.67
    assert norm["market_cap"] == 12000000
    assert len(norm["gainers"]) == 1
    assert norm["gainers"][0]["symbol"] == "BBCA.JK"
    assert norm["gainers"][0]["percent_change"] == 2.5

def test_fallback_message():
    norm_data = {
        "ihsg": {"price": 7500, "change": -20, "percent_change": -0.26},
        "market_cap": "N/A",
        "gainers": [],
        "losers": []
    }
    
    msg = generate_fallback_message(norm_data)
    assert "📉" in msg  # Since change is negative
    assert "7,500.00" in msg or "7500" in msg
    assert "-20" in msg
