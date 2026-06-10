from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ALLOWED_ACTIONS = {"status", "pause", "resume"}
DEFAULT_TASK_NAME = "SellerOne H Maintenance Controller"
REQUEST_REL_PATH = Path("out") / "locks" / "h_maintenance_request.json"
RESULT_REL_PATH = Path("out") / "locks" / "h_maintenance_controller_last_result.json"
ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,120}$")


def repo_root_from_script() -> Path:
    return Path(__file__).resolve().parents[2]


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def request_id_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _short_single_line(value: str, *, field: str, max_len: int = 160) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field}_required")
    if len(text) > max_len:
        raise ValueError(f"{field}_too_long")
    if "\n" in text or "\r" in text:
        raise ValueError(f"{field}_must_be_single_line")
    return text


def build_request_payload(
    *,
    action: str,
    reason: str,
    request_id: str | None = None,
    requested_by: str = "codex",
    requested_utc: str | None = None,
) -> dict[str, Any]:
    action = str(action or "").strip().lower()
    if action not in ALLOWED_ACTIONS:
        raise ValueError("action_must_be_status_pause_or_resume")

    reason = _short_single_line(reason, field="reason")
    requested_by = _short_single_line(requested_by, field="requested_by", max_len=80)
    if request_id is None:
        request_id = f"H_MAINT_{request_id_stamp()}_{action.upper()}"
    request_id = str(request_id).strip()
    if not ID_RE.match(request_id):
        raise ValueError("request_id_has_unsafe_characters")

    return {
        "schema_version": "1",
        "flow": "H",
        "action": action,
        "reason": reason,
        "request_id": request_id,
        "requested_by": requested_by,
        "requested_utc": requested_utc or utc_stamp(),
        "allowed_controller_actions": sorted(ALLOWED_ACTIONS),
        "forbidden_actions": [
            "no Google Sheets writes",
            "no price changes",
            "no queue edits",
            "no local DB alignment",
            "no purchase orders",
            "no receiving events",
            "no send-to-Amazon handoff",
            "no output deletion",
            "no market proof scan",
        ],
    }


def request_path(root: Path) -> Path:
    return root / REQUEST_REL_PATH


def result_path(root: Path) -> Path:
    return root / RESULT_REL_PATH


def write_request(root: Path, payload: dict[str, Any], *, replace: bool = False) -> Path:
    root = root.resolve()
    target = request_path(root)
    locks_dir = target.parent.resolve()
    target_parent = target.parent.resolve()
    if locks_dir != target_parent:
        raise ValueError("request_path_not_under_locks")
    if target.exists() and not replace:
        raise FileExistsError(f"active_request_exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f"{target.name}.tmp.{payload.get('request_id', 'request')}")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="ascii")
    tmp.replace(target)
    return target


def run_controller_task(task_name: str = DEFAULT_TASK_NAME) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["schtasks", "/Run", "/TN", task_name],
        check=False,
        capture_output=True,
        text=True,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write a bounded H maintenance request for the admin-gated controller.")
    parser.add_argument("--action", required=True, choices=sorted(ALLOWED_ACTIONS))
    parser.add_argument("--reason", required=True)
    parser.add_argument("--request-id", default=None)
    parser.add_argument("--requested-by", default="codex")
    parser.add_argument("--root", default=str(repo_root_from_script()))
    parser.add_argument("--replace", action="store_true", help="Replace an unconsumed active request.")
    parser.add_argument("--run-controller", action="store_true", help="Start the installed scheduled task after writing the request.")
    parser.add_argument("--task-name", default=DEFAULT_TASK_NAME)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    payload = build_request_payload(
        action=args.action,
        reason=args.reason,
        request_id=args.request_id,
        requested_by=args.requested_by,
    )
    target = write_request(root, payload, replace=args.replace)
    controller = None
    if args.run_controller:
        controller = run_controller_task(args.task_name)
    summary: dict[str, Any] = {
        "request_written": True,
        "request_path": str(target),
        "result_path": str(result_path(root)),
        "request_id": payload["request_id"],
        "action": payload["action"],
        "controller_task_requested": bool(args.run_controller),
    }
    if controller is not None:
        summary["controller_task_rc"] = controller.returncode
        summary["controller_task_stdout"] = (controller.stdout or "").strip()
        summary["controller_task_stderr"] = (controller.stderr or "").strip()
    print(json.dumps(summary, indent=2, sort_keys=True))
    if controller is not None and controller.returncode != 0:
        return controller.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
