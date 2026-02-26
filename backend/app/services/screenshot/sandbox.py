"""Sandbox screenshot capture — MVP stub with project card fallback.

Future plan:
    When E2B Desktop + custom template is available, this module will:
    1. Spin up an E2B Desktop sandbox with a browser (Chromium)
    2. Install project dependencies and start the dev server
    3. Use Playwright to navigate to localhost:<port> and take a screenshot
    4. Upload the screenshot to R2

    Only this file needs to change — the capture node routes here based
    on screenshot_strategy="sandbox".
"""

from __future__ import annotations

import logging

from app.services.screenshot.project_card import generate_project_card

logger = logging.getLogger(__name__)


def capture_sandbox_screenshot(
    name: str,
    description: str,
    tech_stack: list[str],
    stars: int,
    language: str,
    key_features: list[str],
    run_id: str,
) -> list[dict]:
    """Capture a sandbox screenshot of a running project.

    MVP: Falls back to generate_project_card() since E2B Desktop
    is not yet configured. The sandbox fields (run_command, install_command,
    expected_port) are accepted by the capture node but not used here yet.
    """
    logger.info(
        "Sandbox screenshot not available (MVP), falling back to project card for %s",
        name,
    )
    return generate_project_card(
        name=name,
        description=description,
        tech_stack=tech_stack,
        stars=stars,
        language=language,
        key_features=key_features,
        run_id=run_id,
    )
