from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from . import db, login_manager


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    profile = db.relationship("Profile", uselist=False, back_populates="user",
                              cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Profile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), unique=True, nullable=False)

    first_name = db.Column(db.String(80), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    sex = db.Column(db.String(20))                           # optional
    height_cm = db.Column(db.Float, nullable=False)
    weight_kg = db.Column(db.Float, nullable=False)
    ethnicity = db.Column(db.String(40))                     # optional
    dietary_restrictions = db.Column(db.String(300), default="")   # comma-separated
    diagnosed_conditions = db.Column(db.String(300), default="")   # comma-separated
    concerned_conditions = db.Column(db.String(300), default="")   # comma-separated

    user = db.relationship("User", back_populates="profile")


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))