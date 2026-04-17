CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS admins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    role TEXT NOT NULL DEFAULT 'admin',
    password TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS movies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    genre TEXT NOT NULL DEFAULT 'General',
    release_year INTEGER,
    daily_rate REAL NOT NULL DEFAULT 0,
    price REAL NOT NULL DEFAULT 0,
    stock INTEGER NOT NULL DEFAULT 1,
    image_name TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS rentals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    movie_id INTEGER NOT NULL,
    rental_days INTEGER NOT NULL,
    total_price REAL NOT NULL,
    rented_on TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    due_on TEXT NOT NULL,
    returned_on TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (movie_id) REFERENCES movies(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_rentals_user_active
ON rentals (user_id, returned_on);

CREATE INDEX IF NOT EXISTS idx_rentals_movie_active
ON rentals (movie_id, returned_on);



