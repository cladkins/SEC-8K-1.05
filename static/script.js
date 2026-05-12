const scrapeForm = document.getElementById('scrapeForm');
const startBtn = document.getElementById('startBtn');
const downloadCsvBtn = document.getElementById('downloadCsvBtn');
const downloadMdBtn = document.getElementById('downloadMdBtn');
const statusPanel = document.getElementById('statusPanel');
const errorPanel = document.getElementById('errorPanel');
const resultsPanel = document.getElementById('resultsPanel');
const currentTask = document.getElementById('currentTask');
const progressBar = document.getElementById('progressBar');
const progress = document.getElementById('progress');
const total = document.getElementById('total');
const lastRun = document.getElementById('lastRun');
const lastRunTime = document.getElementById('lastRunTime');
const errorMessage = document.getElementById('errorMessage');
const resultsTableHead = document.getElementById('resultsTableHead');
const resultsTableBody = document.getElementById('resultsTableBody');
const resultsCount = document.getElementById('resultsCount');

let statusCheckInterval = null;

scrapeForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const payload = {
        query: document.getElementById('query').value,
        days: Number(document.getElementById('days').value) || 30,
        forms: document.getElementById('forms').value,
        require_item: document.getElementById('requireItem').value,
    };
    try {
        const response = await fetch('/api/start', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload),
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || 'Failed to start scrape');
        }
        statusPanel.style.display = 'block';
        errorPanel.style.display = 'none';
        resultsPanel.style.display = 'none';
        startBtn.disabled = true;
        downloadCsvBtn.disabled = true;
        downloadMdBtn.disabled = true;
        startStatusCheck();
    } catch (error) {
        errorPanel.style.display = 'block';
        errorMessage.textContent = error.message;
    }
});

downloadCsvBtn.addEventListener('click', () => {
    window.location.href = '/api/download/csv';
});

downloadMdBtn.addEventListener('click', () => {
    window.location.href = '/api/download/md';
});

function startStatusCheck() {
    if (statusCheckInterval) clearInterval(statusCheckInterval);
    statusCheckInterval = setInterval(checkStatus, 1000);
    checkStatus();
}

function stopStatusCheck() {
    if (statusCheckInterval) {
        clearInterval(statusCheckInterval);
        statusCheckInterval = null;
    }
}

async function checkStatus() {
    try {
        const response = await fetch('/api/status');
        const status = await response.json();

        currentTask.textContent = status.current_task;
        progress.textContent = status.progress;
        total.textContent = status.total;

        const percentage = status.total > 0
            ? Math.round((status.progress / status.total) * 100)
            : (status.running ? 5 : 0);
        progressBar.style.width = percentage + '%';

        if (status.completed) {
            stopStatusCheck();
            startBtn.disabled = false;
            downloadCsvBtn.disabled = false;
            downloadMdBtn.disabled = false;
            if (status.last_run) {
                lastRun.style.display = 'block';
                lastRunTime.textContent = status.last_run;
            }
            if (status.results && status.results.length > 0) {
                displayResults(status.results);
            } else {
                resultsPanel.style.display = 'block';
                resultsCount.textContent = 0;
                resultsTableHead.innerHTML = '';
                resultsTableBody.innerHTML = '';
            }
        }

        if (status.error) {
            stopStatusCheck();
            startBtn.disabled = false;
            errorPanel.style.display = 'block';
            errorMessage.textContent = status.error;
        }
    } catch (error) {
        console.error('Status poll failed:', error);
        stopStatusCheck();
        startBtn.disabled = false;
    }
}

function displayResults(results) {
    resultsPanel.style.display = 'block';
    resultsCount.textContent = results.length;

    const headers = Object.keys(results[0]);
    const headerRow = document.createElement('tr');
    headers.forEach(header => {
        const th = document.createElement('th');
        th.textContent = header;
        headerRow.appendChild(th);
    });
    resultsTableHead.innerHTML = '';
    resultsTableHead.appendChild(headerRow);

    resultsTableBody.innerHTML = '';
    results.forEach(result => {
        const row = document.createElement('tr');
        headers.forEach(header => {
            const td = document.createElement('td');
            const value = result[header];
            if (header === 'Link' && value && value.startsWith('http')) {
                const a = document.createElement('a');
                a.href = value;
                a.textContent = 'View Filing';
                a.target = '_blank';
                a.rel = 'noopener';
                td.appendChild(a);
            } else if (value && String(value).length > 140) {
                td.textContent = String(value).substring(0, 140) + '…';
                td.title = String(value);
            } else {
                td.textContent = value == null ? '' : String(value);
            }
            row.appendChild(td);
        });
        resultsTableBody.appendChild(row);
    });
}

window.addEventListener('load', async () => {
    try {
        const response = await fetch('/api/status');
        const status = await response.json();
        if (status.results && status.results.length > 0) {
            displayResults(status.results);
            downloadCsvBtn.disabled = false;
            downloadMdBtn.disabled = false;
            if (status.last_run) {
                lastRun.style.display = 'block';
                lastRunTime.textContent = status.last_run;
                statusPanel.style.display = 'block';
                currentTask.textContent = `Completed (${status.last_run})`;
                progressBar.style.width = '100%';
                progress.textContent = status.total;
                total.textContent = status.total;
            }
        }
    } catch (error) {
        console.error('Initial status load failed:', error);
    }
});
