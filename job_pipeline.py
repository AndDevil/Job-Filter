#!/usr/bin/env python3
"""
Job Aggregation Pipeline Script
-------------------------------
Aggregates, standardizes, deduplicates, and filters job listings from:
1. JobHive (Greenhouse, Lever, Ashby, etc.)
2. JobSpy (LinkedIn, Indeed, Glassdoor, Google, ZipRecruiter)
3. JobSeek (jobseek.dev API)

Installation:
    pip install "jobhive-py[parquet]" python-jobspy pandas requests

Note on Python 3.14 / NumPy Compatibility:
    On modern Python versions (e.g., 3.14+), JobSpy's legacy pinned NumPy 1.26.3
    might fail to build from source. To resolve, install using:
        pip install --no-deps python-jobspy
        pip install pandas requests numpy pydantic anyio httpx
"""

import os
import sys
import time

# Reconfigure stdout/stderr to UTF-8 to prevent UnicodeEncodeErrors on Windows
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

import pandas as pd
import requests

# Set pandas options for nice terminal outputs
pd.set_option('display.max_columns', None)
pd.set_option('display.width', 1000)
pd.set_option('display.max_colwidth', 50)

# ==========================================
# CONFIGURATION SECTION
# ==========================================
SEARCH_TERM = "software engineer"
LOCATION = "United States"
RESULTS_WANTED = 50  # per source

# Optional: Require free API key from jobseek.dev. If empty, skips gracefully.
JOBSEEK_API_KEY = ""

# JobHive Optimization:
# The full JobHive dataset snapshot is ~1.36 GB (all.parquet).
# Setting JOBHIVE_USE_FULL_SNAPSHOT = False searches specific major ATS slices.
# Setting it to True downloads the full process-wide cached snapshot.
JOBHIVE_USE_FULL_SNAPSHOT = False
JOBHIVE_ATS_LIST = ["greenhouse", "lever", "ashby", "bamboohr", "workable", "ycombinator"]

# SCORING WEIGHTS & PARAMETERS
SCORE_REMOTE_BONUS = 10
SCORE_TECH_KEYWORDS = ["python", "typescript", "go", "rust", "react", "node", "django", "fastapi", "aws", "docker", "kubernetes"]
SCORE_TECH_BONUS = 8
SCORE_SENIOR_TITLE_KEYWORDS = ["senior", "lead"]
SCORE_SENIOR_BONUS = 5
SCORE_TOP_TIER_COMPANIES = ["google", "microsoft", "apple", "amazon", "meta", "stripe", "anthropic", "openai", "figma", "vercel"]
SCORE_TOP_TIER_BONUS = 5
SCORE_STARTUP_KEYWORDS = ["startup", "series", "funding", "early-stage"]
SCORE_STARTUP_BONUS = 4
SCORE_SALARY_THRESHOLD = 120000
SCORE_SALARY_BONUS = 3

SCORE_CONTRACT_PENALTY = -10
SCORE_JUNIOR_JAVA_PENALTY = -8
SCORE_REMOTE_FALSE_PENALTY = -5

# Common target schema columns (includes 'score')
SCHEMA_COLUMNS = [
    'job_title', 
    'company', 
    'location', 
    'url', 
    'description', 
    'posted', 
    'salary_min', 
    'salary_max', 
    'is_remote', 
    'source',
    'score'
]

# ==========================================
# STANDARDIZATION SCHEMAS
# ==========================================

