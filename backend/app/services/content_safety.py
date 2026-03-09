"""Content safety filter for AI-generated output.

Validates LLM-generated LinkedIn post drafts against a blocklist of
harmful patterns before storing or displaying to users. Aligned with
Microsoft Responsible AI Standard v2 (Reliability & Safety principle).
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# Patterns that should never appear in a professional LinkedIn post.
# Each tuple: (compiled regex, human-readable reason)
_BLOCKED_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?i)\b(kill|murder|attack|bomb|weapon)\b"), "violent language"),
    (re.compile(r"(?i)\b(hate|slur|racial|sexist|homophobic)\b"), "hateful language"),
    (re.compile(r"(?i)\b(password|secret.?key|api.?key|bearer [a-z0-9])\b"), "potential credential leak"),
    (re.compile(r"(?i)ignore (all )?(previous |prior )?instructions"), "prompt injection echo"),
    (re.compile(r"(?i)you are (now )?a|act as|pretend to be"), "role hijack echo"),
    (re.compile(r"(?i)system prompt|instruction hierarchy"), "system prompt leak"),
]

# Max lengths (defense-in-depth, duplicates generate.py limits)
_MAX_BODY = 3000
_MAX_FIRST_COMMENT = 500


class ContentSafetyError(Exception):
    """Raised when generated content fails safety checks."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"Content blocked: {reason}")


def validate_post_content(body: str, first_comment: str = "") -> tuple[str, str]:
    """Validate and sanitize AI-generated post content.

    Returns the (body, first_comment) if safe.
    Raises ContentSafetyError if content matches a blocked pattern.
    """
    # Length clamping
    body = body[:_MAX_BODY]
    first_comment = first_comment[:_MAX_FIRST_COMMENT]

    # Check both fields against blocked patterns
    for text, label in [(body, "body"), (first_comment, "first_comment")]:
        for pattern, reason in _BLOCKED_PATTERNS:
            if pattern.search(text):
                logger.warning(
                    "Content safety: blocked %s — matched '%s' in %s",
                    reason,
                    pattern.pattern,
                    label,
                )
                raise ContentSafetyError(reason)

    return body, first_comment
