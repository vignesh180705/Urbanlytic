from flask import Flask, render_template, request, session, redirect, url_for, jsonify
from flask_socketio import SocketIO
from google.cloud import firestore
import os, json, re, threading, traceback
from dotenv import load_dotenv
from google.cloud import pubsub_v1
import google.generativeai as genai
from services.report_service import ReportService
from services.ai_service import AIService
from services.user_service import UserService
from repository.incident_repo import IncidentRepository
from repository.user_repository import UserRepository
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash
#from services.clustering_service import ClusteringService

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "supersecret")
socketio = SocketIO(app, cors_allowed_origins="*")

app.config["SESSION_PERMANENT"] = False
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)

PROJECT_ID = os.getenv("GCP_PROJECT_ID")
TOPIC_ID = os.getenv("PUBSUB_TOPIC")
SUBSCRIPTION_ID = os.getenv("SUBSCRIPTION_ID")
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

publisher = pubsub_v1.PublisherClient()
subscriber = pubsub_v1.SubscriberClient()
topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)
subscription_path = subscriber.subscription_path(PROJECT_ID, SUBSCRIPTION_ID)

db = firestore.Client()
ai_classifier = AIService()
incident_repo = IncidentRepository()
user_repo = UserRepository()
report_service = ReportService()
user_service = UserService()
#clustering_service = ClusteringService(eps=0.3, min_samples=2)
def format_timestamp(ts):
    if hasattr(ts, "strftime"):
        return ts.strftime("%Y-%m-%d %H:%M:%S")
    return str(ts)

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if 'user' in session:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        remember = request.form.get("remember")
        user, error = user_service.authenticate_user(username, password)
        if error:
            return render_template("login.html", error=error)
        session["user"] = username
        if remember:
            session.permanent = True
            app.permanent_session_lifetime = timedelta(days=30)
        else:
            session.permanent = False
        return redirect(url_for("dashboard"))
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        data = {
            "name": request.form.get("name"),
            "username": request.form.get("username"),
            "email": request.form.get("mail"),
            "phone": request.form.get("phone"),
            "password": request.form.get("password"),
            "confirm_password": request.form.get("confirm_password"),
        }
        errors = user_service.validate_registration(data)
        if errors:
            return render_template("register.html", **data, **errors)
        user_service.register_user(data)
        return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))
    print(session["user"])
    return render_template("dashboard.html", user=session["user"], current_page="dashboard")


@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("index"))


@app.route("/reports")
def reports():
    if "user" not in session:
        return redirect(url_for("login"))
    
    return render_template("reports.html", user=session["user"], current_page="reports")


@app.route("/analytics")
def analytics():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("analytics.html", user=session["user"], current_page="analytics")


@app.route("/submit", methods=["GET", "POST"])
def submit_report():
    if "user" not in session:
        return jsonify({"status": "error", "detail": "User not logged in"}), 401
    if request.method == "POST":
        try:
            incident_id = report_service.create_report(request.form, request.files, user=session["user"])
            report = incident_repo.get_report_by_id(incident_id)
            if not report:
                return jsonify({"status": "error", "detail": "Report not found after creation"}), 500
            return jsonify({"status": "success", "incident_id": incident_id, "report": report})
        except Exception as e:
            traceback.print_exc()
            return jsonify({"status": "error", "detail": str(e)}), 500
    return render_template("submit_report.html", user=session["user"], current_page="submit_report")

'''@app.route("/cluster_incidents", methods=["POST"])
def cluster_incidents():
    all_reports = incident_repo.get_all_reports()  
    clustered_reports, labels = clustering_service.cluster_reports(all_reports)
    
    # Optionally, save cluster IDs back to DB
    for report in clustered_reports:
        incident_repo.update_cluster_id(report["id"], report["cluster_id"])
    
    return jsonify({"status": "success", "clusters": labels.tolist()})'''

@app.route("/settings")
def settings():
    if "user" not in session:
        return redirect(url_for("login"))

    user_data = user_repo.get_user_by_username(session["user"])
    return render_template("settings.html", user_info=user_data, current_page="settings", user=session["user"])


