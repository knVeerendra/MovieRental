from app import app
from models import DEFAULT_ADMIN, fetch_one


with app.app_context():
    admin = fetch_one("SELECT email FROM admins WHERE email = ?", (DEFAULT_ADMIN["email"],))
    if admin:
        print(f"Admin is ready: {admin['email']}")
    else:
        print("Admin record is missing. Start the app once to seed the database.")
