from __future__ import annotations

import sqlite3
import pandas as pd
import pytest

import scripts.flows.B.B004_build_order_master as b004
from scripts.flows.B.B004_build_order_master import _index_by_key, _l2_row_is_viable


def test_l2_viable_when_l2_qty_positive():
    l1 = pd.Series({"Quantity Ordered": "1"})
    l2 = pd.Series({"Quantity Ordered": "1"})
    assert _l2_row_is_viable(l2, l1) is True


def test_l2_not_viable_when_l2_zero_and_no_payload_with_l1_positive_qty():
    l1 = pd.Series({"Quantity Ordered": "1"})
    l2 = pd.Series(
        {
            "Quantity Ordered": "0",
            "Price_Total": "",
            "Price_VAT": "",
            "Price_ExVAT": "",
            "FBA_Fee_Total": "",
            "Commission_Total": "",
        }
    )
    assert _l2_row_is_viable(l2, l1) is False


def test_l2_viable_when_l2_zero_but_financial_payload_present():
    l1 = pd.Series({"Quantity Ordered": "1"})
    l2 = pd.Series(
        {
            "Quantity Ordered": "0",
            "Price_Total": "9.99",
            "FBA_Fee_Total": "-1.75",
        }
    )
    assert _l2_row_is_viable(l2, l1) is True


def test_index_by_key_picks_duplicate_with_positive_qty():
    df = pd.DataFrame(
        [
            {"Order ID": "A-1", "SKU": "SKU-1", "Quantity Ordered": "0", "Price_Total": "0.00"},
            {"Order ID": "A-1", "SKU": "SKU-1", "Quantity Ordered": "4", "Price_Total": "0.00"},
        ]
    )
    index, stats = _index_by_key(df, source="l3")
    row = index[("A-1", "SKU-1")]
    assert str(row.get("Quantity Ordered")) == "4"
    assert stats["duplicate_groups"] == 1
    assert stats["duplicate_rows"] == 1


def test_index_by_key_uses_latest_date_as_tiebreaker():
    df = pd.DataFrame(
        [
            {
                "Order ID": "A-2",
                "SKU": "SKU-2",
                "Quantity Ordered": "1",
                "Price_Total": "10.00",
                "Date": "2026-04-02T08:00:00Z",
            },
            {
                "Order ID": "A-2",
                "SKU": "SKU-2",
                "Quantity Ordered": "1",
                "Price_Total": "10.00",
                "Date": "2026-04-03T08:00:00Z",
            },
        ]
    )
    index, _ = _index_by_key(df, source="l3")
    row = index[("A-2", "SKU-2")]
    assert str(row.get("Date")) == "2026-04-03T08:00:00Z"


