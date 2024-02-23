# SEC 8-K 1.05 Scraper

This Python script scrapes the SEC's EDGAR database for 8-K forms that contain the term "Material Cybersecurity". It extracts the text associated with "Item 1.05" from each form and stops when it encounters the string "Cautionary Statement".
The script is divided into several functions, each responsible for a specific task:

- `setup_browser()`: This function sets up a headless Firefox browser using Selenium.

- `get_page_source(driver, url)`: This function navigates to the specified URL using the provided Selenium WebDriver and returns the page source parsed with BeautifulSoup.

- `extract_incident_text(driver, link)`: This function navigates to the specified link using the provided Selenium WebDriver, finds the text associated with "Item 1.05", and returns it as a string.

- `main()`: This is the main function that orchestrates the execution of the script. It sets up the browser, navigates to the EDGAR search page, extracts the data from the search results table, navigates to each form's link to extract the incident text, and saves the data to a CSV file.

The script uses the BeautifulSoup library to parse the HTML of the web pages, the Selenium library to automate the browser, and the pandas library to handle the data and save it to a CSV file.

The output of the script is a CSV file named `Edgar 8k 1.05 Results.csv` that contains the scraped data. Each row in the file represents a form, and the columns represent the form's details, including the link to the form and the extracted incident text.

## Table of Contents

- [Installation](#installation)
- [Usage](#usage)

## Installation

Follow these steps to install and setup the project:

1. **Clone the repository**

    Clone this repository to your local machine using the following command:

    ```bash
    git clone https://github.com/cladkins/SEC-8K-1.05
    ```

    
2. **Navigate to the project directory**

    Change your current directory to the project directory:

    ```bash
    cd path/to/project
    ```

3. **Install the required Python packages**

    Use pip to install the required packages:

    ```bash
    pip install -r requirements.txt
    ```

## Usage

Run the script with the following command:

```bash
python edgar8k.py
```
