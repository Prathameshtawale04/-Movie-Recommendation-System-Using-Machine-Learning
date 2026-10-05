"""
MovieFlix - Configuration Module
Manages environment variables, authentication flags, database configuration,
and path constants. Never exposes raw credentials or prints secrets.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Resolve project base directory
BASE_DIR = Path(__file__).resolve().parent

# Load .env file from project root if it exists
ENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH)

# Directory Paths
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
MODELS_DIR = BASE_DIR / "models"
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
IMG_DIR = STATIC_DIR / "img"

# Ensure runtime directories exist
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)

# Processed file paths
RAW_MOVIES_JSON = RAW_DATA_DIR / "tmdb_movies.json"
PROCESSED_MOVIES_CSV = PROCESSED_DATA_DIR / "movies.csv"
CLEAN_MOVIES_CSV = PROCESSED_DATA_DIR / "movies_clean.csv"
TFIDF_MODEL_PKL = MODELS_DIR / "tfidf_model.pkl"
TFIDF_MATRIX_PKL = MODELS_DIR / "tfidf_matrix.pkl"
MOVIE_INDICES_PKL = MODELS_DIR / "movie_indices.pkl"
USERS_DATA_JSON = DATA_DIR / "users.json"

# Fallback poster asset
POSTER_FALLBACK_URL = "/static/img/poster-fallback.svg"

# TMDB Authentication
TMDB_ACCESS_TOKEN = os.getenv("TMDB_ACCESS_TOKEN", "").strip()
TMDB_API_KEY = os.getenv("TMDB_API_KEY", "").strip()
TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p"

# MySQL Configuration
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost").strip()
MYSQL_PORT = int(os.getenv("MYSQL_PORT", 3306))
MYSQL_USER = os.getenv("MYSQL_USER", "root").strip()
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "movieflix").strip()

# Flask Configuration
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "movieflix-dev-secret-key-change-in-prod")
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "False").lower() in ("true", "1", "yes")
FLASK_PORT = int(os.getenv("FLASK_PORT", 5000))


def is_tmdb_v4_configured() -> bool:
    """Return True if a non-empty TMDB v4 Read Access Token is configured."""
    return bool(TMDB_ACCESS_TOKEN)


def is_tmdb_v3_configured() -> bool:
    """Return True if a non-empty TMDB v3 API Key is configured."""
    return bool(TMDB_API_KEY)


def is_tmdb_configured() -> bool:
    """Return True if either v4 access token or v3 API key is configured."""
    return is_tmdb_v4_configured() or is_tmdb_v3_configured()


def is_env_file_present() -> bool:
    """Return True if .env file exists on disk."""
    return ENV_PATH.exists()


def get_auth_strategy() -> str:
    """
    Determine TMDB authentication strategy.
    Prioritizes v4 Bearer Token over v3 API Key.
    Returns: 'v4', 'v3', or 'none'
    """
    if is_tmdb_v4_configured():
        return "v4"
    if is_tmdb_v3_configured():
        return "v3"
    return "none"


def get_safe_diagnostic() -> dict:
    """
    Produce safe diagnostic dictionary for logs and setup checks.
    NEVER returns or exposes credentials.
    """
    return {
        "env_exists": is_env_file_present(),
        "tmdb_v4_configured": is_tmdb_v4_configured(),
        "tmdb_v3_configured": is_tmdb_v3_configured(),
        "tmdb_credential_configured": is_tmdb_configured(),
        "auth_strategy": get_auth_strategy(),
        "mysql_host": MYSQL_HOST,
        "mysql_port": MYSQL_PORT,
        "mysql_user": MYSQL_USER,
        "mysql_database": MYSQL_DATABASE,
        "mysql_password_configured": bool(MYSQL_PASSWORD),
    }