def test_b004_keeps_provisional_row_without_token_cogs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "out"
    out.mkdir()

    pd.DataFrame(
        [
            {
                "Date": "2026-04-18T09:42:05Z",
                "Order ID": "ORDER-1",
                "marketplace_id": "A1F83G8C2ARO7P",
                "SKU": "SKU-1",
                "Quantity Ordered": "1",
                "Price_Total": "10.00",
                "Price_VAT": "1.67",
                "Price_ExVAT": "8.33",
                "Shipping_Total": "0.00",
                "Shipping_VAT": "0.00",
                "Shipping_ExVAT": "0.00",
                "Gift_Total": "0.00",
                "Gift_VAT": "0.00",
                "Gift_ExVAT": "0.00",
                "Promotion_Total": "0.00",
                "Promotion_VAT": "0.00",
                "Promotion_ExVAT": "0.00",
                "COGS_Total": "",
                "COGS_VAT": "",
                "COGS_ExVAT": "",
                "FBA_Fee_Total": "-3.18",
                "FBA_Fee_VAT": "-0.53",
                "FBA_Fee_ExVAT": "-2.65",
                "Commission_Total": "-0.60",
                "Commission_VAT": "-0.10",
                "Commission_ExVAT": "-0.50",
            }
        ]
    ).to_csv(out / "financial_events_level1.csv", index=False)
    pd.DataFrame(
        [
            {
                "Date": "2026-04-18T09:42:05Z",
                "Order ID": "ORDER-1",
                "marketplace_id": "A1F83G8C2ARO7P",
                "SKU": "SKU-1",
                "Quantity Ordered": "1",
                "Price_Total": "10.00",
                "Price_VAT": "1.67",
                "Price_ExVAT": "8.33",
                "Shipping_Total": "0.00",
                "Shipping_VAT": "0.00",
                "Shipping_ExVAT": "0.00",
                "Gift_Total": "0.00",
                "Gift_VAT": "0.00",
                "Gift_ExVAT": "0.00",
                "Promotion_Total": "0.00",
                "Promotion_VAT": "0.00",
                "Promotion_ExVAT": "0.00",
                "FBA_Fee_Total": "-3.18",
                "FBA_Fee_VAT": "-0.53",
                "FBA_Fee_ExVAT": "-2.65",
                "Commission_Total": "-0.60",
                "Commission_VAT": "-0.10",
                "Commission_ExVAT": "-0.50",
            }
        ]
    ).to_csv(out / "financial_events_level2.csv", index=False)
    pd.DataFrame(columns=["Date", "Order ID", "SKU"]).to_csv(out / "financial_events_level3_official.csv", index=False)
    pd.DataFrame(
        [
            {
                "amazon_order_id": "ORDER-1",
                "marketplace_id": "A1F83G8C2ARO7P",
                "ship_country_code": "GB",
            }
        ]
    ).to_csv(out / "orders_all.csv", index=False)
    pd.DataFrame(
        [
            {
                "marketplace_id": "A1F83G8C2ARO7P",
                "country_code": "GB",
                "default_currency": "GBP",
            }
        ]
    ).to_csv(out / "marketplace_participations.csv", index=False)
    pd.DataFrame(columns=["order_id", "seller_sku", "cogs_exvat", "cogs_vat", "cogs_total"]).to_csv(
        out / "token_cogs_ledger.csv", index=False
    )

    monkeypatch.setattr(b004, "SKIP_SHEETS", True)
    monkeypatch.setattr(b004, "PUBLISH_EXISTING_ONLY", False)
    monkeypatch.setattr(b004, "SKU_FILTER", "")
    monkeypatch.setattr(b004, "INCREMENTAL", False)
    monkeypatch.setattr(b004, "MASTER_MIN_DATE", "")
    monkeypatch.setattr(b004, "L1_STABLE_SECONDS", 0)

    b004.main()

    order_master = pd.read_csv(out / "order_master.csv", dtype=str).fillna("")
    assert len(order_master.index) == 1
    row = order_master.iloc[0]
    assert row["Order ID"] == "ORDER-1"
    assert row["SKU"] == "SKU-1"
    assert row["lvl"] == "2"

    missing_tokens = pd.read_csv(out / "orders_missing_tokens.csv", dtype=str).fillna("")
    assert len(missing_tokens.index) == 1
    assert missing_tokens.iloc[0]["Order ID"] == "ORDER-1"


