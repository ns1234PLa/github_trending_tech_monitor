import os
import time
import requests
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Missing Supabase credentials in .env file.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

TECH_STACKS = {
    "Framework": ["React", "Vue", "Next.js", "FastAPI", "Django", "Flutter"],
    "Language": ["Python", "TypeScript", "Rust", "Go", "Kotlin"],
    "Database": ["PostgreSQL", "MongoDB", "Redis", "Supabase"],
    "AI/ML": ["PyTorch", "TensorFlow", "LangChain", "XGBoost"]
}

def get_headers():
    headers = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    return headers

def send_discord_notification(top_breakout_repo, total_repos_count):
    """Send a sleek daily digest to Discord."""
    if not DISCORD_WEBHOOK_URL:
        print("ℹ️ No Discord Webhook URL provided. Skipping notification.")
        return

    payload = {
        "username": "GitHub Tech Monitor",
        "avatar_url": "https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png",
        "embeds": [{
            "title": "🚀 Daily GitHub Market Intelligence Digest",
            "color": 5814783,  # Purple accent
            "fields": [
                {
                    "name": "🔥 Top Breakout Project Today",
                    "value": f"**[{top_breakout_repo['repo_name']}]({top_breakout_repo['html_url']})**\n⭐ {top_breakout_repo['stars']:,} stars | 🍴 {top_breakout_repo['forks']:,} forks\n*{top_breakout_repo['description']}*",
                    "inline": False
                },
                {
                    "name": "📊 Total Tracked Ecosystem Volume",
                    "value": f"**{total_repos_count:,}** public repositories across 19 stacks",
                    "inline": True
                }
            ],
            "footer": {"text": f"Automated Pipeline Execution • {datetime.now().strftime('%Y-%m-%d')}"}
        }]
    }
    
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload)
        if response.status_code == 204:
            print("📣 Discord notification sent successfully!")
        else:
            print(f"⚠️ Discord webhook returned status {response.status_code}")
    except Exception as e:
        print(f"⚠️ Failed to send Discord notification: {e}")

def fetch_tech_stack_counts(today_str: str):
    print("🚀 [Pillar 1] Fetching core tech stack metrics...")
    records = []
    total_count = 0

    for category, techs in TECH_STACKS.items():
        for tech in techs:
            url = f"https://api.github.com/search/repositories?q={tech}"
            response = requests.get(url, headers=get_headers())
            
            if response.status_code == 200:
                count = response.json().get("total_count", 0)
                total_count += count
                print(f"  • [{category}] {tech}: {count:,} repos")
                records.append({
                    "snapshot_date": today_str,
                    "tech_name": tech,
                    "category": category,
                    "repo_count": count
                })
            time.sleep(2)

    if records:
        supabase.table("tech_trends").upsert(
            records, on_conflict="snapshot_date, tech_name"
        ).execute()
        print("✅ Core tech stack trends updated!")
    return total_count

def fetch_breakout_repositories(today_str: str):
    print("\n🔥 [Pillar 2] Discovering dynamic breakout repositories...")
    thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    url = f"https://api.github.com/search/repositories?q=created:>{thirty_days_ago}&sort=stars&order=desc&per_page=20"
    
    response = requests.get(url, headers=get_headers())
    if response.status_code != 200:
        return None

    items = response.json().get("items", [])
    records = []

    for item in items:
        records.append({
            "snapshot_date": today_str,
            "repo_name": item["full_name"],
            "owner_login": item["owner"]["login"],
            "stars": item["stargazers_count"],
            "forks": item["forks_count"],
            "open_issues": item["open_issues_count"],
            "primary_language": item["language"] or "Other",
            "html_url": item["html_url"],
            "description": (item["description"] or "")[:250]
        })

    if records:
        supabase.table("trending_repos").upsert(
            records, on_conflict="snapshot_date, repo_name"
        ).execute()
        print(f"✅ Ingested {len(records)} dynamic breakout repos!")
        return records[0]  # Return top breakout repo for notification
    return None

def run_etl_pipeline():
    today_str = datetime.now().strftime("%Y-%m-%d")
    print(f"--- 🔄 Pipeline Execution Date: {today_str} ---")
    total_repos = fetch_tech_stack_counts(today_str)
    top_breakout = fetch_breakout_repositories(today_str)
    
    if top_breakout:
        send_discord_notification(top_breakout, total_repos)
        
    print("\n🎉 ETL Pipeline executed successfully!")

if __name__ == "__main__":
    run_etl_pipeline()