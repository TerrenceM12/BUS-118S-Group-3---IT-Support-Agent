"""Mock Jira adapter.

Persists tickets to ``data/tickets.json``. ``create_ticket`` returns a
ticket dict with the same shape Jira's REST API returns for
``POST /rest/api/3/issue`` (key, id, fields), so a real adapter can
replace this without changes upstream.
"""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import settings

_TICKETS_PATH = settings.data_dir / "tickets.json"
_lock = threading.Lock()


def _read() -> dict[str, Any]:
    if not _TICKETS_PATH.exists():
        return {"tickets": []}
    return json.loads(_TICKETS_PATH.read_text(encoding="utf-8"))


def _write(data: dict[str, Any]) -> None:
    _TICKETS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _TICKETS_PATH.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def create_ticket(
    *,
    summary: str,
    description: str,
    assignee: str,
    priority: str = "P3",
    labels: list[str] | None = None,
    project_key: str = "ITACCESS",
) -> dict[str, Any]:
    """Create a ticket and return the API-shaped record."""
    with _lock:
        data = _read()
        seq = len(data["tickets"]) + 1
        key = f"{project_key}-{seq}"
        ticket = {
            "id": str(uuid.uuid4()),
            "key": key,
            "fields": {
                "summary": summary,
                "description": description,
                "assignee": {"emailAddress": assignee},
                "priority": {"name": priority},
                "labels": labels or [],
                "status": {"name": "Open"},
                "created": datetime.now(timezone.utc).isoformat(),
            },
        }
        data["tickets"].append(ticket)
        _write(data)
        return ticket


def list_tickets(limit: int = 50) -> list[dict[str, Any]]:
    return list(reversed(_read()["tickets"]))[:limit]


def get_ticket(key: str) -> dict[str, Any] | None:
    for t in _read()["tickets"]:
        if t["key"] == key:
            return t
    return None
