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
