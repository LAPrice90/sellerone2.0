from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass(frozen=True)
class SourceContract:
    source_path: str
    owner_flow: str
    phase1_requirement: str
    required_columns: Tuple[str, ...]
    fallback_rules: Tuple[str, ...]
    must_not_duplicate: Tuple[str, ...]


_SOURCE_CONTRACTS: Dict[str, SourceContract] = {
    "inventory_summaries": SourceContract(
        source_path="out/inventory_summaries.csv",
        owner_flow="A",
        phase1_requirement="mandatory",
        required_columns=(
            "seller_sku",
            "asin",
            "total_quantity",
            "available",
            "inbound_working",
            "inbound_shipped",
            "inbound_receiving",
            "last_updated_time",
        ),
        fallback_rules=(
            "No safe fallback for stock truth. Missing source blocks recommendation build for affected SKUs.",
        ),
        must_not_duplicate=(
            "amazon_current_stock_truth",
            "amazon_inbound_bucket_truth",
        ),
    ),
    "order_master": SourceContract(
        source_path="out/order_master.csv",
        owner_flow="B",
        phase1_requirement="optional",
        required_columns=(
            "Date",
            "Order ID",
            "country_code",
            "SKU",
            "Quantity Ordered",
            "currency_code",
            "Price_ExVAT",
            "COGS_ExVAT",
            "FBA_Fee_ExVAT",
        ),
        fallback_rules=(
            "If unavailable, use `sku_performance_summary` for aggregate economics context.",
            "Do not block recommendation generation when E aggregate economics are present.",
        ),
        must_not_duplicate=(
            "order_line_history_truth",
            "historical_sales_fact_truth",
        ),
    ),
    "sku_sales_velocity": SourceContract(
        source_path="out/sku_sales_velocity.csv",
        owner_flow="E",
        phase1_requirement="mandatory",
        required_columns=(
            "sku",
            "v7",
            "v30",
            "v90",
            "available",
            "total_quantity",
            "asof_date",
        ),
        fallback_rules=(
            "Use `v30` as primary demand signal, with `v7` and `v90` as context.",
            "If demand windows are missing for a SKU, keep status cautious and do not auto-buy.",
        ),
        must_not_duplicate=(
            "velocity_truth",
            "days_in_stock_estimation_truth",
        ),
    ),
    "sku_performance_summary": SourceContract(
        source_path="out/sku_performance_summary.csv",
        owner_flow="E",
        phase1_requirement="mandatory",
        required_columns=(
            "sku",
            "expected_refund_cost_per_unit_gbp",
            "roi_at_our_price_pct",
            "roi_at_buy_box_price_pct",
            "break_even_price_gbp",
            "current_token_cost_gbp",
            "asof_date",
        ),
        fallback_rules=(
            "If economics context is missing, recommendation must downgrade to blocked/unknown economics.",
            "Do not infer forward buy approval from historical ROI alone when current buy cost is missing.",
        ),
        must_not_duplicate=(
            "economics_summary_truth",
            "realized_roi_context_truth",
        ),
    ),
    "product_db_preview": SourceContract(
        source_path="out/product_db_preview.csv",
        owner_flow="A/B integration snapshot",
        phase1_requirement="mandatory",
        required_columns=(
            "seller_sku",
            "asin",
            "supplier_code",
            "supplier_name",
            "supplier_pack_size",
            "moq",
            "supplier_catalog_price",
            "last_purchase_price",
            "sale_status",
            "vat_rate",
        ),
        fallback_rules=(
            "Current buy cost priority: `supplier_catalog_price`, then `last_purchase_price`.",
            "If both cost fields are missing, SKU must be blocked as `blocked_missing_cost`.",
        ),
        must_not_duplicate=(
            "supplier_identity_truth",
            "current_supplier_cost_truth",
        ),
    ),
    "listing_offer_snapshot_latest": SourceContract(
        source_path="out/listing_offer_snapshot_latest.csv",
        owner_flow="H",
        phase1_requirement="optional",
        required_columns=(
            "timestamp_utc",
            "asof_date",
            "sku",
            "asin",
            "our_price",
            "buy_box_price",
            "lowest_fba_price",
        ),
        fallback_rules=(
            "Price basis order: `buy_box_price`, then `lowest_fba_price`, then `our_price`.",
            "If source is stale or missing, fallback to E summary market context with reduced confidence.",
        ),
        must_not_duplicate=(
            "live_market_price_truth",
            "buy_box_presence_truth",
        ),
    ),
    "feeder_backtest_summary_live": SourceContract(
        source_path="out/systems/F/live/feeder_backtest_summary_live.csv",
        owner_flow="F",
        phase1_requirement="optional",
        required_columns=(
            "observed_utc",
            "policy_id",
            "seller_sku",
            "asin",
            "summary_status",
            "history_confidence",
            "market_viability_score",
            "exit_risk_score",
            "estimated_total_profit_gbp",
            "estimated_monthly_profit_gbp",
            "capital_lockup_days",
            "sellable_ceiling_zone",
            "amazon_risk_level",
            "compression_risk_level",
            "recommendation",
            "manual_review_reason",
        ),
        fallback_rules=(
            "If unavailable, keep O backtest columns blank and continue restock processing.",
            "Backtest fields are advisory and must not block O recommendation rendering.",
        ),
        must_not_duplicate=(
            "backtest_viability_truth",
            "backtest_exit_risk_truth",
        ),
    ),
    "f_price_list_manager_batch_rows": SourceContract(
        source_path="out/systems/F/price_list_manager/test_mode/batch_rows.csv",
        owner_flow="F",
        phase1_requirement="optional",
        required_columns=(
            "batch_id",
            "supplier_id",
            "row_key",
            "supplier_sku",
            "supplier_title",
            "barcode",
            "unit_cost",
            "currency",
            "vat_rate",
        ),
        fallback_rules=(
            "Use collected supplier price-list rows as current list-cost truth when a SKU/barcode identity match exists.",
            "If no collected price-list row matches, fall back to Product DB catalog or last purchase cost with reduced confidence.",
        ),
        must_not_duplicate=(
            "supplier_price_list_collector_truth",
        ),
    ),
    "f_price_list_manager_batches": SourceContract(
        source_path="out/systems/F/price_list_manager/test_mode/price_list_batches.csv",
        owner_flow="F",
        phase1_requirement="optional",
        required_columns=(
            "batch_id",
            "supplier_id",
            "source_received_at_utc",
            "source_file_path",
            "converted_file_path",
            "batch_status",
            "updated_at_utc",
        ),
        fallback_rules=(
            "Use batch metadata only for freshness and lineage; do not treat it as product or cost truth by itself.",
        ),
        must_not_duplicate=(
            "supplier_price_list_freshness_truth",
        ),
    ),
}


def get_phase1_source_contracts() -> Dict[str, SourceContract]:
    return dict(_SOURCE_CONTRACTS)


def get_source_contract(name: str) -> SourceContract:
    if name not in _SOURCE_CONTRACTS:
        available = ",".join(sorted(_SOURCE_CONTRACTS.keys()))
        raise ValueError(f"unknown O source contract '{name}', expected one of: {available}")
    return _SOURCE_CONTRACTS[name]
