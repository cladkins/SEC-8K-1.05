"""Flask GUI for the EDGAR 8-K Item 1.05 scraper.

Thin wrapper around edgar8k.py — submitting the form runs the same
collect_filings/write_csv/write_markdown pipeline as the CLI and the
daily GitHub Action, just driven from a browser. No Selenium, no
browser dependency.
"""

from __future__ import annotations

import logging
import os
import threading
from datetime import date, datetime, timedelta
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file

from edgar8k import (
    DEFAULT_FORMS,
    DEFAULT_QUERY,
    DEFAULT_USER_AGENT,
    build_client,
    hit_to_filing,
    render_markdown,
    search_filings,
    write_csv,
    write_markdown,
)

logger = logging.getLogger("edgar8k.web")

OUTPUT_DIR = Path(os.environ.get("EDGAR_OUTPUT_DIR", "results"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)

_lock = threading.Lock()
_status: dict = {
    "running": False,
    "progress": 0,
    "total": 0,
    "current_task": "Idle",
    "error": None,
    "completed": False,
    "results": None,
    "last_run": None,
    "csv_path": None,
    "md_path": None,
}


def _reset_status() -> None:
    _status.update(
        running=True,
        progress=0,
        total=0,
        current_task="Starting…",
        error=None,
        completed=False,
        results=None,
    )


def _update(**kwargs) -> None:
    _status.update(kwargs)


def _scrape_thread(params: dict) -> None:
    """Background worker. Mirrors edgar8k.collect_filings + outputs."""
    try:
        end_date = params.get("end") or date.today()
        days = int(params.get("days", 30))
        start_date = params.get("start") or (end_date - timedelta(days=days))
        user_agent = (os.environ.get("SEC_USER_AGENT") or DEFAULT_USER_AGENT).strip()
        require_item = (params.get("require_item") or "").strip() or None

        _update(current_task=f"Searching EDGAR ({start_date}..{end_date})…")

        with build_client(user_agent) as client:
            hits = search_filings(
                client,
                query=params["query"],
                forms=params["forms"],
                start_date=start_date,
                end_date=end_date,
                require_item=require_item,
            )
            _update(total=len(hits), current_task=f"Found {len(hits)} filings")

            filings = []
            for i, hit in enumerate(hits, 1):
                _update(progress=i, current_task=f"Processing filing {i}/{len(hits)}")
                filing = hit_to_filing(hit, client)
                if filing:
                    filings.append(filing)

        stamp = datetime.now().strftime("%Y-%m-%d")
        csv_path = OUTPUT_DIR / f"{stamp}.csv"
        md_path = OUTPUT_DIR / f"{stamp}.md"
        write_csv(filings, csv_path)
        write_markdown(
            filings,
            md_path,
            start_date=start_date,
            end_date=end_date,
            query=params["query"],
        )
        # Refresh rolling "latest" copies.
        (OUTPUT_DIR / "latest.csv").write_bytes(csv_path.read_bytes())
        (OUTPUT_DIR / "latest.md").write_bytes(md_path.read_bytes())

        _update(
            results=[f.to_row() for f in filings],
            csv_path=str(csv_path),
            md_path=str(md_path),
            completed=True,
            running=False,
            last_run=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            current_task=f"Done — {len(filings)} filings",
        )
    except Exception as e:
        logger.exception("Scrape failed")
        _update(error=str(e), running=False, current_task="Error")


@app.route("/")
def index():
    return render_template("index.html")


@app.post("/api/start")
def api_start():
    with _lock:
        if _status["running"]:
            return jsonify({"error": "A scrape is already in progress"}), 409
        payload = request.get_json(silent=True) or request.form.to_dict()
        params = {
            "query": (payload.get("query") or DEFAULT_QUERY).strip() or DEFAULT_QUERY,
            "forms": (payload.get("forms") or DEFAULT_FORMS).strip() or DEFAULT_FORMS,
            "days": int(payload.get("days") or 30),
            "require_item": payload.get("require_item") if "require_item" in payload else payload.get("requireItem"),
        }
        _reset_status()
        threading.Thread(target=_scrape_thread, args=(params,), daemon=True).start()
    return jsonify({"message": "Scrape started", "params": params})


@app.get("/api/status")
def api_status():
    return jsonify(_status)


@app.get("/api/download/csv")
def download_csv():
    path = OUTPUT_DIR / "latest.csv"
    if not path.exists():
        return jsonify({"error": "No results yet"}), 404
    return send_file(path, as_attachment=True, download_name="edgar-8k-1.05.csv")


@app.get("/api/download/md")
def download_md():
    path = OUTPUT_DIR / "latest.md"
    if not path.exists():
        return jsonify({"error": "No results yet"}), 404
    return send_file(path, as_attachment=True, download_name="edgar-8k-1.05.md")


@app.get("/healthz")
def healthz():
    return jsonify({"ok": True})


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)
