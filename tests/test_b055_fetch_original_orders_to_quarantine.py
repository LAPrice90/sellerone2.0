from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.flows.B import B055_fetch_original_orders_to_quarantine as b055


def _write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)


SOURCE_COLUMNS = [
    "order_id",
    "sku",
    "original_order_recovery_state",
]

QUARANTINE_COLUMNS = [
    "amazon_order_id",
    "marketplace_id",
    "purchase_utc",
    "order_status",
    "sku",
    "asin",
    "order_item_ids",
    "quantity",
    "currency",
    "order_total",
    "last_update_utc",
    "sales_channel",
    "fulfillment_channel",
    "order_payload_json",
    "items_payload_json",
    "source",
    "proof_label",
    "duplicate_state",
    "ready_for_live_merge",
]


class FakeOrderApi:
    def __init__(self) -> None:
        self.fetch_calls: list[str] = []
        self.item_calls: list[str] = []

    def fetch_order(self, order_id: str) -> dict[str, object]:
        self.fetch_calls.append(order_id)
        return {
            "AmazonOrderId": order_id,
            "MarketplaceId": "A1F83G8C2ARO7P",
            "PurchaseDate": "2025-10-20T10:00:00Z",
            "OrderStatus": "Shipped",
            "OrderTotal": {"Amount": "12.34", "CurrencyCode": "GBP"},
            "LastUpdateDate": "2025-10-21T10:00:00Z",
            "SalesChannel": "Amazon.co.uk",
            "FulfillmentChannel": "AFN",
        }

    def list_order_items(self, order_id: str) -> list[dict[str, object]]:
        self.item_calls.append(order_id)
        return [
            {
                "AmazonOrderId": order_id,
                "SellerSKU": "SKU-A",
                "ASIN": "ASIN-A",
                "OrderItemId": "ITEM-1",
                "QuantityOrdered": 1,
            }
        ]


def test_b055_preview_plans_fetch_without_calling_api_or_writing_quarantine(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_original_order_recovery_proof.csv",
        [{"order_id": "ORDER-1", "sku": "SKU-A", "original_order_recovery_state": "needs_api_original_order_fetch_to_quarantine"}],
        SOURCE_COLUMNS,
    )
    client = FakeOrderApi()

    result = b055.build_original_order_fetch_to_quarantine(root=tmp_path, api_client=client, apply_fetch=False)
    summary = {row["metric"]: row["value"] for _, row in result.summary.iterrows()}

    assert summary["status"] == "ok"
    assert summary["planned_api_fetch_rows"] == "1"
    assert summary["fetched_api_proved_rows"] == "0"
    assert client.fetch_calls == []
    assert result.rows.iloc[0]["action_state"] == "planned_api_fetch_to_quarantine"
    assert result.rows.iloc[0]["live_write_allowed"] == "0"


def test_b055_apply_fetch_writes_api_proof_to_quarantine_result(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_original_order_recovery_proof.csv",
        [{"order_id": "ORDER-1", "sku": "SKU-A", "original_order_recovery_state": "needs_api_original_order_fetch_to_quarantine"}],
        SOURCE_COLUMNS,
    )
    client = FakeOrderApi()

    result = b055.build_original_order_fetch_to_quarantine(root=tmp_path, api_client=client, apply_fetch=True)
    summary = {row["metric"]: row["value"] for _, row in result.summary.iterrows()}
    row = result.rows.iloc[0]

    assert summary["status"] == "ok"
    assert summary["fetched_api_proved_rows"] == "1"
    assert client.fetch_calls == ["ORDER-1"]
    assert client.item_calls == ["ORDER-1"]
    assert row["action_state"] == "fetched_api_proved_to_quarantine"
    assert row["proof_label"] == "API proved"
    assert row["purchase_utc"] == "2025-10-20T10:00:00Z"
    assert row["order_item_ids"] == "ITEM-1"
    assert result.quarantine_rows[0]["ready_for_live_merge"] == "0"


def test_b055_blocks_when_order_already_exists_live(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_original_order_recovery_proof.csv",
        [{"order_id": "ORDER-1", "sku": "SKU-A", "original_order_recovery_state": "needs_api_original_order_fetch_to_quarantine"}],
        SOURCE_COLUMNS,
    )
    _write_csv(
        tmp_path / "out" / "orders_all.csv",
        [{"amazon_order_id": "ORDER-1", "purchase_date": "2025-10-20T10:00:00Z"}],
        ["amazon_order_id", "purchase_date"],
    )
    client = FakeOrderApi()

    result = b055.build_original_order_fetch_to_quarantine(root=tmp_path, api_client=client, apply_fetch=True)
    summary = {row["metric"]: row["value"] for _, row in result.summary.iterrows()}

    assert summary["status"] == "ok"
    assert summary["already_live_order_rows"] == "1"
    assert client.fetch_calls == []
    assert result.rows.iloc[0]["action_state"] == "blocked_already_in_live_orders"


def test_b055_write_quarantine_is_explicit(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_original_order_recovery_proof.csv",
        [{"order_id": "ORDER-1", "sku": "SKU-A", "original_order_recovery_state": "needs_api_original_order_fetch_to_quarantine"}],
        SOURCE_COLUMNS,
    )
    result = b055.build_original_order_fetch_to_quarantine(root=tmp_path, api_client=FakeOrderApi(), apply_fetch=True)

    paths = b055.write_original_order_fetch_outputs(result, root=tmp_path, write_quarantine=True)
    written = pd.read_csv(paths["quarantine"], dtype=str, keep_default_na=False)

    assert len(written) == 1
    assert written.iloc[0]["amazon_order_id"] == "ORDER-1"
    assert written.iloc[0]["proof_label"] == "API proved"


def test_b055_clears_when_no_fetch_targets_remain(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_original_order_recovery_proof.csv",
        [],
        [
            "order_id",
            "sku",
            "original_order_recovery_state",
        ],
    )

    result = b055.build_original_order_fetch_to_quarantine(root=tmp_path, apply_fetch=False)
    summary = {row["metric"]: row["value"] for _, row in result.summary.iterrows()}

    assert summary["status"] == "ok"
    assert summary["source_rows"] == "0"
    assert summary["planned_api_fetch_rows"] == "0"
