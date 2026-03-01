"""File-based IPC helpers for communicating with the host."""

import json
import time
import uuid
from pathlib import Path

COMMS_DIR = Path("/comms")


def read_mission() -> dict:
    """Read the mission definition from /comms/mission.json."""
    mission_path = COMMS_DIR / "mission.json"
    if not mission_path.exists():
        raise FileNotFoundError("No mission.json found in /comms/")
    with open(mission_path, "r") as f:
        return json.load(f)


def update_progress(stage: str, message: str) -> None:
    """Write current progress to /comms/progress.json."""
    payload = {
        "stage": stage,
        "message": message,
        "timestamp": time.time(),
    }
    with open(COMMS_DIR / "progress.json", "w") as f:
        json.dump(payload, f, indent=2)


def set_status(status: str, error: str = "") -> None:
    """Write agent status to /comms/status.json."""
    payload = {
        "status": status,
        "error": error,
        "timestamp": time.time(),
    }
    with open(COMMS_DIR / "status.json", "w") as f:
        json.dump(payload, f, indent=2)


def ask_question(
    text: str, options: list[str] | None = None, timeout: int = 300
) -> str:
    """Ask the host a question and poll for an answer.

    Writes the question to /comms/question.json, then polls
    /comms/answer.json every 2 seconds until a matching answer
    appears or the timeout is reached.

    Returns the answer text, or an empty string on timeout.
    """
    question_id = str(uuid.uuid4())
    question_payload = {
        "question_id": question_id,
        "text": text,
        "options": options,
    }
    with open(COMMS_DIR / "question.json", "w") as f:
        json.dump(question_payload, f, indent=2)

    answer_path = COMMS_DIR / "answer.json"
    deadline = time.time() + timeout

    while time.time() < deadline:
        time.sleep(2)
        if answer_path.exists():
            with open(answer_path, "r") as f:
                answer = json.load(f)
            if answer.get("question_id") == question_id:
                return answer.get("answer", "")

    return ""
