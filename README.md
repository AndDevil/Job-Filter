# 💼 Personal Job Search Pipeline & Tracker

An automated job search service that scrapes multiple job boards, standardizes and deduplicates listings, computes custom relevance scores, and allows you to track application progress using a modern interactive Streamlit dashboard.

---

## 🚀 Key Features

1. **Multi-Source Aggregator**:
   - **JobSpy**: Scrapes LinkedIn, Indeed, Glassdoor, Google Jobs, and ZipRecruiter.
   - **JobSeek (Optional)**: Connects to the free `jobseek.dev` API if an API key is provided.
2. **Weighted Smart Scoring**:
   - Scores every job dynamically (0–100) based on remote suitability, matched tech stack keywords, senior titles, top-tier companies, startup mentions, and high salary benchmarks.
   - Applies penalties for contracts, junior Java roles, or explicitly non-remote jobs.
3. **Dynamic Settings & Live Sync**:
   - Search parameters, keyword weighting lists, minimum scores, and alert configurations are loaded dynamically from the PostgreSQL database `settings` table. 
   - Manage and save configurations directly from the Streamlit UI without editing code.
4. **Resume-Driven Auto-Configuration (Dual NLP Engine)**:
   - Upload your PDF/TXT resume to automatically extract skills, recommended designations, seniority level, and startup experience suitability.
   - **Premium Engine:** Uses the Gemini Structured JSON generation API if a `GEMINI_API_KEY` is present.
   - **Local Fallback Engine:** Uses `spaCy` (`en_core_web_sm`) tokenization and noun-chunk extraction locally (works out-of-the-box offline).
   - Auto-fills the config dashboard with a single click.
5. **Real-Time Progress & Execution ETA**:
   - Scraper runs output `[PROGRESS]` logs that are parsed dynamically by the dashboard to show a precise progress percentage and execution timers (elapsed and estimated remaining time).
6. **Application Tracking Dashboard**:
   - Built with Streamlit and SQLite/Supabase PostgreSQL.
   - Features beautiful, card-based layouts with HSL color-coded metrics and charts.
   - Updates application status (New, Applied, Interviewing, Rejected, Offered) and logs custom tracking notes in real-time.
7. **Daily Automation (Node 24 / Git Fixes)**:
   - GitHub Actions workflow runs every day at 8:00 AM UTC and uploads output CSV artifacts.
   - Fully upgraded to **Node.js 24** runtimes and configured with master gitcheckouts to handle automated logs commits cleanly.

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
   > [!NOTE]
   > For the local fallback resume parser, spaCy requires the `en_core_web_sm` model. The dashboard will automatically attempt to download it on first launch, or you can run:
   > ```bash
   > python -m spacy download en_core_web_sm
   > ```

   > [!TIP]
   > On modern Python versions (e.g., Python 3.14+), JobSpy's pinned dependency version for NumPy may fail to compile from source. If you experience build errors, run:
   > ```bash
   > pip install --no-deps python-jobspy
   > pip install pandas requests numpy pydantic anyio httpx streamlit plotly pypdf spacy google-generativeai
   > ```

---

## 🏃 Execution & Usage

### 1. Run the Scraper Pipeline
Execute the Python script manually to scrape, deduplicate, score, and output job datasets:
```bash
python job_pipeline.py
```
**Output Files Generated**:
* `relevant_jobs.csv` (Top scored job opportunities)
* `all_jobs_combined.csv` (All matching job opportunities)

### 2. Start the Streamlit Dashboard
Launch the interactive web application to browse jobs, configure weights, parse resumes, and track applications:
```bash
streamlit run dashboard.py
```
The application will start at `http://localhost:8501`.

---

## 🔄 GitHub Actions Workflow

The scraper is configured to run automatically on GitHub Actions:
* **Trigger Times**: Daily at `08:00 AM UTC` and manual triggers.
* **Outputs**: Artifacts containing `relevant_jobs.csv` and `all_jobs_combined.csv` (retained for 30 days).
* **Setup**: Push the `.github/workflows/scrape.yml` file to your GitHub repository. The workflow uses updated Node 24 actions (`actions/checkout@v6`, `actions/setup-python@v6`, `actions/upload-artifact@v7`) and automatically commits the scraped jobs back to master.

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

### 3. Gemini API Key Setup (Optional)
To use the premium AI model for resume auto-configuration parsing:
1. Obtain an API key from Google AI Studio.
2. Set the `GEMINI_API_KEY` environment variable. If missing, the dashboard automatically drops back to the local spaCy NLP dictionary engine.

### 4. Configuration Variables
Secure your deployment by setting these environment variables locally (or as GitHub Secrets):

| Variable Name | Description | Required / Optional |
|---|---|---|
| `SUPABASE_DB_URL` | Supabase PostgreSQL Connection String | Optional (falls back to local SQLite/CSV) |
| `APP_PASSWORD` | Access password for the Streamlit dashboard (e.g., `Demo2026`) | Optional (locks app if set) |
| `JOBSPY_PROXY` | Proxy endpoint URL or API key | Optional (bypasses cloud rate limits) |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot API Token | Optional (enables phone alerts) |
| `TELEGRAM_CHAT_ID` | Telegram User Chat ID | Optional (enables phone alerts) |
| `DISCORD_WEBHOOK_URL` | Discord Channel Webhook URL | Optional (enables phone alerts) |
| `GEMINI_API_KEY` | Google Gemini API Key for Resume Parser | Optional (falls back to spaCy offline parser) |

### 5. Render Cloud Deployment (Recommended)
1. Push your repository to GitHub.
2. Sign in to the [Render Console](https://dashboard.render.com).
3. Click **New +** > **Blueprint**.
4. Select your GitHub repository and choose the `render` branch to load configs.
5. Render will automatically parse the [render.yaml](file:///c:/Users/Shrish/Downloads/Intern%20projects/Job%20Filter/render.yaml) configuration file. Fill in your environment variables:
   * `SUPABASE_DB_URL`: The **Connection Pooler** URI of your persistent Supabase PostgreSQL database (Session mode recommended).
     * *⚠️ Warning:* If your database password contains special characters (like `%` or `?`), make sure to **URL-encode** them in the connection string (e.g. replace `%` with `%25` and `?` with `%3F`) to prevent DSN parser errors on deployment!
   * `APP_PASSWORD`: The access password to lock/protect your Streamlit dashboard (e.g., `Demo2026`).
   * `GEMINI_API_KEY`: Google Gemini API key for the resume parsing feature.
6. Click **Apply**. Render will automatically provision, install dependencies, compile the spaCy NLP package, and start your Streamlit dashboard.

### 6. Streamlit Community Cloud Deployment
1. Push your repository to GitHub (`master` branch).
2. Sign in to [Streamlit Community Cloud](https://share.streamlit.io/).
3. Click **New app**, select your repository, branch, and file (`dashboard.py`).
4. In the app settings, click **Advanced settings** and paste your environment variables into the **Secrets** text area, e.g.:
   ```toml
    SUPABASE_DB_URL = "postgresql://..."
    APP_PASSWORD = "Demo2026"
    GEMINI_API_KEY = "your-gemini-key"
   ```
5. Click **Deploy**. Your secure dashboard is now live!

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
* **Audit and Run Log**: You can check the execution outcomes in Task Scheduler under the **History** tab.

