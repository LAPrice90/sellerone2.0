from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.flows.B import B068_build_level3_fee_shipping_api_proof_map as b068


RAW_COLUMNS = ["order_id", "sku", "posted_date", "amount_type", "amount", "currency"]


def _write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)


def _raw_row(amount_type: str, amount: str = "1.00") -> dict[str, str]:
    return {
        "order_id": "ORDER-1",
        "sku": "SKU-A",
        "posted_date": "2026-05-23T12:00:00Z",
        "amount_type": amount_type,
        "amount": amount,
        "currency": "GBP",
    }


def _write_common_sources(tmp_path: Path, *, include_commission: bool = True) -> None:
    raw_rows = [
        _raw_row("FBAPerUnitFulfillmentFee", "-2.25"),
        _raw_row("ShippingCharge", "3.99"),
        _raw_row("ShippingTax", "0.80"),
        _raw_row("ShippingChargeback", "-3.99"),
    ]
    if include_commission:
        raw_rows.append(_raw_row("Commission", "-1.25"))
    _write_csv(tmp_path / "out" / "financial_events_level3_raw.csv", raw_rows, RAW_COLUMNS)
    _write_csv(tmp_path / "out" / "financial_events_level3_summary.csv", raw_rows, RAW_COLUMNS)
    _write_csv(
        tmp_path / "out" / "financial_events_level3_official.csv",
        [
            {
                "order_id": "ORDER-1",
                "sku": "SKU-A",
                "Commission_ExVAT": "-1.25" if include_commission else "0",
                "FBA_Fee_ExVAT": "-2.25",
                "Shipping_ExVAT": "4.79",
            }
        ],
        ["order_id", "sku", "Commission_ExVAT", "FBA_Fee_ExVAT", "Shipping_ExVAT"],
    )
    _write_csv(
        tmp_path / "out" / "order_master.csv",
        [
            {
                "order_id": "ORDER-1",
                "sku": "SKU-A",
                "Commission_ExVAT": "-1.25" if include_commission else "0",
                "FBA_Fee_ExVAT": "-2.25",
                "Shipping_ExVAT": "4.79",
            }
        ],
        ["order_id", "sku", "Commission_ExVAT", "FBA_Fee_ExVAT", "Shipping_ExVAT"],
    )
    _write_csv(
        tmp_path / "out" / "financial_events_refunds.csv",
        [
            _raw_row("Refund_Commission", "1.25"),
            _raw_row("Refund_ShippingChargeback", "3.99"),
        ],
        RAW_COLUMNS,
    )
    _write_csv(
        tmp_path / "out" / "financial_events_refunds_official.csv",
        [{"order_id": "ORDER-1", "sku": "SKU-A", "Refund_Commission": "1.25"}],
        ["order_id", "sku", "Refund_Commission"],
    )
    _write_csv(
        tmp_path / "out" / "fee_detail_ledger_api.csv",
        [],
        ["posted_date", "transaction_id", "fee_type", "amount_total", "currency"],
    )
    _write_csv(
        tmp_path / "out" / "financial_transactions_v2024_breakdowns.csv",
        [
            {"transaction_type": "Shipment", "breakdown_type": "Expenses"},
            {"transaction_type": "Refund", "breakdown_type": "Refunded Expenses"},
        ],
        ["transaction_type", "breakdown_type"],
    )


def test_b068_maps_existing_level3_fee_and_shipping_sources_without_live_use(tmp_path: Path) -> None:
    _write_common_sources(tmp_path)

    result = b068.build_level3_fee_shipping_api_proof_map(
        root=tmp_path,
        observed_utc="2026-06-04T11:00:00Z",
    )
    proof_map = result["proof_map"]
    summary = {row["metric"]: row["value"] for _, row in result["summary"].iterrows()}
    labels = {row["money_field"]: row["proof_label"] for _, row in proof_map.iterrows()}

    assert summary["status"] == "ok"
    assert labels["commission"] == "api_source_available"
    assert labels["fba_fee"] == "api_source_available"
    assert labels["shipping_income"] == "api_source_available"
    assert labels["shipping_chargeback_or_cost"] == "api_source_available"
    assert labels["refund_fee_reversals"] == "api_source_available"
    assert labels["fee_detail_ledger_api"] == "superseded_non_blocking"
    assert summary["superseded_non_blocking_rows"] == "1"
    assert set(proof_map["live_roi_use_allowed"]) == {"0"}
    assert set(proof_map["roi_or_restock_use_allowed"]) == {"0"}
    assert set(proof_map["sellerboard_final_truth_allowed"]) == {"0"}


def test_b068_marks_missing_source_without_treating_fee_detail_empty_as_final_truth(tmp_path: Path) -> None:
    _write_common_sources(tmp_path, include_commission=False)

    result = b068.build_level3_fee_shipping_api_proof_map(
        root=tmp_path,
        observed_utc="2026-06-04T11:00:00Z",
    )
    proof_map = result["proof_map"]
    labels = {row["money_field"]: row["proof_label"] for _, row in proof_map.iterrows()}
    fee_detail_reason = proof_map.loc[
        proof_map["money_field"] == "fee_detail_ledger_api",
        "proof_reason",
    ].iloc[0]

    assert labels["commission"] == "api_source_missing"
    assert labels["fee_detail_ledger_api"] == "api_source_missing"
    assert "not ServiceFee rows" in fee_detail_reason


def test_b068_writes_proof_map_and_summary(tmp_path: Path) -> None:
    _write_common_sources(tmp_path)

    result = b068.build_level3_fee_shipping_api_proof_map(
        root=tmp_path,
        observed_utc="2026-06-04T11:00:00Z",
    )
    paths = b068.write_level3_fee_shipping_api_proof_map_outputs(result, root=tmp_path)

    assert paths["proof_map"].exists()
    assert paths["summary"].exists()
