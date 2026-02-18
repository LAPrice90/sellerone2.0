import unittest

from scripts import phase1_oas


class Phase1OasTests(unittest.TestCase):
    def test_market_structure_hash_excludes_price_and_featured_identity(self) -> None:
        start_rows = [
            {
                "offer_variant_id": "V1",
                "fulfilment_channel": "FBA",
                "listing_price_gbp": "10.00",
                "is_featured_offer_winner": "1",
            },
            {
                "offer_variant_id": "V2",
                "fulfilment_channel": "FBM",
                "listing_price_gbp": "10.20",
                "is_featured_offer_winner": "0",
            },
        ]
        end_rows = [
            {
                "offer_variant_id": "V1",
                "fulfilment_channel": "FBA",
                "listing_price_gbp": "9.50",
                "is_featured_offer_winner": "0",
            },
            {
                "offer_variant_id": "V2",
                "fulfilment_channel": "FBM",
                "listing_price_gbp": "11.00",
                "is_featured_offer_winner": "1",
            },
        ]
        self.assertEqual(
            phase1_oas.build_market_structure_hash(start_rows),
            phase1_oas.build_market_structure_hash(end_rows),
        )

    def test_market_structure_hash_changes_when_variant_set_changes(self) -> None:
        hash_a = phase1_oas.build_market_structure_hash(
            [
                {"offer_variant_id": "V1", "fulfilment_channel": "FBA"},
                {"offer_variant_id": "V2", "fulfilment_channel": "FBM"},
            ]
        )
        hash_b = phase1_oas.build_market_structure_hash(
            [
                {"offer_variant_id": "V1", "fulfilment_channel": "FBA"},
                {"offer_variant_id": "V3", "fulfilment_channel": "FBM"},
            ]
        )
        self.assertNotEqual(hash_a, hash_b)

    def test_writer_conflict_detected_when_price_changes_without_our_submit(self) -> None:
        conflict, reason = phase1_oas.detect_writer_conflict(
            submitted_write_in_last_cycle="0",
            previous_verified_our_price_gbp="10.00",
            current_verified_our_price_gbp="10.25",
            approved_manual_override_prices_gbp=[],
        )
        self.assertTrue(conflict)
        self.assertEqual(reason, "WRITER_CONFLICT_EXTERNAL_PRICE_CHANGE")

    def test_writer_conflict_suppressed_for_allowlisted_manual_override(self) -> None:
        conflict, reason = phase1_oas.detect_writer_conflict(
            submitted_write_in_last_cycle="0",
            previous_verified_our_price_gbp="10.00",
            current_verified_our_price_gbp="10.25",
            approved_manual_override_prices_gbp=["10.25"],
        )
        self.assertFalse(conflict)
        self.assertEqual(reason, "WRITER_CHANGE_ALLOWLISTED_MANUAL_OVERRIDE")

    def test_oas_hard_fail_blocks_learning_when_any_invariant_fails(self) -> None:
        decision = phase1_oas.evaluate_oas_hard_fails(
            market_structure_hash_start="HASH_A",
            market_structure_hash_end="HASH_B",
            featured_outcome="UNKNOWN",
            writer_conflict_flag="1",
            promo_suspected_flag="0",
            pricing_health_suppressed_flag="1",
            our_purchasable_flag="0",
            our_purchasable_reliable_flag="1",
            featured_winner_delivery_unknown_flag="1",
        )
        self.assertEqual(decision.admissible_flag, "0")
        self.assertEqual(decision.context_quality_score, "0")
        self.assertIn("OAS_FAIL_MARKET_STRUCTURE_CHANGED", decision.hard_fail_reason_codes)
        self.assertIn("OAS_FAIL_FEATURED_OUTCOME_MISSING", decision.hard_fail_reason_codes)
        self.assertIn("OAS_FAIL_WRITER_CONFLICT", decision.hard_fail_reason_codes)
        self.assertIn("OAS_FAIL_PRICING_HEALTH_OR_SUPPRESSED", decision.hard_fail_reason_codes)
        self.assertIn("OAS_FAIL_OUR_OFFER_NOT_PURCHASABLE", decision.hard_fail_reason_codes)
        self.assertIn("OAS_FAIL_FEATURED_WINNER_DELIVERY_UNKNOWN", decision.hard_fail_reason_codes)

    def test_oas_purchasable_check_disabled_when_signal_not_reliable(self) -> None:
        decision = phase1_oas.evaluate_oas_hard_fails(
            market_structure_hash_start="HASH_A",
            market_structure_hash_end="HASH_A",
            featured_outcome="OURS",
            writer_conflict_flag="0",
            promo_suspected_flag="0",
            pricing_health_suppressed_flag="0",
            our_purchasable_flag="0",
            our_purchasable_reliable_flag="0",
            featured_winner_delivery_unknown_flag="0",
        )
        self.assertEqual(decision.admissible_flag, "1")
        self.assertEqual(decision.context_quality_score, "1")
        self.assertEqual(decision.hard_fail_reason_codes, [])


if __name__ == "__main__":
    unittest.main()
