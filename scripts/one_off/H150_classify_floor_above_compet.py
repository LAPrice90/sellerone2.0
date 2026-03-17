from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"

SUMMARY_PATH = OUT / "floor_above_compet_summary.csv"
BUCKET_A_PATH = OUT / "floor_above_compet_bucket_A.csv"
BUCKET_B_PATH = OUT / "floor_above_compet_bucket_B.csv"
BUCKET_C_PATH = OUT / "floor_above_compet_bucket_C.csv"


def _normalize_header(name: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "_", (name or "").strip().lower())
    return re.sub(r"_+", "_", text).strip("_")


def _to_float(value: object) -> float | None:
    raw = str(value or "").strip()
    if raw == "":
        return None
    cleaned = raw.replace(",", "").replace("£", "").replace("$", "").replace("%", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _to_bool(value: object) -> bool | None:
    text = str(value or "").strip().lower()
    if text in {"1", "true", "yes", "y"}:
        return True
    if text in {"0", "false", "no", "n"}:
        return False
    return None


def _resolve_input_path(explicit: str | None) -> Path:
    if explicit:
        p = Path(explicit)
        if not p.is_absolute():
            p = ROOT / p
        return p
    candidates = [
        OUT / "repricing_tracker.csv",
        OUT / "analysis_reports" / "repricing_tracker.csv",
        OUT / "systems" / "H" / "live" / "repricing_tracker.csv",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        "No input CSV found. Pass --input <path_to_tracker_csv>."
    )


def _load_exclude_skus(path_value: str | None) -> set[str]:
    if not path_value:
        return set()
    p = Path(path_value)
    if not p.is_absolute():
        p = ROOT / p
    if not p.exists():
        raise FileNotFoundError(f"Exclude CSV not found: {p}")
    with p.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames:
            raise ValueError(f"Exclude CSV has no headers: {p}")
        normalized = {_normalize_header(h): h for h in reader.fieldnames}
        if "sku" not in normalized:
            raise ValueError(f"Exclude CSV must include header 'sku': {p}")
        sku_header = normalized["sku"]
        out: set[str] = set()
        for row in reader:
            sku = str(row.get(sku_header, "")).strip()
            if sku:
                out.add(sku)
        return out


def _read_rows(path: Path) -> tuple[list[dict[str, str]], dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames:
            raise ValueError(f"Input CSV has no headers: {path}")
        header_map: dict[str, str] = {
            original: _normalize_header(original) for original in reader.fieldnames
        }
        rows: list[dict[str, str]] = []
        for row in reader:
            normalized_row: dict[str, str] = {}
            for original, value in row.items():
                normalized_row[header_map[original]] = str(value or "").strip()
            rows.append(normalized_row)
        return rows, header_map


def _get_first(row: dict[str, str], keys: list[str]) -> str:
    for key in keys:
        if key in row and row[key] != "":
            return row[key]
    return ""


def _is_floor_above_compet(row: dict[str, str]) -> bool:
    explicit_flag = _get_first(
        row,
        [
            "floor_gt_compet",
            "floor_above_compet",
            "floor_gt_comp",
            "floor_greater_than_compet",
        ],
    )
    flag_value = _to_bool(explicit_flag)
    if flag_value is not None:
        return flag_value

    floor = _to_float(
        _get_first(
            row,
            ["floor", "hard_floor", "hard_floor_price", "floor_price", "min_floor"],
        )
    )
    compet = _to_float(
        _get_first(
            row,
            ["compet", "competitor_price", "best_competitor_price", "comp_price"],
        )
    )
    if floor is None or compet is None:
        return False
    return floor > compet


def _compet_roi(row: dict[str, str]) -> float:
    raw = _get_first(
        row,
        ["compet_roi", "competitor_roi", "roi_at_compet", "roi_compet"],
    )
    value = _to_float(raw)
    if value is None:
        return 0.0
    return value


def _bucket_for_roi(roi: float) -> tuple[str, str]:
    if roi > 5:
        return "A", "PHASE_2_LOW_MARGIN"
    if roi > 0:
        return "B", "PHASE_2_TIGHT"
    return "C", "PHASE_3_EXIT"


def _write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Classify Floor > Compet SKUs into action buckets (report only)."
    )
    parser.add_argument(
        "--input",
        default="",
        help="Path to Repricing Tracker CSV. If omitted, common out/ paths are checked.",
    )
    parser.add_argument(
        "--exclude-skus",
        default="",
        help="Optional CSV path with header 'sku' listing SKUs to exclude from outputs.",
    )
    args = parser.parse_args()

    input_path = _resolve_input_path(args.input.strip() or None)
    exclude_skus = _load_exclude_skus(args.exclude_skus.strip() or None)
    rows, _ = _read_rows(input_path)

    floor_rows = [r for r in rows if _is_floor_above_compet(r)]
    excluded_rows: list[dict[str, str]] = []
    included_floor_rows: list[dict[str, str]] = []
    for row in floor_rows:
        sku = _get_first(row, ["sku", "seller_sku"])
        if sku and sku in exclude_skus:
            excluded_rows.append(row)
        else:
            included_floor_rows.append(row)

    output_rows: list[dict[str, str]] = []
    for row in included_floor_rows:
        roi = _compet_roi(row)
        bucket, action = _bucket_for_roi(roi)
        enriched = dict(row)
        enriched["compet_roi_numeric"] = f"{roi:.4f}"
        enriched["bucket"] = bucket
        enriched["action"] = action
        output_rows.append(enriched)

    a_rows = [r for r in output_rows if r["bucket"] == "A"]
    b_rows = [r for r in output_rows if r["bucket"] == "B"]
    c_rows = [r for r in output_rows if r["bucket"] == "C"]

    out_fields: list[str] = []
    for row in output_rows:
        for key in row.keys():
            if key not in out_fields:
                out_fields.append(key)
    if not out_fields:
        out_fields = ["bucket", "action", "compet_roi_numeric"]

    _write_csv(BUCKET_A_PATH, a_rows, out_fields)
    _write_csv(BUCKET_B_PATH, b_rows, out_fields)
    _write_csv(BUCKET_C_PATH, c_rows, out_fields)

    summary_rows = [
        {
            "metric": "input_path",
            "value": str(input_path),
        },
        {
            "metric": "input_rows",
            "value": str(len(rows)),
        },
        {
            "metric": "floor_above_compet_rows",
            "value": str(len(included_floor_rows)),
        },
        {
            "metric": "excluded_rows",
            "value": str(len(excluded_rows)),
        },
        {
            "metric": "bucket_A_count",
            "value": str(len(a_rows)),
        },
        {
            "metric": "bucket_B_count",
            "value": str(len(b_rows)),
        },
        {
            "metric": "bucket_C_count",
            "value": str(len(c_rows)),
        },
    ]
    _write_csv(SUMMARY_PATH, summary_rows, ["metric", "value"])

    print(f"floor_above_compet_input={input_path}")
    print(f"floor_above_compet_rows={len(included_floor_rows)}")
    excluded_sku_list: list[str] = []
    for row in excluded_rows:
        sku = _get_first(row, ["sku", "seller_sku"])
        if sku and sku not in excluded_sku_list:
            excluded_sku_list.append(sku)
    print(f"EXCLUDED_COUNT={len(excluded_rows)}")
    print(f"EXCLUDED_SKUS_SAMPLE={','.join(excluded_sku_list[:10])}")
    print(f"bucket_A={len(a_rows)}")
    print(f"bucket_B={len(b_rows)}")
    print(f"bucket_C={len(c_rows)}")
    print(f"summary_out={SUMMARY_PATH}")
    print(f"bucket_A_out={BUCKET_A_PATH}")
    print(f"bucket_B_out={BUCKET_B_PATH}")
    print(f"bucket_C_out={BUCKET_C_PATH}")


if __name__ == "__main__":
    main()
