import unittest

from scripts.phase1 import phase1_ceilings


class Phase1CeilingsTests(unittest.TestCase):
    def test_compliance_ceiling_ignores_cpt_and_uses_anchor(self) -> None:
        result = phase1_ceilings.compute_compliance_ceiling(
            cpt_gbp="9.99",
            external_reference_price_gbp="12.00",
            compliance_anchor_gbp="20.00",
            policy_buffer_pct="0.03",
            manual_cap_gbp="99.99",
        )
        self.assertEqual(result.compliance_ceiling_landed_gbp, "20.00")
        self.assertEqual(result.compliance_confidence, "0.7")
        self.assertIn("COMPLIANCE_CPT_TELEMETRY_ONLY", result.reason_codes)
        self.assertIn("COMPLIANCE_ANCHOR_FALLBACK", result.reason_codes)

    def test_compliance_ceiling_uses_anchor_fallback_when_cpt_missing(self) -> None:
        result = phase1_ceilings.compute_compliance_ceiling(
            cpt_gbp="",
            external_reference_price_gbp="11.00",
            compliance_anchor_gbp="20.00",
            policy_buffer_pct="0.03",
            manual_cap_gbp="17.50",
        )
        self.assertEqual(result.compliance_ceiling_landed_gbp, "20.00")
        self.assertEqual(result.compliance_confidence, "0.7")
        self.assertIn("COMPLIANCE_CPT_UNAVAILABLE", result.reason_codes)
        self.assertIn("COMPLIANCE_ANCHOR_FALLBACK", result.reason_codes)

    def test_compliance_ceiling_uses_manual_cap_fallback_when_cpt_and_anchor_missing(self) -> None:
        result = phase1_ceilings.compute_compliance_ceiling(
            cpt_gbp="",
            external_reference_price_gbp="11.00",
            compliance_anchor_gbp="",
            policy_buffer_pct="0.03",
            manual_cap_gbp="17.50",
        )
        self.assertEqual(result.compliance_ceiling_landed_gbp, "17.50")
        self.assertEqual(result.compliance_confidence, "0.5")
        self.assertIn("COMPLIANCE_CPT_UNAVAILABLE", result.reason_codes)
        self.assertIn("COMPLIANCE_MANUAL_CAP_FALLBACK", result.reason_codes)

    def test_compliance_ceiling_unavailable_when_all_inputs_missing(self) -> None:
        result = phase1_ceilings.compute_compliance_ceiling(
            cpt_gbp="",
            external_reference_price_gbp="",
            compliance_anchor_gbp="",
            policy_buffer_pct="0.03",
            manual_cap_gbp="",
        )
        self.assertEqual(result.compliance_ceiling_landed_gbp, "")
        self.assertEqual(result.compliance_confidence, "0")
        self.assertIn("COMPLIANCE_CPT_UNAVAILABLE", result.reason_codes)
        self.assertIn("COMPLIANCE_UNAVAILABLE", result.reason_codes)

    def test_eligibility_ladder_prefers_usable_foep(self) -> None:
        result = phase1_ceilings.resolve_eligibility_ladder(
            foep_price_gbp="12.34",
            foep_status="OK",
            foep_last_refresh_utc="2026-02-13T11:00:00Z",
            cpt_gbp="12.00",
            manual_cap_gbp="13.00",
            last_known_safe_gbp="11.00",
            now_utc="2026-02-13T12:00:00Z",
            foep_stale_hours=48,
            foep_sanity_min_mult="0.5",
            foep_sanity_max_mult="2.0",
            market_reference_price_gbp="12.10",
        )
        self.assertEqual(result.eligibility_source, "FOEP")
        self.assertEqual(result.eligibility_ceiling_landed_gbp, "12.34")
        self.assertEqual(result.eligibility_confidence, "0.95")
        self.assertIn("ELIG_CEILING_FOEP_USED", result.reason_codes)

    def test_eligibility_ladder_uses_manual_when_foep_missing_and_cpt_present(self) -> None:
        result = phase1_ceilings.resolve_eligibility_ladder(
            foep_price_gbp="",
            foep_status="",
            foep_last_refresh_utc="",
            cpt_gbp="11.89",
            manual_cap_gbp="12.50",
            last_known_safe_gbp="10.99",
            now_utc="2026-02-13T12:00:00Z",
            foep_stale_hours=48,
            foep_sanity_min_mult="0.5",
            foep_sanity_max_mult="2.0",
            market_reference_price_gbp="11.50",
        )
        self.assertEqual(result.eligibility_source, "MANUAL")
        self.assertEqual(result.eligibility_ceiling_landed_gbp, "12.50")
        self.assertIn("FOEP_MISSING", result.reason_codes)
        self.assertIn("CPT_TELEMETRY_ONLY", result.reason_codes)
        self.assertIn("ELIG_CEILING_MANUAL_USED", result.reason_codes)

    def test_eligibility_ladder_falls_back_to_manual_on_ineligible_foep_without_cpt(self) -> None:
        result = phase1_ceilings.resolve_eligibility_ladder(
            foep_price_gbp="12.34",
            foep_status="ASIN_NOT_ELIGIBLE",
            foep_last_refresh_utc="2026-02-13T10:00:00Z",
            cpt_gbp="",
            manual_cap_gbp="12.10",
            last_known_safe_gbp="11.50",
            now_utc="2026-02-13T12:00:00Z",
            foep_stale_hours=48,
            foep_sanity_min_mult="0.5",
            foep_sanity_max_mult="2.0",
            market_reference_price_gbp="12.00",
        )
        self.assertEqual(result.eligibility_source, "MANUAL")
        self.assertEqual(result.eligibility_ceiling_landed_gbp, "12.10")
        self.assertIn("FOEP_INELIGIBLE_ASIN", result.reason_codes)
        self.assertIn("ELIG_CEILING_MANUAL_USED", result.reason_codes)

    def test_eligibility_ladder_falls_back_to_last_known_safe(self) -> None:
        result = phase1_ceilings.resolve_eligibility_ladder(
            foep_price_gbp="",
            foep_status="",
            foep_last_refresh_utc="",
            cpt_gbp="",
            manual_cap_gbp="",
            last_known_safe_gbp="10.75",
            now_utc="2026-02-13T12:00:00Z",
            foep_stale_hours=48,
            foep_sanity_min_mult="0.5",
            foep_sanity_max_mult="2.0",
            market_reference_price_gbp="",
        )
        self.assertEqual(result.eligibility_source, "LAST_KNOWN_SAFE")
        self.assertEqual(result.eligibility_ceiling_landed_gbp, "10.75")
        self.assertIn("ELIG_CEILING_LAST_KNOWN_SAFE_USED", result.reason_codes)

    def test_final_ceiling_clamps_to_lowest_of_three_and_sets_binding_type(self) -> None:
        result = phase1_ceilings.compute_final_ceiling(
            compliance_ceiling_landed_gbp="19.40",
            eligibility_ceiling_landed_gbp="18.90",
            manual_cap_gbp="18.50",
        )
        self.assertEqual(result.final_ceiling_landed_gbp, "18.50")
        self.assertEqual(result.binding_ceiling_type, "MANUAL_CAP")
        self.assertIn("BINDING_CEILING_MANUAL_CAP", result.reason_codes)

    def test_final_ceiling_manual_cap_binds_when_compliance_unavailable(self) -> None:
        result = phase1_ceilings.compute_final_ceiling(
            compliance_ceiling_landed_gbp="",
            eligibility_ceiling_landed_gbp="9.99",
            manual_cap_gbp="9.99",
        )
        self.assertEqual(result.final_ceiling_landed_gbp, "9.99")
        self.assertEqual(result.binding_ceiling_type, "MANUAL_CAP")
        self.assertIn("BINDING_CEILING_MANUAL_CAP", result.reason_codes)

    def test_final_ceiling_compliance_binds_when_lower_than_manual(self) -> None:
        result = phase1_ceilings.compute_final_ceiling(
            compliance_ceiling_landed_gbp="9.69",
            eligibility_ceiling_landed_gbp="9.99",
            manual_cap_gbp="9.99",
        )
        self.assertEqual(result.final_ceiling_landed_gbp, "9.69")
        self.assertEqual(result.binding_ceiling_type, "COMPLIANCE")
        self.assertIn("BINDING_CEILING_COMPLIANCE", result.reason_codes)

    def test_final_ceiling_eligibility_binds_when_lower_than_manual(self) -> None:
        result = phase1_ceilings.compute_final_ceiling(
            compliance_ceiling_landed_gbp="",
            eligibility_ceiling_landed_gbp="9.50",
            manual_cap_gbp="9.99",
        )
        self.assertEqual(result.final_ceiling_landed_gbp, "9.50")
        self.assertEqual(result.binding_ceiling_type, "ELIGIBILITY")
        self.assertIn("BINDING_CEILING_ELIGIBILITY", result.reason_codes)

    def test_suppression_reactivation_infers_upper_bound_from_lowest_competitor(self) -> None:
        result = phase1_ceilings.resolve_suppression_reactivation_target(
            buy_box_state="SUPPRESSED_ASIN",
            now_utc="2026-03-07T15:42:04Z",
            competitive_price_threshold_gbp="",
            competitive_price_gbp="",
            average_selling_price_gbp="",
            foep_price_gbp="",
            probe_threshold_estimate_gbp="",
            existing_final_ceiling_landed_gbp="12.00",
            anchor_floor_price_gbp="4.90",
            hard_floor_gbp="4.50",
            probe_ceiling_candidate_gbp="",
            best_competitor_price_gbp="5.70",
            no_buy_box_offer_present="1",
            current_suppression_ceiling_landed_temp="",
            current_suppression_ceiling_expiry_utc="",
        )
        self.assertEqual(result.suppression_reactivation_target_landed_gbp, "")
        self.assertEqual(result.suppression_threshold_upper_bound_gbp, "5.70")
        self.assertEqual(result.suppression_ceiling_landed_temp, "5.70")
        self.assertEqual(result.suppression_ceiling_source, "LOWEST_COMPETITOR_INFERENCE")
        self.assertIn("SUPPRESSION_THRESHOLD_UPPER_BOUND_INFERRED_LOWEST_COMPETITOR", result.reason_codes)


if __name__ == "__main__":
    unittest.main()

