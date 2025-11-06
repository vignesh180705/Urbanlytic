from google.cloud import firestore

class ReportRepository:
    def __init__(self, db):
        self.db = db

    def save_report(self, report_dict):
        doc_ref = self.db.collection("incidents").document()
        doc_ref.set(report_dict)
        return doc_ref.id

    def get_server_timestamp(self):
        return firestore.SERVER_TIMESTAMP
    
    def get_report_by_id(self, incident_id):
        doc_ref = self.db.collection("incidents").document(incident_id)
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict()
        return None
    
