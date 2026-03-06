"""Sandbox screenshot capture via E2B Desktop.

Spins up a virtual desktop sandbox, clones the repo, installs deps,
starts the dev server, opens a browser, and captures a screenshot
of the running app. Falls back to project card on any failure.
"""

from __future__ import annotations

import logging
import time
from typing import Callable

from app.config import settings
from app.services.image_processor import get_dimensions, process_image, validate_image
from app.services.r2_storage import upload_image
from app.services.screenshot.project_card import generate_project_card

logger = logging.getLogger(__name__)

_POLL_INTERVAL = 3  # seconds between port-ready checks
_PORT_TIMEOUT = 60  # max seconds to wait for dev server
_RENDER_WAIT = 3  # seconds to wait after opening browser


def capture_sandbox_screenshot(
    name: str,
    description: str,
    tech_stack: list[str],
    stars: int,
    language: str,
    key_features: list[str],
    run_id: str,
    repo_url: str = "",
    run_command: str = "",
    install_command: str = "",
    expected_port: int | None = None,
    on_stream_url: Callable[[str], None] | None = None,
) -> list[dict]:
    """Capture a screenshot of the project running in an E2B Desktop sandbox.

    Falls back to generate_project_card() on any failure — never crashes
    the pipeline.
    """
    card_kwargs = {
        "name": name,
        "description": description,
        "tech_stack": tech_stack,
        "stars": stars,
        "language": language,
        "key_features": key_features,
        "run_id": run_id,
    }

    def _fallback(reason: str) -> list[dict]:
        logger.info("Sandbox fallback (%s) for %s — using project card", reason, name)
        return generate_project_card(**card_kwargs)

    # --- Guard checks ---
    if not repo_url:
        return _fallback("no repo_url")
    if not run_command:
        return _fallback("no run_command")
    if not expected_port:
        return _fallback("no expected_port")
    if not settings.e2b_api_key:
        return _fallback("no E2B API key")

    # --- Lazy import ---
    try:
        from e2b_desktop import Sandbox  # type: ignore[import-untyped]
    except ImportError:
        return _fallback("e2b_desktop not installed")

    # --- Build clone URL (inject token for private repos) ---
    clone_url = repo_url
    if settings.github_token and "github.com" in repo_url:
        clone_url = repo_url.replace(
            "https://github.com/",
            f"https://{settings.github_token}@github.com/",
        )

    desktop = None
    try:
        logger.info("Creating E2B Desktop sandbox for %s", name)
        create_kwargs: dict = {
            "api_key": settings.e2b_api_key,
            "resolution": (1280, 800),
            "timeout": 300,
            "envs": {
                "CI": "true",
                "BROWSER": "none",
                "GITHUB_TOKEN": settings.github_token,
            },
        }
        if settings.e2b_template_id:
            create_kwargs["template"] = settings.e2b_template_id

        desktop = Sandbox.create(**create_kwargs)

        # Start live stream if callback provided
        if on_stream_url is not None:
            try:
                desktop.stream.start(require_auth=True)
                auth_key = desktop.stream.get_auth_key()
                url = desktop.stream.get_url(auth_key=auth_key, view_only=True)
                on_stream_url(url)
            except Exception as exc:
                logger.warning("Failed to start desktop stream: %s", exc)

        # Clone repo
        logger.info("Cloning %s", repo_url)
        result = desktop.commands.run(
            f"git clone --depth 1 {clone_url} /home/user/project",
            timeout=120,
        )
        if result.exit_code != 0:
            return _fallback(f"git clone failed: {result.stderr[:200]}")

        # Install dependencies
        if install_command:
            logger.info("Installing deps: %s", install_command)
            result = desktop.commands.run(
                install_command,
                cwd="/home/user/project",
                timeout=120,
            )
            if result.exit_code != 0:
                return _fallback(f"install failed: {result.stderr[:200]}")

        # Start dev server in background
        logger.info("Starting dev server: %s", run_command)
        desktop.commands.run(
            run_command,
            cwd="/home/user/project",
            background=True,
        )

        # Wait for port to be ready
        logger.info("Waiting for port %d", expected_port)
        port_ready = False
        elapsed = 0.0
        while elapsed < _PORT_TIMEOUT:
            check = desktop.commands.run(
                f"curl -s -o /dev/null -w '%{{http_code}}' http://localhost:{expected_port}",
                timeout=10,
            )
            if check.exit_code == 0 and check.stdout.strip() not in ("", "000"):
                port_ready = True
                break
            time.sleep(_POLL_INTERVAL)
            elapsed += _POLL_INTERVAL

        if not port_ready:
            return _fallback(f"port {expected_port} not ready after {_PORT_TIMEOUT}s")

        # Open browser and wait for render
        logger.info("Opening browser at http://localhost:%d", expected_port)
        desktop.open(f"http://localhost:{expected_port}")
        time.sleep(_RENDER_WAIT)

        # Take screenshot
        logger.info("Taking screenshot")
        screenshot_bytes = desktop.screenshot()

        if not screenshot_bytes or not validate_image(screenshot_bytes):
            return _fallback("screenshot invalid or empty")

        # Process and upload
        processed = process_image(screenshot_bytes, max_width=1280, max_height=800)
        width, height = get_dimensions(processed)
        url = upload_image(processed, run_id, "sandbox_screenshot.png")

        logger.info("Sandbox screenshot uploaded: %s", url)
        return [{
            "url": url,
            "alt_text": f"Screenshot of {name} running in sandbox",
            "source": "sandbox",
            "width": width,
            "height": height,
        }]

    except Exception as exc:
        logger.error("Sandbox screenshot failed: %s", exc)
        return _fallback(f"exception: {exc}")

    finally:
        if desktop is not None:
            try:
                desktop.kill()
            except Exception:
                logger.warning("Failed to kill sandbox for %s", name)
