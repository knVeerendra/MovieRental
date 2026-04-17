import sqlite3
from pathlib import Path

from flask import current_app, g
from werkzeug.security import generate_password_hash


DEFAULT_MOVIES = [
    {
        "name": "Wrath of Man",
        "description": "A cash truck guard quietly hunts the crew behind a deadly robbery.",
        "genre": "Action Thriller",
        "release_year": 2021,
        "daily_rate": 4.99,
        "stock": 3,
        "image_name": "Wrath-of-man.jpg",
    },
    {
        "name": "Avatar",
        "description": "A marine enters the world of Pandora and faces a divided loyalty.",
        "genre": "Sci-Fi Adventure",
        "release_year": 2009,
        "daily_rate": 5.99,
        "stock": 4,
        "image_name": "avatar.jpg",
    },
    {
        "name": "Into the Wild",
        "description": "A young graduate leaves comfort behind for a life-changing wilderness journey.",
        "genre": "Drama",
        "release_year": 2007,
        "daily_rate": 3.99,
        "stock": 2,
        "image_name": "itw.jpg",
    },
    {
        "name": "Breaking Bad",
        "description": "A chemistry teacher turns to crime after a life-altering diagnosis.",
        "genre": "Crime Drama",
        "release_year": 2008,
        "daily_rate": 4.49,
        "stock": 5,
        "image_name": "bb.jpg",
    },
    {
        "name": "Deadpool",
        "description": "A sharp-tongued antihero tears through enemies with style and chaos.",
        "genre": "Action Comedy",
        "release_year": 2016,
        "daily_rate": 6.49,
        "stock": 3,
        "image_name": "deadpool.jpg",
    },
    {
        "name": "The Dark Knight",
        "description": "Batman faces the Joker in a battle that changes Gotham forever.",
        "genre": "Superhero Crime",
        "release_year": 2008,
        "daily_rate": 5.49,
        "stock": 4,
        "image_name": "dark.jpg",
    },
]

DEFAULT_ADMIN = {"email": "admin@example.com", "password": "admin123"}

SCHEMA = """
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
"""


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript(SCHEMA)
    apply_migrations(db)
    seed_defaults(db)
    db.commit()


def apply_migrations(db):
    ensure_columns(
        db,
        "users",
        {"created_at": "TEXT"},
    )
    ensure_columns(
        db,
        "admins",
        {
            "role": "TEXT NOT NULL DEFAULT 'admin'",
            "created_at": "TEXT",
        },
    )
    ensure_columns(
        db,
        "movies",
        {
            "description": "TEXT NOT NULL DEFAULT ''",
            "genre": "TEXT NOT NULL DEFAULT 'General'",
            "release_year": "INTEGER",
            "daily_rate": "REAL NOT NULL DEFAULT 0",
            "price": "REAL NOT NULL DEFAULT 0",
            "stock": "INTEGER NOT NULL DEFAULT 1",
            "image_name": "TEXT",
            "created_at": "TEXT",
        },
    )


def ensure_columns(db, table_name, columns):
    existing_columns = {
        row["name"] for row in db.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
    for column_name, definition in columns.items():
        if column_name not in existing_columns:
            db.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")


def seed_defaults(db):
    for movie in DEFAULT_MOVIES:
        db.execute(
            """
            INSERT INTO movies (
                name, description, genre, release_year, daily_rate, price, stock, image_name
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                description = excluded.description,
                genre = excluded.genre,
                release_year = excluded.release_year,
                daily_rate = excluded.daily_rate,
                price = excluded.price,
                stock = excluded.stock,
                image_name = excluded.image_name
            """,
            (
                movie["name"],
                movie["description"],
                movie["genre"],
                movie["release_year"],
                movie["daily_rate"],
                movie["daily_rate"],
                movie["stock"],
                movie["image_name"],
            ),
        )

    admin = db.execute(
        "SELECT id, password FROM admins WHERE email = ?",
        (DEFAULT_ADMIN["email"],),
    ).fetchone()
    hashed_password = generate_password_hash(DEFAULT_ADMIN["password"])
    if admin is None:
        db.execute(
            "INSERT INTO admins (email, role, password) VALUES (?, ?, ?)",
            (DEFAULT_ADMIN["email"], "admin", hashed_password),
        )
    elif admin["password"] == DEFAULT_ADMIN["password"]:
        db.execute(
            "UPDATE admins SET password = ? WHERE id = ?",
            (hashed_password, admin["id"]),
        )


def init_app(app):
    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    with app.app_context():
        init_db()


def fetch_one(query, params=()):
    return get_db().execute(query, params).fetchone()


def fetch_all(query, params=()):
    return get_db().execute(query, params).fetchall()


def execute(query, params=()):
    db = get_db()
    cursor = db.execute(query, params)
    db.commit()
    return cursor
