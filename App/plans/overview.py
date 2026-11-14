"""Overview (home) page: latest readings, today's plan from every page, consistency and what's next."""
import re
from datetime import date, timedelta

from flask import Blueprint, jsonify, redirect, render_template, url_for
from flask_login import current_user, login_required

from .. import db
from ..models import ChecklistCheck, Reading, SleepLog
from . import exercise as exercise_page
from . import routes as diet_page
from . import sleep as sleep_page
from .readings import MMOL_TO_MGDL, SUGAR_TIMINGS, ReadingError, make_reading, urgent_for
from .routes import body, error

bp = Blueprint("overview", __name__)

# Times for things the plans don't give a time for
MEAL_TIMES = {"Breakfast": "08:00", "Lunch": "12:30", "Snack": "15:30", "Dinner": "18:30"}
WORKOUT_TIME = "17:30"
SUGAR_CHECK_TIME = "07:30"
BP_CHECK_TIME = "08:30"

DIABETES = {"type1", "type2", "prediabetes"}


# ------------------------------------------------------------------ Helpers

def conditions(profile):
    return set((profile.diagnosed_conditions or "").split(",")) - {""}


def hhmm(minutes):
    minutes %= 24 * 60
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def from_clock(text):
    """ "9:15 pm" -> "21:15", or None."""
    match = re.fullmatch(r"(\d{1,2}):(\d{2})\s*(am|pm)", str(text or "").strip().lower())
    if not match:
        return None
    hour = int(match[1]) % 12 + (12 if match[3] == "pm" else 0)
    return f"{hour:02d}:{match[2]}"


def closeness(value, low, high, zero_low, zero_high):
    """100 inside [low, high], falling to 0 at zero_low / zero_high. Our own simple score."""
    if value < low:
        return max(0, round(100 * (1 - (low - value) / (low - zero_low))))
    if value > high:
        return max(0, round(100 * (1 - (value - high) / (zero_high - high))))
    return 100


# --------------------------------------------------------- Reading cards

def sugar_range(diabetic, timing):
    """Common guideline targets in mg/dL (ADA for diabetes)."""
    if timing == "fasting":
        return (80, 130) if diabetic else (70, 99)
    return (70, 180) if diabetic else (70, 140)


def sugar_card(reading, profile):
    if reading is None:
        return None
    value = reading.sugar_mgdl
    low, high = sugar_range(bool(conditions(profile) & DIABETES), reading.timing)
    if value < 54:
        status, tone = "Very low", "bad"
    elif value < low:
        status, tone = "Low", "bad"
    elif value <= high:
        status, tone = "In target range", "good"
    elif value <= high * 1.25:
        status, tone = "A bit high", "warn"
    else:
        status, tone = "High", "bad"
    shown = f"{value / MMOL_TO_MGDL:.1f}" if reading.unit == "mmol/L" else f"{value:g}"
    target = (f"{low / MMOL_TO_MGDL:.1f}–{high / MMOL_TO_MGDL:.1f}" if reading.unit == "mmol/L" else f"{low}–{high}")
    return {
        "value": shown, "unit": reading.unit, "status": status, "tone": tone,
        "score": closeness(value, low, high, 40, high * 2),
        "detail": f"{SUGAR_TIMINGS.get(reading.timing, '')} · target {target} {reading.unit}",
        "at": reading.created_at.isoformat() + "Z",  # stored in UTC; the browser shows local time
    }


def pressure_card(reading):
    if reading is None:
        return None
    sys, dia = reading.systolic, reading.diastolic
    if sys >= 180 or dia >= 120:
        status, tone = "Crisis range", "bad"
    elif sys >= 140 or dia >= 90:
        status, tone = "High (stage 2)", "bad"
    elif sys >= 130 or dia >= 80:
        status, tone = "High (stage 1)", "warn"
    elif sys >= 120:
        status, tone = "Elevated", "warn"
    elif sys < 90 or dia < 60:
        status, tone = "Low", "warn"
    else:
        status, tone = "Looking healthy", "good"
    score = min(closeness(sys, 90, 119, 60, 180), closeness(dia, 60, 79, 40, 120))
    return {"value": f"{sys}/{dia}", "unit": "mmHg", "status": status, "tone": tone, "score": score,
            "detail": "Normal is under 120/80", "at": reading.created_at.isoformat() + "Z"}


