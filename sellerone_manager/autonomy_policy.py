from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .paths import get_manager_paths


POLICY_REL_PATH = Path("config") / "manager" / "autonomy_policy.json"

DEFAULT_POLICY: dict[str, Any] = {
    "status": "inactive",
    "mode": "manual",
    "controlled_technical_pause_resume_allowed": False,
    "controlled_technical_pause_requires_controller": False,
    "business_decisions_delegated": False,
}

TECHNICAL_PAUSE_WORDS = (
    "technical pause",
    "scheduler pause",
    "h scheduler",
    "h isolation",
    "pause h",
    "controlled proof",
    "proof window",
    "controlled one-shot",
)

BUSINESS_DECISION_WORDS = (
    "price change",
    "price write",
    "pricing change",
    "publish",
    "sheet write",
    "google sheets write",
    "queue edit",
    "f061 queue",
    "product db alignment",
    "local db alignment",
    "output deletion",
    "purchase commitment",
    "receiving action",
    "send-to-amazon",
    "manual-review exception",
    "entertainment trading",
    "dashboard_yes_no",
)

QUIET_AUTONOMY_PARKED_DECISION_WORDS = BUSINESS_DECISION_WORDS + (
    "ui can replace sheet",
    "operator decision",
    "manual review",
    "business judgement",
    "business judgment",
    "proof window",
    "controlled one-shot",
    "login mode",
    "stax",
    "bbp extension",
    "extension worker",
)


def load_autonomy_policy(root: Path | str | None = None) -> dict[str, Any]:
    paths = get_manager_paths(root)
    path = paths.root / POLICY_REL_PATH
    if not path.exists():
        return dict(DEFAULT_POLICY)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(DEFAULT_POLICY)
    if not isinstance(payload, dict):
        return dict(DEFAULT_POLICY)
    policy = dict(DEFAULT_POLICY)
    policy.update(payload)
    return policy


def controlled_technical_pause_allowed(root: Path | str | None = None) -> bool:
    policy = load_autonomy_policy(root)
    if str(policy.get("status", "")).strip().lower() != "active":
        return False
    if not bool(policy.get("controlled_technical_pause_resume_allowed", False)):
        return False
    if bool(policy.get("business_decisions_delegated", False)):
        return False
    if bool(policy.get("controlled_technical_pause_requires_controller", False)):
        return h_maintenance_controller_installed(root)
    return True


def quiet_autonomy_active(root: Path | str | None = None) -> bool:
    policy = load_autonomy_policy(root)
    return (
        str(policy.get("status", "")).strip().lower() == "active"
        and str(policy.get("mode", "")).strip().lower() == "quiet_autonomy"
        and not bool(policy.get("business_decisions_delegated", False))
    )


def is_quiet_autonomy_parked_decision_text(text: str) -> bool:
    lower = str(text or "").lower()
    return any(word in lower for word in QUIET_AUTONOMY_PARKED_DECISION_WORDS)


def h_maintenance_controller_installed(root: Path | str | None = None) -> bool:
    paths = get_manager_paths(root)
    path = paths.root / "out" / "locks" / "h_maintenance_controller_install_status.json"
    if not path.exists():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(payload, dict):
        return False
    return _truthy(payload.get("installed")) and _truthy(payload.get("success"))


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "ok", "installed", "success"}


def is_controlled_technical_pause_text(text: str) -> bool:
    lower = str(text or "").lower()
    if not any(word in lower for word in TECHNICAL_PAUSE_WORDS):
        return False
    return not any(word in lower for word in BUSINESS_DECISION_WORDS)
