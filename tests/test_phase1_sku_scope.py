import tempfile
import unittest
from pathlib import Path

import pandas as pd

from scripts.phase1 import phase1_sku_scope


class Phase1SkuScopeTests(unittest.TestCase):
    def test_switch_join_and_effective_flags(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            product_db = root / "product_db_preview.csv"
            merchant = root / "merchant_listings_latest.csv"
            listing = root / "listing_offer_snapshot_2026-02-17.csv"
            switches = root / "h_sku_switches.csv"

            pd.DataFrame(
                [
                    {"seller_sku": "SKU_ACTIVE_WRITE", "asin": "A1", "sale_status": "active"},
                    {"seller_sku": "SKU_INACTIVE", "asin": "A2", "sale_status": "active"},
                    {"seller_sku": "SKU_MANUAL_DISABLE", "asin": "A3", "sale_status": "active"},
                    {"seller_sku": "SKU_OOS", "asin": "A4", "sale_status": "active"},
                ]
            ).to_csv(product_db, index=False)
            pd.DataFrame(
                [
                    {"seller-sku": "SKU_ACTIVE_WRITE", "asin1": "A1", "status": "Active"},
                    {"seller-sku": "SKU_INACTIVE", "asin1": "A2", "status": "Inactive"},
                    {"seller-sku": "SKU_MANUAL_DISABLE", "asin1": "A3", "status": "Active"},
                    {"seller-sku": "SKU_OOS", "asin1": "A4", "status": "Active"},
                ]
            ).to_csv(merchant, index=False)
            pd.DataFrame(
                [
                    {"sku": "SKU_ACTIVE_WRITE", "asin": "A1", "our_price": "12.00", "we_present_flag": "1"},
                    {"sku": "SKU_INACTIVE", "asin": "A2", "our_price": "11.00", "we_present_flag": "1"},
                    {"sku": "SKU_MANUAL_DISABLE", "asin": "A3", "our_price": "10.00", "we_present_flag": "1"},
                    {"sku": "SKU_OOS", "asin": "A4", "our_price": "0.00", "we_present_flag": "0"},
                ]
            ).to_csv(listing, index=False)
            pd.DataFrame(
                [
                    {"sku": "SKU_ACTIVE_WRITE", "observe_enabled": "1", "write_enabled": "1", "manual_disable": "0"},
                    {"sku": "SKU_INACTIVE", "observe_enabled": "1", "write_enabled": "1", "manual_disable": "0"},
                    {"sku": "SKU_MANUAL_DISABLE", "observe_enabled": "1", "write_enabled": "1", "manual_disable": "1"},
                    {"sku": "SKU_OOS", "observe_enabled": "1", "write_enabled": "1", "manual_disable": "0"},
                ]
            ).to_csv(switches, index=False)

            df = phase1_sku_scope.build_scope_df(
                asof_utc="2026-02-17T12:00:00Z",
                product_db_path=product_db,
                merchant_path=merchant,
                listing_snapshot_path=listing,
                sku_switches_path=switches,
            )
            by_sku = {str(r["sku"]).strip().upper(): r for _, r in df.iterrows()}

            self.assertEqual(str(by_sku["SKU_ACTIVE_WRITE"]["repricing_enabled"]), "1")
            self.assertEqual(str(by_sku["SKU_ACTIVE_WRITE"]["write_effective"]), "1")
            self.assertEqual(str(by_sku["SKU_ACTIVE_WRITE"]["writer_mode"]), "CODEX_H")

            self.assertEqual(str(by_sku["SKU_INACTIVE"]["repricing_enabled"]), "0")
            self.assertEqual(str(by_sku["SKU_INACTIVE"]["write_effective"]), "0")
            self.assertIn("inactive", str(by_sku["SKU_INACTIVE"]["reason_code"]))

            self.assertEqual(str(by_sku["SKU_MANUAL_DISABLE"]["repricing_enabled"]), "0")
            self.assertEqual(str(by_sku["SKU_MANUAL_DISABLE"]["write_effective"]), "0")
            self.assertIn("manual_disable", str(by_sku["SKU_MANUAL_DISABLE"]["reason_code"]))

            self.assertEqual(str(by_sku["SKU_OOS"]["repricing_enabled"]), "0")
            self.assertEqual(str(by_sku["SKU_OOS"]["write_effective"]), "0")
            self.assertIn("out_of_stock", str(by_sku["SKU_OOS"]["reason_code"]))

    def test_switch_defaults_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            product_db = root / "product_db_preview.csv"
            merchant = root / "merchant_listings_latest.csv"
            listing = root / "listing_offer_snapshot_2026-02-17.csv"

            pd.DataFrame([{"seller_sku": "SKU_DEFAULT", "asin": "A1", "sale_status": "active"}]).to_csv(product_db, index=False)
            pd.DataFrame([{"seller-sku": "SKU_DEFAULT", "asin1": "A1", "status": "Active"}]).to_csv(merchant, index=False)
            pd.DataFrame([{"sku": "SKU_DEFAULT", "asin": "A1", "our_price": "12.00", "we_present_flag": "1"}]).to_csv(listing, index=False)

            df = phase1_sku_scope.build_scope_df(
                asof_utc="2026-02-17T12:00:00Z",
                product_db_path=product_db,
                merchant_path=merchant,
                listing_snapshot_path=listing,
                sku_switches_path=root / "missing_switches.csv",
            )
            row = df.iloc[0]
            self.assertEqual(str(row["observe_enabled"]), "1")
            self.assertEqual(str(row["write_enabled"]), "0")
            self.assertEqual(str(row["manually_disabled"]), "0")
            self.assertEqual(str(row["observe_effective"]), "1")
            self.assertEqual(str(row["write_effective"]), "0")

    def test_legacy_writer_modes_compat(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            product_db = root / "product_db_preview.csv"
            merchant = root / "merchant_listings_latest.csv"
            listing = root / "listing_offer_snapshot_2026-02-17.csv"
            writer_modes = root / "phase1_writer_modes.csv"

            pd.DataFrame([{"seller_sku": "SKU_LEGACY", "asin": "A1", "sale_status": "active"}]).to_csv(product_db, index=False)
            pd.DataFrame([{"seller-sku": "SKU_LEGACY", "asin1": "A1", "status": "Active"}]).to_csv(merchant, index=False)
            pd.DataFrame([{"sku": "SKU_LEGACY", "asin": "A1", "our_price": "12.00", "we_present_flag": "1"}]).to_csv(listing, index=False)
            pd.DataFrame([{"sku": "SKU_LEGACY", "pricing_writer_mode": "CODEX_H"}]).to_csv(writer_modes, index=False)

            df = phase1_sku_scope.build_scope_df(
                asof_utc="2026-02-17T12:00:00Z",
                product_db_path=product_db,
                merchant_path=merchant,
                listing_snapshot_path=listing,
                writer_modes_path=writer_modes,
            )
            row = df.iloc[0]
            self.assertEqual(str(row["write_enabled"]), "1")
            self.assertEqual(str(row["write_effective"]), "1")
            self.assertEqual(str(row["writer_mode"]), "CODEX_H")


if __name__ == "__main__":
    unittest.main()
