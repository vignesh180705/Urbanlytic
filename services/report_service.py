import os
from flask import url_for
from werkzeug.utils import secure_filename
from .ai_service import AIService
from repository.incident_repo import IncidentRepository
from google.cloud import firestore

class ReportService:
    def __init__(self):
        self.repo = IncidentRepository()
        self.ai_service = AIService()

    def create_report(self, form_data, files, user):
        incident = {
            "location": form_data.get("location"),
            "type": form_data.get("type"),
            "description": form_data.get("description"),
            "submitted_by": user,
            "timestamp": firestore.SERVER_TIMESTAMP
        }
        media = files.get("media")
        if media:
            filename = secure_filename(media.filename)
            media.save(os.path.join("static/uploads", filename))
            incident["media_url"] = url_for('static', filename=f"uploads/{filename}")
        ai_result = self.ai_service.classify_incident(incident["description"])
        incident.update(ai_result)
        incident_id = self.repo.save(incident)
        return incident_id
