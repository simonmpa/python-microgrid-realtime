from flask import Flask, jsonify
import shared_state  # Import the shared state module

app = Flask(__name__)

@app.route("/soc", methods=["GET"])
def soc():
    return jsonify(shared_state.state_of_charge)