@app.route("/update_profile", methods=["POST"])
def update_profile():
    if "user" not in session:
        return jsonify({"status": "error", "detail": "Not logged in"}), 401

    data = request.get_json()
    username = session["user"]
    errors = user_service.validate_profile_update(username, data)
    if errors:
        detail=""
        for i in errors:
            if i=="mailError":
                detail+="\nEmail already in use."
            if i=="phoneError":
                detail+="\nInvalid Phone Number."
            if i=="mailNotValidError":
                detail+="\nInvalid Email Address."
        return jsonify({"status": "error", "detail": detail, "errors": errors}), 400
    try:
        user_service.update_profile(username, data)
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "detail": detail}), 500


@app.route("/change_password", methods=["POST"])
def change_password():
    if "user" not in session:
        return jsonify({"status": "error", "detail": "Not logged in"}), 401
    data = request.get_json()
    username = session["user"]
    errors = user_service.validate_password_change(
        username,
        data.get("current_password"),
        data.get("new_password"),
        data.get("confirm_password"),
    )
    if errors:
        detail=""
        for i in errors:
            if i=="currentPassError":
                detail+="\nCurrent password is incorrect."
            if i=="passError":
                detail+="\nNew passwords do not match."
            if i=="lengthError":
                detail+="\nPassword must be at least 8 characters long."
            if i=="upperCaseError":
                detail+="\nPassword must contain at least one uppercase letter."
            if i=="numberError":
                detail+="\nPassword must contain at least one digit."
            if i=="specialCharError":
                detail+="\nPassword must contain at least one special character."
            if i=="lowerCaseError":
                detail+="\nPassword must contain at least one lowercase letter."
        return jsonify({"status": "error", "detail": detail, "errors": errors}), 400

    try:
        user_service.change_password(username, data["new_password"])
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "detail": str(e)}), 500


@app.route("/user/reports")
def get_user_reports():
    if "user" not in session:
        return jsonify({"status": "error", "detail": "Not logged in"}), 401

    username = session["user"]
    reports_stream = incident_repo.get_reports_by_username(username)

    reports = []
    for doc in reports_stream:
        r = doc.to_dict()
        r["timestamp"] = format_timestamp(r.get("timestamp"))
        r["priority"] = r.get("priority", "Low")
        r["status"] = r.get("status", "Pending")
        reports.append(r)

    return jsonify({"status": "success", "reports": reports})

@app.route('/user/all_reports')
def get_all_reports():
    if "user" not in session:
        return jsonify({"status": "error", "detail": "Not logged in"})
    reports_stream = incident_repo.get_all_reports()
    reports = []
    for doc in reports_stream:
        print('doc:', doc)
        r = doc.to_dict()
        r["timestamp"] = format_timestamp(r.get("timestamp"))
        r["priority"] = r.get("priority", "Low")
        r["status"] = r.get("status", "Pending")
        reports.append(r)
    print("Reports:",reports)
    return jsonify({"status": "success", "reports": reports})

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method=='POST':
        username = request.form.get('username')
        password = request.form.get('password')
        admins = db.collection("admins").where("username", "==", username).get()
        admin_data = admins[0].to_dict() if admins else None
        if not admin_data:
            error='Invalid Username'
            return render_template("admin_login.html", error=error)
        if password!=admin_data.get('password'):
            error='Invalid Password'
            return render_template("admin_login.html", error=error)
        session['user']='admin'
        return redirect(url_for("admin_dashboard"))
    return render_template('admin_login.html',error=None)
        

@app.route("/admin/users")
def admin_users():
    users_stream = user_repo.get_all_users()
    users = []
    for doc in users_stream:
        data = doc.to_dict()
        created_at = data.get("created_at")
        users.append({
            "Name": data.get("name", "N/A"),
            "Username": data.get("username", "N/A"),
            "Email": data.get("email", "N/A"),
            "Phone": data.get("phone", "N/A"),
            "Joined": format_timestamp(created_at) if created_at else "—",
        })
    return render_template("admin_users.html", users=users, current_page="admin_users")


