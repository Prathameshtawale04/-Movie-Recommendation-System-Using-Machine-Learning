-- ==============================================================================
-- MovieFlix Database Schema
-- Database: movieflix
-- Encoding: utf8mb4 / utf8mb4_unicode_ci
-- ==============================================================================

CREATE DATABASE IF NOT EXISTS movieflix
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE movieflix;

-- -----------------------------------------------------------------------------
-- 1. Movies Table
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS movies (
    id INT PRIMARY KEY,
    tmdb_id INT,
    title VARCHAR(255) NOT NULL,
    original_title VARCHAR(255),
    overview TEXT,
    release_date VARCHAR(20),
    genres TEXT,
    popularity FLOAT DEFAULT 0.0,
    vote_average FLOAT DEFAULT 0.0,
    vote_count INT DEFAULT 0,
    poster_path VARCHAR(255),
    poster_url VARCHAR(500),
    backdrop_path VARCHAR(255),
    backdrop_url VARCHAR(500),
    original_language VARCHAR(10) DEFAULT 'en',
    cast TEXT,
    director VARCHAR(255),
    keywords TEXT,
    runtime INT DEFAULT 0,
    adult BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_tmdb_id (tmdb_id),
    INDEX idx_title (title),
    INDEX idx_popularity (popularity),
    INDEX idx_vote_average (vote_average),
    INDEX idx_release_date (release_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- 2. Users Table
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    username VARCHAR(50),
    email VARCHAR(120) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_email (email),
    INDEX idx_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- 3. Watchlist Table
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS watchlist (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    movie_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_user_movie_watchlist (user_id, movie_id),
    INDEX idx_watchlist_user (user_id),
    INDEX idx_watchlist_movie (movie_id),
    CONSTRAINT fk_watchlist_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_watchlist_movie FOREIGN KEY (movie_id) REFERENCES movies(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- 4. Ratings Table
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ratings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    movie_id INT NOT NULL,
    rating FLOAT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_user_movie_rating (user_id, movie_id),
    INDEX idx_ratings_user (user_id),
    INDEX idx_ratings_movie (movie_id),
    CONSTRAINT chk_rating_range CHECK (rating >= 1.0 AND rating <= 5.0),
    CONSTRAINT fk_ratings_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_ratings_movie FOREIGN KEY (movie_id) REFERENCES movies(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- 5. User Activity Table (Optional Auditing & Interaction Tracking)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_activity (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    activity_type VARCHAR(50) NOT NULL,
    movie_id INT,
    details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_activity_user (user_id),
    INDEX idx_activity_type (activity_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
