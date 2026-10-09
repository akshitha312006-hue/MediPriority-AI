from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "medipriority.db"
app = Flask(__name__)
app.secret_key = "change-this-demo-secret-key"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS assessments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_name TEXT NOT NULL,
                age INTEGER NOT NULL,
                contact TEXT,
                symptoms TEXT NOT NULL,
                duration TEXT NOT NULL,
                severity INTEGER NOT NULL,
                red_flags TEXT,
                priority TEXT NOT NULL,
                recommendation TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'New',
                created_at TEXT NOT NULL
            )
        """)

def assess_priority(symptoms, severity, duration, red_flags):
    """Transparent demo rules; not a diagnosis or a substitute for clinical triage."""
    flags = {x.strip().lower() for x in (red_flags or "").split(",") if x.strip()}
    text = symptoms.lower()
    emergency_terms = {
        "chest pain", "difficulty breathing", "trouble breathing", "unconscious",
        "fainting", "stroke symptoms", "face drooping", "one-sided weakness",
        "severe bleeding", "seizure", "blue lips"
    }
    emergency_flags = {
        "chest pain", "difficulty breathing", "unconsciousness/fainting",
        "stroke signs", "severe bleeding", "seizure", "blue lips"
    }
    if flags.intersection(emergency_flags) or any(term in text for term in emergency_terms):
        return ("Emergency", "Seek emergency medical help now. Call your local emergency number (112 in India). Do not wait for this website or use it to decide whether symptoms are safe.")
    if severity >= 8 or "high fever in infant" in text or "severe allergic reaction" in text:
        return ("High", "Get urgent medical assessment as soon as possible today. If symptoms worsen or an emergency warning sign appears, seek emergency help.")
    if severity >= 5 or duration in ("1–3 days", "4–7 days", "More than 1 week"):
        return ("Moderate", "Arrange a medical consultation soon, especially if symptoms persist, worsen, or affect normal activities.")
    return ("Routine", "Consider routine medical advice if needed. Monitor symptoms and seek care if they persist or worsen.")

@app.route("/")
def index():
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM assessments").fetchone()[0]
        emergency = conn.execute("SELECT COUNT(*) FROM assessments WHERE priority='Emergency'").fetchone()[0]
        high = conn.execute("SELECT COUNT(*) FROM assessments WHERE priority='High'").fetchone()[0]
        recent = conn.execute("SELECT * FROM assessments ORDER BY id DESC LIMIT 6").fetchall()
    return render_template("index.html", total=total, emergency=emergency, high=high, recent=recent)

@app.route("/assess", methods=["GET", "POST"])
def assess():
    if request.method == "POST":
        name = request.form.get("patient_name", "").strip()
        age_raw = request.form.get("age", "").strip()
        contact = request.form.get("contact", "").strip()
        symptoms = request.form.get("symptoms", "").strip()
        duration = request.form.get("duration", "").strip()
        red_flags = ",".join(request.form.getlist("red_flags"))
        try:
            age = int(age_raw)
            severity = int(request.form.get("severity", "1"))
        except ValueError:
            flash("Enter a valid age and symptom severity.", "error")
            return redirect(url_for("assess"))
        if not name or not symptoms or not duration or not (0 <= age <= 120) or not (1 <= severity <= 10):
            flash("Please complete all required fields using valid values.", "error")
            return redirect(url_for("assess"))
        priority, recommendation = assess_priority(symptoms, severity, duration, red_flags)
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M")
        with get_db() as conn:
            cur = conn.execute("""
                INSERT INTO assessments
                (patient_name, age, contact, symptoms, duration, severity, red_flags, priority, recommendation, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'New', ?)
            """, (name, age, contact, symptoms, duration, severity, red_flags, priority, recommendation, created_at))
            record_id = cur.lastrowid
        return redirect(url_for("result", record_id=record_id))
    return render_template("assess.html")

@app.route("/result/<int:record_id>")
def result(record_id):
    with get_db() as conn:
        record = conn.execute("SELECT * FROM assessments WHERE id=?", (record_id,)).fetchone()
    if record is None:
        flash("Assessment not found.", "error")
        return redirect(url_for("index"))
    return render_template("result.html", record=record)

@app.route("/records")
def records():
    q = request.args.get("q", "").strip()
    priority = request.args.get("priority", "").strip()
    sql = "SELECT * FROM assessments WHERE 1=1"
    params = []
    if q:
        sql += " AND (patient_name LIKE ? OR symptoms LIKE ?)"
        params += [f"%{q}%", f"%{q}%"]
    if priority in ("Emergency", "High", "Moderate", "Routine"):
        sql += " AND priority=?"
        params.append(priority)
    sql += " ORDER BY id DESC"
    with get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
    return render_template("records.html", rows=rows, q=q, priority=priority)

@app.post("/records/<int:record_id>/status")
def update_status(record_id):
    status = request.form.get("status", "New")
    if status not in ("New", "Reviewed", "Follow-up"):
        status = "New"
    with get_db() as conn:
        conn.execute("UPDATE assessments SET status=? WHERE id=?", (status, record_id))
    flash("Record status updated.", "success")
    return redirect(url_for("records"))

@app.post("/records/<int:record_id>/delete")
def delete_record(record_id):
    with get_db() as conn:
        conn.execute("DELETE FROM assessments WHERE id=?", (record_id,))
    flash("Record deleted from this local demo database.", "success")
    return redirect(url_for("records"))

@app.route("/about")
def about():
    return render_template("about.html")

init_db()

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
