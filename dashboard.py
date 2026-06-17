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

DB_FILE = "job_tracker.db"

# 2. Database Functions
def init_db():
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

# 3. Load Jobs Cache
@st.cache_data(ttl=600)
def load_csv_jobs():
    if not os.path.exists("relevant_jobs.csv"):
        return pd.DataFrame()
    return pd.read_csv("relevant_jobs.csv")

# Initialize Database
init_db()

# Custom CSS styling for premium look
st.markdown("""
<style>
/* Badges */
.score-badge {
    background-color: #2563eb;
    color: white;
    padding: 3px 10px;
    border-radius: 6px;
    font-weight: bold;
    font-size: 0.85rem;
    display: inline-block;
}
.sidebar-metric {
    background-color: rgba(255, 255, 255, 0.05);
    padding: 10px;
    border-radius: 8px;
    border: 1px solid rgba(255, 255, 255, 0.1);
    margin-bottom: 8px;
    text-align: center;
}
</style>
""", unsafe_allow_html=True)

# 4. App Header
st.title("💼 Personal Job Tracker & Dashboard")
st.markdown("Browse scraped roles, score relevance, and track your job applications.")
st.markdown("---")

# Load data files
jobs_df = load_csv_jobs()

if jobs_df.empty:
    st.warning("⚠️ **No jobs database found.** Please run the pipeline script `job_pipeline.py` first to scrape and score some jobs.")
    st.stop()

# Get status tracker data
tracker_df = get_tracker_data()

# Merge jobs with tracker data on url -> job_url
merged_df = jobs_df.merge(tracker_df, left_on='url', right_on='job_url', how='left')
merged_df['status'] = merged_df['status'].fillna('New')
merged_df['notes'] = merged_df['notes'].fillna('')

# 5. Sidebar Navigation & Filters
st.sidebar.header("🔍 Filters")

# Search Query Filter
search_query = st.sidebar.text_input("Search Jobs or Companies", "").strip().lower()

# Minimum Score Filter
min_score = st.sidebar.slider("Minimum Relevance Score", min_value=0, max_value=100, value=0)

# Company Filter
companies = sorted(merged_df['company'].dropna().unique())
selected_companies = st.sidebar.multiselect("Filter by Company", options=companies, default=[])

# Status Filter
status_opts = ["New", "Applied", "Interviewing", "Rejected", "Offered"]
selected_statuses = st.sidebar.multiselect("Filter by Status", options=status_opts, default=status_opts)

# Apply Filters
filtered_df = merged_df[merged_df['score'] >= min_score]

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
                st.markdown(f"<div style='text-align: right;'><span class='score-badge'>Score: {row['score']}</span></div>", unsafe_allow_html=True)
            
            # Badges metadata row
            badges = []
            if pd.notna(row['location']):
                badges.append(f"📍 {row['location']}")
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
