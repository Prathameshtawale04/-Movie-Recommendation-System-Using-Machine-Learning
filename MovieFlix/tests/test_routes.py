"""
MovieFlix - Web Route & API Integration Tests
Tests Flask endpoints, Jinja template rendering, JSON schemas,
and HTTP status codes using the Flask test client.
"""

import pytest
import sys
import json
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import app
from recommender import recommender


@pytest.fixture
def client():
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    if not recommender.is_loaded:
        recommender.reload()
    with app.test_client() as test_client:
        yield test_client


def test_home_page_route(client):
    """GET / should render the Netflix-style homepage with 200 OK."""
    response = client.get("/")
    assert response.status_code == 200
    assert b"MOVIE" in response.data and b"FLIX" in response.data
    assert b"Trending Now" in response.data or b"TOP SPOTLIGHT" in response.data


def test_search_route_with_query(client):
    """GET /search?q=Batman should return matching results."""
    response = client.get("/search?q=Batman")
    assert response.status_code == 200
    assert b"Batman" in response.data


def test_search_route_empty_query(client):
    """GET /search without query should display search page without error."""
    response = client.get("/search")
    assert response.status_code == 200
    assert b"Search" in response.data


def test_movie_details_route_existing(client):
    """GET /movie/<id> for valid movie should render details and recommendations."""
    response = client.get("/movie/27205")  # Inception
    assert response.status_code == 200
    assert b"Inception" in response.data
    assert b"Movies Like This" in response.data or b"Because you liked" in response.data


def test_movie_details_route_404(client):
    """GET /movie/<invalid_id> should render friendly 404 error page."""
    response = client.get("/movie/99999999")
    assert response.status_code == 404
    assert b"404" in response.data


def test_recommendations_route_existing(client):
    """GET /recommendations/<id> should render dedicated similarity view."""
    response = client.get("/recommendations/27205")
    assert response.status_code == 200
    assert b"Inception" in response.data
    assert b"Because You Watched" in response.data or b"Recommendations" in response.data


def test_health_check_api(client):
    """GET /health must return JSON with healthy status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["status"] == "healthy"
    assert "recommender" in data
    assert data["recommender"]["loaded"] is True


def test_api_movies_list(client):
    """GET /api/movies should return JSON movie list."""
    response = client.get("/api/movies?limit=5")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["status"] == "success"
    assert len(data["results"]) <= 5
    if len(data["results"]) > 0:
        first = data["results"][0]
        assert "id" in first
        assert "title" in first
        assert "poster_url" in first


def test_api_search_endpoint(client):
    """GET /api/search?q=Dark should return JSON matches."""
    response = client.get("/api/search?q=Dark")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["status"] == "success"
    assert data["count"] > 0


def test_api_search_empty_query(client):
    """GET /api/search without query should return 400 Bad Request."""
    response = client.get("/api/search")
    assert response.status_code == 400
    data = json.loads(response.data)
    assert data["status"] == "error"


def test_api_recommendations_endpoint(client):
    """GET /api/recommendations/<id> should return ranked recommendations."""
    response = client.get("/api/recommendations/27205?limit=3")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["status"] == "success"
    assert data["source_movie_id"] == 27205
    assert len(data["recommendations"]) <= 3
    if len(data["recommendations"]) > 0:
        assert "similarity_score" in data["recommendations"][0]
        assert "match_percentage" in data["recommendations"][0]
