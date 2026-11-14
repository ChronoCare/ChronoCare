import os
from datetime import date
from flask import Flask, render_template, redirect, url_for, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from flask_wtf.csrf import CSRFProtect
from dotenv import load_dotenv

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()
login_manager.login_view = "auth.login"
load_dotenv()  # reads GROQ_API_KEY, SECRET_KEY, ... from the .env file



def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-only-change-me")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///chronocare.db")
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    # Login and signup live in App/auth/__init__.py
    from .auth import auth as auth_bp
    app.register_blueprint(auth_bp)

    # Diet plan page and its API live in App/plans/routes.py
    from .plans.routes import bp as plans_bp
    app.register_blueprint(plans_bp)

    # Exercise page and its API live in App/plans/exercise.py
    from .plans.exercise import bp as exercise_bp
    app.register_blueprint(exercise_bp)


    @app.after_request
    def no_store_for_logged_in_pages(response):
        # Browsers won't keep a copy of private pages, so Back can't show them after logout
        if request.endpoint != "static" and current_user.is_authenticated:
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.route("/")
    def index():
        # Logged-out visitors see the login page first
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))
        return render_template("index.html")

    @app.route("/sleep")
    def sleep():
        return render_template("sleep.html")

    @app.route("/insights")
    def insights():
        return render_template("insights.html")

    @app.route("/profile")
    def profile():
        return render_template("profile.html")

    @app.context_processor
    def inject_year():
        return {"now_year": date.today().year}

    with app.app_context():
        from . import models  # noqa: F401  (so the tables get created)
        db.create_all()

    return app