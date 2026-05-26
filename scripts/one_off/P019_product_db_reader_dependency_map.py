from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from scripts.core.storage.product_db_contract import utc_now_iso


DEFAULT_OUTPUT_DIR = ROOT / "out" / "sql_migration" / "product_db_contract"
DEFAULT_MAP_PATH = DEFAULT_OUTPUT_DIR / "product_db_reader_dependency_map.csv"
DEFAULT_SUMMARY_PATH = DEFAULT_OUTPUT_DIR / "product_db_reader_dependency_summary.json"

SCAN_SUBTREES: tuple[str, ...] = ("scripts", "project_control", "plans")
SCAN_SUFFIXES: tuple[str, ...] = (".py", ".md", ".csv", ".bat")
PATTERNS: tuple[str, ...] = (
    "product_db_preview.csv",
    "Product_DB",
    "product_db_products",
    "load_product_db_products_from_sqlite",
    "load_product_db_for_validation",
)

MAP_COLUMNS: tuple[str, ...] = (
    "file_path",
    "line_number",
    "matched_pattern",
    "owner_flow",
    "current_source",
    "proposed_source",
    "safe_proof_type",
    "blocked_without_approval",
    "line_excerpt",
)


def _text(value: object) -> str:
    return str(value or "").strip()


def _rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _owner_for_path(rel_path: str) -> str:
    parts = rel_path.split("/")
    if len(parts) >= 3 and parts[0] == "scripts" and parts[1] == "flows":
        return parts[2].upper()
    if rel_path.startswith("scripts/one_off/"):
        return "P"
    if rel_path.startswith("scripts/core/"):
        return "shared"
    if rel_path.startswith("scripts/"):
        return "shared"
    if rel_path.startswith("project_control/") or rel_path.startswith("plans/"):
        return "governance"
    if rel_path.endswith(".bat"):
        return "entrypoint"
    return "unknown"


def _current_source(patterns: set[str]) -> str:
    has_sql = bool(patterns & {"product_db_products", "load_product_db_products_from_sqlite"})
    has_csv = bool(patterns & {"product_db_preview.csv", "load_product_db_for_validation"})
    has_sheet = "Product_DB" in patterns
    sources: list[str] = []
    if has_sql:
        sources.append("sql")
    if has_csv:
        sources.append("csv_mirror")
    if has_sheet:
        sources.append("sheet")
    return "mixed" if len(sources) > 1 else (sources[0] if sources else "unknown")


def _proof_type(owner: str) -> str:
    return {
        "A": "A-owned proof required",
        "B": "B-owned maintenance proof required",
        "H": "H-owned controlled proof required",
        "E": "E-owned proof required",
        "F": "F-owned proof required",
        "O": "O-owned local proof",
        "P": "local-only proof",
        "shared": "local contract tests",
        "governance": "documentation proof",
        "entrypoint": "manual owner review",
    }.get(owner, "needs owner classification")


def _blocked(owner: str) -> str:
    return "1" if owner in {"A", "B", "H", "entrypoint", "unknown"} else "0"


def _iter_scan_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for subtree in SCAN_SUBTREES:
        base = root / subtree
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file() and path.suffix.lower() in SCAN_SUFFIXES:
                rel = _rel(path, root)
                if "/__pycache__/" in rel or rel.startswith("plans/archive/"):
                    continue
                files.append(path)
    return sorted(files)


def run_check(
    *,
    root: Path = ROOT,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    observed_utc: str | None = None,
) -> dict[str, Any]:
    observed = observed_utc or utc_now_iso()
    output_dir.mkdir(parents=True, exist_ok=True)
    map_path = output_dir / DEFAULT_MAP_PATH.name
    summary_path = output_dir / DEFAULT_SUMMARY_PATH.name

    rows: list[dict[str, str]] = []
    for path in _iter_scan_files(root):
        rel_path = _rel(path, root)
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for index, line in enumerate(lines, start=1):
            matched = {pattern for pattern in PATTERNS if pattern in line}
            if not matched:
                continue
            owner = _owner_for_path(rel_path)
            current_source = _current_source(matched)
            proposed_source = "sql_first_with_csv_export_fallback" if owner in {"O", "P", "shared"} else "map_only_until_flow_owned_proof"
            rows.append(
                {
                    "file_path": rel_path,
                    "line_number": str(index),
                    "matched_pattern": "|".join(sorted(matched)),
                    "owner_flow": owner,
                    "current_source": current_source,
                    "proposed_source": proposed_source,
                    "safe_proof_type": _proof_type(owner),
                    "blocked_without_approval": _blocked(owner),
                    "line_excerpt": line.strip()[:240],
                }
            )

    df = pd.DataFrame(rows, columns=MAP_COLUMNS)
    df.to_csv(map_path, index=False)
    owner_counts = df["owner_flow"].value_counts().to_dict() if not df.empty else {}
    unknown_owner_count = int(df["owner_flow"].eq("unknown").sum()) if not df.empty else 0
    blocked_count = int(df["blocked_without_approval"].eq("1").sum()) if not df.empty else 0
    payload = {
        "status": "fail" if unknown_owner_count else ("warn" if blocked_count else "ok"),
        "observed_utc": observed,
        "reader_reference_rows": int(len(df.index)),
        "unique_files": int(df["file_path"].nunique()) if not df.empty else 0,
        "unknown_owner_count": unknown_owner_count,
        "blocked_without_approval_count": blocked_count,
        "owner_counts": {str(k): int(v) for k, v in owner_counts.items()},
        "map_path": str(map_path),
        "summary_path": str(summary_path),
    }
    summary_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    return payload


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Map Product DB reader dependencies and owner proof boundaries.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    payload = run_check(root=Path(args.root), output_dir=Path(args.output_dir))
    if args.format == "json":
        print(json.dumps(payload, indent=2, ensure_ascii=True))
    else:
        for key, value in payload.items():
            print(f"{key}={value}")
    return 0 if payload["status"] != "fail" else 1


if __name__ == "__main__":
    raise SystemExit(main())
