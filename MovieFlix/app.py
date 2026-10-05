"""
MovieFlix - Main Flask Web Application & RESTful API
Provides Netflix-inspired web routes, recommendation engine integration,
database querying, user authentication, watchlist, movie ratings,
personalized recommendations, and JSON API endpoints with CSRF protection.
"""

import logging
from typing import List, Dict, Any, Optional
from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    session,
    redirect,
    url_for,
    flash,
)
from flask_wtf.csrf import CSRFProtect, CSRFError
from werkzeug.security import generate_password_hash

from config import (
    FLASK_SECRET_KEY,
    FLASK_DEBUG,
    FLASK_PORT,
    POSTER_FALLBACK_URL,
)
import db
import auth
from auth import login_required
from recommender import (
    recommender,
    recommend_movies,
    recommend_by_movie_id,
    recommend_for_user,
    recommend_by_title,
    search_movies as recommender_search,
)
from tmdb_client import poster_url, backdrop_url

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("movieflix.app")

app = Flask(__name__)
app.config["SECRET_KEY"] = FLASK_SECRET_KEY
app.config["JSON_SORT_KEYS"] = False
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = False  # Set True in production with HTTPS
app.config["WTF_CSRF_TIME_LIMIT"] = None

# Initialize CSRF Protection
csrf = CSRFProtect(app)


# ------------------------------------------------------------------------------
# Context Processors & Helpers
# ------------------------------------------------------------------------------

@app.context_processor
def inject_global_context():
    """Provides current_user and helper utilities to all Jinja2 templates."""
    user_id = session.get("user_id")
    current_user = None
    if user_id:
        current_user = db.get_user_by_id(user_id)
        if not current_user:
            # Session exists for deleted/nonexistent user
            session.clear()

    return {
        "current_user": current_user,
        "is_authenticated": bool(current_user),
        "POSTER_FALLBACK_URL": POSTER_FALLBACK_URL,
    }


def get_movies_data(limit: int = 50, sort_by: str = "popularity") -> List[Dict[str, Any]]:
    """
    Retrieves movies list from database;
    falls back to recommender in-memory dataset if database is empty.
    """
    movies = db.get_all_movies(limit=limit, sort_by=sort_by)
    if not movies and recommender.is_loaded and recommender.movies_df is not None:
        df = recommender.movies_df.copy()
        if sort_by == "popularity" and "popularity" in df.columns:
            df = df.sort_values(by="popularity", ascending=False)
        elif sort_by == "vote_average" and "vote_average" in df.columns:
            df = df.sort_values(by="vote_average", ascending=False)
        elif sort_by == "release_date" and "release_date" in df.columns:
            df = df.sort_values(by="release_date", ascending=False)
        movies = df.head(limit).to_dict(orient="records")

    for m in movies:
        p_path = m.get("poster_path")
        m["poster_url"] = poster_url(p_path) if p_path and str(p_path) != "nan" else m.get("poster_url", POSTER_FALLBACK_URL)
        if not m["poster_url"] or "None" in str(m["poster_url"]):
            m["poster_url"] = POSTER_FALLBACK_URL
        b_path = m.get("backdrop_path")
        m["backdrop_url"] = backdrop_url(b_path) if b_path and str(b_path) != "nan" else m.get("backdrop_url", "")
    return movies


def get_movie_record(movie_id: int) -> Optional[Dict[str, Any]]:
    """Fetches a single movie record by ID from DB or recommender cache."""
    movie = db.get_movie(movie_id)
    if not movie and recommender.is_loaded:
        movie = recommender.get_movie_by_id(movie_id)
    if movie:
        p_path = movie.get("poster_path")
        movie["poster_url"] = poster_url(p_path) if p_path and str(p_path) != "nan" else movie.get("poster_url", POSTER_FALLBACK_URL)
        if not movie["poster_url"] or "None" in str(movie["poster_url"]):
            movie["poster_url"] = POSTER_FALLBACK_URL
        b_path = movie.get("backdrop_path")
        movie["backdrop_url"] = backdrop_url(b_path) if b_path and str(b_path) != "nan" else movie.get("backdrop_url", "")
    return movie


# ------------------------------------------------------------------------------
# Public Web Routes
# ------------------------------------------------------------------------------

