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
