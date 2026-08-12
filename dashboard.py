import os
import time
import sqlite3
import json
import pandas as pd
import streamlit as st
import plotly.express as px

# 1. Page Configuration
st.set_page_config(
    page_title="Personal Job Tracker",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Password Security Shield ---
def check_password():
    password_env = os.getenv("APP_PASSWORD")
    if not password_env:
        return True

    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False

    if st.session_state["authenticated"]:
        return True

    # Show centered login container
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown("<h2 style='text-align: center;'>🔐 Personal Job Tracker</h2>", unsafe_allow_html=True)
            st.markdown("<p style='text-align: center; color: #888;'>This dashboard is protected. Please enter the access password.</p>", unsafe_allow_html=True)
            password_input = st.text_input("Password", type="password", key="login_password")
            if st.button("Unlock Dashboard", use_container_width=True):
                if password_input == password_env:
                    st.session_state["authenticated"] = True
                    st.rerun()
                else:
                    st.error("❌ Incorrect password. Please try again.")
    return False

if not check_password():
    st.stop()

# --- PostgreSQL Caching and Configuration ---
SUPABASE_DB_URL = os.getenv("SUPABASE_DB_URL")
if SUPABASE_DB_URL:
    SUPABASE_DB_URL = SUPABASE_DB_URL.strip()
DB_FILE = "job_tracker.db"

try:
    import psycopg2
    from psycopg2.pool import ThreadedConnectionPool
except ImportError:
    psycopg2 = None
    ThreadedConnectionPool = None

@st.cache_resource
def get_connection_pool(db_url):
    if not psycopg2:
        return None
    # Pool with 1 to 10 connections
    return ThreadedConnectionPool(1, 10, db_url)

from contextlib import contextmanager

@contextmanager
def get_db_connection():
    if SUPABASE_DB_URL and psycopg2:
        pool = get_connection_pool(SUPABASE_DB_URL)
        if pool is None:
            raise Exception("PostgreSQL driver 'psycopg2' is not installed.")
        conn = pool.getconn()
        try:
            yield conn
        finally:
            pool.putconn(conn)
    else:
        conn = sqlite3.connect(DB_FILE)
        try:
            yield conn
        finally:
            conn.close()

# --- Auto-Refresh Check on Data Change (Local Mode only) ---
if not SUPABASE_DB_URL:
    CSV_FILE = "relevant_jobs.csv"
    if os.path.exists(CSV_FILE):
        current_mtime = os.path.getmtime(CSV_FILE)
        if "last_csv_mtime" not in st.session_state:
            st.session_state["last_csv_mtime"] = current_mtime
        elif current_mtime != st.session_state["last_csv_mtime"]:
            st.session_state["last_csv_mtime"] = current_mtime
            st.cache_data.clear()
            st.rerun()

# 2. Database Functions
def init_db():
    if SUPABASE_DB_URL and psycopg2:
        try:
            with get_db_connection() as conn:
                c = conn.cursor()
                c.execute("""
                    CREATE TABLE IF NOT EXISTS jobs (
                        url TEXT PRIMARY KEY,
                        job_title TEXT,
                        company TEXT,
                        location TEXT,
                        description TEXT,
                        posted TEXT,
                        salary_min FLOAT,
                        salary_max FLOAT,
                        is_remote BOOLEAN,
                        source TEXT,
                        score INTEGER,
                        alert_sent BOOLEAN DEFAULT FALSE,
                        scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                c.execute("""
                    CREATE TABLE IF NOT EXISTS applications (
                        job_url TEXT PRIMARY KEY REFERENCES jobs(url) ON DELETE CASCADE,
                        status TEXT DEFAULT 'New',
                        notes TEXT DEFAULT '',
                        applied_date TEXT,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                c.execute("""
                    CREATE TABLE IF NOT EXISTS settings (
                        key TEXT PRIMARY KEY,
                        value TEXT
                    );
                """)
                conn.commit()
        except Exception as e:
            st.error(f"Failed to initialize PostgreSQL tables: {e}")
    else:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS applications (
                job_url TEXT PRIMARY KEY,
                status TEXT,
                notes TEXT,
                applied_date TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );
        """)
        conn.commit()
        conn.close()

DEFAULT_CONFIG = {
    "search_term": "software engineer",
    "location": "United States",
    "results_wanted": 50,
    "min_notification_score": 85,
    "score_remote_bonus": 10,
    "score_tech_bonus": 8,
    "score_senior_bonus": 5,
    "score_top_tier_bonus": 5,
    "score_startup_bonus": 4,
    "score_salary_bonus": 3,
    "score_contract_penalty": -10,
    "score_junior_java_penalty": -8,
    "score_remote_false_penalty": -5,
    "tech_keywords": ["python", "typescript", "go", "rust", "react", "node", "django", "fastapi", "aws", "docker", "kubernetes"],
    "senior_title_keywords": ["senior", "lead"],
    "top_tier_companies": ["google", "microsoft", "apple", "amazon", "meta", "stripe", "anthropic", "openai", "figma", "vercel"],
    "startup_keywords": ["startup", "series", "funding", "early-stage"],
    "salary_threshold": 120000
}

def load_config():
    config = DEFAULT_CONFIG.copy()
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT key, value FROM settings;")
            rows = c.fetchall()
            
            if not rows:
                # Seed defaults
                for k, v in DEFAULT_CONFIG.items():
                    val_str = json.dumps(v)
                    if SUPABASE_DB_URL and psycopg2:
                        c.execute("INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO NOTHING;", (k, val_str))
                    else:
                        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?);", (k, val_str))
                conn.commit()
            else:
                for key, val_str in rows:
                    try:
                        config[key] = json.loads(val_str)
                    except Exception:
                        config[key] = val_str
    except Exception as e:
        st.warning(f"⚠️ Failed to load configuration from DB: {e}. Using code defaults.")
    return config

def save_config(config_dict):
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            for k, v in config_dict.items():
                val_str = json.dumps(v)
                if SUPABASE_DB_URL and psycopg2:
                    c.execute("""
                        INSERT INTO settings (key, value)
                        VALUES (%s, %s)
                        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;
                    """, (k, val_str))
                else:
                    c.execute("""
                        INSERT INTO settings (key, value)
                        VALUES (?, ?)
                        ON CONFLICT (key) DO UPDATE SET value = excluded.value;
                    """, (k, val_str))
            conn.commit()
            st.success("✅ Configurations saved successfully!")
    except Exception as e:
        st.error(f"❌ Failed to save configuration: {e}")

def get_tracker_data():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM applications", conn)
    conn.close()
    return df

def save_status(job_url, status, notes, applied_date=None):
    if SUPABASE_DB_URL and psycopg2:
        try:
            with get_db_connection() as conn:
                c = conn.cursor()
                c.execute("SELECT applied_date FROM applications WHERE job_url = %s", (job_url,))
                row = c.fetchone()
                if row:
                    final_applied_date = applied_date or row[0]
                else:
                    final_applied_date = applied_date
                
                c.execute("""
                    INSERT INTO applications (job_url, status, notes, applied_date)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT(job_url) DO UPDATE SET
                        status = EXCLUDED.status,
                        notes = EXCLUDED.notes,
                        applied_date = EXCLUDED.applied_date,
                        updated_at = CURRENT_TIMESTAMP
                """, (job_url, status, notes, final_applied_date))
                conn.commit()
        except Exception as e:
            st.error(f"Failed to update application status in cloud database: {e}")
    else:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        
        # Keep existing applied date if not explicitly set
        c.execute("SELECT applied_date FROM applications WHERE job_url = ?", (job_url,))
        row = c.fetchone()
        if row:
            final_applied_date = applied_date or row[0]
        else:
            final_applied_date = applied_date
            
        c.execute("""
            INSERT INTO applications (job_url, status, notes, applied_date)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(job_url) DO UPDATE SET
                status = excluded.status,
                notes = excluded.notes,
                applied_date = excluded.applied_date
        """, (job_url, status, notes, final_applied_date))
        conn.commit()
        conn.close()

# Callback to update the database when a widget changes
def update_db(url, key_prefix):
    status = st.session_state[f"{key_prefix}_status"]
    notes = st.session_state[f"{key_prefix}_notes"]
    applied_date = None
    if status == "Applied":
        applied_date = time.strftime("%Y-%m-%d")
    save_status(url, status, notes, applied_date)

# 3. Load Jobs Cache (Local Mode)
@st.cache_data(ttl=600)
def load_csv_jobs():
    if not os.path.exists("relevant_jobs.csv"):
        return pd.DataFrame()
    return pd.read_csv("relevant_jobs.csv")

# Load Jobs Cache (Cloud Mode)
def load_cloud_jobs():
    query = """
        SELECT j.url, j.job_title, j.company, j.location, j.description, j.posted, 
               j.salary_min, j.salary_max, j.is_remote, j.source, j.score,
               COALESCE(a.status, 'New') as status, COALESCE(a.notes, '') as notes, 
               a.applied_date, a.job_url
        FROM jobs j
        LEFT JOIN applications a ON j.url = a.job_url
        WHERE a.status IS NOT NULL OR j.url IN (
            SELECT url FROM jobs ORDER BY score DESC, posted DESC LIMIT 100
        )
        ORDER BY j.score DESC, j.posted DESC;
    """
    try:
        with get_db_connection() as conn:
            df = pd.read_sql_query(query, conn)
            if not df.empty and 'job_url' not in df.columns:
                df['job_url'] = df['url']
            return df
    except Exception as e:
        st.error(f"Error fetching data from PostgreSQL: {e}")
        return pd.DataFrame()

# Initialize Database
init_db()

# Custom CSS styling for premium look
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap');

/* Apply modern typography */
html, body, [class*="css"], .stApp {
    font-family: 'Outfit', sans-serif;
}

/* Glassmorphism card look */
div[data-testid="stVerticalBlockBorder"] {
    background: rgba(255, 255, 255, 0.03) !important;
    border: 1px solid rgba(255, 255, 255, 0.08) !important;
    border-radius: 16px !important;
    padding: 1.5rem !important;
    box-shadow: 0 4px 30px rgba(0, 0, 0, 0.15) !important;
    backdrop-filter: blur(10px) !important;
    -webkit-backdrop-filter: blur(10px) !important;
    transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
}

div[data-testid="stVerticalBlockBorder"]:hover {
    transform: translateY(-2px);
    border-color: rgba(37, 99, 235, 0.4) !important;
    box-shadow: 0 6px 35px rgba(37, 99, 235, 0.15) !important;
}

/* Dynamic Score Badges */
.score-badge {
    background: linear-gradient(135deg, #3b82f6, #1d4ed8);
    color: white;
    padding: 6px 14px;
    border-radius: 20px;
    font-weight: 600;
    font-size: 0.9rem;
    display: inline-block;
    box-shadow: 0 4px 15px rgba(59, 130, 246, 0.25);
}

.score-badge-high {
    background: linear-gradient(135deg, #10b981, #059669);
    color: white;
    padding: 6px 14px;
    border-radius: 20px;
    font-weight: 600;
    font-size: 0.9rem;
    display: inline-block;
    box-shadow: 0 4px 15px rgba(16, 185, 129, 0.25);
}

.score-badge-very-high {
    background: linear-gradient(135deg, #f59e0b, #d97706);
    color: white;
    padding: 6px 14px;
    border-radius: 20px;
    font-weight: 600;
    font-size: 0.9rem;
    display: inline-block;
    box-shadow: 0 4px 15px rgba(245, 158, 11, 0.25);
}

/* Sidebar Metric styling */
.sidebar-metric {
    background: rgba(255, 255, 255, 0.03);
    padding: 12px;
    border-radius: 12px;
    border: 1px solid rgba(255, 255, 255, 0.07);
    margin-bottom: 10px;
    text-align: center;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
}

/* Header Gradient */
.gradient-title {
    background: linear-gradient(135deg, #60a5fa, #2563eb, #7c3aed);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-weight: 800;
    font-size: 2.5rem;
    margin-bottom: 0.2rem;
}
</style>
""", unsafe_allow_html=True)

# 4. App Header
st.markdown("<h1 class='gradient-title'>💼 Personal Job Tracker & Dashboard</h1>", unsafe_allow_html=True)
st.markdown("Browse scraped roles, score relevance, and track your job applications.")
st.markdown("---")

# Load data files (Cloud or Local mode)
if SUPABASE_DB_URL:
    merged_df = load_cloud_jobs()
else:
    jobs_df = load_csv_jobs()
    if jobs_df.empty:
        st.warning("⚠️ **No jobs database found.** Please run the pipeline script `job_pipeline.py` first to scrape and score some jobs.")
        st.stop()
    tracker_df = get_tracker_data()
    # Merge jobs with tracker data on url -> job_url
    merged_df = jobs_df.merge(tracker_df, left_on='url', right_on='job_url', how='left')
    merged_df['status'] = merged_df['status'].fillna('New')
    merged_df['notes'] = merged_df['notes'].fillna('')

if merged_df.empty:
    st.warning("⚠️ **No jobs found.** Please run the pipeline script `job_pipeline.py` first to scrape, score, and sync some jobs.")
    st.stop()

# Helper to extract country for filtering/sorting
def extract_country(location):
    if not location or not isinstance(location, str):
        return "Unknown"
    loc = location.strip().lower()
    if loc.endswith("usa") or loc.endswith("us") or "united states" in loc:
        return "United States"
    if loc.endswith("uk") or "united kingdom" in loc or "london" in loc:
        return "United Kingdom"
    if loc.endswith("ca") or "canada" in loc:
        return "Canada"
    if "india" in loc or loc.endswith("in"):
        return "India"
    if "germany" in loc or loc.endswith("de"):
        return "Germany"
    if "remote" in loc:
        return "Remote"
    parts = location.split(",")
    if len(parts) > 1:
        return parts[-1].strip()
    return location.strip()

merged_df['country'] = merged_df['location'].apply(extract_country)

# 5. Sidebar Navigation & Filters
st.sidebar.header("🔍 Filters & Sorting")

# Search Query Filter
search_query = st.sidebar.text_input("Search Jobs or Companies", "").strip().lower()

# Minimum Score Filter
min_score = st.sidebar.slider("Minimum Relevance Score", min_value=0, max_value=100, value=0)

# Country Filter
countries = sorted(merged_df['country'].dropna().unique())
selected_countries = st.sidebar.multiselect("Filter by Country", options=countries, default=[])

# Company Filter
companies = sorted(merged_df['company'].dropna().unique())
selected_companies = st.sidebar.multiselect("Filter by Company", options=companies, default=[])

# Status Filter
status_opts = ["New", "Applied", "Interviewing", "Rejected", "Offered"]
selected_statuses = st.sidebar.multiselect("Filter by Status", options=status_opts, default=status_opts)

# Sorting Configuration
sort_by = st.sidebar.selectbox(
    "Sort Listings By",
    options=["Relevance Score", "Date Posted", "Country", "Location"],
    index=0
)

# Apply Filters
filtered_df = merged_df[merged_df['score'] >= min_score]

if selected_countries:
    filtered_df = filtered_df[filtered_df['country'].isin(selected_countries)]

if selected_companies:
    filtered_df = filtered_df[filtered_df['company'].isin(selected_companies)]
    
if selected_statuses:
    filtered_df = filtered_df[filtered_df['status'].isin(selected_statuses)]
    
if search_query:
    filtered_df = filtered_df[
        filtered_df['job_title'].str.lower().str.contains(search_query, na=False) |
        filtered_df['company'].str.lower().str.contains(search_query, na=False) |
        filtered_df['description'].str.lower().str.contains(search_query, na=False)
    ]

# Apply Sorting
if sort_by == "Relevance Score":
    filtered_df = filtered_df.sort_values(by=["score", "posted"], ascending=[False, False])
elif sort_by == "Date Posted":
    filtered_df = filtered_df.sort_values(by=["posted", "score"], ascending=[False, False])
elif sort_by == "Country":
    filtered_df = filtered_df.sort_values(by=["country", "score"], ascending=[True, False])
elif sort_by == "Location":
    filtered_df = filtered_df.sort_values(by=["location", "score"], ascending=[True, False])

# 6. Sidebar Stats & Metrics
st.sidebar.markdown("---")
st.sidebar.header("📊 Application Stats")

total_count = len(filtered_df)
applied_count = len(merged_df[merged_df['status'] == 'Applied'])
interview_count = len(merged_df[merged_df['status'] == 'Interviewing'])
offered_count = len(merged_df[merged_df['status'] == 'Offered'])

col1, col2 = st.sidebar.columns(2)
with col1:
    st.markdown(f"<div class='sidebar-metric'><b>Total Matching</b><br><span style='font-size: 1.5rem;'>{total_count}</span></div>", unsafe_allow_html=True)
    st.markdown(f"<div class='sidebar-metric'><b>Applied</b><br><span style='font-size: 1.5rem;'>{applied_count}</span></div>", unsafe_allow_html=True)
with col2:
    st.markdown(f"<div class='sidebar-metric'><b>Interviewing</b><br><span style='font-size: 1.5rem;'>{interview_count}</span></div>", unsafe_allow_html=True)
    st.markdown(f"<div class='sidebar-metric'><b>Offered</b><br><span style='font-size: 1.5rem; color:#22c55e;'>{offered_count}</span></div>", unsafe_allow_html=True)

# Top Companies Chart in Sidebar
if not filtered_df.empty:
    st.sidebar.markdown("---")
    st.sidebar.markdown("**Top Hiring Companies**")
    top_cos = filtered_df['company'].value_counts().head(8).reset_index()
    top_cos.columns = ['Company', 'Jobs']
    
    fig = px.bar(
        top_cos, 
        x='Jobs', 
        y='Company', 
        orientation='h', 
        color_discrete_sequence=['#2563eb']
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=5, b=5),
        height=240,
        xaxis=dict(gridcolor="rgba(255,255,255,0.05)", zeroline=False),
        yaxis=dict(autorange="reversed")
    )
    st.sidebar.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

# 7. Main Panel Display
tab_jobs, tab_settings, tab_guide = st.tabs(["💼 Job Listings & Tracker", "⚙️ Pipeline Settings", "📖 User Guide"])

with tab_jobs:
    if filtered_df.empty:
        st.info("No jobs match the selected filter criteria. Try expanding your search!")
    else:
        st.subheader(f"Showing {len(filtered_df)} Scored Job Listings")
        
        for idx, row in filtered_df.iterrows():
            key_prefix = f"job_{idx}"
            url = row['url']
            
            # Display each job in a bordered container card
            with st.container(border=True):
                col_title, col_score = st.columns([5, 1])
                with col_title:
                    st.markdown(f"### {row['job_title']}")
                    st.markdown(f"🏢 **{row['company']}**")
                with col_score:
                    score_val = int(row['score']) if pd.notna(row['score']) else 0
                    if score_val >= 90:
                        badge_class = "score-badge-very-high"
                    elif score_val >= 80:
                        badge_class = "score-badge-high"
                    else:
                        badge_class = "score-badge"
                    st.markdown(f"<div style='text-align: right;'><span class='{badge_class}'>Score: {score_val}</span></div>", unsafe_allow_html=True)
                
                # Badges metadata row
                badges = []
                if pd.notna(row['location']):
                    badges.append(f"📍 {row['location']}")
                if pd.notna(row['country']) and row['country'] != row['location']:
                    badges.append(f"🌍 {row['country']}")
                if row['is_remote']:
                    badges.append("🌐 Remote")
                if pd.notna(row['source']):
                    badges.append(f"🔍 {row['source']}")
                if pd.notna(row['posted']):
                    badges.append(f"📅 Posted: {row['posted']}")
                st.markdown(" | ".join(badges))
                
                # Optional Salary info
                salary_info = []
                if pd.notna(row['salary_min']) and row['salary_min'] > 0:
                    salary_info.append(f"Min: ${row['salary_min']:,.0f}")
                if pd.notna(row['salary_max']) and row['salary_max'] > 0:
                    salary_info.append(f"Max: ${row['salary_max']:,.0f}")
                if salary_info:
                    st.markdown(f"💵 **Salary**: {' - '.join(salary_info)}")
                
                # Expander for Description
                if pd.notna(row['description']):
                    with st.expander("📄 View Job Description"):
                        st.write(row['description'])
                
                # Status dropdown, notes input and apply button row
                st.markdown("<br>", unsafe_allow_html=True)
                col_sel, col_notes, col_btn = st.columns([2, 3, 1])
                with col_sel:
                    current_status = row['status']
                    if current_status not in status_opts:
                        current_status = "New"
                    idx_status = status_opts.index(current_status)
                    
                    st.selectbox(
                        "Application Status",
                        options=status_opts,
                        index=idx_status,
                        key=f"{key_prefix}_status",
                        on_change=update_db,
                        args=(url, key_prefix)
                    )
                    if row['applied_date']:
                        st.caption(f"🗓️ Applied on: {row['applied_date']}")
                        
                with col_notes:
                    st.text_input(
                        "Application Notes",
                        value=row['notes'],
                        key=f"{key_prefix}_notes",
                        on_change=update_db,
                        args=(url, key_prefix),
                        placeholder="Enter notes about interview, contacts, etc."
                    )
                    
                with col_btn:
                    # Vertical spacer to align button
                    st.write("")
                    st.write("")
                    st.link_button("Apply ↗", url, use_container_width=True)

with tab_settings:
    st.markdown("### ⚙️ Pipeline Configurations")
    st.write("Customize your job search query, scoring rules, and keyword preferences. These values are saved to the database and will be used by the scraper (both locally and on GitHub Actions).")
    st.markdown("---")
    
    # Load current configuration
    current_config = load_config()
    
    # Create forms/columns
    col_search, col_notif = st.columns(2)
    with col_search:
        st.subheader("🔍 Search Target")
        new_search_term = st.text_input("Search Term", value=current_config.get("search_term", "software engineer"))
        new_location = st.text_input("Location", value=current_config.get("location", "United States"))
        new_results_wanted = st.number_input("Results wanted per source", min_value=1, max_value=200, value=current_config.get("results_wanted", 50))
        
    with col_notif:
        st.subheader("🔔 Alerts & Notifications")
        new_min_notification_score = st.slider("Minimum score for Telegram/Discord alerts", min_value=0, max_value=100, value=current_config.get("min_notification_score", 85))
        new_salary_threshold = st.number_input("Salary Bonus Threshold ($)", min_value=10000, max_value=500000, value=current_config.get("salary_threshold", 120000), step=5000)
        
    st.markdown("---")
    st.subheader("🔢 Scoring Parameters")
    
    col_w1, col_w2, col_w3 = st.columns(3)
    with col_w1:
        st.markdown("**Bonuses**")
        new_score_remote_bonus = st.number_input("Remote suitability bonus", value=current_config.get("score_remote_bonus", 10))
        new_score_tech_bonus = st.number_input("Tech stack match bonus", value=current_config.get("score_tech_bonus", 8))
        new_score_senior_bonus = st.number_input("Senior/Lead title bonus", value=current_config.get("score_senior_bonus", 5))
        
    with col_w2:
        st.markdown("**Company Bonuses**")
        new_score_top_tier_bonus = st.number_input("Top-tier company bonus", value=current_config.get("score_top_tier_bonus", 5))
        new_score_startup_bonus = st.number_input("Startup mentions bonus", value=current_config.get("score_startup_bonus", 4))
        new_score_salary_bonus = st.number_input("High salary bonus", value=current_config.get("score_salary_bonus", 3))
        
    with col_w3:
        st.markdown("**Penalties**")
        new_score_contract_penalty = st.number_input("Contract listing penalty", value=current_config.get("score_contract_penalty", -10))
        new_score_junior_java_penalty = st.number_input("Junior Java penalty", value=current_config.get("score_junior_java_penalty", -8))
        new_score_remote_false_penalty = st.number_input("Explicit non-remote penalty", value=current_config.get("score_remote_false_penalty", -5))
        
    st.markdown("---")
    st.subheader("📝 Keywords & Lists")
    
    new_tech_keywords = st.text_area(
        "Technology Stack Keywords (comma-separated)",
        value=", ".join(current_config.get("tech_keywords", []))
    )
    
    new_top_tier_companies = st.text_area(
        "Top-Tier Target Companies (comma-separated, lowercase)",
        value=", ".join(current_config.get("top_tier_companies", []))
    )
    
    col_k1, col_k2 = st.columns(2)
    with col_k1:
        new_senior_title_keywords = st.text_area(
            "Seniority Title Keywords (comma-separated)",
            value=", ".join(current_config.get("senior_title_keywords", []))
        )
    with col_k2:
        new_startup_keywords = st.text_area(
            "Startup Indicators (comma-separated)",
            value=", ".join(current_config.get("startup_keywords", []))
        )
        
    # Helper parser
    def parse_csv_list(text):
        return [x.strip().lower() for x in text.split(",") if x.strip()]
        
    st.markdown("<br>", unsafe_allow_html=True)
    col_act1, col_act2 = st.columns(2)
    with col_act1:
        if st.button("💾 Save Configurations", use_container_width=True):
            updated_config = {
                "search_term": new_search_term.strip(),
                "location": new_location.strip(),
                "results_wanted": int(new_results_wanted),
                "min_notification_score": int(new_min_notification_score),
                "score_remote_bonus": int(new_score_remote_bonus),
                "score_tech_bonus": int(new_score_tech_bonus),
                "score_senior_bonus": int(new_score_senior_bonus),
                "score_top_tier_bonus": int(new_score_top_tier_bonus),
                "score_startup_bonus": int(new_score_startup_bonus),
                "score_salary_bonus": int(new_score_salary_bonus),
                "score_contract_penalty": int(new_score_contract_penalty),
                "score_junior_java_penalty": int(new_score_junior_java_penalty),
                "score_remote_false_penalty": int(new_score_remote_false_penalty),
                "tech_keywords": parse_csv_list(new_tech_keywords),
                "senior_title_keywords": parse_csv_list(new_senior_title_keywords),
                "top_tier_companies": parse_csv_list(new_top_tier_companies),
                "startup_keywords": parse_csv_list(new_startup_keywords),
                "salary_threshold": int(new_salary_threshold)
            }
            save_config(updated_config)
            st.cache_data.clear()
            time.sleep(1)
            st.rerun()
            
            
    with col_act2:
        if st.button("🚀 Trigger Scraper Pipeline Now", use_container_width=True):
            import subprocess
            import sys
            import re
            
            # Create a progress bar placeholder
            progress_bar = st.progress(0, text="🚀 Starting Scraper Pipeline...")
            
            try:
                # Launch the pipeline process as a subprocess
                process = subprocess.Popen(
                    [sys.executable, "job_pipeline.py"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    bufsize=1  # Line buffered
                )
                
                # Read stdout in real-time
                start_time = time.time()
                while True:
                    line = process.stdout.readline()
                    if not line and process.poll() is not None:
                        break
                    if line:
                        # Search for progress markers (e.g. [PROGRESS] 50 Scraping Indeed...)
                        match = re.search(r"\[PROGRESS\]\s+(\d+)\s*(.*)", line)
                        if match:
                            percent = int(match.group(1))
                            desc = match.group(2).strip()
                            
                            # Calculate ETA metrics
                            elapsed = time.time() - start_time
                            if percent > 0:
                                est_total = elapsed / (percent / 100.0)
                                remaining = max(0.0, est_total - elapsed)
                                eta_text = f"(Elapsed: {int(elapsed)}s | Remaining: {int(remaining)}s)"
                            else:
                                eta_text = f"(Elapsed: {int(elapsed)}s)"
                                
                            if not desc:
                                desc = f"Running scraper... {percent}%"
                            
                            progress_bar.progress(percent, text=f"⚡ {desc} {eta_text}")
                
                # Get process result
                stdout, stderr = process.communicate()
                
                if process.returncode == 0:
                    progress_bar.progress(100, text="✅ Scraper Pipeline Completed Successfully!")
                    st.success("✅ Scraper Pipeline Completed Successfully!")
                    st.cache_data.clear()
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ Scraper run failed.")
                    st.text_area("Error Logs (stderr)", value=stderr, height=200)
                    st.text_area("Console Output (stdout)", value=stdout, height=200)
            except Exception as e:
                st.error(f"❌ Failed to launch pipeline process: {e}")

with tab_guide:
    st.markdown("## 📖 User Guide & Documentation")
    st.write("Welcome to the Personal Job Tracker & Scraper user guide! This section explains how the system aggregates, standardizes, scores, saves, and automates your job search.")
    
    st.markdown("---")
    
    # Section 1: Scoring Rules
    st.markdown("### 🔢 1. Weighted Relevance Scoring Engine")
    st.write("Each scraped job listing is evaluated dynamically on a **0 to 100 point scale** based on your scoring rules:")
    
    col_bonuses, col_penalties = st.columns(2)
    with col_bonuses:
        st.markdown("#### **📈 Bonuses**")
        st.markdown("""
        * **🌐 Remote Suitability:** Active if 'remote' is in the title, description, or location. *(Default: +10)*
        * **💻 Tech Stack Match:** Match with target technologies (e.g. Python, TypeScript, Go, React, AWS). *(Default: +8)*
        * **👑 Seniority/Lead Role:** Match with senior keyword tags in the job title. *(Default: +5)*
        * **🏢 Top-Tier Companies:** Match with target companies (e.g. Google, Apple, Meta, OpenAI). *(Default: +5)*
        * **🚀 Startup Mentions:** Triggered by startup, funding, or series labels in the description. *(Default: +4)*
        * **💵 Competitive Salary:** Awarded if the minimum salary exceeds the threshold (e.g., $120,000). *(Default: +3)*
        """)
        
    with col_penalties:
        st.markdown("#### **📉 Penalties**")
        st.markdown("""
        * **💼 Contract Roles:** Applied if the title/description mentions 'contract'. *(Default: -10)*
        * **☕ Junior Java Roles:** Triggered by 'java' mentions if the role is not explicitly senior. *(Default: -8)*
        * **🚫 Non-Remote Placement:** Applied if the role is explicitly marked as non-remote or on-site. *(Default: -5)*
        """)
        
    st.markdown("---")
    
    # Section 2: Configuration settings
    st.markdown("### ⚙️ 2. Dynamic Configurations Storage")
    st.markdown("""
    * **Key-Value Settings Table:** All search targets, scoring rules, and keyword lists are saved directly to a database `settings` table (SQLite locally, Supabase PostgreSQL in cloud mode).
    * **Zero Code Changes:** Changing settings in the **Pipeline Settings** tab and clicking **Save Configurations** immediately overrides the defaults without editing files.
    * **Automated Scraper Sync:** Both the local background scraper and the daily GitHub Actions scraper fetch configurations directly from the database at startup, meaning your scraper always runs with your latest settings automatically!
    """)
    
    st.markdown("---")
    
    # Section 3: Webhook alerts
    st.markdown("### 🔔 3. Discord & Telegram Telemetry Webhooks")
    st.write("You can receive instant mobile alerts whenever a new high-scoring job is found by configuring the following environment variables or secrets:")
    st.markdown("""
    #### **📢 Discord Webhooks Setup**
    1. Open your Discord server, click **Channel Settings** -> **Integrations** -> **Create Webhook**.
    2. Copy the Webhook URL.
    3. Save it in the repository secrets or local system env as `DISCORD_WEBHOOK_URL`.
    
    #### **💬 Telegram Bot Setup**
    1. Search for `@BotFather` on Telegram, send `/newbot`, and copy the generated **HTTP Bot Token** (`TELEGRAM_BOT_TOKEN`).
    2. Message `@userinfobot` to retrieve your personal **User Chat ID** (`TELEGRAM_CHAT_ID`).
    3. Save both variables. The bot will automatically message you new job alerts!
    """)
    
    st.markdown("---")
    
    # Section 4: Automation
    st.markdown("### 🔄 4. Scraper Automation Runners")
    
    tab_auto_local, tab_auto_cloud = st.tabs(["💻 Local Background Daemon", "☁️ GitHub Actions Cloud"])
    
    with tab_auto_local:
        st.markdown("#### **Local Background Runner (Windows Task Scheduler)**")
        st.write("You can set up the scraper to run automatically in the background on your local machine using the built-in Windows scripts:")
        st.markdown("""
        1. **Admin Privileges:** Right-click [install_app.bat](file:///c:/Users/Shrish/Downloads/Intern%20projects/Job%20Filter/install_app.bat) and select **Run as Administrator**.
        2. **Automatic Scheduled Task:** The installer registers a task in Windows Task Scheduler named `JobScraper_Daily` to run silently at **8:00 AM** every day.
        3. **Startup Dashboard:** The installer copies [run_dashboard_silent.vbs](file:///c:/Users/Shrish/Downloads/Intern%20projects/Job%20Filter/run_dashboard_silent.vbs) to the Windows Startup folder, ensuring your Streamlit app starts automatically in the background on boot.
        4. **Clean Uninstall:** To remove scheduled tasks and startup entries, run [uninstall_app.bat](file:///c:/Users/Shrish/Downloads/Intern%20projects/Job%20Filter/uninstall_app.bat) as Administrator.
        """)
        
    with tab_auto_cloud:
        st.markdown("#### **Cloud Runner (GitHub Actions)**")
        st.write("The scraper is set up to run automatically in the cloud every day on a schedule:")
        st.markdown("""
        * **Workflow Schedule:** The [.github/workflows/scrape.yml](file:///c:/Users/Shrish/Downloads/Intern%20projects/Job%20Filter/.github/workflows/scrape.yml) workflow runs daily at **8:00 AM UTC** on `ubuntu-latest`.
        * **Output Archives:** Generates and uploads `relevant_jobs.csv` and `all_jobs_combined.csv` as download artifacts.
        * **Auto-Commit Integration:** Automatically commits any new jobs and history logs (`sent_alerts.txt`) back to your GitHub repository to preserve state across runs.
        """)