@app.route("/")
def index():
    """
    Netflix-inspired homepage.
    Displays hero spotlight and scroll-tied sections:
    Trending Now, Top Rated, Action, Comedy, Drama, Sci-Fi.
    If logged in, also includes Personalized Preview and Watchlist preview.
    """
    all_movies = get_movies_data(limit=120, sort_by="popularity")
    hero_movie = all_movies[0] if all_movies else None

    user_id = session.get("user_id")
    in_watchlist_hero = False
    if user_id and hero_movie:
        in_watchlist_hero = db.is_in_watchlist(user_id, hero_movie["id"])

    # Organize category rows
    trending = all_movies[:14] if all_movies else []
    top_rated = sorted(all_movies, key=lambda m: float(m.get("vote_average", 0.0) or 0.0), reverse=True)[:14]
    
    # Genre-specific rows
    action = [m for m in all_movies if "action" in str(m.get("genres", "")).lower()][:14]
    comedy = [m for m in all_movies if "comedy" in str(m.get("genres", "")).lower()][:14]
    drama = [m for m in all_movies if "drama" in str(m.get("genres", "")).lower()][:14]
    scifi = [m for m in all_movies if "sci-fi" in str(m.get("genres", "")).lower() or "science fiction" in str(m.get("genres", "")).lower()][:14]

    # User personalized row
    user_recs_data = None
    user_watchlist_preview = None
    if user_id:
        user_recs_data = recommender.recommend_for_user(user_id, top_n=10)
        user_watchlist_preview = db.get_user_watchlist(user_id)[:10]

    return render_template(
        "index.html",
        hero_movie=hero_movie,
        in_watchlist_hero=in_watchlist_hero,
        trending=trending,
        top_rated=top_rated,
        action=action,
        comedy=comedy,
        drama=drama,
        scifi=scifi,
        user_recs_data=user_recs_data,
        user_watchlist_preview=user_watchlist_preview,
    )


@app.route("/search")
def search():
    """
    Search route handling ?q= parameter.
    Searches titles, cast, director, and overview in DB and recommender index.
    """
    query = request.args.get("q", "").strip()
    if not query:
        return render_template("search.html", query="", movies=[], count=0)

    results = db.search_movies_db(query, limit=50)
    if not results and recommender.is_loaded:
        results = recommender_search(query, limit=50)

    for m in results:
        p_path = m.get("poster_path")
        m["poster_url"] = poster_url(p_path) if p_path and str(p_path) != "nan" else m.get("poster_url", POSTER_FALLBACK_URL)
        if not m["poster_url"] or "None" in str(m["poster_url"]):
            m["poster_url"] = POSTER_FALLBACK_URL

    return render_template("search.html", query=query, movies=results, count=len(results))


@app.route("/movie/<int:movie_id>")
def movie_details(movie_id: int):
    """
    Rich movie details page.
    Renders high-res backdrop, synopsis, metadata, user rating widget,
    watchlist toggle, and 'Movies Like This' content-based recommendations.
    """
    movie = get_movie_record(movie_id)
    if not movie:
        return render_template("404.html", message=f"Movie ID {movie_id} was not found."), 404

    # Calculate content-based recommendations (TF-IDF & Cosine Similarity)
    recommendations = recommend_movies(movie_id, top_n=10)

    # Check user interactions if logged in
    user_id = session.get("user_id")
    in_watchlist = False
    user_rating = None
    if user_id:
        in_watchlist = db.is_in_watchlist(user_id, movie_id)
        user_rating = db.get_user_rating(user_id, movie_id)

    rating_stats = db.get_movie_rating_stats(movie_id)

    return render_template(
        "movie.html",
        movie=movie,
        recommendations=recommendations,
        in_watchlist=in_watchlist,
        user_rating=user_rating,
        rating_stats=rating_stats,
    )


@app.route("/recommendations/<int:movie_id>")
def recommendations_view(movie_id: int):
    """
    Dedicated recommendation page: 'Because You Watched [Movie]'.
    Displays ranked content-based recommendations with similarity metrics.
    """
    movie = get_movie_record(movie_id)
    if not movie:
        return render_template("404.html", message=f"Cannot generate recommendations for nonexistent movie ID {movie_id}."), 404

    recommendations = recommend_movies(movie_id, top_n=12)

    return render_template(
        "recommendations.html",
        movie=movie,
        recommendations=recommendations,
    )


