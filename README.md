# 💼 Personal Job Search Pipeline & Tracker

An automated job search service that scrapes multiple job boards, standardizes and deduplicates listings, computes custom relevance scores, and allows you to track application progress using a modern interactive Streamlit dashboard.

---

## 🚀 Key Features

1. **Multi-Source Aggregator**:
   - **JobHive**: Scrapes 3.2M+ jobs from 86K+ companies across major ATS systems (Greenhouse, Lever, Ashby, BambooHR, Workable, YCombinator).
   - **JobSpy**: Scrapes LinkedIn, Indeed, Glassdoor, Google Jobs, and ZipRecruiter.
   - **JobSeek (Optional)**: Connects to the free `jobseek.dev` API if an API key is provided.
2. **Weighted Smart Scoring**:
   - Scores every job dynamically (0–100) based on remote suitability, matched tech stack keywords, senior titles, top-tier companies, startup mentions, and high salary benchmarks.
   - Applies penalties for contracts, junior Java roles, or explicitly non-remote jobs.
3. **Application Tracking Dashboard**:
   - Built with Streamlit and SQLite.
   - Features beautiful, card-based layouts with HSL color-coded metrics and charts.
   - Updates application status (New, Applied, Interviewing, Rejected, Offered) and logs custom tracking notes in real-time.
4. **Daily Automation**:
   - GitHub Actions workflow runs every day at 8:00 AM UTC and uploads the fresh outputs as downloadable CSV artifacts.

---

## 🛠️ Setup Instructions

### Prerequisites
- Python 3.10 or higher
- Git

### Local Installation
Follow these steps to set up the project on your machine:

1. **Clone the repository**:
   ```bash
   git clone <your-repo-url>
   cd "Job Filter"
   ```

2. **Create a virtual environment**:
   - **macOS/Linux**:
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```
   - **Windows**:
     ```powershell
     python -m venv .venv
     .venv\Scripts\Activate.ps1
     ```

3. **Install Dependencies**:
   Install the required packages using the generated `requirements.txt`:
   ```bash
   pip install -r requirements.txt
   ```
   > [!TIP]
   > On modern Python versions (e.g., Python 3.14+), JobSpy's pinned dependency version for NumPy may fail to compile from source. If you experience build errors, run:
   > ```bash
   > pip install --no-deps python-jobspy
   > pip install pandas requests numpy pydantic anyio httpx streamlit plotly
   > ```

---

## 🏃 Execution & Usage

### 1. Run the Scraper Pipeline
Execute the Python script manually to scrape, deduplicate, score, and output job datasets:
```bash
python job_pipeline.py
```
**Output Files Generated**:
* `relevant_jobs.csv` (Top 50 scored job opportunities)
* `all_jobs_combined.csv` (All matching job opportunities)

### 2. Start the Streamlit Dashboard
Launch the interactive web application to browse jobs and track your applications:
```bash
streamlit run dashboard.py
```
The application will start at `http://localhost:8501`.

---

## 🔄 GitHub Actions Workflow

The scraper is configured to run automatically on GitHub Actions:
* **Trigger Times**: Daily at `08:00 AM UTC` and manual triggers.
* **Outputs**: Artifacts containing `relevant_jobs.csv` and `all_jobs_combined.csv` (retained for 30 days).
* **Setup**: Push the `.github/workflows/scrape.yml` file to your GitHub repository to enable the workflow.

---

## ☁️ Cloud Migration & Alerts Setup (Supabase & Webhooks)

This project supports running as a cloud-native service. When configured, jobs are synced to a cloud PostgreSQL database, and new high-scoring matches trigger alerts directly to your phone via Telegram or Discord.

