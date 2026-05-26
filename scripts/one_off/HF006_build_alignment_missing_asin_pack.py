from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ALIGNMENT_PATH = ROOT / "out" / "analysis_reports" / "hf_learning_alignment_30d_latest.csv"
DEFAULT_IDENTITY_PATH = ROOT / "out" / "analysis_reports" / "hf_learning_identity_bridge_latest.csv"
DEFAULT_SCRAPE_PATH = ROOT / "out" / "systems" / "F" / "live" / "feeder_legacy_scrape_evidence_live.csv"
DEFAULT_OUTPUT_DIR = ROOT / "out" / "analysis_reports"


@dataclass(frozen=True)
class AlignmentMissingAsinPackResult:
    pack_df: pd.DataFrame
    report_path: Path
    latest_path: Path
    summary: dict[str, object]


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


def _identity_supplier_sku_map(identity_df: pd.DataFrame) -> dict[str, str]:
    if identity_df.empty:
        return {}
    work = pd.DataFrame()
    work["asin"] = identity_df.get("asin", "").map(_normalize_text)
    work["supplier_sku"] = identity_df.get("supplier_sku", "").map(_normalize_text)
    work = work[(work["asin"] != "") & (work["supplier_sku"] != "")].copy()
    if work.empty:
        return {}
    work["asin_key"] = work["asin"].map(_normalize_key)
    work = work.sort_values(["asin_key", "supplier_sku"], ascending=[True, True], kind="stable")
    work = work.drop_duplicates(subset=["asin_key"], keep="first")
    return {
        _normalize_key(row["asin"]): _normalize_text(row["supplier_sku"])
        for _, row in work.iterrows()
    }


def _scrape_presence_map(scrape_df: pd.DataFrame) -> dict[str, str]:
    if scrape_df.empty:
        return {}
    work = pd.DataFrame()
    work["asin"] = scrape_df.get("asin", "").map(_normalize_text)
    work["supplier_id"] = scrape_df.get("supplier_id", "").map(_normalize_text)
    work = work[work["asin"] != ""].copy()
    if work.empty:
        return {}

    per_asin_suppliers: dict[str, set[str]] = {}
    for _, row in work.iterrows():
        asin_key = _normalize_key(row.get("asin", ""))
        supplier_id = _normalize_text(row.get("supplier_id", ""))
        if asin_key == "":
            continue
        if asin_key not in per_asin_suppliers:
            per_asin_suppliers[asin_key] = set()
        if supplier_id != "":
            per_asin_suppliers[asin_key].add(supplier_id)

    return {
        asin_key: "|".join(sorted(suppliers))
        for asin_key, suppliers in per_asin_suppliers.items()
    }


def _alignment_missing_asins(alignment_df: pd.DataFrame) -> pd.DataFrame:
    if alignment_df.empty:
        return pd.DataFrame(columns=["asin", "source_alignment_window_end_utc"])

    work = pd.DataFrame()
    work["asin"] = alignment_df.get("asin", "").map(_normalize_text)
    work["sku"] = alignment_df.get("sku", "").map(_normalize_text)
    work["expected_units_source"] = alignment_df.get("expected_units_source", "").map(_normalize_text)
    work["source_alignment_window_end_utc"] = alignment_df.get("alignment_window_end_utc", "").map(_normalize_text)
    work["asin_key"] = work["asin"].map(_normalize_key)
    work = work[(work["asin"] != "") & work["expected_units_source"].isin({"", "no_source"})].copy()
    if work.empty:
        return work
    work = work.sort_values(["asin_key", "sku"], ascending=[True, True], kind="stable")
    work = work.drop_duplicates(subset=["asin_key"], keep="first")
    return work.reset_index(drop=True)


