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

@patch('send_whatsapp.requests.post')
def test_send_whatsapp_gateway_success(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": True, "message": "Message sent successfully"}
    mock_post.return_value = mock_response
    
    env_vars = {
        "WA_GATEWAY_URL": "http://localhost:3000",
        "WHATSAPP_TARGET": "08123456789"
    }
    
    with patch.dict(os.environ, env_vars, clear=True):
        result = send_whatsapp_message("Test gateway message")
        
    assert result["status"] is True
    assert mock_post.called
    assert mock_post.call_args[0][0] == "http://localhost:3000/send"
    json_data = mock_post.call_args[1]["json"]
    assert json_data["target"] == "08123456789"
    assert json_data["message"] == "Test gateway message"

@patch('send_whatsapp.requests.post')
def test_send_whatsapp_gateway_failure(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 503
    mock_response.text = "Service Unavailable"
    mock_post.return_value = mock_response
    
    env_vars = {
        "WA_GATEWAY_URL": "http://localhost:3000",
        "WHATSAPP_TARGET": "08123456789"
    }
    
    with patch.dict(os.environ, env_vars, clear=True):
        with pytest.raises(WhatsAppError):
            send_whatsapp_message("Test message")

@patch('send_whatsapp.requests.get')
def test_get_registered_subscribers(mock_get):
    from send_whatsapp import get_registered_subscribers
    mock_res = MagicMock()
    mock_res.status_code = 200
    mock_res.json.return_value = {"status": True, "count": 2, "subscribers": ["6281111111", "6282222222"]}
    mock_get.return_value = mock_res

    subs = get_registered_subscribers("http://localhost:3000")
    assert len(subs) == 2
    assert "6281111111" in subs
    assert "6282222222" in subs

@patch('send_whatsapp.requests.post')
@patch('send_whatsapp.requests.get')
def test_send_whatsapp_broadcast_multiple_subscribers(mock_get, mock_post):
    mock_get_res = MagicMock()
    mock_get_res.status_code = 200
    mock_get_res.json.return_value = {
        "status": True,
        "count": 2,
        "subscribers": ["6281111111@s.whatsapp.net", "6282222222@s.whatsapp.net"]
    }
    mock_get.return_value = mock_get_res

    mock_post_res = MagicMock()
    mock_post_res.status_code = 200
    mock_post_res.json.return_value = {"status": True, "results": []}
    mock_post.return_value = mock_post_res

    env_vars = {
        "WA_GATEWAY_URL": "http://localhost:3000",
        "WHATSAPP_TARGET": "08123456789"
    }

    with patch.dict(os.environ, env_vars, clear=True):
        result = send_whatsapp_message("Broadcast message")

    assert result["status"] is True
    assert mock_post.called
    json_data = mock_post.call_args[1]["json"]
    # Check that both subscribers and the admin target are included
    assert isinstance(json_data["target"], list)
    assert len(json_data["target"]) == 3
    assert "6281111111@s.whatsapp.net" in json_data["target"]
    assert "6282222222@s.whatsapp.net" in json_data["target"]
    assert "08123456789" in json_data["target"]


