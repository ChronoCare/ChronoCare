"""Sleep page and its API. Works like the diet and exercise pages, plus sleep logging."""
import copy
import re
from datetime import date, timedelta

from flask import Blueprint, jsonify, redirect, render_template, url_for
from flask_login import current_user, login_required

from .. import ai_service, db
from ..models import ChecklistCheck, SleepGoal, SleepLog, SleepPlan
from .routes import body, error, profile_for_ai

bp = Blueprint("sleep", __name__)

DEFAULT_GOAL = {"hours": 8.0, "bedtime": "23:00", "note": "", "set": False}
HOUR_CHOICES = [6, 6.5, 7, 7.5, 8, 8.5, 9, 9.5, 10]
QUALITY = {1: "Very poor", 2: "Poor", 3: "Okay", 4: "Good", 5: "Great"}


# ------------------------------------------------------------------ Helpers

def to_minutes(text):
    """ "23:15" -> 1395 minutes after midnight, or None if it isn't a valid time."""
    match = re.fullmatch(r"(\d{1,2}):(\d{2})", str(text or "").strip())
    if not match or int(match[1]) > 23 or int(match[2]) > 59:
        return None
    return int(match[1]) * 60 + int(match[2])


def hours_slept(bedtime, wake_time):
    """Works across midnight: 23:00 -> 07:00 is 8 hours."""
    return round(((to_minutes(wake_time) - to_minutes(bedtime)) % (24 * 60)) / 60, 2)


def goal_dict(user):
    goal = SleepGoal.query.filter_by(user_id=user.id).order_by(SleepGoal.created_at.desc()).first()
    if goal is None:
        return dict(DEFAULT_GOAL)
    return {"hours": goal.target_hours, "bedtime": goal.bedtime, "note": goal.note or "", "set": True,
            "setOn": goal.created_at.strftime("%b %d, %Y")}


def recent_nights(user, days=7):
    """The last 7 nights, oldest first. Nights with no log have hours = None."""
    first = date.today() - timedelta(days=days)
    logs = {log.night: log for log in SleepLog.query.filter(SleepLog.user_id == user.id,
                                                            SleepLog.night >= first,
                                                            SleepLog.night < date.today())}
    nights = []
    for i in range(days):
        night = first + timedelta(days=i)
        log = logs.get(night)
        nights.append({
            "date": night.isoformat(),
            "label": night.strftime("%a"),
            "hours": log.hours if log else None,
            "bedtime": log.bedtime if log else None,
            "wake": log.wake_time if log else None,
            "quality": log.quality if log else None,
            "note": (log.note or "") if log else "",
        })
    return nights


def sleep_stats(nights):
    logged = [n for n in nights if n["hours"] is not None]
    if not logged:
        return {"logged": 0, "nights": len(nights)}
    # Average bedtime: count times after midnight as "late evening" (e.g. 00:30 -> 24:30)
    beds = [m + 24 * 60 if m < 12 * 60 else m for m in (to_minutes(n["bedtime"]) for n in logged)]
    qualities = [n["quality"] for n in logged if n["quality"]]
    best = max(logged, key=lambda n: n["hours"])
    return {
        "logged": len(logged),
        "nights": len(nights),
        "average": round(sum(n["hours"] for n in logged) / len(logged), 1),
        "best": best["hours"],
        "bestLabel": best["label"],
        "avgBedtime": ai_service.clock(round(sum(beds) / len(beds))),
        "avgQuality": round(sum(qualities) / len(qualities), 1) if qualities else None,
    }


def recent_text(stats):
    """One sentence about recent sleep, for the AI."""
    if not stats["logged"]:
        return "No sleep logged yet."
    text = (f"{stats['logged']} of the last {stats['nights']} nights logged. Average {stats['average']} hours, "
            f"typical bedtime {stats['avgBedtime']}.")
    if stats["avgQuality"]:
        text += f" Average sleep quality {stats['avgQuality']} out of 5."
    return text


def get_active_plan(user):
    return (SleepPlan.query.filter_by(user_id=user.id, is_active=True)
            .order_by(SleepPlan.created_at.desc()).first())


def routine_label(item):
    return f"{item['time']} · {item['name']}" if item["time"] else item["name"]


def build_routine(user, plan):
    """Tonight's routine with today's ticks filled in (uses the shared checklist table)."""
    if plan is None:
        return []
    ticked = {c.label for c in ChecklistCheck.query.filter_by(user_id=user.id, day=date.today(), done=True)}
    return [dict(item, label=routine_label(item), done=routine_label(item) in ticked)
            for item in plan.data["routine"]]


# -------------------------------------------------------------------- Page

