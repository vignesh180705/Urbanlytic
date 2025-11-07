from google.cloud import firestore

db = firestore.Client()

class IncidentRepository:
    def __init__(self):
        self.collection = db.collection("incidents")

    def save(self, incident_data):
        doc_ref = self.collection.document()
        doc_ref.set(incident_data)
        return doc_ref.id
    def get_report_by_id(self, incident_id):
        doc_ref = self.collection.document(incident_id)
        doc = doc_ref.get()
        if doc.exists:
            return {"id": doc.id, **doc.to_dict()}
        return None

    def update_report_status(self, incident_id, status, proof_url=None):
        update_data = {"status": status}
        if proof_url:
            update_data["proof_image"] = proof_url
        self.collection.document(incident_id).update(update_data)

    def get_all_reports(self):
        docs = self.collection.stream()
        return docs
    
    def get_recent_high_priority_reports(self, limit=5):
        query = self.collection.where("priority", "==", "High").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(limit)
        docs = query.stream()
        return docs
    
    def get_reports_by_time(self):
        query = self.collection.order_by("timestamp", direction=firestore.Query.DESCENDING)
        docs = query.stream()
        return docs
    
    def get_reports_by_username(self, username):
        query = self.collection.where("submitted_by", "==", username).order_by("timestamp", direction=firestore.Query.DESCENDING)
        docs = query.stream()
        return docs