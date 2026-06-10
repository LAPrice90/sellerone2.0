from __future__ import annotations

import csv
from pathlib import Path

from sellerone_manager.b_order_recovery import (
    EXPECTED_CURSOR_REL_PATH,
    EXPECTED_QUARANTINE_REL_PATH,
    SUMMARY_COLUMNS,
    build_b_order_recovery_plan,
    write_b_order_recovery_outputs,
)
from sellerone_manager.b_order_recovery_scanner import run_b_order_recovery_scan
from sellerone_manager.hourly_mot import build_b_hourly_mot, write_hourly_mot_outputs
from sellerone_manager.sellerboard_bridge import ORDER_RECONCILIATION_COLUMNS, ORDER_RECONCILIATION_NAME


OBSERVED = "2026-05-27T12:00:00Z"


class _FakeRecoveryApi:
    def fetch_order(self, order_id: str) -> dict[str, object]:
        return {
            "AmazonOrderId": order_id,
            "PurchaseDate": "2026-05-23T11:59:20Z",
            "OrderStatus": "Shipped",
            "MarketplaceId": "A2VIGQ35RCS4UG",
            "OrderTotal": {"Amount": "41.19", "CurrencyCode": "AED"},
        }

    def list_order_items(self, order_id: str) -> list[dict[str, object]]:
        return [
            {
                "AmazonOrderId": order_id,
                "ASIN": "B072K2PG11",
                "SellerSKU": "GH-XAAE-HRU7",
                "QuantityOrdered": 1,
            }
        ]

    def list_orders_page(
        self,
        *,
        marketplace_id: str,
        created_after: str,
        created_before: str,
        next_token: str | None = None,
    ) -> tuple[list[dict[str, object]], str | None]:
        return ([], None)


class _FakePartialCursorApi(_FakeRecoveryApi):
    def list_orders_page(
        self,
        *,
        marketplace_id: str,
        created_after: str,
        created_before: str,
        next_token: str | None = None,
    ) -> tuple[list[dict[str, object]], str | None]:
        return ([{"AmazonOrderId": "page-order"}], "next-page")


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _write_marketplaces(root: Path) -> None:
    _write_csv(
        root / "out" / "marketplace_participations.csv",
        ["marketplace_id", "name", "country_code", "domain_name", "is_participating"],
        [
            {
                "marketplace_id": "A1F83G8C2ARO7P",
                "name": "Amazon.co.uk",
                "country_code": "GB",
                "domain_name": "www.amazon.co.uk",
                "is_participating": "1",
            },
            {
                "marketplace_id": "A2VIGQ35RCS4UG",
                "name": "Amazon.ae",
                "country_code": "AE",
                "domain_name": "www.amazon.ae",
                "is_participating": "1",
            },
        ],
    )


def _write_orders(root: Path, *, include_missing_order_locally: bool = False) -> None:
    rows = [
        {
            "amazon_order_id": "205-1111111-1111111",
            "purchase_date": "2026-05-27T10:00:00Z",
            "order_status": "Shipped",
            "marketplace_id": "A1F83G8C2ARO7P",
            "sales_channel": "Amazon.co.uk",
        }
    ]
    if include_missing_order_locally:
        rows.append(
            {
                "amazon_order_id": "171-1388771-2409132",
                "purchase_date": "2026-05-23T11:59:20Z",
                "order_status": "Shipped",
                "marketplace_id": "A2VIGQ35RCS4UG",
                "sales_channel": "Amazon.ae",
            }
        )
    _write_csv(
        root / "out" / "orders_all.csv",
        ["amazon_order_id", "purchase_date", "order_status", "marketplace_id", "sales_channel"],
        rows,
    )
    (root / "out" / "orders_last_updated.txt").parent.mkdir(parents=True, exist_ok=True)
    (root / "out" / "orders_last_updated.txt").write_text("2026-05-27T10:00:00Z", encoding="utf-8")


