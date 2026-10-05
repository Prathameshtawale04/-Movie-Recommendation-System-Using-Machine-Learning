"""
MovieFlix - TMDB Connectivity & Authentication Test
Interactive CLI diagnostic script to verify TMDB connectivity, authentication,
and image resolution. Does not expose tokens or secrets.
"""

import sys
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import (
    is_tmdb_v4_configured,
    is_tmdb_v3_configured,
    is_tmdb_configured,
    get_auth_strategy,
    is_env_file_present,
)
from tmdb_client import tmdb_client, poster_url


def run_diagnostic():
    print("=" * 60)
    print("MovieFlix TMDB API Diagnostic")
    print("=" * 60)

    print(f".env file detected:         {is_env_file_present()}")
    print(f"TMDB v4 configured:         {is_tmdb_v4_configured()}")
    print(f"TMDB v3 configured:         {is_tmdb_v3_configured()}")
    print(f"TMDB credential configured: {is_tmdb_configured()}")
    print(f"Active Auth Strategy:       {get_auth_strategy().upper()}")
    print("-" * 60)

    if not is_tmdb_configured():
        print("RESULT: FAILURE")
        print("No TMDB credentials found.")
        print("Please edit .env and set TMDB_ACCESS_TOKEN (v4) or TMDB_API_KEY (v3).")
        return False

    print("Testing live connection with TMDB API...")
    success, message = tmdb_client.test_connection()
    if success:
        print(f"RESULT: SUCCESS - {message}")

        # Fetch sample popular movie
        try:
            sample = tmdb_client.popular_movies(page=1)
            results = sample.get("results", [])
            if results:
                first = results[0]
                print(f"Sample Movie:     '{first.get('title')}' (ID: {first.get('id')})")
                print(f"Release Date:     {first.get('release_date')}")
                print(f"Vote Average:     {first.get('vote_average')}")
                print(f"Verified Poster:  {poster_url(first.get('poster_path'))}")
        except Exception as exc:
            print(f"Notice: Could not fetch sample movie: {exc}")

        print("=" * 60)
        return True
    else:
        print("RESULT: CONNECTION FAILED")
        print(f"Details: {message}")
        print("The TMDB credential was rejected. Check the TMDB API Read Access Token or API Key in .env.")
        print("=" * 60)
        return False


if __name__ == "__main__":
    passed = run_diagnostic()
    sys.exit(0 if passed else 1)
