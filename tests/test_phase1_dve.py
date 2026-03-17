import unittest
from decimal import Decimal

from scripts.phase1 import phase1_dve


class Phase1DveTests(unittest.TestCase):
    def test_penalty_curve_v0_expected_values_and_cap(self) -> None:
        self.assertEqual(phase1_dve.penalty_for_gap_days(0), Decimal("0.00"))
        self.assertEqual(phase1_dve.penalty_for_gap_days(1), Decimal("0.15"))
        self.assertEqual(phase1_dve.penalty_for_gap_days(2), Decimal("0.30"))
        self.assertEqual(phase1_dve.penalty_for_gap_days(3), Decimal("0.45"))
        self.assertEqual(phase1_dve.penalty_for_gap_days(4), Decimal("0.60"))
        self.assertEqual(phase1_dve.penalty_for_gap_days(9), Decimal("0.60"))

    def test_apply_dve_v0_computes_effective_price_against_expected_rows(self) -> None:
        rows = [
            {"offer_variant_id": "OURS", "landed_price_gbp": "10.00", "min_delivery_days": "1"},
            {"offer_variant_id": "FAST_RIVAL", "landed_price_gbp": "10.20", "min_delivery_days": "0"},
            {"offer_variant_id": "SLOW_RIVAL", "landed_price_gbp": "9.95", "min_delivery_days": "3"},
        ]
        result = phase1_dve.apply_dve_v0(rows)

        self.assertEqual(result.penalty_curve_version, "v0")
        self.assertEqual(result.fastest_delivery_days, 0)
        self.assertFalse(result.delivery_penalty_unknown_flag)

        by_id = {row["offer_variant_id"]: row for row in result.rows}
        self.assertEqual(by_id["FAST_RIVAL"]["delivery_gap_days"], "0")
        self.assertEqual(by_id["FAST_RIVAL"]["delivery_penalty_gbp"], "0.00")
        self.assertEqual(by_id["FAST_RIVAL"]["effective_price_gbp"], "10.20")

        self.assertEqual(by_id["OURS"]["delivery_gap_days"], "1")
        self.assertEqual(by_id["OURS"]["delivery_penalty_gbp"], "0.15")
        self.assertEqual(by_id["OURS"]["effective_price_gbp"], "10.15")

        self.assertEqual(by_id["SLOW_RIVAL"]["delivery_gap_days"], "3")
        self.assertEqual(by_id["SLOW_RIVAL"]["delivery_penalty_gbp"], "0.45")
        self.assertEqual(by_id["SLOW_RIVAL"]["effective_price_gbp"], "10.40")

    def test_apply_dve_v0_unknown_delivery_falls_back_to_landed_only(self) -> None:
        rows = [{"offer_variant_id": "X", "landed_price_gbp": "12.34", "min_delivery_days": ""}]
        result = phase1_dve.apply_dve_v0(rows)
        row = result.rows[0]

        self.assertTrue(result.delivery_penalty_unknown_flag)
        self.assertIsNone(result.fastest_delivery_days)
        self.assertEqual(row["delivery_gap_days"], "")
        self.assertEqual(row["delivery_penalty_gbp"], "")
        self.assertEqual(row["effective_price_gbp"], "12.34")


if __name__ == "__main__":
    unittest.main()

