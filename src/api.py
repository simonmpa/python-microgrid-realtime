from flask import Flask, jsonify, request

app = Flask(__name__)

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