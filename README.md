# ChronoCare

**Health made simple.** ChronoCare is a web app that helps people manage their everyday health in one place. It builds personalised **meal**, **workout** and **sleep** plans with AI, tracks **blood pressure**, **blood sugar** and **sleep**, and turns it all into a simple daily plan with progress tracking.

> ⚠️ **ChronoCare is not medical advice.** It is a student project for general wellness tracking. It does not replace a doctor, nurse or other health professional. In an emergency, call 911.

---

## Features

| Page | What it does |
|---|---|
| **Overview** | Latest blood sugar, blood pressure and sleep, each with a score showing how close it is to the healthy range. **Today's plan** combines meals, workouts, the bedtime routine and health checks into one timeline, with a weekly **consistency** tracker, a **care note** and what's **up next**. |
| **Diet plan** | An AI-generated 7-day meal plan based on age, height, weight, cultural background, dietary restrictions, health conditions and goal. Day and week charts (macros and calories), swappable meal alternatives, recipe links and a daily checklist. |
| **Exercise** | A 7-day workout plan matched to fitness level, equipment and session length. Minutes-by-intensity charts, swappable alternatives (walks, HIIT, calisthenics, yoga and more) and "how to" video links. |
| **Sleep** | Log bedtime, wake time and sleep quality. See last night against your goal, plus a weekly average and chart. Get an AI bedtime routine built from your sleep goal and recent nights, with swappable wind-down activities. |
| **Insights** | Snapshot of every area and a full history of readings, symptoms, sleep, checklists, goals and plans. |
| **Log symptom / Log health data** | Quick popups to record readings and symptoms. Symptoms get practical self-care advice, and dangerous readings get immediate "get help now" guidance. |

Everyone signs up, answers a short **About you** form (age, height, weight, conditions, diet), and every plan is built from those answers.

---

## Tech stack

