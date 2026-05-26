from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.O.O006_build_ui_preview_samples import build_ui_preview_samples
from scripts.flows.O._schemas import get_o_output_contract


def _write_source_rows(tmp_path: Path) -> None:
    path = tmp_path / get_o_output_contract("restock_source_view").rel_path
    path.parent.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, str]] = []
    supplier_map = {
        "DHB": 4,
        "Stax": 3,
        "TD Synnex": 3,
    }
    counter = 0
    for supplier_name, total in supplier_map.items():
        for idx in range(total):
            counter += 1
            rows.append(
                {
                    "asof_utc": "2026-04-04T12:00:00Z",
                    "seller_sku": f"SKU-{counter:02d}",
                    "asin": f"ASIN-{counter:02d}",
                    "supplier_code": f"SUP-{supplier_name[:2].upper()}",
                    "supplier_name": supplier_name,
                    "sale_status": "active",
                    "available_now": str(idx),
                    "total_quantity_now": str(idx),
                    "amazon_inbound_working": "0",
                    "amazon_inbound_shipped": "0",
                    "amazon_inbound_receiving": "0",
                    "velocity_7d": "0.4",
                    "velocity_30d": "0.5",
                    "velocity_90d": "0.5",
                    "current_supplier_buy_cost_gbp": str(1.5 + idx),
                    "current_supplier_cost_source": "supplier_catalog_price",
                    "market_price_gbp": str(3.5 + idx),
                    "market_price_basis_used": "BUY_BOX_PRICE",
                    "expected_refund_cost_per_unit_gbp": "0.1",
                    "roi_at_market_price_pct": "20",
                    "source_inventory_asof": "2026-04-04T12:00:00Z",
                    "source_velocity_asof": "2026-04-04",
                    "source_performance_asof": "2026-04-04",
                    "title": f"{supplier_name} Product {idx + 1}",
                    "main_image": f"https://example.com/{supplier_name.lower().replace(' ', '-')}-{idx + 1}.jpg",
                    "days_cover_available_only": "2",
                    "days_cover_total_pipeline": "2",
                }
            )

    pd.DataFrame(rows).to_csv(path, index=False)


def test_o006_builds_ten_preview_rows_across_three_suppliers(tmp_path: Path) -> None:
    _write_source_rows(tmp_path)

    rec_df, queue_df = build_ui_preview_samples(root=tmp_path, preview_utc="2026-04-04T13:00:00Z")

    assert len(rec_df) == 10
    assert len(queue_df) == 10
    assert set(queue_df["supplier_name"]) == {"DHB", "Stax", "TD Synnex"}
    assert queue_df.groupby("supplier_name").size().to_dict() == {"DHB": 4, "Stax": 3, "TD Synnex": 3}
    assert set(queue_df["cost_mode"]) == {"test"}
    assert set(queue_df["recommendation_basis"]) == {"ui_preview_sample"}
    assert int(queue_df["main_image"].astype(str).str.strip().ne("").sum()) == 10
    assert int(queue_df["title"].astype(str).str.strip().ne("").sum()) == 10
    assert set(queue_df["queue_status"]) == {"needs_review"}
    assert set(rec_df["recommendation_status"]) == {"full_restock", "test_restock"}
