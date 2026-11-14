"""Every AI call in ChronoCare goes through this file.

The rest of the app only calls generate_meal_plan() and symptom_advice(),
so switching AI provider later means changing this file only.
With no GROQ_API_KEY set, it runs in demo mode and returns sample data.
"""
import json
import os
import re
from urllib.parse import quote_plus

DEFAULT_MODEL = "llama-3.3-70b-versatile"
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
SLOTS = ["Breakfast", "Lunch", "Dinner", "Snack"]


class AIError(Exception):
    """The AI call failed or returned something unusable."""


def is_mock():
    return not os.getenv("GROQ_API_KEY")


def recipe_link(name):
    # AI models often invent recipe URLs that don't exist, so link to a search instead.
    return "https://www.google.com/search?q=" + quote_plus(f"{name} recipe")


def _ask_json(system, prompt, max_tokens):
    from groq import Groq, GroqError  # imported here so demo mode works without the package

    try:
        client = Groq()  # reads GROQ_API_KEY from the environment
        response = client.chat.completions.create(
            model=os.getenv("GROQ_MODEL", DEFAULT_MODEL),
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.6,
            max_tokens=max_tokens,
        )
    except GroqError as e:
        raise AIError(f"The AI service failed: {e}") from e

    text = response.choices[0].message.content or ""
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise AIError("The AI sent back an unreadable answer. Please try again.") from e


def _profile_text(profile, goal=None):
    lines = [
        f"Age: {profile.get('age')}",
        f"Sex: {profile.get('sex')}",
        f"Height: {profile.get('height_cm')} cm",
        f"Weight: {profile.get('weight_kg')} kg",
        f"Cultural background / favourite cuisine: {profile.get('ethnicity') or 'not given'}",
        f"Dietary restrictions / allergies: {profile.get('dietary_restrictions') or 'none given'}",
        f"Health conditions: {profile.get('health_conditions') or 'none given'}",
    ]
    if goal is not None:
        lines.append(f"Goal: {goal or 'no goal set, aim for balanced healthy eating'}")
    return "\n".join(lines)


def _num(value):
    """Turn 450, "450" or "450 kcal" into 450. Anything else becomes 0."""
    match = re.search(r"\d+(\.\d+)?", str(value))
    return round(float(match[0])) if match else 0


def _text_list(items, limit):
    if not isinstance(items, list):
        return []
    return [str(i).strip()[:200] for i in items if str(i).strip()][:limit]


# ---------------------------------------------------------------- Meal plans

PLAN_SYSTEM = """You are the meal planner inside ChronoCare, a wellness app. You create practical, healthy 7-day meal plans.

Rules:
- Base portions and calories on the person's age, sex, height, weight and goal. Never go below 1,200 kcal a day for women or 1,500 kcal a day for men, and avoid extreme or fad diets.
- Include dishes from the person's cultural background or favourite cuisine, mixed with other simple, healthy meals. Use real, well-known dish names that are easy to find recipes for.
- Strictly respect dietary restrictions and allergies.
- Adjust for health conditions, e.g. lower sodium for high blood pressure, steady low-GI carbohydrates for diabetes.
- Vary the meals across the week. Repeating a meal up to twice is fine.

Respond with JSON only, in exactly this shape:
{
  "summary": "one or two sentences on how the plan supports the goal",
  "daily_calories": 2000,
  "days": [
    {"day": "Monday", "meals": [
      {"slot": "Breakfast", "name": "Dish name", "description": "under 15 words", "calories": 450, "protein_g": 25, "carbs_g": 50, "fat_g": 15}
    ]}
  ],
  "alternatives": [],
  "checklist": []
}
"days" must have all 7 days, Monday to Sunday, each with exactly one Breakfast, Lunch, Dinner and Snack.
"alternatives" must have 8 meals in the same format as the day meals: 2 each for Breakfast, Lunch, Dinner and Snack, all different from the plan's meals.
"checklist" must have 3 short daily habits that support the goal, e.g. "Drink 8 glasses of water"."""


