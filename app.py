"""
app.py
Flask Media Downloader with:
- yt-dlp backend (video/audio)
- SQLite logging
- Direct push-to-browser downloads
- Dashboard + Re-download feature
- Auto-clean expired files
"""
import os
import threading
import time
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from flask import Flask, request, render_template, send_file, abort, flash, redirect, url_for

from downloader.yt_dlp_downloader import download_with_ytdlp, MAX_FILE_SIZE_BYTES

# --- Config ---
BASE_DIR = Path(__file__).resolve().parent
DOWNLOADS_DIR = BASE_DIR / "downloads"
DB_PATH = BASE_DIR / "downloads.db"
ALLOWED_HOSTS = {
    "youtube.com", "youtu.be", "instagram.com", "tiktok.com", "x.com",
    "twitter.com", "facebook.com", "fb.watch", "vimeo.com", "reddit.com"
}

DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
app.secret_key = "supersecret"
app.config.update(DOWNLOADS_DIR=str(DOWNLOADS_DIR), DB_PATH=str(DB_PATH))


# --- DB helpers ---
def get_conn():
    conn = sqlite3.connect(str(DB_PATH), detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS downloads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                filename TEXT NOT NULL,
                filepath TEXT NOT NULL,
                created_at TEXT NOT NULL,
                auto_clean_hours INTEGER DEFAULT 0,
                expires_at TEXT,
                status TEXT DEFAULT 'ready',
                error TEXT,
                mode TEXT DEFAULT 'video'
            )
        """)
        conn.commit()


init_db()


def add_record(url, filename, filepath, mode="video", hours=0, status="ready", error=None):
    created = datetime.utcnow().isoformat()
    expires = None
    if hours and int(hours) > 0:
        expires = (datetime.utcnow() + timedelta(hours=int(hours))).isoformat()
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO downloads (url, filename, filepath, created_at, auto_clean_hours, expires_at, status, error, mode) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (url, filename, filepath, created, int(hours or 0), expires, status, error, mode)
        )
        conn.commit()
        return cur.lastrowid


def list_records(limit=500):
    with get_conn() as conn:
        cur = conn.execute("SELECT * FROM downloads ORDER BY id DESC LIMIT ?", (limit,))
        return cur.fetchall()


def fetch_record(db_id):
    with get_conn() as conn:
        cur = conn.execute("SELECT * FROM downloads WHERE id=?", (db_id,))
        return cur.fetchone()


def update_status(db_id, status, error=None):
    with get_conn() as conn:
        conn.execute("UPDATE downloads SET status=?, error=? WHERE id=?", (status, error, db_id))
        conn.commit()


# --- Cleaner thread ---
def cleaner_loop(interval_seconds=60):
    while True:
        try:
            now = datetime.utcnow().isoformat()
            with get_conn() as conn:
                rows = conn.execute(
                    "SELECT id, filepath FROM downloads WHERE expires_at IS NOT NULL AND expires_at <= ? AND status='ready'",
                    (now,)
                ).fetchall()
                for r in rows:
                    db_id = r["id"]
                    path = Path(r["filepath"])
                    try:
                        if path.exists():
                            path.unlink()
                        update_status(db_id, "deleted")
                        app.logger.info(f"Auto-deleted expired file id={db_id} path={path}")
                    except Exception as e:
                        app.logger.exception("Cleaner error removing file: %s", e)
        except Exception:
            app.logger.exception("Cleaner loop error")
        time.sleep(interval_seconds)


threading.Thread(target=cleaner_loop, daemon=True).start()


# --- Helpers ---
def is_allowed_url(url: str) -> bool:
    try:
        from urllib.parse import urlparse
        netloc = urlparse(url).netloc.lower()
        return any(host in netloc for host in ALLOWED_HOSTS)
    except Exception:
        return False


# --- Routes ---
@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/download", methods=["POST"])
def download_endpoint():
    """Directly download and push to browser download bar + log"""
    url = request.form.get("url")
    mode = (request.form.get("mode") or "video").lower()
    try:
        auto_clean_hours = int(request.form.get("auto_clean_hours") or 0)
    except Exception:
        auto_clean_hours = 0

    if not url:
        flash("Missing URL")
        return redirect(url_for("index"))
    if not is_allowed_url(url):
        flash("Host not allowed")
        return redirect(url_for("index"))

    try:
        result = download_with_ytdlp(url, str(DOWNLOADS_DIR), mode=mode)
        filepath = result["filepath"]
        filename = result["filename"]

        if MAX_FILE_SIZE_BYTES is not None and os.path.getsize(filepath) > MAX_FILE_SIZE_BYTES:
            os.remove(filepath)
            flash("File too large")
            return redirect(url_for("index"))

        add_record(url, filename, filepath, mode=mode, hours=auto_clean_hours, status="ready")

        return send_file(
            filepath,
            as_attachment=True,
            download_name=filename,
            mimetype="video/mp4"
        )

    except Exception as e:
        flash(f"Download failed: {str(e)}")
        return redirect(url_for("index"))


@app.route("/dashboard", methods=["GET"])
def dashboard():
    logs = list_records(500)
    return render_template("dashboard.html", logs=logs)


@app.route("/redownload/<int:download_id>", methods=["GET"])
def redownload(download_id):
    """Re-download a file from its original URL"""
    row = fetch_record(download_id)
    if not row:
        flash("Record not found")
        return redirect(url_for("dashboard"))

    url = row["url"]
    mode = row["mode"]
    try:
        result = download_with_ytdlp(url, str(DOWNLOADS_DIR), mode=mode)
        filepath = result["filepath"]
        filename = result["filename"]

        add_record(url, filename, filepath, mode=mode, status="ready")

        return send_file(filepath, as_attachment=True, download_name=filename)
    except Exception as e:
        flash(f"Re-download failed: {str(e)}")
        return redirect(url_for("dashboard"))


# ---- Run ----
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