def sleep_card(user):
    log = SleepLog.query.filter_by(user_id=user.id).order_by(SleepLog.night.desc()).first()
    if log is None:
        return None
    goal = sleep_page.goal_dict(user)["hours"]
    stats = sleep_page.sleep_stats(sleep_page.recent_nights(user))
    diff_min = round((log.hours - stats["average"]) * 60) if stats["logged"] > 1 else None
    if diff_min is None or abs(diff_min) < 5:
        status = f"Goal is {goal:g} h"
    else:
        status = f"{abs(diff_min) // 60} h {abs(diff_min) % 60} m" if abs(diff_min) >= 60 else f"{abs(diff_min)} m"
        status += " above average" if diff_min > 0 else " below average"
    tone = "good" if log.hours >= goal - 0.25 else "warn" if log.hours >= goal - 1 else "bad"
    total = round(log.hours * 60)
    return {"value": f"{total // 60}h {total % 60:02d}m", "unit": "", "status": status, "tone": tone,
            "score": min(100, round(100 * log.hours / goal)),
            "detail": f"Night of {log.night.strftime('%a %b %d')} · goal {goal:g} h", "at": None}


def latest(user, kind):
    return (Reading.query.filter_by(user_id=user.id, kind=kind)
            .order_by(Reading.created_at.desc()).first())


def reading_cards(user):
    return {
        "sugar": sugar_card(latest(user, "blood_sugar"), user.profile),
        "pressure": pressure_card(latest(user, "blood_pressure")),
        "sleep": sleep_card(user),
    }


# ---------------------------------------------------------- Today's plan

def load_plans(user):
    return {
        "meal": diet_page.get_active_plan(user),
        "workout": exercise_page.get_active_plan(user),
        "sleep": sleep_page.get_active_plan(user),
        "sleep_goal": sleep_page.goal_dict(user),
        "conditions": conditions(user.profile),
        "joined": user.created_at.date(),
    }


def active_on(plan, day):
    """Only count a plan from the day it was made, so earlier days don't look like misses."""
    return plan is not None and plan.created_at.date() <= day


def plan_items(plans, day):
    """Everything planned for one day, in time order. `label` matches the checklist on each page."""
    items = []
    weekday = day.weekday()

    if plans["conditions"] & DIABETES and plans["joined"] <= day:
        items.append({"time": SUGAR_CHECK_TIME, "kind": "check", "title": "Check fasting blood sugar",
                      "detail": "Before breakfast", "label": "Check fasting blood sugar",
                      "action": "log-sugar", "actionLabel": "Log reading"})
    if "hypertension" in plans["conditions"] and plans["joined"] <= day:
        items.append({"time": BP_CHECK_TIME, "kind": "check", "title": "Check blood pressure",
                      "detail": "Sit quietly for 5 minutes first", "label": "Check blood pressure",
                      "action": "log-pressure", "actionLabel": "Log reading"})

    if active_on(plans["meal"], day):
        for meal in plans["meal"].data["days"][weekday]["meals"]:
            items.append({"time": MEAL_TIMES.get(meal["slot"], "12:00"), "kind": "meal", "title": meal["name"],
                          "detail": f"{meal['slot']} · {meal['calories']} kcal · {meal['protein_g']} g protein",
                          "label": f"{meal['slot']}: {meal['name']}",
                          "link": meal["recipe_url"], "linkLabel": "View recipe"})

    if active_on(plans["workout"], day):
        start = int(WORKOUT_TIME[:2]) * 60 + int(WORKOUT_TIME[3:])
        for session in plans["workout"].data["days"][weekday]["sessions"]:
            items.append({"time": hhmm(start), "kind": "rest" if session["category"] == "Rest" else "workout",
                          "title": session["name"],
                          "detail": f"{session['duration_min']} min · {session['intensity']} intensity",
                          "label": exercise_page.session_label(session),
                          "link": session["video_url"], "linkLabel": "How to"})
            start += session["duration_min"] + 15

    if active_on(plans["sleep"], day) and plans["sleep"].data["routine"]:
        first = plans["sleep"].data["routine"][0]
        items.append({"time": from_clock(first["time"]) or "21:30", "kind": "sleep", "title": "Wind down for sleep",
                      "detail": f"Starts with: {first['name']}", "label": sleep_page.routine_label(first),
                      "link": url_for("sleep.sleep_page"), "linkLabel": "See routine"})
    elif plans["sleep_goal"]["set"] and not plans["sleep"]:
        bed = sleep_page.to_minutes(plans["sleep_goal"]["bedtime"])
        items.append({"time": hhmm(bed - 30), "kind": "sleep", "title": "Wind down for sleep",
                      "detail": "Dim the lights and put screens away", "label": "Wind down for sleep",
                      "link": url_for("sleep.sleep_page"), "linkLabel": "See routine"})

    items.sort(key=lambda item: item["time"])
    return items


