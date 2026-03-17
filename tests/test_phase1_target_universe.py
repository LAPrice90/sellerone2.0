import tempfile
import unittest
from pathlib import Path

import pandas as pd

from scripts.phase1.phase1_target_universe import resolve_target_universe


class Phase1TargetUniverseTests(unittest.TestCase):
    def test_active_merchant_requires_listing_and_in_stock(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            out = root / "out"
            out.mkdir(parents=True, exist_ok=True)

            pd.DataFrame(
                [
                    {"seller-sku": "SKU_IN_STOCK", "status": "Active"},
                    {"seller-sku": "SKU_OUT_STOCK", "status": "Active"},
                    {"seller-sku": "SKU_NO_LISTING", "status": "Active"},
                    {"seller-sku": "SKU_INACTIVE", "status": "Inactive"},
                ]
            ).to_csv(out / "merchant_listings_latest.csv", index=False)

            pd.DataFrame(
                [
                    {"sku": "SKU_IN_STOCK", "our_price": "12.50", "we_present_flag": "1"},
                    {"sku": "SKU_OUT_STOCK", "our_price": "0.00", "we_present_flag": "0"},
                    {"sku": "SKU_OTHER", "our_price": "11.00", "we_present_flag": "1"},
                ]
            ).to_csv(out / "listing_offer_snapshot_2026-02-17.csv", index=False)

            result = resolve_target_universe(
                {"target_universe_mode": "active_merchant"},
                out_dir=out,
                scope_path=out / "phase1_sku_scope.csv",
            )

            self.assertEqual(result["mode"], "active_merchant")
            self.assertEqual(result["source"], "merchant_active_with_listing_in_stock")
            self.assertEqual(result["candidate_count"], 3)
            self.assertEqual(result["resolved_count"], 1)
            self.assertEqual(result["skipped_no_listing_count"], 1)
            self.assertEqual(result["skipped_out_of_stock_count"], 1)
            self.assertEqual(result["skus"], ["SKU_IN_STOCK"])

    def test_scope_non_parked_mode(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            out = root / "out"
            out.mkdir(parents=True, exist_ok=True)
            scope_path = out / "phase1_sku_scope.csv"
            pd.DataFrame(
                [
                    {"sku": "SKU_A", "parked_flag": "0"},
                    {"sku": "SKU_B", "parked_flag": "1"},
                    {"sku": "SKU_C", "parked_flag": "0"},
                ]
            ).to_csv(scope_path, index=False)

            result = resolve_target_universe(
                {"target_universe_mode": "scope_non_parked"},
                out_dir=out,
                scope_path=scope_path,
            )

            self.assertEqual(result["mode"], "scope_non_parked")
            self.assertEqual(result["candidate_count"], 3)
            self.assertEqual(result["resolved_count"], 2)
            self.assertEqual(result["skipped_parked_count"], 1)
            self.assertEqual(result["skus"], ["SKU_A", "SKU_C"])

    def test_lab_cohort_mode(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            out = root / "out"
            out.mkdir(parents=True, exist_ok=True)
            cohort_path = root / "h_lab_cohort.csv"
            pd.DataFrame(
                [
                    {"sku": "SKU_A", "lane": "pilot", "enabled": "yes", "effective_utc": "", "note": ""},
                    {"sku": "SKU_B", "lane": "pilot", "enabled": "0", "effective_utc": "", "note": ""},
                    {"sku": "SKU_C", "lane": "pilot", "enabled": "TRUE", "effective_utc": "", "note": ""},
                ]
            ).to_csv(cohort_path, index=False)

            result = resolve_target_universe(
                {"target_universe_mode": "lab_cohort"},
                out_dir=out,
                scope_path=out / "phase1_sku_scope.csv",
                cohort_path=cohort_path,
            )

            self.assertEqual(result["mode"], "lab_cohort")
            self.assertEqual(result["source"], "h_lab_cohort_enabled")
            self.assertEqual(result["candidate_count"], 2)
            self.assertEqual(result["resolved_count"], 2)
            self.assertEqual(result["skus"], ["SKU_A", "SKU_C"])

    def test_single_sku_mode_uses_whitelist(self) -> None:
        result = resolve_target_universe(
            {
                "target_universe_mode": "single_sku",
                "pilot_whitelist_skus": "SKU_A, sku_b,SKU_A",
                "sku": "SKU_FALLBACK",
            }
        )

        self.assertEqual(result["mode"], "single_sku")
        self.assertEqual(result["source"], "config_single_sku")
        self.assertEqual(result["candidate_count"], 2)
        self.assertEqual(result["resolved_count"], 2)
        self.assertEqual(result["skus"], ["SKU_A", "SKU_B"])


if __name__ == "__main__":
    unittest.main()

