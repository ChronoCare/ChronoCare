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

-------------------------------
## Getting Started

### 1. Create a virtual environment
```bash
python -m venv venv
```

### 2. Activate it
**Windows:**
```bash
venv\Scripts\activate
```
**Mac/Linux:**
```bash
source venv/bin/activate
```
You should see `(venv)` at the start of your terminal prompt.

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Set up environment variables
Create a `.env` file in the project root:
```
SECRET_KEY=your-secret-key
ANTHROPIC_API_KEY=your-api-key
```
> ⚠️ Never commit `.env`. It's already in `.gitignore`.

### 5. Run the app
```bash
python run.py
```
Then open http://127.0.0.1:5000 in your browser.

---

## Adding New Packages

1. Make sure your venv is activated (you see `(venv)` in your terminal).
2. Install the package:
   ```bash
   pip install package-name
   ```
3. Update `requirements.txt`:
   ```bash
   pip freeze > requirements.txt
   ```
4. Commit `requirements.txt` **in the same PR** as the code that uses the package.

### After pulling changes
If `requirements.txt` changed, run this to stay in sync:
```bash
pip install -r requirements.txt
```