# ------------------------------------------------------------------------------
# Authentication Routes
# ------------------------------------------------------------------------------

@app.route("/register", methods=["GET", "POST"])
def register():
    """
    User registration route.
    Validates name, email, password, confirm password, prevents duplicate email,
    hashes password with Werkzeug, and redirects to login on success.
    """
    if auth.is_authenticated():
        return redirect(url_for("index"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        is_valid, err_msg = auth.validate_registration(name, email, password, confirm_password)
        if not is_valid:
            flash(err_msg, "error")
            return render_template("register.html", name=name, email=email)

        password_hash = generate_password_hash(password)
        success, db_msg, user_id = db.create_user(name, email, password_hash)

        if not success:
            flash(db_msg, "error")
            return render_template("register.html", name=name, email=email)

        flash("Registration successful! Please sign in with your email and password.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """
    User login route.
    Verifies credentials via check_password_hash and initializes secure session.
    """
    if auth.is_authenticated():
        return redirect(url_for("index"))

    next_page = request.args.get("next", "")

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Please enter both email and password.", "error")
            return render_template("login.html", email=email, next=next_page)

        user = db.get_user_by_email(email)
        if not user or not auth.verify_password(user.get("password_hash", ""), password):
            flash("Invalid email or password. Please try again.", "error")
            return render_template("login.html", email=email, next=next_page)

        # Secure session establishment
        auth.login_user(user)
        flash(f"Welcome back, {user.get('name', 'Movie Lover')}!", "success")

        if next_page and next_page.startswith("/") and not next_page.startswith("//"):
            return redirect(next_page)
        return redirect(url_for("index"))

    return render_template("login.html", next=next_page)


@app.route("/logout", methods=["GET", "POST"])
def logout():
    """Clears user session and redirects to home."""
    auth.logout_user()
    flash("You have been signed out.", "info")
    return redirect(url_for("index"))


# ------------------------------------------------------------------------------
# Authenticated Routes (Watchlist, Ratings, Profile, Personalized Recs)
# ------------------------------------------------------------------------------

@app.route("/profile")
@login_required
def profile():
    """
    User profile view.
    Displays user name, email, registration date, watchlist count,
    ratings count, recently rated movies, and personalized recommendations.
    Never exposes password hashes.
    """
    user_id = session["user_id"]
    stats = db.get_user_profile_stats(user_id)
    recs_data = recommender.recommend_for_user(user_id, top_n=8)

    return render_template(
        "profile.html",
        stats=stats,
        recommendations=recs_data.get("recommendations", []),
        is_personalized=recs_data.get("is_personalized", False),
        reason=recs_data.get("reason", ""),
    )


@app.route("/watchlist")
@login_required
def watchlist():
    """Renders user's personal watchlist in a Netflix-style grid."""
    user_id = session["user_id"]
    watchlist_movies = db.get_user_watchlist(user_id)

    for m in watchlist_movies:
        p_path = m.get("poster_path")
        m["poster_url"] = poster_url(p_path) if p_path and str(p_path) != "nan" else m.get("poster_url", POSTER_FALLBACK_URL)
        if not m["poster_url"] or "None" in str(m["poster_url"]):
            m["poster_url"] = POSTER_FALLBACK_URL

    return render_template("watchlist.html", movies=watchlist_movies, count=len(watchlist_movies))


@app.route("/watchlist/add/<int:movie_id>", methods=["POST"])
@login_required
def watchlist_add(movie_id: int):
    """Adds a movie to the user's watchlist."""
    user_id = session["user_id"]
    movie = get_movie_record(movie_id)
    if not movie:
        if request.is_json:
            return jsonify({"status": "error", "message": "Movie not found."}), 404
        flash("Movie not found.", "error")
        return redirect(request.referrer or url_for("index"))

    success, msg = db.add_to_watchlist(user_id, movie_id)

    if request.is_json:
        return jsonify({
            "status": "success" if success else "error",
            "message": msg,
            "in_watchlist": True,
            "movie_id": movie_id,
        })

    flash(msg, "success" if success else "info")
    return redirect(request.referrer or url_for("movie_details", movie_id=movie_id))


@app.route("/watchlist/remove/<int:movie_id>", methods=["POST"])
@login_required
def watchlist_remove(movie_id: int):
    """Removes a movie from the user's watchlist."""
    user_id = session["user_id"]
    success, msg = db.remove_from_watchlist(user_id, movie_id)

    if request.is_json:
        return jsonify({
            "status": "success" if success else "error",
            "message": msg,
            "in_watchlist": False,
            "movie_id": movie_id,
        })

    flash(msg, "info")
    return redirect(request.referrer or url_for("watchlist"))


@app.route("/ratings")
@login_required
def ratings():
    """Displays all movies rated by the user with their ratings and timestamps."""
    user_id = session["user_id"]
    rated_movies = db.get_user_ratings(user_id)

    for m in rated_movies:
        p_path = m.get("poster_path")
        m["poster_url"] = poster_url(p_path) if p_path and str(p_path) != "nan" else m.get("poster_url", POSTER_FALLBACK_URL)
        if not m["poster_url"] or "None" in str(m["poster_url"]):
            m["poster_url"] = POSTER_FALLBACK_URL

    return render_template("ratings.html", movies=rated_movies, count=len(rated_movies))


@app.route("/movie/<int:movie_id>/rate", methods=["POST"])
@login_required
def rate_movie_route(movie_id: int):
    """Submits or updates a 1-5 star user rating for a movie."""
    user_id = session["user_id"]
    movie = get_movie_record(movie_id)
    if not movie:
        if request.is_json:
            return jsonify({"status": "error", "message": "Movie not found."}), 404
        flash("Movie not found.", "error")
        return redirect(request.referrer or url_for("index"))

    # Extract rating value from JSON or form data
    if request.is_json:
        rating_val = request.json.get("rating")
    else:
        rating_val = request.form.get("rating")

    try:
        score = float(rating_val)
        if score < 1.0 or score > 5.0:
            raise ValueError()
    except (ValueError, TypeError):
        if request.is_json:
            return jsonify({"status": "error", "message": "Rating must be between 1 and 5 stars."}), 400
        flash("Invalid rating. Must be between 1 and 5.", "error")
        return redirect(request.referrer or url_for("movie_details", movie_id=movie_id))

    success, msg = db.rate_movie(user_id, movie_id, score)
    stats = db.get_movie_rating_stats(movie_id)

    if request.is_json:
        return jsonify({
            "status": "success" if success else "error",
            "message": msg,
            "movie_id": movie_id,
            "user_rating": score,
            "avg_rating": stats.get("avg_rating"),
            "rating_count": stats.get("rating_count"),
        })

    flash(msg, "success" if success else "error")
    return redirect(request.referrer or url_for("movie_details", movie_id=movie_id))


@app.route("/recommendations/user")
@login_required
def user_recommendations():
    """
    Personalized recommendation page: 'Recommended For You'.
    Aggregates user's rating scores and watchlist entries to compute
    a personalized preference vector and ranks top matching films.
    Falls back to popular movies with explanation if user history is empty.
    """
    user_id = session["user_id"]
    recs_data = recommender.recommend_for_user(user_id, top_n=18)

    return render_template(
        "recommendations.html",
        is_user_recommendations=True,
        recommendations=recs_data.get("recommendations", []),
        is_personalized=recs_data.get("is_personalized", False),
        reason=recs_data.get("reason", ""),
    )


# ------------------------------------------------------------------------------
# REST API Endpoints (CSRF Exempt for API consumers)
# ------------------------------------------------------------------------------

@csrf.exempt
@app.route("/api/movies", methods=["GET"])
def api_movies():
    """GET /api/movies?limit=20&sort_by=popularity"""
    try:
        limit = min(int(request.args.get("limit", 20)), 100)
    except ValueError:
        limit = 20
    sort_by = request.args.get("sort_by", "popularity")
    movies = get_movies_data(limit=limit, sort_by=sort_by)
    return jsonify({
        "status": "success",
        "count": len(movies),
        "results": movies,
    }), 200


@csrf.exempt
@app.route("/api/movies/<int:movie_id>", methods=["GET"])
def api_movie_detail(movie_id: int):
    """GET /api/movies/<movie_id>"""
    movie = get_movie_record(movie_id)
    if not movie:
        return jsonify({"status": "error", "message": f"Movie ID {movie_id} not found."}), 404
    stats = db.get_movie_rating_stats(movie_id)
    movie_response = dict(movie)
    movie_response["rating_stats"] = stats
    return jsonify({"status": "success", "movie": movie_response}), 200


@csrf.exempt
@app.route("/api/search", methods=["GET"])
def api_search():
    """GET /api/search?q=query"""
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"status": "error", "message": "Search parameter 'q' cannot be empty."}), 400

    results = db.search_movies_db(query, limit=50)
    if not results and recommender.is_loaded:
        results = recommender_search(query, limit=50)

    for m in results:
        p_path = m.get("poster_path")
        m["poster_url"] = poster_url(p_path) if p_path and str(p_path) != "nan" else m.get("poster_url", POSTER_FALLBACK_URL)
        if not m["poster_url"] or "None" in str(m["poster_url"]):
            m["poster_url"] = POSTER_FALLBACK_URL

    return jsonify({
        "status": "success",
        "query": query,
        "count": len(results),
        "results": results,
    }), 200


@csrf.exempt
@app.route("/api/recommendations/<int:movie_id>", methods=["GET"])
def api_recommendations(movie_id: int):
    """GET /api/recommendations/<movie_id>?limit=10"""
    try:
        limit = min(int(request.args.get("limit", 10)), 30)
    except ValueError:
        limit = 10

    movie = get_movie_record(movie_id)
    if not movie:
        return jsonify({"status": "error", "message": f"Source movie ID {movie_id} not found."}), 404

    recs = recommend_movies(movie_id, top_n=limit)
    return jsonify({
        "status": "success",
        "source_movie_id": movie_id,
        "source_movie_title": movie.get("title"),
        "count": len(recs),
        "recommendations": recs,
    }), 200


@csrf.exempt
@app.route("/health", methods=["GET"])
def health_check():
    """System diagnostic and health check endpoint."""
    db_ok, db_msg = db.test_db_connection()
    return jsonify({
        "status": "healthy",
        "service": "MovieFlix Intelligent Recommendation System",
        "database": {
            "connected": db_ok,
            "message": db_msg,
            "total_movies": db.get_movie_count(),
            "total_users": db.get_user_count(),
            "total_watchlist": db.get_watchlist_count(),
            "total_ratings": db.get_rating_count(),
        },
        "recommender": {
            "loaded": recommender.is_loaded,
            "indexed_movies": len(recommender.movie_id_to_idx) if recommender.is_loaded else 0,
        },
    }), 200


# ------------------------------------------------------------------------------
# Error Handlers
# ------------------------------------------------------------------------------

@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    if request.path.startswith("/api/") or request.is_json:
        return jsonify({"status": "error", "message": "CSRF verification failed."}), 400
    flash("Your session timed out or form verification failed. Please try again.", "error")
    return redirect(request.referrer or url_for("index"))


@app.errorhandler(404)
def handle_404(e):
    if request.path.startswith("/api/"):
        return jsonify({"status": "error", "message": "API endpoint or resource not found."}), 404
    return render_template("404.html"), 404


@app.errorhandler(500)
def handle_500(e):
    logger.error("Internal Server Error: %s", e)
    if request.path.startswith("/api/"):
        return jsonify({"status": "error", "message": "Internal server processing error."}), 500
    return render_template(
        "error.html",
        error_code=500,
        error_title="Cinema Projector Glitch",
        error_message="An internal glitch occurred. Our projectionists have been notified.",
    ), 500


# ------------------------------------------------------------------------------
# Server Bootstrap
# ------------------------------------------------------------------------------

if __name__ == "__main__":
    logger.info("Initializing MovieFlix server...")
    db_ok = db.init_db()
    if db_ok:
        logger.info("Database initialized successfully.")
    else:
        logger.warning("Database initialization had warnings.")

    if not recommender.is_loaded:
        logger.info("Triggering recommender initialization...")
        recommender.reload()

    logger.info("Starting MovieFlix web server on http://127.0.0.1:%d", FLASK_PORT)
    app.run(host="0.0.0.0", port=FLASK_PORT, debug=FLASK_DEBUG)
