from flask import Flask, jsonify
import os
import psycopg2
from psycopg2 import OperationalError

from config import DATABASE_URL

app = Flask(__name__)


def get_db_connection():
    """Return a database connection. Railway and Docker Compose set DATABASE_URL."""
    return psycopg2.connect(DATABASE_URL)


@app.route('/')
def index():
    return jsonify({"Choo Choo": "Welcome to your Flask app 🚅"})


@app.route('/health')
def health():
    """Check app and database connectivity."""
    try:
        if DATABASE_URL:
            conn = get_db_connection()
            conn.close()
            return jsonify({"status": "ok", "database": "connected"})
    except OperationalError:
        return jsonify({"status": "ok", "database": "disconnected"}), 503
    return jsonify({"status": "ok", "database": "not configured"})


if __name__ == '__main__':
    app.run(debug=True, port=os.getenv("PORT", default=5000))
