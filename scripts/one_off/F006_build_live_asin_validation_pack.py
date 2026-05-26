from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCRAPE_PATH = ROOT / "out" / "systems" / "F" / "live" / "feeder_legacy_scrape_evidence_live.csv"
DEFAULT_OUTPUT_DIR = ROOT / "out" / "analysis_reports"


@dataclass(frozen=True)
class LiveAsinValidationPackResult:
    pack_df: pd.DataFrame
    report_path: Path
    latest_path: Path


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _to_timestamp_slug(observed_utc: str) -> str:
    dt = datetime.strptime(observed_utc, "%Y-%m-%dT%H:%M:%SZ")
    return dt.strftime("%Y%m%dT%H%M%SZ")


def _normalize_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"", "nan", "none", "null"}:
        return ""
    return text


def _normalize_key(value: object) -> str:
    return _normalize_text(value).upper()


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _amazon_link(asin: str) -> str:
    asin_key = _normalize_text(asin)
    if asin_key == "":
        return ""
    return f"https://www.amazon.co.uk/dp/{asin_key}"


def _latest_rows(scrape_df: pd.DataFrame) -> pd.DataFrame:
    if scrape_df.empty:
        return scrape_df
    work = scrape_df.copy()
    work["asin_norm"] = work.get("asin", "").map(_normalize_key)
    work["supplier_sku_norm"] = work.get("supplier_sku", "").map(_normalize_key)
    work = work[(work["asin_norm"] != "") | (work["supplier_sku_norm"] != "")].copy()
    work["_observed_ts"] = pd.to_datetime(work.get("observed_utc", "").map(_normalize_text), errors="coerce")
    work = work.sort_values("_observed_ts", ascending=False, kind="stable")
    work = work.drop_duplicates(subset=["asin_norm", "supplier_sku_norm"], keep="first")
    return work.reset_index(drop=True)


