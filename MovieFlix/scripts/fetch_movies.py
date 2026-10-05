"""
MovieFlix - Data Collection Script
Fetches real movie metadata from TMDB API using discover/movie endpoint,
enriches top titles with credits/keywords, respects rate limits, and saves
raw JSON and processed CSV datasets.
"""

import sys
import os
import json
import time
import argparse
import logging
from pathlib import Path
from typing import List, Dict, Any

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import (
    RAW_MOVIES_JSON,
    PROCESSED_MOVIES_CSV,
    is_tmdb_configured,
)
from tmdb_client import tmdb_client, poster_url, backdrop_url

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("fetch_movies")


def parse_args():
    parser = argparse.ArgumentParser(description="Fetch real movie metadata from TMDB.")
    parser.add_argument(
        "--pages",
        type=int,
        default=20,
        help="Number of pages to fetch from TMDB discover (default: 20, 20 results per page)",
    )
    parser.add_argument(
        "--enrich",
        action="store_true",
        default=True,
        help="Enrich movies with cast, director, and keywords",
    )
    return parser.parse_args()


def fetch_movies(pages: int = 20, enrich: bool = True) -> List[Dict[str, Any]]:
    """
    Queries TMDB discover/movie endpoint across multiple pages.
    Deduplicates and enriches records.
    """
    if not is_tmdb_configured():
        logger.error(
            "TMDB credentials not configured. Please add TMDB_ACCESS_TOKEN or "
            "TMDB_API_KEY to your .env file before running data collection."
        )
        sys.exit(1)

    # Pre-fetch genre mapping to convert genre IDs into human-readable genre strings
    logger.info("Fetching genre taxonomy from TMDB...")
    genre_map = tmdb_client.genre_list()
    logger.info("Retrieved %d genre definitions.", len(genre_map))

    movies_by_id: Dict[int, Dict[str, Any]] = {}

    logger.info("Starting collection of %d pages from TMDB discover/movie...", pages)
    for page in range(1, pages + 1):
        try:
            logger.info("Fetching discover page %d / %d...", page, pages)
            data = tmdb_client.discover_movies(page=page, sort_by="popularity.desc")
            results = data.get("results", [])

            for item in results:
                m_id = item.get("id")
                if not m_id or m_id in movies_by_id:
                    continue

                # Map genre IDs to text names
                genre_names = [genre_map.get(gid, "") for gid in item.get("genre_ids", []) if gid in genre_map]
                genre_str = ", ".join(filter(None, genre_names))

                p_path = item.get("poster_path")
                b_path = item.get("backdrop_path")

                movie_record: Dict[str, Any] = {
                    "id": m_id,
                    "title": item.get("title", ""),
                    "original_title": item.get("original_title", ""),
                    "overview": item.get("overview", "") or "",
                    "release_date": item.get("release_date", "") or "",
                    "vote_average": float(item.get("vote_average", 0.0) or 0.0),
                    "vote_count": int(item.get("vote_count", 0) or 0),
                    "popularity": float(item.get("popularity", 0.0) or 0.0),
                    "poster_path": p_path or "",
                    "poster_url": poster_url(p_path),
                    "backdrop_path": b_path or "",
                    "backdrop_url": backdrop_url(b_path),
                    "genres": genre_str,
                    "keywords": "",
                    "runtime": 0,
                    "original_language": item.get("original_language", "en") or "en",
                    "adult": bool(item.get("adult", False)),
                    "cast": "",
                    "director": "",
                }
                movies_by_id[m_id] = movie_record

            # Polite pacing between discovery pages
            time.sleep(0.2)

        except Exception as exc:
            logger.error("Failed fetching page %d: %s", page, exc)
            time.sleep(1.0)

    movie_list = list(movies_by_id.values())
    logger.info("Successfully discovered %d unique movies.", len(movie_list))

    # Optional metadata enrichment (top movies get cast, director, keywords, runtime)
    if enrich and movie_list:
        logger.info("Enriching movies with credits, keywords, and runtime...")
        # Sort by popularity to prioritize enriching top-viewed movies
        sorted_movies = sorted(movie_list, key=lambda m: m["popularity"], reverse=True)
        # Limit deep enrichment calls to top 200 to keep runtimes fast and stay well within API limits
        enrich_target = sorted_movies[: min(len(sorted_movies), 200)]

        for idx, movie in enumerate(enrich_target, start=1):
            m_id = movie["id"]
            if idx % 20 == 0 or idx == len(enrich_target):
                logger.info("Enriching metadata [%d / %d] (movie ID %d)...", idx, len(enrich_target), m_id)

            try:
                # Fetch credits for cast and director
                credits = tmdb_client.movie_credits(m_id)
                cast_members = [c.get("name", "") for c in credits.get("cast", [])[:5] if c.get("name")]
                movie["cast"] = ", ".join(cast_members)

                directors = [c.get("name", "") for c in credits.get("crew", []) if c.get("job") == "Director"]
                movie["director"] = ", ".join(directors[:2])

                # Fetch keywords
                kw_data = tmdb_client.movie_keywords(m_id)
                kws = [k.get("name", "") for k in kw_data.get("keywords", [])[:8] if k.get("name")]
                movie["keywords"] = ", ".join(kws)

                time.sleep(0.1)
            except Exception as exc:
                logger.debug("Enrichment skipped for movie %d: %s", m_id, exc)

    return movie_list


def save_datasets(movies: List[Dict[str, Any]]):
    """Saves raw JSON dump and initial CSV file."""
    import pandas as pd

    # 1. Save raw JSON
    RAW_MOVIES_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(RAW_MOVIES_JSON, "w", encoding="utf-8") as f:
        json.dump(movies, f, indent=2, ensure_ascii=False)
    logger.info("Raw JSON saved to: %s (%d records)", RAW_MOVIES_JSON, len(movies))

    # 2. Save processed CSV
    PROCESSED_MOVIES_CSV.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(movies)
    df.to_csv(PROCESSED_MOVIES_CSV, index=False, encoding="utf-8")
    logger.info("Processed CSV saved to: %s", PROCESSED_MOVIES_CSV)


def main():
    args = parse_args()
    movies = fetch_movies(pages=args.pages, enrich=args.enrich)
    if movies:
        save_datasets(movies)
        print(f"\nData collection complete! Gathered {len(movies)} movies.")
        print(f"Next step: run python scripts/clean_data.py")
    else:
        logger.warning("No movies were retrieved.")


if __name__ == "__main__":
    main()
