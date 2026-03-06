"""Structured audit logging for security-sensitive events.

Logs are emitted as JSON to a dedicated ``audit`` logger so they can be
routed to a SIEM or log aggregator independently of application logs.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

_logger = logging.getLogger("audit")


def _emit(event_type: str, **fields: Any) -> None:
    """Write a structured JSON audit log entry."""
    entry = {
        "event": event_type,
        "ts": time.time(),
        **{k: v for k, v in fields.items() if v is not None},
    }
    _logger.info(json.dumps(entry, default=str))


def log_auth_event(
    *,
    action: str,
    github_id: str = "",
    success: bool,
    reason: str = "",
    ip: str = "",
) -> None:
    """Log authentication attempts (success and failure)."""
    _emit(
        "auth",
        action=action,
        github_id=github_id,
        success=success,
        reason=reason,
        ip=ip,
    )


def log_publish_event(
    *,
    github_id: str,
    draft_id: str,
    success: bool,
    error: str = "",
) -> None:
    """Log LinkedIn publish actions."""
    _emit(
        "publish",
        github_id=github_id,
        draft_id=draft_id,
        success=success,
        error=error,
    )


def log_token_event(
    *,
    action: str,
    github_id: str,
    platform: str = "linkedin",
) -> None:
    """Log token lifecycle events (store, refresh, delete)."""
    _emit(
        "token",
        action=action,
        github_id=github_id,
        platform=platform,
    )
