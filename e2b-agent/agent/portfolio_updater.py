"""Create a PR to add the project to a portfolio site repository."""

import json
import re
import subprocess
from datetime import date
from pathlib import Path

import httpx

PORTFOLIO_DIR = Path("/workspace/portfolio")


def update_portfolio(
    exploration: dict, images: list[dict], mission: dict
) -> str | None:
    """Clone the portfolio repo, add a project entry, and open a PR.

    Returns the PR URL on success, or None on failure.
    """
    portfolio_repo = mission.get("portfolio_repo")
    portfolio_owner = mission.get("portfolio_owner")
    github_token = mission.get("github_token", "")

    if not portfolio_repo or not portfolio_owner or not github_token:
        return None

    try:
        return _do_update(exploration, images, portfolio_owner, portfolio_repo, github_token)
    except Exception:
        return None


def _do_update(
    exploration: dict,
    images: list[dict],
    owner: str,
    repo: str,
    token: str,
) -> str | None:
    """Perform the clone, commit, push, and PR creation."""
    clone_url = f"https://{token}@github.com/{owner}/{repo}.git"

    if PORTFOLIO_DIR.exists():
        subprocess.run(["rm", "-rf", str(PORTFOLIO_DIR)], check=True)

    subprocess.run(
        ["git", "clone", "--depth", "1", clone_url, str(PORTFOLIO_DIR)],
        check=True, capture_output=True, text=True,
    )

    project_name = exploration.get("name", "project")
    branch = f"add-project-{_sanitize(project_name)}"

    subprocess.run(
        ["git", "checkout", "-b", branch],
        cwd=str(PORTFOLIO_DIR), check=True, capture_output=True, text=True,
    )

    # Build project entry
    entry = _build_entry(exploration, images)

    # Find or create projects file
    projects_file = _find_projects_file()
    _append_entry(projects_file, entry)

    # Commit and push
    subprocess.run(["git", "add", "-A"], cwd=str(PORTFOLIO_DIR), check=True)
    subprocess.run(
        ["git", "commit", "-m", f"Add project: {project_name}"],
        cwd=str(PORTFOLIO_DIR), check=True, capture_output=True, text=True,
    )
    subprocess.run(
        ["git", "push", "-u", "origin", branch],
        cwd=str(PORTFOLIO_DIR), check=True, capture_output=True, text=True,
    )

    # Create PR via GitHub API
    return _create_pr(owner, repo, token, project_name, branch)


def _sanitize(name: str) -> str:
    """Sanitize a string for use as a git branch name."""
    return re.sub(r"[^a-zA-Z0-9_-]", "-", name).strip("-").lower()


def _build_entry(exploration: dict, images: list[dict]) -> dict:
    """Build a project entry dict."""
    readme = exploration.get("readme", "")
    description = ""
    for line in readme.split("\n"):
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and not stripped.startswith("!"):
            description = stripped
            break

    return {
        "name": exploration.get("name", "project"),
        "description": description,
        "url": exploration.get("repo_url", ""),
        "images": [img["url"] for img in images],
        "date": str(date.today()),
    }


def _find_projects_file() -> Path:
    """Locate or create the projects JSON file."""
    candidates = [
        PORTFOLIO_DIR / "_data" / "projects.json",
        PORTFOLIO_DIR / "projects.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate

    # Default: create _data/projects.json
    default = PORTFOLIO_DIR / "_data" / "projects.json"
    default.parent.mkdir(parents=True, exist_ok=True)
    default.write_text("[]")
    return default


def _append_entry(projects_file: Path, entry: dict) -> None:
    """Append a project entry to the projects JSON file."""
    data = json.loads(projects_file.read_text())
    if not isinstance(data, list):
        data = []
    data.append(entry)
    projects_file.write_text(json.dumps(data, indent=2))


def _create_pr(
    owner: str, repo: str, token: str, project_name: str, branch: str
) -> str | None:
    """Create a pull request via the GitHub API."""
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    body = {
        "title": f"Add project: {project_name}",
        "body": f"Automated PR to add **{project_name}** to the portfolio.\n\nCreated by DevShowcase agent.",
        "head": branch,
        "base": "main",
    }
    resp = httpx.post(url, json=body, headers=headers, timeout=15)
    if resp.status_code in (200, 201):
        return resp.json().get("html_url")
    return None
