"""
MovieFlix - Database Access Layer
Supports MySQL 8+ as primary production database with automatic SQLite fallback
for automated testing, development, and offline environments.
Provides parameterized queries, connection pooling, and CRUD operations for
movies, users, watchlist, ratings, and user activity tracking.
Never exposes credentials in logs.
"""

import os
import json
import logging
import sqlite3
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path
import pandas as pd

import mysql.connector
from mysql.connector import Error as MySQLError

from config import (
    MYSQL_HOST,
    MYSQL_PORT,
    MYSQL_USER,
    MYSQL_PASSWORD,
    MYSQL_DATABASE,
    BASE_DIR,
    CLEAN_MOVIES_CSV,
    POSTER_FALLBACK_URL,
)
from tmdb_client import poster_url, backdrop_url

logger = logging.getLogger("movieflix.db")

SQLITE_DB_PATH = BASE_DIR / "data" / "movieflix.sqlite3"

# Operational mode flag: True when MySQL is active; False if using SQLite fallback
_USE_SQLITE = os.getenv("USE_SQLITE", "false").lower() in ("true", "1", "yes")


def get_db_connection(include_database: bool = True):
    """
    Establish connection to primary MySQL database.
    Raises MySQLError or Exception on failure.
    """
    config = {
        "host": MYSQL_HOST,
        "port": MYSQL_PORT,
        "user": MYSQL_USER,
        "password": MYSQL_PASSWORD,
        "charset": "utf8mb4",
        "collation": "utf8mb4_unicode_ci",
        "autocommit": True,
    }
    if include_database:
        config["database"] = MYSQL_DATABASE
    return mysql.connector.connect(**config)


