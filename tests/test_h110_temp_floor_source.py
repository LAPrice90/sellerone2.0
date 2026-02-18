import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from scripts import H110_run_phase1_h_pilot as h110


class H110TempFloorSourceTests(unittest.TestCase):
    def test_temp_floor_uses_token_and_product_db_not_orders(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            out = root / "out"
            out.mkdir(parents=True, exist_ok=True)

            product_db_path = out / "product_db_preview.csv"
            token_ledger_path = out / "token_ledger_live.csv"
            token_cogs_path = out / "token_cogs_ledger.csv"
            snapshot_path = out / "sku_temp_floor_snapshot.csv"

            pd.DataFrame(
                [
                    {
                        "seller_sku": "TEST-SKU-1",
                        "last_vat_rate_pct": "20",
                        "live_listing_price": "11.97",
                        "last_sold_price": "11.97",
                        "last_fba_fee_ex_vat_100": "3.05",
                        "last_fba_fee_ex_vat": "3.05",
                        "fba_fee_100": "3.05",
                        "referral_fee_100": "15",
                        "last_commission_pct": "8",
                        "last_commission_pct_100": "8",
                    }
                ]
            ).to_csv(product_db_path, index=False)

            pd.DataFrame(
                [
                    {
                        "token_id": "T1",
                        "seller_sku": "TEST-SKU-1",
                        "cost_per_unit": "5.35",
                        "status": "available",
                        "sort_rank": "1",
                        "received_date": "2026-02-17T00:00:00Z",
                    }
                ]
            ).to_csv(token_ledger_path, index=False)

            pd.DataFrame(columns=["seller_sku", "cogs_exvat", "cogs_total"]).to_csv(token_cogs_path, index=False)

            with (
                patch.object(h110, "PRODUCT_DB_PATH", product_db_path),
                patch.object(h110, "TOKEN_LEDGER_PATH", token_ledger_path),
                patch.object(h110, "TOKEN_COGS_LEDGER_PATH", token_cogs_path),
                patch.object(h110, "TEMP_FLOOR_SNAPSHOT_PATH", snapshot_path),
                patch.object(
                    h110,
                    "H_FLOOR_VAT_POLICY",
                    {
                        "vat_registered": True,
                        "recover_input_vat_on_cogs": True,
                        "recover_input_vat_on_fees": True,
                    },
                ),
            ):
                out_map, blocked = h110._load_temp_floor_by_sku()

            self.assertIn("TEST-SKU-1", out_map)
            self.assertNotIn("TEST-SKU-1", blocked)
            self.assertAlmostEqual(float(out_map["TEST-SKU-1"]), 11.97, places=2)

            snap = pd.read_csv(snapshot_path, dtype=str).fillna("")
            row = snap.loc[snap["sku"].eq("TEST-SKU-1")].iloc[-1]
            self.assertEqual(row["order_id"], "")
            self.assertEqual(row["cogs_total_gbp"], "5.35")


if __name__ == "__main__":
    unittest.main()
