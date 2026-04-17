import os
import sqlite3
from datetime import datetime, timedelta
from uuid import uuid4

from flask import abort, flash, jsonify, redirect, render_template, request, session, url_for
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash, generate_password_hash

from models import execute, fetch_all, fetch_one


def register_main_routes(app):
    @app.route("/")
    def index():
        if session.get("admin_id"):
            return redirect(url_for("admin_dashboard"))
        if session.get("user_id"):
            return redirect(url_for("dashboard"))
        return redirect(url_for("login"))

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if request.method == "POST":
            username = request.form["username"].strip()
            email = request.form["email"].strip().lower()
            password = request.form["password"]

            if not username or not email or not password:
                flash("All fields are required.", "danger")
                return redirect(url_for("register"))

            existing_user = fetch_one("SELECT id FROM users WHERE email = ?", (email,))
            if existing_user:
                flash("That email is already registered.", "danger")
                return redirect(url_for("register"))

            execute(
                "INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
                (username, email, generate_password_hash(password)),
            )
            flash("Account created. You can sign in now.", "success")
            return redirect(url_for("login"))

        return render_template("user_register.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email = request.form["email"].strip().lower()
            password = request.form["password"]
            user = fetch_one("SELECT * FROM users WHERE email = ?", (email,))

            if user and check_password_hash(user["password"], password):
                session.clear()
                session["user_id"] = user["id"]
                session["username"] = user["username"]
                flash(f"Welcome back, {user['username']}.", "success")
                return redirect(url_for("dashboard"))

            flash("Invalid email or password.", "danger")

        return render_template("user_login.html")

    @app.route("/dashboard")
    def dashboard():
        user_id = session.get("user_id")
        if not user_id:
            return redirect(url_for("login"))
        catalog_movies = fetch_all(
            """
            SELECT
                m.*,
                (m.stock - COALESCE(active.active_count, 0)) AS available_stock,
                ur.id AS user_rental_id,
                ur.due_on AS user_due_on
            FROM movies m
            LEFT JOIN (
                SELECT movie_id, COUNT(*) AS active_count
                FROM rentals
                WHERE returned_on IS NULL
                GROUP BY movie_id
            ) active ON active.movie_id = m.id
            LEFT JOIN (
                SELECT id, movie_id, due_on, total_price
                FROM rentals
                WHERE user_id = ? AND returned_on IS NULL
            ) ur ON ur.movie_id = m.id
            ORDER BY m.name
            """,
            (user_id,),
        )
        active_rentals = fetch_all(
            """
            SELECT
                r.id,
                r.rented_on,
                r.due_on,
                r.rental_days,
                r.total_price,
                m.name AS movie_name
            FROM rentals r
            JOIN movies m ON m.id = r.movie_id
            WHERE r.user_id = ? AND r.returned_on IS NULL
            ORDER BY r.due_on
            """,
            (user_id,),
        )
        rental_history = fetch_all(
            """
            SELECT
                r.id,
                r.rented_on,
                r.due_on,
                r.returned_on,
                r.total_price,
                m.name AS movie_name
            FROM rentals r
            JOIN movies m ON m.id = r.movie_id
            WHERE r.user_id = ? AND r.returned_on IS NOT NULL
            ORDER BY r.returned_on DESC
            LIMIT 8
            """,
            (user_id,),
        )
        stats = fetch_one(
            """
            SELECT
                COUNT(*) AS rental_count,
                COALESCE(SUM(total_price), 0) AS total_spent
            FROM rentals
            WHERE user_id = ?
            """,
            (user_id,),
        )
        recommendations = fetch_recommendations(user_id)
        return render_template(
            "catalog_dark.html",
            movies=catalog_movies,
            active_rentals=active_rentals,
            rental_history=rental_history,
            stats=stats,
            recommendations=recommendations,
        )

    @app.post("/rent/<int:movie_id>")
    def rent_movie(movie_id):
        user_id = session.get("user_id")
        if not user_id:
            return redirect(url_for("login"))
        rental_days = clamp_rental_days(request.form.get("rental_days", "3"))
        rental, error_message, _ = create_rental_record(user_id, movie_id, rental_days)
        if rental is None:
            flash(error_message, "danger")
            return redirect(url_for("dashboard"))

        flash(f"{rental['movie_name']} rented for {rental['rental_days']} day(s).", "success")
        return redirect(url_for("dashboard"))

    @app.post("/return/<int:rental_id>")
    def return_movie(rental_id):
        user_id = session.get("user_id")
        has_admin_access = has_admin_session()
        rental, error_message, status_code = return_rental_record(
            rental_id,
            acting_user_id=user_id,
            is_admin_user=has_admin_access,
        )
        if rental is None:
            if status_code == 404:
                abort(404)
            if status_code == 403:
                abort(403)
            flash(error_message, "danger")
            return redirect(url_for("admin_dashboard" if has_admin_access else "dashboard"))

        flash(f"{rental['movie_name']} returned successfully.", "success")
        return redirect(url_for("admin_dashboard" if has_admin_access else "dashboard"))

    @app.get("/api/movies")
    def api_get_movies():
        movie_rows = fetch_all(
            """
            SELECT
                m.id,
                m.name,
                m.description,
                m.genre,
                m.release_year,
                m.daily_rate,
                m.stock,
                m.image_name,
                (m.stock - COALESCE(active.active_count, 0)) AS available_stock
            FROM movies m
            LEFT JOIN (
                SELECT movie_id, COUNT(*) AS active_count
                FROM rentals
                WHERE returned_on IS NULL
                GROUP BY movie_id
            ) active ON active.movie_id = m.id
            ORDER BY m.name
            """
        )
        return jsonify({"movies": [serialize_movie_record(movie_row) for movie_row in movie_rows]})

    @app.post("/api/rent")
    def api_rent_movie():
        payload = request.get_json(silent=True) or {}
        user_id = payload.get("user_id")
        movie_id = payload.get("movie_id")
        rental_days = clamp_rental_days(payload.get("rental_days", 3))

        if user_id is None or movie_id is None:
            return jsonify({"error": "user_id and movie_id are required."}), 400

        rental, error_message, status_code = create_rental_record(user_id, movie_id, rental_days)
        if rental is None:
            return jsonify({"error": error_message}), status_code

        return (
            jsonify(
                {
                    "message": "Movie rented successfully.",
                    "rental": serialize_rental_record(rental),
                }
            ),
            201,
        )

    @app.post("/api/return")
    def api_return_movie():
        payload = request.get_json(silent=True) or {}
        rental_id = payload.get("rental_id")
        user_id = payload.get("user_id")
        is_admin_user = bool(payload.get("is_admin", False))

        if rental_id is None:
            return jsonify({"error": "rental_id is required."}), 400

        rental, error_message, status_code = return_rental_record(
            rental_id,
            acting_user_id=user_id,
            is_admin_user=is_admin_user,
        )
        if rental is None:
            return jsonify({"error": error_message}), status_code

        return jsonify(
            {
                "message": "Movie returned successfully.",
                "rental": serialize_rental_record(rental),
            }
        )

    @app.route("/admin_login", methods=["GET", "POST"])
    def admin_login():
        if request.method == "POST":
            email = request.form["email"].strip().lower()
            password = request.form["password"]
            admin = fetch_one("SELECT * FROM admins WHERE email = ?", (email,))

            if admin and check_password_hash(admin["password"], password):
                session.clear()
                session["admin_id"] = admin["id"]
                session["admin_email"] = admin["email"]
                session["admin_role"] = admin["role"]
                flash("Admin session started.", "success")
                return redirect(url_for("admin_dashboard"))

            flash("Invalid admin credentials.", "danger")

        return render_template("admin_login_new.html")

    @app.route("/admin_dashboard", methods=["GET", "POST"])
    def admin_dashboard():
        if not has_admin_session():
            return redirect(url_for("admin_login"))

        if request.method == "POST":
            action = request.form.get("action")
            if action == "add_movie":
                name = request.form["name"].strip()
                genre = request.form["genre"].strip() or "General"
                price_value = request.form["price"].strip()
                image_file = request.files.get("image")
                image_name = save_uploaded_image(image_file, app.config["UPLOAD_FOLDER"])

                try:
                    execute(
                        """
                        INSERT INTO movies (
                            name, description, genre, release_year, daily_rate, price, stock, image_name
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            name,
                            "",
                            genre,
                            None,
                            float(price_value),
                            float(price_value),
                            1,
                            image_name,
                        ),
                    )
                except sqlite3.IntegrityError:
                    flash("A movie with that name already exists.", "danger")
                else:
                    flash("Movie added to the catalog.", "success")
                return redirect(url_for("admin_dashboard"))

            if action == "delete_movie":
                movie_id = request.form["movie_id"]
                execute("DELETE FROM movies WHERE id = ?", (movie_id,))
                flash("Movie deleted.", "success")
                return redirect(url_for("admin_dashboard"))

            if action == "update_price":
                movie_id = request.form["movie_id"]
                price_value = float(request.form["price"])
                execute(
                    "UPDATE movies SET price = ?, daily_rate = ? WHERE id = ?",
                    (price_value, price_value, movie_id),
                )
                flash("Movie price updated.", "success")
                return redirect(url_for("admin_dashboard"))

        stats = fetch_one(
            """
            SELECT
                (SELECT COUNT(*) FROM users) AS user_count,
                (SELECT COUNT(*) FROM movies) AS movie_count,
                (SELECT COUNT(*) FROM rentals WHERE returned_on IS NULL) AS active_rentals,
                (SELECT COUNT(*) FROM rentals WHERE returned_on IS NULL AND due_on < CURRENT_TIMESTAMP) AS overdue_rentals,
                (SELECT COALESCE(SUM(total_price), 0) FROM rentals) AS revenue
            """
        )
        movies = fetch_all(
            """
            SELECT
                m.*,
                COALESCE(active.active_count, 0) AS active_count,
                (m.stock - COALESCE(active.active_count, 0)) AS available_stock
            FROM movies m
            LEFT JOIN (
                SELECT movie_id, COUNT(*) AS active_count
                FROM rentals
                WHERE returned_on IS NULL
                GROUP BY movie_id
            ) active ON active.movie_id = m.id
            ORDER BY m.name
            """
        )
        active_rentals = fetch_all(
            """
            SELECT
                r.id,
                u.username,
                u.email,
                m.name AS movie_name,
                r.rental_days,
                r.total_price,
                r.rented_on,
                r.due_on
            FROM rentals r
            JOIN users u ON u.id = r.user_id
            JOIN movies m ON m.id = r.movie_id
            WHERE r.returned_on IS NULL
            ORDER BY r.due_on
            """
        )
        recent_rentals = fetch_all(
            """
            SELECT
                u.username,
                m.name AS movie_name,
                r.total_price,
                r.rented_on,
                r.returned_on
            FROM rentals r
            JOIN users u ON u.id = r.user_id
            JOIN movies m ON m.id = r.movie_id
            ORDER BY r.rented_on DESC
            LIMIT 10
            """
        )
        return render_template(
            "admin_overview.html",
            stats=stats,
            movies=movies,
            active_rentals=active_rentals,
            recent_rentals=recent_rentals,
        )

    @app.route("/admin_charts")
    def admin_charts():
        if not has_admin_session():
            return redirect(url_for("admin_login"))
        leaderboard = fetch_all(
            """
            SELECT
                u.username,
                COUNT(r.id) AS rentals,
                COALESCE(SUM(r.total_price), 0) AS spent
            FROM users u
            LEFT JOIN rentals r ON r.user_id = u.id
            GROUP BY u.id, u.username
            ORDER BY rentals DESC, spent DESC, u.username
            LIMIT 10
            """
        )
        movie_breakdown = fetch_all(
            """
            SELECT
                m.name,
                COUNT(r.id) AS rental_count,
                COALESCE(SUM(r.total_price), 0) AS revenue
            FROM movies m
            LEFT JOIN rentals r ON r.movie_id = m.id
            GROUP BY m.id, m.name
            ORDER BY rental_count DESC, revenue DESC, m.name
            """
        )
        return render_template(
            "reports.html",
            leaderboard=leaderboard,
            movie_breakdown=movie_breakdown,
        )

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))


def has_admin_session():
    return bool(session.get("admin_id")) and session.get("admin_role") == "admin"


def save_uploaded_image(image_file, upload_folder):
    if image_file is None or not image_file.filename:
        return None

    safe_name = secure_filename(image_file.filename)
    if not safe_name:
        return None

    unique_name = f"{uuid4().hex}_{safe_name}"
    image_file.save(os.path.join(upload_folder, unique_name))
    return f"uploads/{unique_name}"


def fetch_recommendations(user_id, limit=4):
    recommendations = fetch_all(
        """
        WITH preferred_genres AS (
            SELECT
                m.genre,
                COUNT(*) AS rental_count,
                MAX(r.rented_on) AS last_rented_on
            FROM rentals r
            JOIN movies m ON m.id = r.movie_id
            WHERE r.user_id = ?
            GROUP BY m.genre
        ),
        available_movies AS (
            SELECT
                m.id,
                m.name,
                m.description,
                m.genre,
                m.release_year,
                m.daily_rate,
                m.image_name,
                (m.stock - COALESCE(active.active_count, 0)) AS available_stock,
                CASE WHEN EXISTS (
                    SELECT 1
                    FROM rentals ur
                    WHERE ur.user_id = ?
                        AND ur.movie_id = m.id
                        AND ur.returned_on IS NULL
                ) THEN 1 ELSE 0 END AS is_user_active
            FROM movies m
            LEFT JOIN (
                SELECT movie_id, COUNT(*) AS active_count
                FROM rentals
                WHERE returned_on IS NULL
                GROUP BY movie_id
            ) active ON active.movie_id = m.id
        )
        SELECT
            a.*,
            COALESCE(pg.rental_count, 0) AS genre_match_score
        FROM available_movies a
        LEFT JOIN preferred_genres pg ON pg.genre = a.genre
        WHERE a.available_stock > 0
            AND a.is_user_active = 0
            AND NOT EXISTS (
                SELECT 1
                FROM rentals rr
                WHERE rr.user_id = ?
                    AND rr.movie_id = a.id
            )
        ORDER BY
            genre_match_score DESC,
            pg.last_rented_on DESC,
            a.release_year DESC,
            a.name ASC
        LIMIT ?
        """,
        (user_id, user_id, user_id, limit),
    )
    if recommendations:
        return recommendations

    return fetch_all(
        """
        SELECT
            m.id,
            m.name,
            m.description,
            m.genre,
            m.release_year,
            m.daily_rate,
            m.image_name,
            (m.stock - COALESCE(active.active_count, 0)) AS available_stock
        FROM movies m
        LEFT JOIN (
            SELECT movie_id, COUNT(*) AS active_count
            FROM rentals
            WHERE returned_on IS NULL
            GROUP BY movie_id
        ) active ON active.movie_id = m.id
        WHERE (m.stock - COALESCE(active.active_count, 0)) > 0
        ORDER BY m.release_year DESC, m.name ASC
        LIMIT ?
        """,
        (limit,),
    )


def create_rental_record(user_id, movie_id, rental_days):
    user = fetch_one("SELECT id FROM users WHERE id = ?", (user_id,))
    if user is None:
        return None, "User not found.", 404

    movie = fetch_one("SELECT * FROM movies WHERE id = ?", (movie_id,))
    if movie is None:
        return None, "Movie not found.", 404

    active_rental = fetch_one(
        """
        SELECT id FROM rentals
        WHERE user_id = ? AND movie_id = ? AND returned_on IS NULL
        """,
        (user_id, movie_id),
    )
    if active_rental:
        return None, "You already have this movie rented.", 409

    availability = fetch_one(
        """
        SELECT m.stock - COUNT(r.id) AS available_stock
        FROM movies m
        LEFT JOIN rentals r
            ON r.movie_id = m.id
            AND r.returned_on IS NULL
        WHERE m.id = ?
        GROUP BY m.id, m.stock
        """,
        (movie_id,),
    )
    if availability is None or availability["available_stock"] <= 0:
        return None, "That title is currently unavailable.", 409

    due_on = datetime.utcnow() + timedelta(days=rental_days)
    total_price = float(movie["daily_rate"]) * rental_days
    rental_id = execute(
        """
        INSERT INTO rentals (user_id, movie_id, rental_days, total_price, due_on)
        VALUES (?, ?, ?, ?, ?)
        """,
        (user_id, movie_id, rental_days, total_price, due_on.isoformat(timespec="seconds")),
    ).lastrowid
    rental = fetch_one(
        """
        SELECT r.*, m.name AS movie_name
        FROM rentals r
        JOIN movies m ON m.id = r.movie_id
        WHERE r.id = ?
        """,
        (rental_id,),
    )
    return rental, None, 201


def return_rental_record(rental_id, acting_user_id=None, is_admin_user=False):
    rental = fetch_one(
        """
        SELECT r.*, m.name AS movie_name
        FROM rentals r
        JOIN movies m ON m.id = r.movie_id
        WHERE r.id = ?
        """,
        (rental_id,),
    )
    if rental is None:
        return None, "Rental not found.", 404

    if not is_admin_user and rental["user_id"] != acting_user_id:
        return None, "You are not allowed to return this rental.", 403

    if rental["returned_on"] is not None:
        return None, "That rental has already been returned.", 409

    execute(
        "UPDATE rentals SET returned_on = CURRENT_TIMESTAMP WHERE id = ?",
        (rental_id,),
    )
    updated_rental = fetch_one(
        """
        SELECT r.*, m.name AS movie_name
        FROM rentals r
        JOIN movies m ON m.id = r.movie_id
        WHERE r.id = ?
        """,
        (rental_id,),
    )
    return updated_rental, None, 200


def serialize_movie_record(movie):
    return {
        "id": movie["id"],
        "name": movie["name"],
        "description": movie["description"],
        "genre": movie["genre"],
        "release_year": movie["release_year"],
        "daily_rate": movie["daily_rate"],
        "stock": movie["stock"],
        "available_stock": movie["available_stock"],
        "image_name": movie["image_name"],
    }


def serialize_rental_record(rental):
    return {
        "id": rental["id"],
        "user_id": rental["user_id"],
        "movie_id": rental["movie_id"],
        "movie_name": rental["movie_name"],
        "rental_days": rental["rental_days"],
        "total_price": rental["total_price"],
        "rented_on": rental["rented_on"],
        "due_on": rental["due_on"],
        "returned_on": rental["returned_on"],
    }


def clamp_rental_days(value):
    try:
        rental_days = int(value)
    except (TypeError, ValueError):
        return 3
    return min(max(rental_days, 1), 14)
