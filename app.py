import asyncio
from fastapi import FastAPI, Request, WebSocket, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from google.cloud import pubsub_v1
from dotenv import load_dotenv
import json, os, threading
from datetime import datetime
from google.cloud import firestore
from google.cloud.firestore_v1 import SERVER_TIMESTAMP
import google.generativeai as genai
import re

load_dotenv()

PROJECT_ID = os.getenv("GCP_PROJECT_ID")
TOPIC_ID = os.getenv("PUBSUB_TOPIC")
SUBSCRIPTION_ID = os.getenv("SUBSCRIPTION_ID")
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
publisher = pubsub_v1.PublisherClient()
subscriber = pubsub_v1.SubscriberClient()

topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)
subscription_path = subscriber.subscription_path(PROJECT_ID, SUBSCRIPTION_ID)

app = FastAPI(title="Urbanlytic Ingestion + Dashboard")
templates = Jinja2Templates(directory="templates")

active_websockets = []
loop = asyncio.get_event_loop()  # capture FastAPI event loop

db = firestore.Client()

class IncidentReport(BaseModel):
    user_id: str
    description: str
    location: str

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

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
        # fallback
        result = {
            "category": "Other",
            "summary": description[:100]
        }
    return result


@app.post("/submit")
async def submit_report(report: IncidentReport):
    try:
        incident = report.dict()

        # 👉 Call AI classifier
        ai_result = classify_incident(incident["description"])

        # Prepare two versions of the payload
        incident_for_pubsub = {
            **incident,
            **ai_result,  # add category + summary
            "timestamp": datetime.utcnow().isoformat()
        }

        incident_for_firestore = {
            **incident,
            **ai_result,  # add category + summary
            "timestamp": firestore.SERVER_TIMESTAMP
        }

        # Publish to Pub/Sub
        future = publisher.publish(
            topic_path,
            json.dumps(incident_for_pubsub).encode("utf-8")
        )
        message_id = future.result()

        # Save to Firestore
        doc_ref = db.collection("incidents").document()
        doc_ref.set(incident_for_firestore)

        return {
            "status": "success",
            "message_id": message_id,
            "incident_id": doc_ref.id,
            "incident": incident_for_pubsub
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/history")
async def get_history():
    try:
        # Query last 10 incidents (sorted by timestamp desc)
        docs = db.collection("incidents").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(10).stream()
        history = [doc.to_dict() for doc in docs]
        return {"incidents": history}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    active_websockets.append(ws)
    try:
        while True:
            await ws.receive_text()  # keep alive
    except:
        active_websockets.remove(ws)

# Pub/Sub callback
def callback(message):
    data = message.data.decode("utf-8")
    print("📩 Received from Pub/Sub:", data)

    # Broadcast safely
    for ws in list(active_websockets):
        try:
            asyncio.run_coroutine_threadsafe(ws.send_text(data), loop)
        except Exception:
            active_websockets.remove(ws)

    message.ack()


def start_subscriber():
    streaming_pull_future = subscriber.subscribe(subscription_path, callback=callback)
    try:
        streaming_pull_future.result()
    except Exception as e:
        streaming_pull_future.cancel()

threading.Thread(target=start_subscriber, daemon=True).start()