def test_b004_applies_placeholder_cogs_for_missing_token_rows(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sqlite_path = tmp_path / "pilot.sqlite3"
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "sql_primary_csv_export")
    monkeypatch.setenv("SELLERONE_SQLITE_PATH", str(sqlite_path))
    out = tmp_path / "out"
    out.mkdir()

    pd.DataFrame(
        [
            {
                "Date": "2026-04-20T09:42:05Z",
                "Order ID": "ORDER-NEW",
                "marketplace_id": "A1F83G8C2ARO7P",
                "SKU": "SKU-1",
                "Quantity Ordered": "2",
                "Price_Total": "20.00",
                "Price_VAT": "3.33",
                "Price_ExVAT": "16.67",
                "Shipping_Total": "0.00",
                "Shipping_VAT": "0.00",
                "Shipping_ExVAT": "0.00",
                "Gift_Total": "0.00",
                "Gift_VAT": "0.00",
                "Gift_ExVAT": "0.00",
                "Promotion_Total": "0.00",
                "Promotion_VAT": "0.00",
                "Promotion_ExVAT": "0.00",
                "COGS_Total": "",
                "COGS_VAT": "",
                "COGS_ExVAT": "",
                "FBA_Fee_Total": "-3.18",
                "FBA_Fee_VAT": "-0.53",
                "FBA_Fee_ExVAT": "-2.65",
                "Commission_Total": "-0.60",
                "Commission_VAT": "-0.10",
                "Commission_ExVAT": "-0.50",
            }
        ]
    ).to_csv(out / "financial_events_level1.csv", index=False)
    pd.DataFrame(
        [
            {
                "Date": "2026-04-20T09:42:05Z",
                "Order ID": "ORDER-NEW",
                "marketplace_id": "A1F83G8C2ARO7P",
                "SKU": "SKU-1",
                "Quantity Ordered": "2",
                "Price_Total": "20.00",
                "Price_VAT": "3.33",
                "Price_ExVAT": "16.67",
                "Shipping_Total": "0.00",
                "Shipping_VAT": "0.00",
                "Shipping_ExVAT": "0.00",
                "Gift_Total": "0.00",
                "Gift_VAT": "0.00",
                "Gift_ExVAT": "0.00",
                "Promotion_Total": "0.00",
                "Promotion_VAT": "0.00",
                "Promotion_ExVAT": "0.00",
                "FBA_Fee_Total": "-3.18",
                "FBA_Fee_VAT": "-0.53",
                "FBA_Fee_ExVAT": "-2.65",
                "Commission_Total": "-0.60",
                "Commission_VAT": "-0.10",
                "Commission_ExVAT": "-0.50",
            }
        ]
    ).to_csv(out / "financial_events_level2.csv", index=False)
    pd.DataFrame(columns=["Date", "Order ID", "SKU"]).to_csv(out / "financial_events_level3_official.csv", index=False)
    pd.DataFrame(
        [
            {"amazon_order_id": "ORDER-NEW", "marketplace_id": "A1F83G8C2ARO7P", "ship_country_code": "GB"},
            {"amazon_order_id": "ORDER-OLD", "marketplace_id": "A1F83G8C2ARO7P", "ship_country_code": "GB"},
        ]
    ).to_csv(out / "orders_all.csv", index=False)
    pd.DataFrame(
        [{"marketplace_id": "A1F83G8C2ARO7P", "country_code": "GB", "default_currency": "GBP"}]
    ).to_csv(out / "marketplace_participations.csv", index=False)
    pd.DataFrame(
        [
            {
                "order_id": "ORDER-OLD",
                "order_date": "2026-04-10T09:00:00Z",
                "seller_sku": "SKU-1",
                "token_id": "SKU-1-0001",
                "token_cost": "2.5",
                "currency": "GBP",
                "allocation_date": "2026-04-10T09:00:00Z",
                "quantity": "1",
                "source": "token_allocations_live",
                "built_at": "2026-04-10T10:00:00Z",
                "vat_rate_pct": "20",
                "cogs_exvat": "2.5",
                "cogs_vat": "0.5",
                "cogs_total": "3.0",
            }
        ]
    ).to_csv(out / "token_cogs_ledger.csv", index=False)

    monkeypatch.setattr(b004, "SKIP_SHEETS", True)
    monkeypatch.setattr(b004, "PUBLISH_EXISTING_ONLY", False)
    monkeypatch.setattr(b004, "SKU_FILTER", "")
    monkeypatch.setattr(b004, "INCREMENTAL", False)
    monkeypatch.setattr(b004, "MASTER_MIN_DATE", "")
    monkeypatch.setattr(b004, "L1_STABLE_SECONDS", 0)

    b004.main()

    order_master = pd.read_csv(out / "order_master.csv", dtype=str).fillna("")
    row = order_master.loc[order_master["Order ID"] == "ORDER-NEW"].iloc[0]
    assert row["COGS_Placeholder_Applied"] == "1"
    assert row["COGS_Basis_Type"] == "placeholder_last_cost"
    assert row["COGS_Basis_Source"] == "token_cogs_ledger_last_actual"
    assert row["Missing_Token_Flag"] == "1"
    assert row["Missing_Token_Reason"] == "missing_token_placeholder_applied"
    assert float(row["COGS_ExVAT"]) == pytest.approx(-5.0, abs=1e-6)

    missing_tokens = pd.read_csv(out / "orders_missing_tokens.csv", dtype=str).fillna("")
    miss_row = missing_tokens.loc[missing_tokens["Order ID"] == "ORDER-NEW"].iloc[0]
    assert miss_row["placeholder_applied_flag"] == "1"
    assert float(miss_row["placeholder_cost_per_unit"]) == pytest.approx(2.5, abs=1e-6)
    assert float(miss_row["placeholder_total_cogs"]) == pytest.approx(5.0, abs=1e-6)

    connection = sqlite3.connect(sqlite_path)
    try:
        rows = connection.execute(
            "SELECT order_id, sku, cogs_placeholder_applied FROM b_order_master"
        ).fetchall()
    finally:
        connection.close()

    assert rows == [("ORDER-NEW", "SKU-1", "1")]


