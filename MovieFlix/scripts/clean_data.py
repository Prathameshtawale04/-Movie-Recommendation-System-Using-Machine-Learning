"""
MovieFlix - Data Cleaning Pipeline
Cleans and normalizes raw movie data using Pandas:
- Duplicate removal based on unique TMDB movie ID
- Missing value imputation and normalization
- Text normalization, whitespace cleanup, and string sanitization
- Date normalization to standard ISO YYYY-MM-DD
- Strict poster path and URL verification (guarding against /None)
- Numeric type casting (vote_average, vote_count, popularity, runtime)
- Empty overview fallback handling
Outputs cleaned dataset to data/processed/movies_clean.csv.
"""

import sys
import logging
from pathlib import Path
from typing import Any
import pandas as pd
import numpy as np

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import (
    PROCESSED_MOVIES_CSV,
    CLEAN_MOVIES_CSV,
    RAW_MOVIES_JSON,
    POSTER_FALLBACK_URL,
)
from tmdb_client import poster_url, backdrop_url

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("clean_data")


def clean_text_field(text: Any) -> str:
    """Strip whitespace and collapse multiple internal spaces."""
    if pd.isna(text) or text is None:
        return ""
    val = str(text).strip()
    return " ".join(val.split())


def clean_date_field(date_val: Any) -> str:
    """Normalize date strings to standard YYYY-MM-DD format."""
    if pd.isna(date_val) or not date_val:
        return ""
    val_str = str(date_val).strip()
    # Check basic date format
    try:
        dt = pd.to_datetime(val_str, errors="coerce")
        if pd.notna(dt):
            return dt.strftime("%Y-%m-%d")
    except Exception:
        pass
    return ""


def clean_poster_path(path_val: Any) -> str:
    """Validate and clean poster path, ensuring valid leading slash."""
    if pd.isna(path_val) or not path_val:
        return ""
    clean = str(path_val).strip()
    if clean in ("None", "null", "none", "nan") or not clean.startswith("/"):
        return ""
    return clean


def clean_movies(input_df: pd.DataFrame) -> pd.DataFrame:
    """
    Core data cleaning transformations on DataFrame.
    """
    logger.info("Input dataset contains %d records.", len(input_df))

    df = input_df.copy()

    # Step 1: Ensure required columns exist
    expected_cols = [
        "id", "title", "original_title", "overview", "release_date",
        "vote_average", "vote_count", "popularity", "poster_path",
        "backdrop_path", "genres", "keywords", "runtime",
        "original_language", "adult", "cast", "director"
    ]
    for col in expected_cols:
        if col not in df.columns:
            df[col] = ""

    # Step 2: Remove duplicate movie records based on 'id'
    initial_count = len(df)
    df["id"] = pd.to_numeric(df["id"], errors="coerce")
    df = df.dropna(subset=["id"])
    df["id"] = df["id"].astype(int)
    df = df.drop_duplicates(subset=["id"], keep="first")
    duplicates_removed = initial_count - len(df)
    logger.info("Removed %d duplicate/invalid ID records. Remaining: %d", duplicates_removed, len(df))

    # Step 3: Text Normalization and whitespace cleanup
    text_cols = ["title", "original_title", "overview", "genres", "keywords", "cast", "director", "original_language"]
    for col in text_cols:
        df[col] = df[col].apply(clean_text_field)

    # Filter out entries where title is missing or blank
    df = df[df["title"].str.len() > 0]

    # Step 4: Empty Overview handling
    df["overview"] = df["overview"].apply(
        lambda ov: ov if len(ov) > 5 else "No comprehensive overview available for this title."
    )

    # Step 5: Date Normalization
    df["release_date"] = df["release_date"].apply(clean_date_field)

    # Step 6: Defensive Poster & Backdrop URL Resolution
    df["poster_path"] = df["poster_path"].apply(clean_poster_path)
    df["backdrop_path"] = df["backdrop_path"].apply(clean_poster_path)

    # Generate verified full URLs
    df["poster_url"] = df["poster_path"].apply(poster_url)
    df["backdrop_url"] = df["backdrop_path"].apply(backdrop_url)

    # Step 7: Numeric Type Conversion and bounds verification
    df["vote_average"] = pd.to_numeric(df["vote_average"], errors="coerce").fillna(0.0).clip(0.0, 10.0).round(1)
    df["vote_count"] = pd.to_numeric(df["vote_count"], errors="coerce").fillna(0).astype(int)
    df["popularity"] = pd.to_numeric(df["popularity"], errors="coerce").fillna(0.0).round(2)
    df["runtime"] = pd.to_numeric(df["runtime"], errors="coerce").fillna(0).astype(int)
    df["adult"] = df["adult"].astype(bool)

    # Reset index cleanly
    df = df.reset_index(drop=True)
    logger.info("Cleaning completed. Final cleaned movie count: %d", len(df))
    return df


def main():
    logger.info("=" * 60)
    logger.info("MovieFlix - Starting Data Cleaning Pipeline")
    logger.info("=" * 60)

    # Determine input source
    if PROCESSED_MOVIES_CSV.exists():
        logger.info("Reading dataset from: %s", PROCESSED_MOVIES_CSV)
        df_raw = pd.read_csv(PROCESSED_MOVIES_CSV)
    elif RAW_MOVIES_JSON.exists():
        logger.info("Reading dataset from raw JSON: %s", RAW_MOVIES_JSON)
        df_raw = pd.read_json(RAW_MOVIES_JSON)
    else:
        logger.error(
            "No movie dataset found in data/processed/movies.csv or data/raw/tmdb_movies.json. "
            "Please run 'python scripts/fetch_movies.py' first to collect TMDB data."
        )
        sys.exit(1)

    cleaned_df = clean_movies(df_raw)

    # Save to data/processed/movies_clean.csv
    CLEAN_MOVIES_CSV.parent.mkdir(parents=True, exist_ok=True)
    cleaned_df.to_csv(CLEAN_MOVIES_CSV, index=False, encoding="utf-8")
    logger.info("Saved cleaned dataset to: %s", CLEAN_MOVIES_CSV)

    # Summary statistics
    posters_with_path = (cleaned_df["poster_path"] != "").sum()
    posters_fallback = (cleaned_df["poster_url"] == POSTER_FALLBACK_URL).sum()
    logger.info("Summary: %d movies | %d with TMDB poster | %d using fallback",
                len(cleaned_df), posters_with_path, posters_fallback)


if __name__ == "__main__":
    main()
