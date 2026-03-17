import tempfile
import unittest
from pathlib import Path

import pandas as pd

from scripts.h.h_floor_truth import (
    REASON_REFERRAL_BAND_MISSING_100,
    compute_h_floor_for_sku,
    load_h_floor_context,
    resolve_h_floor_inputs,
)


class HFloorTruthTests(unittest.TestCase):
    def _context(self, *, product_rows: list[dict[str, object]], token_rows: list[dict[str, object]], token_cogs_rows: list[dict[str, object]]):
        td = tempfile.TemporaryDirectory()
        root = Path(td.name)
        out = root / "out"
        out.mkdir(parents=True, exist_ok=True)
        product_path = out / "product_db_preview.csv"
        token_path = out / "token_ledger_live.csv"
        token_cogs_path = out / "token_cogs_ledger.csv"

        pd.DataFrame(product_rows).to_csv(product_path, index=False)
        pd.DataFrame(token_rows).to_csv(token_path, index=False)
        pd.DataFrame(token_cogs_rows).to_csv(token_cogs_path, index=False)
        ctx = load_h_floor_context(
            product_db_path=product_path,
            token_ledger_path=token_path,
            token_cogs_path=token_cogs_path,
        )
        return td, ctx

    def test_sample_math_matches_expected_floor(self) -> None:
        td, ctx = self._context(
            product_rows=[
                {
                    "seller_sku": "TEST-SKU",
                    "last_vat_rate_pct": "20",
                    "last_fba_fee_ex_vat_100": "3.05",
                    "last_fba_fee_ex_vat": "3.05",
                    "last_commission_pct_100": "8",
                    "live_listing_price": "11.97",
                }
            ],
            token_rows=[
                {
                    "seller_sku": "TEST-SKU",
                    "cost_per_unit": "5.35",
                    "status": "available",
                    "sort_rank": "1",
                }
            ],
            token_cogs_rows=[],
        )
        try:
            inputs, result = compute_h_floor_for_sku("TEST-SKU", 11.97, context=ctx)
        finally:
            td.cleanup()

        self.assertAlmostEqual(inputs.cogs_exvat_gbp, 5.35, places=2)
        self.assertAlmostEqual(inputs.fba_exvat_gbp, 3.05, places=2)
        self.assertAlmostEqual(inputs.referral_pct, 0.08, places=4)
        self.assertAlmostEqual(inputs.referral_amount_gbp, 0.96, places=2)
        self.assertAlmostEqual(inputs.digital_fee_exvat_gbp, 0.08, places=2)
        self.assertAlmostEqual(inputs.margin_exvat_gbp, 0.535, places=3)
        self.assertAlmostEqual(result.sale_exvat_gbp, 9.975, places=3)
        self.assertAlmostEqual(result.floor_total_gbp, 11.97, places=2)

    def test_band_selection_boundary(self) -> None:
        td, ctx = self._context(
            product_rows=[
                {
                    "seller_sku": "BAND-SKU",
                    "last_vat_rate_pct": "20",
                    "last_fba_fee_ex_vat_10": "2.50",
                    "last_fba_fee_ex_vat_100": "3.50",
                    "last_commission_pct_10": "8",
                    "last_commission_pct_100": "15",
                }
            ],
            token_rows=[
                {"seller_sku": "BAND-SKU", "cost_per_unit": "5.00", "status": "available", "sort_rank": "1"}
            ],
            token_cogs_rows=[],
        )
        try:
            inputs_10 = resolve_h_floor_inputs("BAND-SKU", 10.00, context=ctx)
            inputs_100 = resolve_h_floor_inputs("BAND-SKU", 10.01, context=ctx)
        finally:
            td.cleanup()

        self.assertEqual(inputs_10.band_bucket, "10")
        self.assertEqual(inputs_10.source_referral, "L3_BAND_10")
        self.assertAlmostEqual(inputs_10.fba_exvat_gbp, 2.50, places=2)
        self.assertEqual(inputs_100.band_bucket, "100")
        self.assertEqual(inputs_100.source_referral, "L3_BAND_100")
        self.assertAlmostEqual(inputs_100.fba_exvat_gbp, 3.50, places=2)

    def test_referral_uses_same_band_and_never_crosses(self) -> None:
        td, ctx = self._context(
            product_rows=[
                {
                    "seller_sku": "REF-SKU",
                    "last_vat_rate_pct": "20",
                    "last_fba_fee_ex_vat_100": "3.05",
                    "referral_fee_10": "8",
                    "referral_fee_100": "",
                    "last_commission_pct_10": "8",
                    "last_commission_pct_100": "",
                }
            ],
            token_rows=[
                {"seller_sku": "REF-SKU", "cost_per_unit": "5.35", "status": "available", "sort_rank": "1"}
            ],
            token_cogs_rows=[],
        )
        try:
            inputs, _ = compute_h_floor_for_sku("REF-SKU", 11.97, context=ctx)
        finally:
            td.cleanup()

        self.assertEqual(inputs.band_bucket, "100")
        self.assertEqual(inputs.source_referral, "MISSING")
        self.assertIn(REASON_REFERRAL_BAND_MISSING_100, inputs.reason_codes)

    def test_dual_band_solver_can_select_under_10_when_candidate_above_10(self) -> None:
        td, ctx = self._context(
            product_rows=[
                {
                    "seller_sku": "DUAL-SKU",
                    "last_vat_rate_pct": "20",
                    "last_fba_fee_ex_vat_10": "1.20",
                    "last_fba_fee_ex_vat_100": "3.50",
                    "last_commission_pct_10": "8",
                    "last_commission_pct_100": "15",
                }
            ],
            token_rows=[
                {"seller_sku": "DUAL-SKU", "cost_per_unit": "2.50", "status": "available", "sort_rank": "1"}
            ],
            token_cogs_rows=[],
        )
        try:
            inputs, result = compute_h_floor_for_sku("DUAL-SKU", 10.50, context=ctx)
        finally:
            td.cleanup()

        self.assertEqual(inputs.band_bucket, "10")
        self.assertLessEqual(result.floor_total_gbp, 10.0)

    def test_token_next_available_selected(self) -> None:
        td, ctx = self._context(
            product_rows=[
                {
                    "seller_sku": "TOK-SKU",
                    "last_vat_rate_pct": "20",
                    "last_fba_fee_ex_vat_100": "3.05",
                    "last_commission_pct_100": "8",
                }
            ],
            token_rows=[
                {"seller_sku": "TOK-SKU", "cost_per_unit": "6.00", "status": "available", "sort_rank": "2"},
                {"seller_sku": "TOK-SKU", "cost_per_unit": "5.00", "status": "available", "sort_rank": "1"},
                {"seller_sku": "TOK-SKU", "cost_per_unit": "4.00", "status": "consumed", "sort_rank": "0"},
            ],
            token_cogs_rows=[],
        )
        try:
            inputs, _ = compute_h_floor_for_sku("TOK-SKU", 12.00, context=ctx)
        finally:
            td.cleanup()

        self.assertAlmostEqual(inputs.cogs_exvat_gbp, 5.00, places=2)
        self.assertEqual(inputs.source_cogs, "token_ledger_live_next_available")

    def test_token_cogs_median_fallback_when_live_missing(self) -> None:
        td, ctx = self._context(
            product_rows=[
                {
                    "seller_sku": "TOK-FALLBACK",
                    "last_vat_rate_pct": "20",
                    "last_fba_fee_ex_vat_100": "3.05",
                    "last_commission_pct_100": "8",
                }
            ],
            token_rows=[],
            token_cogs_rows=[
                {"seller_sku": "TOK-FALLBACK", "cogs_exvat": "4.00", "cogs_total": "4.00"},
                {"seller_sku": "TOK-FALLBACK", "cogs_exvat": "6.00", "cogs_total": "6.00"},
                {"seller_sku": "TOK-FALLBACK", "cogs_exvat": "10.00", "cogs_total": "10.00"},
            ],
        )
        try:
            inputs, _ = compute_h_floor_for_sku("TOK-FALLBACK", 12.00, context=ctx)
        finally:
            td.cleanup()

        self.assertAlmostEqual(inputs.cogs_exvat_gbp, 6.00, places=2)
        self.assertEqual(inputs.source_cogs, "token_cogs_ledger_median")


if __name__ == "__main__":
    unittest.main()

