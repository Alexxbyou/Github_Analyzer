"""
GitHub Account Repository Analyzer

Analyzes all repositories under a GitHub account and produces a structured
dataset summarizing activity, contribution volume, repository size, and
technology stack for each repository.

Usage:
    python Script/github_analyzer.py
    python Script/github_analyzer.py --no-cache
    python Script/github_analyzer.py --anonymize
    python Script/github_analyzer.py --exclude repo1 repo2
"""

import argparse
import json
import os
import time

import pandas as pd
from dotenv import load_dotenv
from github import Auth, Github, GithubException
from tqdm import tqdm


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def format_tech_stack(languages: dict, top_n: int = 3) -> str:
    """Format language bytes dict into 'Python (70%), JS (10%)' string."""
    total = sum(languages.values())
    if total == 0:
        return ""
    sorted_langs = sorted(languages.items(), key=lambda x: x[1], reverse=True)[:top_n]
    parts = [f"{lang} ({bytes_count / total * 100:.0f}%)" for lang, bytes_count in sorted_langs]
    return ", ".join(parts)


def load_cache(cache_dir: str, repo_name: str) -> dict | None:
    path = os.path.join(cache_dir, f"{repo_name}.json")
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return None


def save_cache(cache_dir: str, repo_name: str, data: dict) -> None:
    path = os.path.join(cache_dir, f"{repo_name}.json")
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def fetch_repos(user, include_forks: bool = False):
    """Return list of repos owned by the authenticated user."""
    all_repos = list(user.get_repos(affiliation="owner"))
    if include_forks:
        return all_repos
    return [r for r in all_repos if not r.fork]


def analyze_repo(repo) -> dict:
    """Collect all metrics for a single repository."""
    row = {
        "repo_name": repo.name,
        "repo_description": repo.description or "",
        "visibility": "private" if repo.private else "public",
        "repo_size_kb": repo.size,
    }

    # Languages (top 3)
    languages = repo.get_languages()
    row["tech_stack"] = format_tech_stack(languages)

    # Branch count
    row["no_branches"] = len(list(repo.get_branches()))

    # Contributor stats — sum ALL contributors (solo-developed repos)
    row["commits_by_owner"] = 0
    row["lines_added"] = 0
    row["lines_deleted"] = 0

    stats = None
    for _ in range(3):
        stats = repo.get_stats_contributors()
        if stats is not None:
            break
        time.sleep(2)

    if stats:
        for contributor in stats:
            row["commits_by_owner"] += contributor.total
            row["lines_added"] += sum(w.a for w in contributor.weeks)
            row["lines_deleted"] += sum(w.d for w in contributor.weeks)

    # Activity dates (first & last commit, no author filter)
    row["activity_start_date"] = None
    row["activity_end_date"] = None

    try:
        commits = repo.get_commits()
        total_commits = commits.totalCount
        if total_commits > 0:
            row["activity_end_date"] = commits[0].commit.author.date.strftime("%Y-%m-%d")
            row["activity_start_date"] = commits[total_commits - 1].commit.author.date.strftime("%Y-%m-%d")
    except GithubException:
        pass  # empty repo

    return row


def build_dataframe(results: list, anonymize: bool, exclude: list[str]) -> pd.DataFrame:
    """Assemble results into a clean DataFrame."""
    df = pd.DataFrame(results)

    # Derived fields
    df["net_lines_of_code"] = df["lines_added"] - df["lines_deleted"]
    df["activity_start_date"] = pd.to_datetime(df["activity_start_date"])
    df["activity_end_date"] = pd.to_datetime(df["activity_end_date"])
    df["activity_span_days"] = (df["activity_end_date"] - df["activity_start_date"]).dt.days

    # Exclusion flag
    df["excl_line_counts"] = df["repo_name"].isin(exclude)

    # Anonymize
    if anonymize:
        df["repo_name"] = [f"project-{i+1:03d}" for i in range(len(df))]
        df["repo_description"] = ""

    # Column order
    column_order = [
        "repo_name",
        "repo_description",
        "visibility",
        "tech_stack",
        "repo_size_kb",
        "activity_start_date",
        "activity_end_date",
        "activity_span_days",
        "commits_by_owner",
        "lines_added",
        "lines_deleted",
        "net_lines_of_code",
        "no_branches",
        "excl_line_counts",
    ]
    df = df[column_order]

    # Sort and filter
    df = df.sort_values("commits_by_owner", ascending=False).reset_index(drop=True)
    df = df[(df["commits_by_owner"] > 0) & (df["repo_size_kb"] > 0)]

    if anonymize:
        df.drop(columns=["repo_description"], inplace=True)

    return df


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Analyze GitHub account repositories.")
    parser.add_argument("--no-cache", action="store_true", help="Ignore cached results and re-fetch all repos.")
    parser.add_argument("--anonymize", action="store_true", help="Replace repo names with project-001, project-002, ...")
    parser.add_argument("--exclude", nargs="*", default=[], help="Repo names to flag as excl_line_counts.")
    parser.add_argument("--output-dir", default=None, help="Output directory (default: <project_root>/Output).")
    args = parser.parse_args()

    # Resolve project root (Script/ is one level down)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Load .env
    load_dotenv(os.path.join(project_root, ".env"))
    gh_token = os.getenv("GH_TOKEN")
    if not gh_token:
        print("Error: GH_TOKEN not found in .env file")
        return

    # Authenticate
    g = Github(auth=Auth.Token(gh_token))
    user = g.get_user()
    username = user.login

    rate = g.get_rate_limit().rate
    print(f"Authenticated as: {username}")
    print(f"Rate limit: {rate.remaining} / {rate.limit}")

    # Fetch repos
    repos = fetch_repos(user)
    print(f"\nFound {len(repos)} non-fork repos.")

    # Setup dirs
    output_dir = args.output_dir or os.path.join(project_root, "Output")
    cache_dir = os.path.join(output_dir, "cache")
    os.makedirs(cache_dir, exist_ok=True)

    # Analyze each repo
    results = []
    for repo in tqdm(repos, desc="Analyzing repos"):
        if not args.no_cache:
            cached = load_cache(cache_dir, repo.name)
            if cached:
                results.append(cached)
                continue

        row = analyze_repo(repo)
        save_cache(cache_dir, repo.name, row)
        results.append(row)
        time.sleep(0.5)

    # Build DataFrame and export
    df = build_dataframe(results, anonymize=args.anonymize, exclude=args.exclude)

    output_path = os.path.join(output_dir, "github_analysis.csv")
    df.to_csv(output_path, index=False)

    print(f"\nExported to: {output_path}")
    print(f"Shape: {df.shape[0]} repos x {df.shape[1]} columns")
    print(f"Rate limit remaining: {g.get_rate_limit().rate.remaining}")

    # Summary
    active = df[~df["excl_line_counts"]]
    print(f"\nSummary (excluding flagged repos):")
    print(f"  Total commits: {active['commits_by_owner'].sum()}")
    print(f"  Total branches: {active['no_branches'].sum()}")
    print(f"  Net lines of code: {active['net_lines_of_code'].sum()}")


if __name__ == "__main__":
    main()