**Backend:** Python 3.11, Flask 3 (Blueprints), Flask-SQLAlchemy, Flask-Login, Flask-WTF (forms and CSRF protection)
**Frontend:** Jinja2 templates, HTML, CSS, vanilla JavaScript, [Chart.js](https://www.chartjs.org/), [Lucide icons](https://lucide.dev/)
**AI:** [Groq](https://groq.com/) API (default model `openai/gpt-oss-120b`)
**Database:** SQLite for local development, PostgreSQL in production
**Deployment:** Gunicorn on [Render](https://render.com/)

---

## Getting started

### 1. Clone and create a virtual environment

```bash
git clone https://github.com/ChronoCare/ChronoCare.git
cd ChronoCare
python -m venv venv
```

Activate it:

- **Windows:** `venv\Scripts\activate`
- **Mac/Linux:** `source venv/bin/activate`

You should see `(venv)` at the start of your terminal prompt.

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Create a `.env` file

In the project root (next to the `App` folder):

```
SECRET_KEY=any-long-random-string
GROQ_API_KEY=
GROQ_MODEL=openai/gpt-oss-120b
```

- **No API key? No problem.** With `GROQ_API_KEY` left empty, the app runs in **demo mode** with sample plans and advice, so you can try everything for free.
- For real AI plans, get a free key at [console.groq.com](https://console.groq.com) → API Keys.
- Generate a secret key with: `python -c "import secrets; print(secrets.token_hex(32))"`

> ⚠️ Never commit `.env`. It's already in `.gitignore`.

### 4. Run the app

```bash
flask --app App run --debug
```

Open http://127.0.0.1:5000, sign up, and fill in the **About you** page.

The database (`instance/chronocare.db`) is created automatically the first time the app runs.

---

## Project structure

```
ChronoCare/
├── App/
│   ├── __init__.py         # App factory: config, blueprints, home route
│   ├── models.py           # Database tables
│   ├── ai_service.py       # Every AI call (Groq) + demo data + emergency rules
│   ├── auth/               # Sign up, log in, log out, About you
│   ├── plans/
│   │   ├── routes.py       # Diet plan page + shared APIs (goal, checklist, symptoms)
│   │   ├── exercise.py     # Exercise page
│   │   ├── sleep.py        # Sleep page
│   │   ├── overview.py     # Overview (home) page
│   │   ├── insights.py     # Insights page
│   │   └── readings.py     # Parsing blood pressure / blood sugar readings
│   ├── templates/          # Jinja2 pages (base.html is the shared layout)
│   └── static/
│       ├── styles.css
│       └── js/             # One script per page, plus symptom.js (shared popup)
├── requirements.txt
└── .env                    # Your secrets (not in git)
```

### Main tables

| Table | Holds |
|---|---|
| `User`, `Profile` | Account and About you answers |
| `Goal`, `SleepGoal` | Health goal (shared by diet and exercise) and sleep goal |
| `MealPlan`, `WorkoutPlan`, `SleepPlan` | AI plans, stored as JSON |
| `ChecklistCheck` | Ticked checklist items per day (shared by every page) |
| `Reading` | Blood pressure and blood sugar readings |
| `SleepLog` | One row per night slept |
| `SymptomLog` | Logged symptoms and the advice given |

---

## How the AI is used safely

- **All AI calls live in [`App/ai_service.py`](App/ai_service.py)**. To switch AI provider, only this file changes.
- **Emergency rules run before the AI.** Readings like blood pressure ≥ 180/120, very low or very high blood sugar, or words like "chest pain" always get fixed "call 911 / see a doctor" guidance, never an AI answer.
- **Prompts forbid medication advice** and diagnoses, require strict respect for allergies and dietary restrictions, and adapt for conditions like diabetes and high blood pressure.
- **AI output is checked and cleaned** before it's saved, so a malformed answer can't break a page.
- **Recipe and exercise links are search links**, because AI models often invent URLs that don't exist.

### Healthy ranges used on the Overview

| Reading | Range used |
|---|---|
| Blood pressure | Normal under 120/80, Elevated 120–129, Stage 1 130–139 / 80–89, Stage 2 ≥ 140 / 90, Crisis ≥ 180 / 120 (American Heart Association categories) |
| Blood sugar (with diabetes) | 80–130 mg/dL (4.4–7.2 mmol/L) before eating, under 180 after (American Diabetes Association targets) |
| Blood sugar (without diabetes) | 70–99 mg/dL fasting, under 140 after eating |
| Sleep | Hours slept as a % of the person's own sleep goal |

The percentage score on each card is our own simple guide to how close a reading is to that range, not a medical measure.


## Working on the code

### Adding new packages

1. Make sure your venv is activated (you see `(venv)` in your terminal).
2. Install the package:
   ```bash
   pip install package-name
   ```
3. Update `requirements.txt`:
   - **Mac/Linux:** `pip freeze > requirements.txt`
   - **Windows (PowerShell):** `pip freeze | Out-File -Encoding utf8 requirements.txt`
     (plain `>` in PowerShell saves the file as UTF-16, which build servers can't read)
4. Commit `requirements.txt` **in the same PR** as the code that uses the package.

### After pulling changes

If `requirements.txt` changed:

```bash
pip install -r requirements.txt
```

### Changing database tables

`db.create_all()` creates **new** tables but doesn't change existing ones. If you add a column to an existing model:

- **Locally:** delete `instance/chronocare.db` and restart (you'll need to sign up again).
- **In production:** use a migration tool such as [Flask-Migrate](https://flask-migrate.readthedocs.io/). Don't delete the live database.

### Troubleshooting

| Problem | Fix |
|---|---|
| `model_not_found` from Groq | The model was retired. Pick a current one at [console.groq.com](https://console.groq.com) and update `GROQ_MODEL` in `.env`. |
| "Demo mode" badge won't go away | Check `GROQ_API_KEY` in `.env`, then restart the server (`.env` is only read at startup). |
| `BuildError: Could not build url for endpoint` | A `url_for(...)` points to a route name that doesn't exist. Page routes use their blueprint name, e.g. `url_for('plans.diet_plan')`. |
| A page has no styling | Hard-refresh with **Ctrl+Shift+R**, and check `styles.css` for an unclosed `{`. |

---

## Team

Built by the ChronoCare team. See [Contributors](https://github.com/ChronoCare/ChronoCare/graphs/contributors).

## License

[MIT](LICENSE) © 2026 ChronoCare