def _clean_meal(meal, fallback_slot):
    if not isinstance(meal, dict) or not str(meal.get("name", "")).strip():
        return None
    slot = str(meal.get("slot", "")).strip().title()
    name = str(meal["name"]).strip()[:120]
    return {
        "slot": slot if slot in SLOTS else fallback_slot,
        "name": name,
        "description": str(meal.get("description", "")).strip()[:200],
        "calories": _num(meal.get("calories")),
        "protein_g": _num(meal.get("protein_g")),
        "carbs_g": _num(meal.get("carbs_g")),
        "fat_g": _num(meal.get("fat_g")),
        "recipe_url": recipe_link(name),
    }


def _clean_plan(raw):
    """Check the AI's answer and fill in anything missing, so the page never breaks."""
    days_in = [d for d in (raw.get("days") or []) if isinstance(d, dict)] if isinstance(raw, dict) else []
    if not days_in:
        raise AIError("The AI didn't return a meal plan. Please try again.")

    days = []
    for i, day_name in enumerate(DAYS):
        source = days_in[i % len(days_in)]
        meals = [_clean_meal(m, SLOTS[j % len(SLOTS)]) for j, m in enumerate(source.get("meals") or [])]
        meals = [m for m in meals if m]
        if not meals:
            raise AIError(f"The AI left {day_name} empty. Please try again.")
        days.append({"day": day_name, "meals": meals})

    alternatives = [_clean_meal(m, "Snack") for m in (raw.get("alternatives") or [])]
    return {
        "summary": str(raw.get("summary", "")).strip()[:400],
        "daily_calories": _num(raw.get("daily_calories")),
        "days": days,
        "alternatives": [m for m in alternatives if m],
        "checklist": _text_list(raw.get("checklist"), 4),
    }


def generate_meal_plan(profile, goal, note=""):
    if is_mock():
        return _clean_plan(_mock_plan())

    prompt = "Create a 7-day meal plan for this person.\n\n" + _profile_text(profile, goal or "")
    if note:
        prompt += f"\n\nExtra request from the user: {note}"
    return _clean_plan(_ask_json(PLAN_SYSTEM, prompt, max_tokens=6000))


# ------------------------------------------------------------- Symptom advice

SYMPTOM_SYSTEM = """You are a careful health assistant inside ChronoCare, a wellness app. A user has logged a symptom or a reading and wants practical, general self-care guidance.

Rules:
- You are not a doctor. Do not diagnose, and never tell the user to start, stop or change a medication or dose.
- Give simple, specific actions. For example, for low blood sugar: "Have 15 g of fast-acting carbs, like half a cup of juice, then recheck in 15 minutes."
- Or you can give instructions such as "Eat an apple, or chew on some gum, etc.
- Where food helps, suggest foods or drinks that fit their cultural background and dietary restrictions.
- Never forget about dietary restrictions, and verify with reliable sources. We want to take people dietary restrictions very seriously!
- Always say clearly when to contact a doctor and when to call emergency services (911).
- Keep every item under 20 words.

Respond with JSON only, in exactly this shape:
{
  "summary": "one sentence on what this reading or symptom may mean",
  "do_now": ["2 to 4 immediate steps"],
  "eat": ["0 to 3 foods or drinks that may help"],
  "avoid": ["0 to 3 things to avoid"],
  "seek_help_if": ["2 or 3 warning signs that mean they should get medical help"]
}"""

EMERGENCY_WORDS = (
    "chest pain", "can't breathe", "cannot breathe", "cant breathe", "short of breath",
    "shortness of breath", "fainted", "passed out", "unconscious", "slurred", "numb",
    "face drooping", "seizure", "confused", "confusion",
)
CALL_911 = "If you have chest pain, trouble breathing, confusion, numbness or trouble speaking, call 911 now."


