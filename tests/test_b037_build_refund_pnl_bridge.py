from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.flows.B import B037_build_refund_pnl_bridge as b037


def _write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)


def _patch_paths(monkeypatch, tmp_path: Path) -> Path:
    out = tmp_path / "out"
    monkeypatch.setattr(b037, "OUT", out)
    monkeypatch.setattr(b037, "REFUNDS_OFFICIAL", out / "financial_events_refunds_official.csv")
    monkeypatch.setattr(b037, "ORDER_LEDGER_FX", out / "order_ledger_fx.csv")
    monkeypatch.setattr(b037, "ORDER_MASTER", out / "order_master.csv")
    monkeypatch.setattr(
        b037,
        "SELLERBOARD_RECONCILIATION",
        out / "systems" / "M" / "sellerboard_bridge" / "b_sellerboard_bridge_order_reconciliation.csv",
    )
    monkeypatch.setattr(b037, "TOKEN_LEDGER", out / "token_ledger_live.csv")
    monkeypatch.setattr(b037, "TOKEN_RETURN_LEDGER", out / "token_return_ledger.csv")
    monkeypatch.setattr(
        b037,
        "AMAZON_RETURN_REPORT_RELS",
        [
            out / "systems" / "B" / "refunds" / "b_fba_customer_returns.csv",
            out / "systems" / "M" / "b_refund_return_api_probe" / "b_fba_customer_returns_probe.csv",
            out / "fba_customer_returns.csv",
        ],
    )
    monkeypatch.setattr(b037, "OUT_DIR", out / "systems" / "B" / "refunds")
    monkeypatch.setattr(b037, "OUT_BRIDGE", out / "systems" / "B" / "refunds" / "b_refund_pnl_bridge.csv")
    monkeypatch.setattr(b037, "OUT_RATE", out / "systems" / "B" / "refunds" / "b_sku_refund_rate.csv")
    return out


def test_b037_maps_api_refund_and_keeps_sellerboard_only_return_separate(monkeypatch, tmp_path: Path) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    _write_csv(
        out / "order_ledger_fx.csv",
        [
            {
                "Date": "2026-05-10T10:00:00Z",
                "Order ID": "ORDER-1",
                "country_code": "GB",
                "SKU": "SKU-A",
                "Quantity Ordered": "10",
                "Price_Total_GBP": "120",
                "Price_ExVAT_GBP": "100",
            },
            {
                "Date": "2026-05-11T10:00:00Z",
                "Order ID": "ORDER-2",
                "country_code": "GB",
                "SKU": "SKU-B",
                "Quantity Ordered": "1",
                "Price_Total_GBP": "12",
                "Price_ExVAT_GBP": "10",
            },
        ],
        ["Date", "Order ID", "country_code", "SKU", "Quantity Ordered", "Price_Total_GBP", "Price_ExVAT_GBP"],
    )
    _write_csv(
        out / "financial_events_refunds_official.csv",
        [
            {
                "Date": "2026-05-20T09:00:00Z",
                "Order ID": "ORDER-1",
                "SKU": "SKU-A",
                "Quantity Ordered": "1",
                "Price_Total": "-12",
                "Price_VAT": "-2",
                "Price_ExVAT": "-10",
                "Shipping_Total": "0",
                "Commission_Total": "1",
                "Digital_Fee_Total": "0",
                "FBA_Fee_Total": "2",
                "FixedClosingFee_Total": "0",
            }
        ],
        [
            "Date",
            "Order ID",
            "SKU",
            "Quantity Ordered",
            "Price_Total",
            "Price_VAT",
            "Price_ExVAT",
            "Shipping_Total",
            "Commission_Total",
            "Digital_Fee_Total",
            "FBA_Fee_Total",
            "FixedClosingFee_Total",
        ],
    )
    _write_csv(
        out / "systems" / "M" / "sellerboard_bridge" / "b_sellerboard_bridge_order_reconciliation.csv",
        [
            {"amazon_order_id": "ORDER-1", "mapped_sku": "SKU-A", "sellerboard_status": "Return", "sellerboard_units": "1", "sellerboard_purchase_utc": "2026-05-10T10:00:00Z"},
            {"amazon_order_id": "ORDER-2", "mapped_sku": "SKU-B", "sellerboard_status": "Return", "sellerboard_units": "1", "sellerboard_purchase_utc": "2026-05-11T10:00:00Z"},
        ],
        ["amazon_order_id", "mapped_sku", "sellerboard_status", "sellerboard_units", "sellerboard_purchase_utc"],
    )

    bridge = b037.build_refund_bridge()
    assert set(bridge["api_refund_proof_state"]) == {"api_proved", "sellerboard_bridge_only"}

    api_row = bridge.loc[bridge["order_id"] == "ORDER-1"].iloc[0]
    assert api_row["sellerboard_match_state"] == "sellerboard_return_witness"
    assert api_row["refund_profit_impact_exvat"] == "-7"
    assert api_row["pnl_inclusion_state"] == "pnl_official_refund_source"

    bridge_only = bridge.loc[bridge["order_id"] == "ORDER-2"].iloc[0]
    assert bridge_only["api_refund_proof_state"] == "sellerboard_bridge_only"
    assert bridge_only["pnl_inclusion_state"] == "not_in_pnl_no_api_refund"

    rates = b037.build_sku_refund_rate(bridge)
    sku_a_30 = rates[(rates["sku"] == "SKU-A") & (rates["basis"] == "sale_cohort") & (rates["window_days"] == "30")].iloc[0]
    assert float(sku_a_30["refund_unit_rate"]) == pytest.approx(0.1)
    assert float(sku_a_30["expected_refund_cost_per_unit_gbp"]) == pytest.approx(0.7)


