# Edgar 8K Scripts

This repository contains two Python scripts for scraping the SEC Edgar database for 8-K forms that mention "Material Cybersecurity" within the last 30 days.

## Table of Contents

1. [Scripts](#scripts)
    - [edgar8k.py](#edgar8kpy)
    - [edgar8kemail.py](#edgar8kemailpy)
2. [Requirements](#requirements)
3. [Installation](#installation)
4. [Usage](#usage)
5. [Output](#output)
6. [License](#license)

## Scripts

### edgar8k.py

This script scrapes the data and saves it to a CSV file.

### edgar8kemail.py

This script scrapes the data, saves it to a CSV file, includes the data in the body of an email, and sends the email with the CSV file as an attachment using SendGrid.

## Requirements

- Python 3.6+
- Selenium
- BeautifulSoup
- pandas
- SendGrid (only for `edgar8kemail.py`)

## Installation

1. Clone this repository.
2. Install the required packages with `pip install -r requirements.txt`.

## Usage

1. Set your SendGrid API key, sender email, and recipient email in `mysecrets.py` (only for `edgar8kemail.py`).
2. Run the desired script with `python3 <script_name>`.

## Output

The scripts will create a CSV file named `Edgar 8k 1.05 Results.csv` with the scraped data. `edgar8kemail.py` will also send an email with the CSV file as an attachment and the data in the body of the email.

## License

This project is licensed under the terms of the GNU General Public License v3.0.