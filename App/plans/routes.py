import copy
from datetime import date

from flask import Blueprint, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from .. import ai_service, db
from ..auth import CONDITION_CHOICES, DIET_CHOICES, ETHNICITY_CHOICES, SEX_CHOICES
from .readings import ReadingError, make_reading
from ..models import ChecklistCheck, Goal, MealPlan, SymptomLog

bp = Blueprint("plans", __name__)

DEFAULT_HABITS = ["Drink 8 glasses of water", "Take a 15-minute walk"]
METRICS = ["Blood sugar", "Blood pressure", "Feeling weak", "Dizziness", "Headache", "Muscle or joint pain", "Other"]


# ------------------------------------------------------------------ Helpers

def labels(codes, choices):
    """Turn stored codes like "halal,nut_allergy" into "Halal, Nut allergy"."""
    lookup = dict(choices)
    return ", ".join(lookup.get(code, code) for code in (codes or "").split(",") if code)


def profile_for_ai(user):
    """The About you answers, written out in plain words for the AI."""
    p = user.profile
    conditions = labels(p.diagnosed_conditions, CONDITION_CHOICES)
    concerned = labels(p.concerned_conditions, CONDITION_CHOICES)
    if concerned:
        conditions = f"{conditions}; " if conditions else ""
        conditions += f"concerned about developing: {concerned}"
    return {
        "age": p.age,
        "sex": labels(p.sex, SEX_CHOICES) or "not given",
        "height_cm": p.height_cm,
        "weight_kg": p.weight_kg,
        "ethnicity": labels(p.ethnicity, ETHNICITY_CHOICES),
        "dietary_restrictions": labels(p.dietary_restrictions, DIET_CHOICES),
        "health_conditions": conditions,
    }


def get_active_plan(user):
    return (MealPlan.query.filter_by(user_id=user.id, is_active=True)
            .order_by(MealPlan.created_at.desc()).first())


def build_checklist(user, plan):
    """Today's meals plus a few habits, with today's ticks filled in."""
    items = list(DEFAULT_HABITS)
    if plan:
        today = plan.data["days"][date.today().weekday()]
        items = [f"{m['slot']}: {m['name']}" for m in today["meals"]]
        items += plan.data.get("checklist") or DEFAULT_HABITS

    ticked = {c.label for c in ChecklistCheck.query.filter_by(user_id=user.id, day=date.today(), done=True)}
    items = list(dict.fromkeys(items))  # drop duplicates, keep order
    return [{"label": item, "done": item in ticked} for item in items]


def body():
    return request.get_json(silent=True) or {}


def error(message, status=400):
    return jsonify({"error": message}), status


# -------------------------------------------------------------------- Page

@bp.route("/diet_plan")
@login_required
def diet_plan():
    if current_user.profile is None:  # plans need the About you answers
        return redirect(url_for("auth.about_you"))

    plan = get_active_plan(current_user)
    page_data = {
        "plan": plan.data if plan else None,
        "checklist": build_checklist(current_user, plan),
        "todayIndex": date.today().weekday(),
    }
    return render_template(
        "diet_plan.html",
        profile=current_user.profile,
        details=profile_for_ai(current_user),
        goal=current_user.current_goal,
        metrics=METRICS,
        mock_mode=ai_service.is_mock(),
        today=date.today(),
        page_data=page_data,
    )


# --------------------------------------------------------------------- API

@bp.post("/api/goal")
@login_required
def save_goal():
    text = str(body().get("text") or "").strip()
    if not text:
        return error("Write your goal first.")
    if len(text) > 500:
        return error("Keep your goal under 500 characters.")

    db.session.add(Goal(user_id=current_user.id, text=text))
    db.session.commit()
    return jsonify(ok=True)


@bp.post("/api/diet/generate")
@login_required
def generate_plan():
    if current_user.profile is None:
        return error("Fill in the About you page first.")

    note = str(body().get("note") or "").strip()[:300]
    goal = current_user.current_goal
    try:
        data = ai_service.generate_meal_plan(profile_for_ai(current_user), goal.text if goal else None, note)
    except ai_service.AIError as e:
        return error(str(e), 502)

    MealPlan.query.filter_by(user_id=current_user.id, is_active=True).update({"is_active": False})
    db.session.add(MealPlan(user_id=current_user.id, data=data, note=note or None))
    db.session.commit()
    return jsonify(ok=True)


@bp.post("/api/diet/swap")
@login_required
def swap_meal():
    """Swap a meal in the schedule with one of the alternatives."""
    plan = get_active_plan(current_user)
    if plan is None:
        return error("You don't have a meal plan yet.", 404)

    data = copy.deepcopy(plan.data)
    try:
        day_i, meal_i, alt_i = (int(body()[k]) for k in ("day", "meal", "alt"))
        if min(day_i, meal_i, alt_i) < 0:
            raise IndexError
        meals = data["days"][day_i]["meals"]
        old_meal, new_meal = meals[meal_i], data["alternatives"][alt_i]
    except (KeyError, IndexError, TypeError, ValueError):
        return error("That meal or alternative doesn't exist.")

    if old_meal["slot"] != new_meal["slot"]:
        return error(f"Pick a {old_meal['slot'].lower()} alternative.")

    # The old meal goes into the alternatives, so the swap can be undone
    meals[meal_i], data["alternatives"][alt_i] = new_meal, old_meal
    plan.data = data  # assign a new object so SQLAlchemy notices the change
    db.session.commit()
    return jsonify(plan=data, checklist=build_checklist(current_user, plan))


@bp.post("/api/checklist")
@login_required
def toggle_checklist():
    item = str(body().get("label") or "").strip()[:255]
    if not item:
        return error("Missing checklist item.")

    check = ChecklistCheck.query.filter_by(user_id=current_user.id, day=date.today(), label=item).first()
    if check is None:
        check = ChecklistCheck(user_id=current_user.id, day=date.today(), label=item)
        db.session.add(check)
    check.done = bool(body().get("done"))
    db.session.commit()
    return jsonify(ok=True)


@bp.post("/api/symptom")
@login_required
def log_symptom():
    data = body()
    metric = data.get("metric") if data.get("metric") in METRICS else "Other"
    reading = str(data.get("reading") or "").strip()[:50]
    description = str(data.get("description") or "").strip()[:500]
    context = "exercise" if data.get("context") == "exercise" else ""  # which page it came from

    if not reading and not description:
        return error("Enter a reading or describe how you feel.")

    profile = profile_for_ai(current_user) if current_user.profile else {}
    try:
        advice = ai_service.symptom_advice(metric, reading, description, profile, context)
    except ai_service.AIError as e:
        return error(str(e), 502)

    db.session.add(SymptomLog(user_id=current_user.id, metric=metric, reading=reading or None,
                              description=description or None, advice=advice))
    # A blood pressure or blood sugar number also counts as a reading, so the overview shows it
    saved_reading = False
    kind = {"Blood pressure": "blood_pressure", "Blood sugar": "blood_sugar"}.get(metric)
    if kind and reading:
        try:
            db.session.add(make_reading(current_user.id, kind, reading))
            saved_reading = True
        except ReadingError:
            pass  # e.g. "120" for blood pressure: still saved as a symptom, just not as a reading

    db.session.commit()
    return jsonify(advice=advice, savedReading=saved_reading)
