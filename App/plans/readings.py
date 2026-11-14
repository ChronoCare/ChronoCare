"""Turning typed blood pressure and blood sugar readings into Reading rows.

Shared by the overview's "Log health data" popup and the "Log symptom" popup
(diet and exercise pages), so both follow the same rules and the overview
always shows whichever reading is newest.
"""
import re

from .. import ai_service
from ..models import Reading

MMOL_TO_MGDL = 18
SUGAR_TIMINGS = {"fasting": "Before eating", "after_meal": "1 to 2 hours after eating", "random": "Other time"}


class ReadingError(ValueError):
    """The reading couldn't be understood. The message is shown to the user."""


def make_reading(user_id, kind, raw, unit=None, timing=None):
    """Build (but don't save) a Reading from what the user typed, or raise ReadingError.

    unit:   "mg/dL" or "mmol/L". If missing (the symptom popup has no unit box),
            it's taken from the text ("4.2 mmol/L") or guessed: up to 35 is mmol/L, above is mg/dL.
    timing: "fasting", "after_meal" or "random" (the default).
    """
    raw = str(raw or "").strip()

    if kind == "blood_pressure":
        match = re.search(r"(\d{2,3})\s*/\s*(\d{2,3})", raw)
        if not match:
            raise ReadingError("Enter both numbers, like 120/80.")
        sys, dia = int(match[1]), int(match[2])
        if not (60 <= sys <= 260 and 30 <= dia <= 160 and sys > dia):
            raise ReadingError("That doesn't look like a blood pressure reading. Check the numbers.")
        return Reading(user_id=user_id, kind=kind, systolic=sys, diastolic=dia, unit="mmHg")

    if kind == "blood_sugar":
        match = re.search(r"\d+(\.\d+)?", raw)
        if not match:
            raise ReadingError("Enter your blood sugar as a number, like 5.6 or 100.")
        value = float(match[0])
        if unit not in ("mg/dL", "mmol/L"):
            text = raw.lower()
            unit = "mmol/L" if "mmol" in text else "mg/dL" if "mg" in text else ("mmol/L" if value <= 35 else "mg/dL")
        mgdl = value * MMOL_TO_MGDL if unit == "mmol/L" else value
        if not 18 <= mgdl <= 630:
            raise ReadingError(f"That doesn't look like a blood sugar reading in {unit}. Check the number and unit.")
        timing = timing if timing in SUGAR_TIMINGS else "random"
        return Reading(user_id=user_id, kind=kind, sugar_mgdl=round(mgdl, 1), unit=unit, timing=timing)

    raise ReadingError("Choose blood sugar or blood pressure.")


def urgent_for(reading):
    """The fixed emergency advice for a dangerous reading, or None."""
    if reading.kind == "blood_pressure":
        return ai_service.urgent_check("Blood pressure", f"{reading.systolic}/{reading.diastolic}", "")
    # Always pass mmol/L: urgent_check guesses the unit, and a very low mg/dL number would look like mmol/L
    return ai_service.urgent_check("Blood sugar", f"{reading.sugar_mgdl / MMOL_TO_MGDL:.1f}", "")
