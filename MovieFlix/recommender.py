"""
MovieFlix - Content-Based Recommendation Engine & User Personalization
Computes Cosine Similarity across precomputed TF-IDF feature representations.
Features:
1. Item-to-Item Content-Based Recommendation: recommend_movies(movie_id, top_n=10)
2. User-Profile Personalized Recommendation: recommend_for_user(user_id, top_n=10)
3. Fallback Popularity Recommendations for cold start
Deterministic, reproducible, and mathematically rigorous.
"""

import pickle
import logging
from typing import List, Dict, Any, Optional
import pandas as pd
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from config import (
    TFIDF_MODEL_PKL,
    TFIDF_MATRIX_PKL,
    MOVIE_INDICES_PKL,
    CLEAN_MOVIES_CSV,
    POSTER_FALLBACK_URL,
)
from tmdb_client import poster_url, backdrop_url
import db

logger = logging.getLogger("movieflix.recommender")


class RecommenderEngine:
    """
    Singleton Recommender Engine maintaining in-memory TF-IDF matrix
    and fast lookup structures.
    """

    def __init__(self):
        self.tfidf = None
        self.tfidf_matrix = None
        self.movie_id_to_idx: Dict[int, int] = {}
        self.idx_to_movie_id: Dict[int, int] = {}
        self.movies_df: Optional[pd.DataFrame] = None
        self.is_loaded = False
        self._load_artifacts()

    def _load_artifacts(self) -> bool:
        """Loads serialized TF-IDF model and indices from disk."""
        if TFIDF_MODEL_PKL.exists() and TFIDF_MATRIX_PKL.exists() and MOVIE_INDICES_PKL.exists():
            try:
                with open(TFIDF_MODEL_PKL, "rb") as f:
                    self.tfidf = pickle.load(f)
                with open(TFIDF_MATRIX_PKL, "rb") as f:
                    self.tfidf_matrix = pickle.load(f)
                with open(MOVIE_INDICES_PKL, "rb") as f:
                    lookup_data = pickle.load(f)
                    self.movie_id_to_idx = lookup_data["movie_id_to_idx"]
                    self.idx_to_movie_id = lookup_data["idx_to_movie_id"]
                    self.movies_df = lookup_data.get("movies_df")

                if CLEAN_MOVIES_CSV.exists():
                    try:
                        self.movies_df = pd.read_csv(CLEAN_MOVIES_CSV)
                    except Exception:
                        pass

                self.is_loaded = True
                logger.info("Recommender loaded %d movies from serialized models.", len(self.movie_id_to_idx))
                return True
            except Exception as exc:
                logger.error("Failed to load model artifacts: %s", exc)

        # Fallback: if model files not yet built, check if cleaned CSV exists
        if CLEAN_MOVIES_CSV.exists():
            try:
                logger.info("Models not found; attempting dynamic initialization from cleaned CSV...")
                from scripts.build_features import build_ir_pipeline
                build_ir_pipeline(CLEAN_MOVIES_CSV)
                return self._load_artifacts()
            except Exception as exc:
                logger.warning("Could not auto-generate feature models: %s", exc)

        self.is_loaded = False
        return False

    def reload(self) -> bool:
        """Force reloads model artifacts from disk."""
        return self._load_artifacts()

    def get_movie_by_id(self, movie_id: int) -> Optional[Dict[str, Any]]:
        """Fetch movie details from in-memory index."""
        if not self.is_loaded or self.movies_df is None:
            return None
        matches = self.movies_df[self.movies_df["id"] == movie_id]
        if matches.empty:
            return None
        row = matches.iloc[0].to_dict()
        p_path = row.get("poster_path")
        row["poster_url"] = poster_url(p_path) if p_path and str(p_path) != "nan" else row.get("poster_url", POSTER_FALLBACK_URL)
        if not row["poster_url"] or "None" in str(row["poster_url"]):
            row["poster_url"] = POSTER_FALLBACK_URL
        return row

    def recommend_movies(self, movie_id: int, top_n: int = 10) -> List[Dict[str, Any]]:
        """
        Calculates cosine similarity between the given movie and all movies in the corpus.
        1. Find selected movie
        2. Find its TF-IDF vector
        3. Calculate cosine similarity
        4. Rank movies by similarity
        5. Remove selected movie
        6. Return top N movies
        Deterministic, no random recommendations.
        """
        if not self.is_loaded or self.tfidf_matrix is None or self.movies_df is None:
            logger.warning("Recommender engine is not ready (no models loaded).")
            return []

        try:
            m_id = int(movie_id)
        except (ValueError, TypeError):
            return []

        if m_id not in self.movie_id_to_idx:
            logger.info("Movie ID %d not found in recommender index.", m_id)
            return []

        movie_idx = self.movie_id_to_idx[m_id]

        # Extract feature vector for target movie: shape (1, vocab_size)
        target_vector = self.tfidf_matrix[movie_idx]

        # Calculate cosine similarity with all vectors in corpus: shape (1, num_movies)
        cosine_scores = cosine_similarity(target_vector, self.tfidf_matrix).flatten()

        # Enumerate scores with their index, and filter out the target movie itself
        scored_candidates = [
            (idx, float(score)) for idx, score in enumerate(cosine_scores) if idx != movie_idx
        ]

        # Sort descending by cosine similarity score
        scored_candidates.sort(key=lambda x: x[1], reverse=True)

        top_candidates = scored_candidates[:top_n]
        recommendations = []
        max_score = top_candidates[0][1] if top_candidates and top_candidates[0][1] > 0 else 1.0

        for idx, score in top_candidates:
            cand_id = self.idx_to_movie_id.get(idx)
            if cand_id is None:
                continue

            movie_row = self.movies_df[self.movies_df["id"] == cand_id]
            if movie_row.empty:
                continue

            item = movie_row.iloc[0].to_dict()
            item["similarity_score"] = round(float(score), 4)

            # Normalized match percentage: maps to realistic 70% - 98% range
            if max_score > 0 and score > 0:
                rel_ratio = score / max_score
                match_pct = int(round(72 + (rel_ratio * 26)))
            else:
                match_pct = 60
            item["match_percentage"] = min(99, max(50, match_pct))

            p_path = item.get("poster_path")
            item["poster_url"] = poster_url(p_path) if p_path and str(p_path) != "nan" else item.get("poster_url", POSTER_FALLBACK_URL)
            if not item["poster_url"] or "None" in str(item["poster_url"]):
                item["poster_url"] = POSTER_FALLBACK_URL

            recommendations.append(item)

        return recommendations

    def recommend_for_user(self, user_id: int, top_n: int = 10) -> Dict[str, Any]:
        """
        Generates content-based personalized recommendations for a user
        based on their ratings (weighting high ratings) and watchlist additions.
        Cold-start users receive transparent popularity-based fallback recommendations.
        Returns: {
            'is_personalized': bool,
            'reason': str,
            'recommendations': List[Dict[str, Any]]
        }
        """
        if not self.is_loaded or self.tfidf_matrix is None or self.movies_df is None:
            return {"is_personalized": False, "reason": "Recommender unavailable.", "recommendations": []}

        # Step 1: Collect user ratings and watchlist
        user_ratings = db.get_user_ratings(user_id)
        user_watchlist = db.get_user_watchlist(user_id)

        # Movies to strictly exclude from recommendations (already interacted)
        excluded_ids = set()
        weighted_vectors = []
        weights = []

        # Process rated movies
        for r in user_ratings:
            m_id = int(r["id"])
            excluded_ids.add(m_id)
            score = float(r.get("user_rating", 3.0))

            if m_id in self.movie_id_to_idx and score >= 3.0:
                idx = self.movie_id_to_idx[m_id]
                vec = self.tfidf_matrix[idx].toarray().flatten()
                # Weight formula: positive scale from 3.0 stars upwards
                w = (score - 2.5) * 1.5
                weighted_vectors.append(vec)
                weights.append(w)

        # Process watchlist movies (implicit positive intent, weight = 2.0)
        for w_item in user_watchlist:
            m_id = int(w_item["id"])
            excluded_ids.add(m_id)
            if m_id in self.movie_id_to_idx:
                idx = self.movie_id_to_idx[m_id]
                vec = self.tfidf_matrix[idx].toarray().flatten()
                weighted_vectors.append(vec)
                weights.append(2.0)

        # If user has no positive interactions, fallback to popular titles
        if not weighted_vectors:
            popular_df = self.movies_df.sort_values(
                by=["popularity", "vote_average"], ascending=[False, False]
            )
            # Filter out any excluded items
            popular_candidates = popular_df[~popular_df["id"].isin(excluded_ids)].head(top_n)

            fallback_recs = []
            for _, row in popular_candidates.iterrows():
                item = row.to_dict()
                p_path = item.get("poster_path")
                item["poster_url"] = poster_url(p_path) if p_path and str(p_path) != "nan" else item.get("poster_url", POSTER_FALLBACK_URL)
                if not item["poster_url"] or "None" in str(item["poster_url"]):
                    item["poster_url"] = POSTER_FALLBACK_URL
                item["match_percentage"] = int(min(98, max(75, round(item.get("vote_average", 7.0) * 10))))
                fallback_recs.append(item)

            return {
                "is_personalized": False,
                "reason": "Start rating or adding movies to your watchlist to unlock tailored AI recommendations.",
                "recommendations": fallback_recs,
            }

        # Step 2: Compute synthesized user preference vector
        user_vector = np.average(weighted_vectors, axis=0, weights=weights).reshape(1, -1)

        # Step 3: Compute cosine similarity between user vector and all movies
        user_scores = cosine_similarity(user_vector, self.tfidf_matrix).flatten()

        # Step 4: Rank candidates excluding already interacted movies
        scored_candidates = []
        for idx, score in enumerate(user_scores):
            m_id = self.idx_to_movie_id.get(idx)
            if m_id and m_id not in excluded_ids:
                scored_candidates.append((idx, float(score)))

        scored_candidates.sort(key=lambda x: x[1], reverse=True)
        top_candidates = scored_candidates[:top_n]

        max_score = top_candidates[0][1] if top_candidates and top_candidates[0][1] > 0 else 1.0
        personalized_recs = []

        for idx, score in top_candidates:
            cand_id = self.idx_to_movie_id.get(idx)
            if cand_id is None:
                continue

            movie_row = self.movies_df[self.movies_df["id"] == cand_id]
            if movie_row.empty:
                continue

            item = movie_row.iloc[0].to_dict()
            item["similarity_score"] = round(float(score), 4)

            if max_score > 0 and score > 0:
                rel_ratio = score / max_score
                match_pct = int(round(75 + (rel_ratio * 23)))
            else:
                match_pct = 70
            item["match_percentage"] = min(99, max(50, match_pct))

            p_path = item.get("poster_path")
            item["poster_url"] = poster_url(p_path) if p_path and str(p_path) != "nan" else item.get("poster_url", POSTER_FALLBACK_URL)
            if not item["poster_url"] or "None" in str(item["poster_url"]):
                item["poster_url"] = POSTER_FALLBACK_URL

            personalized_recs.append(item)

        return {
            "is_personalized": True,
            "reason": f"Synthesized from your {len(user_ratings)} rating(s) and {len(user_watchlist)} watchlist item(s).",
            "recommendations": personalized_recs,
        }

    def recommend_by_movie_id(self, movie_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Convenience alias for recommend_movies."""
        return self.recommend_movies(movie_id, top_n=limit)

    def recommend_by_title(self, title: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Finds movie matching title and returns recommendations."""
        if not self.is_loaded or self.movies_df is None or not title:
            return []

        clean_t = str(title).strip().lower()
        exact_match = self.movies_df[self.movies_df["title"].str.lower() == clean_t]
        if not exact_match.empty:
            movie_id = int(exact_match.iloc[0]["id"])
            return self.recommend_movies(movie_id, top_n=limit)

        partial_match = self.movies_df[self.movies_df["title"].str.lower().str.contains(clean_t, regex=False)]
        if not partial_match.empty:
            movie_id = int(partial_match.iloc[0]["id"])
            return self.recommend_movies(movie_id, top_n=limit)

        return []

    def search_movies(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Search movies in local dataset across title, cast, genres, etc."""
        if not self.is_loaded or self.movies_df is None or not query:
            return []

        q = str(query).strip().lower()
        if not q:
            return []

        ALIASES = {
            "srk": "shah rukh khan",
            "ddlj": "dilwale dulhania",
            "k3g": "kabhi khushi",
            "kgf": "k.g.f",
            "rrr": "rrr",
            "nolan": "christopher nolan",
            "tarantino": "quentin tarantino",
        }

        search_terms = [q]
        if q in ALIASES:
            search_terms.append(ALIASES[q])

        search_cols = ["title", "original_title", "overview", "cast", "director", "genres", "keywords"]
        mask = pd.Series(False, index=self.movies_df.index)
        for term in search_terms:
            for col in search_cols:
                if col in self.movies_df.columns:
                    mask |= self.movies_df[col].astype(str).str.lower().str.contains(term, regex=False, na=False)

        results_df = self.movies_df[mask].copy()
        if results_df.empty:
            return []

        results_df = results_df.sort_values(by="popularity", ascending=False).head(limit)

        movies = []
        for _, row in results_df.iterrows():
            item = row.to_dict()
            p_path = item.get("poster_path")
            item["poster_url"] = poster_url(p_path) if p_path and str(p_path) != "nan" else item.get("poster_url", POSTER_FALLBACK_URL)
            if not item["poster_url"] or "None" in str(item["poster_url"]):
                item["poster_url"] = POSTER_FALLBACK_URL
            movies.append(item)

        return movies

    def get_similar_movies(self, movie_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        return self.recommend_movies(movie_id, top_n=limit)


# Global singleton instance
recommender = RecommenderEngine()


# Module-level convenience functions
def recommend_movies(movie_id: int, top_n: int = 10) -> List[Dict[str, Any]]:
    return recommender.recommend_movies(movie_id, top_n=top_n)


def recommend_by_movie_id(movie_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    return recommender.recommend_movies(movie_id, top_n=limit)


def recommend_for_user(user_id: int, top_n: int = 10) -> Dict[str, Any]:
    return recommender.recommend_for_user(user_id, top_n=top_n)


def recommend_by_title(title: str, limit: int = 10) -> List[Dict[str, Any]]:
    return recommender.recommend_by_title(title, limit=limit)


def search_movies(query: str, limit: int = 50) -> List[Dict[str, Any]]:
    return recommender.search_movies(query, limit=limit)


def get_similar_movies(movie_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    return recommender.get_similar_movies(movie_id, limit=limit)
