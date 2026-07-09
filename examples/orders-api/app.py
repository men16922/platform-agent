"""orders-api — minimal service for platform-agent deployment demo."""

import os
import socket
from flask import Flask, jsonify

app = Flask(__name__)

VERSION = os.getenv("APP_VERSION", "v1.4.2")
ENV = os.getenv("APP_ENV", "production")


@app.route("/healthz")
def healthz():
    return jsonify({"status": "ok", "version": VERSION})


@app.route("/id")
def identity():
    return jsonify({
        "service": "orders-api",
        "version": VERSION,
        "env": ENV,
        "hostname": socket.gethostname(),
    })


@app.route("/")
def root():
    return jsonify({"service": "orders-api", "version": VERSION, "status": "running"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
