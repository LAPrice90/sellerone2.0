from __future__ import annotations

from scripts.flows.H import H110_run_phase1_h_pilot as h110


def test_scan_due_order_uses_oldest_scan_before_sku_name() -> None:
    rows = [
        {"sku": "0A-FIRST", "write_effective": "1"},
        {"sku": "RB-LATER", "write_effective": "1"},
        {"sku": "AA-READONLY", "write_effective": "0"},
    ]
    last_scan_utc = {
        "0A-FIRST": "2026-04-30T13:57:08Z",
        "RB-LATER": "2026-04-30T13:44:35Z",
        "AA-READONLY": "2026-04-30T10:00:00Z",
    }

    ordered = h110._sort_due_rows_by_oldest_scan(rows, last_scan_utc)

    assert [row["sku"] for row in ordered] == ["RB-LATER", "0A-FIRST", "AA-READONLY"]


def test_scan_due_order_prioritizes_never_scanned_write_skus() -> None:
    rows = [
        {"sku": "0A-FIRST", "write_effective": "1"},
        {"sku": "ZZ-NEVER", "write_effective": "1"},
    ]
    last_scan_utc = {"0A-FIRST": "2026-04-30T13:57:08Z"}

    ordered = h110._sort_due_rows_by_oldest_scan(rows, last_scan_utc)

    assert [row["sku"] for row in ordered] == ["ZZ-NEVER", "0A-FIRST"]
