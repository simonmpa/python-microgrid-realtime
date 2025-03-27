import requests
import datetime
from flask import Flask, jsonify, request

app = Flask(__name__)


@app.route("/soc", methods=["GET"])
def soc():
    if hasattr(g, "state_of_charge"):
        return jsonify(g.state_of_charge)
    else:
        return jsonify([])
