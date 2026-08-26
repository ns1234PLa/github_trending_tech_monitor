import logging
import os
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List

import requests
from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("BackfillPipeline")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Missing Supabase credentials in .env file.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Target ecosystem taxonomy
TECH_STACKS: Dict[str, List[str]] = {
    "Framework": ["React", "Vue", "Next.js", "FastAPI", "Django", "Flutter", "Svelte", "Astro"],
    "Language": ["Python", "TypeScript", "Go", "Rust", "Kotlin", "Zig", "Elixir", "Gleam", "Mojo", "Julia"],
    "Database": ["PostgreSQL", "MongoDB", "Redis", "DuckDB", "ClickHouse", "Neo4j", "SurrealDB"],
    "AI/ML": ["PyTorch", "TensorFlow", "XGBoost", "LangChain", "LlamaIndex", "vLLM", "Ollama", "ChromaDB", "Qdrant"],
    "Cloud/DevOps": ["Supabase", "Docker", "Kubernetes", "Terraform"],
}

def get_github_headers() -> Dict[str, str]:
    headers = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    return headers

def run_backfill(start_date_str: str, end_date_str: str):
    start_dt = datetime.strptime(start_date_str, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date_str, "%Y-%m-%d")
    
    current_dt = start_dt
    headers = get_github_headers()

    while current_dt <= end_dt:
        date_str = current_dt.strftime("%Y-%m-%d")
        logger.info(f"--- Processing snapshot for Date: {date_str} ---")
        records: List[Dict[str, Any]] = []

        for category, techs in TECH_STACKS.items():
            for tech in techs:
                # Cumulative repository query up to snapshot date
                query = f"{tech} created:<={date_str}"
                url = f"https://api.github.com/search/repositories?q={query}"

                try:
                    response = requests.get(url, headers=headers, timeout=15)
                    if response.status_code == 200:
                        count = response.json().get("total_count", 0)
                        logger.info(f"[{date_str}] [{category}] {tech:<12}: {count:>10,} repos")
                        records.append({
                            "snapshot_date": date_str,
                            "tech_name": tech,
                            "category": category,
                            "repo_count": count,
                        })
                    elif response.status_code == 403:
                        logger.warning("Rate limit hit! Sleeping for 60 seconds...")
                        time.sleep(60)
                    else:
                        logger.warning(f"Error {response.status_code} for {tech} on {date_str}")
                except Exception as exc:
                    logger.error(f"Failed request for {tech}: {exc}")

                # Stays within GitHub Search API rate limits (30 req/min with token)
                time.sleep(2.0)

        if records:
            try:
                supabase.table("tech_trends").upsert(
                    records, on_conflict="snapshot_date, tech_name"
                ).execute()
                logger.info(f"Successfully upserted {len(records)} records for {date_str}.")
            except Exception as exc:
                logger.error(f"Supabase upsert error on {date_str}: {exc}")

        current_dt += timedelta(days=1)

import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill telemetry data for GitHub Trending Tech Monitor.")
    parser.add_argument("--start", type=str, default=(datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"), help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, default=datetime.now().strftime("%Y-%m-%d"), help="End date (YYYY-MM-DD)")
    
    args = parser.parse_args()
    
    logger.info(f"Initiating historical backfill from {args.start} to {args.end}")
    run_backfill(args.start, args.end)