def standardize_jobhive(df):
    """Maps JobHive columns to standard schema."""
    if df is None or df.empty:
        return pd.DataFrame(columns=SCHEMA_COLUMNS)
    
    standardized = pd.DataFrame()
    standardized['job_title'] = df['title'] if 'title' in df.columns else pd.Series(dtype='object')
    standardized['company'] = df['company'] if 'company' in df.columns else pd.Series(dtype='object')
    standardized['location'] = df['location'] if 'location' in df.columns else pd.Series(dtype='object')
    
    # Prioritize URL column, fallback to apply_url
    if 'url' in df.columns:
        standardized['url'] = df['url']
    elif 'apply_url' in df.columns:
        standardized['url'] = df['apply_url']
    else:
        standardized['url'] = pd.Series(dtype='object')
        
    standardized['description'] = df['description'] if 'description' in df.columns else pd.Series(dtype='object')
    
    # Normalize posted date to YYYY-MM-DD
    if 'posted_at' in df.columns:
        standardized['posted'] = pd.to_datetime(df['posted_at'], errors='coerce', utc=True).dt.strftime('%Y-%m-%d')
    else:
        standardized['posted'] = pd.Series(dtype='object')
        
    standardized['salary_min'] = df['salary_min'] if 'salary_min' in df.columns else pd.Series(dtype='float64')
    standardized['salary_max'] = df['salary_max'] if 'salary_max' in df.columns else pd.Series(dtype='float64')
    
    # Boolean remote indicator
    if 'is_remote' in df.columns:
        standardized['is_remote'] = df['is_remote'].fillna(False).astype(bool)
    else:
        standardized['is_remote'] = standardized['location'].fillna("").astype(str).str.lower().str.contains("remote")
        
    # Append the sub-ATS to the source name
    if 'ats_type' in df.columns:
        standardized['source'] = df['ats_type'].apply(lambda x: f"jobhive/{x}" if pd.notna(x) else "jobhive")
    else:
        standardized['source'] = "jobhive"
        
    # Enforce standard columns
    for col in SCHEMA_COLUMNS:
        if col not in standardized.columns:
            standardized[col] = None
            
    return standardized[SCHEMA_COLUMNS]


def standardize_jobspy(df):
    """Maps JobSpy columns to standard schema."""
    if df is None or df.empty:
        return pd.DataFrame(columns=SCHEMA_COLUMNS)
        
    standardized = pd.DataFrame()
    standardized['job_title'] = df['title'] if 'title' in df.columns else pd.Series(dtype='object')
    standardized['company'] = df['company'] if 'company' in df.columns else pd.Series(dtype='object')
    standardized['location'] = df['location'] if 'location' in df.columns else pd.Series(dtype='object')
    standardized['url'] = df['job_url'] if 'job_url' in df.columns else pd.Series(dtype='object')
    standardized['description'] = df['description'] if 'description' in df.columns else pd.Series(dtype='object')
    
    if 'date_posted' in df.columns:
        standardized['posted'] = pd.to_datetime(df['date_posted'], errors='coerce', utc=True).dt.strftime('%Y-%m-%d')
    else:
        standardized['posted'] = pd.Series(dtype='object')
        
    standardized['salary_min'] = df['min_amount'] if 'min_amount' in df.columns else pd.Series(dtype='float64')
    standardized['salary_max'] = df['max_amount'] if 'max_amount' in df.columns else pd.Series(dtype='float64')
    
    if 'is_remote' in df.columns:
        standardized['is_remote'] = df['is_remote'].fillna(False).astype(bool)
    else:
        standardized['is_remote'] = standardized['location'].fillna("").astype(str).str.lower().str.contains("remote")
        
    if 'site' in df.columns:
        standardized['source'] = df['site'].apply(lambda x: f"jobspy/{x}" if pd.notna(x) else "jobspy")
    else:
        standardized['source'] = "jobspy"
        
    for col in SCHEMA_COLUMNS:
        if col not in standardized.columns:
            standardized[col] = None
            
    return standardized[SCHEMA_COLUMNS]


def standardize_jobseek(df):
    """Maps JobSeek API payload fields to standard schema."""
    if df is None or df.empty:
        return pd.DataFrame(columns=SCHEMA_COLUMNS)
        
    standardized = pd.DataFrame()
    
    def get_candidate_col(candidates, input_df):
        for candidate in candidates:
            if candidate in input_df.columns:
                return input_df[candidate]
        return pd.Series(dtype='object')
        
    standardized['job_title'] = get_candidate_col(['title', 'job_title', 'role'], df)
    standardized['company'] = get_candidate_col(['company', 'company_name', 'company_title'], df)
    standardized['location'] = get_candidate_col(['location', 'job_location'], df)
    standardized['url'] = get_candidate_col(['url', 'link', 'apply_link', 'job_url'], df)
    standardized['description'] = get_candidate_col(['description', 'body', 'job_description'], df)
    
    posted_col = get_candidate_col(['posted', 'posted_at', 'date', 'date_posted', 'created_at'], df)
    if not posted_col.empty and posted_col.notna().any():
        standardized['posted'] = pd.to_datetime(posted_col, errors='coerce', utc=True).dt.strftime('%Y-%m-%d')
    else:
        standardized['posted'] = pd.Series(dtype='object')
        
    standardized['salary_min'] = get_candidate_col(['salary_min', 'min_salary', 'salary_range_min'], df)
    standardized['salary_max'] = get_candidate_col(['salary_max', 'max_salary', 'salary_range_max'], df)
    
    remote_col = get_candidate_col(['is_remote', 'remote', 'workplace'], df)
    if not remote_col.empty and remote_col.notna().any():
        standardized['is_remote'] = remote_col.apply(
            lambda x: True if (isinstance(x, bool) and x) or 
                             (isinstance(x, str) and "remote" in x.lower()) 
                      else False
        )
    else:
        standardized['is_remote'] = standardized['location'].fillna("").astype(str).str.lower().str.contains("remote")
        
    standardized['source'] = "jobseek"
    
    for col in SCHEMA_COLUMNS:
        if col not in standardized.columns:
            standardized[col] = None
            
    return standardized[SCHEMA_COLUMNS]

