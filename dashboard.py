import os
import time
import sqlite3
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
        conn.commit()
        conn.close()

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

