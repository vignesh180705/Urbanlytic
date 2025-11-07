from google.cloud import firestore
db = firestore.Client()
users=db.collection("users").stream()
for i in users:
    print(i.to_dict())