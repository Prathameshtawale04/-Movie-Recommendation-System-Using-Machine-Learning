"""
MovieFlix - User Authentication & Session Tests
Tests registration, password hashing, login verification, duplicate checking,
session persistence, and logout workflows.
"""

import pytest
import sys
import uuid
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import app
import db
import auth


@pytest.fixture
def client():
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    with app.test_client() as test_client:
        yield test_client


def test_user_registration_and_login_flow(client):
    """Verifies end-to-end user registration and subsequent login."""
    uid = uuid.uuid4().hex[:8]
    unique_name = f"Cinephile {uid}"
    unique_email = f"cinephile_{uid}@example.com"
    raw_password = "superSecretPassword123"

    # Step 1: Render Registration page
    resp = client.get("/register")
    assert resp.status_code == 200
    assert b"Create Account" in resp.data

    # Step 2: Register user
    reg_resp = client.post("/register", data={
        "name": unique_name,
        "email": unique_email,
        "password": raw_password,
        "confirm_password": raw_password,
    }, follow_redirects=True)
    assert reg_resp.status_code == 200
    assert b"Registration successful" in reg_resp.data or b"Please sign in" in reg_resp.data

    # Step 3: Login with correct credentials
    login_resp = client.post("/login", data={
        "email": unique_email,
        "password": raw_password,
    }, follow_redirects=True)
    assert login_resp.status_code == 200
    assert b"Welcome back" in login_resp.data

    # Step 4: Logout
    logout_resp = client.post("/logout", follow_redirects=True)
    assert logout_resp.status_code == 200
    assert b"signed out" in logout_resp.data


def test_duplicate_registration_rejected(client):
    """Duplicate email registration must be rejected."""
    uid = uuid.uuid4().hex[:8]
    unique_email = f"dup_{uid}@example.com"
    password = "password123"

    # First registration
    client.post("/register", data={
        "name": "First User",
        "email": unique_email,
        "password": password,
        "confirm_password": password,
    })

    # Second registration with same email
    dup_resp = client.post("/register", data={
        "name": "Second User",
        "email": unique_email,
        "password": password,
        "confirm_password": password,
    }, follow_redirects=True)

    assert dup_resp.status_code == 200
    assert b"already registered" in dup_resp.data


def test_registration_password_mismatch(client):
    """Registration fails when password and confirm_password do not match."""
    resp = client.post("/register", data={
        "name": "Mismatch User",
        "email": "mismatch@example.com",
        "password": "password123",
        "confirm_password": "differentPassword123",
    })
    assert resp.status_code == 200
    assert b"Passwords do not match" in resp.data


def test_login_invalid_password(client):
    """Login fails when incorrect password is provided."""
    uid = uuid.uuid4().hex[:8]
    unique_email = f"wrong_pw_{uid}@example.com"
    client.post("/register", data={
        "name": "Wrong Password User",
        "email": unique_email,
        "password": "validPassword123",
        "confirm_password": "validPassword123",
    })

    # Attempt login with wrong password
    resp = client.post("/login", data={
        "email": unique_email,
        "password": "totallyIncorrectPassword",
    })
    assert resp.status_code == 200
    assert b"Invalid email or password" in resp.data