# ==========================================
# FETCHING FUNCTIONS WITH EXCEPTION HANDLING
# ==========================================

def fetch_jobhive(search_term, location, results_wanted, ats_list, use_full_snapshot):
    """Fetches job details from jobhive dataset snapshots."""
    print("🚀 [JobHive] Starting scraper run...", flush=True)
    try:
        from jobhive import search
        
        if use_full_snapshot:
            print("[JobHive] Loading full dataset (~1.36 GB snapshot). This may take time...", flush=True)
            df = search(query=search_term, location=location, limit=results_wanted)
            print(f"✅ [JobHive] Loaded {len(df)} postings from full snapshot.", flush=True)
            return df
        else:
            print(f"[JobHive] Querying subset ATS systems: {ats_list}", flush=True)
            dfs = []
            for ats in ats_list:
                print(f"  - Scraping ATS: {ats:15}...", end="", flush=True)
                start_time = time.time()
                try:
                    df_ats = search(query=search_term, location=location, ats=ats, limit=results_wanted)
                    dfs.append(df_ats)
                    elapsed = time.time() - start_time
                    print(f" ✅ SUCCESS ({len(df_ats)} jobs in {elapsed:.1f}s)", flush=True)
                except Exception as e:
                    print(f" ❌ FAILED ({e})", flush=True)
            if dfs:
                combined = pd.concat(dfs, ignore_index=True)
                print(f"✅ [JobHive] Total raw jobs gathered: {len(combined)}", flush=True)
                return combined
            return pd.DataFrame()
            
    except Exception as e:
        print(f"❌ [JobHive] General scraper error encountered: {e}", flush=True)
        return pd.DataFrame()


def fetch_jobspy(search_term, location, results_wanted):
    """Scrapes LinkedIn, Indeed, Glassdoor, Google, ZipRecruiter using JobSpy."""
    print("🚀 [JobSpy] Starting scraper run...", flush=True)
    try:
        from jobspy import scrape_jobs
        site_names = ["linkedin", "indeed", "glassdoor", "google", "zip_recruiter"]
        
        print(f"[JobSpy] Querying {site_names} for '{search_term}' in '{location}'...", flush=True)
        df = scrape_jobs(
            site_name=site_names,
            search_term=search_term,
            location=location,
            results_wanted=results_wanted,
            hours_old=72,
            country_indeed="USA"
        )
        print(f"✅ [JobSpy] Successfully scraped {len(df)} jobs.", flush=True)
        return df
    except Exception as e:
        print(f"❌ [JobSpy] General scraper error encountered: {e}", flush=True)
        return pd.DataFrame()


def fetch_jobseek(search_term, api_key, results_wanted):
    """Queries jobseek.dev API using API Key, handles skip gracefully."""
    print("🚀 [JobSeek] Starting scraper run...", flush=True)
    if not api_key:
        print("⚠️ [JobSeek] API Key not provided (empty). Skipping source gracefully.", flush=True)
        return pd.DataFrame()
        
    try:
        url = "https://jobseek.dev/api/v1/jobs/search"
        headers = {
            "X-API-Key": api_key,
            "Accept": "application/json"
        }
        params = {
            "q": search_term,
            "limit": results_wanted,
            "sort": "date"
        }
        print(f"[JobSeek] Querying {url} with term '{search_term}'...", flush=True)
        response = requests.get(url, headers=headers, params=params, timeout=15)
        response.raise_for_status()
        
        payload = response.json()
        if not payload.get("success"):
            print("❌ [JobSeek] API returned failure status in response JSON.", flush=True)
            return pd.DataFrame()
            
        data = payload.get("data", [])
        print(f"✅ [JobSeek] Successfully retrieved {len(data)} jobs.", flush=True)
        return pd.DataFrame(data)
    except Exception as e:
        print(f"❌ [JobSeek] General API client error encountered: {e}", flush=True)
        return pd.DataFrame()

