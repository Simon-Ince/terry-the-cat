from flask import Flask, jsonify, request, redirect, render_template, send_from_directory, send_file, session
import io
import os
import sys
import logging
import time as time_module
from datetime import datetime, timezone

import psycopg2
from psycopg2 import OperationalError
from psycopg2.extras import RealDictCursor
from flask_wtf.csrf import CSRFProtect

from config import DATABASE_URL, SECRET_KEY

app = Flask(__name__)
app.config["SECRET_KEY"] = SECRET_KEY
CSRFProtect(app)

# Ensure errors are visible in Railway logs
logging.basicConfig(stream=sys.stderr, level=logging.INFO)
logger = logging.getLogger(__name__)

# Store last DB error for the debug page (in-memory, per process)
_last_db_error = None
_last_db_error_at = None

# Rate limit: 10 POSTs per minute per IP (in-memory)
_rate_limit_store = {}  # ip -> [timestamp, ...]
RATE_LIMIT_MAX = 10
RATE_LIMIT_WINDOW_SEC = 60

# Duplicate guard: same "what" within this many seconds = duplicate
DUPLICATE_WINDOW_SEC = 300  # 5 minutes

# Input limit for "what"
WHAT_MAX_LENGTH = 200

# DB retries
DB_RETRIES = 3
DB_RETRY_DELAY_SEC = 0.5

INIT_SQL = """
CREATE TABLE IF NOT EXISTS feedings (
    id SERIAL PRIMARY KEY,
    fed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    what TEXT NOT NULL
);
"""
# Add fed_by if missing (migration)
ALTER_FED_BY_SQL = "ALTER TABLE feedings ADD COLUMN fed_by TEXT;"


def _set_last_error(e):
    global _last_db_error, _last_db_error_at
    _last_db_error = str(e)
    _last_db_error_at = time_module.time()


def _retry_db(fn, *args, **kwargs):
    """Run a DB call with up to DB_RETRIES attempts on OperationalError."""
    last_err = None
    for attempt in range(DB_RETRIES):
        try:
            return fn(*args, **kwargs)
        except OperationalError as e:
            last_err = e
            if attempt < DB_RETRIES - 1:
                time_module.sleep(DB_RETRY_DELAY_SEC)
    raise last_err


def get_db_connection():
    """Return a database connection. Railway and Docker Compose set DATABASE_URL."""
    return psycopg2.connect(DATABASE_URL)


def _relative_time(dt):
    """Return human-readable relative time, e.g. '2 hours ago', 'just now'."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    delta_sec = (now - dt).total_seconds()
    if delta_sec < 0:
        return "just now"
    if delta_sec < 60:
        return "just now"
    if delta_sec < 3600:
        m = int(delta_sec / 60)
        return f"{m} min ago" if m == 1 else f"{m} min ago"
    if delta_sec < 86400:
        h = int(delta_sec / 3600)
        return "1 hour ago" if h == 1 else f"{h} hours ago"
    if delta_sec < 604800:
        d = int(delta_sec / 86400)
        return "1 day ago" if d == 1 else f"{d} days ago"
    if delta_sec < 2592000:
        w = int(delta_sec / 604800)
        return "1 week ago" if w == 1 else f"{w} weeks ago"
    return dt.strftime("%d %b")


def init_db():
    """Create feedings table and run migrations if needed."""
    def _init():
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(INIT_SQL)
        conn.commit()
        try:
            cur.execute(ALTER_FED_BY_SQL)
            conn.commit()
        except Exception as e:
            if "already exists" not in str(e).lower() and "duplicate_column" not in str(e).lower():
                raise
            conn.rollback()
        cur.close()
        conn.close()

    try:
        _retry_db(_init)
    except OperationalError as e:
        _set_last_error(e)
        logger.exception("init_db failed")


def get_recent_feedings(limit=20):
    """Return the most recent feedings, or empty list if DB unavailable."""
    def _query():
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            "SELECT id, fed_at, what, fed_by FROM feedings ORDER BY fed_at DESC LIMIT %s",
            (limit,),
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(r) for r in rows]

    try:
        return _retry_db(_query)
    except OperationalError as e:
        _set_last_error(e)
        logger.exception("get_recent_feedings failed")
        return []


def get_last_fed():
    """Return the single most recent feeding, or None."""
    feedings = get_recent_feedings(limit=1)
    return feedings[0] if feedings else None


def get_feed_count_today():
    """Return number of feedings in the last 24 hours."""
    def _query():
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) AS n FROM feedings WHERE fed_at > NOW() - INTERVAL '24 hours'"
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        return row[0] if row else 0

    try:
        return _retry_db(_query)
    except OperationalError as e:
        _set_last_error(e)
        logger.exception("get_feed_count_today failed")
        return None


def get_feed_count_this_week():
    """Return number of feedings in the last 7 days."""
    def _query():
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) AS n FROM feedings WHERE fed_at > NOW() - INTERVAL '7 days'"
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        return row[0] if row else 0

    try:
        return _retry_db(_query)
    except OperationalError as e:
        _set_last_error(e)
        logger.exception("get_feed_count_this_week failed")
        return None


def get_feedings_per_day_this_week():
    """Return list of {date, count} for last 7 days (UTC date)."""
    def _query():
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """
            SELECT DATE(fed_at) AS day, COUNT(*) AS n
            FROM feedings
            WHERE fed_at > NOW() - INTERVAL '7 days'
            GROUP BY DATE(fed_at)
            ORDER BY day
            """
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(r) for r in rows]

    try:
        return _retry_db(_query)
    except OperationalError as e:
        _set_last_error(e)
        logger.exception("get_feedings_per_day_this_week failed")
        return []


def get_most_common_foods_this_month(limit=15):
    """Return list of {what, count} for last 30 days, normalized (lowercased)."""
    def _query():
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """
            SELECT LOWER(TRIM(what)) AS what, COUNT(*) AS n
            FROM feedings
            WHERE fed_at > NOW() - INTERVAL '30 days'
            GROUP BY LOWER(TRIM(what))
            ORDER BY n DESC
            LIMIT %s
            """,
            (limit,),
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(r) for r in rows]

    try:
        return _retry_db(_query)
    except OperationalError as e:
        _set_last_error(e)
        logger.exception("get_most_common_foods_this_month failed")
        return []


def has_duplicate_recent(what_normalized):
    """True if the same 'what' was logged in the last DUPLICATE_WINDOW_SEC."""
    def _query():
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT 1 FROM feedings
            WHERE LOWER(TRIM(what)) = LOWER(%s)
              AND fed_at > NOW() - INTERVAL '1 second' * %s
            LIMIT 1
            """,
            (what_normalized, DUPLICATE_WINDOW_SEC),
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        return row is not None

    try:
        return _retry_db(_query)
    except OperationalError:
        return False


