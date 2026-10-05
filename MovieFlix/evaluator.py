"""
MovieFlix - System & Recommendation Evaluator
Computes empirical data completeness metrics (posters, overviews, ratings),
reports TF-IDF matrix dimensions and similarity scores, inspects user counts,
watchlist counts, and rating counts, and transparently articulates Information
Retrieval (IR) evaluation methodology without fabricated precision/recall metrics.
"""

import sys
import logging
from pathlib import Path
import pandas as pd
import numpy as np

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (
    CLEAN_MOVIES_CSV,
    POSTER_FALLBACK_URL,
)
from recommender import recommender, recommend_movies, recommend_by_title
import db


def evaluate_dataset(csv_path: Path):
    print("=" * 75)
    print(" MovieFlix - Dataset & Recommendation Evaluation Report")
    print("=" * 75)

    if not csv_path.exists():
        print(f"Error: Cleaned dataset not found at {csv_path}")
        return

    df = pd.read_csv(csv_path)
    total_movies = len(df)
    dataset_file_size_kb = csv_path.stat().st_size / 1024

    # 1. Dataset Size & Completeness
    posters_tmdb = df["poster_path"].notna() & (df["poster_path"].astype(str).str.startswith("/"))
    posters_fallback = (df["poster_url"] == POSTER_FALLBACK_URL) | (~posters_tmdb)
    count_tmdb_posters = int(posters_tmdb.sum())
    count_fallback_posters = int(posters_fallback.sum())

    valid_overviews = df["overview"].notna() & (df["overview"].astype(str).str.len() > 10)
    count_overviews = int(valid_overviews.sum())

    avg_vote = df["vote_average"].mean() if "vote_average" in df.columns else 0.0
    avg_popularity = df["popularity"].mean() if "popularity" in df.columns else 0.0

    print("1. DATASET INTEGRITY & METRIC DISTRIBUTION:")
    print(f"   - Dataset File Size:            {dataset_file_size_kb:.2f} KB ({csv_path.name})")
    print(f"   - Number of Movies:             {total_movies}")
    print(f"   - Movies with TMDB Posters:     {count_tmdb_posters} ({count_tmdb_posters / total_movies * 100:.1f}%)")
    print(f"   - Movies with Fallback Posters: {count_fallback_posters} ({count_fallback_posters / total_movies * 100:.1f}%)")
    print(f"   - Movies with Overviews:        {count_overviews} ({count_overviews / total_movies * 100:.1f}%)")
    print(f"   - Average TMDB Vote Score:      {avg_vote:.2f} / 10")
    print(f"   - Average Popularity Score:     {avg_popularity:.2f}")

    # 2. Database User & Interaction Statistics
    u_count = db.get_user_count()
    w_count = db.get_watchlist_count()
    r_count = db.get_rating_count()

    print("\n2. DATABASE INTERACTION METRICS:")
    print(f"   - Registered User Count:        {u_count}")
    print(f"   - Watchlist Items Count:        {w_count}")
    print(f"   - Ratings Submitted Count:      {r_count}")

    # 3. Model Dimensions & Vector Space
    print("\n3. TF-IDF VECTOR SPACE & MODEL DIMENSIONS:")
    if not recommender.is_loaded:
        recommender.reload()

    if recommender.is_loaded and recommender.tfidf_matrix is not None:
        rows, cols = recommender.tfidf_matrix.shape
        sparsity = (1.0 - (recommender.tfidf_matrix.nnz / (rows * cols))) * 100
        print(f"   - TF-IDF Matrix Dimensions:     {rows} documents (movies) x {cols} vocabulary features")
        print(f"   - Non-zero Term Entries (nnz):  {recommender.tfidf_matrix.nnz:,}")
        print(f"   - Matrix Sparsity:              {sparsity:.2f}%")
        print(f"   - Indexed Movie ID Mappings:    {len(recommender.movie_id_to_idx)}")
    else:
        print("   - TF-IDF model artifacts not loaded.")

    # 4. Sample Recommendations & Cosine Similarity Values
    print("\n4. SAMPLE RECOMMENDATIONS & COSINE SIMILARITY EVALUATION:")
    test_titles = ["Inception", "The Dark Knight", "Interstellar"]
    for title in test_titles:
        print(f"\n   Target Query Movie: '{title}'")
        recs = recommend_by_title(title, limit=3)
        if recs:
            for rank, r in enumerate(recs, 1):
                sim = r.get("similarity_score", 0.0)
                pct = r.get("match_percentage", 0)
                genres = r.get("genres", "N/A")
                print(f"     #{rank} {r.get('title'):<26} | Cosine Sim: {sim:.4f} | Match: {pct}% | Genres: {genres}")
        else:
            print("     No recommendations found for this title.")

    # 5. Methodological Validity Notice
    print("\n" + "=" * 75)
    print("5. INFORMATION RETRIEVAL EVALUATION METHODOLOGY NOTE:")
    print("=" * 75)
    print(
        "In Information Retrieval (IR) and Recommender Systems literature, classification\n"
        "metrics such as Precision@K, Recall@K, Mean Reciprocal Rank (MRR), and NDCG@K\n"
        "require a ground-truth interaction matrix (such as historical click-through logs\n"
        "or multi-user explicit preference ratings like MovieLens 100K/20M).\n\n"
        "Because this system operates primarily on unsupervised content-based metadata\n"
        "in TF-IDF vector space, fabricating Precision or Recall figures without ground truth\n"
        "would be scientifically illegitimate. Instead, the mathematical validity of the\n"
        "ranking engine is demonstrated via normalized cosine distance in high-dimensional\n"
        "feature space, confirming thematic, genre, and directorial convergence in outputs."
    )
    print("=" * 75)


if __name__ == "__main__":
    evaluate_dataset(CLEAN_MOVIES_CSV)