# ==========================================
# PIPELINE POST-PROCESSING
# ==========================================

def score_job(row):
    """Calculates a numeric relevance score (0-100) for a job posting."""
    score = 0
    
    title = str(row.get('job_title', '')).lower()
    description = str(row.get('description', '')).lower()
    location = str(row.get('location', '')).lower()
    company = str(row.get('company', '')).lower()
    
    # 1. Remote Bonus: +10 if "remote" in title, description, or location
    if "remote" in title or "remote" in description or "remote" in location:
        score += SCORE_REMOTE_BONUS
        
    # 2. Tech Keywords: +8 if any of the tech keywords match
    if any(tech in title or tech in description for tech in SCORE_TECH_KEYWORDS):
        score += SCORE_TECH_BONUS
        
    # 3. Seniority: +5 if "senior" or "lead" in title
    if any(kw in title for kw in SCORE_SENIOR_TITLE_KEYWORDS):
        score += SCORE_SENIOR_BONUS
        
    # 4. Top-Tier Company: +5 if company matches top-tier list
    if any(company == company_name or company_name in company for company_name in SCORE_TOP_TIER_COMPANIES):
        score += SCORE_TOP_TIER_BONUS
        
    # 5. Startup indicators: +4 if mentions startup keywords
    if any(kw in description for kw in SCORE_STARTUP_KEYWORDS):
        score += SCORE_STARTUP_BONUS
        
    # 6. High Salary: +3 if salary_min > 120000
    salary_min = row.get('salary_min')
    if pd.notna(salary_min) and float(salary_min) > SCORE_SALARY_THRESHOLD:
        score += SCORE_SALARY_BONUS
        
    # 7. Contract Penalty: -10 if "contract" in title or description
    if "contract" in title or "contract" in description:
        score += SCORE_CONTRACT_PENALTY
        
    # 8. Junior Java: -8 if "java" in text but "senior" is not in title
    if "java" in (title + " " + description) and "senior" not in title:
        score += SCORE_JUNIOR_JAVA_PENALTY
        
    # 9. Explicitly NOT remote: -5 if is_remote is explicitly False
    is_remote_val = row.get('is_remote')
    if is_remote_val is False or (pd.notna(is_remote_val) and str(is_remote_val).lower() == "false"):
        score += SCORE_REMOTE_FALSE_PENALTY
        
    return max(0, min(100, score))


def deduplicate_jobs(df):
    """
    Deduplicates records based on title, company, and location.
    Priority order is maintained as: jobhive > jobseek > jobspy
    """
    if df.empty:
        return df
        
    def get_source_priority(source_val):
        s = str(source_val).lower()
        if s.startswith("jobhive"):
            return 1
        elif s.startswith("jobseek"):
            return 2
        elif s.startswith("jobspy"):
            return 3
        return 4
        
    df = df.copy()
    
    # Populate deduplication metadata
    df["_priority"] = df["source"].apply(get_source_priority)
    df["_norm_title"] = df["job_title"].fillna("").astype(str).str.lower().str.replace(r"\s+", " ", regex=True).str.strip()
    df["_norm_company"] = df["company"].fillna("").astype(str).str.lower().str.replace(r"\s+", " ", regex=True).str.strip()
    df["_norm_location"] = df["location"].fillna("").astype(str).str.lower().str.replace(r"\s+", " ", regex=True).str.strip()
    
    # Sort so high-priority records (1) are placed first
    df = df.sort_values(by="_priority", ascending=True)
    
    # Drop duplicates, retaining the first occurrence
    df = df.drop_duplicates(subset=["_norm_title", "_norm_company", "_norm_location"], keep="first")
    
    # Clean up tracking metadata columns
    df = df.drop(columns=["_priority", "_norm_title", "_norm_company", "_norm_location"])
    return df

