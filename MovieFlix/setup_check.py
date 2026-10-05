"""
MovieFlix - System Diagnostics & Setup Verification
Verifies Python version, dependencies, environment configuration,
TMDB credentials, MySQL connectivity, database tables, datasets,
recommendation model artifacts, and poster fallbacks.
Clearly displays PASS, FAIL, and WARNING statuses without exposing secrets.
"""

import sys
import os
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (
    BASE_DIR,
    is_env_file_present,
    is_tmdb_v4_configured,
    is_tmdb_v3_configured,
    is_tmdb_configured,
    MYSQL_HOST,
    MYSQL_PORT,
    MYSQL_USER,
    MYSQL_DATABASE,
    CLEAN_MOVIES_CSV,
    TFIDF_MODEL_PKL,
    TFIDF_MATRIX_PKL,
    MOVIE_INDICES_PKL,
    POSTER_FALLBACK_URL,
    IMG_DIR,
)
from tmdb_client import tmdb_client
import db


def print_status(status: str, check_name: str, detail: str = ""):
    colors = {
        "PASS": "\033[92m[PASS]\033[0m",
        "FAIL": "\033[91m[FAIL]\033[0m",
        "WARNING": "\033[93m[WARNING]\033[0m",
    }
    label = colors.get(status, f"[{status}]")
    if detail:
        print(f" {label:<18} {check_name:<30} -> {detail}")
    else:
        print(f" {label:<18} {check_name}")


def main():
    print("=" * 75)
    print(" MovieFlix - Comprehensive System Setup & Health Check")
    print("=" * 75)
    print(f" Working Directory: {BASE_DIR}\n")

    overall_pass = True

    # 1. Python Version
    v = sys.version_info
    py_ver = f"{v.major}.{v.minor}.{v.micro}"
    if v.major >= 3 and v.minor >= 10:
        print_status("PASS", "Python Version", f"v{py_ver} (>= 3.10 required)")
    else:
        print_status("FAIL", "Python Version", f"v{py_ver} is too old. Upgrade to Python 3.10+")
        overall_pass = False

    # 2. Required Packages
    required_pkgs = [
        ("flask", "Flask"),
        ("flask_wtf", "Flask-WTF"),
        ("wtforms", "WTForms"),
        ("werkzeug", "Werkzeug"),
        ("requests", "Requests"),
        ("dotenv", "python-dotenv"),
        ("pandas", "Pandas"),
        ("numpy", "NumPy"),
        ("sklearn", "Scikit-Learn"),
        ("bs4", "BeautifulSoup4"),
        ("mysql.connector", "mysql-connector-python"),
        ("pytest", "Pytest"),
    ]
    pkg_missing = []
    for mod_name, pkg_name in required_pkgs:
        try:
            __import__(mod_name)
        except ImportError:
            pkg_missing.append(pkg_name)

    if not pkg_missing:
        print_status("PASS", "Required Packages", f"All {len(required_pkgs)} core dependencies installed")
    else:
        print_status("FAIL", "Required Packages", f"Missing: {', '.join(pkg_missing)}")
        overall_pass = False

    # 3. Environment File (.env)
    if is_env_file_present():
        print_status("PASS", ".env Configuration", "Environment configuration file detected")
    else:
        print_status("WARNING", ".env Configuration", ".env missing. Run: copy .env.example .env")

    # 4. TMDB Credentials
    v4 = is_tmdb_v4_configured()
    v3 = is_tmdb_v3_configured()
    if v4:
        print_status("PASS", "TMDB Credentials", "Configured (TMDB v4 Read Access Token)")
    elif v3:
        print_status("PASS", "TMDB Credentials", "Configured (TMDB v3 API Key)")
    else:
        print_status("WARNING", "TMDB Credentials", "Not configured in .env (offline catalog mode active)")

    # 5. TMDB API Connectivity
    if is_tmdb_configured():
        ok, msg = tmdb_client.test_connection()
        if ok:
            print_status("PASS", "TMDB API Connectivity", "Connected to TMDB API endpoints successfully")
        else:
            print_status("WARNING", "TMDB API Connectivity", f"Failed: {msg}")
    else:
        print_status("WARNING", "TMDB API Connectivity", "Skipped (no API credentials provided)")

    # 6. Database Connectivity
    mysql_ok, mysql_msg = db.test_db_connection()
    if mysql_ok:
        print_status("PASS", "Database Connectivity", f"{mysql_msg}")
    else:
        print_status("WARNING", "Database Connectivity", f"{mysql_msg} (Fallback to SQLite active)")

    # 7. Database Tables
    db_init_ok = db.init_db()
    if db_init_ok:
        m_count = db.get_movie_count()
        u_count = db.get_user_count()
        w_count = db.get_watchlist_count()
        r_count = db.get_rating_count()
        print_status("PASS", "Database Tables", f"movies ({m_count}), users ({u_count}), watchlist ({w_count}), ratings ({r_count})")
    else:
        print_status("WARNING", "Database Tables", "Could not verify all tables")

    # 8. Movie Dataset
    if CLEAN_MOVIES_CSV.exists():
        import pandas as pd
        df = pd.read_csv(CLEAN_MOVIES_CSV)
        print_status("PASS", "Movie Dataset", f"{CLEAN_MOVIES_CSV.name} contains {len(df)} cleaned titles")
    else:
        print_status("FAIL", "Movie Dataset", f"Cleaned dataset not found at {CLEAN_MOVIES_CSV}")
        overall_pass = False

    # 9. Recommendation Model Artifacts
    models_ready = TFIDF_MODEL_PKL.exists() and TFIDF_MATRIX_PKL.exists() and MOVIE_INDICES_PKL.exists()
    if models_ready:
        print_status("PASS", "Recommendation Model", "Serialized TF-IDF vectorizer, matrix, and indices verified")
    else:
        print_status("WARNING", "Recommendation Model", "Model artifacts missing. Run: python scripts/build_features.py")

    # 10. Poster Configuration
    fallback_file = IMG_DIR / "poster-fallback.svg"
    if fallback_file.exists():
        print_status("PASS", "Poster Configuration", f"Fallback asset verified at {fallback_file.name}")
    else:
        print_status("FAIL", "Poster Configuration", f"Missing fallback SVG at {fallback_file}")
        overall_pass = False

    print("\n" + "=" * 75)
    if overall_pass:
        print(" [SUMMARY] Setup Check PASSED! System is ready to run MovieFlix.")
        print(" Launch application: python app.py")
    else:
        print(" [SUMMARY] Setup Check FAILED. Please resolve errors listed above.")
    print("=" * 75)


if __name__ == "__main__":
    main()
