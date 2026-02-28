import os
from datetime import timedelta
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

# Application-wide configuration
class Config:
    SECRET_KEY = os.environ.get("CAMPUS_PULSE_SECRET_KEY") or os.urandom(32)
    SQLALCHEMY_DATABASE_URI = os.environ.get("CAMPUS_PULSE_DATABASE_URL") or "sqlite:///campus_pulse.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_NAME = "cp_session"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = bool(os.environ.get("CAMPUS_PULSE_SECURE_COOKIES", "0") == "1")
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    UPLOAD_FOLDER = os.environ.get("CAMPUS_PULSE_UPLOADS") or os.path.join(os.getcwd(), "uploads")


def create_app(config_object: type[Config] | None = None) -> Flask:
    app = Flask(__name__, template_folder="templates")
    app.config.from_object(config_object or Config)

    # Ensure upload folder exists
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # Initialize database
    from .models import db  # Local import to avoid circulars
    db.init_app(app)

    with app.app_context():
        db.create_all()

    # Register routes
    from .routes import main_bp, auth_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")

    return app