def _rate_limit_check(ip):
    """Return True if this IP is over the rate limit."""
    now = time_module.time()
    if ip not in _rate_limit_store:
        _rate_limit_store[ip] = []
    times = _rate_limit_store[ip]
    # Prune old
    times[:] = [t for t in times if now - t < RATE_LIMIT_WINDOW_SEC]
    if len(times) >= RATE_LIMIT_MAX:
        return True
    times.append(now)
    return False


def _sanitize_what(s):
    """Trim and cap length; return None if empty."""
    if s is None:
        return None
    s = " ".join(s.strip().split())  # trim and collapse internal whitespace
    if not s:
        return None
    return s[:WHAT_MAX_LENGTH] if len(s) > WHAT_MAX_LENGTH else s


@app.route("/")
def index():
    init_db()
    last = get_last_fed()
    recent = get_recent_feedings()
    feed_count_today = get_feed_count_today()
    feed_count_week = get_feed_count_this_week()
    show_db_error = request.args.get("db_error") == "1"
    show_duplicate = request.args.get("duplicate") == "1"
    show_rate_limit = request.args.get("rate_limit") == "1"
    undo_feed_id = session.get("undo_feed_id")
    # Add relative time and exact time for template
    if last:
        last["relative_time"] = _relative_time(last["fed_at"])
        last["fed_by_display"] = (last.get("fed_by") or "").strip() or "Anonymous"
    for f in recent:
        f["relative_time"] = _relative_time(f["fed_at"])
        f["fed_by_display"] = (f.get("fed_by") or "").strip() or "Anonymous"
    return render_template(
        "index.html",
        last_fed=last,
        feedings=recent,
        feed_count_today=feed_count_today,
        feed_count_week=feed_count_week,
        show_db_error=show_db_error,
        show_duplicate=show_duplicate,
        show_rate_limit=show_rate_limit,
        undo_feed_id=undo_feed_id,
    )


@app.route("/feed", methods=["POST"])
def feed():
    init_db()
    # Rate limit
    ip = request.remote_addr or "unknown"
    if _rate_limit_check(ip):
        return redirect("/?rate_limit=1")

    what = _sanitize_what(request.form.get("what"))
    fed_by = (request.form.get("fed_by") or "").strip() or None
    if fed_by:
        fed_by = fed_by[:100]  # cap optional name

    if not what:
        return redirect("/")

    # Duplicate guard
    if has_duplicate_recent(what):
        return redirect("/?duplicate=1")

    def _insert():
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO feedings (what, fed_by) VALUES (%s, %s) RETURNING id",
            (what, fed_by),
        )
        row = cur.fetchone()
        conn.commit()
        fid = row[0] if row else None
        cur.close()
        conn.close()
        return fid

    try:
        feed_id = _retry_db(_insert)
        global _last_db_error, _last_db_error_at
        _last_db_error = None
        _last_db_error_at = None
        if feed_id is not None:
            session["undo_feed_id"] = feed_id
    except OperationalError as e:
        _set_last_error(e)
        logger.exception("feed INSERT failed")
        return redirect("/?db_error=1")
    return redirect("/")


