"""Fetch SEC EDGAR 8-K filings disclosing Material Cybersecurity Incidents (Item 1.05).

Hits EDGAR's full-text-search JSON API directly (no browser), pulls the Item 1.05
disclosure text for each hit, writes a CSV, and optionally emails the result via
SendGrid or SMTP.
"""

from __future__ import annotations

import argparse
import base64
import logging
import os
import re
import smtplib
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Iterable

import httpx
import pandas as pd
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

EDGAR_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"
EDGAR_ARCHIVE_BASE = "https://www.sec.gov/Archives/edgar/data"

DEFAULT_QUERY = '"Material Cybersecurity Incidents"'
DEFAULT_FORMS = "8-K"
DEFAULT_OUTPUT = "Edgar 8k 1.05 Results.csv"

CSV_COLUMNS = [
    "Form & File",
    "Filed",
    "Reporting for",
    "Filing entity/person",
    "CIK",
    "Located",
    "Incorporated",
    "File number",
    "Film number",
    "Link",
    "Cybersecurity Incident",
]

# SEC fair-access policy requires a real contact in the User-Agent.
# Override via SEC_USER_AGENT env var.
DEFAULT_USER_AGENT = "Chris Adkins cladkins@gmail.com"

logger = logging.getLogger("edgar8k")


@dataclass
class Filing:
    form_and_file: str
    filed: str
    reporting_for: str
    filing_entity: str
    cik: str
    located: str
    incorporated: str
    file_number: str
    film_number: str
    link: str
    incident_text: str

    def to_row(self) -> dict:
        return {
            "Form & File": self.form_and_file,
            "Filed": self.filed,
            "Reporting for": self.reporting_for,
            "Filing entity/person": self.filing_entity,
            "CIK": self.cik,
            "Located": self.located,
            "Incorporated": self.incorporated,
            "File number": self.file_number,
            "Film number": self.film_number,
            "Link": self.link,
            "Cybersecurity Incident": self.incident_text,
        }


def build_client(user_agent: str) -> httpx.Client:
    return httpx.Client(
        headers={
            "User-Agent": user_agent,
            "Accept-Encoding": "gzip, deflate",
        },
        timeout=30.0,
        follow_redirects=True,
    )


def get_with_retry(client: httpx.Client, url: str, *, params=None, headers=None, attempts: int = 4) -> httpx.Response:
    last_exc: Exception | None = None
    for i in range(attempts):
        try:
            resp = client.get(url, params=params, headers=headers)
            if resp.status_code == 429 or resp.status_code >= 500:
                raise httpx.HTTPStatusError(f"status {resp.status_code}", request=resp.request, response=resp)
            resp.raise_for_status()
            return resp
        except (httpx.HTTPError, httpx.TransportError) as e:
            last_exc = e
            wait = 2 ** i
            logger.warning("Request to %s failed (%s); retrying in %ss", url, e, wait)
            time.sleep(wait)
    assert last_exc is not None
    raise last_exc


def search_filings(
    client: httpx.Client,
    *,
    query: str,
    forms: str,
    start_date: date,
    end_date: date,
    require_item: str | None,
) -> list[dict]:
    params = {
        "q": query,
        "dateRange": "custom",
        "startdt": start_date.isoformat(),
        "enddt": end_date.isoformat(),
        "forms": forms,
    }
    logger.info(
        "Searching EDGAR  q=%s forms=%s window=%s..%s",
        query, forms, start_date.isoformat(), end_date.isoformat(),
    )
    resp = get_with_retry(client, EDGAR_SEARCH_URL, params=params)
    hits = resp.json().get("hits", {}).get("hits", [])
    logger.info("EDGAR returned %d hits", len(hits))

    if require_item:
        kept = []
        dropped = []
        for h in hits:
            items = (h.get("_source") or {}).get("items") or []
            if require_item in items:
                kept.append(h)
            else:
                dropped.append((h.get("_id", "?"), items))
        for hit_id, items in dropped:
            logger.info("Dropping %s (items=%s, missing %s)", hit_id, items, require_item)
        logger.info("Kept %d/%d hits matching Item %s", len(kept), len(hits), require_item)
        return kept

    return hits