@bp.route("/sleep")
@login_required
def sleep_page():
    if current_user.profile is None:  # plans need the About you answers
        return redirect(url_for("auth.about_you"))

    plan = get_active_plan(current_user)
    nights = recent_nights(current_user)
    goal = goal_dict(current_user)
    page_data = {
        "plan": plan.data if plan else None,
        "routine": build_routine(current_user, plan),
        "nights": nights,
        "stats": sleep_stats(nights),
        "goal": goal,
        "quality": QUALITY,
    }
    return render_template(
        "sleep.html",
        profile=current_user.profile,
        goal=goal,
        goal_bedtime=ai_service.clock(to_minutes(goal["bedtime"])),
        hour_choices=HOUR_CHOICES,
        quality=QUALITY,
        mock_mode=ai_service.is_mock(),
        today=date.today(),
        page_data=page_data,
    )


# --------------------------------------------------------------------- API
# Routine ticks use the shared /api/checklist endpoint in plans/routes.py.

@bp.post("/api/sleep/log")
@login_required
def log_sleep():
    data = body()
    try:
        night = date.fromisoformat(str(data.get("night")))
    except ValueError:
        return error("Pick which night this was.")
    if not date.today() - timedelta(days=30) <= night < date.today():
        return error("You can log any of the last 30 nights.")

    bedtime, wake = str(data.get("bedtime") or ""), str(data.get("wake") or "")
    if to_minutes(bedtime) is None or to_minutes(wake) is None:
        return error("Enter both the time you went to bed and the time you woke up.")
    hours = hours_slept(bedtime, wake)
    if not 0.5 <= hours <= 16:
        return error("That works out to under 30 minutes or over 16 hours. Check the times.")

    try:
        quality = int(data["quality"]) if data.get("quality") else None
    except (TypeError, ValueError):
        quality = None
    if quality not in QUALITY:
        quality = None

    log = SleepLog.query.filter_by(user_id=current_user.id, night=night).first()
    if log is None:  # logging the same night again updates it
        log = SleepLog(user_id=current_user.id, night=night)
        db.session.add(log)
    log.bedtime, log.wake_time, log.hours, log.quality = bedtime, wake, hours, quality
    log.note = str(data.get("note") or "").strip()[:300] or None
    db.session.commit()

    nights = recent_nights(current_user)
    return jsonify(nights=nights, stats=sleep_stats(nights))


@bp.post("/api/sleep/goal")
@login_required
def save_goal():
    data = body()
    try:
        hours = float(data.get("hours"))
    except (TypeError, ValueError):
        return error("Choose how many hours you want to sleep.")
    if not 4 <= hours <= 12:
        return error("Pick a goal between 4 and 12 hours.")
    bedtime = str(data.get("bedtime") or "")
    if to_minutes(bedtime) is None:
        return error("Choose a bedtime.")

    db.session.add(SleepGoal(user_id=current_user.id, target_hours=hours, bedtime=bedtime,
                             note=str(data.get("note") or "").strip()[:300] or None))
    db.session.commit()
    return jsonify(ok=True)


@bp.post("/api/sleep/generate")
@login_required
def generate_routine():
    if current_user.profile is None:
        return error("Fill in the About you page first.")

    note = str(body().get("note") or "").strip()[:300]
    stats = sleep_stats(recent_nights(current_user))
    try:
        plan_data = ai_service.generate_sleep_routine(profile_for_ai(current_user), goal_dict(current_user),
                                                      recent_text(stats), note)
    except ai_service.AIError as e:
        return error(str(e), 502)

    SleepPlan.query.filter_by(user_id=current_user.id, is_active=True).update({"is_active": False})
    db.session.add(SleepPlan(user_id=current_user.id, data=plan_data, note=note or None))
    db.session.commit()
    return jsonify(ok=True)


@bp.post("/api/sleep/swap")
@login_required
def swap_item():
    """Swap a routine step with an alternative. The new step keeps the old step's time."""
    plan = get_active_plan(current_user)
    if plan is None:
        return error("You don't have a bedtime routine yet.", 404)

    data = copy.deepcopy(plan.data)
    try:
        item_i, alt_i = (int(body()[k]) for k in ("item", "alt"))
        if min(item_i, alt_i) < 0:
            raise IndexError
        old, new = data["routine"][item_i], data["alternatives"][alt_i]
    except (KeyError, IndexError, TypeError, ValueError):
        return error("That step or alternative doesn't exist.")

    new["time"], old["time"] = old["time"], ""
    data["routine"][item_i], data["alternatives"][alt_i] = new, old
    plan.data = data  # assign a new object so SQLAlchemy notices the change
    db.session.commit()
    return jsonify(plan=data, routine=build_routine(current_user, plan))
