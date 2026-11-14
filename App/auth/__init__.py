from flask import Blueprint, render_template, redirect, url_for, session
from flask_login import login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from wtforms import (StringField, PasswordField, BooleanField, SubmitField,
                     IntegerField, FloatField, SelectField, SelectMultipleField, widgets)
from wtforms.validators import (DataRequired, Email, EqualTo, Length,
                                NumberRange, ValidationError)

from .. import db
from ..models import User, Profile

auth = Blueprint("auth", __name__, url_prefix="/auth")

# Choices for the About you page
SEX_CHOICES = [("", "Prefer not to say"), ("female", "Female"),
               ("male", "Male"), ("intersex", "Intersex")]

ETHNICITY_CHOICES = [
    ("", "Prefer not to say"), ("south_asian", "South Asian"),
    ("east_asian", "East Asian"), ("southeast_asian", "Southeast Asian"),
    ("black", "Black / African / Caribbean"), ("hispanic", "Hispanic / Latino"),
    ("indigenous", "Indigenous"), ("middle_eastern", "Middle Eastern / North African"),
    ("white", "White"), ("mixed", "Mixed"), ("other", "Other"),
]

DIET_CHOICES = [
    ("vegetarian", "Vegetarian"), ("vegan", "Vegan"), ("pescatarian", "Pescatarian"),
    ("halal", "Halal"), ("kosher", "Kosher"), ("gluten_free", "Gluten-free"),
    ("dairy_free", "Dairy-free"), ("egg_free", "Egg-free"), ("soy_free", "Soy-free"),
    ("nut_allergy", "Nut allergy"), ("shellfish_allergy", "Shellfish allergy"),
]

CONDITION_CHOICES = [
    ("type1", "Type 1 diabetes"), ("type2", "Type 2 diabetes"),
    ("prediabetes", "Prediabetes"), ("celiac", "Celiac disease"),
    ("iron_deficiency", "Iron deficiency"), ("hypertension", "High blood pressure"),
]

# Readable names for stored codes, used by the "pretty" template filter
LABELS = {code: label
          for group in (SEX_CHOICES, ETHNICITY_CHOICES, DIET_CHOICES, CONDITION_CHOICES)
          for code, label in group if code}


@auth.app_template_filter("pretty")
def pretty(code):
    return LABELS.get(code, str(code).replace("_", " ").capitalize())


# Forms
class CheckboxField(SelectMultipleField):
    widget = widgets.ListWidget(prefix_label=False)
    option_widget = widgets.CheckboxInput()


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


class AboutYouForm(FlaskForm):
    first_name = StringField("First name", validators=[DataRequired(), Length(max=80)])
    last_name = StringField("Last name", validators=[DataRequired(), Length(max=80)])
    age = IntegerField("Age", validators=[DataRequired(), NumberRange(min=1, max=120)])
    height_cm = FloatField("Height (cm)", validators=[DataRequired(), NumberRange(min=50, max=250)])
    weight_kg = FloatField("Weight (kg)", validators=[DataRequired(), NumberRange(min=20, max=350)])
    sex = SelectField("Sex (optional)", choices=SEX_CHOICES)
    ethnicity = SelectField("Ethnicity (optional)", choices=ETHNICITY_CHOICES)
    dietary = CheckboxField("Dietary restrictions or allergies (optional)", choices=DIET_CHOICES)
    diagnosed = CheckboxField("Conditions I've been diagnosed with", choices=CONDITION_CHOICES)
    concerned = CheckboxField("Conditions I'm concerned about developing", choices=CONDITION_CHOICES)
    submit = SubmitField("Continue")


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField("Current password", validators=[DataRequired()])
    new_password = PasswordField("New password", validators=[DataRequired(), Length(min=8, max=128)])
    confirm_password = PasswordField("Confirm new password", validators=[
        DataRequired(), EqualTo("new_password", message="Passwords don't match.")])
    submit = SubmitField("Change password")

    def validate_current_password(self, field):
        if not current_user.check_password(field.data):
            raise ValidationError("That isn't your current password.")

    def validate_new_password(self, field):
        if current_user.check_password(field.data):
            raise ValidationError("Choose a password different from your current one.")


# Helpers
def next_page(user):
    """New accounts fill in the About you page before seeing the dashboard."""
    if user.profile is None:
        return redirect(url_for("auth.about_you"))
    return redirect(url_for("index"))


# Routes
@auth.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return next_page(current_user)
    form = SignupForm()
    if form.validate_on_submit():
        user = User(email=form.email.data.strip().lower())
        user.set_password(form.password.data)  # stored as a hash, never plain text
        db.session.add(user)
        db.session.commit()
        login_user(user)
        return next_page(user)
    return render_template("signup.html", form=form)


@auth.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return next_page(current_user)
    form = LoginForm()
    error = None
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.strip().lower()).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember_me.data)
            return next_page(user)
        error = "Incorrect email or password."
    return render_template("login.html", form=form, error=error)


@auth.route("/about-you", methods=["GET", "POST"])
@login_required
def about_you():
    if current_user.profile is not None:  # already filled in
        return redirect(url_for("index"))
    form = AboutYouForm()
    if form.validate_on_submit():
        profile = Profile(
            user_id=current_user.id,
            first_name=form.first_name.data.strip(),
            last_name=form.last_name.data.strip(),
            age=form.age.data,
            sex=form.sex.data or None,
            height_cm=form.height_cm.data,
            weight_kg=form.weight_kg.data,
            ethnicity=form.ethnicity.data or None,
            dietary_restrictions=",".join(form.dietary.data),
            diagnosed_conditions=",".join(form.diagnosed.data),
            concerned_conditions=",".join(form.concerned.data),
        )
        db.session.add(profile)
        db.session.commit()
        return redirect(url_for("index"))  # will go to the readings page once it exists
    return render_template("about_you.html", form=form)


@auth.route("/logout", methods=["POST"])
@login_required
def logout():
    session.clear()    # wipe everything stored in the browser session
    logout_user()      # sign out and clear the "keep me logged in" cookie
    response = redirect(url_for("auth.login"))
    response.delete_cookie("remember_token")  # make sure that cookie is gone
    return response