import tempfile
import unittest
from pathlib import Path

import pandas as pd

from scripts import phase1_sku_scope


class Phase1SkuScopeTests(unittest.TestCase):
    def test_strict_union_parked_rule_and_reason_codes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            product_db = root / "product_db_preview.csv"
            merchant = root / "merchant_listings_latest.csv"
            listing = root / "listing_offer_snapshot_2026-02-17.csv"
            writer_modes = root / "phase1_writer_modes.csv"

            pd.DataFrame(
                [
                    {"seller_sku": "SKU_DROP", "asin": "A1", "sale_status": "dropped"},
                    {"seller_sku": "SKU_DISC", "asin": "A2", "sale_status": "discontinued"},
                    {"seller_sku": "SKU_OK", "asin": "A3", "sale_status": "active"},
                ]
            ).to_csv(product_db, index=False)
            pd.DataFrame(
                [
                    {"seller-sku": "SKU_DROP", "asin1": "A1", "status": "Active"},
                    {"seller-sku": "SKU_DISC", "asin1": "A2", "status": "Active"},
                    {"seller-sku": "SKU_OK", "asin1": "A3", "status": "Inactive"},
                    {"seller-sku": "SKU_STOCK", "asin1": "A4", "status": "Active"},
                ]
            ).to_csv(merchant, index=False)
            pd.DataFrame(
                [
                    {"sku": "SKU_DROP", "asin": "A1", "our_price": "12.00", "we_present_flag": "1"},
                    {"sku": "SKU_DISC", "asin": "A2", "our_price": "11.00", "we_present_flag": "1"},
                    {"sku": "SKU_OK", "asin": "A3", "our_price": "10.00", "we_present_flag": "1"},
                    {"sku": "SKU_STOCK", "asin": "A4", "our_price": "9.00", "we_present_flag": "1"},
                ]
            ).to_csv(listing, index=False)
            pd.DataFrame(
                [
                    {"sku": "SKU_STOCK", "pricing_writer_mode": "CODEX_H"},
                ]
            ).to_csv(writer_modes, index=False)

            df = phase1_sku_scope.build_scope_df(
                asof_utc="2026-02-17T12:00:00Z",
                product_db_path=product_db,
                merchant_path=merchant,
                listing_snapshot_path=listing,
                writer_modes_path=writer_modes,
            )
            by_sku = {str(r["sku"]).strip().upper(): r for _, r in df.iterrows()}

            self.assertEqual(by_sku["SKU_DROP"]["parked_flag"], "1")
            self.assertIn("PARK_SALE_STATUS_DROPPED", by_sku["SKU_DROP"]["park_reason_codes"])

            self.assertEqual(by_sku["SKU_DISC"]["parked_flag"], "1")
            self.assertIn("PARK_SALE_STATUS_DISCONTINUED", by_sku["SKU_DISC"]["park_reason_codes"])

            self.assertEqual(by_sku["SKU_OK"]["parked_flag"], "1")
            self.assertIn("PARK_MERCHANT_INACTIVE", by_sku["SKU_OK"]["park_reason_codes"])

            self.assertEqual(by_sku["SKU_STOCK"]["parked_flag"], "0")
            self.assertEqual(by_sku["SKU_STOCK"]["cpt_tier"], "ACTIVE_WRITE")

    def test_scope_marks_no_listing_rows_as_parked(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            product_db = root / "product_db_preview.csv"
            merchant = root / "merchant_listings_latest.csv"
            writer_modes = root / "phase1_writer_modes.csv"

            pd.DataFrame([{"seller_sku": "SKU_NO_LISTING", "asin": "A9", "sale_status": "active"}]).to_csv(product_db, index=False)
            pd.DataFrame([{"seller-sku": "SKU_NO_LISTING", "asin1": "A9", "status": "Active"}]).to_csv(merchant, index=False)
            pd.DataFrame([{"sku": "SKU_NO_LISTING", "pricing_writer_mode": "READ_ONLY"}]).to_csv(writer_modes, index=False)

            df = phase1_sku_scope.build_scope_df(
                asof_utc="2026-02-17T12:00:00Z",
                product_db_path=product_db,
                merchant_path=merchant,
                listing_snapshot_path=root / "missing_listing.csv",
                writer_modes_path=writer_modes,
            )
            row = df.iloc[0]
            self.assertEqual(str(row["parked_flag"]), "1")
            self.assertIn("PARK_NO_LISTING_ROW", str(row["park_reason_codes"]))
            self.assertIn("PARK_OUT_OF_STOCK", str(row["park_reason_codes"]))
            self.assertEqual(str(row["cpt_tier"]), "PARKED")

    def test_scope_marks_missing_merchant_row_as_inactive(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            product_db = root / "product_db_preview.csv"
            merchant = root / "merchant_listings_latest.csv"
            listing = root / "listing_offer_snapshot_2026-02-17.csv"
            writer_modes = root / "phase1_writer_modes.csv"

            pd.DataFrame([{"seller_sku": "SKU_NO_MERCHANT", "asin": "A10", "sale_status": "active"}]).to_csv(product_db, index=False)
            pd.DataFrame([{"seller-sku": "SKU_OTHER", "asin1": "AX", "status": "Active"}]).to_csv(merchant, index=False)
            pd.DataFrame([{"sku": "SKU_NO_MERCHANT", "asin": "A10", "our_price": "10.00", "we_present_flag": "1"}]).to_csv(listing, index=False)
            pd.DataFrame([{"sku": "SKU_NO_MERCHANT", "pricing_writer_mode": "CODEX_H"}]).to_csv(writer_modes, index=False)

            df = phase1_sku_scope.build_scope_df(
                asof_utc="2026-02-17T12:00:00Z",
                product_db_path=product_db,
                merchant_path=merchant,
                listing_snapshot_path=listing,
                writer_modes_path=writer_modes,
            )
            row = df.loc[df["sku"].astype(str).str.upper().eq("SKU_NO_MERCHANT")].iloc[0]
            self.assertEqual(str(row["parked_flag"]), "1")
            self.assertIn("PARK_MERCHANT_INACTIVE", str(row["park_reason_codes"]))
            self.assertEqual(str(row["cpt_tier"]), "PARKED")


if __name__ == "__main__":
    unittest.main()
