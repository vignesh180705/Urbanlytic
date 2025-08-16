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

@app.post("/submit")
async def submit_report(report: IncidentReport):
    try:
        incident = report.dict()

        # Prepare two versions of the payload
        # 👉 For Pub/Sub and WebSocket: use fixed UTC timestamp
        incident_for_pubsub = {
            **incident,
            "timestamp": datetime.utcnow().isoformat()
        }

        # 👉 For Firestore: use server-generated timestamp
        incident_for_firestore = {
            **incident,
            "timestamp": firestore.SERVER_TIMESTAMP
        }

        # Publish to Pub/Sub
        future = publisher.publish(
            topic_path,
            json.dumps(incident_for_pubsub).encode("utf-8")
        )
        message_id = future.result()  # wait for publish confirmation (optional)

        # Save to Firestore (returns a DocumentReference)
        doc_ref = db.collection("incidents").document()
        doc_ref.set(incident_for_firestore)

        return {
            "status": "success",
            "message_id": message_id,
            "incident_id": doc_ref.id,
            "incident": incident_for_pubsub  # return client-friendly version
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

def classify_incident(description: str) -> str:
    model = genai.GenerativeModel("gemini-1.5-flash")  # or gemini-pro
    prompt = f"""
    You are an incident classification agent. 
    Classify the following report into one of these categories:
    [Accident, Fire, Theft, Medical, Traffic, Other]

    Report: "{description}"

    Return ONLY the category.
    """
    response = model.generate_content(prompt)
    return response.text.strip()


threading.Thread(target=start_subscriber, daemon=True).start()
