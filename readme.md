# SEC 8-K Cybersecurity Incident Disclosures

Pulls SEC EDGAR 8-K filings that disclose a cybersecurity incident, extracts
the disclosure text, and saves the results to a CSV. Two categories, run as
separate searches and tagged in the output (see Notes below):
Item 1.05 (mandatory, materiality already determined) and Item 7.01/8.01
(voluntary, "still investigating, materiality not yet determined"). Optionally
emails the CSV via SendGrid or SMTP.

Originally a Selenium scraper; rewritten to use the official EDGAR
full-text-search JSON API. No browser required.

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # then edit
```

## Configure

Edit `.env`. The only required variable is `SEC_USER_AGENT`, which the SEC's
fair-access policy mandates — it must contain a real name and email:

```
SEC_USER_AGENT="Your Name you@example.com"
```

If you plan to email the report, also fill in either the SendGrid or SMTP block.

## Run

```bash
# Default: last 30 days, "Material Cybersecurity Incidents" in 8-K filings,
# writes to "Edgar 8k 1.05 Results.csv".
python edgar8k.py

# Custom window
python edgar8k.py --days 7
python edgar8k.py --start 2024-01-01 --end 2024-03-31

# Different query / forms
python edgar8k.py --query '"ransomware"' --forms 8-K,10-K

# Disable the Item 1.05 filter (include search false-positives like 10-Ks
# that merely mention the phrase)
python edgar8k.py --require-item ""

# Skip the Item 7.01/8.01 voluntary-disclosure pass (Item 1.05 only)
python edgar8k.py --no-voluntary

# Email the result
python edgar8k.py --email sendgrid
python edgar8k.py --email smtp

# Verbose logging
python edgar8k.py -v
```

## Web GUI (Docker)

A small Flask GUI is bundled for browser-driven runs. It uses the same
`edgar8k.py` core as the CLI — no Selenium, no browser inside the
container.

```bash
# Build and run
docker compose up --build

# Or without compose
docker build -t edgar8k-web .
docker run --rm -p 5000:5000 \
  -e SEC_USER_AGENT="Your Name you@example.com" \
  -v "$(pwd)/results:/data" \
  edgar8k-web
```

Then open <http://localhost:5000>. The form mirrors the CLI flags
(`query`, `days`, `forms`, `require_item`); CSV and Markdown outputs
land in `./results/`.

## CSV columns

`Form & File`, `Filed`, `Reporting for`, `Filing entity/person`, `CIK`,
`Located`, `Incorporated`, `File number`, `Film number`, `Link`,
`Disclosure Type`, `Cybersecurity Incident`.

`Disclosure Type` is `item_1_05` (mandatory, materiality determined) or
`item_7_01_8_01` (voluntary, materiality not yet determined).

## Notes

- Item 1.05 was added to Form 8-K by the SEC's 2023 cybersecurity disclosure
  rule and became required for most registrants on Dec 18, 2023.
- The disclosure extractor finds the matched item's header ("Item 1.05" or
  "Item 7.01"/"Item 8.01") in the filing's HTML and captures text up to the
  next Item header or a "Cautionary Statement" block.
- EDGAR's full-text search can return false positives (e.g. 10-Ks that
  mention the phrase "Material Cybersecurity Incidents" only as boilerplate).
  By default `--require-item 1.05` filters those out using EDGAR's structured
  `items` field on each hit.
- The Item 7.01/8.01 voluntary pass searches the broader, generic phrase
  "cybersecurity incident" (no Item 1.05 boilerplate required), since that's
  the whole point - catching early disclosures before a materiality
  determination exists. That looser phrase can hit an accession where the
  actual match is in an unrelated document within the same filing (e.g. a
  press release about board changes, filed under 7.01/8.01 for an unrelated
  reason). A real disclosure always has extractable body text right after its
  item header, so a "Not found" extraction on this pass is treated as a false
  positive and silently dropped, rather than shown against a company that
  didn't have an incident. (Item 1.05 hits keep "Not found" as a visible
  row instead - a real, mandatory disclosure failing to extract is a bug
  worth seeing, not a filing worth hiding.)
- Requests are spaced out to stay under SEC's 10 req/sec rate limit.
