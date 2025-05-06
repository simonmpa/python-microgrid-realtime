from flask import Flask, jsonify, request, g
import sqlite3
from datetime import datetime

app = Flask(__name__)

conn = sqlite3.connect("database.db")

state_object = None


@app.route("/soc", methods=["GET"])
def soc():
    if state_object is None:
        return jsonify({"error": "No data available"}), 404
    return jsonify({"state": state_object})

@app.route("/insert", methods=["POST"])
def insert():
    global state_object
    if not request.json or "data" not in request.json:
        return jsonify({"error": "Invalid request"}), 400

    state_object = request.json["data"]
    return jsonify({"message": "Inserted!"}), 201

@app.route("/schedule-job", methods=["POST"])
def schedule_job():
    body = request.get_json()

    if not body or "Gridname" not in body or "Load" not in body or "Completed_at" not in body:
        missing = []
        if not body:
            missing.append("body")
        else:
            if "Gridname" not in body:
                missing.append("Gridname")
            if "Load" not in body:
                missing.append("Load")
            if "Completed_at" not in body:
                missing.append("Completed_at")

        return jsonify({"error": f"Missing field(s): {', '.join(missing)}"}), 400

    try:
        # Try to parse the input string into a datetime object
        completed_at_dt = datetime.fromisoformat(body["Completed_at"])
    except ValueError:
        return jsonify({"error": "Invalid datetime format for Completed_at. Expected ISO 8601 format like '2025-04-22T10:05:47'."}), 400

    # Format it to 'YYYY-MM-DD HH:MM:SS' string
    completed_at_str = completed_at_dt.strftime("%Y-%m-%d %H:%M:%S")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO microgrids (Gridname, Load, Completed_at) VALUES (?, ?, ?)",
        (body["Gridname"], body["Load"], completed_at_str)
    )
    cursor.close()
    conn.commit()
    conn.close()

    return jsonify({"message": "Scheduled!"}), 201