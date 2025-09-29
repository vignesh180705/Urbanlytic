from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_socketio import SocketIO
from google.cloud import firestore
import os, json, re, threading
from dotenv import load_dotenv
from datetime import datetime
from google.cloud import pubsub_v1
import google.generativeai as genai
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# ------------------ Setup ------------------ #
load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "supersecret")  # Needed for sessions
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

# ------------------ AI Classification ------------------ #
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

# ------------------ Routes ------------------ #
@app.route("/")
def index():
    return render_template("index.html")

from datetime import timedelta

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        remember = request.form.get("remember")  # checkbox value ("on" if checked)

        user_ref = db.collection("users").document(username).get()
        if user_ref.exists:
            user = user_ref.to_dict()
            if check_password_hash(user["password"], password):
                session["user"] = username

                # If Remember Me checked, extend session lifetime
                if remember == "on":
                    session.permanent = True
                    app.permanent_session_lifetime = timedelta(days=30)
                else:
                    session.permanent = False

                return redirect(url_for("dashboard"))
            else:
                return render_template("login.html", error="Invalid password")
        else:
            return render_template("login.html", error="User not found")

    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name")
        username = request.form.get("username")
        email = request.form.get("mail")
        phone = request.form.get("phone")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        # Error flags
        errors = {}

        # Check username already exists
        user_ref = db.collection("users").document(username).get()
        if user_ref.exists:
            errors["userError"] = True

        # Password mismatch
        if password != confirm_password:
            errors["passError"] = True

        # Password strength checks
        if len(password) < 8:
            errors["lengthError"] = True
        if not re.search(r"[A-Z]", password):
            errors["upperCaseError"] = True
        if not re.search(r"[a-z]", password):
            errors["lowerCaseError"] = True
        if not re.search(r"[0-9]", password):
            errors["numberError"] = True
        if not re.search(r"[@$!%*?&#]", password):
            errors["specialCharError"] = True

        # Phone validation (10+ digits)
        if not phone.isdigit() or len(phone) < 10:
            errors["phoneError"] = True

        # Email validation (simple regex)
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            errors["mailNotValidError"] = True

        # Check if email exists
        existing_email = db.collection("users").where("email", "==", email).get()
        if existing_email:
            errors["mailError"] = True

        # If errors, return back to form with inputs preserved
        if errors:
            return render_template(
                "register.html",
                name=name,
                username=username,
                mail=email,
                phone=phone,
                **errors
            )

        # Store hashed password
        hashed_pw = generate_password_hash(password)
        db.collection("users").document(username).set({
            "name": name,
            "username": username,
            "email": email,
            "phone": phone,
            "password": hashed_pw,
            "created_at": datetime.utcnow()
        })
        return redirect(url_for("login"),successMsg="Registration successful! Please log in.")

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

# ------------------ Reports + Analytics ------------------ #
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

# ------------------ Incident submission ------------------ #

@app.route("/submit", methods=["GET","POST"])
def submit_report():
    if "user" not in session:
        return jsonify({"status": "error", "detail": "User not logged in"}), 401
    if request.method == "POST":
        try:
            incident = {
                "location": request.form.get("location"),
                "type": request.form.get("type"),
                "description": request.form.get("description"),
                "timestamp": firestore.SERVER_TIMESTAMP
            }

            # Handle media file if uploaded
            media = request.files.get("media")
            if media:
                filename = secure_filename(media.filename)
                media.save(os.path.join("static/uploads", filename))
                incident["media_url"] = url_for('static', filename=f"uploads/{filename}")

            # AI classification
            ai_result = classify_incident(incident["description"])
            incident.update(ai_result)

            # Save to Firestore
            doc_ref = db.collection("incidents").document()
            doc_ref.set(incident)

            return jsonify({"status": "success", "incident_id": doc_ref.id})
        except Exception as e:
            return jsonify({"status": "error", "detail": str(e)}), 500
    return render_template("submit_report.html", user=session['user'], current_page='submit_report')

@app.route("/history")
def get_history():
    docs = db.collection("incidents").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(10).stream()
    return jsonify({"incidents": [doc.to_dict() for doc in docs]})

# ------------------ Pub/Sub Subscriber ------------------ #
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

# ------------------ Run ------------------ #
if __name__ == "__main__":
    socketio.run(app,debug=True)
