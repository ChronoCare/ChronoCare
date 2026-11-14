import os
from datetime import date
from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user, login_required
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
    db.init_app(app); login_manager.init_app(app); csrf.init_app(app)

    # Blueprints: login/sign-up, then one for each page
    from .auth import auth as auth_bp, ChangePasswordForm
    app.register_blueprint(auth_bp)
    from .plans.routes import bp as plans_bp          # diet plan
    app.register_blueprint(plans_bp)
    from .plans.exercise import bp as exercise_bp     # exercise
    app.register_blueprint(exercise_bp)
    from .plans.sleep import bp as sleep_bp           # sleep
    app.register_blueprint(sleep_bp)

    # Overview page (the "/" route below) and its API live in App/plans/overview.py
    from .plans.overview import bp as overview_bp, render_overview
    app.register_blueprint(overview_bp)

    from .plans.insights import bp as insights_bp     # insights
    app.register_blueprint(insights_bp)

    @app.after_request
    def no_store_for_logged_in_pages(response):
        # Stops the Back button from showing private pages after logging out
        if request.endpoint != "static" and current_user.is_authenticated:
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.route("/")
    def index():
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))
        return render_overview()

    @app.route("/profile", methods=["GET", "POST"])
    @login_required
    def profile():
        if current_user.profile is None:
            return redirect(url_for("auth.about_you"))
        form = ChangePasswordForm()
        if form.validate_on_submit():
            current_user.set_password(form.new_password.data)
            db.session.commit()
            flash("Your password has been changed.", "ok")
            return redirect(url_for("profile"))
        return render_template("profile.html", form=form, profile=current_user.profile)

    @app.context_processor
    def inject_year():
        return {"now_year": date.today().year}

    with app.app_context():
        from . import models  # noqa: F401
        db.create_all()

    return app