import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

# Logging setup with clean timestamping
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("TechMonitorETL")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

if not SUPABASE_URL or not SUPABASE_KEY:
    logger.critical(
        "❌ Missing required Supabase environment variables (SUPABASE_URL, SUPABASE_KEY)."
    )
    raise ValueError("Missing Supabase credentials in environment configuration.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

TECH_STACKS: Dict[str, List[str]] = {
    "Framework": ["React", "Vue", "Next.js", "FastAPI", "Django", "Flutter"],
    "Language": ["Python", "TypeScript", "Rust", "Go", "Kotlin"],
    "Database": ["PostgreSQL", "MongoDB", "Redis", "Supabase"],
    "AI/ML": ["PyTorch", "TensorFlow", "LangChain", "XGBoost"],
}


def get_github_headers() -> Dict[str, str]:
    """Generates standard GitHub API headers with authentication if available."""
    headers = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    else:
        logger.warning(
            "⚠️ GITHUB_TOKEN not provided. Rate limits will be restricted to 60 req/hr."
        )
    return headers


def execute_github_request(
    url: str, max_retries: int = 3
) -> Optional[requests.Response]:
    """Executes a GET request against the GitHub API with exponential backoff retry logic."""
    headers = get_github_headers()

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code == 200:
                return response
            elif response.status_code == 403:
                logger.error(
                    "❌ GitHub API Rate limit exceeded or access forbidden."
                )
                break
            else:
                logger.warning(
                    f"⚠️ GitHub API returned HTTP {response.status_code} (Attempt {attempt}/{max_retries})"
                )
        except requests.exceptions.RequestException as exc:
            logger.warning(
                f"⚠️ Request exception occurred: {exc} (Attempt {attempt}/{max_retries})"
            )

        if attempt < max_retries:
            time.sleep(2**attempt)  # Exponential backoff: 2s, 4s, 8s...

    return None


def send_discord_notification(
    top_breakout_repo: Dict[str, Any], total_repos_count: int
) -> None:
    """Dispatches a structured digest payload to a Discord Webhook channel."""
    if not DISCORD_WEBHOOK_URL:
        logger.info(
            "ℹ️ DISCORD_WEBHOOK_URL not configured. Skipping Discord alert."
        )
        return

    # Sanitize inputs
    repo_desc = top_breakout_repo.get("description") or "No description provided."
    if len(repo_desc) > 200:
        repo_desc = f"{repo_desc[:197]}..."

    embed_payload = {
        "username": "GitHub Tech Monitor",
        "avatar_url": "https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png",
        "embeds": [
            {
                "title": "🚀 Daily GitHub Market Intelligence Digest",
                "color": 5814783,  # Purple accent
                "fields": [
                    {
                        "name": "🔥 Top Breakout Project Today",
                        "value": (
                            f"**[{top_breakout_repo['repo_name']}]({top_breakout_repo['html_url']})**\n"
                            f"⭐ {top_breakout_repo['stars']:,} stars | 🍴 {top_breakout_repo['forks']:,} forks\n"
                            f"_{repo_desc}_"
                        ),
                        "inline": False,
                    },
                    {
                        "name": "📊 Tracked Ecosystem Volume",
                        "value": f"**{total_repos_count:,}** public repositories across 19 technologies",
                        "inline": True,
                    },
                ],
                "footer": {
                    "text": f"Automated Pipeline Execution • {datetime.now(timezone.utc).strftime('%Y-%m-%d UTC')}"
                },
            }
        ],
    }

    try:
        response = requests.post(
            DISCORD_WEBHOOK_URL, json=embed_payload, timeout=10
        )
        if response.status_code in [200, 204]:
            logger.info("📣 Discord digest dispatched successfully.")
        else:
            logger.error(
                f"❌ Discord notification failed with HTTP {response.status_code}: {response.text}"
            )
    except Exception as exc:
        logger.error(
            f"❌ Exception occurred while dispatching Discord alert: {exc}"
        )


def fetch_tech_stack_counts(today_str: str) -> int:
    """[Pillar 1] Queries GitHub for aggregate counts per tech stack and upserts records to Supabase."""
    logger.info("🚀 [Pillar 1/2] Fetching core tech stack volume metrics...")
    records: List[Dict[str, Any]] = []
    total_count = 0

    for category, techs in TECH_STACKS.items():
        for tech in techs:
            url = f"https://api.github.com/search/repositories?q={tech}"
            response = execute_github_request(url)

            if response:
                count = response.json().get("total_count", 0)
                total_count += count
                logger.info(f"   • [{category}] {tech:<12}: {count:>10,} repos")

                records.append(
                    {
                        "snapshot_date": today_str,
                        "tech_name": tech,
                        "category": category,
                        "repo_count": count,
                    }
                )

            # Polite delay between API calls
            time.sleep(1.5)

    if records:
        try:
            supabase.table("tech_trends").upsert(
                records, on_conflict="snapshot_date, tech_name"
            ).execute()
            logger.info(
                f"✅ Upserted {len(records)} tech trend records to Supabase."
            )
        except Exception as exc:
            logger.error(
                f"❌ Database error during tech_trends upsertion: {exc}"
            )

    return total_count


def fetch_breakout_repositories(today_str: str) -> Optional[Dict[str, Any]]:
    """[Pillar 2] Discovers top breakout repositories created within the past 30 days."""
    logger.info("🔥 [Pillar 2/2] Ingesting dynamic breakout repositories...")

    thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    url = f"https://api.github.com/search/repositories?q=created:>{thirty_days_ago}&sort=stars&order=desc&per_page=20"

    response = execute_github_request(url)
    if not response:
        logger.error(
            "❌ Failed to retrieve breakout repositories from GitHub."
        )
        return None

    items = response.json().get("items", [])
    records: List[Dict[str, Any]] = []

    for item in items:
        records.append(
            {
                "snapshot_date": today_str,
                "repo_name": item["full_name"],
                "owner_login": item["owner"]["login"],
                "stars": item["stargazers_count"],
                "forks": item["forks_count"],
                "open_issues": item["open_issues_count"],
                "primary_language": item["language"] or "Other",
                "html_url": item["html_url"],
                "description": (item["description"] or "")[:250],
            }
        )

    if records:
        try:
            supabase.table("trending_repos").upsert(
                records, on_conflict="snapshot_date, repo_name"
            ).execute()
            logger.info(
                f"✅ Upserted {len(records)} breakout repositories to Supabase."
            )
            return records[0]  # Return top breakout repository
        except Exception as exc:
            logger.error(
                f"❌ Database error during trending_repos upsertion: {exc}"
            )

    return None


def run_etl_pipeline() -> None:
    """Main Orchestrator function."""
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    logger.info("=" * 60)
    logger.info(f"🔄 Starting Tech Monitor Pipeline | Date: {today_str}")
    logger.info("=" * 60)

    try:
        total_repos = fetch_tech_stack_counts(today_str)
        top_breakout = fetch_breakout_repositories(today_str)

        if top_breakout:
            send_discord_notification(top_breakout, total_repos)

        logger.info("=" * 60)
        logger.info("🎉 Pipeline execution completed successfully.")
        logger.info("=" * 60)

    except Exception as exc:
        logger.critical(
            f"💥 Pipeline terminated due to unhandled exception: {exc}",
            exc_info=True,
        )


if __name__ == "__main__":
    run_etl_pipeline()