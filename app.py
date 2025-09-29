from flask import Flask, render_template, request, session, redirect, url_for, jsonify
from flask_socketio import SocketIO
from google.cloud import firestore
import os, json, re, threading
from dotenv import load_dotenv
from google.cloud import pubsub_v1
import google.generativeai as genai
from services.report_service import ReportService
from services.ai_service import AIService
from repository.report_repository import ReportRepository
from services.user_service import UserService

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "supersecret")  
socketio = SocketIO(app, cors_allowed_origins="*")

PROJECT_ID = os.getenv("GCP_PROJECT_ID")
TOPIC_ID = os.getenv("PUBSUB_TOPIC")
SUBSCRIPTION_ID = os.getenv("SUBSCRIPTION_ID")
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

publisher = pubsub_v1.PublisherClient()
subscriber = pubsub_v1.SubscriberClient()
topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)
subscription_path = subscriber.subscription_path(PROJECT_ID, SUBSCRIPTION_ID)

db = firestore.Client()

ai_classifier = AIService()
report_repository = ReportRepository(db)
report_service = ReportService()
user_service = UserService()
auth_service = UserService()

def classify_incident(description: str) -> dict:
    model = genai.GenerativeModel("gemini-1.5-flash")
    prompt = f"""
    You are an incident classification agent. 
    Classify the following report into one of these categories:
    [Accident, Fire, Theft, Medical, Traffic, Other]

    Also provide a short summary in plain English. 
    Assign priority for the complaint among Low,Medium, and High.

    Report: "{description}"
    Respond ONLY in JSON with keys: category, summary, priority.
    """
    response = model.generate_content(prompt)
    raw_text = response.text.strip()
    cleaned = re.sub(r"^```(?:json)?|```$", "", raw_text, flags=re.MULTILINE).strip()
    try:
        return json.loads(cleaned)
    except Exception:
        return {"category": "Other", "summary": description[:100], "priority": "Low"}

@app.route("/")
def index():
    return render_template("index.html")

from datetime import timedelta

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        user, error = user_service.authenticate_user(username, password)
        if error:
            return render_template("login.html", error=error)

        session["user"] = username
        return redirect(url_for("dashboard"))

    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        data = {
            "name": request.form.get("name"),
            "username": request.form.get("username"),
            "email": request.form.get("mail"),
            "phone": request.form.get("phone"),
            "password": request.form.get("password"),
            "confirm_password": request.form.get("confirm_password")
        }

        errors = user_service.validate_registration(data)
        if errors:
            return render_template("register.html", **data, **errors)

        user_service.register_user(data)
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("dashboard.html", user=session["user"], current_page='dashboard')

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("index"))

@app.route("/reports")
def reports():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("reports.html", user=session['user'], current_page='reports')

@app.route("/analytics")
def analytics():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("analytics.html", user=session['user'], current_page='analytics')


import traceback

@app.route("/submit", methods=["GET","POST"])
def submit_report():
    if "user" not in session:
        return jsonify({"status": "error", "detail": "User not logged in"}), 401

    if request.method == "POST":
        try:
            incident_id = report_service.create_report(request.form, request.files, user=session['user'])
            return jsonify({"status": "success", "incident_id": incident_id})
        except Exception as e:
            print("Submit Error:", e)
            traceback.print_exc()
            return jsonify({"status": "error", "detail": str(e)}), 500

    return render_template("submit_report.html", user=session['user'], current_page='submit_report')

def callback(message):
    try:
        data = json.loads(message.data.decode("utf-8"))
        socketio.emit("new_incident", data)
        message.ack()
    except Exception as e:
        print("Subscriber error:", e)

def start_subscriber():
    future = subscriber.subscribe(subscription_path, callback=callback)
    try:
        future.result()
    except Exception as e:
        future.cancel()

threading.Thread(target=start_subscriber, daemon=True).start()

@app.route("/user/reports")
def get_user_reports():
    if "user" not in session:
        return jsonify({"status": "error", "detail": "Not logged in"}), 401

    username = session["user"]
    reports_ref = db.collection("incidents").where("submitted_by", "==", username).order_by("timestamp", direction=firestore.Query.DESCENDING)
    reports = [doc.to_dict() for doc in reports_ref.stream()]

    # Ensure timestamp is JSON serializable
    for r in reports:
        if "timestamp" in r:
            r["timestamp"] = r["timestamp"]

        if "media_url" in r:
            r["media_url"] = r["media_url"]

        if "priority" not in r: r["priority"] = "Low"
        if "status" not in r: r["status"] = "Pending"

    return jsonify({"status": "success", "reports": reports})


if __name__ == "__main__":
    socketio.run(app,debug=True)
