from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_socketio import SocketIO
from google.cloud import firestore
import os, json, re, threading
from dotenv import load_dotenv
from datetime import datetime
from google.cloud import pubsub_v1
import google.generativeai as genai
from werkzeug.security import generate_password_hash, check_password_hash

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

    Report: "{description}"
    Respond ONLY in JSON with keys: category, summary.
    """
    response = model.generate_content(prompt)
    raw_text = response.text.strip()
    cleaned = re.sub(r"^```(?:json)?|```$", "", raw_text, flags=re.MULTILINE).strip()
    try:
        return json.loads(cleaned)
    except Exception:
        return {"category": "Other", "summary": description[:100]}

# ------------------ Routes ------------------ #
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    '''if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        user_ref = db.collection("users").document(username).get()
        if user_ref.exists:
            user = user_ref.to_dict()
            if check_password_hash(user["password"], password):
                session["user"] = username
                return redirect(url_for("dashboard"))
            else:
                return render_template("login.html", error="Invalid password")
        else:
            return render_template("login.html", error="User not found")
    return render_template("login.html")'''
    return redirect(url_for("dashboard"))

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name")
        username = request.form.get("username")
        email = request.form.get("mail")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        # Check errors
        if password != confirm_password:
            return render_template("register.html", passError=True, name=name, username=username, mail=email)

        user_ref = db.collection("users").document(username).get()
        if user_ref.exists:
            return render_template("register.html", userError=True, name=name, username=username, mail=email)

        # Store hashed password
        hashed_pw = generate_password_hash(password)
        db.collection("users").document(username).set({
            "name": name,
            "username": username,
            "email": email,
            "password": hashed_pw,
            "created_at": datetime.utcnow()
        })
        return redirect(url_for("login"))

    return render_template("register.html")

@app.route("/dashboard")
def dashboard():
    '''if "user" not in session:
        return redirect(url_for("login"))
    return render_template("dashboard.html", user=session["user"])'''
    return render_template("dashboard.html", user="DemoUser", current_page='dashboard')

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("index"))

# ------------------ Reports + Analytics ------------------ #
@app.route("/reports")
def reports():
    '''if "user" not in session:
        return redirect(url_for("login"))'''
    return render_template("reports.html", current_page='reports')

@app.route("/analytics")
def analytics():
    '''if "user" not in session:
        return redirect(url_for("login"))'''
    return render_template("analytics.html", current_page='analytics')

# ------------------ Incident submission ------------------ #
@app.route("/submit", methods=["POST"])
def submit_report():
    try:
        incident = request.json
        ai_result = classify_incident(incident["description"])

        pubsub_dict = {**incident, **ai_result, "timestamp": datetime.utcnow().isoformat()}
        firestore_dict = {**incident, **ai_result, "timestamp": firestore.SERVER_TIMESTAMP}

        # Publish to Pub/Sub
        future = publisher.publish(topic_path, json.dumps(pubsub_dict).encode("utf-8"))
        message_id = future.result()

        # Save to Firestore
        doc_ref = db.collection("incidents").document()
        doc_ref.set(firestore_dict)

        socketio.emit("new_incident", pubsub_dict)

        return jsonify({"status": "success", "message_id": message_id, "incident_id": doc_ref.id})
    except Exception as e:
        return jsonify({"status": "error", "detail": str(e)}), 500

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
