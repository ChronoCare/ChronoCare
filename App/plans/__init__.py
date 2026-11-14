"""Insights page and its API. Reads what the other pages already save."""
from datetime import date, datetime, time

from flask import Blueprint, jsonify, redirect, render_template, url_for
from flask_login import current_user, login_required

from .. import ai_service
from ..models import (ChecklistCheck, Goal, MealPlan, SleepGoal, SleepLog,
                      SleepPlan, SymptomLog, WorkoutPlan)
from . import exercise, sleep
from .routes import METRICS
from .routes import build_checklist as diet_checklist
from .routes import get_active_plan as diet_active_plan

bp = Blueprint("insights", __name__)


# ------------------------------------------------------------------ Helpers

def stamp(moment):
    """Times are stored in UTC. The browser shows them in the person's own time zone."""
    return moment.isoformat() + "Z"


def latest_reading(user, metric):
    log = (SymptomLog.query.filter_by(user_id=user.id, metric=metric)
           .filter(SymptomLog.reading.isnot(None))
           .order_by(SymptomLog.created_at.desc()).first())
    if log is None:
        return None
    return {"reading": log.reading, "when": stamp(log.created_at)}


def diet_stats(user):
    plan = diet_active_plan(user)
    goal = user.current_goal  # one goal, shared by the diet and exercise pages
    stats = {"hasPlan": plan is not None, "goal": goal.text if goal else None,
             "meals": 0, "calories": 0, "done": 0, "total": 0}
    if plan:
        today = plan.data["days"][date.today().weekday()]
        stats["meals"] = len(today["meals"])
        stats["calories"] = sum(m["calories"] for m in today["meals"]
                                if isinstance(m.get("calories"), (int, float)))
        checklist = diet_checklist(user, plan)
        stats["total"] = len(checklist)
        stats["done"] = sum(1 for item in checklist if item["done"])
    return stats


def exercise_stats(user):
    plan = exercise.get_active_plan(user)
    stats = {"hasPlan": plan is not None, "sessions": 0, "minutes": 0,
             "level": None, "done": 0, "total": 0}
    if plan:
        today = plan.data["days"][date.today().weekday()]
        workouts = [s for s in today["sessions"] if s["category"] != "Rest"]
        stats["sessions"] = len(workouts)
        stats["minutes"] = sum(s["duration_min"] for s in workouts)
        stats["level"] = (plan.data.get("prefs") or {}).get("level")
        checklist = exercise.build_checklist(user, plan)
        stats["total"] = len(checklist)
        stats["done"] = sum(1 for item in checklist if item["done"])
    return stats


def sleep_summary(user):
    nights = sleep.recent_nights(user)
    goal = sleep.goal_dict(user)
    routine = sleep.build_routine(user, sleep.get_active_plan(user))
    return {
        "stats": sleep.sleep_stats(nights),
        "goal": ({"hours": goal["hours"],
                  "bedtime": ai_service.clock(sleep.to_minutes(goal["bedtime"]))}
                 if goal["set"] else None),
        "routineDone": sum(1 for item in routine if item["done"]),
        "routineTotal": len(routine),
    }


def history(user):
    """Everything the person has recorded, newest first."""
    events = []

    def add(kind, title, when, sort, value="", detail="", all_day=False):
        events.append({"kind": kind, "title": title, "value": value, "detail": detail,
                       "when": when, "allDay": all_day, "_sort": sort})

    add("goal", "Joined ChronoCare", stamp(user.created_at), user.created_at)

    # Blood pressure, blood sugar and other symptoms from the Log symptom popup
    kinds = {"Blood pressure": "bp", "Blood sugar": "sugar"}
    for log in SymptomLog.query.filter_by(user_id=user.id):
        add(kinds.get(log.metric, "symptom"), log.metric, stamp(log.created_at), log.created_at,
            value=log.reading or "", detail=log.description or "")

    for log in SleepLog.query.filter_by(user_id=user.id):
        bits = [f"{log.bedtime} to {log.wake_time}"]
        if log.quality in sleep.QUALITY:
            bits.append(f"{sleep.QUALITY[log.quality]} quality")
        if log.note:
            bits.append(log.note)
        add("sleep", "Sleep", log.night.isoformat(), datetime.combine(log.night, time(12)),
            value=f"{log.hours:g} h", detail=" · ".join(bits), all_day=True)

    # Ticked checklist items, one entry per day
    days = {}
    for check in ChecklistCheck.query.filter_by(user_id=user.id, done=True):
        days.setdefault(check.day, []).append(check.label)
    for day, items in days.items():
        shown = ", ".join(items[:3]) + (f" and {len(items) - 3} more" if len(items) > 3 else "")
        add("checklist", "Checklist", day.isoformat(), datetime.combine(day, time(12)),
            value=f"{len(items)} done", detail=shown, all_day=True)

    for goal in Goal.query.filter_by(user_id=user.id):
        add("goal", "Goal set", stamp(goal.created_at), goal.created_at, detail=goal.text)
    for goal in SleepGoal.query.filter_by(user_id=user.id):
        detail = f"Bedtime {goal.bedtime}" + (f" · {goal.note}" if goal.note else "")
        add("goal", "Sleep goal set", stamp(goal.created_at), goal.created_at,
            value=f"{goal.target_hours:g} h", detail=detail)
    for model, title in ((MealPlan, "Meal plan created"), (WorkoutPlan, "Workout plan created"),
                         (SleepPlan, "Bedtime routine created")):
        for plan in model.query.filter_by(user_id=user.id):
            add("goal", title, stamp(plan.created_at), plan.created_at, detail=plan.note or "")

    events.sort(key=lambda e: e["_sort"], reverse=True)
    for event in events:
        del event["_sort"]
    return events


def insights_data(user):
    return {
        "bp": latest_reading(user, "Blood pressure"),
        "sugar": latest_reading(user, "Blood sugar"),
        "diet": diet_stats(user),
        "exercise": exercise_stats(user),
        "sleep": sleep_summary(user),
        "history": history(user),
    }


# -------------------------------------------------------------------- Page

@bp.route("/insights")
@login_required
def insights_page():
    if current_user.profile is None:  # the About you answers come first
        return redirect(url_for("auth.about_you"))
    return render_template(
        "insights.html",
        profile=current_user.profile,
        data=insights_data(current_user),
        metrics=METRICS,        # for the Log symptom popup
        symptom_context="",
    )


# --------------------------------------------------------------------- API

@bp.get("/api/insights")
@login_required
def insights_api():
    """The page asks for this again after something new is logged."""
    return jsonify(insights_data(current_user))