def test_b037_does_not_recover_cogs_from_return_order_id_alone(monkeypatch, tmp_path: Path) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    _write_csv(
        out / "order_ledger_fx.csv",
        [
            {
                "Date": "2026-05-10T10:00:00Z",
                "Order ID": "ORDER-1",
                "country_code": "GB",
                "SKU": "SKU-A",
                "Quantity Ordered": "1",
                "Price_Total_GBP": "12",
                "Price_ExVAT_GBP": "10",
            }
        ],
        ["Date", "Order ID", "country_code", "SKU", "Quantity Ordered", "Price_Total_GBP", "Price_ExVAT_GBP"],
    )
    _write_csv(
        out / "financial_events_refunds_official.csv",
        [
            {
                "Date": "2026-05-20T09:00:00Z",
                "Order ID": "ORDER-1",
                "SKU": "SKU-A",
                "Quantity Ordered": "1",
                "Price_Total": "-12",
                "Price_VAT": "-2",
                "Price_ExVAT": "-10",
                "Shipping_Total": "0",
                "Commission_Total": "1",
                "Digital_Fee_Total": "0",
                "FBA_Fee_Total": "2",
                "FixedClosingFee_Total": "0",
            }
        ],
        [
            "Date",
            "Order ID",
            "SKU",
            "Quantity Ordered",
            "Price_Total",
            "Price_VAT",
            "Price_ExVAT",
            "Shipping_Total",
            "Commission_Total",
            "Digital_Fee_Total",
            "FBA_Fee_Total",
            "FixedClosingFee_Total",
        ],
    )
    _write_csv(
        out / "token_ledger_live.csv",
        [
            {
                "token_id": "TOKEN-1",
                "seller_sku": "SKU-A",
                "status": "allocated",
                "return_order_id": "ORDER-1",
                "last_return_order_id": "",
                "cost_per_unit": "4.25",
                "notes": "",
            }
        ],
        ["token_id", "seller_sku", "status", "return_order_id", "last_return_order_id", "cost_per_unit", "notes"],
    )

    bridge = b037.build_refund_bridge()

    row = bridge.iloc[0]
    assert row["return_cogs_recovered_exvat"] == "0"
    assert row["refund_profit_impact_exvat"] == "-7"
    assert "no_returned_token_cogs_recovered" in row["notes"]


