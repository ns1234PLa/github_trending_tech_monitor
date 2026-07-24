import os
import time
import requests
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Missing Supabase credentials in .env file.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

TECH_STACKS = {
    "Framework": ["React", "Vue", "Next.js", "FastAPI", "Django", "Flutter"],
    "Language": ["Python", "TypeScript", "Rust", "Go", "Kotlin"],
    "Database": ["PostgreSQL", "MongoDB", "Redis", "Supabase"],
    "AI/ML": ["PyTorch", "TensorFlow", "LangChain", "XGBoost"]
}

def fetch_github_repo_count(tech_name: str) -> int:
    """Query GitHub Search API for repository count."""
    url = f"https://api.github.com/search/repositories?q={tech_name}"
    headers = {"Accept": "application/vnd.github.v3+json"}
    
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json().get("total_count", 0)
    else:
        print(f"Warning: Failed to fetch data for {tech_name} (Status Code: {response.status_code})")
        return 0

def run_etl_pipeline():
    print("Starting GitHub Tech Stack Ingestion Pipeline...")
    records = []
    today = datetime.now().strftime("%Y-%m-%d")

    for category, techs in TECH_STACKS.items():
        for tech in techs:
            count = fetch_github_repo_count(tech)
            print(f"  • [{category}] {tech}: {count:,} repos")
            records.append({
                "snapshot_date": today,
                "tech_name": tech,
                "category": category,
                "repo_count": count
            })
            time.sleep(2)  # Pause for 2 seconds to avoid hitting API rate limits

    if records:
        response = supabase.table("tech_trends").upsert(records, on_conflict="snapshot_date, tech_name").execute()
        print("Data successfully ingested into Supabase!")

if __name__ == "__main__":
    run_etl_pipeline()