def _write_sellerboard_missing(root: Path) -> None:
    _write_csv(
        root / "out" / "systems" / "M" / "sellerboard_bridge" / ORDER_RECONCILIATION_NAME,
        ORDER_RECONCILIATION_COLUMNS,
        [
            {
                "amazon_order_id": "171-1388771-2409132",
                "sellerboard_status": "Shipped",
                "sellerboard_purchase_utc": "2026-05-23T11:59:20Z",
                "sellerboard_sales_channel": "Amazon.ae",
                "sellerboard_currency": "AED",
                "sellerboard_asin": "B072K2PG11",
                "mapped_sku": "",
                "match_status": "sellerboard_shipped_missing_in_sellerone",
                "proof_label": "Sellerboard bridge estimate",
            }
        ],
    )


def _write_cursors(root: Path, *, include_ae: bool = True) -> None:
    rows = [
        {
            "marketplace_id": "A1F83G8C2ARO7P",
            "last_success_utc": "2026-05-27T10:00:00Z",
            "cursor_utc": "2026-05-27T10:00:00Z",
            "status": "ok",
        }
    ]
    if include_ae:
        rows.append(
            {
                "marketplace_id": "A2VIGQ35RCS4UG",
                "last_success_utc": "2026-05-27T10:00:00Z",
                "cursor_utc": "2026-05-27T10:00:00Z",
                "status": "ok",
            }
        )
    _write_csv(
        root / EXPECTED_CURSOR_REL_PATH,
        ["marketplace_id", "last_success_utc", "cursor_utc", "status"],
        rows,
    )


def _write_quarantine(root: Path, *, proof_label: str = "API proved", ready_for_live_merge: str = "0") -> None:
    _write_csv(
        root / EXPECTED_QUARANTINE_REL_PATH,
        [
            "amazon_order_id",
            "marketplace_id",
            "purchase_utc",
            "order_status",
            "sku",
            "asin",
            "quantity",
            "currency",
            "order_total",
            "source",
            "proof_label",
            "duplicate_state",
            "ready_for_live_merge",
        ],
        [
            {
                "amazon_order_id": "171-1388771-2409132",
                "marketplace_id": "A2VIGQ35RCS4UG",
                "purchase_utc": "2026-05-23T11:59:20Z",
                "order_status": "Shipped",
                "sku": "GH-XAAE-HRU7",
                "asin": "B072K2PG11",
                "quantity": "1",
                "currency": "AED",
                "order_total": "41.19",
                "source": "api_backdate",
                "proof_label": proof_label,
                "duplicate_state": "unique_in_quarantine",
                "ready_for_live_merge": ready_for_live_merge,
            }
        ],
    )


def _metrics(result) -> dict[str, str]:
    return {row["metric"]: row["value"] for row in result.summary_rows}


def test_b_order_recovery_flags_unrecovered_missing_order_and_missing_cursor(tmp_path: Path) -> None:
    _write_marketplaces(tmp_path)
    _write_orders(tmp_path)
    _write_sellerboard_missing(tmp_path)
    _write_cursors(tmp_path, include_ae=False)

    result = build_b_order_recovery_plan(root=tmp_path, observed_utc=OBSERVED)
    metrics = _metrics(result)
    rows = {row["marketplace_id"]: row for row in result.plan_rows}

    assert result.status == "fail"
    assert metrics["backdate_start_utc"] == "2025-11-01T00:00:00Z"
    assert metrics["unrecovered_missing_sellerboard_orders"] == "1"
    assert metrics["per_marketplace_cursor_missing_count"] == "1"
    assert rows["A2VIGQ35RCS4UG"]["recovery_status"] == "fail"
    assert rows["A2VIGQ35RCS4UG"]["proof_label"] == "not yet proven"


def test_b_order_recovery_clears_when_missing_order_is_api_proved_in_quarantine(tmp_path: Path) -> None:
    _write_marketplaces(tmp_path)
    _write_orders(tmp_path)
    _write_sellerboard_missing(tmp_path)
    _write_cursors(tmp_path)
    _write_quarantine(tmp_path)

    result = build_b_order_recovery_plan(root=tmp_path, observed_utc=OBSERVED)
    paths = write_b_order_recovery_outputs(result, tmp_path / "out" / "systems" / "M")
    metrics = _metrics(result)

    assert result.status == "ok"
    assert metrics["unrecovered_missing_sellerboard_orders"] == "0"
    assert metrics["quarantine_api_proved_missing_orders"] == "1"
    assert paths["summary_csv"].exists()


