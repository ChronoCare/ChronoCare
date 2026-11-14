"""Exercise page and its API. Works like the diet plan page (plans/routes.py)."""
import copy
from datetime import date

from flask import Blueprint, jsonify, redirect, render_template, url_for
from flask_login import current_user, login_required

from .. import ai_service, db
from ..models import ChecklistCheck, WorkoutPlan
from .routes import METRICS, body, error, profile_for_ai

bp = Blueprint("exercise", __name__)

DEFAULT_HABITS = ["Stretch for 5 minutes", "Stand up and move every hour"]
LEVELS = ["Beginner", "Intermediate", "Advanced"]
EQUIPMENT = ["No equipment", "Home: dumbbells or bands", "Full gym"]
MINUTES = [15, 20, 30, 45, 60]
DEFAULT_PREFS = {"level": "Beginner", "equipment": "No equipment", "minutes": 30}


# ------------------------------------------------------------------ Helpers

def get_active_plan(user):
    return (WorkoutPlan.query.filter_by(user_id=user.id, is_active=True)
            .order_by(WorkoutPlan.created_at.desc()).first())


def session_label(session):
    prefix = "Rest" if session["category"] == "Rest" else "Workout"
    return f"{prefix}: {session['name']} ({session['duration_min']} min)"


def build_checklist(user, plan):
    """Today's sessions plus a few habits, with today's ticks filled in."""
    items = list(DEFAULT_HABITS)
    if plan:
        today = plan.data["days"][date.today().weekday()]
        items = [session_label(s) for s in today["sessions"]]
        items += plan.data.get("checklist") or DEFAULT_HABITS

    ticked = {c.label for c in ChecklistCheck.query.filter_by(user_id=user.id, day=date.today(), done=True)}
    items = list(dict.fromkeys(items))  # drop duplicates, keep order
    return [{"label": item, "done": item in ticked} for item in items]


def read_prefs(data):
    """Fitness level, equipment and session length from the New plan form."""
    try:
        minutes = int(data.get("minutes"))
    except (TypeError, ValueError):
        minutes = DEFAULT_PREFS["minutes"]
    return {
        "level": data.get("level") if data.get("level") in LEVELS else DEFAULT_PREFS["level"],
        "equipment": data.get("equipment") if data.get("equipment") in EQUIPMENT else DEFAULT_PREFS["equipment"],
        "minutes": minutes if minutes in MINUTES else DEFAULT_PREFS["minutes"],
    }


# -------------------------------------------------------------------- Page

@bp.route("/exercise")
@login_required
def exercise_plan():
    if current_user.profile is None:  # plans need the About you answers
        return redirect(url_for("auth.about_you"))

    plan = get_active_plan(current_user)
    page_data = {
        "plan": plan.data if plan else None,
        "checklist": build_checklist(current_user, plan),
        "todayIndex": date.today().weekday(),
    }
    return render_template(
        "exercise.html",
        profile=current_user.profile,
        details=profile_for_ai(current_user),
        goal=current_user.current_goal,
        prefs=(plan.data.get("prefs") if plan else None) or DEFAULT_PREFS,
        levels=LEVELS,
        equipment=EQUIPMENT,
        minutes=MINUTES,
        mock_mode=ai_service.is_mock(),
        metrics=METRICS,             # for the Log symptom popup
        symptom_context="exercise",  # tells the AI it may be workout-related
        today=date.today(),
        page_data=page_data,
    )


# --------------------------------------------------------------------- API
# Goals and checklist ticks use the same endpoints as the diet page:
# /api/goal and /api/checklist in plans/routes.py.

@bp.post("/api/exercise/generate")
@login_required
def generate_plan():
    if current_user.profile is None:
        return error("Fill in the About you page first.")

    data = body()
    prefs = read_prefs(data)
    note = str(data.get("note") or "").strip()[:300]
    goal = current_user.current_goal
    try:
        plan_data = ai_service.generate_workout_plan(profile_for_ai(current_user),
                                                     goal.text if goal else None, prefs, note)
    except ai_service.AIError as e:
        return error(str(e), 502)

    WorkoutPlan.query.filter_by(user_id=current_user.id, is_active=True).update({"is_active": False})
    db.session.add(WorkoutPlan(user_id=current_user.id, data=plan_data, note=note or None))
    db.session.commit()
    return jsonify(ok=True)


@bp.post("/api/exercise/swap")
@login_required
def swap_session():
    """Swap a session in the schedule with any of the alternatives."""
    plan = get_active_plan(current_user)
    if plan is None:
        return error("You don't have a workout plan yet.", 404)

    data = copy.deepcopy(plan.data)
    try:
        day_i, session_i, alt_i = (int(body()[k]) for k in ("day", "session", "alt"))
        if min(day_i, session_i, alt_i) < 0:
            raise IndexError
        sessions = data["days"][day_i]["sessions"]
        old, new = sessions[session_i], data["alternatives"][alt_i]
    except (KeyError, IndexError, TypeError, ValueError):
        return error("That session or alternative doesn't exist.")

    # The old session goes into the alternatives, so the swap can be undone
    sessions[session_i], data["alternatives"][alt_i] = new, old
    plan.data = data  # assign a new object so SQLAlchemy notices the change
    db.session.commit()
    return jsonify(plan=data, checklist=build_checklist(current_user, plan))
