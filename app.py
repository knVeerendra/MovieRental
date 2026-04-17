import os
from flask import Flask

from models import close_db, init_app
from routes import register_routes


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")
    os.makedirs(app.instance_path, exist_ok=True)
    app.config["DATABASE"] = os.path.join(app.instance_path, "movie_rental_system.db")
    app.config["UPLOAD_FOLDER"] = os.path.join(app.static_folder, "uploads")
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    init_app(app)
    register_routes(app)
    app.teardown_appcontext(close_db)

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
