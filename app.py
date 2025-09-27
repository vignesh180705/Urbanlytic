import os
import json
import re
import threading
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from google.cloud import pubsub_v1, firestore
import google.generativeai as genai

load_dotenv()

# GCP + AI setup
PROJECT_ID = os.getenv("GCP_PROJECT_ID")
TOPIC_ID = os.getenv("PUBSUB_TOPIC")
SUBSCRIPTION_ID = os.getenv("SUBSCRIPTION_ID")
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

publisher = pubsub_v1.PublisherClient()
subscriber = pubsub_v1.SubscriberClient()

topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)
subscription_path = subscriber.subscription_path(PROJECT_ID, SUBSCRIPTION_ID)

db = firestore.Client()

# Flask app + SocketIO
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# In-memory active websocket clients
active_websockets = []

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
    Example:
    {{
      "category": "Traffic",
      "summary": "Minor traffic jam near Central Avenue"
    }}
    """
    response = model.generate_content(prompt)
    raw_text = response.text.strip()
    cleaned = re.sub(r"^```(?:json)?|```$", "", raw_text, flags=re.MULTILINE).strip()
    try:
        result = json.loads(cleaned)
    except Exception:
        result = {"category": "Other", "summary": description[:100]}
    return result

# ------------------ Routes ------------------ #
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/report")
def report():
    return render_template("reports.html")

@app.route("/login")
def login():
    return render_template("login.html")

@app.route("/register")
def register():
    return render_template("register.html")

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

        # Emit to active websockets
        socketio.emit("new_incident", pubsub_dict)

        return jsonify({
            "status": "success",
            "message_id": message_id,
            "incident_id": doc_ref.id,
            "incident": pubsub_dict
        })
    except Exception as e:
        return jsonify({"status": "error", "detail": str(e)}), 500

@app.route("/history")
def get_history():
    try:
        docs = db.collection("incidents").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(10).stream()
        history = [doc.to_dict() for doc in docs]
        return jsonify({"incidents": history})
    except Exception as e:
        return jsonify({"status": "error", "detail": str(e)}), 500

# ------------------ WebSocket ------------------ #
@socketio.on("connect")
def handle_connect():
    active_websockets.append(request.sid)
    print("Client connected:", request.sid)

@socketio.on("disconnect")
def handle_disconnect():
    if request.sid in active_websockets:
        active_websockets.remove(request.sid)
    print("Client disconnected:", request.sid)

# ------------------ Pub/Sub Subscriber ------------------ #
def callback(message):
    data = message.data.decode("utf-8")
    print("Received from Pub/Sub:", data)
    socketio.emit("new_incident", json.loads(data))
    message.ack()

def start_subscriber():
    streaming_pull_future = subscriber.subscribe(subscription_path, callback=callback)
    try:
        streaming_pull_future.result()
    except Exception as e:
        streaming_pull_future.cancel()
        print("Subscriber stopped:", e)

threading.Thread(target=start_subscriber, daemon=True).start()

# ------------------ Run App ------------------ #
if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=8000)
