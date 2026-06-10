from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.flows.B import B064_build_return_cogs_residual_review as b064


def _write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)


BRIDGE_COLUMNS = [
    "order_id",
    "sku",
    "amazon_return_disposition",
    "token_return_state",
    "return_cogs_recovered_exvat",
    "blocked_return_cogs_exvat",
    "blocked_return_cogs_source",
]


def test_b064_marks_blocked_non_sellable_cogs_as_safe_visible_evidence(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_refund_return_token_bridge.csv",
        [
            {
                "order_id": "ORDER-1",
                "sku": "SKU-A",
                "amazon_return_disposition": "CUSTOMER_DAMAGED",
                "token_return_state": "returned_complete_no_available_token_seen",
                "return_cogs_recovered_exvat": "0",
                "blocked_return_cogs_exvat": "2.50",
                "blocked_return_cogs_source": "token_return_ledger",
            }
        ],
        BRIDGE_COLUMNS,
    )

    result = b064.build_return_cogs_residual_review(root=tmp_path, observed_utc="2026-06-04T08:00:00Z")
    review = result["review"]
    summary = {row["metric"]: row["value"] for _, row in result["summary"].iterrows()}

    assert summary["status"] == "ok"
    assert summary["review_rows"] == "1"
    assert summary["blocked_rows"] == "1"
    assert summary["unsafe_rows"] == "0"
    assert review.loc[0, "residual_review_state"] == "blocked_from_roi_and_stock_recovery"
    assert review.loc[0, "roi_or_restock_use_allowed"] == "0"


def test_b064_fails_if_non_sellable_cogs_is_still_allowed(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_refund_return_token_bridge.csv",
        [
            {
                "order_id": "ORDER-1",
                "sku": "SKU-A",
                "amazon_return_disposition": "DEFECTIVE",
                "token_return_state": "returned_complete_no_available_token_seen",
                "return_cogs_recovered_exvat": "2.50",
                "blocked_return_cogs_exvat": "0",
                "blocked_return_cogs_source": "",
            }
        ],
        BRIDGE_COLUMNS,
    )

    summary = {
        row["metric"]: row["value"]
        for _, row in b064.build_return_cogs_residual_review(root=tmp_path)["summary"].iterrows()
    }

    assert summary["status"] == "fail"
    assert summary["unsafe_rows"] == "1"