def _with_case(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    work = df.copy()
    last_completed_label = work.get("bbp_sales_last_completed_month_label", "").map(_normalize_text)
    replay_source = work.get("bbp_sales_replay_demand_basis_source", "").map(_normalize_text)
    asin = work.get("asin", "").map(_normalize_text)
    work["validation_case"] = ""

    completed_mask = (last_completed_label != "") & (replay_source == "bbp_last_completed_month")
    zero_history_mask = replay_source == "bbp_zero_history"
    missing_basis_mask = (asin != "") & (last_completed_label == "") & (replay_source == "")

    work.loc[completed_mask, "validation_case"] = "trusted_completed_month"
    work.loc[zero_history_mask, "validation_case"] = "explicit_zero_history"
    work.loc[missing_basis_mask, "validation_case"] = "missing_completed_month_basis"
    return work


def _pick_case_rows(df: pd.DataFrame, *, case_name: str, limit: int) -> pd.DataFrame:
    if df.empty or limit <= 0:
        return pd.DataFrame(columns=df.columns if not df.empty else [])
    rows = df[df.get("validation_case", "").map(_normalize_text) == case_name].copy()
    if rows.empty:
        return rows
    rows["_observed_ts"] = pd.to_datetime(rows.get("observed_utc", "").map(_normalize_text), errors="coerce")
    rows = rows.sort_values("_observed_ts", ascending=False, kind="stable").head(limit)
    return rows.drop(columns=["_observed_ts"], errors="ignore")


def build_live_asin_validation_pack(
    *,
    scrape_path: Path = DEFAULT_SCRAPE_PATH,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    completed_count: int = 4,
    zero_history_count: int = 2,
    missing_basis_count: int = 4,
    observed_utc: str | None = None,
) -> LiveAsinValidationPackResult:
    snapshot_utc = observed_utc or _utc_now_iso()
    scrape_df = _read_csv(scrape_path)

    output_dir.mkdir(parents=True, exist_ok=True)
    ts_slug = _to_timestamp_slug(snapshot_utc)
    report_path = output_dir / f"f_live_asin_validation_pack_{ts_slug}.csv"
    latest_path = output_dir / "f_live_asin_validation_pack_latest.csv"

    if scrape_df.empty:
        empty_cols = [
            "observed_utc",
            "validation_case",
            "sample_rank",
            "supplier_id",
            "supplier_name",
            "supplier_sku",
            "asin",
            "amazon_link",
        ]
        empty_df = pd.DataFrame(columns=empty_cols)
        empty_df.to_csv(report_path, index=False)
        empty_df.to_csv(latest_path, index=False)
        print(
            json.dumps(
                {
                    "status": "success",
                    "observed_utc": snapshot_utc,
                    "rows": 0,
                    "csv_output": str(report_path),
                    "latest_csv": str(latest_path),
                }
            )
        )
        return LiveAsinValidationPackResult(pack_df=empty_df, report_path=report_path, latest_path=latest_path)

    base_df = _with_case(_latest_rows(scrape_df))
    selected = pd.concat(
        [
            _pick_case_rows(base_df, case_name="trusted_completed_month", limit=max(completed_count, 0)),
            _pick_case_rows(base_df, case_name="explicit_zero_history", limit=max(zero_history_count, 0)),
            _pick_case_rows(base_df, case_name="missing_completed_month_basis", limit=max(missing_basis_count, 0)),
        ],
        ignore_index=True,
    )
    if selected.empty:
        selected = pd.DataFrame(columns=base_df.columns)
    else:
        selected["asin_norm"] = selected.get("asin", "").map(_normalize_key)
        selected["supplier_sku_norm"] = selected.get("supplier_sku", "").map(_normalize_key)
        selected = selected.drop_duplicates(subset=["validation_case", "asin_norm", "supplier_sku_norm"], keep="first")

    out_rows: list[dict[str, str]] = []
    case_order = ["trusted_completed_month", "explicit_zero_history", "missing_completed_month_basis"]
    rank = 1
    for case_name in case_order:
        case_rows = selected[selected.get("validation_case", "").map(_normalize_text) == case_name].copy()
        if case_rows.empty:
            continue
        case_rows["_observed_ts"] = pd.to_datetime(case_rows.get("observed_utc", "").map(_normalize_text), errors="coerce")
        case_rows = case_rows.sort_values("_observed_ts", ascending=False, kind="stable")
        for _, row in case_rows.iterrows():
            asin = _normalize_text(row.get("asin", ""))
            out_rows.append(
                {
                    "observed_utc": snapshot_utc,
                    "validation_case": case_name,
                    "sample_rank": str(rank),
                    "scrape_observed_utc": _normalize_text(row.get("observed_utc", "")),
                    "supplier_id": _normalize_text(row.get("supplier_id", "")),
                    "supplier_name": _normalize_text(row.get("supplier_name", "")),
                    "supplier_sku": _normalize_text(row.get("supplier_sku", "")),
                    "asin": asin,
                    "amazon_link": _amazon_link(asin),
                    "bbp_sales_last_completed_month_label": _normalize_text(row.get("bbp_sales_last_completed_month_label", "")),
                    "bbp_sales_last_completed_month_units": _normalize_text(row.get("bbp_sales_last_completed_month_units", "")),
                    "bbp_sales_current_month_label": _normalize_text(row.get("bbp_sales_current_month_label", "")),
                    "bbp_sales_current_month_units": _normalize_text(row.get("bbp_sales_current_month_units", "")),
                    "bbp_sales_future_month_count_ignored": _normalize_text(
                        row.get("bbp_sales_future_month_count_ignored", "")
                    ),
                    "bbp_sales_replay_demand_basis_source": _normalize_text(
                        row.get("bbp_sales_replay_demand_basis_source", "")
                    ),
                    "bbp_sales_replay_demand_basis_units": _normalize_text(
                        row.get("bbp_sales_replay_demand_basis_units", "")
                    ),
                    "bbp_sales_chart_month_labels": _normalize_text(row.get("bbp_sales_chart_month_labels", "")),
                    "bbp_sales_chart_month_units": _normalize_text(row.get("bbp_sales_chart_month_units", "")),
                }
            )
            rank += 1

    pack_df = pd.DataFrame(out_rows)
    pack_df.to_csv(report_path, index=False)
    pack_df.to_csv(latest_path, index=False)

    case_counts = (
        pack_df.get("validation_case", pd.Series(dtype=str)).map(_normalize_text).value_counts().to_dict()
        if not pack_df.empty
        else {}
    )
    print(
        json.dumps(
            {
                "status": "success",
                "observed_utc": snapshot_utc,
                "rows": int(len(pack_df)),
                "case_counts": case_counts,
                "csv_output": str(report_path),
                "latest_csv": str(latest_path),
            }
        )
    )
    return LiveAsinValidationPackResult(pack_df=pack_df, report_path=report_path, latest_path=latest_path)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a mixed live-ASIN validation pack from scrape evidence.")
    parser.add_argument("--scrape-path", default=str(DEFAULT_SCRAPE_PATH))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--completed-count", type=int, default=4)
    parser.add_argument("--zero-history-count", type=int, default=2)
    parser.add_argument("--missing-basis-count", type=int, default=4)
    parser.add_argument("--observed-utc", default=None, help="Override observed_utc in YYYY-MM-DDTHH:MM:SSZ.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    build_live_asin_validation_pack(
        scrape_path=Path(args.scrape_path),
        output_dir=Path(args.output_dir),
        completed_count=args.completed_count,
        zero_history_count=args.zero_history_count,
        missing_basis_count=args.missing_basis_count,
        observed_utc=args.observed_utc,
    )


if __name__ == "__main__":
    main()