def test_b037_recovers_cogs_only_from_reusable_return_token_with_return_ledger(monkeypatch, tmp_path: Path) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    _write_csv(
        out / "order_ledger_fx.csv",
        [
            {
                "Date": "2026-05-10T10:00:00Z",
                "Order ID": "ORDER-1",
                "country_code": "GB",
                "SKU": "SKU-A",
                "Quantity Ordered": "1",
                "Price_Total_GBP": "12",
                "Price_ExVAT_GBP": "10",
            }
        ],
        ["Date", "Order ID", "country_code", "SKU", "Quantity Ordered", "Price_Total_GBP", "Price_ExVAT_GBP"],
    )
    _write_csv(
        out / "financial_events_refunds_official.csv",
        [
            {
                "Date": "2026-05-20T09:00:00Z",
                "Order ID": "ORDER-1",
                "SKU": "SKU-A",
                "Quantity Ordered": "1",
                "Price_Total": "-12",
                "Price_VAT": "-2",
                "Price_ExVAT": "-10",
                "Shipping_Total": "0",
                "Commission_Total": "1",
                "Digital_Fee_Total": "0",
                "FBA_Fee_Total": "2",
                "FixedClosingFee_Total": "0",
            }
        ],
        [
            "Date",
            "Order ID",
            "SKU",
            "Quantity Ordered",
            "Price_Total",
            "Price_VAT",
            "Price_ExVAT",
            "Shipping_Total",
            "Commission_Total",
            "Digital_Fee_Total",
            "FBA_Fee_Total",
            "FixedClosingFee_Total",
        ],
    )
    _write_csv(
        out / "token_ledger_live.csv",
        [
            {
                "token_id": "TOKEN-1-R",
                "seller_sku": "SKU-A",
                "status": "available",
                "return_order_id": "",
                "last_return_order_id": "ORDER-1",
                "cost_per_unit": "4.25",
                "notes": "return_sellable_dup:B009-ORDER-1",
            }
        ],
        ["token_id", "seller_sku", "status", "return_order_id", "last_return_order_id", "cost_per_unit", "notes"],
    )
    _write_csv(
        out / "token_return_ledger.csv",
        [
            {
                "return_event_id": "B009-ORDER-1",
                "return_date": "2026-05-21T10:00:00Z",
                "seller_sku": "SKU-A",
                "token_id": "TOKEN-1-R",
                "token_cost": "4.25",
                "currency": "GBP",
                "source": "amazon_customer_return_order_aware",
                "event_type": "CustomerReturns",
            }
        ],
        ["return_event_id", "return_date", "seller_sku", "token_id", "token_cost", "currency", "source", "event_type"],
    )
    _write_csv(
        out / "systems" / "B" / "refunds" / "b_fba_customer_returns.csv",
        [
            {
                "order-id": "ORDER-1",
                "sku": "SKU-A",
                "return-date": "2026-05-21T10:00:00Z",
                "detailed-disposition": "SELLABLE",
            }
        ],
        ["order-id", "sku", "return-date", "detailed-disposition"],
    )

    bridge = b037.build_refund_bridge()

    row = bridge.iloc[0]
    assert row["return_cogs_recovered_exvat"] == "4.25"
    assert row["refund_profit_impact_exvat"] == "-2.75"


def test_b037_blocks_reusable_token_cogs_without_amazon_sellable_return(monkeypatch, tmp_path: Path) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    _write_csv(
        out / "order_ledger_fx.csv",
        [
            {
                "Date": "2026-05-10T10:00:00Z",
                "Order ID": "ORDER-NO-RETURN",
                "country_code": "GB",
                "SKU": "SKU-NO-RETURN",
                "Quantity Ordered": "1",
                "Price_Total_GBP": "12",
                "Price_ExVAT_GBP": "10",
            }
        ],
        ["Date", "Order ID", "country_code", "SKU", "Quantity Ordered", "Price_Total_GBP", "Price_ExVAT_GBP"],
    )
    _write_csv(
        out / "financial_events_refunds_official.csv",
        [
            {
                "Date": "2026-05-20T09:00:00Z",
                "Order ID": "ORDER-NO-RETURN",
                "SKU": "SKU-NO-RETURN",
                "Quantity Ordered": "1",
                "Price_Total": "-12",
                "Price_VAT": "-2",
                "Price_ExVAT": "-10",
                "Shipping_Total": "0",
                "Commission_Total": "1",
                "Digital_Fee_Total": "0",
                "FBA_Fee_Total": "2",
                "FixedClosingFee_Total": "0",
            }
        ],
        [
            "Date",
            "Order ID",
            "SKU",
            "Quantity Ordered",
            "Price_Total",
            "Price_VAT",
            "Price_ExVAT",
            "Shipping_Total",
            "Commission_Total",
            "Digital_Fee_Total",
            "FBA_Fee_Total",
            "FixedClosingFee_Total",
        ],
    )
    _write_csv(
        out / "token_ledger_live.csv",
        [
            {
                "token_id": "TOKEN-NO-RETURN-R",
                "seller_sku": "SKU-NO-RETURN",
                "status": "available",
                "return_order_id": "",
                "last_return_order_id": "ORDER-NO-RETURN",
                "notes": "return_sellable_dup:RET-NO-RETURN",
            }
        ],
        ["token_id", "seller_sku", "status", "return_order_id", "last_return_order_id", "notes"],
    )
    _write_csv(
        out / "token_return_ledger.csv",
        [
            {
                "return_event_id": "RET-NO-RETURN",
                "return_date": "2026-05-21T10:00:00Z",
                "seller_sku": "SKU-NO-RETURN",
                "token_id": "TOKEN-NO-RETURN-R",
                "token_cost": "4.25",
                "currency": "GBP",
                "source": "amazon_customer_return_order_aware",
                "event_type": "CustomerReturns",
            }
        ],
        ["return_event_id", "return_date", "seller_sku", "token_id", "token_cost", "currency", "source", "event_type"],
    )

    bridge = b037.build_refund_bridge()

    row = bridge.iloc[0]
    assert row["return_cogs_recovered_exvat"] == "0"
    assert "return_cogs_blocked_missing_amazon_sellable_return_proof" in row["notes"]


