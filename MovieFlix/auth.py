"""
MovieFlix - Authentication & Session Security Module
Handles user registration validation, secure password hashing via Werkzeug,
credential verification, session lifecycle management, and route access control.
"""

import re
import functools
import logging
from typing import Optional, Tuple, Dict, Any
from flask import session, redirect, url_for, flash, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

logger = logging.getLogger("movieflix.auth")

EMAIL_REGEX = re.compile(r"^[\w\.-]+@([\w-]+\.)+[\w-]{2,8}$")


def hash_password(password: str) -> str:
    """Generate a secure cryptographic password hash using PBKDF2-SHA256."""
    return generate_password_hash(password, method="scrypt") if hasattr(generate_password_hash, "scrypt") else generate_password_hash(password)


def verify_password(stored_hash: str, password_attempt: str) -> bool:
    """Safely verify a plaintext password attempt against stored hash."""
    if not stored_hash or not password_attempt:
        return False
    return check_password_hash(stored_hash, password_attempt)


def validate_email(email: str) -> bool:
    """Validates email format using regex."""
    if not email or len(email) > 120:
        return False
    return bool(EMAIL_REGEX.match(email.strip()))


def validate_registration(name: str, email: str, password: str, confirm_password: str) -> Tuple[bool, str]:
    """
    Validates user registration input according to security specifications.
    Returns: (is_valid: bool, error_message: str)
    """
    if not name or not name.strip():
        return False, "Full Name is required."

    if len(name.strip()) < 2:
        return False, "Name must be at least 2 characters long."

    if not email or not email.strip():
        return False, "Email address is required."

    if not validate_email(email):
        return False, "Please enter a valid email address (e.g., student@college.edu)."

    if not password:
        return False, "Password is required."

    if len(password) < 6:
        return False, "Password must be at least 6 characters long."

    if password != confirm_password:
        return False, "Passwords do not match. Please re-enter your password."

    return True, ""


def login_user(user: Dict[str, Any]) -> None:
    """
    Initializes secure Flask session for an authenticated user.
    NEVER stores password hashes, plain passwords, or API tokens in session.
    """
    session.clear()
    session["user_id"] = user["id"]
    session["user_name"] = user.get("name") or user.get("username", "Movie Lover")
    session["user_email"] = user.get("email", "")
    session.permanent = False
    logger.info("User ID %s signed in successfully.", user.get("id"))


def logout_user() -> None:
    """Clears all session keys, logging out user."""
    user_id = session.get("user_id")
    session.clear()
    logger.info("User ID %s signed out.", user_id)


def get_current_user_id() -> Optional[int]:
    """Retrieve currently authenticated user ID from session or None."""
    return session.get("user_id")


def is_authenticated() -> bool:
    """Check if the current request session belongs to an authenticated user."""
    return bool(session.get("user_id"))


def login_required(f):
    """
    Decorator for views requiring authentication.
    Redirects unauthenticated users to /login?next=<path>.
    Returns 401 JSON for AJAX/API requests.
    """
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_authenticated():
            if request.is_json or request.path.startswith("/api/") or request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({
                    "status": "error",
                    "authenticated": False,
                    "message": "Authentication required. Please sign in."
                }), 401

            flash("Please sign in to access this page.", "warning")
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)
    return decorated_function