_DISPLAY_NAME_RE = re.compile(r"^(?P<name>.*?)\s*\(CIK\s*(?P<cik>\d+)\)\s*$")


def parse_display_name(display: str) -> tuple[str, str]:
    """Split 'COMPANY (TICKER) (CIK 0000123)' into ('COMPANY (TICKER) ', 'CIK 0000123')."""
    m = _DISPLAY_NAME_RE.match(display)
    if not m:
        return display, ""
    name = m.group("name").strip() + " "
    return name, f"CIK {m.group('cik')}"


def build_filing_url(cik: str, adsh: str, filename: str) -> str:
    adsh_nodash = adsh.replace("-", "")
    return f"{EDGAR_ARCHIVE_BASE}/{cik}/{adsh_nodash}/{filename}"


_ITEM_HEADER_RE = re.compile(r"Item\s*1\.05", re.IGNORECASE)
_NEXT_BOUNDARY_RE = re.compile(
    r"(?:\bItem\s+\d+\.\d+\b|Cautionary\s+Statement)",
    re.IGNORECASE,
)


def extract_incident_text(html: str) -> str:
    """Pull the body of the Item 1.05 disclosure from a filing's HTML."""
    soup = BeautifulSoup(html, "lxml")
    raw = soup.get_text(separator=" ", strip=True)
    # Collapse runs of whitespace.
    text = re.sub(r"\s+", " ", raw).strip()
    if not text:
        return "Not found"

    start = _ITEM_HEADER_RE.search(text)
    if not start:
        return "Not found"

    after = text[start.end():]
    end = _NEXT_BOUNDARY_RE.search(after)
    body = after[: end.start()] if end else after
    return body.strip()


def hit_to_filing(hit: dict, client: httpx.Client) -> Filing | None:
    source = hit.get("_source", {})
    hit_id = hit.get("_id", "")
    if ":" in hit_id:
        adsh, filename = hit_id.split(":", 1)
    else:
        adsh = source.get("adsh", "")
        filename = ""

    ciks = source.get("ciks") or []
    cik = ciks[0] if ciks else ""
    display_names = source.get("display_names") or []
    display = display_names[0] if display_names else ""
    entity, cik_field = parse_display_name(display)

    biz_locations = source.get("biz_locations") or []
    biz_states = source.get("biz_states") or []
    inc_states = source.get("inc_states") or []
    file_numbers = source.get("file_num") or []
    film_numbers = source.get("film_num") or []
    located = biz_locations[0] if biz_locations else (biz_states[0] if biz_states else "")

    form = source.get("form", "")
    form_and_file = f"{form} (Current report) " if form else ""

    link = build_filing_url(cik, adsh, filename) if cik and filename else ""

    incident_text = "Not found"
    if link:
        try:
            doc_resp = get_with_retry(client, link)
            incident_text = extract_incident_text(doc_resp.text)
        except Exception as e:
            logger.warning("Failed to fetch %s: %s", link, e)
        # Be polite to SEC servers (10 req/sec cap).
        time.sleep(0.15)

    return Filing(
        form_and_file=form_and_file,
        filed=source.get("file_date", ""),
        reporting_for=source.get("period_ending") or source.get("period_of_report") or "",
        filing_entity=entity,
        cik=cik_field,
        located=located,
        incorporated=inc_states[0] if inc_states else "",
        file_number=file_numbers[0] if file_numbers else "",
        film_number=film_numbers[0] if film_numbers else "",
        link=link,
        incident_text=incident_text,
    )


def collect_filings(
    *,
    user_agent: str,
    query: str,
    forms: str,
    start_date: date,
    end_date: date,
    require_item: str | None,
) -> list[Filing]:
    with build_client(user_agent) as client:
        hits = search_filings(
            client,
            query=query,
            forms=forms,
            start_date=start_date,
            end_date=end_date,
            require_item=require_item,
        )
        filings: list[Filing] = []
        for i, hit in enumerate(hits, 1):
            logger.info("[%d/%d] Fetching filing detail", i, len(hits))
            filing = hit_to_filing(hit, client)
            if filing:
                filings.append(filing)
        return filings