# ==========================================
# MAIN ROUTINE ENTRYPOINT
# ==========================================

def main():
    print("=" * 80)
    print("                 JOB FILTER AGGREGATION SERVICE PIPELINE                     ")
    print("=" * 80)
    print(f"SEARCH TERM:    '{SEARCH_TERM}'")
    print(f"LOCATION:       '{LOCATION}'")
    print(f"RESULTS LIMIT:  {RESULTS_WANTED} per source")
    print("-" * 80, flush=True)
    
    # Phase 1: Retrieve raw data
    raw_jh = fetch_jobhive(SEARCH_TERM, LOCATION, RESULTS_WANTED, JOBHIVE_ATS_LIST, JOBHIVE_USE_FULL_SNAPSHOT)
    print()
    raw_js = fetch_jobspy(SEARCH_TERM, LOCATION, RESULTS_WANTED)
    print()
    raw_jk = fetch_jobseek(SEARCH_TERM, JOBSEEK_API_KEY, RESULTS_WANTED)
    
    # Phase 2: Standardize schemas
    print("\n" + "-" * 80)
    print("⚙️ STANDARDIZING SCHEMAS TO COMMON TARGET FORMAT")
    print("-" * 80, flush=True)
    
    df_jh = standardize_jobhive(raw_jh)
    df_js = standardize_jobspy(raw_js)
    df_jk = standardize_jobseek(raw_jk)
    
    print(f"Standardized records - JobHive: {len(df_jh)} | JobSeek: {len(df_jk)} | JobSpy: {len(df_js)}", flush=True)
    
    # Phase 3: Combine and Deduplicate
    print("\n" + "-" * 80)
    print("🔄 MERGING & DEDUPLICATING ENTRIES (Priority: JobHive > JobSeek > JobSpy)")
    print("-" * 80, flush=True)
    
    combined_raw = pd.concat([df_jh, df_jk, df_js], ignore_index=True)
    deduped_all = deduplicate_jobs(combined_raw)
    
    print(f"Raw Combined Total: {len(combined_raw)} records")
    print(f"Deduplicated Total: {len(deduped_all)} records", flush=True)
    
    # Calculate score for ALL jobs in pipeline
    print("🔢 Calculating relevance scores...", flush=True)
    deduped_all["score"] = deduped_all.apply(score_job, axis=1)
    
    # Sort entire dataset by score descending, then date posted descending
    deduped_all = deduped_all.sort_values(by=["score", "posted"], ascending=[False, False])
    
    # Save Combined File
    deduped_all.to_csv("all_jobs_combined.csv", index=False)
    print("Saved aggregated dataset to: 'all_jobs_combined.csv'", flush=True)
    
    # Phase 4: Filter relevant records
    print("\n" + "-" * 80)
    print("🎯 EXTRACTING TOP RELEVANT JOBS (Sorted by Relevance Score Descending)")
    print("-" * 80, flush=True)
    
    # Keep the top 50 jobs
    relevant_jobs = deduped_all.head(50).copy()
    print(f"Extracted top {len(relevant_jobs)} scored jobs.", flush=True)
    
    # Save Relevant File
    relevant_jobs.to_csv("relevant_jobs.csv", index=False)
    print("Saved relevant dataset to: 'relevant_jobs.csv'", flush=True)
    
    # Phase 5: Format terminal displays
    print("\n" + "=" * 80)
    print("🏢 RELEVANT COMPANIES (from top 50 jobs)")
    print("=" * 80)
    if not relevant_jobs.empty:
        unique_companies = sorted(relevant_jobs["company"].dropna().unique())
        for idx, company in enumerate(unique_companies, 1):
            print(f"{idx:3}. {company}")
    else:
        print("(No relevant companies found)")
        
    print("\n" + "=" * 80)
    print("💼 RELEVANT JOBS (Top 50 Scored)")
    print("=" * 80)
    if not relevant_jobs.empty:
        table_subset = relevant_jobs[['score', 'job_title', 'company', 'location', 'url']]
        print(table_subset.to_string(index=False))
    else:
        print("(No relevant jobs found)")
        
    print("\n" + "=" * 80)
    print("🎉 JOB FILTER PIPELINE EXECUTION COMPLETE")
    print("=" * 80, flush=True)

if __name__ == "__main__":
    main()