def _urgent(summary, first_step):
    return {
        "urgent": True,
        "summary": summary,
        "do_now": [first_step, CALL_911, "Otherwise, contact your doctor or a nurse advice line right away."],
        "eat": [],
        "avoid": [],
        "seek_help_if": [],
    }


def urgent_check(metric, reading, description):
    """Fixed safety rules that run before (and instead of) the AI for dangerous readings."""
    text = f"{reading} {description}".lower()
    if any(word in text for word in EMERGENCY_WORDS):
        return _urgent("These symptoms can be a sign of an emergency.",
                       "Stop what you're doing and sit or lie down somewhere safe.")

    if metric == "Blood pressure":
        match = re.search(r"(\d{2,3})\s*/\s*(\d{2,3})", reading or "")
        if match and (int(match[1]) >= 180 or int(match[2]) >= 120):
            return _urgent("A reading of 180/120 or higher is at the level of a hypertensive crisis.",
                           "Sit quietly for 5 minutes, then measure again.")

    if metric == "Blood sugar":
        match = re.search(r"\d+(\.\d+)?", reading or "")
        if match:
            value = float(match[0])
            mmol = value / 18 if value > 35 else value  # big numbers are probably mg/dL
            if mmol < 3.0:
                return _urgent("This is a severely low blood sugar level.",
                               "If you can swallow safely, have 15-20 g of fast sugar now: juice, regular pop or glucose tablets.")
            if mmol >= 16.7:
                return _urgent("This is a very high blood sugar level.",
                               "Drink water and recheck soon. Contact your doctor today, sooner if you feel unwell.")
    return None


def _clean_advice(raw):
    raw = raw if isinstance(raw, dict) else {}
    summary = str(raw.get("summary", "")).strip()[:300]
    if not summary:
        raise AIError("The AI didn't return any advice. Please try again.")
    return {
        "urgent": False,
        "summary": summary,
        "do_now": _text_list(raw.get("do_now"), 4),
        "eat": _text_list(raw.get("eat"), 3),
        "avoid": _text_list(raw.get("avoid"), 3),
        "seek_help_if": _text_list(raw.get("seek_help_if"), 3),
    }


def symptom_advice(metric, reading, description, profile):
    urgent = urgent_check(metric, reading, description)
    if urgent:
        return urgent
    if is_mock():
        return _mock_advice(metric)

    prompt = (
        f"Logged: {metric}\n"
        f"Reading: {reading or 'not given'}\n"
        f"How they feel: {description or 'not given'}\n\n"
        f"About the user:\n{_profile_text(profile)}"
    )
    return _clean_advice(_ask_json(SYMPTOM_SYSTEM, prompt, max_tokens=1200))


# ---------------------------------------------------- Demo data (no API key)