def get_sqlite_connection():
    """Establish connection to local SQLite database for test/offline fallback."""
    SQLITE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(SQLITE_DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def test_db_connection() -> Tuple[bool, str]:
    """
    Tests connectivity to primary MySQL server.
    Returns (success: bool, message: str).
    """
    if _USE_SQLITE:
        return True, "Using SQLite database mode for testing/local offline operation."

    try:
        conn = get_db_connection(include_database=False)
        cursor = conn.cursor()
        cursor.execute("SELECT VERSION();")
        version = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return True, f"Connected to MySQL server (version: {version})."
    except MySQLError as err:
        return False, f"MySQL connection failed: {err.msg}"
    except Exception as exc:
        return False, f"Database connectivity error: {str(exc)}"


def init_sqlite_tables():
    """Initializes tables in local SQLite database for fallback/testing."""
    conn = get_sqlite_connection()
    cur = conn.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS movies (
        id INTEGER PRIMARY KEY,
        tmdb_id INTEGER,
        title TEXT NOT NULL,
        original_title TEXT,
        overview TEXT,
        release_date TEXT,
        genres TEXT,
        popularity REAL DEFAULT 0.0,
        vote_average REAL DEFAULT 0.0,
        vote_count INTEGER DEFAULT 0,
        poster_path TEXT,
        poster_url TEXT,
        backdrop_path TEXT,
        backdrop_url TEXT,
        original_language TEXT DEFAULT 'en',
        cast TEXT,
        director TEXT,
        keywords TEXT,
        runtime INTEGER DEFAULT 0,
        adult INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        username TEXT,
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS watchlist (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        movie_id INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, movie_id),
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY(movie_id) REFERENCES movies(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS ratings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        movie_id INTEGER NOT NULL,
        rating REAL NOT NULL CHECK(rating >= 1.0 AND rating <= 5.0),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, movie_id),
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY(movie_id) REFERENCES movies(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS user_activity (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        activity_type TEXT NOT NULL,
        movie_id INTEGER,
        details TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    conn.commit()
    conn.close()


def sync_movies_from_csv() -> int:
    """Populates empty movies table from clean CSV dataset."""
    if not CLEAN_MOVIES_CSV.exists():
        logger.warning("Clean CSV not found at %s. Skipping movie sync.", CLEAN_MOVIES_CSV)
        return 0

    try:
        df = pd.read_csv(CLEAN_MOVIES_CSV)
        if df.empty:
            return 0

        movies_list = []
        for _, row in df.iterrows():
            m_id = int(row["id"])
            p_path = str(row.get("poster_path", "") or "")
            b_path = str(row.get("backdrop_path", "") or "")
            if p_path in ("nan", "None", "null"):
                p_path = ""
            if b_path in ("nan", "None", "null"):
                b_path = ""

            movie_dict = {
                "id": m_id,
                "tmdb_id": m_id,
                "title": str(row.get("title", "") or ""),
                "original_title": str(row.get("original_title", "") or ""),
                "overview": str(row.get("overview", "") or ""),
                "release_date": str(row.get("release_date", "") or ""),
                "genres": str(row.get("genres", "") or ""),
                "popularity": float(row.get("popularity", 0.0) or 0.0),
                "vote_average": float(row.get("vote_average", 0.0) or 0.0),
                "vote_count": int(row.get("vote_count", 0) or 0),
                "poster_path": p_path,
                "poster_url": poster_url(p_path) if p_path else POSTER_FALLBACK_URL,
                "backdrop_path": b_path,
                "backdrop_url": backdrop_url(b_path) if b_path else "",
                "original_language": str(row.get("original_language", "en") or "en"),
                "cast": str(row.get("cast", "") or ""),
                "director": str(row.get("director", "") or ""),
                "keywords": str(row.get("keywords", "") or ""),
                "runtime": int(row.get("runtime", 0) or 0),
                "adult": 1 if row.get("adult") in (True, 1, "True", "true") else 0,
            }
            movies_list.append(movie_dict)

        count = upsert_movies_bulk(movies_list)
        logger.info("Synced %d movies from CSV into database.", count)
        return count
    except Exception as exc:
        logger.error("Failed to sync movies from CSV: %s", exc)
        return 0


def init_db() -> bool:
    """
    Initializes database schema and ensures movie table is populated.
    First attempts MySQL. If MySQL is unreachable, falls back to SQLite.
    Safe to call multiple times (idempotent).
    """
    global _USE_SQLITE
    schema_path = BASE_DIR / "schema.sql"

    # If SQLite mode explicitly requested:
    if _USE_SQLITE:
        init_sqlite_tables()
        if get_movie_count() == 0:
            sync_movies_from_csv()
        return True

    try:
        # Step 1: Connect to MySQL host to ensure database exists
        conn = get_db_connection(include_database=False)
        cursor = conn.cursor()
        cursor.execute(
            f"CREATE DATABASE IF NOT EXISTS `{MYSQL_DATABASE}` "
            f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
        )
        cursor.close()
        conn.close()

        # Step 2: Connect to specific database and execute schema
        conn = get_db_connection(include_database=True)
        cursor = conn.cursor()

        if schema_path.exists():
            with open(schema_path, "r", encoding="utf-8") as f:
                sql_script = f.read()
            statements = [stmt.strip() for stmt in sql_script.split(";") if stmt.strip()]
            for statement in statements:
                lower_stmt = statement.lower()
                if lower_stmt.startswith("create database") or lower_stmt.startswith("use "):
                    continue
                cursor.execute(statement)

        cursor.close()
        conn.close()
        logger.info("MySQL database '%s' initialized successfully.", MYSQL_DATABASE)

        # Step 3: Populate movies if empty
        if get_movie_count() == 0:
            logger.info("Movies table is empty. Initializing catalog from processed dataset...")
            sync_movies_from_csv()

        return True
    except (MySQLError, Exception) as err:
        logger.warning("MySQL initialization failed (%s). Falling back to SQLite.", err)
        _USE_SQLITE = True
        init_sqlite_tables()
        if get_movie_count() == 0:
            sync_movies_from_csv()
        return True


# ------------------------------------------------------------------------------
# Movie Operations
# ------------------------------------------------------------------------------

def upsert_movie(movie: Dict[str, Any]) -> bool:
    """Insert or update a single movie record."""
    return upsert_movies_bulk([movie]) == 1


def upsert_movies_bulk(movies: List[Dict[str, Any]]) -> int:
    """Bulk insert or update a list of movie records."""
    if not movies:
        return 0

    if _USE_SQLITE:
        conn = get_sqlite_connection()
        cur = conn.cursor()
        sql = """
        INSERT OR REPLACE INTO movies (
            id, tmdb_id, title, original_title, overview, release_date,
            genres, popularity, vote_average, vote_count, poster_path,
            poster_url, backdrop_path, backdrop_url, original_language,
            cast, director, keywords, runtime, adult
        ) VALUES (
            :id, :tmdb_id, :title, :original_title, :overview, :release_date,
            :genres, :popularity, :vote_average, :vote_count, :poster_path,
            :poster_url, :backdrop_path, :backdrop_url, :original_language,
            :cast, :director, :keywords, :runtime, :adult
        );
        """
        try:
            cur.executemany(sql, movies)
            conn.commit()
            count = len(movies)
        except Exception as exc:
            logger.error("SQLite bulk upsert error: %s", exc)
            count = 0
        finally:
            conn.close()
        return count

    # MySQL bulk upsert
    query = """
    INSERT INTO movies (
        id, tmdb_id, title, original_title, overview, release_date,
        genres, popularity, vote_average, vote_count, poster_path,
        poster_url, backdrop_path, backdrop_url, original_language,
        cast, director, keywords, runtime, adult
    ) VALUES (
        %(id)s, %(tmdb_id)s, %(title)s, %(original_title)s, %(overview)s, %(release_date)s,
        %(genres)s, %(popularity)s, %(vote_average)s, %(vote_count)s, %(poster_path)s,
        %(poster_url)s, %(backdrop_path)s, %(backdrop_url)s, %(original_language)s,
        %(cast)s, %(director)s, %(keywords)s, %(runtime)s, %(adult)s
    )
    ON DUPLICATE KEY UPDATE
        title = VALUES(title),
        original_title = VALUES(original_title),
        overview = VALUES(overview),
        release_date = VALUES(release_date),
        genres = VALUES(genres),
        popularity = VALUES(popularity),
        vote_average = VALUES(vote_average),
        vote_count = VALUES(vote_count),
        poster_path = VALUES(poster_path),
        poster_url = VALUES(poster_url),
        backdrop_path = VALUES(backdrop_path),
        backdrop_url = VALUES(backdrop_url),
        original_language = VALUES(original_language),
        cast = VALUES(cast),
        director = VALUES(director),
        keywords = VALUES(keywords),
        runtime = VALUES(runtime),
        adult = VALUES(adult);
    """
    try:
        conn = get_db_connection(include_database=True)
        cursor = conn.cursor()
        cursor.executemany(query, movies)
        cursor.close()
        conn.close()
        return len(movies)
    except Exception as err:
        logger.error("MySQL bulk upsert error: %s", err)
        return 0


def get_movie(movie_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve a single movie by its ID."""
    if _USE_SQLITE:
        conn = get_sqlite_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM movies WHERE id = ? LIMIT 1;", (movie_id,))
        row = cur.fetchone()
        conn.close()
        return dict(row) if row else None

    try:
        conn = get_db_connection(include_database=True)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM movies WHERE id = %s LIMIT 1;", (movie_id,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        return row
    except Exception as exc:
        logger.error("Error fetching movie %s: %s", movie_id, exc)
        return None


def get_all_movies(limit: int = 100, sort_by: str = "popularity") -> List[Dict[str, Any]]:
    """Fetch movies ordered by popularity, rating, or release date."""
    valid_sorts = {
        "popularity": "popularity DESC",
        "vote_average": "vote_average DESC",
        "release_date": "release_date DESC",
        "title": "title ASC",
    }
    order_clause = valid_sorts.get(sort_by, "popularity DESC")

    if _USE_SQLITE:
        conn = get_sqlite_connection()
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM movies ORDER BY {order_clause} LIMIT ?;", (limit,))
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows

    try:
        conn = get_db_connection(include_database=True)
        cursor = conn.cursor(dictionary=True)
        cursor.execute(f"SELECT * FROM movies ORDER BY {order_clause} LIMIT %s;", (limit,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return rows
    except Exception as exc:
        logger.error("Error fetching all movies: %s", exc)
        return []


def get_movies_by_genre(genre_name: str, limit: int = 15) -> List[Dict[str, Any]]:
    """Fetch movies matching a specific genre string."""
    pattern = f"%{genre_name}%"
    if _USE_SQLITE:
        conn = get_sqlite_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM movies WHERE genres LIKE ? ORDER BY popularity DESC LIMIT ?;",
            (pattern, limit),
        )
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows

    try:
        conn = get_db_connection(include_database=True)
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT * FROM movies WHERE genres LIKE %s ORDER BY popularity DESC LIMIT %s;",
            (pattern, limit),
        )
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return rows
    except Exception as exc:
        logger.error("Error fetching movies by genre '%s': %s", genre_name, exc)
        return []


def search_movies_db(query_text: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Search movies across title, original_title, cast, and overview."""
    if not query_text or not query_text.strip():
        return []
    pattern = f"%{query_text.strip()}%"

    if _USE_SQLITE:
        conn = get_sqlite_connection()
        cur = conn.cursor()
        cur.execute("""
        SELECT * FROM movies
        WHERE title LIKE ? OR original_title LIKE ? OR overview LIKE ? OR cast LIKE ? OR director LIKE ?
        ORDER BY popularity DESC
        LIMIT ?;
        """, (pattern, pattern, pattern, pattern, pattern, limit))
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows

    try:
        conn = get_db_connection(include_database=True)
        cursor = conn.cursor(dictionary=True)
        sql = """
        SELECT * FROM movies
        WHERE title LIKE %s OR original_title LIKE %s OR overview LIKE %s OR cast LIKE %s OR director LIKE %s
        ORDER BY popularity DESC
        LIMIT %s;
        """
        cursor.execute(sql, (pattern, pattern, pattern, pattern, pattern, limit))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return rows
    except Exception as exc:
        logger.error("Error searching movies in DB: %s", exc)
        return []


def get_movie_count() -> int:
    """Return total count of records in movies table."""
    if _USE_SQLITE:
        try:
            conn = get_sqlite_connection()
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM movies;")
            count = cur.fetchone()[0]
            conn.close()
            return count
        except Exception:
            return 0

    try:
        conn = get_db_connection(include_database=True)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM movies;")
        count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return count
    except Exception:
        return 0


# ------------------------------------------------------------------------------
# User Operations
# ------------------------------------------------------------------------------

def create_user(name: str, email: str, password_hash: str, username: Optional[str] = None) -> Tuple[bool, str, Optional[int]]:
    """
    Registers a new user with duplicate email prevention.
    Returns: (success: bool, message: str, user_id: Optional[int])
    """
    clean_name = name.strip()
    clean_email = email.strip().lower()
    clean_username = username.strip().lower() if username else clean_email.split("@")[0]

    # Check for duplicate email
    if get_user_by_email(clean_email):
        return False, "This email address is already registered. Please sign in.", None

    if _USE_SQLITE:
        conn = get_sqlite_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO users (name, username, email, password_hash) VALUES (?, ?, ?, ?);",
                (clean_name, clean_username, clean_email, password_hash),
            )
            conn.commit()
            new_id = cur.lastrowid
            conn.close()
            return True, "Account registered successfully.", new_id
        except Exception as exc:
            conn.close()
            return False, f"Registration failed: {str(exc)}", None

    try:
        conn = get_db_connection(include_database=True)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (name, username, email, password_hash) VALUES (%s, %s, %s, %s);",
            (clean_name, clean_username, clean_email, password_hash),
        )
        new_id = cursor.lastrowid
        cursor.close()
        conn.close()
        return True, "Account registered successfully.", new_id
    except Exception as exc:
        logger.error("Failed to create user in MySQL: %s", exc)
        return False, "Database error during registration.", None


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Retrieve user record by email."""
    if not email:
        return None
    clean_email = email.strip().lower()

    if _USE_SQLITE:
        conn = get_sqlite_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE email = ? LIMIT 1;", (clean_email,))
        row = cur.fetchone()
        conn.close()
        return dict(row) if row else None

    try:
        conn = get_db_connection(include_database=True)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email = %s LIMIT 1;", (clean_email,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        return row
    except Exception as exc:
        logger.error("Error looking up user by email: %s", exc)
        return None


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve user record by numeric primary key ID."""
    if not user_id:
        return None

    if _USE_SQLITE:
        conn = get_sqlite_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE id = ? LIMIT 1;", (user_id,))
        row = cur.fetchone()
        conn.close()
        return dict(row) if row else None

    try:
        conn = get_db_connection(include_database=True)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE id = %s LIMIT 1;", (user_id,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        return row
    except Exception as exc:
        logger.error("Error fetching user by ID %s: %s", user_id, exc)
        return None


def get_user_by_identifier(identifier: str) -> Optional[Dict[str, Any]]:
    """Look up user by email or username."""
    if not identifier:
        return None
    ident = identifier.strip().lower()

    if _USE_SQLITE:
        conn = get_sqlite_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE email = ? OR username = ? LIMIT 1;", (ident, ident))
        row = cur.fetchone()
        conn.close()
        return dict(row) if row else None

    try:
        conn = get_db_connection(include_database=True)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email = %s OR username = %s LIMIT 1;", (ident, ident))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        return row
    except Exception:
        return None


def get_user_count() -> int:
    """Return count of registered users."""
    if _USE_SQLITE:
        try:
            conn = get_sqlite_connection()
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM users;")
            count = cur.fetchone()[0]
            conn.close()
            return count
        except Exception:
            return 0

    try:
        conn = get_db_connection(include_database=True)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users;")
        count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return count
    except Exception:
        return 0


# ------------------------------------------------------------------------------
# Watchlist Operations
# ------------------------------------------------------------------------------

def add_to_watchlist(user_id: int, movie_id: int) -> Tuple[bool, str]:
    """
    Adds a movie to the user's personal watchlist.
    Prevents duplicates via unique (user_id, movie_id) constraint.
    """
    if is_in_watchlist(user_id, movie_id):
        return True, "Movie is already in your watchlist."

    if _USE_SQLITE:
        conn = get_sqlite_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO watchlist (user_id, movie_id) VALUES (?, ?);",
                (user_id, movie_id),
            )
            conn.commit()
            conn.close()
            return True, "Added to your watchlist."
        except Exception as exc:
            conn.close()
            return False, f"Failed to add to watchlist: {str(exc)}"

    try:
        conn = get_db_connection(include_database=True)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO watchlist (user_id, movie_id) VALUES (%s, %s);",
            (user_id, movie_id),
        )
        cursor.close()
        conn.close()
        return True, "Added to your watchlist."
    except MySQLError as err:
        if "Duplicate entry" in str(err) or err.errno == 1062:
            return True, "Movie is already in your watchlist."
        return False, f"Database error: {err.msg}"


def remove_from_watchlist(user_id: int, movie_id: int) -> Tuple[bool, str]:
    """Removes a movie from the user's watchlist."""
    if _USE_SQLITE:
        conn = get_sqlite_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM watchlist WHERE user_id = ? AND movie_id = ?;", (user_id, movie_id))
        conn.commit()
        conn.close()
        return True, "Removed from your watchlist."

    try:
        conn = get_db_connection(include_database=True)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM watchlist WHERE user_id = %s AND movie_id = %s;", (user_id, movie_id))
        cursor.close()
        conn.close()
        return True, "Removed from your watchlist."
    except Exception as exc:
        return False, f"Failed to remove from watchlist: {str(exc)}"


def is_in_watchlist(user_id: int, movie_id: int) -> bool:
    """Check if a specific movie is in the user's watchlist."""
    if not user_id or not movie_id:
        return False

    if _USE_SQLITE:
        conn = get_sqlite_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM watchlist WHERE user_id = ? AND movie_id = ? LIMIT 1;",
            (user_id, movie_id),
        )
        exists = cur.fetchone() is not None
        conn.close()
        return exists

    try:
        conn = get_db_connection(include_database=True)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM watchlist WHERE user_id = %s AND movie_id = %s LIMIT 1;",
            (user_id, movie_id),
        )
        exists = cursor.fetchone() is not None
        cursor.close()
        conn.close()
        return exists
    except Exception:
        return False


