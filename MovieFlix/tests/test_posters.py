"""
MovieFlix - Poster URL Resolution Tests
Verifies that poster_url() strictly enforces fallback handling and never produces
malformed URLs like https://image.tmdb.org/t/p/w500/None or .../w500/.
"""

import pytest
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tmdb_client import poster_url, backdrop_url, image_url
from config import POSTER_FALLBACK_URL


def test_poster_url_valid_path():
    """Valid paths must be prefixed with the TMDB CDN base."""
    path = "/ljsZTbVsrQSqZgWeep2B1QiDKuh.jpg"
    result = poster_url(path)
    assert result == "https://image.tmdb.org/t/p/w500/ljsZTbVsrQSqZgWeep2B1QiDKuh.jpg"
    assert "/None" not in result


def test_poster_url_none():
    """None must safely resolve to the fallback SVG."""
    result = poster_url(None)
    assert result == POSTER_FALLBACK_URL
    assert "None" not in result
    assert result == "/static/img/poster-fallback.svg"


def test_poster_url_empty_string():
    """Empty strings must return fallback SVG."""
    result = poster_url("")
    assert result == POSTER_FALLBACK_URL

    result_spaces = poster_url("   ")
    assert result_spaces == POSTER_FALLBACK_URL


def test_poster_url_literal_none_string():
    """Strings like 'None' or 'null' must never generate https://image.tmdb.org/t/p/w500/None."""
    assert poster_url("None") == POSTER_FALLBACK_URL
    assert poster_url("null") == POSTER_FALLBACK_URL
    assert poster_url("None.jpg") == POSTER_FALLBACK_URL


def test_poster_url_missing_leading_slash():
    """Paths without a leading slash are invalid and must return fallback."""
    result = poster_url("poster_without_slash.jpg")
    assert result == POSTER_FALLBACK_URL


def test_backdrop_url_fallback():
    """Backdrop URL should return empty string on invalid/None input for CSS fallback."""
    assert backdrop_url(None) == ""
    assert backdrop_url("") == ""
    assert backdrop_url("None") == ""
    valid_b = backdrop_url("/sample_backdrop.jpg")
    assert valid_b == "https://image.tmdb.org/t/p/w1280/sample_backdrop.jpg"
