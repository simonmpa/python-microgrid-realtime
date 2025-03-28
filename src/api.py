from flask import Flask, jsonify, request, g
import sqlite3

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

    if not body or "Gridname" not in body or "Load" not in body:
        return jsonify({"error": "Missing Gridname or Load"}), 400

    print(body)

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO microgrids (Gridname, Load) VALUES (?, ?)", (body["Gridname"], body["Load"])
    )
    cursor.close()
    conn.commit()
    conn.close()

    return jsonify({"message": "Scheduled!"}), 201