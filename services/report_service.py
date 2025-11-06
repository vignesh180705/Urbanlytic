import os
from flask import url_for
from werkzeug.utils import secure_filename
from .ai_service import AIService
from repository.incident_repo import IncidentRepository
from google.cloud import firestore
import json
from google.cloud import pubsub_v1
publisher = pubsub_v1.PublisherClient()
project_id = os.getenv("GCP_PROJECT_ID")
topic_id = os.getenv("PUBSUB_TOPIC")
topic_path = publisher.topic_path(project_id, topic_id)
class ReportService:
    def __init__(self):
        self.repo = IncidentRepository()
        self.ai_service = AIService()

    def create_report(self, form_data, files, user):
        incident = {
            "location": form_data.get("location"),
            "category": form_data.get("type"),  # User-selected category
            "description": form_data.get("description"),
            "submitted_by": user,
            "timestamp": firestore.SERVER_TIMESTAMP,
            "priority": "Low",              # default until AI assigns
            "type": "Other",                # AI classification default
            "summary": form_data.get("summary", ""),
            "status": "Pending"             # default status
        }

        media = files.get("media")
        if media:
            filename = secure_filename(media.filename)
            media.save(os.path.join("static/uploads", filename))
            incident["media_url"] = url_for('static', filename=f"uploads/{filename}")

        if self.ai_service:
            ai_result = self.ai_service.classify_incident(incident["description"])
            incident.update({
                "type": ai_result.get("category", "Other"),      # AI classification
                "priority": ai_result.get("priority", "Low"),
                "summary": ai_result.get("summary", incident["summary"])
            })

        incident_id = self.repo.save(incident)
        try:
            message_data = incident.copy()
            message_data["incident_id"] = incident_id
            message_json = json.dumps(message_data).encode("utf-8")
            publisher.publish(topic_path, message_json)
        except Exception as e:
            print("Error publishing to Pub/Sub:", e)

        return incident_id
        return incident_id
