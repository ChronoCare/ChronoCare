# ChronoCare
-----------------------
```
app/
├── __init__.py      # app factory
├── models.py        # User, Profile, Reading, Plan
├── auth/            # login, signup
├── dashboard/       # charts, today summary, alerts
├── logs/            # blood sugar / BP / meal / sleep entry
├── plans/           # Claude-generated plans
├── templates/
└── static/
seed.py              # fake demo data for judging
```

## Tech Stack

**Backend**
- Python + Flask (Blueprints)
- Flask-SQLAlchemy (database ORM)
- Flask-Login (authentication)
- Flask-WTF (forms + CSRF protection)

**Frontend**
- Jinja2 templates
- CSS
- HTML
- Chart.js (blood sugar, BP, and sleep charts)

**Database**
- SQLite (local development)
- PostgreSQL (production)

**AI & Data**
- Claude API (Anthropic): personalized meal, exercise, and sleep plans
- USDA FoodData Central API: nutrition data

**Deployment**
- Render / Railway
