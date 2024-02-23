import time
import re
from bs4 import BeautifulSoup, NavigableString
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd

# Set up headless browser options
options = Options()
options.headless = True

# URL to scrape
url = "https://www.sec.gov/edgar/search/#/q=%2522Material%2520Cybersecurity%2520Incidents%2522&dateRange=30d&category=custom&forms=8-K&sort=desc"

# Set up headless browser
driver = webdriver.Firefox(options=options)

# Get the page
driver.get(url)

# Wait for the search results to be loaded
wait = WebDriverWait(driver, 10)
results = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'div.col-md-8.col-lg-9 table.table:nth-child(3) > tbody:nth-child(2)')))

# Add an additional delay
time.sleep(5)

# Parse the results with BeautifulSoup
soup = BeautifulSoup(driver.page_source, 'html.parser')

# Find the table
table = soup.select_one('div.col-md-8.col-lg-9 table.table:nth-child(3)')

# Extract the headers
headers = [header.text for header in table.find('thead').find_all('th')]
headers.append('Link')  # Add a new column for the link
headers.append('Cybersecurity Incident')  # Add a new column for the cybersecurity incident

# Extract the rows
rows = []
for row in table.find('tbody').find_all('tr'):
    cells = [cell.text for cell in row.find_all('td')]
    link = row.find('a')['href'].lstrip('#')
    adsh = row.find('a')['data-adsh'].replace('-', '')
    cik = cells[4].split(' ')[1]  # Extract the CIK from the CIK column and remove leading zeros
    full_link = f"https://www.sec.gov/Archives/edgar/data/{cik}/{adsh}/{link}"
    cells.append(full_link)  # Add the link to the row

    # Visit the link and extract the cybersecurity incident
    driver.get(full_link)
    time.sleep(5)
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    incident_header = soup.find(string=lambda text: 'Item' in text if text else False)
    if incident_header:
        incident_text = []
        for element in incident_header.next_elements:
            if isinstance(element, NavigableString):
                if element.strip().startswith('Item') or 'Cautionary Statement' in element:
                    break
                incident_text.append(element.strip())
        incident_text = ' '.join(incident_text)
    else:
        incident_text = 'Not found'
    cells.append(incident_text)  # Add the cybersecurity incident to the row

    rows.append(cells)

# Create a DataFrame
df = pd.DataFrame(rows, columns=headers)

# Save the DataFrame to a CSV file
df.to_csv('Edgar 8k 1.05 Results.csv', index=False)

print("Data saved to output.csv")

# Close the browser
driver.quit()