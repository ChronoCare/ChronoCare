from flask import Flask, render_template
from datetime import date


def create_app():
    app = Flask(__name__)

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/diet_plan")
    def diet_plan():
        return render_template("diet_plan.html")

    @app.route("/exercise")
    def exercise():
        return render_template("exercise.html")

    @app.route("/sleep")
    def sleep():
        return render_template("sleep.html")

    @app.route("/insights")
    def insights():
        return render_template("insights.html")

    @app.route("/profile")
    def profile():
        return render_template("profile.html")

    @app.context_processor
    def inject_year():
        return {"now_year": date.today().year}


    return app