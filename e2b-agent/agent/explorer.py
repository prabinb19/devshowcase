"""Repository exploration — clone, read README, walk file tree."""

import os
import subprocess
from pathlib import Path

REPO_DIR = Path("/workspace/repo")
MAX_FILE_ENTRIES = 500

CONFIG_FILES = [
    "package.json",
    "pyproject.toml",
    "Cargo.toml",
    "go.mod",
    "requirements.txt",
    "pom.xml",
]


def explore_repo(repo_url: str, github_token: str) -> dict:
    """Clone a repository and return structured exploration data.

    Returns a dict with repo_url, name, readme, file_tree, and config_files.
    """
    clone_url = repo_url
    if github_token and "github.com" in repo_url:
        clone_url = repo_url.replace(
            "https://github.com", f"https://{github_token}@github.com"
        )

    if REPO_DIR.exists():
        subprocess.run(["rm", "-rf", str(REPO_DIR)], check=True)

    subprocess.run(
        ["git", "clone", "--depth", "1", clone_url, str(REPO_DIR)],
        check=True,
        text=True,
    )

    # Extract repo name from URL
    name = repo_url.rstrip("/").split("/")[-1].removesuffix(".git")

    # Detect default branch
    default_branch = _detect_default_branch()

    # Read README
    readme = _read_readme()

    # Walk file tree
    file_tree = _walk_file_tree()

    # Read config files
    config_files = _read_config_files()

    return {
        "repo_url": repo_url,
        "name": name,
        "default_branch": default_branch,
        "readme": readme,
        "file_tree": file_tree,
        "config_files": config_files,
    }


def _detect_default_branch() -> str:
    """Get the default branch name from the cloned repo."""
    try:
        result = subprocess.run(
            ["git", "-C", str(REPO_DIR), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, check=True,
        )
        return result.stdout.strip() or "main"
    except Exception:
        return "main"


def _read_readme() -> str:
    """Try to read README.md or readme.md from the repo root."""
    for candidate in ["README.md", "readme.md", "Readme.md"]:
        readme_path = REPO_DIR / candidate
        if readme_path.exists():
            return readme_path.read_text(errors="replace")
    return ""


def _walk_file_tree() -> list[str]:
    """Walk the repo and return relative file paths, capped at MAX_FILE_ENTRIES."""
    entries: list[str] = []
    for root, dirs, files in os.walk(REPO_DIR):
        # Skip .git directory
        dirs[:] = [d for d in dirs if d != ".git"]
        for filename in files:
            full_path = Path(root) / filename
            rel_path = str(full_path.relative_to(REPO_DIR))
            entries.append(rel_path)
            if len(entries) >= MAX_FILE_ENTRIES:
                return entries
    return entries


def _read_config_files() -> dict[str, str]:
    """Read known config files from the repo root."""
    configs: dict[str, str] = {}
    for config_name in CONFIG_FILES:
        config_path = REPO_DIR / config_name
        if config_path.exists():
            configs[config_name] = config_path.read_text(errors="replace")
    return configs