def test_b_order_recovery_scanner_writes_quarantine_and_cursor_proof(tmp_path: Path) -> None:
    _write_marketplaces(tmp_path)
    _write_orders(tmp_path)
    _write_sellerboard_missing(tmp_path)

    scan = run_b_order_recovery_scan(root=tmp_path, observed_utc=OBSERVED, api_client=_FakeRecoveryApi())
    result = build_b_order_recovery_plan(root=tmp_path, observed_utc=OBSERVED)
    metrics = _metrics(result)

    assert scan.status == "ok"
    assert scan.quarantine_rows_written == 1
    assert scan.cursor_rows_written == 2
    assert metrics["unrecovered_missing_sellerboard_orders"] == "0"
    assert metrics["per_marketplace_cursor_missing_count"] == "0"
    assert result.status == "ok"


def test_b_order_recovery_scanner_partial_cursor_stays_not_proven(tmp_path: Path) -> None:
    _write_marketplaces(tmp_path)
    _write_orders(tmp_path)
    _write_sellerboard_missing(tmp_path)

    scan = run_b_order_recovery_scan(
        root=tmp_path,
        observed_utc=OBSERVED,
        api_client=_FakePartialCursorApi(),
        max_pages_per_marketplace=1,
    )
    result = build_b_order_recovery_plan(root=tmp_path, observed_utc=OBSERVED)
    metrics = _metrics(result)

    assert scan.status == "partial"
    assert metrics["per_marketplace_cursor_missing_count"] == "2"
    assert result.status == "fail"


def test_b_order_recovery_blocks_live_merge_ready_quarantine_row(tmp_path: Path) -> None:
    _write_marketplaces(tmp_path)
    _write_orders(tmp_path)
    _write_sellerboard_missing(tmp_path)
    _write_cursors(tmp_path)
    _write_quarantine(tmp_path, ready_for_live_merge="yes")

    result = build_b_order_recovery_plan(root=tmp_path, observed_utc=OBSERVED)
    metrics = _metrics(result)

    assert result.status == "decision_needed"
    assert metrics["merge_ready_without_approval_orders"] == "1"


def test_b_order_recovery_duplicate_guard_flags_existing_local_order(tmp_path: Path) -> None:
    _write_marketplaces(tmp_path)
    _write_orders(tmp_path, include_missing_order_locally=True)
    _write_sellerboard_missing(tmp_path)
    _write_cursors(tmp_path)
    _write_quarantine(tmp_path)

    result = build_b_order_recovery_plan(root=tmp_path, observed_utc=OBSERVED)
    metrics = _metrics(result)

    assert result.status == "fail"
    assert metrics["duplicate_risk_orders"] == "1"


def test_b_hourly_mot_creates_recovery_and_future_cursor_work_items(tmp_path: Path) -> None:
    _write_marketplaces(tmp_path)
    _write_orders(tmp_path)
    _write_sellerboard_missing(tmp_path)
    _write_cursors(tmp_path, include_ae=False)

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    paths = write_hourly_mot_outputs(result, tmp_path / "out" / "systems" / "M")
    rows = {row["check"]: row for row in result["rows"]}
    worklist_rows = list(csv.DictReader(paths["mot_worklist_csv"].open(newline="", encoding="utf-8")))

    assert rows["b_backdate_recovery_quarantine"]["status"] == "fail"
    assert rows["b_future_marketplace_order_cursors"]["status"] == "fail"
    assert any(row["check"] == "b_backdate_recovery_quarantine" for row in worklist_rows)
    assert any(row["check"] == "b_future_marketplace_order_cursors" for row in worklist_rows)
    assert "no B run" in next(row for row in worklist_rows if row["check"] == "b_backdate_recovery_quarantine")["forbidden_actions"]


def test_b_order_recovery_summary_schema_constant_is_stable() -> None:
    assert SUMMARY_COLUMNS == [
        "observed_utc",
        "metric",
        "status",
        "value",
        "proof_label",
        "notes",
        "source_path",
    ]