_MOCK_MEALS = {
    "Breakfast": [
        ("Overnight oats with berries", "Oats, Greek yogurt, chia and mixed berries", 380, 18, 55, 10),
        ("Masala omelette with whole-wheat toast", "Eggs, onion, tomato and spices on toast", 420, 26, 30, 20),
        ("Greek yogurt parfait", "Yogurt layered with granola and fruit", 330, 20, 42, 8),
        ("Avocado toast with egg", "Sourdough, smashed avocado and a poached egg", 400, 16, 35, 22),
        ("Banana peanut butter smoothie", "Banana, milk, oats and peanut butter", 390, 17, 52, 13),
    ],
    "Lunch": [
        ("Chicken shawarma bowl", "Spiced chicken, rice, salad and garlic sauce", 560, 40, 55, 18),
        ("Lentil dal with brown rice", "Red lentils, tomato and spices with rice", 520, 22, 85, 9),
        ("Quinoa chickpea salad", "Quinoa, chickpeas, cucumber and lemon dressing", 480, 19, 62, 16),
        ("Turkey and hummus wrap", "Whole-wheat wrap with turkey, hummus and greens", 470, 32, 45, 16),
        ("Vegetable stir-fry with tofu", "Tofu, mixed vegetables and soy-ginger sauce", 450, 24, 48, 17),
    ],
    "Dinner": [
        ("Baked salmon with roasted vegetables", "Salmon fillet, sweet potato and broccoli", 610, 42, 45, 26),
        ("Chicken tikka with cauliflower rice", "Yogurt-marinated chicken with spiced cauliflower", 540, 45, 22, 28),
        ("Turkey chili", "Lean turkey, beans and tomatoes", 560, 44, 50, 16),
        ("Beef and broccoli with brown rice", "Lean beef, broccoli and a light soy sauce", 620, 40, 60, 20),
        ("Shrimp tacos with slaw", "Corn tortillas, grilled shrimp and crunchy slaw", 530, 34, 55, 18),
    ],
    "Snack": [
        ("Apple with peanut butter", "One apple and a tablespoon of peanut butter", 200, 5, 25, 9),
        ("Hummus with carrot sticks", "A quarter cup of hummus with carrots", 180, 6, 20, 8),
        ("Roasted chickpeas", "Crunchy oven-roasted chickpeas", 170, 8, 24, 5),
        ("Trail mix", "Nuts, seeds and a few raisins", 210, 6, 16, 14),
        ("Cottage cheese with pineapple", "Half a cup of cottage cheese and fruit", 160, 14, 16, 4),
    ],
}


def _mock_meal(slot, item):
    name, description, calories, protein, carbs, fat = item
    return {"slot": slot, "name": name, "description": description, "calories": calories,
            "protein_g": protein, "carbs_g": carbs, "fat_g": fat}


def _mock_plan():
    days = [
        {"day": day, "meals": [_mock_meal(slot, _MOCK_MEALS[slot][i % 3]) for slot in SLOTS]}
        for i, day in enumerate(DAYS)
    ]
    alternatives = [_mock_meal(slot, item) for slot in SLOTS for item in _MOCK_MEALS[slot][3:]]
    return {
        "summary": "Demo plan: balanced meals around 1,700 kcal a day. Add a Groq API key for a plan built around you.",
        "daily_calories": 1700,
        "days": days,
        "alternatives": alternatives,
        "checklist": ["Drink 8 glasses of water", "Take a 20-minute walk", "Eat a vegetable with every meal"],
    }


_MOCK_ADVICE = {
    "Blood sugar": {
        "summary": "Demo advice. For a low reading (under 4.0 mmol/L), follow the 15-15 rule.",
        "do_now": ["Have 15 g of fast-acting carbs, like half a cup of juice.", "Recheck in 15 minutes and repeat if still low."],
        "eat": ["Once you're back in range, a snack with protein, like cheese and crackers."],
        "avoid": ["Exercising until your level is back in range."],
        "seek_help_if": ["It stays low after two treatments.", "You feel confused or very drowsy."],
    },
    "Blood pressure": {
        "summary": "Demo advice. A single high reading is common; recheck at rest.",
        "do_now": ["Sit quietly for 5 minutes, feet flat, then measure again.", "Write both readings down."],
        "eat": ["Potassium-rich foods like bananas or leafy greens."],
        "avoid": ["Salty snacks and caffeine for now."],
        "seek_help_if": ["It reaches 180/120 or higher.", "You get chest pain, a severe headache or vision changes."],
    },
}
_MOCK_DEFAULT = {
    "summary": "Demo advice. Feeling weak or unwell is often linked to food, fluids or rest.",
    "do_now": ["Sit down and rest for a few minutes.", "Drink a glass of water."],
    "eat": ["A small snack with carbs and protein, like yogurt and fruit."],
    "avoid": ["Driving or heavy exercise until you feel better."],
    "seek_help_if": ["It gets worse or doesn't improve within a few hours.", "You faint or feel confused."],
}


def _mock_advice(metric):
    advice = dict(_MOCK_ADVICE.get(metric, _MOCK_DEFAULT))
    advice.update(urgent=False, demo=True)
    return advice