@app.route("/undo", methods=["POST"])
def undo():
    """Remove the last feeding (only if it matches session undo_feed_id)."""
    undo_id = session.get("undo_feed_id")
    if not undo_id:
        return redirect("/")
    try:
        req_id = request.form.get("undo_id", type=int)
    except (TypeError, ValueError):
        return redirect("/")
    if req_id != undo_id:
        return redirect("/")
    session.pop("undo_feed_id", None)
    init_db()

    def _delete():
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM feedings WHERE id = %s", (undo_id,))
        conn.commit()
        cur.close()
        conn.close()

    try:
        _retry_db(_delete)
    except OperationalError as e:
        _set_last_error(e)
        logger.exception("undo DELETE failed")
    return redirect("/")


@app.route("/api/feedings")
def api_feedings():
    """JSON list of recent feedings."""
    init_db()
    limit = min(int(request.args.get("limit", 20)), 100)
    feedings = get_recent_feedings(limit=limit)
    for f in feedings:
        f["fed_at"] = f["fed_at"].isoformat()
        f["fed_by"] = f.get("fed_by")
    return jsonify({"feedings": feedings})


@app.route("/api/last")
def api_last():
    """JSON for the most recent feeding."""
    init_db()
    last = get_last_fed()
    if not last:
        return jsonify({"last_fed": None})
    last["fed_at"] = last["fed_at"].isoformat()
    last["fed_by"] = last.get("fed_by")
    return jsonify({"last_fed": last})


@app.route("/qr")
def qr():
    """Serve a QR code image pointing at this app's URL."""
    import qrcode
    url = request.url_root.rstrip("/") or request.host_url.rstrip("/")
    img = qrcode.make(url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png", download_name="terry-qr.png")


@app.route("/share")
def share():
    """Page with QR code and link for posters/flyers."""
    app_url = request.url_root.rstrip("/") or request.host_url.rstrip("/")
    return render_template("share.html", app_url=app_url)


@app.route("/stats")
def stats():
    """Simple stats: feedings per day this week, most common foods this month."""
    init_db()
    per_day = get_feedings_per_day_this_week()
    top_foods = get_most_common_foods_this_month()
    for row in per_day:
        row["day_str"] = row["day"].strftime("%a %d %b") if hasattr(row["day"], "strftime") else str(row["day"])
    max_per_day = max((row["n"] for row in per_day), default=1)
    return render_template("stats.html", per_day=per_day, top_foods=top_foods, max_per_day=max_per_day)


@app.route("/sw.js")
def service_worker():
    """Serve service worker at root so scope can be / for PWA."""
    return send_from_directory(app.static_folder, "sw.js", mimetype="application/javascript")


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
    m = re.match(r"(postgresql://[^:]+:)([^@]+)(@.+)", url)
    if m:
        return m.group(1) + "****" + m.group(3)
    return url


@app.route("/debug")
def debug():
    """Debug page: DB status, last error, env hints."""
    init_db()
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

    feed_count_today = get_feed_count_today()
    feed_count_week = get_feed_count_this_week()

    import time as _time
    global _last_db_error, _last_db_error_at
    last_error_at_str = None
    if _last_db_error_at:
        last_error_at_str = _time.strftime(
            "%Y-%m-%d %H:%M:%S UTC",
            _time.gmtime(_last_db_error_at),
        )
    has_railway = bool(os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_PROJECT_ID"))
    database_points_to_localhost = (
        DATABASE_URL is not None
        and ("localhost" in DATABASE_URL or "127.0.0.1" in DATABASE_URL)
    )
    return render_template(
        "debug.html",
        db_configured=db_configured,
        db_connected=db_connected,
        db_error=db_error,
        last_db_error=_last_db_error,
        last_db_error_at=last_error_at_str,
        database_url_redacted=_redact_url(DATABASE_URL),
        has_railway=has_railway,
        database_points_to_localhost=database_points_to_localhost,
        port=os.getenv("PORT", "not set"),
        feed_count_today=feed_count_today,
        feed_count_week=feed_count_week,
    )


if __name__ == "__main__":
    app.run(debug=True, port=os.getenv("PORT", default=5000))