def ticked_by_day(user, first_day):
    ticked = {}
    for check in ChecklistCheck.query.filter(ChecklistCheck.user_id == user.id, ChecklistCheck.day >= first_day,
                                             ChecklistCheck.done.is_(True)):
        ticked.setdefault(check.day, set()).add(check.label)
    return ticked


def consistency(user, plans, weeks=4):
    """This week and the 3 before it, scored against the current plans (from the day each was made)."""
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    first_day = monday - timedelta(weeks=weeks - 1)
    ticked = ticked_by_day(user, first_day)
    result = []
    for w in range(weeks - 1, -1, -1):  # oldest first, this week last
        start = monday - timedelta(weeks=w)
        days, done_sum, total_sum = [], 0, 0
        for i in range(7):
            day = start + timedelta(days=i)
            if day > today:
                status, done, total = "future", 0, 0
            else:
                labels = {item["label"] for item in plan_items(plans, day)}
                total = len(labels)
                done = len(labels & ticked.get(day, set()))
                status = "none" if done == 0 else "all" if done == total else "some"
                done_sum, total_sum = done_sum + done, total_sum + total
            days.append({"date": day.isoformat(), "dow": day.strftime("%a").upper(), "num": day.day,
                         "done": done, "total": total, "status": status, "isToday": day == today})
        result.append({"label": f"{start.strftime('%b %d')} – {(start + timedelta(days=6)).strftime('%b %d')}",
                       "days": days, "done": done_sum, "total": total_sum})
    return result


# ------------------------------------------------------------- Care note

def care_note(cards, plans, today_items):
    """A short, rule-based note: the most important thing first."""
    bp, sugar, sleep = cards["pressure"], cards["sugar"], cards["sleep"]
    if bp and bp["status"] in ("Crisis range", "High (stage 2)"):
        return {"title": "Your last blood pressure was high",
                "text": "Recheck after resting for 5 minutes. If it stays at 180/120 or above, or you have chest pain, "
                        "shortness of breath or vision changes, call 911. Otherwise let your doctor know."}
    if sugar and sugar["status"] in ("Low", "Very low"):
        return {"title": "Your last blood sugar was low",
                "text": "Have 15 g of fast-acting carbs, like half a cup of juice, and recheck in 15 minutes."}
    if sugar and sugar["status"] == "High":
        return {"title": "Your last blood sugar was high",
                "text": "Drink water, recheck later and contact your doctor if it stays high."}
    if sleep and sleep["tone"] == "bad":
        return {"title": "You slept less than your goal",
                "text": "Try starting your wind-down routine 30 minutes earlier tonight."}
    if any(item["kind"] == "workout" for item in today_items):
        return {"title": "Remember to stay hydrated",
                "text": "Aim for 8 glasses of water today, especially before and after your workout."}
    tips = plans["sleep"].data.get("tips") if plans["sleep"] else None
    if tips:
        return {"title": "Tip for tonight", "text": tips[0]}
    return {"title": "Remember to stay hydrated", "text": "Aim for 8 glasses of water today."}


# -------------------------------------------------------------------- Page

def render_overview():
    """Called by the "/" route in App/__init__.py (kept there so url_for("index") keeps working)."""
    if current_user.profile is None:
        return redirect(url_for("auth.about_you"))

    plans = load_plans(current_user)
    items = plan_items(plans, date.today())
    ticked = ticked_by_day(current_user, date.today()).get(date.today(), set())
    for item in items:
        item["done"] = item["label"] in ticked
    cards = reading_cards(current_user)

    page_data = {
        "items": items,
        "cards": cards,
        "weeks": consistency(current_user, plans),
        "hasPlans": any(plans[k] for k in ("meal", "workout", "sleep")),
    }
    return render_template(
        "index.html",
        profile=current_user.profile,
        note=care_note(cards, plans, items),
        sugar_timings=SUGAR_TIMINGS,
        page_data=page_data,
    )


# --------------------------------------------------------------------- API

@bp.post("/api/readings")
@login_required
def log_reading():
    data = body()
    try:
        reading = make_reading(current_user.id, data.get("kind"), data.get("value"),
                               data.get("unit"), data.get("timing"))
    except ReadingError as e:
        return error(str(e))

    db.session.add(reading)
    db.session.commit()
    return jsonify(cards=reading_cards(current_user), urgent=urgent_for(reading))
