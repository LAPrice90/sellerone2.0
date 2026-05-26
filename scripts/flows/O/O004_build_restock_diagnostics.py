from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from scripts.flows.O._paths import ensure_o_directories, get_o_path_contract
from scripts.flows.O._schemas import get_o_output_contract


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _summary_row(metric: str, value: int | float | str) -> dict[str, str]:
    return {"metric": metric, "value": str(value)}


def _truthy_series(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin({"1", "true", "yes", "y", "on"})


def _ensure_text_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for col in columns:
        if col not in df.columns:
            df[col] = ""
    return df


def build_restock_diagnostics(root: Path | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    ensure_o_directories(root=root_path)

    live_dir = root_path / get_o_output_contract("restock_source_view").rel_path
    source_path = live_dir
    rec_path = root_path / get_o_output_contract("restock_recommendations_live").rel_path

    diagnostics_path = root_path / "out" / "systems" / "O" / "live" / "restock_diagnostics.csv"
    summary_path = root_path / "out" / "systems" / "O" / "live" / "restock_diagnostics_summary.csv"

    if not source_path.exists() or not rec_path.exists():
        detail_df = pd.DataFrame(columns=["diagnostics_utc", "seller_sku", "diagnostic_key", "diagnostic_value"])
        summary_df = pd.DataFrame(
            [
                _summary_row("diagnostics_utc", _utc_now_iso()),
                _summary_row("source_exists", int(source_path.exists())),
                _summary_row("recommendations_exists", int(rec_path.exists())),
            ]
        )
        diagnostics_path.parent.mkdir(parents=True, exist_ok=True)
        detail_df.to_csv(diagnostics_path, index=False)
        summary_df.to_csv(summary_path, index=False)
        print({"status": "success", "rows": 0, "summary_rows": len(summary_df), "diagnostics": str(diagnostics_path), "summary": str(summary_path)})
        return detail_df, summary_df

    source_df = pd.read_csv(source_path, dtype=str).fillna("")
    rec_df = pd.read_csv(rec_path, dtype=str).fillna("")
    rec_df = _ensure_text_columns(rec_df, ["cost_mode", "recommendation_basis"])
    merged = source_df.merge(
        rec_df[
            [
                "seller_sku",
                "recommendation_status",
                "reason_codes",
                "recommended_qty_raw",
                "recommended_qty_rounded",
                "forward_roi_pct",
                "confidence_note",
                "blocked_note",
                "cost_mode",
                "recommendation_basis",
            ]
        ].rename(columns={"cost_mode": "recommendation_cost_mode"}),
        on="seller_sku",
        how="left",
    )
    merged = _ensure_text_columns(
        merged,
        [
            "current_cost_source",
            "current_cost_confidence",
            "current_cost_value_gbp",
            "current_cost_class",
            "cost_mode",
            "recommendation_cost_mode",
            "recommendation_basis",
            "cost_source_type",
            "cost_source_reference",
            "current_cost_truth_type",
            "current_supplier_cost_source",
            "market_price_basis_used",
            "sale_status",
            "sale_status_normalized",
            "supplier_catalog_price",
            "last_purchase_price",
            "velocity_30d",
            "available_now",
            "amazon_inbound_working",
            "amazon_inbound_shipped",
            "amazon_inbound_receiving",
            "source_notes",
            "market_price_gbp",
            "is_active_candidate",
            "has_current_cost_input",
            "has_current_market_price_input",
            "has_demand_input",
            "has_minimum_restock_inputs",
            "coverage_block_reason",
        ],
    )
    merged["cost_mode"] = merged["cost_mode"].astype(str)
    merged.loc[merged["cost_mode"].str.strip().eq(""), "cost_mode"] = merged["recommendation_cost_mode"].astype(str)
    merged.loc[merged["cost_mode"].astype(str).str.strip().eq(""), "cost_mode"] = "live"
    merged["diagnostics_utc"] = _utc_now_iso()
    merged["missing_supplier_catalog_price"] = merged["supplier_catalog_price"].astype(str).str.strip().eq("")
    merged["missing_last_purchase_price"] = merged["last_purchase_price"].astype(str).str.strip().eq("")
    merged["missing_both_cost_fields"] = merged["missing_supplier_catalog_price"] & merged["missing_last_purchase_price"]
    merged["missing_market_price_context"] = (
        merged["market_price_gbp"].astype(str).str.strip().eq("")
        | merged["market_price_basis_used"].astype(str).str.strip().eq("MISSING_MARKET_CONTEXT")
    )
    merged["zero_or_null_velocity_30d"] = _num(merged["velocity_30d"]).fillna(0).le(0)
    merged["zero_or_null_available_now"] = _num(merged["available_now"]).fillna(0).le(0)
    merged["zero_or_null_inbound_working"] = _num(merged["amazon_inbound_working"]).fillna(0).le(0)
    merged["zero_or_null_inbound_shipped"] = _num(merged["amazon_inbound_shipped"]).fillna(0).le(0)
    merged["zero_or_null_inbound_receiving"] = _num(merged["amazon_inbound_receiving"]).fillna(0).le(0)
    merged["reduced_confidence_row"] = merged["source_notes"].astype(str).str.contains("REDUCED_CONFIDENCE", na=False)
    merged["fallback_cost_row"] = merged["current_supplier_cost_source"].astype(str).str.strip().eq("last_purchase_price")
    merged["roi_below_10"] = _num(merged["forward_roi_pct"]).lt(10).fillna(False)
    merged["roi_between_10_and_15"] = (_num(merged["forward_roi_pct"]).ge(10) & _num(merged["forward_roi_pct"]).lt(15)).fillna(False)
    merged["roi_above_15"] = _num(merged["forward_roi_pct"]).ge(15).fillna(False)
    merged["roi_null"] = _num(merged["forward_roi_pct"]).isna()
    merged["net_needed_qty_raw_le_0"] = _num(merged["recommended_qty_raw"]).fillna(0).le(0)
    merged["test_spend_capped"] = merged["reason_codes"].astype(str).str.contains("TEST_SPEND_CAP_APPLIED", na=False)
    merged["moq_pack_rounding_applied"] = _num(merged["recommended_qty_rounded"]).gt(_num(merged["recommended_qty_raw"])).fillna(False)
    merged["is_active_candidate"] = _truthy_series(merged.get("is_active_candidate", pd.Series(["0"] * len(merged))))
    merged["has_current_cost_input"] = _truthy_series(merged.get("has_current_cost_input", pd.Series(["0"] * len(merged))))
    merged["has_current_market_price_input"] = _truthy_series(merged.get("has_current_market_price_input", pd.Series(["0"] * len(merged))))
    merged["has_demand_input"] = _truthy_series(merged.get("has_demand_input", pd.Series(["0"] * len(merged))))
    merged["has_minimum_restock_inputs"] = _truthy_series(merged.get("has_minimum_restock_inputs", pd.Series(["0"] * len(merged))))
    merged["current_cost_truth_type"] = merged["current_cost_truth_type"].astype(str).str.strip()
    merged.loc[
        merged["current_cost_truth_type"].eq("") & merged["has_current_cost_input"] & merged["cost_mode"].astype(str).str.strip().str.lower().eq("test"),
        "current_cost_truth_type",
    ] = "test_cost_truth"
    merged.loc[
        merged["current_cost_truth_type"].eq("") & merged["has_current_cost_input"] & (~merged["cost_mode"].astype(str).str.strip().str.lower().eq("test")),
        "current_cost_truth_type",
    ] = "live_cost_truth"
    merged.loc[merged["current_cost_truth_type"].eq(""), "current_cost_truth_type"] = "no_cost_truth"
    merged["coverage_block_reason"] = merged.get("coverage_block_reason", "").astype(str).str.strip()
    merged["active_missing_cost_only"] = merged["is_active_candidate"] & (~merged["has_current_cost_input"]) & merged["has_current_market_price_input"] & merged["has_demand_input"]
    merged["active_missing_market_only"] = merged["is_active_candidate"] & merged["has_current_cost_input"] & (~merged["has_current_market_price_input"]) & merged["has_demand_input"]
    merged["active_missing_demand_only"] = merged["is_active_candidate"] & merged["has_current_cost_input"] & merged["has_current_market_price_input"] & (~merged["has_demand_input"])
    merged["active_missing_both_cost_and_market"] = merged["is_active_candidate"] & (~merged["has_current_cost_input"]) & (~merged["has_current_market_price_input"]) & merged["has_demand_input"]
    merged["active_missing_multiple_inputs"] = merged["is_active_candidate"] & (
        ((~merged["has_current_cost_input"]).astype(int) + (~merged["has_current_market_price_input"]).astype(int) + (~merged["has_demand_input"]).astype(int)) >= 2
    )
    merged["active_test_cost_truth"] = merged["is_active_candidate"] & merged["has_current_cost_input"] & merged["cost_mode"].astype(str).str.strip().str.lower().eq("test")
    merged["active_live_cost_truth"] = merged["is_active_candidate"] & merged["has_current_cost_input"] & (~merged["cost_mode"].astype(str).str.strip().str.lower().eq("test"))
    merged["active_no_cost_truth"] = merged["is_active_candidate"] & (~merged["has_current_cost_input"])
    merged["active_blocked_weak_demand_only"] = merged["is_active_candidate"] & merged["has_current_cost_input"] & merged["has_current_market_price_input"] & (~merged["has_demand_input"])
    merged["active_actionable_now"] = merged["has_minimum_restock_inputs"]
    merged["active_other_blocked"] = merged["is_active_candidate"] & (~merged["active_actionable_now"]) & (~merged["active_missing_cost_only"]) & (~merged["active_missing_market_only"]) & (~merged["active_missing_demand_only"]) & (~merged["active_missing_both_cost_and_market"])

    detail_cols = [
        "diagnostics_utc",
        "seller_sku",
        "asin",
        "supplier_code",
        "supplier_name",
        "sale_status",
        "sale_status_normalized",
        "cost_mode",
        "recommendation_basis",
        "cost_source_type",
        "cost_source_reference",
        "current_cost_truth_type",
        "current_cost_source",
        "current_cost_confidence",
        "current_cost_value_gbp",
        "current_cost_class",
        "current_supplier_cost_source",
        "market_price_basis_used",
        "velocity_30d",
        "is_active_candidate",
        "has_current_cost_input",
        "has_current_market_price_input",
        "has_demand_input",
        "has_minimum_restock_inputs",
        "coverage_block_reason",
        "recommendation_status",
        "reason_codes",
        "recommended_qty_raw",
        "recommended_qty_rounded",
        "forward_roi_pct",
        "confidence_note",
        "blocked_note",
        "missing_supplier_catalog_price",
        "missing_last_purchase_price",
        "missing_both_cost_fields",
        "missing_market_price_context",
        "zero_or_null_velocity_30d",
        "zero_or_null_available_now",
        "zero_or_null_inbound_working",
        "zero_or_null_inbound_shipped",
        "zero_or_null_inbound_receiving",
        "reduced_confidence_row",
        "fallback_cost_row",
        "roi_below_10",
        "roi_between_10_and_15",
        "roi_above_15",
        "roi_null",
        "net_needed_qty_raw_le_0",
        "test_spend_capped",
        "moq_pack_rounding_applied",
        "active_actionable_now",
        "active_missing_cost_only",
        "active_missing_market_only",
        "active_missing_demand_only",
        "active_missing_both_cost_and_market",
        "active_missing_multiple_inputs",
        "active_test_cost_truth",
        "active_live_cost_truth",
        "active_no_cost_truth",
        "active_blocked_weak_demand_only",
        "active_other_blocked",
    ]
    detail_df = merged[detail_cols].copy()

    reason_counts = (
        rec_df["reason_codes"]
        .astype(str)
        .str.split(",")
        .explode()
        .fillna("")
        .str.strip()
    )
    reason_counts = reason_counts[reason_counts != ""].value_counts()

    summary_rows: list[dict[str, str]] = []
    summary_rows.append(_summary_row("diagnostics_utc", _utc_now_iso()))
    summary_rows.append(_summary_row("rows_source", len(source_df)))
    summary_rows.append(_summary_row("rows_recommendations", len(rec_df)))
    summary_rows.append(_summary_row("rows_recommendation_wait", int(rec_df["recommendation_status"].eq("wait").sum())))
    summary_rows.append(_summary_row("rows_recommendation_test_restock", int(rec_df["recommendation_status"].eq("test_restock").sum())))
    summary_rows.append(_summary_row("rows_recommendation_full_restock", int(rec_df["recommendation_status"].eq("full_restock").sum())))
    summary_rows.append(_summary_row("missing_supplier_catalog_price", int(detail_df["missing_supplier_catalog_price"].sum())))
    summary_rows.append(_summary_row("missing_last_purchase_price", int(detail_df["missing_last_purchase_price"].sum())))
    summary_rows.append(_summary_row("missing_both_cost_fields", int(detail_df["missing_both_cost_fields"].sum())))
    summary_rows.append(_summary_row("missing_market_price_context", int(detail_df["missing_market_price_context"].sum())))
    summary_rows.append(_summary_row("zero_or_null_velocity_30d", int(detail_df["zero_or_null_velocity_30d"].sum())))
    summary_rows.append(_summary_row("zero_or_null_available_now", int(detail_df["zero_or_null_available_now"].sum())))
    summary_rows.append(_summary_row("zero_or_null_inbound_working", int(detail_df["zero_or_null_inbound_working"].sum())))
    summary_rows.append(_summary_row("zero_or_null_inbound_shipped", int(detail_df["zero_or_null_inbound_shipped"].sum())))
    summary_rows.append(_summary_row("zero_or_null_inbound_receiving", int(detail_df["zero_or_null_inbound_receiving"].sum())))
    summary_rows.append(_summary_row("reduced_confidence_rows", int(detail_df["reduced_confidence_row"].sum())))
    summary_rows.append(_summary_row("fallback_cost_rows", int(detail_df["fallback_cost_row"].sum())))
    summary_rows.append(_summary_row("roi_below_10", int(detail_df["roi_below_10"].sum())))
    summary_rows.append(_summary_row("roi_between_10_and_15", int(detail_df["roi_between_10_and_15"].sum())))
    summary_rows.append(_summary_row("roi_above_15", int(detail_df["roi_above_15"].sum())))
    summary_rows.append(_summary_row("roi_null", int(detail_df["roi_null"].sum())))
    summary_rows.append(_summary_row("net_needed_qty_raw_le_0", int(detail_df["net_needed_qty_raw_le_0"].sum())))
    summary_rows.append(_summary_row("test_spend_capped_rows", int(detail_df["test_spend_capped"].sum())))
    summary_rows.append(_summary_row("moq_pack_rounding_changed_rows", int(detail_df["moq_pack_rounding_applied"].sum())))
    summary_rows.append(_summary_row("rows_active_only", int(detail_df["is_active_candidate"].sum())))
    summary_rows.append(_summary_row("rows_inactive_or_unknown", int((~detail_df["is_active_candidate"]).sum())))
    summary_rows.append(_summary_row("active_rows_with_demand", int((detail_df["is_active_candidate"] & detail_df["has_demand_input"]).sum())))
    summary_rows.append(_summary_row("active_rows_with_cost", int((detail_df["is_active_candidate"] & detail_df["has_current_cost_input"]).sum())))
    summary_rows.append(_summary_row("active_rows_with_market_price", int((detail_df["is_active_candidate"] & detail_df["has_current_market_price_input"]).sum())))
    summary_rows.append(_summary_row("active_rows_with_demand_and_cost", int((detail_df["is_active_candidate"] & detail_df["has_demand_input"] & detail_df["has_current_cost_input"]).sum())))
    summary_rows.append(_summary_row("active_rows_with_demand_and_market", int((detail_df["is_active_candidate"] & detail_df["has_demand_input"] & detail_df["has_current_market_price_input"]).sum())))
    summary_rows.append(_summary_row("active_rows_with_cost_and_market", int((detail_df["is_active_candidate"] & detail_df["has_current_cost_input"] & detail_df["has_current_market_price_input"]).sum())))
    summary_rows.append(_summary_row("active_rows_with_demand_cost_market", int((detail_df["is_active_candidate"] & detail_df["has_demand_input"] & detail_df["has_current_cost_input"] & detail_df["has_current_market_price_input"]).sum())))
    summary_rows.append(_summary_row("active_actionable_now", int(detail_df["active_actionable_now"].sum())))
    summary_rows.append(_summary_row("active_missing_cost_only", int(detail_df["active_missing_cost_only"].sum())))
    summary_rows.append(_summary_row("active_missing_market_only", int(detail_df["active_missing_market_only"].sum())))
    summary_rows.append(_summary_row("active_missing_both_cost_and_market", int(detail_df["active_missing_both_cost_and_market"].sum())))
    summary_rows.append(_summary_row("active_missing_demand_only", int(detail_df["active_missing_demand_only"].sum())))
    summary_rows.append(_summary_row("active_missing_multiple_inputs", int(detail_df["active_missing_multiple_inputs"].sum())))
    summary_rows.append(_summary_row("active_rows_with_test_cost_truth", int(detail_df["active_test_cost_truth"].sum())))
    summary_rows.append(_summary_row("active_rows_with_live_cost_truth", int(detail_df["active_live_cost_truth"].sum())))
    summary_rows.append(_summary_row("active_rows_with_no_cost_truth", int(detail_df["active_no_cost_truth"].sum())))
    summary_rows.append(_summary_row("active_blocked_weak_demand_only", int(detail_df["active_blocked_weak_demand_only"].sum())))
    summary_rows.append(_summary_row("active_other_blocked", int(detail_df["active_other_blocked"].sum())))
    summary_rows.append(
        _summary_row(
            "active_rows_with_current_supplier_cost",
            int((detail_df["is_active_candidate"] & detail_df["current_cost_class"].astype(str).eq("current_supplier_cost")).sum()),
        )
    )
    summary_rows.append(
        _summary_row(
            "active_rows_with_last_purchase_fallback_only",
            int((detail_df["is_active_candidate"] & detail_df["current_cost_class"].astype(str).eq("last_purchase_fallback")).sum()),
        )
    )
    summary_rows.append(
        _summary_row(
            "active_rows_with_no_cost_input",
            int((detail_df["is_active_candidate"] & detail_df["current_cost_class"].astype(str).eq("no_cost")).sum()),
        )
    )
    summary_rows.append(
        _summary_row(
            "active_rows_with_ambiguous_cost",
            int((detail_df["is_active_candidate"] & detail_df["current_cost_class"].astype(str).eq("ambiguous_cost")).sum()),
        )
    )
    summary_rows.append(
        _summary_row(
            "active_rows_cost_confidence_weak_for_roi",
            int(
                (
                    detail_df["is_active_candidate"]
                    & detail_df["current_cost_value_gbp"].astype(str).str.strip().ne("")
                    & detail_df["current_cost_confidence"].astype(str).isin({"low", "none"})
                ).sum()
            ),
        )
    )
    summary_rows.append(
        _summary_row(
            "active_rows_with_demand_market_current_supplier_cost",
            int(
                (
                    detail_df["is_active_candidate"]
                    & detail_df["has_demand_input"]
                    & detail_df["has_current_market_price_input"]
                    & detail_df["current_cost_class"].astype(str).eq("current_supplier_cost")
                ).sum()
            ),
        )
    )
    summary_rows.append(
        _summary_row(
            "active_rows_with_demand_market_last_purchase_fallback",
            int(
                (
                    detail_df["is_active_candidate"]
                    & detail_df["has_demand_input"]
                    & detail_df["has_current_market_price_input"]
                    & detail_df["current_cost_class"].astype(str).eq("last_purchase_fallback")
                ).sum()
            ),
        )
    )

    for reason, count in reason_counts.items():
        summary_rows.append(_summary_row(f"reason_count::{reason}", int(count)))

    coverage_reason_counts = detail_df["coverage_block_reason"].astype(str).str.strip().value_counts()
    for reason, count in coverage_reason_counts.items():
        if reason:
            summary_rows.append(_summary_row(f"coverage_block_reason::{reason}", int(count)))

    active_cost_source_counts = (
        detail_df.loc[detail_df["is_active_candidate"], "current_cost_source"]
        .astype(str)
        .str.strip()
        .replace("", "missing")
        .value_counts()
    )
    for source, count in active_cost_source_counts.items():
        summary_rows.append(_summary_row(f"active_cost_source::{source}", int(count)))

    active_cost_confidence_counts = (
        detail_df.loc[detail_df["is_active_candidate"], "current_cost_confidence"]
        .astype(str)
        .str.strip()
        .replace("", "missing")
        .value_counts()
    )
    for confidence, count in active_cost_confidence_counts.items():
        summary_rows.append(_summary_row(f"active_cost_confidence::{confidence}", int(count)))

    active_cost_truth_type_counts = (
        detail_df.loc[detail_df["is_active_candidate"], "current_cost_truth_type"]
        .astype(str)
        .str.strip()
        .replace("", "missing")
        .value_counts()
    )
    for truth_type, count in active_cost_truth_type_counts.items():
        summary_rows.append(_summary_row(f"active_cost_truth_type::{truth_type}", int(count)))

    summary_df = pd.DataFrame(summary_rows)
    diagnostics_path.parent.mkdir(parents=True, exist_ok=True)
    detail_df.to_csv(diagnostics_path, index=False)
    summary_df.to_csv(summary_path, index=False)
    print(
        {
            "status": "success",
            "rows": len(detail_df),
            "summary_rows": len(summary_df),
            "diagnostics": str(diagnostics_path),
            "summary": str(summary_path),
        }
    )
    return detail_df, summary_df


def main() -> None:
    build_restock_diagnostics()


if __name__ == "__main__":
    main()
