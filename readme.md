# SEC 8-K Item 1.05 — Material Cybersecurity Incidents

Pulls SEC EDGAR 8-K filings that disclose a Material Cybersecurity Incident
under Item 1.05, extracts the disclosure text, and saves the results to a CSV.
Optionally emails the CSV via SendGrid or SMTP.

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

# Email the result
python edgar8k.py --email sendgrid
python edgar8k.py --email smtp

# Verbose logging
python edgar8k.py -v
```

## CSV columns

`Form & File`, `Filed`, `Reporting for`, `Filing entity/person`, `CIK`,
`Located`, `Incorporated`, `File number`, `Film number`, `Link`,
`Cybersecurity Incident`.

## Notes

- Item 1.05 was added to Form 8-K by the SEC's 2023 cybersecurity disclosure
  rule and became required for most registrants on Dec 18, 2023.
- The disclosure extractor finds the "Item 1.05" header in the filing's HTML
  and captures text up to the next Item header or a "Cautionary Statement"
  block.
- EDGAR's full-text search can return false positives (e.g. 10-Ks that
  mention the phrase "Material Cybersecurity Incidents" only as boilerplate).
  By default `--require-item 1.05` filters those out using EDGAR's structured
  `items` field on each hit.
- Requests are spaced out to stay under SEC's 10 req/sec rate limit.
