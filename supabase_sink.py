"""Optional Supabase sink for scrape results.

Upserts rows from a results CSV into the `sec_cyber_incidents` table (keyed on
accession number) so the Cyber Policy Garage /incidents page can read them.
Strictly additive: does nothing unless BOTH SUPABASE_URL and
SUPABASE_SERVICE_ROLE_KEY are set, so CSV/Markdown/email behavior is unchanged
wherever Supabase isn't configured, and a sink failure never fails a scrape
that already produced its files.

Usage:
    python supabase_sink.py results/2026-08-13.csv [more.csv ...]  # CLI / Action
    from supabase_sink import sync_csv                             # Flask GUI
"""

from __future__ import annotations

import csv
import logging
import os
import re
import sys
from pathlib import Path

import httpx

logger = logging.getLogger("edgar8k.supabase")

TABLE = "sec_cyber_incidents"

# .../Archives/edgar/data/<cik>/<18-digit accession, no dashes>/<file>
_ACCESSION_RE = re.compile(r"/edgar/data/\d+/(\d{18})/")
_ENTITY_RE = re.compile(r"^(?P<name>.+?)(?:\s*\((?P<tickers>[^)]+)\))?\s*$")


def _accession_from_link(link: str) -> str | None:
    m = _ACCESSION_RE.search(link or "")
    if not m:
        return None
    raw = m.group(1)
    # EDGAR canonical form: 0001437749-26-009193
    return f"{raw[:10]}-{raw[10:12]}-{raw[12:]}"


def _split_entity(entity: str) -> tuple[str, str | None]:
    m = _ENTITY_RE.match((entity or "").strip())
    if not m:
        return (entity or "").strip(), None
    return m.group("name").strip(), (m.group("tickers") or "").strip() or None


def _date_or_none(value: str) -> str | None:
    value = (value or "").strip()
    return value if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) else None


def _clean_incident_text(value: str) -> str | None:
    # The Item 1.05 extractor slices right after the item header, which can
    # leave leading punctuation like ". Material Cybersecurity Incidents ...".
    return re.sub(r"^[\s.:;,–—-]+", "", (value or "").strip()) or None


def row_to_record(row: dict) -> dict | None:
    accession = _accession_from_link(row.get("Link", ""))
    if not accession:
        # No link means no stable key and no fetched disclosure text - skip.
        return None
    name, tickers = _split_entity(row.get("Filing entity/person", ""))
    return {
        "accession_number": accession,
        "company_name": name,
        "tickers": tickers,
        "cik": re.sub(r"\D", "", row.get("CIK", "")) or None,
        "form": (row.get("Form & File") or "").strip() or None,
        "filed": _date_or_none(row.get("Filed", "")),
        "reporting_for": _date_or_none(row.get("Reporting for", "")),
        "located": (row.get("Located") or "").strip() or None,
        "incorporated": (row.get("Incorporated") or "").strip() or None,
        "file_number": (row.get("File number") or "").strip() or None,
        "film_number": (row.get("Film number") or "").strip() or None,
        "link": row.get("Link") or None,
        "incident_text": _clean_incident_text(row.get("Cybersecurity Incident", "")),
        # Absent in CSVs from before this column existed - None there is
        # correct (unknown), not a false claim of either disclosure type.
        "disclosure_type": (row.get("Disclosure Type") or "").strip() or None,
    }


def sync_csv(csv_path: str | Path) -> int:
    """Upsert one results CSV. Returns rows upserted (0 when disabled/failed)."""
    url = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or ""
    if not url or not key:
        logger.info("Supabase sink disabled (SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set)")
        return 0

    path = Path(csv_path)
    try:
        with path.open(newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
    except OSError as e:
        logger.warning("Supabase sink: cannot read %s: %s", path, e)
        return 0

    # De-dupe within the file (same filing can appear via multiple documents).
    records: dict[str, dict] = {}
    skipped = 0
    for row in rows:
        record = row_to_record(row)
        if record is None:
            skipped += 1
            continue
        records[record["accession_number"]] = record
    if skipped:
        logger.info("Supabase sink: skipped %d row(s) without a filing link", skipped)
    if not records:
        logger.info("Supabase sink: nothing to upsert from %s", path)
        return 0

    try:
        resp = httpx.post(
            f"{url}/rest/v1/{TABLE}",
            params={"on_conflict": "accession_number"},
            headers={
                "apikey": key,
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "Prefer": "resolution=merge-duplicates,return=minimal",
            },
            json=list(records.values()),
            timeout=30.0,
        )
        resp.raise_for_status()
    except httpx.HTTPError as e:
        logger.warning("Supabase sink: upsert failed: %s", e)
        return 0

    logger.info("Supabase sink: upserted %d incident(s) from %s", len(records), path)
    return len(records)


def main(argv: list[str]) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if not argv:
        print("usage: python supabase_sink.py <results.csv> [more.csv ...]", file=sys.stderr)
        return 2
    total = sum(sync_csv(p) for p in argv)
    logger.info("Supabase sink: %d total upsert(s)", total)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
