from flask import Flask, jsonify, request, redirect, render_template
import os
import psycopg2
from psycopg2 import OperationalError
from psycopg2.extras import RealDictCursor

from config import DATABASE_URL

app = Flask(__name__)

INIT_SQL = """
CREATE TABLE IF NOT EXISTS feedings (
    id SERIAL PRIMARY KEY,
    fed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    what TEXT NOT NULL
);
"""


def get_db_connection():
    """Return a database connection. Railway and Docker Compose set DATABASE_URL."""
    return psycopg2.connect(DATABASE_URL)


def init_db():
    """Create feedings table if it doesn't exist."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(INIT_SQL)
        conn.commit()
        cur.close()
        conn.close()
    except OperationalError:
        pass  # No DB in dev or health check will show it


def get_recent_feedings(limit=20):
    """Return the most recent feedings, or empty list if DB unavailable."""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            "SELECT id, fed_at, what FROM feedings ORDER BY fed_at DESC LIMIT %s",
            (limit,),
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(r) for r in rows]
    except OperationalError:
        return []


def get_last_fed():
    """Return the single most recent feeding, or None."""
    feedings = get_recent_feedings(limit=1)
    return feedings[0] if feedings else None


@app.route("/")
def index():
    init_db()
    last = get_last_fed()
    recent = get_recent_feedings()
    return render_template("index.html", last_fed=last, feedings=recent)


@app.route("/feed", methods=["POST"])
def feed():
    init_db()
    what = (request.form.get("what") or "").strip()
    if not what:
        return redirect("/")
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO feedings (what) VALUES (%s)", (what,))
        conn.commit()
        cur.close()
        conn.close()
    except OperationalError:
        pass  # Redirect home anyway; user can retry
    return redirect("/")


@app.route("/api/feedings")
def api_feedings():
    """JSON list of recent feedings."""
    init_db()
    limit = min(int(request.args.get("limit", 20)), 100)
    feedings = get_recent_feedings(limit=limit)
    for f in feedings:
        f["fed_at"] = f["fed_at"].isoformat()
    return jsonify({"feedings": feedings})


@app.route("/api/last")
def api_last():
    """JSON for the most recent feeding."""
    init_db()
    last = get_last_fed()
    if not last:
        return jsonify({"last_fed": None})
    last["fed_at"] = last["fed_at"].isoformat()
    return jsonify({"last_fed": last})


@app.route("/health")
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


if __name__ == "__main__":
    app.run(debug=True, port=os.getenv("PORT", default=5000))