### 1. Supabase Database Setup
1. Create a free account at [Supabase](https://supabase.com/).
2. Create a new project.
3. Go to **Project Settings** -> **Database** and copy your **URI connection string** (PostgreSQL). It looks like this:
   `postgresql://postgres:[YOUR-PASSWORD]@db.iaphlkshrcgnlunkwgta.supabase.co:5432/postgres`
4. Set this as the `SUPABASE_DB_URL` environment variable. The scraper will automatically set up the schema and sync listings.

### 2. Real-Time Phone Alerts Setup

#### Telegram Bot Setup (Optional)
1. Message `@BotFather` on Telegram and send `/newbot` to create your bot. Copy the generated **Bot Token**.
2. Start a chat with your bot, then message `@userinfobot` to retrieve your personal **Telegram Chat ID**.
3. Set the environment variables `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`.

#### Discord Webhook Setup (Optional)
1. Open Discord, go to **Server Settings** -> **Integrations** -> **Webhooks**.
2. Click **Create Webhook**, select the target channel, and copy the **Webhook URL**.
3. Set this as the `DISCORD_WEBHOOK_URL` environment variable.

### 3. JobSpy Proxy Setup
To bypass rate limits when scraping on cloud runners (like GitHub Actions), configure a proxy:
1. Obtain a rotating proxy address or API endpoint (e.g., from ScraperAPI, Webshare).
2. Set the `JOBSPY_PROXY` environment variable. JobSpy will route all HTTP requests through this proxy.

### 4. Configuration Variables
Secure your deployment by setting these environment variables locally (or as GitHub Secrets):

| Variable Name | Description | Required / Optional |
|---|---|---|
| `SUPABASE_DB_URL` | Supabase PostgreSQL Connection String | Optional (falls back to local SQLite/CSV) |
| `APP_PASSWORD` | Access password for the Streamlit dashboard | Optional (locks app if set) |
| `JOBSPY_PROXY` | Proxy endpoint URL or API key | Optional (bypasses cloud rate limits) |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot API Token | Optional (enables phone alerts) |
| `TELEGRAM_CHAT_ID` | Telegram User Chat ID | Optional (enables phone alerts) |
| `DISCORD_WEBHOOK_URL` | Discord Channel Webhook URL | Optional (enables phone alerts) |
| `NOTIFICATION_MIN_SCORE` | Minimum score threshold for notifications (default: `85`) | Optional |

### 5. Streamlit Cloud Deployment
1. Push your repository to GitHub.
2. Sign in to [Streamlit Community Cloud](https://share.streamlit.io/).
3. Click **New app**, select your repository, branch, and file (`dashboard.py`).
4. In the app settings, click **Advanced settings** and paste your environment variables into the **Secrets** text area, e.g.:
   ```toml
   SUPABASE_DB_URL = "postgresql://..."
   APP_PASSWORD = "your-secure-password"
   ```
5. Click **Deploy**. Your secure dashboard is now live and connected to your database!

---

## 💻 Windows Local Setup & Automation

### 1. One-Click execution (`run.bat`)
We have provided a `run.bat` file in the project root. Double-click it to:
* Verify or initialize the virtual environment (`venv`) automatically.
* Install missing dependencies.
* Run the job scraping pipeline (`job_pipeline.py`).
* Choose if you want to start the Streamlit dashboard (`Launch tracker dashboard? (y/n)`).

### 2. Windows Task Scheduler Setup
To automate the pipeline daily at 8:00 AM, select one of the options below:

#### Option A: Command Line (schtasks)
Run Command Prompt as **Administrator** and execute the following command:
```cmd
schtasks /create /tn "JobAggregatorPipeline" /tr "C:\path\to\project\run.bat" /sc daily /st 08:00
```
> [!IMPORTANT]
> Make sure to replace `C:\path\to\project` with the actual absolute path to your `Job Filter` folder.

#### Option B: Windows Task Scheduler GUI
1. Press `Win + R`, type `taskschd.msc`, and press Enter to open Task Scheduler.
2. In the right-hand panel, click **Create Basic Task...**
3. **Name**: Enter `Job Aggregator Pipeline` and click Next.
4. **Trigger**: Select **Daily** and click Next. Set the start time to `08:00 AM` and recur every 1 day, then click Next.
5. **Action**: Select **Start a program** and click Next.
6. **Program/script**: Browse and select `C:\path\to\project\run.bat`.
7. **Start in (optional)**: Enter the folder path `C:\path\to\project` (without quotes) to ensure the batch script resolves relative file paths correctly. Click Next.
8. Click **Finish**.

### How to Test and Check Logs
* **Immediate Test**: Right-click the task `JobAggregatorPipeline` in the Active Tasks list and select **Run**.
* **Audit and Run Log**: You can check the execution outcomes in Task Scheduler under the **History** tab (ensure "Enable All Tasks History" is checked in the Actions panel).
