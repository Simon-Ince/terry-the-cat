from flask import Flask, jsonify, request, redirect, render_template
import os
import sys
import logging
import psycopg2
from psycopg2 import OperationalError
from psycopg2.extras import RealDictCursor

from config import DATABASE_URL

app = Flask(__name__)

# Ensure errors are visible in Railway logs
logging.basicConfig(stream=sys.stderr, level=logging.INFO)
logger = logging.getLogger(__name__)

# Store last DB error for the debug page (in-memory, per process)
_last_db_error = None
_last_db_error_at = None

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


def _set_last_error(e):
    global _last_db_error, _last_db_error_at
    import time
    _last_db_error = str(e)
    _last_db_error_at = time.time()


def init_db():
    """Create feedings table if it doesn't exist."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(INIT_SQL)
        conn.commit()
        cur.close()
        conn.close()
    except OperationalError as e:
        _set_last_error(e)
        logger.exception("init_db failed")


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
    except OperationalError as e:
        _set_last_error(e)
        logger.exception("get_recent_feedings failed")
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
    show_db_error = request.args.get("db_error") == "1"
    return render_template(
        "index.html",
        last_fed=last,
        feedings=recent,
        show_db_error=show_db_error,
    )


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
        global _last_db_error, _last_db_error_at
        _last_db_error = None
        _last_db_error_at = None
    except OperationalError as e:
        _set_last_error(e)
        logger.exception("feed INSERT failed")
        return redirect("/?db_error=1")
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


def _redact_url(url):
    """Hide password in DATABASE_URL for debug output."""
    if not url:
        return None
    import re
    # Replace password in postgresql://user:password@host:port/db
    m = re.match(r"(postgresql://[^:]+:)([^@]+)(@.+)", url)
    if m:
        return m.group(1) + "****" + m.group(3)
    return url


@app.route("/debug")
def debug():
    """Debug page: DB status, last error, env hints."""
    db_configured = bool(DATABASE_URL)
    db_connected = False
    db_error = None
    try:
        if DATABASE_URL:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.fetchone()
            cur.close()
            conn.close()
            db_connected = True
    except OperationalError as e:
        db_error = str(e)
        _set_last_error(e)

    import time as _time
    global _last_db_error, _last_db_error_at
    last_error_at_str = None
    if _last_db_error_at:
        last_error_at_str = _time.strftime(
            "%Y-%m-%d %H:%M:%S UTC",
            _time.gmtime(_last_db_error_at),
        )
    return render_template(
        "debug.html",
        db_configured=db_configured,
        db_connected=db_connected,
        db_error=db_error,
        last_db_error=_last_db_error,
        last_db_error_at=last_error_at_str,
        database_url_redacted=_redact_url(DATABASE_URL),
        has_railway=bool(os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_PROJECT_ID")),
        port=os.getenv("PORT", "not set"),
    )


if __name__ == "__main__":
    app.run(debug=True, port=os.getenv("PORT", default=5000))
