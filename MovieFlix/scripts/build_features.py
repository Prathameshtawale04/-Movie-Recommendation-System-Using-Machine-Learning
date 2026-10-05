"""
MovieFlix - Information Retrieval (IR) Feature Engineering
Constructs textual metadata representation ("soup"), fits a TF-IDF Vectorizer
with unigrams and bigrams, computes the sparse term-document matrix, and
serializes the trained model artifacts to models/ for instant runtime retrieval.
"""

import sys
import re
import pickle
import logging
from pathlib import Path
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import (
    CLEAN_MOVIES_CSV,
    TFIDF_MODEL_PKL,
    TFIDF_MATRIX_PKL,
    MOVIE_INDICES_PKL,
    MODELS_DIR,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("build_features")


def sanitize_text(text: str) -> str:
    """Removes non-alphanumeric noise while preserving spacing."""
    if not text:
        return ""
    # Replace punctuation with spaces and lowercase
    cleaned = re.sub(r"[^\w\s]", " ", str(text).lower())
    return " ".join(cleaned.split())


def create_metadata_soup(row: pd.Series) -> str:
    """
    Combines core textual features into a rich document representation.
    Emphasizes genres, director, and keywords by slight repetition to give
    them proportional salience alongside the lengthier overview.
    """
    title = sanitize_text(row.get("title", ""))
    orig_title = sanitize_text(row.get("original_title", ""))
    overview = sanitize_text(row.get("overview", ""))

    # Normalize comma-separated tags
    genres = " ".join([sanitize_text(g) for g in str(row.get("genres", "")).split(",") if g.strip()])
    keywords = " ".join([sanitize_text(k) for k in str(row.get("keywords", "")).split(",") if k.strip()])
    cast = " ".join([sanitize_text(c) for c in str(row.get("cast", "")).split(",") if c.strip()])
    director = sanitize_text(row.get("director", ""))

    # Feature combination: overview provides semantic context;
    # genres, director, and keywords reinforce thematic cohesion.
    soup_parts = [
        title,
        orig_title,
        overview,
        genres,
        genres,       # Boost genre weight
        keywords,
        keywords,     # Boost thematic keyword weight
        director,
        director,     # Boost directorial style weight
        cast,
    ]
    return " ".join([part for part in soup_parts if part])


def build_ir_pipeline(csv_path: Path):
    """
    Reads cleaned movie dataset, constructs metadata representations,
    computes TF-IDF vectorization, and serializes artifacts.
    """
    if not csv_path.exists():
        logger.error("Cleaned dataset not found at: %s. Run scripts/clean_data.py first.", csv_path)
        sys.exit(1)

    logger.info("Loading cleaned movies from: %s", csv_path)
    df = pd.read_csv(csv_path)

    if df.empty:
        logger.error("Dataset is empty. Cannot build TF-IDF model.")
        sys.exit(1)

    logger.info("Constructing metadata soup for %d movies...", len(df))
    df["soup"] = df.apply(create_metadata_soup, axis=1)

    logger.info("Initializing TfidfVectorizer (stop_words='english', ngram_range=(1, 2), max_features=7500)...")
    tfidf = TfidfVectorizer(
        stop_words="english",
        ngram_range=(1, 2),
        max_features=7500,
        sublinear_tf=True,
        norm="l2",
    )

    logger.info("Fitting TF-IDF vectorizer and transforming corpus...")
    tfidf_matrix = tfidf.fit_transform(df["soup"])
    logger.info("TF-IDF matrix generated: %d documents x %d vocabulary terms.",
                tfidf_matrix.shape[0], tfidf_matrix.shape[1])

    # Build bidirectional lookup index: movie_id -> matrix row index
    movie_id_to_idx = {int(row["id"]): idx for idx, row in df.iterrows()}
    idx_to_movie_id = {idx: int(row["id"]) for idx, row in df.iterrows()}

    saved_cols = [
        "id", "title", "original_title", "overview", "release_date",
        "vote_average", "vote_count", "popularity", "poster_url",
        "backdrop_url", "genres", "runtime", "cast", "director", "keywords"
    ]
    avail_cols = [c for c in saved_cols if c in df.columns]

    lookup_data = {
        "movie_id_to_idx": movie_id_to_idx,
        "idx_to_movie_id": idx_to_movie_id,
        "movies_df": df[avail_cols].copy(),
    }

    # Ensure models directory exists
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("Serializing model artifacts to %s...", MODELS_DIR)

    with open(TFIDF_MODEL_PKL, "wb") as f:
        pickle.dump(tfidf, f, protocol=pickle.HIGHEST_PROTOCOL)

    with open(TFIDF_MATRIX_PKL, "wb") as f:
        pickle.dump(tfidf_matrix, f, protocol=pickle.HIGHEST_PROTOCOL)

    with open(MOVIE_INDICES_PKL, "wb") as f:
        pickle.dump(lookup_data, f, protocol=pickle.HIGHEST_PROTOCOL)

    logger.info("Saved: %s", TFIDF_MODEL_PKL)
    logger.info("Saved: %s", TFIDF_MATRIX_PKL)
    logger.info("Saved: %s", MOVIE_INDICES_PKL)
    logger.info("IR feature engineering completed successfully!")


def main():
    logger.info("=" * 60)
    logger.info("MovieFlix - Building TF-IDF Features & Vector Index")
    logger.info("=" * 60)
    build_ir_pipeline(CLEAN_MOVIES_CSV)


if __name__ == "__main__":
    main()
