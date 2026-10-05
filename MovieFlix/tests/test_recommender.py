"""
MovieFlix - Recommender Engine Tests
Verifies TF-IDF cosine similarity ranking, source movie exclusion,
nonexistent ID handling, and title search functionality.
"""

import pytest
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from recommender import (
    recommender,
    recommend_by_movie_id,
    recommend_by_title,
    search_movies,
)


@pytest.fixture(scope="module", autouse=True)
def ensure_engine_loaded():
    """Ensure models are loaded before running recommender tests."""
    if not recommender.is_loaded:
        recommender.reload()
    assert recommender.is_loaded is True, "Recommender model failed to load for tests."


def test_recommendation_excludes_source_movie():
    """CRITICAL: Output must never recommend the queried movie itself."""
    source_id = 27205  # Inception
    recs = recommend_by_movie_id(source_id, limit=10)
    assert len(recs) > 0

    recommended_ids = [r["id"] for r in recs]
    assert source_id not in recommended_ids


def test_recommendation_ranking_order():
    """Recommendations must be sorted descending by similarity score."""
    source_id = 155  # The Dark Knight
    recs = recommend_by_movie_id(source_id, limit=5)
    assert len(recs) >= 2

    scores = [r["similarity_score"] for r in recs]
    for i in range(len(scores) - 1):
        assert scores[i] >= scores[i + 1], f"Rank inversion at {i}: {scores[i]} < {scores[i+1]}"


def test_nonexistent_movie_id():
    """Querying an unknown movie ID must return an empty list gracefully."""
    recs = recommend_by_movie_id(999999999, limit=5)
    assert recs == []

    # Invalid input formats
    assert recommend_by_movie_id(None) == []
    assert recommend_by_movie_id("not-a-number") == []


def test_recommend_by_title():
    """Recommender can locate movie by title and generate recommendations."""
    recs = recommend_by_title("Interstellar", limit=4)
    assert len(recs) > 0
    # Must not contain Interstellar in recommendations
    titles = [r["title"].lower() for r in recs]
    assert "interstellar" not in titles


def test_search_movies_query():
    """Search matches words in title or overview and returns ranked list."""
    results = search_movies("Matrix")
    assert len(results) > 0
    assert any("Matrix" in r["title"] for r in results)

    # Empty search query returns empty list
    assert search_movies("") == []
    assert search_movies("   ") == []