def test_b004_sql_primary_writes_diagnostic_tables_and_csv_exports(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sqlite_path = tmp_path / "pilot.sqlite3"
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "sql_primary_csv_export")
    monkeypatch.setenv("SELLERONE_SQLITE_PATH", str(sqlite_path))

    master = pd.DataFrame(
        [
            {
                "Order ID": "ORDER-1",
                "SKU": "SKU-1",
                "Date": "2026-04-28T10:00:00Z",
                "lvl": "1",
                "Quantity Ordered": "2",
                "currency_code": "GBP",
                "COGS_ExVAT": "",
                "COGS_Placeholder_Applied": "",
                "COGS_Basis_Source": "",
                "COGS_Basis_Date": "",
                "Missing_Token_Reason": "",
                "FBA_Fee_Total": "",
                "FBA_Fee_VAT": "",
                "FBA_Fee_ExVAT": "",
                "Commission_Total": "",
                "Commission_VAT": "",
                "Commission_ExVAT": "",
            }
        ]
    )

    b004._write_missing_token_orders(master)
    l1_missing = b004._write_l1_missing_fee_keys(master)
    b004._write_output_frame(
        pd.DataFrame([{"Order ID": "ORPHAN-1", "SKU": "SKU-X"}]),
        b004.L3_ORPHANS_PATH,
        b004.SQL_TABLE_L3_ORPHANS,
    )

    assert l1_missing == 1
    assert len(pd.read_csv(tmp_path / "out" / "orders_missing_tokens.csv", dtype=str).fillna("")) == 1
    assert len(pd.read_csv(tmp_path / "out" / "l1_missing_fee_keys.csv", dtype=str).fillna("")) == 1
    assert len(pd.read_csv(tmp_path / "out" / "l3_orphans.csv", dtype=str).fillna("")) == 1

    connection = sqlite3.connect(sqlite_path)
    try:
        counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ["b_orders_missing_tokens", "b_l1_missing_fee_keys", "b_l3_orphans"]
        }
        l1_rows = connection.execute(
            "SELECT order_id, sku FROM b_l1_missing_fee_keys"
        ).fetchall()
    finally:
        connection.close()

    assert counts == {
        "b_orders_missing_tokens": 1,
        "b_l1_missing_fee_keys": 1,
        "b_l3_orphans": 1,
    }
    assert l1_rows == [("ORDER-1", "SKU-1")]
