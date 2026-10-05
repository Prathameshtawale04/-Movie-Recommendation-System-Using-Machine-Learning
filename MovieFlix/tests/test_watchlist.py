"""
MovieFlix - Watchlist & Ratings Unit and Integration Tests
Tests:
- Adding titles to watchlist
- Removing titles from watchlist
- Preventing duplicate watchlist entries
- Star ratings submission (1-5 range)
- Rating updates for existing movies
- Unauthenticated access redirection / 401 handling
"""

import pytest
import sys
import uuid
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import app
import db
from auth import hash_password


@pytest.fixture
def client():
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    with app.test_client() as test_client:
        yield test_client


@pytest.fixture
def test_user():
    """Creates a temporary test user in DB for testing interactions."""
    uid = uuid.uuid4().hex[:8]
    email = f"cine_{uid}@test.edu"
    pwd_hash = hash_password("testPass123")
    success, msg, user_id = db.create_user(f"Tester {uid}", email, pwd_hash)
    assert success
    user = db.get_user_by_id(user_id)
    return user


def test_watchlist_requires_auth(client):
    """Accessing watchlist without login redirects to /login."""
    resp = client.get("/watchlist", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_watchlist_add_and_remove_flow(client, test_user):
    """Test full cycle: add movie to watchlist, verify presence, and remove it."""
    with client.session_transaction() as sess:
        sess["user_id"] = test_user["id"]
        sess["user_name"] = test_user["name"]

    movie_id = 27205  # Inception

    # Add to watchlist via form POST
    add_resp = client.post(f"/watchlist/add/{movie_id}", follow_redirects=True)
    assert add_resp.status_code == 200

    # Verify is in watchlist
    assert db.is_in_watchlist(test_user["id"], movie_id) is True

    # Duplicate add attempt should be idempotent
    dup_resp = client.post(f"/watchlist/add/{movie_id}", follow_redirects=True)
    assert dup_resp.status_code == 200
    assert db.is_in_watchlist(test_user["id"], movie_id) is True

    # View watchlist page
    w_page = client.get("/watchlist")
    assert w_page.status_code == 200
    assert b"Inception" in w_page.data

    # Remove from watchlist
    rem_resp = client.post(f"/watchlist/remove/{movie_id}", follow_redirects=True)
    assert rem_resp.status_code == 200
    assert db.is_in_watchlist(test_user["id"], movie_id) is False


def test_watchlist_ajax_json(client, test_user):
    """Test AJAX JSON endpoint for watchlist toggle."""
    with client.session_transaction() as sess:
        sess["user_id"] = test_user["id"]

    movie_id = 155  # The Dark Knight
    res = client.post(
        f"/watchlist/add/{movie_id}",
        json={"movie_id": movie_id},
        headers={"Content-Type": "application/json"}
    )
    assert res.status_code == 200
    json_data = res.get_json()
    assert json_data["status"] == "success"
    assert json_data["in_watchlist"] is True

    # Clean up
    client.post(f"/watchlist/remove/{movie_id}")


def test_movie_rating_submission_and_update(client, test_user):
    """Test rating submission (1-5 stars) and subsequent update."""
    with client.session_transaction() as sess:
        sess["user_id"] = test_user["id"]

    movie_id = 157336  # Interstellar

    # Submit 4 stars
    rate_resp = client.post(
        f"/movie/{movie_id}/rate",
        data={"rating": "4.0"},
        follow_redirects=True
    )
    assert rate_resp.status_code == 200
    assert db.get_user_rating(test_user["id"], movie_id) == 4.0

    # Update to 5 stars
    update_resp = client.post(
        f"/movie/{movie_id}/rate",
        data={"rating": "5.0"},
        follow_redirects=True
    )
    assert update_resp.status_code == 200
    assert db.get_user_rating(test_user["id"], movie_id) == 5.0

    # View ratings page
    ratings_page = client.get("/ratings")
    assert ratings_page.status_code == 200
    assert b"Interstellar" in ratings_page.data


def test_invalid_rating_value_rejected(client, test_user):
    """Ratings outside 1-5 or non-numeric should be rejected."""
    with client.session_transaction() as sess:
        sess["user_id"] = test_user["id"]

    movie_id = 27205

    # Out of range (7 stars)
    resp = client.post(
        f"/movie/{movie_id}/rate",
        json={"rating": 7.0},
        headers={"Content-Type": "application/json"}
    )
    assert resp.status_code == 400
    assert b"Rating must be between 1 and 5" in resp.data
