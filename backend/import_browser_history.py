"""
import_browser_history.py
=========================
Reads Chrome / Edge browsing history from the local SQLite database and
imports each entry into DMRE by POSTing to POST /api/memories.

Usage (run from backend/ with .venv active):
    .venv\\Scripts\\python.exe import_browser_history.py
    .venv\\Scripts\\python.exe import_browser_history.py --browser edge --limit 500

Options:
    --browser   chrome | edge  (default: chrome)
    --limit     max URLs to import (default: 1000, newest first)
    --backend   backend URL (default: http://localhost:8000)
"""

import argparse
import shutil
import sqlite3
import tempfile
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

# Chrome/Edge store time as microseconds since 1601-01-01 (Windows FILETIME epoch)
CHROME_EPOCH = datetime(1601, 1, 1, tzinfo=timezone.utc)

HISTORY_PATHS = {
    "chrome": [
        Path.home() / "AppData/Local/Google/Chrome/User Data/Default/History",
        Path.home() / "AppData/Local/Google/Chrome Beta/User Data/Default/History",
    ],
    "edge": [
        Path.home() / "AppData/Local/Microsoft/Edge/User Data/Default/History",
    ],
}


def chrome_time_to_datetime(microseconds: int) -> datetime:
    return CHROME_EPOCH + timedelta(microseconds=microseconds)


def find_history_db(browser: str) -> Path:
    for path in HISTORY_PATHS.get(browser, []):
        if path.exists():
            return path
    raise FileNotFoundError(
        f"Could not find {browser} history database.\n"
        f"Looked in: {[str(p) for p in HISTORY_PATHS.get(browser, [])]}"
    )


def read_history(db_path: Path, limit: int) -> list[dict]:
    """Copy the DB to a temp file (browser may have it locked) and read it."""
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    shutil.copy2(db_path, tmp_path)

    try:
        conn = sqlite3.connect(str(tmp_path))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            """
            SELECT u.url,
                   u.title,
                   u.visit_count,
                   u.last_visit_time
            FROM   urls u
            WHERE  u.hidden = 0
              AND  u.url LIKE 'http%'
            ORDER  BY u.last_visit_time DESC
            LIMIT  ?
            """,
            (limit,),
        )
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows
    finally:
        tmp_path.unlink(missing_ok=True)


def import_entry(entry: dict, backend_url: str) -> bool:
    visited_at = chrome_time_to_datetime(entry["last_visit_time"])
    payload = {
        "url":         entry["url"],
        "title":       entry["title"] or "",
        "page_text":   "",          # no live fetch — title-only indexing
        "visited_at":  visited_at.isoformat(),
        "visit_count": max(1, entry["visit_count"]),
        "dwell_time":  0.0,
        "click_count": 0,
        "scroll_depth": 0.0,
    }
    try:
        r = requests.post(f"{backend_url}/api/memories", json=payload, timeout=10)
        return r.status_code in (200, 201)
    except Exception as exc:
        print(f"  ✗ network error: {exc}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Import browser history into DMRE")
    parser.add_argument("--browser", default="chrome", choices=["chrome", "edge"])
    parser.add_argument("--limit",   default=1000, type=int)
    parser.add_argument("--backend", default="http://localhost:8000")
    args = parser.parse_args()

    print(f"Looking for {args.browser} history…")
    db_path = find_history_db(args.browser)
    print(f"Found: {db_path}")

    entries = read_history(db_path, args.limit)
    print(f"Read {len(entries)} URLs from history. Starting import…\n")

    ok = fail = skip = 0
    for i, entry in enumerate(entries, 1):
        url = entry["url"]

        # Skip search engine results pages and common noise URLs
        if any(s in url for s in ["google.com/search", "bing.com/search", "localhost", "127.0.0.1"]):
            skip += 1
            continue

        success = import_entry(entry, args.backend)
        if success:
            ok += 1
            status = "✓"
        else:
            fail += 1
            status = "✗"

        title = (entry["title"] or url)[:60]
        print(f"  [{i:4d}] {status} {title}")

        # Rate-limit: 10 requests/sec to avoid overwhelming the backend
        time.sleep(0.1)

    print(f"\nDone. Imported: {ok}  Failed: {fail}  Skipped: {skip}")


if __name__ == "__main__":
    main()
