"""
MovieFlix - TMDB Client Authentication & Connection Tests
Tests credential detection, dual auth strategy (v4 vs v3),
and mockable HTTP error handling without exposing secrets.
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from tmdb_client import TMDBClient


def test_credential_detection_flags(monkeypatch):
    """Verifies boolean diagnostic flags reflect environment without leaking keys."""
    # Test 1: Neither configured
    monkeypatch.setattr(config, "TMDB_ACCESS_TOKEN", "")
    monkeypatch.setattr(config, "TMDB_API_KEY", "")
    assert config.is_tmdb_v4_configured() is False
    assert config.is_tmdb_v3_configured() is False
    assert config.is_tmdb_configured() is False
    assert config.get_auth_strategy() == "none"

    # Test 2: v3 configured only
    monkeypatch.setattr(config, "TMDB_ACCESS_TOKEN", "")
    monkeypatch.setattr(config, "TMDB_API_KEY", "dummy_v3_api_key_test_123")
    assert config.is_tmdb_v4_configured() is False
    assert config.is_tmdb_v3_configured() is True
    assert config.is_tmdb_configured() is True
    assert config.get_auth_strategy() == "v3"

    # Test 3: v4 configured (takes priority)
    monkeypatch.setattr(config, "TMDB_ACCESS_TOKEN", "dummy_v4_token_bearer_xyz")
    monkeypatch.setattr(config, "TMDB_API_KEY", "dummy_v3_api_key_test_123")
    assert config.is_tmdb_v4_configured() is True
    assert config.is_tmdb_v3_configured() is True
    assert config.is_tmdb_configured() is True
    assert config.get_auth_strategy() == "v4"


def test_auth_header_and_params(monkeypatch):
    """Verifies that v4 creates Bearer Authorization and v3 creates api_key param."""
    client = TMDBClient()

    # Case A: v4 active
    monkeypatch.setattr(config, "TMDB_ACCESS_TOKEN", "v4_bearer_secret")
    monkeypatch.setattr(config, "TMDB_API_KEY", "")
    headers, params = client._get_auth_headers_and_params()
    assert headers.get("Authorization") == "Bearer v4_bearer_secret"
    assert "api_key" not in params

    # Case B: v3 active
    monkeypatch.setattr(config, "TMDB_ACCESS_TOKEN", "")
    monkeypatch.setattr(config, "TMDB_API_KEY", "v3_key_secret")
    headers, params = client._get_auth_headers_and_params()
    assert "Authorization" not in headers
    assert params.get("api_key") == "v3_key_secret"


def test_unconfigured_client_raises_error(monkeypatch):
    """Client must safely reject calls if credentials are missing."""
    monkeypatch.setattr(config, "TMDB_ACCESS_TOKEN", "")
    monkeypatch.setattr(config, "TMDB_API_KEY", "")
    client = TMDBClient()
    with pytest.raises(RuntimeError) as exc_info:
        client._request("movie/popular")
    assert "TMDB credentials not configured" in str(exc_info.value)


@patch("requests.Session.get")
def test_mock_tmdb_connection_success(mock_get, monkeypatch):
    """Simulates successful TMDB configuration handshake."""
    monkeypatch.setattr(config, "TMDB_ACCESS_TOKEN", "mock_token")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"images": {"base_url": "http://image.tmdb.org/t/p/"}}
    mock_get.return_value = mock_resp

    client = TMDBClient()
    success, message = client.test_connection()
    assert success is True
    assert "Connection successful" in message


@patch("requests.Session.get")
def test_mock_tmdb_401_error(mock_get, monkeypatch):
    """Simulates 401 Unauthorized handling without crashing."""
    monkeypatch.setattr(config, "TMDB_API_KEY", "invalid_key")
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.text = "Invalid API key"
    mock_get.return_value = mock_resp

    client = TMDBClient()
    success, message = client.test_connection()
    assert success is False
    assert "401" in message
