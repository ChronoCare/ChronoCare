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

    goals = db.relationship("Goal", backref="user", lazy=True, order_by="Goal.created_at.desc()", cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def current_goal(self):
        return self.goals[0] if self.goals else None
    

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

# ---------- Diet plan page ----------

class Goal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class MealPlan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    data = db.Column(db.JSON, nullable=False)   # days, meals, alternatives, checklist
    note = db.Column(db.String(300))            # what the user asked for when generating
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ChecklistCheck(db.Model):
    """One ticked (or unticked) checklist item for one day."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    day = db.Column(db.Date, nullable=False)
    label = db.Column(db.String(255), nullable=False)
    done = db.Column(db.Boolean, default=False)

    __table_args__ = (db.UniqueConstraint("user_id", "day", "label"),)


class SymptomLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    metric = db.Column(db.String(50), nullable=False)
    reading = db.Column(db.String(50))
    description = db.Column(db.Text)
    advice = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))