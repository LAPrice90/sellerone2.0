from __future__ import annotations

import argparse
import csv
import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[2]
PLAN_DIR = ROOT / "plans" / "active" / "h-f-feedback-learning-loop-v1"
MANIFEST_PATH = PLAN_DIR / "FROZEN_INPUT_MANIFEST.md"

DEFAULT_SOURCE_PATHS = [
    "out/cycle_alerts/checklist_H.csv",
    "out/h_strategy_outcome_log.csv",
    "out/h_strategy_outcome_daily.csv",
    "out/listing_offer_snapshot_latest.csv",
    "out/listing_offer_seller_snapshot_latest.csv",
    "out/listing_offer_history.csv",
    "out/listing_offer_seller_observation_history.csv",
    "out/hos_daily_market_snapshot_latest.csv",
    "out/sku_performance_summary.csv",
    "out/sku_sales_velocity.csv",
    "out/systems/F/live/f_screening_row_state_live.csv",
    "out/systems/F/live/feeder_approval_queue_live.csv",
    "out/systems/F/history/feeder_approval_decisions_log.csv",
    "out/systems/F/live/feeder_po_handoff_ready_live.csv",
    "out/systems/F/live/feeder_candidate_recommendations_live.csv",
    "out/systems/F/live/feeder_legacy_scrape_evidence_live.csv",
    "out/systems/F/live/feeder_legacy_chart_daily_raw_live.csv",
    "out/analysis_reports/f_backtest_calibration_set_latest.csv",
    "out/analysis_reports/f_sales_history_validation_latest.csv",
]


@dataclass(frozen=True)
class FreezeRecord:
    rel_path: str
    row_count: int
    last_write_utc: str
    sha256: str


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _csv_row_count(path: Path) -> int:
    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader, None)
        if header is None:
            return 0
        count = 0
        for row in reader:
            if any(str(cell).strip() for cell in row):
                count += 1
        return count


def _sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def collect_freeze_records(repo_root: Path, rel_paths: Iterable[str]) -> dict[str, FreezeRecord]:
    records: dict[str, FreezeRecord] = {}
    for rel in rel_paths:
        rel_norm = str(rel).replace("\\", "/").strip()
        abs_path = repo_root / Path(rel_norm)
        if not abs_path.exists():
            raise FileNotFoundError(f"required freeze source missing: {rel_norm}")
        row_count = _csv_row_count(abs_path)
        last_write = abs_path.stat().st_mtime
        last_write_utc = datetime.fromtimestamp(last_write, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        sha256 = _sha256_file(abs_path)
        records[rel_norm] = FreezeRecord(
            rel_path=rel_norm,
            row_count=row_count,
            last_write_utc=last_write_utc,
            sha256=sha256,
        )
    return records


def _replace_status_value(text: str, label: str, new_value: str) -> str:
    pattern = re.compile(rf"(- {re.escape(label)}:\r?\n\s*-\s*).+")
    updated, count = pattern.subn(lambda match: f"{match.group(1)}{new_value}", text, count=1)
    if count != 1:
        raise ValueError(f"status label not found in manifest: {label}")
    return updated


def _update_table_rows(text: str, records: dict[str, FreezeRecord]) -> str:
    lines = text.splitlines()
    seen_paths: set[str] = set()
    out_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("| `") and stripped.endswith("|"):
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            if len(cells) >= 6:
                path_cell = cells[0]
                if path_cell.startswith("`") and path_cell.endswith("`"):
                    rel_path = path_cell[1:-1].replace("\\", "/")
                    record = records.get(rel_path)
                    if record is not None:
                        role = cells[1]
                        notes = cells[5]
                        new_row = (
                            f"| `{record.rel_path}` | {role} | {record.row_count} | "
                            f"`{record.last_write_utc}` | `{record.sha256}` | {notes} |"
                        )
                        out_lines.append(new_row)
                        seen_paths.add(record.rel_path)
                        continue
        out_lines.append(line)

    missing = [path for path in records if path not in seen_paths]
    if missing:
        missing_text = ", ".join(missing)
        raise ValueError(f"manifest table rows missing for: {missing_text}")
    return "\n".join(out_lines) + "\n"


def freeze_manifest(
    manifest_path: Path,
    repo_root: Path,
    rel_paths: Iterable[str],
    *,
    owner: str,
    timestamp_utc: str | None = None,
) -> dict[str, FreezeRecord]:
    owner_norm = owner.strip() or "codex"
    timestamp = (timestamp_utc or "").strip() or _utc_now_iso()
    records = collect_freeze_records(repo_root, rel_paths)

    text = manifest_path.read_text(encoding="utf-8", errors="replace")
    text = _replace_status_value(text, "Freeze state", "locked")
    text = _replace_status_value(text, "Freeze owner", owner_norm)
    text = _replace_status_value(text, "Freeze timestamp UTC", timestamp)
    text = _update_table_rows(text, records)
    manifest_path.write_text(text, encoding="utf-8")
    return records


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Lock frozen-input manifest for H/F learning prep gate.")
    parser.add_argument("--manifest-path", default=str(MANIFEST_PATH), help="Path to FROZEN_INPUT_MANIFEST.md")
    parser.add_argument("--repo-root", default=str(ROOT), help="Repository root")
    parser.add_argument("--owner", default="codex", help="Freeze owner label")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    manifest_path = Path(args.manifest_path)
    repo_root = Path(args.repo_root)

    records = freeze_manifest(
        manifest_path=manifest_path,
        repo_root=repo_root,
        rel_paths=DEFAULT_SOURCE_PATHS,
        owner=args.owner,
    )
    print(f"freeze_manifest_path={manifest_path}")
    print("freeze_state=locked")
    print(f"freeze_owner={args.owner.strip() or 'codex'}")
    print(f"sources_locked={len(records)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
