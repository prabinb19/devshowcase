"""Screenshot capture services — strategy pattern for different screenshot types."""

from app.services.screenshot.project_card import generate_project_card
from app.services.screenshot.readme_images import capture_readme_images
from app.services.screenshot.sandbox import capture_sandbox_screenshot

__all__ = [
    "capture_readme_images",
    "capture_sandbox_screenshot",
    "generate_project_card",
]
