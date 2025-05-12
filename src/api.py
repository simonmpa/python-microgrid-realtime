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


@app.route("/delete-db", methods=["DELETE"])
def delete_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM microgrids")
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"message": "Database cleared!"}), 200


@app.route("/schedule-job", methods=["POST"])
def schedule_job():
    body = request.get_json()

    if (
        not body
        or "Node" not in body
        or "CPU" not in body
        or "Completed_at" not in body
    ):
        missing = []
        if not body:
            missing.append("body")
        else:
            if "Node" not in body:
                missing.append("Node")
            if "CPU" not in body:
                missing.append("CPU")
            if "Completed_at" not in body:
                missing.append("Completed_at")

        return jsonify({"error": f"Missing field(s): {', '.join(missing)}"}), 400

    try:
        completed_at_dt = datetime.fromisoformat(body["Completed_at"])
    except ValueError:
        return (
            jsonify(
                {
                    "error": "Invalid datetime format for Completed_at. Expected ISO 8601 format like '2025-04-22T10:05:47'."
                }
            ),
            400,
        )

    # Format it to 'YYYY-MM-DD HH:MM:SS' string
    completed_at_str = completed_at_dt.strftime("%Y-%m-%d %H:%M:%S")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO microgrids (Node, CPU, Completed_at) VALUES (?, ?, ?)",
        (body["Node"].upper(), body["CPU"], completed_at_str),
    )
    cursor.close()
    conn.commit()
    conn.close()

    return jsonify({"message": "Scheduled!"}), 201
