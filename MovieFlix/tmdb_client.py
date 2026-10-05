"""
MovieFlix - TMDB API Client
Handles authentication (v4 Bearer Token with fallback to v3 API Key),
session pooling with automatic retries for rate limits (HTTP 429) and server errors (HTTP 5xx),
and defensive poster image URL resolution. Never leaks credentials.
"""

import logging
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Optional, Dict, Any, Tuple

from config import (
    TMDB_ACCESS_TOKEN,
    TMDB_API_KEY,
    TMDB_BASE_URL,
    TMDB_IMAGE_BASE_URL,
    POSTER_FALLBACK_URL,
    is_tmdb_v4_configured,
    is_tmdb_v3_configured,
    is_tmdb_configured,
)

logger = logging.getLogger(__name__)

# User-Agent header for TMDB API calls
USER_AGENT = "MovieFlix/1.0 (Educational College Project - Python/Requests)"
DEFAULT_TIMEOUT = (5.0, 15.0)  # (connect timeout, read timeout)


class TMDBClient:
    """
    Robust TMDB API Client supporting v4 Bearer Tokens and v3 API Keys
    with connection pooling, exponential backoff retries, and defensive parsing.
    """

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

        # Configure resilient retry strategy for network glitches, 429, and 5xx
        retries = Retry(
            total=3,
            backoff_factor=0.8,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def _get_auth_headers_and_params(self) -> Tuple[Dict[str, str], Dict[str, str]]:
        """
        Determines authentication parameters securely.
        Prioritizes v4 Bearer Token. If not available, uses v3 api_key query param.
        Never reveals secret content in debug messages.
        """
        import config
        headers: Dict[str, str] = {"Accept": "application/json"}
        params: Dict[str, str] = {}

        if config.is_tmdb_v4_configured():
            headers["Authorization"] = f"Bearer {config.TMDB_ACCESS_TOKEN}"
        elif config.is_tmdb_v3_configured():
            params["api_key"] = config.TMDB_API_KEY
        return headers, params

    def _request(self, endpoint: str, extra_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Executes an authenticated GET request against TMDB endpoint.
        Returns parsed JSON or raises informative RuntimeError.
        """
        if not is_tmdb_configured():
            raise RuntimeError(
                "TMDB credentials not configured. Please set TMDB_ACCESS_TOKEN (v4) "
                "or TMDB_API_KEY (v3) in your .env file."
            )

        url = f"{TMDB_BASE_URL}/{endpoint.lstrip('/')}"
        headers, params = self._get_auth_headers_and_params()
        if extra_params:
            params.update(extra_params)

        try:
            response = self.session.get(url, headers=headers, params=params, timeout=DEFAULT_TIMEOUT)
        except requests.exceptions.Timeout:
            logger.error("TMDB API request timed out for endpoint: %s", endpoint)
            raise RuntimeError(f"TMDB request timed out while contacting endpoint: {endpoint}")
        except requests.exceptions.RequestException as exc:
            logger.error("Network error accessing TMDB endpoint %s: %s", endpoint, exc)
            raise RuntimeError(f"Network error while connecting to TMDB: {exc}")

        # Handle HTTP status codes gracefully
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 401:
            raise RuntimeError(
                "TMDB API credential rejected (HTTP 401 Unauthorized). "
                "Verify your TMDB_ACCESS_TOKEN or TMDB_API_KEY in .env."
            )
        elif response.status_code == 404:
            raise RuntimeError(f"Resource not found on TMDB (HTTP 404): {endpoint}")
        elif response.status_code == 429:
            raise RuntimeError("TMDB rate limit exceeded (HTTP 429). Please retry shortly.")
        elif response.status_code >= 500:
            raise RuntimeError(f"TMDB server error (HTTP {response.status_code}).")
        else:
            raise RuntimeError(f"Unexpected TMDB API response (HTTP {response.status_code}): {response.text[:200]}")

    def test_connection(self) -> Tuple[bool, str]:
        """
        Safely tests TMDB credentials.
        Returns (success: bool, status_message: str). Never prints secrets.
        """
        if not is_tmdb_configured():
            return False, "Neither TMDB_ACCESS_TOKEN (v4) nor TMDB_API_KEY (v3) is configured in .env."

        try:
            # configuration endpoint is lightweight and verifies token/key validity
            data = self._request("configuration")
            if "images" in data:
                auth_type = "v4 Bearer Token" if is_tmdb_v4_configured() else "v3 API Key"
                return True, f"Connection successful using {auth_type}."
            return False, "Unexpected response structure from TMDB configuration endpoint."
        except RuntimeError as err:
            return False, str(err)
        except Exception as exc:
            return False, f"Unexpected error during connection test: {str(exc)}"

    def discover_movies(self, page: int = 1, sort_by: str = "popularity.desc") -> Dict[str, Any]:
        """Fetch discovered movies with pagination and sorting."""
        params = {
            "page": page,
            "sort_by": sort_by,
            "include_adult": "false",
            "include_video": "false",
            "language": "en-US",
        }
        return self._request("discover/movie", params)

    def popular_movies(self, page: int = 1) -> Dict[str, Any]:
        """Fetch popular movies."""
        params = {"page": page, "language": "en-US"}
        return self._request("movie/popular", params)

    def search_movies(self, query: str, page: int = 1) -> Dict[str, Any]:
        """Search movies by query string."""
        if not query or not query.strip():
            return {"page": 1, "results": [], "total_results": 0, "total_pages": 0}
        params = {"query": query.strip(), "page": page, "include_adult": "false", "language": "en-US"}
        return self._request("search/movie", params)

    def movie_details(self, movie_id: int) -> Dict[str, Any]:
        """Fetch full details for a given movie ID."""
        return self._request(f"movie/{movie_id}", {"language": "en-US"})

    def movie_credits(self, movie_id: int) -> Dict[str, Any]:
        """Fetch cast and crew credits for a given movie ID."""
        return self._request(f"movie/{movie_id}/credits")

    def movie_keywords(self, movie_id: int) -> Dict[str, Any]:
        """Fetch keywords for a given movie ID."""
        return self._request(f"movie/{movie_id}/keywords")

    def genre_list(self) -> Dict[int, str]:
        """Fetch TMDB movie genres as a {genre_id: genre_name} mapping."""
        try:
            data = self._request("genre/movie/list", {"language": "en-US"})
            return {g["id"]: g["name"] for g in data.get("genres", [])}
        except Exception:
            return {}


# Defensive Image & Poster URL Resolvers
def image_url(path: Optional[str], size: str = "w500") -> str:
    """
    Constructs a full TMDB image URL.
    Safely rejects invalid paths and returns fallback.
    """
    if not path or not isinstance(path, str):
        return POSTER_FALLBACK_URL
    clean_path = path.strip()
    if not clean_path or clean_path == "None" or clean_path == "null" or not clean_path.startswith("/"):
        return POSTER_FALLBACK_URL
    return f"{TMDB_IMAGE_BASE_URL}/{size}{clean_path}"


def poster_url(path: Optional[str]) -> str:
    """
    Returns verified poster URL.
    GUARANTEED never to produce .../w500/None or .../w500/.
    Returns '/static/img/poster-fallback.svg' on missing/invalid path.
    """
    return image_url(path, size="w500")


def backdrop_url(path: Optional[str]) -> str:
    """
    Returns verified backdrop URL (w1280).
    If missing or invalid, returns empty string so UI can show a dark gradient fallback.
    """
    if not path or not isinstance(path, str):
        return ""
    clean_path = path.strip()
    if not clean_path or clean_path == "None" or clean_path == "null" or not clean_path.startswith("/"):
        return ""
    return f"{TMDB_IMAGE_BASE_URL}/w1280{clean_path}"


# Singleton client instance
tmdb_client = TMDBClient()
