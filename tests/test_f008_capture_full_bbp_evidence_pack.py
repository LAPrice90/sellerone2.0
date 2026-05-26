from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.one_off.F008_capture_full_bbp_evidence_pack import capture_full_bbp_evidence_pack


class _FakeAdapter:
    def __init__(self, *, session_id: int, snapshot_path: Path) -> None:
        self.session_id = session_id
        self.snapshot_path = snapshot_path
        self.calls = 0
        self.closed = False

    def process_scrape(
        self,
        *,
        asin: str,
        break_even_price: float,
        min_sell_price: float,
        product_cost: float,
        row_index: int,
        brand_name: str,
        vat_rate: float,
        skip_date_scraping: bool,
        old_chrome_forced: bool,
    ):
        self.calls += 1
        _ = (
            break_even_price,
            min_sell_price,
            product_cost,
            row_index,
            brand_name,
            vat_rate,
            skip_date_scraping,
            old_chrome_forced,
        )
        return {
            "success": True,
            "scraped_data": {
                "asin": asin,
                "bbp_section_snapshot_path": str(self.snapshot_path),
                "bbp_sales_chart_source": "estSalesMonthlyChart:chartjs",
                "bbp_sales_last_completed_month_label": "2026-03",
                "bbp_sales_last_completed_month_units": "10",
                "bbp_sales_current_month_label": "2026-04",
                "bbp_sales_current_month_units": str(10 + self.session_id),
                "bbp_sales_future_month_count_ignored": "2",
                "bbp_sales_replay_demand_basis_source": "bbp_last_completed_month",
                "bbp_sales_replay_demand_basis_units": "10",
                "bbp_sales_chart_month_labels": "01/26|02/26|03/26|04/26|05/26*",
                "bbp_sales_chart_month_units": "8|9|10|11|12",
            },
        }

    def close(self) -> None:
        self.closed = True


def test_f008_writes_manifest_and_raw_for_three_passes_with_session_reuse(tmp_path: Path) -> None:
    asin_pack = tmp_path / "asin_pack.csv"
    pd.DataFrame(
        [
            {
                "sample_rank": "1",
                "validation_case": "trusted_completed_month",
                "supplier_sku": "SKU-1",
                "asin": "B000TEST01",
                "amazon_link": "https://www.amazon.co.uk/dp/B000TEST01",
            }
        ]
    ).to_csv(asin_pack, index=False)

    snapshot_path = tmp_path / "snapshot.json"
    snapshot_path.write_text(json.dumps({"node_count": 123}), encoding="utf-8")

    adapters_created: dict[int, _FakeAdapter] = {}

    def _factory(session_id: int) -> _FakeAdapter:
        adapter = _FakeAdapter(session_id=session_id, snapshot_path=snapshot_path)
        adapters_created[session_id] = adapter
        return adapter

    def _screens(_adapter: object, asin: str, pass_index: int, out_dir: Path) -> dict[str, str]:
        full = out_dir / f"{asin}_p{pass_index}_full.png"
        full.write_bytes(b"fake")
        return {
            "bbp_full_screenshot_path": str(full),
            "bbp_section_screenshot_path": "",
            "bbp_sales_chart_screenshot_path": "",
            "amazon_sold_screenshot_path": "",
            "screenshot_error": "",
        }

    result = capture_full_bbp_evidence_pack(
        asin_pack_path=asin_pack,
        output_dir=tmp_path / "out",
        max_asins=1,
        passes=3,
        observed_utc="2026-04-14T18:00:00Z",
        adapter_factory=_factory,
        screenshot_captor=_screens,
    )

    assert len(result.manifest_df) == 3
    assert result.manifest_path.exists()
    assert result.latest_path.exists()
    assert set(result.manifest_df["session_id"].tolist()) == {"1", "3"}
    assert result.manifest_df.iloc[0]["bbp_snapshot_loaded"] == "1"
    assert (result.manifest_df["capture_status"] == "success").all()

    raw_paths = result.manifest_df["raw_json_path"].tolist()
    assert len(raw_paths) == 3
    for raw_path in raw_paths:
        path = Path(raw_path)
        assert path.exists()
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["run_metadata"]["capture_status"] == "success"
        assert payload["bbp_section_snapshot_json"]["node_count"] == 123

    assert adapters_created[1].calls == 2
    assert adapters_created[3].calls == 1
    assert adapters_created[1].closed is True
    assert adapters_created[3].closed is True