def write_csv(filings: Iterable[Filing], path: Path) -> pd.DataFrame:
    df = pd.DataFrame([f.to_row() for f in filings], columns=CSV_COLUMNS)
    df.to_csv(path, index=False)
    logger.info("Wrote %d rows to %s", len(df), path)
    return df


def send_sendgrid(df: pd.DataFrame, csv_path: Path) -> None:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import (
        Attachment,
        Disposition,
        FileContent,
        FileName,
        FileType,
        Mail,
    )

    api_key = require_env("SENDGRID_API_KEY")
    sender = require_env("SENDER_EMAIL")
    recipient = require_env("RECIPIENT_EMAIL")

    encoded = base64.b64encode(csv_path.read_bytes()).decode()
    message = Mail(
        from_email=sender,
        to_emails=recipient,
        subject="Edgar 8k 1.05 Results",
        html_content=df.to_html(index=False),
    )
    message.attachment = Attachment(
        FileContent(encoded),
        FileName(csv_path.name),
        FileType("application/csv"),
        Disposition("attachment"),
    )
    SendGridAPIClient(api_key).send(message)
    logger.info("Email sent to %s via SendGrid", recipient)


def send_smtp(df: pd.DataFrame, csv_path: Path) -> None:
    host = require_env("SMTP_SERVER")
    port = int(require_env("SMTP_PORT"))
    username = require_env("SMTP_USERNAME")
    password = require_env("SMTP_PASSWORD")
    sender = require_env("SENDER_EMAIL")
    recipient = require_env("RECIPIENT_EMAIL")

    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = "Edgar 8k 1.05 Results"
    msg.attach(MIMEText(df.to_html(index=False), "html"))

    part = MIMEBase("application", "octet-stream")
    part.set_payload(csv_path.read_bytes())
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", f'attachment; filename="{csv_path.name}"')
    msg.attach(part)

    with smtplib.SMTP(host, port) as server:
        server.starttls()
        server.login(username, password)
        server.send_message(msg)
    logger.info("Email sent to %s via SMTP %s:%s", recipient, host, port)


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"Missing required env var: {name}")
    return value


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--query", default=DEFAULT_QUERY, help=f"EDGAR full-text query (default: {DEFAULT_QUERY!r})")
    p.add_argument("--forms", default=DEFAULT_FORMS, help=f"Form types, comma-separated (default: {DEFAULT_FORMS!r})")
    p.add_argument(
        "--require-item",
        default="1.05",
        help="Drop hits whose 8-K items list does not contain this value. Pass empty string to disable (default: '1.05').",
    )
    p.add_argument("--days", type=int, default=30, help="Look-back window in days (default: 30)")
    p.add_argument("--start", type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(), help="Start date YYYY-MM-DD (overrides --days)")
    p.add_argument("--end", type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(), help="End date YYYY-MM-DD (default: today)")
    p.add_argument("--output", type=Path, default=Path(DEFAULT_OUTPUT), help=f"CSV output path (default: {DEFAULT_OUTPUT!r})")
    p.add_argument("--email", choices=["none", "sendgrid", "smtp"], default="none", help="Email the results after writing the CSV")
    p.add_argument("--user-agent", default=os.environ.get("SEC_USER_AGENT", DEFAULT_USER_AGENT), help="Value for the SEC User-Agent header")
    p.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    end_date = args.end or date.today()
    start_date = args.start or (end_date - timedelta(days=args.days))

    filings = collect_filings(
        user_agent=args.user_agent,
        query=args.query,
        forms=args.forms,
        start_date=start_date,
        end_date=end_date,
        require_item=args.require_item or None,
    )
    df = write_csv(filings, args.output)

    if args.email == "sendgrid":
        send_sendgrid(df, args.output)
    elif args.email == "smtp":
        send_smtp(df, args.output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