def test_b037_blocks_cogs_from_non_sellable_corrected_return_token(monkeypatch, tmp_path: Path) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    _write_csv(
        out / "order_ledger_fx.csv",
        [
            {
                "Date": "2026-05-10T10:00:00Z",
                "Order ID": "ORDER-NS",
                "country_code": "GB",
                "SKU": "SKU-NS",
                "Quantity Ordered": "1",
                "Price_Total_GBP": "12",
                "Price_ExVAT_GBP": "10",
            }
        ],
        ["Date", "Order ID", "country_code", "SKU", "Quantity Ordered", "Price_Total_GBP", "Price_ExVAT_GBP"],
    )
    _write_csv(
        out / "financial_events_refunds_official.csv",
        [
            {
                "Date": "2026-05-20T09:00:00Z",
                "Order ID": "ORDER-NS",
                "SKU": "SKU-NS",
                "Quantity Ordered": "1",
                "Price_Total": "-12",
                "Price_VAT": "-2",
                "Price_ExVAT": "-10",
                "Shipping_Total": "0",
                "Commission_Total": "1",
                "Digital_Fee_Total": "0",
                "FBA_Fee_Total": "2",
                "FixedClosingFee_Total": "0",
            }
        ],
        [
            "Date",
            "Order ID",
            "SKU",
            "Quantity Ordered",
            "Price_Total",
            "Price_VAT",
            "Price_ExVAT",
            "Shipping_Total",
            "Commission_Total",
            "Digital_Fee_Total",
            "FBA_Fee_Total",
            "FixedClosingFee_Total",
        ],
    )
    _write_csv(
        out / "token_ledger_live.csv",
        [
            {
                "token_id": "TOKEN-NS-R",
                "seller_sku": "SKU-NS",
                "status": "unsellable",
                "return_order_id": "",
                "last_return_order_id": "ORDER-NS",
                "notes": "return_sellable_dup:RET-NS;non_sellable_return_correction_blocked",
            }
        ],
        ["token_id", "seller_sku", "status", "return_order_id", "last_return_order_id", "notes"],
    )
    _write_csv(
        out / "token_return_ledger.csv",
        [
            {
                "return_event_id": "RET-NS",
                "return_date": "2026-05-21T10:00:00Z",
                "seller_sku": "SKU-NS",
                "token_id": "TOKEN-NS-R",
                "token_cost": "4.25",
                "currency": "GBP",
                "source": "amazon_customer_return_order_aware",
                "event_type": "CustomerReturns",
            }
        ],
        ["return_event_id", "return_date", "seller_sku", "token_id", "token_cost", "currency", "source", "event_type"],
    )

    bridge = b037.build_refund_bridge()

    row = bridge.iloc[0]
    assert row["return_cogs_recovered_exvat"] == "0"
    assert row["refund_profit_impact_exvat"] == "-7"
    assert "no_returned_token_cogs_recovered" in row["notes"]
