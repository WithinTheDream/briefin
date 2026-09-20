import pytest
from unittest.mock import patch, MagicMock
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from send_whatsapp import send_whatsapp_message, format_for_whatsapp, WhatsAppError

def test_format_for_whatsapp():
    raw = "📊 **Sectors Daily Brief**\n**IHSG:** 7500"
    formatted = format_for_whatsapp(raw)
    assert "*Sectors Daily Brief*" in formatted
    assert "*IHSG:*" in formatted
    assert "**" not in formatted

@patch('send_whatsapp.requests.post')
def test_send_whatsapp_success(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": True, "target": ["08123456789"]}
    mock_post.return_value = mock_response
    
    env_vars = {
        "FONNTE_TOKEN": "mock_fonnte_token",
        "WHATSAPP_TARGET": "08123456789"
    }
    
    with patch.dict(os.environ, env_vars):
        result = send_whatsapp_message("Test message")
        
    assert result["status"] is True
    assert mock_post.called
    headers = mock_post.call_args[1]["headers"]
    data = mock_post.call_args[1]["data"]
    assert headers["Authorization"] == "mock_fonnte_token"
    assert data["target"] == "08123456789"

@patch('send_whatsapp.requests.post')
def test_send_whatsapp_api_failure(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.text = "Bad Request"
    mock_post.return_value = mock_response
    
    env_vars = {
        "FONNTE_TOKEN": "mock_fonnte_token",
        "WHATSAPP_TARGET": "08123456789"
    }
    
    with patch.dict(os.environ, env_vars):
        with pytest.raises(WhatsAppError):
            send_whatsapp_message("Test message")

def test_send_whatsapp_missing_credentials():
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError, match="Missing WhatsApp credentials"):
            send_whatsapp_message("Test message")
