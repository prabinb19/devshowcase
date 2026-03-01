"""DevShowcase agent — runs inside E2B sandbox."""

import json
import sys
import traceback

from comms import read_mission, update_progress, set_status
from explorer import explore_repo
from image_extractor import extract_images
from post_generator import generate_post
from portfolio_updater import update_portfolio


def main() -> None:
    try:
        set_status("running")
        mission = read_mission()

        repo_url = mission["repo_url"]
        gemini_api_key = mission["gemini_api_key"]
        github_token = mission.get("github_token", "")

        # Step 1: Explore
        update_progress("exploring", "Cloning and exploring repository...")
        exploration = explore_repo(repo_url, github_token)

        # Step 2: Extract images
        update_progress("extracting_images", "Extracting README images...")
        images = extract_images(exploration.get("readme", ""), repo_url)

        # Step 3: Generate post
        update_progress("generating", "Generating LinkedIn post with Gemini...")
        post = generate_post(exploration, images, gemini_api_key)

        # Step 4: Portfolio update (optional)
        pr_url = None
        if mission.get("portfolio_repo") and mission.get("portfolio_owner"):
            update_progress("portfolio", "Updating portfolio site...")
            pr_url = update_portfolio(exploration, images, mission)

        # Write result
        result = {
            "post_draft": post,
            "images": images,
            "exploration_log": f"Explored {exploration.get('name', 'repo')}: {len(exploration.get('file_tree', []))} files found",
            "portfolio_pr_url": pr_url,
        }

        with open("/output/result.json", "w") as f:
            json.dump(result, f, indent=2)

        set_status("completed")

    except Exception as exc:
        traceback.print_exc()
        set_status("failed", str(exc))
        sys.exit(1)


if __name__ == "__main__":
    main()