@app.route("/admin/reports")
def admin_reports():
    reports_stream = incident_repo.get_reports_by_time()
    reports = []
    for r in reports_stream:
        data = r.to_dict()
        data['id'] = r.id
        reports.append({
            "id": data.get("id"),
            "type": data.get("type", "Unknown"),
            "category": data.get("category", "Unknown"),
            "summary": data.get("summary", "No description"),
            "location": data.get("location", "N/A"),
            "priority": data.get("priority", "Low"),
            "status": data.get("status", "Pending"),
            "media_url": data.get("media_url"),
            "timestamp": format_timestamp(data.get("timestamp")),
            "user_email": data.get("submitted_by", "Unknown"),
        })
        print(data.get("id"))
    return render_template("admin_reports.html", reports=reports, page_title="All Reports")

@app.route("/admin/reports/<incident_id>")
def admin_report_detail(incident_id):
    report = incident_repo.get_report_by_id(incident_id)
    if not report:
        return "Report not found", 404
    report["timestamp"] = format_timestamp(report.get("timestamp"))
    return render_template("admin_report_detail.html", report=report, current_page="admin_reports", page_title=f"Report #{incident_id}")

@app.route("/admin/reports/<incident_id>/update", methods=["POST"])
def update_report_status(incident_id):
    status = request.form.get("status")
    proof = request.files.get("proof")

    proof_url = None
    if status == "Resolved":
        if not proof:
            return jsonify({"status": "error", "detail": "Proof image required for resolution"}), 400
        filename = secure_filename(proof.filename)
        proof.save(os.path.join("static/uploads/proofs", filename))
        proof_url = url_for("static", filename=f"uploads/proofs/{filename}")

    incident_repo.update_report_status(incident_id, status, proof_url)
    return redirect(url_for("admin_reports"))

@app.route("/admin/reports/<incident_id>/proof", methods=["POST"])
def upload_proof(incident_id):
    file = request.files.get("proof_image")
    notes = request.form.get("notes", "")

    if not file:
        return "No file uploaded", 400

    filename = secure_filename(file.filename)
    path = os.path.join("static/proofs", filename)
    file.save(path)
    image_url = url_for('static', filename=f"proofs/{filename}")

    '''db.collection("proofs").add({
        "incident_id": incident_id,
        "uploaded_by": session.get("user", "admin"),
        "image_url": image_url,
        "timestamp": firestore.SERVER_TIMESTAMP,
        "notes": notes
    })'''

    incident_repo.update_report_status(incident_id, "Resolved", proof_url=image_url)

    return redirect(url_for('admin_report_detail', incident_id=incident_id))


@app.route("/admin/dashboard")
def admin_dashboard():
    reports_stream = incident_repo.get_reports_by_time()
    reports = [r.to_dict() for r in reports_stream]
    stats = {
        "total_reports": len(reports),
        "in_progress": len([r for r in reports if r.get("status") == "In Progress"]),
        "resolved": len([r for r in reports if r.get("status") == "Resolved"]),
        "active_users": (user_repo.get_users_count())
    }
    print("Stats:", stats)
    recent_reports_stream = incident_repo.get_recent_high_priority_reports(limit=5)
    recent_reports = []
    for doc in recent_reports_stream:
        data = doc.to_dict()
        data["id"] = doc.id 
        data["timestamp"] = format_timestamp(data.get("timestamp"))
        recent_reports.append(data)
    print("Recent Reports:",recent_reports)
    return render_template("admin_dashboard.html", stats=stats, recent_reports=recent_reports, current_page="admin_dashboard")



def callback(message):
    try:
        data = json.loads(message.data.decode("utf-8"))
        socketio.emit("new_incident", data)
        message.ack()
    except Exception as e:
        print("Subscriber error:", e)


def start_subscriber():
    future = subscriber.subscribe(subscription_path, callback=callback)
    try:
        future.result()
    except Exception:
        future.cancel()


threading.Thread(target=start_subscriber, daemon=True).start()

if __name__ == "__main__":
    socketio.run(app, debug=True)
