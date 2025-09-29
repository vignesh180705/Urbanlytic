from google.cloud import firestore

db = firestore.Client()

class IncidentRepository:
    def __init__(self):
        self.collection = db.collection("incidents")

    def save(self, incident_data):
        doc_ref = self.collection.document()
        doc_ref.set(incident_data)
        return doc_ref.id
