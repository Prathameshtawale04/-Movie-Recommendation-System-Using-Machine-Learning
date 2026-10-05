"""
MovieFlix - Automated TMDB Poster Validator & Resolver
Scans all movies in raw and processed catalogs, verifies poster accessibility via HTTP HEAD,
and automatically extracts real, working TMDB poster images from official pages.
"""

import sys
import json
import logging
import re
import urllib.parse
from pathlib import Path
import concurrent.futures
import requests
import pandas as pd

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("fix_posters")

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_JSON = BASE_DIR / "data" / "raw" / "tmdb_movies.json"
CLEAN_CSV = BASE_DIR / "data" / "processed" / "movies_clean.csv"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9"
}

def is_working_image(url: str) -> bool:
    if not url or not str(url).startswith("http"):
        return False
    try:
        r = requests.head(url, headers=HEADERS, timeout=4, allow_redirects=True)
        return r.status_code == 200
    except Exception:
        return False


def resolve_tmdb_poster(movie_id: int, title: str):
    """
    Attempts to retrieve authentic working TMDB poster path.
    1. Direct TMDB movie page
    2. TMDB search page by title
    """
    # Attempt 1: Direct movie page
    try:
        url = f"https://www.themoviedb.org/movie/{movie_id}"
        r = requests.get(url, headers=HEADERS, timeout=8)
        if r.status_code == 200:
            m = re.search(r'/t/p/w[0-9_a-z\(\)]+/([a-zA-Z0-9_\.]+\.jpg)', r.text)
            if m:
                path = f"/{m.group(1)}"
                full_url = f"https://image.tmdb.org/t/p/w500{path}"
                if is_working_image(full_url):
                    return path, full_url
    except Exception:
        pass

    # Attempt 2: Search by title
    try:
        q = urllib.parse.quote(title)
        url = f"https://www.themoviedb.org/search/movie?query={q}"
        r = requests.get(url, headers=HEADERS, timeout=8)
        if r.status_code == 200:
            m = re.search(r'/t/p/w[0-9_a-z\(\)]+/([a-zA-Z0-9_\.]+\.jpg)', r.text)
            if m:
                path = f"/{m.group(1)}"
                full_url = f"https://image.tmdb.org/t/p/w500{path}"
                if is_working_image(full_url):
                    return path, full_url
    except Exception:
        pass

    return None, None


def process_movie(movie: dict):
    mid = movie.get("id")
    title = movie.get("title", "Unknown")
    current_url = movie.get("poster_url")

    # If poster URL already works, keep it
    if is_working_image(current_url):
        return movie, False

    logger.info("Resolving poster for ID %s: '%s'...", mid, title)
    new_path, new_url = resolve_tmdb_poster(mid, title)

    if new_url:
        movie["poster_path"] = new_path
        movie["poster_url"] = new_url
        logger.info("  -> FIXED '%s': %s", title, new_url)
        return movie, True
    else:
        logger.warning("  -> COULD NOT RESOLVE '%s' (keeping fallback)", title)
        movie["poster_path"] = None
        movie["poster_url"] = "/static/img/poster-fallback.svg"
        return movie, False


def main():
    logger.info("Starting TMDB Poster Resolution Pipeline...")
    
    if not RAW_JSON.exists():
        logger.error("Raw movies JSON not found at %s", RAW_JSON)
        sys.exit(1)

    with open(RAW_JSON, "r", encoding="utf-8") as f:
        movies = json.load(f)

    logger.info("Scanning %d movies in catalog for non-working posters...", len(movies))

    fixed_count = 0
    updated_movies = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
        futures = [executor.submit(process_movie, m) for m in movies]
        for future in concurrent.futures.as_completed(futures):
            res_movie, was_fixed = future.result()
            updated_movies.append(res_movie)
            if was_fixed:
                fixed_count += 1

    # Preserve order by ID
    movie_id_order = {m.get("id"): idx for idx, m in enumerate(movies)}
    updated_movies.sort(key=lambda m: movie_id_order.get(m.get("id"), 9999))

    # Save to raw JSON
    with open(RAW_JSON, "w", encoding="utf-8") as f:
        json.dump(updated_movies, f, indent=2, ensure_ascii=False)
    logger.info("Saved updated raw catalog to: %s", RAW_JSON)

    # Save to processed CSV
    if CLEAN_CSV.exists():
        df = pd.read_csv(CLEAN_CSV)
        # Update poster_path and poster_url in DataFrame
        url_map = {m["id"]: m.get("poster_url") for m in updated_movies}
        path_map = {m["id"]: m.get("poster_path") for m in updated_movies}
        df["poster_url"] = df["id"].map(url_map).fillna(df["poster_url"])
        df["poster_path"] = df["id"].map(path_map).fillna(df["poster_path"])
        df.to_csv(CLEAN_CSV, index=False, encoding="utf-8")
        logger.info("Saved updated processed CSV to: %s", CLEAN_CSV)

    logger.info("Poster Resolution Pipeline Completed!")
    logger.info("Summary: %d movies updated with verified, authentic TMDB posters.", fixed_count)


if __name__ == "__main__":
    main()
