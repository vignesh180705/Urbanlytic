from google.cloud import firestore

db = firestore.Client()

class UserRepository:
    def __init__(self):
        self.collection = db.collection("users")

    def get_user_by_username(self, username):
        doc = self.collection.document(username).get()
        return doc.to_dict() if doc.exists else None

    def get_user_by_email(self, email):
        docs = self.collection.where("email", "==", email).get()
        return docs[0].to_dict() if docs else None

    def save_user(self, user_dict):
        self.collection.document(user_dict["username"]).set(user_dict)
