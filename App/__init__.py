import os
from datetime import date
from flask import Flask, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from flask_wtf import FlaskForm
from flask_wtf.csrf import CSRFProtect
from wtforms import StringField, PasswordField, SubmitField, BooleanField
from wtforms.validators import DataRequired, Email, ValidationError, Length

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()
login_manager.login_view = "auth.login"

# Must come after db and login_manager exist, or models.py can't import them
from .models import User  # noqa: E402


# Forms
class SignupForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=8, max=128)])
    submit = SubmitField("Create account")

    def validate_email(self, field):
        if User.query.filter_by(email=field.data.strip().lower()).first():
            raise ValidationError("An account with this email already exists. Try logging in.")


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    remember_me = BooleanField("Keep me logged in")
    submit = SubmitField("Log in")


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-only-change-me")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///chronocare.db")

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    # Login and signup live in app/auth/__init__.py
    from .auth import auth as auth_bp
    app.register_blueprint(auth_bp)

    # Pages
    @app.route("/")
    def index():
        # Logged-out visitors see the login page first
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))
        return render_template("index.html")

    @app.route("/diet_plan")
    def diet_plan():
        return render_template("diet_plan.html")

    @app.route("/exercise")
    def exercise():
        return render_template("exercise.html")

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
        db.create_all()

    return app