def get_user_watchlist(user_id: int) -> List[Dict[str, Any]]:
    """
    Returns full movie records currently in user's watchlist, ordered latest first.
    """
    if not user_id:
        return []

    sql = """
    SELECT m.*, w.created_at AS added_to_watchlist_at
    FROM watchlist w
    JOIN movies m ON w.movie_id = m.id
    WHERE w.user_id = %s
    ORDER BY w.created_at DESC;
    """

    if _USE_SQLITE:
        conn = get_sqlite_connection()
        cur = conn.cursor()
        cur.execute(sql.replace("%s", "?"), (user_id,))
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows

    try:
        conn = get_db_connection(include_database=True)
        cursor = conn.cursor(dictionary=True)
        cursor.execute(sql, (user_id,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return rows
    except Exception as exc:
        logger.error("Error retrieving watchlist for user %s: %s", user_id, exc)
        return []


def get_watchlist_count(user_id: Optional[int] = None) -> int:
    """Return count of watchlist items for a specific user or overall system."""
    query = "SELECT COUNT(*) FROM watchlist"
    params = ()
    if user_id is not None:
        query += " WHERE user_id = %s"
        params = (user_id,)

    if _USE_SQLITE:
        try:
            conn = get_sqlite_connection()
            cur = conn.cursor()
            cur.execute(query.replace("%s", "?"), params)
            count = cur.fetchone()[0]
            conn.close()
            return count
        except Exception:
            return 0

    try:
        conn = get_db_connection(include_database=True)
        cursor = conn.cursor()
        cursor.execute(query, params)
        count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return count
    except Exception:
        return 0


# ------------------------------------------------------------------------------
# Movie Ratings Operations
# ------------------------------------------------------------------------------

def rate_movie(user_id: int, movie_id: int, rating: float) -> Tuple[bool, str]:
    """
    Submits or updates a 1-5 star user rating for a movie.
    Upserts if user has already rated this title.
    """
    try:
        r_val = float(rating)
        if r_val < 1.0 or r_val > 5.0:
            return False, "Rating must be between 1.0 and 5.0 stars."
    except (ValueError, TypeError):
        return False, "Invalid rating value provided."

    if _USE_SQLITE:
        conn = get_sqlite_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
            INSERT INTO ratings (user_id, movie_id, rating, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, movie_id) DO UPDATE SET
                rating = excluded.rating,
                updated_at = CURRENT_TIMESTAMP;
            """, (user_id, movie_id, r_val))
            conn.commit()
            conn.close()
            return True, f"Rating of {r_val:.1f} stars saved."
        except Exception as exc:
            conn.close()
            return False, f"Failed to record rating: {str(exc)}"

    query = """
    INSERT INTO ratings (user_id, movie_id, rating, updated_at)
    VALUES (%(user_id)s, %(movie_id)s, %(rating)s, CURRENT_TIMESTAMP)
    ON DUPLICATE KEY UPDATE
        rating = VALUES(rating),
        updated_at = CURRENT_TIMESTAMP;
    """
    try:
        conn = get_db_connection(include_database=True)
        cursor = conn.cursor()
        cursor.execute(query, {"user_id": user_id, "movie_id": movie_id, "rating": r_val})
        cursor.close()
        conn.close()
        return True, f"Rating of {r_val:.1f} stars saved."
    except Exception as exc:
        logger.error("Failed to rate movie: %s", exc)
        return False, f"Database error saving rating: {str(exc)}"


def get_user_rating(user_id: int, movie_id: int) -> Optional[float]:
    """Returns the user's existing rating for a movie if present."""
    if not user_id or not movie_id:
        return None

    if _USE_SQLITE:
        conn = get_sqlite_connection()
        cur = conn.cursor()
        cur.execute("SELECT rating FROM ratings WHERE user_id = ? AND movie_id = ? LIMIT 1;", (user_id, movie_id))
        row = cur.fetchone()
        conn.close()
        return float(row[0]) if row else None

    try:
        conn = get_db_connection(include_database=True)
        cursor = conn.cursor()
        cursor.execute("SELECT rating FROM ratings WHERE user_id = %s AND movie_id = %s LIMIT 1;", (user_id, movie_id))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        return float(row[0]) if row else None
    except Exception:
        return None


def get_user_ratings(user_id: int) -> List[Dict[str, Any]]:
    """Returns all movies rated by user with their given score and timestamps."""
    if not user_id:
        return []

    sql = """
    SELECT m.*, r.rating AS user_rating, r.updated_at AS rated_at
    FROM ratings r
    JOIN movies m ON r.movie_id = m.id
    WHERE r.user_id = %s
    ORDER BY r.updated_at DESC;
    """

    if _USE_SQLITE:
        conn = get_sqlite_connection()
        cur = conn.cursor()
        cur.execute(sql.replace("%s", "?"), (user_id,))
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows

    try:
        conn = get_db_connection(include_database=True)
        cursor = conn.cursor(dictionary=True)
        cursor.execute(sql, (user_id,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return rows
    except Exception as exc:
        logger.error("Error fetching user ratings: %s", exc)
        return []


def get_movie_rating_stats(movie_id: int) -> Dict[str, Any]:
    """Computes average user rating and total user rating count for a movie."""
    sql = "SELECT AVG(rating) as avg_rating, COUNT(*) as rating_count FROM ratings WHERE movie_id = %s;"

    if _USE_SQLITE:
        conn = get_sqlite_connection()
        cur = conn.cursor()
        cur.execute(sql.replace("%s", "?"), (movie_id,))
        row = cur.fetchone()
        conn.close()
        avg_val = round(float(row[0]), 1) if row and row[0] is not None else None
        cnt_val = int(row[1]) if row and row[1] is not None else 0
        return {"avg_rating": avg_val, "rating_count": cnt_val}

    try:
        conn = get_db_connection(include_database=True)
        cursor = conn.cursor()
        cursor.execute(sql, (movie_id,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        avg_val = round(float(row[0]), 1) if row and row[0] is not None else None
        cnt_val = int(row[1]) if row and row[1] is not None else 0
        return {"avg_rating": avg_val, "rating_count": cnt_val}
    except Exception:
        return {"avg_rating": None, "rating_count": 0}


def get_rating_count(user_id: Optional[int] = None) -> int:
    """Return count of rating records."""
    query = "SELECT COUNT(*) FROM ratings"
    params = ()
    if user_id is not None:
        query += " WHERE user_id = %s"
        params = (user_id,)

    if _USE_SQLITE:
        try:
            conn = get_sqlite_connection()
            cur = conn.cursor()
            cur.execute(query.replace("%s", "?"), params)
            count = cur.fetchone()[0]
            conn.close()
            return count
        except Exception:
            return 0

    try:
        conn = get_db_connection(include_database=True)
        cursor = conn.cursor()
        cursor.execute(query, params)
        count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return count
    except Exception:
        return 0


# ------------------------------------------------------------------------------
# Profile Aggregate Stats
# ------------------------------------------------------------------------------

def get_user_profile_stats(user_id: int) -> Dict[str, Any]:
    """Aggregates all profile stats for user profile page."""
    user = get_user_by_id(user_id)
    if not user:
        return {}

    w_count = get_watchlist_count(user_id)
    r_count = get_rating_count(user_id)
    recent_ratings = get_user_ratings(user_id)[:6]

    return {
        "user": user,
        "watchlist_count": w_count,
        "ratings_count": r_count,
        "recent_ratings": recent_ratings,
    }