def build_alignment_missing_asin_pack(
    *,
    alignment_path: Path = DEFAULT_ALIGNMENT_PATH,
    identity_path: Path = DEFAULT_IDENTITY_PATH,
    scrape_path: Path = DEFAULT_SCRAPE_PATH,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    max_asins: int = 0,
    only_not_in_scrape: bool = False,
    observed_utc: str | None = None,
) -> AlignmentMissingAsinPackResult:
    snapshot_utc = observed_utc or _utc_now_iso()
    alignment_df = _read_csv(alignment_path)
    identity_df = _read_csv(identity_path)
    scrape_df = _read_csv(scrape_path)

    output_dir.mkdir(parents=True, exist_ok=True)
    ts_slug = _to_timestamp_slug(snapshot_utc)
    report_path = output_dir / f"hf_alignment_missing_asin_pack_{ts_slug}.csv"
    latest_path = output_dir / "hf_alignment_missing_asin_pack_latest.csv"

    missing_df = _alignment_missing_asins(alignment_df)
    supplier_sku_by_asin = _identity_supplier_sku_map(identity_df)
    scrape_suppliers_by_asin = _scrape_presence_map(scrape_df)

    rows: list[dict[str, str]] = []
    for _, row in missing_df.iterrows():
        asin = _normalize_text(row.get("asin", ""))
        asin_key = _normalize_key(asin)
        supplier_sku = supplier_sku_by_asin.get(asin_key, "")
        scrape_suppliers = scrape_suppliers_by_asin.get(asin_key, "")
        scrape_present_flag = "1" if scrape_suppliers != "" else "0"
        rows.append(
            {
                "observed_utc": snapshot_utc,
                "validation_case": "alignment_missing_expected_baseline",
                "sample_rank": "",
                "supplier_sku": supplier_sku,
                "asin": asin,
                "amazon_link": _amazon_link(asin),
                "source_alignment_window_end_utc": _normalize_text(row.get("source_alignment_window_end_utc", "")),
                "expected_units_source": _normalize_text(row.get("expected_units_source", "")),
                "scrape_present_flag": scrape_present_flag,
                "scrape_supplier_ids": scrape_suppliers,
            }
        )

    pack_df = pd.DataFrame(rows)
    if pack_df.empty:
        pack_df = pd.DataFrame(
            columns=[
                "observed_utc",
                "validation_case",
                "sample_rank",
                "supplier_sku",
                "asin",
                "amazon_link",
                "source_alignment_window_end_utc",
                "expected_units_source",
                "scrape_present_flag",
                "scrape_supplier_ids",
            ]
        )
    else:
        if only_not_in_scrape:
            pack_df = pack_df[pack_df["scrape_present_flag"] == "0"].copy()

        # Prioritize ASINs with no scrape presence first.
        pack_df["_priority"] = pack_df["scrape_present_flag"].map(lambda v: 0 if _normalize_text(v) == "0" else 1)
        pack_df["_asin_key"] = pack_df["asin"].map(_normalize_key)
        pack_df = pack_df.sort_values(["_priority", "_asin_key"], ascending=[True, True], kind="stable").reset_index(drop=True)

        if max_asins > 0:
            pack_df = pack_df.head(max_asins).copy()

        pack_df["sample_rank"] = [str(i) for i in range(1, len(pack_df.index) + 1)]
        pack_df = pack_df.drop(columns=["_priority", "_asin_key"], errors="ignore")

    pack_df.to_csv(report_path, index=False)
    pack_df.to_csv(latest_path, index=False)

    scrape_present_rows = int((pack_df.get("scrape_present_flag", "").map(_normalize_text) == "1").sum())
    summary = {
        "status": "success",
        "observed_utc": snapshot_utc,
        "alignment_rows_total": int(len(alignment_df)),
        "alignment_no_source_unique_asins": int(len(missing_df)),
        "pack_rows": int(len(pack_df)),
        "scrape_present_rows": scrape_present_rows,
        "scrape_missing_rows": int(len(pack_df)) - scrape_present_rows,
        "only_not_in_scrape": bool(only_not_in_scrape),
        "max_asins": int(max_asins),
        "report_path": str(report_path),
        "latest_path": str(latest_path),
    }
    print(json.dumps(summary))
    return AlignmentMissingAsinPackResult(
        pack_df=pack_df,
        report_path=report_path,
        latest_path=latest_path,
        summary=summary,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build an ASIN capture pack from HF alignment rows where expected_units_source is blank/no_source. "
            "This is a non supplier-locked bridge input for F008 full capture."
        )
    )
    parser.add_argument("--alignment-path", default=str(DEFAULT_ALIGNMENT_PATH))
    parser.add_argument("--identity-path", default=str(DEFAULT_IDENTITY_PATH))
    parser.add_argument("--scrape-path", default=str(DEFAULT_SCRAPE_PATH))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--max-asins", type=int, default=0, help="Optional cap for output ASIN rows. 0 = no cap.")
    parser.add_argument(
        "--only-not-in-scrape",
        action="store_true",
        help="Keep only ASINs that are not present in feeder_legacy_scrape_evidence_live.",
    )
    parser.add_argument("--observed-utc", default=None, help="Override observed_utc in YYYY-MM-DDTHH:MM:SSZ.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    build_alignment_missing_asin_pack(
        alignment_path=Path(args.alignment_path),
        identity_path=Path(args.identity_path),
        scrape_path=Path(args.scrape_path),
        output_dir=Path(args.output_dir),
        max_asins=args.max_asins,
        only_not_in_scrape=bool(args.only_not_in_scrape),
        observed_utc=args.observed_utc,
    )


if __name__ == "__main__":
    main()
