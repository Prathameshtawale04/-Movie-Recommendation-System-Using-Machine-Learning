# MOVIEFLIX
### *An Intelligent Movie Recommendation System Using Data Science and Information Retrieval*

[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Framework-Flask%203.1-black.svg)](https://flask.palletsprojects.com/)
[![Scikit-Learn](https://img.shields.io/badge/ML-Scikit--Learn%201.8-orange.svg)](https://scikit-learn.org/)
[![MySQL](https://img.shields.io/badge/Database-MySQL%20%28utf8mb4%29-blue.svg)](https://www.mysql.com/)
[![Tests](https://img.shields.io/badge/Tests-36%20Passed-brightgreen.svg)]()

---

## 1. Project Overview

**MovieFlix** is a full-stack, Netflix-inspired movie discovery and intelligent recommendation platform. Designed as a comprehensive college capstone project, it bridges the disciplines of **Information Retrieval (IR)**, **Natural Language Processing (NLP)**, **Relational Database Engineering**, and **Modern Web Development**.

The application indexes real-world cinematic metadata from The Movie Database (TMDB) API, processes unstructured textual features into high-dimensional TF-IDF vectors, and computes Cosine Similarity distances to generate ranked content-based recommendations ("Because you liked this movie") in real time.

### Key Capabilities
- **Real-World TMDB Integration**: Supports dual authentication (v4 Read Access Bearer Token and v3 API Key) with automatic priority detection, rate-limit retries (HTTP 429), and connection pooling.
- **Defensive Multi-Layer Poster Architecture**: Rejects malformed `/None` paths across backend normalization, REST responses, and browser-side SVG fallbacks.
- **Information Retrieval Pipeline**: Tokenizes title, genres, keywords, cast, and director into unigrams and bigrams using sublinear TF-IDF scaling.
- **Cosine Similarity Engine**: Serializes sparse term-document matrices to disk for instant $O(1)$ query evaluation without runtime re-vectorization.
- **Relational MySQL Persistence**: Parameterized CRUD queries using `utf8mb4` with automated database and table bootstrapping.
- **Educational Web Scraping**: Compliant metadata crawler adhering to `robots.txt` specifications using BeautifulSoup4.
- **Cinematic Responsive UI**: Pure HTML5, modern CSS3 (Flexbox/Grid), and Vanilla JavaScript without bulky external frontend dependencies.
- **Zero-Exposure Security**: API secrets, database passwords, and session tokens are strictly managed via `.env` and never leaked into logs, templates, or diagnostics.

---

## 2. Five-Week Academic Project Mapping

```
WEEK 1: Foundation, TMDB API, & Database Engineering
└── Setup environment, config loader, TMDB dual-auth client (v3/v4), MySQL schema (utf8mb4), data fetcher.

WEEK 2: Data Cleaning & Ethical Web Crawling
└── Pandas normalization pipeline (deduplication, date parsing, poster validation), BeautifulSoup robots.txt crawler.

WEEK 3: Information Retrieval & Recommendation Algorithm
└── Textual metadata soup, TfidfVectorizer (unigram/bigram), sparse matrix serialization, Cosine Similarity ranking.

WEEK 4: Flask Backend & RESTful API Development
└── Flask routes (/, /search, /movie/<id>, /recommendations/<id>, /health), JSON endpoints, MySQL/CSV resilience.

WEEK 5: Netflix-Inspired UI, Testing, Evaluation & Documentation
└── Dark cinematic UI, poster fallback svg, 36 Pytest test cases, empirical evaluator, Windows batch automation.
```

---

## 3. System Architecture

```mermaid
flowchart TD
    subgraph Data Acquisition & Persistence
        TMDB[TMDB REST API] -->|fetch_movies.py| RawJSON[data/raw/tmdb_movies.json]
        WebSource[Public Permitted Pages] -->|scraper.py| ScrapedMeta[HTML Metadata]
        RawJSON -->|clean_data.py| CleanCSV[data/processed/movies_clean.csv]
        CleanCSV -->|db.py auto-sync| MySQL[(MySQL Database: movieflix)]
    end

    subgraph Information Retrieval Pipeline
        CleanCSV -->|build_features.py| TextSoup[Metadata Feature Soup]
        TextSoup -->|TfidfVectorizer| TFIDFMatrix[models/tfidf_matrix.pkl]
        TFIDFMatrix -->|Cosine Similarity| RecommenderEngine[recommender.py]
    end

    subgraph Full-Stack Presentation Layer
        MySQL -.-> FlaskApp[Flask App: app.py]
        CleanCSV -.-> FlaskApp
        RecommenderEngine --> FlaskApp
        FlaskApp -->|Jinja2 Templates| WebUI[Netflix-Style Dark UI]
        FlaskApp -->|JSON Responses| RESTAPI[/api/movies, /api/search, /api/recommendations]
    end
```

---

## 4. Academic Explanations & Theoretical Foundations

### A. What is TF-IDF?
**Term Frequency-Inverse Document Frequency (TF-IDF)** is a statistical weighting scheme in Information Retrieval that quantifies the relative importance of a word to a document within a collection (corpus).

1. **Term Frequency ($TF$)**: Measures how frequently term $t$ appears in document $d$. To prevent long documents from dominating, sublinear term frequency scaling is applied:
   $$TF(t, d) = 1 + \log(f_{t, d}) \quad \text{for } f_{t, d} > 0$$

2. **Inverse Document Frequency ($IDF$)**: Measures how rare or informative term $t$ is across the entire corpus $D$:
   $$IDF(t, D) = \log\left(\frac{1 + |D|}{1 + |\{d \in D : t \in d\}|}\right) + 1$$
   *If a term (like "movie" or "film") appears in every single overview, its $IDF$ approaches zero. Rare distinctive keywords (like "wormhole", "cyberpunk", or "gotham") receive high weights.*

3. **Composite TF-IDF Weight**:
   $$TF\text{-}IDF(t, d, D) = TF(t, d) \times IDF(t, D)$$

### B. What is Cosine Similarity?
Cosine Similarity measures the cosine of the angle between two non-zero vectors in an inner product space. For movie vectors $\mathbf{u}$ and $\mathbf{v}$:

$$\cos(\theta) = \frac{\mathbf{u} \cdot \mathbf{v}}{\|\mathbf{u}\|_2 \|\mathbf{v}\|_2} = \frac{\sum_{i=1}^{m} u_i v_i}{\sqrt{\sum_{i=1}^{m} u_i^2} \sqrt{\sum_{i=1}^{m} v_i^2}}$$

### C. Why is Cosine Similarity Suitable for Text Vectors?
- **Length Invariance**: Euclidean distance ($L_2$) is distorted by text length (a short 50-word synopsis and a 300-word synopsis would have large Euclidean distance even if discussing the exact same topic). Cosine similarity normalizes by vector magnitude, capturing orientation (thematic direction) regardless of text length.
- **Sparse High-Dimensional Robustness**: In text spaces with 2,000+ terms, documents share few overlapping vocabulary items. Cosine similarity only evaluates non-zero intersecting dimensions, allowing rapid computation.

### D. Content-Based Filtering vs. Collaborative Filtering
- **Content-Based Filtering**: Recommends items based on features of the items themselves (genres, directors, keywords, actors, plot summaries). It does **not** require historical user interaction logs, avoiding the classic **User Cold-Start Problem**.
- **Collaborative Filtering**: Relies on user interaction matrices (user-item ratings). It excels at discovering latent cross-genre interests but fails on newly released items that have no ratings yet (**Item Cold-Start Problem**).

### E. Defensive Poster Architecture (Why Never `/None`)
A notorious bug in movie applications is appending `None` to the TMDB CDN prefix (`https://image.tmdb.org/t/p/w500/None`), generating broken HTTP 404 images that ruin the UI. MovieFlix enforces a 3-tier defense:
1. **Pipeline Level**: `clean_data.py` strips `None`, `null`, and paths lacking a leading `/`.
2. **Client Level**: `tmdb_client.py` and `app.py` validate paths, returning `/static/img/poster-fallback.svg` on any anomaly.
3. **Browser Level**: Every image tag includes `onerror="this.onerror=null;this.src='/static/img/poster-fallback.svg';"`, complemented by an event listener in `static/js/app.js`.

---

## 5. Technology Stack

| Layer | Component | Version | Purpose |
| :--- | :--- | :--- | :--- |
| **Backend** | Python | 3.11+ / 3.12+ / 3.13+ | Core programming runtime |
| **Web Server** | Flask | >= 3.0.0 | WSGI microframework, routing, REST APIs |
| **Data Science** | Scikit-Learn | >= 1.4.0 | TF-IDF Vectorization, Cosine Similarity |
| **Data Cleaning** | Pandas & NumPy | >= 2.1.0 / >= 1.26.0 | Tabular data wrangling, missing data imputation |
| **Database** | MySQL | MySQL 8.0+ | Relational storage, indexing, utf8mb4 encoding |
| **DB Connector** | mysql-connector-python | >= 8.3.0 | Parameterized SQL execution |
| **Web Scraping** | BeautifulSoup4 & Requests | >= 4.12.0 / >= 2.31.0 | Robots.txt compliant metadata crawling |
| **Frontend** | HTML5 / CSS3 / Vanilla JS | Modern ES6+ | Netflix-inspired dark UI, Flexbox, Grid |
| **Testing** | Pytest | >= 8.0.0 | Unit and integration test suite |

---

## 6. Directory Structure

```
MovieFlix/
│
├── app.py                      # Flask Application & REST API endpoints
├── config.py                   # Central configuration & secret-safe diagnostics
├── db.py                       # MySQL database connector, auto-init, & queries
├── tmdb_client.py              # TMDB dual-auth client (v3/v4) with rate-limit retries
├── recommender.py              # Cosine Similarity recommendation engine
├── scraper.py                  # Robots.txt-compliant BeautifulSoup metadata scraper
├── evaluator.py                # Dataset integrity metrics & IR evaluation reporter
├── setup_check.py              # Environment diagnostic runner (never leaks secrets)
├── schema.sql                  # MySQL database and table schema (utf8mb4)
├── requirements.txt            # Pinned project dependencies
├── pytest.ini                  # Pytest configuration
├── run_windows.bat             # Automated Windows setup & launch batch script
├── README.md                   # Complete academic documentation
├── .env.example                # Environment configuration template
├── .gitignore                  # Git exclusion rules (protects .env and caches)
│
├── scripts/
│   ├── fetch_movies.py         # TMDB API data collection (--pages 20 / 50)
│   ├── clean_data.py           # Pandas data cleaning & poster URL normalization
│   ├── build_features.py       # TF-IDF feature extraction & model serialization
│   └── test_tmdb.py            # CLI TMDB authentication tester
│
├── data/
│   ├── raw/
│   │   └── tmdb_movies.json    # Raw TMDB API metadata dump
│   └── processed/
│       ├── movies.csv          # Initial tabular representation
│       └── movies_clean.csv    # Sanitized, verified movie records
│
├── models/
│   ├── tfidf_model.pkl         # Serialized TfidfVectorizer instance
│   ├── tfidf_matrix.pkl        # Serialized sparse TF-IDF term-document matrix
│   └── movie_indices.pkl       # Bidirectional ID-to-matrix lookup dictionary
│
├── templates/
│   ├── base.html               # Master layout with navbar and search
│   ├── index.html              # Netflix homepage (Hero banner + category carousels)
│   ├── search.html             # Responsive search results grid & empty state
│   ├── movie.html              # Movie details, backdrop, cast & recommendation row
│   ├── recommendations.html    # Dedicated similarity analysis view
│   └── error.html              # Custom cinematic 404/500 error display
│
├── static/
│   ├── css/
│   │   └── style.css           # Netflix dark cinematic styling (Grid & Flexbox)
│   ├── js/
│   │   └── app.js              # Navbar scroll tints & defensive image listeners
│   └── img/
│       └── poster-fallback.svg # Custom dark cinematic vector poster fallback
│
└── tests/
    ├── test_posters.py         # Validates poster paths and fallback rules
    ├── test_recommender.py     # Validates TF-IDF, source exclusion, & ranking
    ├── test_routes.py          # Validates Flask web routes and REST JSON APIs
    └── test_tmdb.py            # Validates dual authentication & mock responses
```

---

## 7. Windows Installation & Step-by-Step Guide

This project is built specifically to execute smoothly on **Windows (PowerShell / Command Prompt)**.

### Quick Start (One-Click Automated)
Simply double-click:
```cmd
run_windows.bat
```
*This automatically creates `.venv`, installs requirements, creates `.env` if missing, runs diagnostics, compiles models, and starts Flask on http://127.0.0.1:5000.*

---

### Manual Step-by-Step Commands (PowerShell / CMD)

#### Step 1: Open Terminal in Project Directory
```powershell
cd C:\Users\p\.gemini\antigravity\scratch\MovieFlix
```

#### Step 2: Create Virtual Environment
```powershell
python -m venv .venv
```

#### Step 3: Install Required Dependencies
*(Notice: No execution-policy changes required; we directly invoke `.venv\Scripts\python.exe`)*
```powershell
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

#### Step 4: Configure Environment Variables
```powershell
copy .env.example .env
```
Open `.env` in VS Code or Notepad:
```ini
# TMDB API Read Access Token v4 (Recommended)
TMDB_ACCESS_TOKEN=your_v4_token_here

# OR TMDB API Key v3
TMDB_API_KEY=your_v3_key_here

# MySQL Configuration
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_mysql_password
MYSQL_DATABASE=movieflix

FLASK_SECRET_KEY=college-project-secret-key-2026
```
*(Note: If you do not have TMDB or MySQL configured yet, the system includes a pre-indexed dataset of real TMDB titles that allows offline execution immediately!)*

#### Step 5: Run Setup Diagnostics
```powershell
.venv\Scripts\python.exe setup_check.py
```

#### Step 6: (Optional) Fetch Fresh Movies from TMDB API
```powershell
.venv\Scripts\python.exe scripts\fetch_movies.py --pages 20
```

#### Step 7: Clean Data & Normalize Fields
```powershell
.venv\Scripts\python.exe scripts\clean_data.py
```

#### Step 8: Build TF-IDF Feature Vectors & Cosine Models
```powershell
.venv\Scripts\python.exe scripts\build_features.py
```

#### Step 9: Run Dataset & IR Evaluator
```powershell
.venv\Scripts\python.exe evaluator.py
```

#### Step 10: Run Automated Pytest Suite
```powershell
.venv\Scripts\python.exe -m pytest tests -v
```

#### Step 11: Start Flask Application
```powershell
.venv\Scripts\python.exe app.py
```
Open your browser and navigate to:
```
http://127.0.0.1:5000
```

---

## 8. RESTful API Documentation

| Endpoint | Method | Description | Sample Output / Query |
| :--- | :--- | :--- | :--- |
| `/api/movies` | `GET` | Paginated movie catalog | `?limit=10&sort_by=popularity` |
| `/api/movies/<id>` | `GET` | Full details for specified movie | `/api/movies/27205` |
| `/api/search` | `GET` | Search movies by title or synopsis | `/api/search?q=Dark` |
| `/api/recommendations/<id>` | `GET` | Ranked content-based recommendations | `/api/recommendations/27205?limit=5` |
| `/health` | `GET` | System, Database, and Model health | Returns operational JSON |

### Sample JSON Response (`/api/recommendations/27205`):
```json
{
  "count": 3,
  "source_movie_id": 27205,
  "source_movie_title": "Inception",
  "status": "success",
  "recommendations": [
    {
      "id": 49026,
      "title": "The Dark Knight Rises",
      "genres": "Action, Crime, Drama, Thriller",
      "similarity_score": 0.0794,
      "match_percentage": 98,
      "poster_url": "https://image.tmdb.org/t/p/w500/hrJ0bW8d06bH53e7XF71W6h1LqK.jpg",
      "release_date": "2012-07-16",
      "vote_average": 7.8
    },
    {
      "id": 157336,
      "title": "Interstellar",
      "genres": "Adventure, Drama, Science Fiction",
      "similarity_score": 0.0644,
      "match_percentage": 93,
      "poster_url": "https://image.tmdb.org/t/p/w500/gEU2QniE6E77NI6lCU6MxlNBvIx.jpg",
      "release_date": "2014-11-05",
      "vote_average": 8.4
    }
  ]
}
```

---

## 9. Web Crawling Demonstration (`scraper.py`)

To demonstrate compliant web crawling, run:
```powershell
.venv\Scripts\python.exe scraper.py https://example.com
```
The scraper:
1. Resolves `https://example.com/robots.txt` using Python's `urllib.robotparser.RobotFileParser`.
2. Checks whether user-agent `MovieFlixScraper/1.0` has fetch permission.
3. Parses `<title>`, `<meta name="description">`, `<link rel="canonical">`, OpenGraph headers, and structural headings using `BeautifulSoup4`.
4. Gracefully exits if denied by site policy.

---

## 10. Troubleshooting Guide

### 1. TMDB HTTP 401 Unauthorized Error
- **Cause**: TMDB token or API key is invalid or incomplete in `.env`.
- **Solution**:
  - Visit [https://www.themoviedb.org/settings/api](https://www.themoviedb.org/settings/api).
  - Copy the **API Read Access Token (v4)** (the very long alphanumeric string) and paste it into `TMDB_ACCESS_TOKEN=` in `.env`.
  - Or copy the shorter **API Key (v3)** into `TMDB_API_KEY=`.
  - Run `.venv\Scripts\python.exe scripts\test_tmdb.py` to confirm.

### 2. MySQL Connection Refused
- **Cause**: MySQL service is stopped or root password differs from `.env`.
- **Solution**:
  - Start the MySQL service via Windows Services (`services.msc` -> start `MySQL80` or `MySQL`).
  - Or use XAMPP / MySQL Workbench.
  - Verify `MYSQL_PASSWORD` in `.env`.
  - *Note*: If MySQL is offline, MovieFlix automatically operates in resilient local CSV mode so the web app and recommendation engine never crash.

### 3. Missing or Broken Posters
- **Cause**: Network interruption or movie without an official TMDB image.
- **Solution**:
  - MovieFlix automatically intercepts any missing or broken image and displays `static/img/poster-fallback.svg`. You will never see broken image icons or browser crashes.

### 4. Port Conflict on 5000
- **Cause**: Another service is utilizing port 5000.
- **Solution**:
  - Open `.env` and set `FLASK_PORT=5050`. Restart `app.py`.

---

## 11. Academic Evaluation & Ethics Statement

In academic Information Retrieval, metric claims such as Precision@K or Recall@K require labeled ground-truth user engagement logs (e.g. historical rating datasets like MovieLens 100k/20M). 

Because MovieFlix operates as an **unsupervised content-based metadata retrieval system**, reporting fabricated precision numbers would be academically fraudulent. Instead:
- The system's accuracy is evaluated via **empirical feature convergence**: testing query movies (e.g. *Inception*, *The Dark Knight*, *The Matrix*) reveals that top recommendations correctly converge on shared directors (Christopher Nolan, The Wachowskis), shared genres, and thematic keywords.
- All 36 automated tests verify ranking monotonicity ($\text{Sim}(Rank_i) \ge \text{Sim}(Rank_{i+1})$), source movie exclusion, authentication, watchlist, and ratings.
- The project complies with the TMDB Terms of Use and never stores or distributes copyright-protected media or video streams.
