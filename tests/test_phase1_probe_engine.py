import unittest
from decimal import Decimal

from scripts import phase1_probe_engine


class Phase1ProbeEngineTests(unittest.TestCase):
    def test_best_rival_effective_price_ignores_our_offer(self) -> None:
        rows = [
            {"is_our_offer": "1", "effective_price_gbp": "10.10"},
            {"is_our_offer": "0", "effective_price_gbp": "10.40"},
            {"is_our_offer": "0", "effective_price_gbp": "10.05"},
        ]
        rival = phase1_probe_engine.best_rival_effective_price(rows)
        self.assertEqual(rival, Decimal("10.05"))

    def test_resolve_probe_state_applies_spec_transitions(self) -> None:
        regain = phase1_probe_engine.resolve_probe_state(
            featured_outcome="NOT_OURS",
            best_rival_effective_price_gbp=Decimal("10.00"),
            highest_delta_win_effective_gbp="",
            lowest_delta_loss_effective_gbp="",
            delta_tolerance_gbp="0.02",
        )
        self.assertEqual(regain.state, "REGAIN")

        raise_find_loss = phase1_probe_engine.resolve_probe_state(
            featured_outcome="OURS",
            best_rival_effective_price_gbp=Decimal("10.00"),
            highest_delta_win_effective_gbp="0.05",
            lowest_delta_loss_effective_gbp="",
            delta_tolerance_gbp="0.02",
        )
        self.assertEqual(raise_find_loss.state, "RAISE_FIND_LOSS")

        narrow = phase1_probe_engine.resolve_probe_state(
            featured_outcome="OURS",
            best_rival_effective_price_gbp=Decimal("10.00"),
            highest_delta_win_effective_gbp="0.02",
            lowest_delta_loss_effective_gbp="0.20",
            delta_tolerance_gbp="0.02",
        )
        self.assertEqual(narrow.state, "BRACKET_NARROW")

        stable = phase1_probe_engine.resolve_probe_state(
            featured_outcome="OURS",
            best_rival_effective_price_gbp=Decimal("10.00"),
            highest_delta_win_effective_gbp="0.10",
            lowest_delta_loss_effective_gbp="0.11",
            delta_tolerance_gbp="0.02",
        )
        self.assertEqual(stable.state, "STABLE_WIN")

        unknown = phase1_probe_engine.resolve_probe_state(
            featured_outcome="UNKNOWN",
            best_rival_effective_price_gbp=Decimal("10.00"),
            highest_delta_win_effective_gbp="0.10",
            lowest_delta_loss_effective_gbp="0.11",
            delta_tolerance_gbp="0.02",
        )
        self.assertEqual(unknown.state, "HOLD_OBSERVE")
        self.assertTrue(unknown.learning_blocked)

    def test_choose_next_price_bracket_midpoint_and_clamps(self) -> None:
        decision = phase1_probe_engine.choose_next_price(
            state="BRACKET_NARROW",
            current_price_gbp="10.00",
            hard_floor_gbp="9.50",
            final_ceiling_landed_gbp="10.20",
            max_step_down_gbp="0.20",
            max_step_up_gbp="0.20",
            max_daily_drop_gbp="0.60",
            daily_drop_used_gbp="0.00",
            highest_delta_win_effective_gbp="-0.04",
            lowest_delta_loss_effective_gbp="0.10",
            best_rival_effective_price_gbp="10.10",
            stable_buffer_gbp="0.02",
        )
        self.assertEqual(decision.target_price_gbp, "10.13")
        self.assertTrue(decision.write_required)
        self.assertIn("STEP_BRACKET_MIDPOINT", decision.reason_codes)

        regain_clamp = phase1_probe_engine.choose_next_price(
            state="REGAIN",
            current_price_gbp="9.55",
            hard_floor_gbp="9.50",
            final_ceiling_landed_gbp="11.00",
            max_step_down_gbp="0.20",
            max_step_up_gbp="0.20",
            max_daily_drop_gbp="0.60",
            daily_drop_used_gbp="0.50",
            highest_delta_win_effective_gbp="",
            lowest_delta_loss_effective_gbp="",
            best_rival_effective_price_gbp="9.40",
            stable_buffer_gbp="0.02",
        )
        self.assertEqual(regain_clamp.target_price_gbp, "9.50")
        self.assertIn("STEP_REGAIN_TO_RIVAL", regain_clamp.reason_codes)
        self.assertIn("GUARDRAIL_HARD_FLOOR_CLAMP", regain_clamp.reason_codes)

    def test_update_delta_memory_updates_bounds_and_confidence(self) -> None:
        memory = {
            "highest_delta_win_effective_gbp": "",
            "lowest_delta_loss_effective_gbp": "",
            "valid_test_count": "0",
            "contaminated_test_count": "0",
            "last_valid_test_utc": "",
        }
        win_update = phase1_probe_engine.update_delta_memory(
            current_memory=memory,
            observed_delta_effective_gbp="-0.05",
            observed_outcome="WIN",
            oas_admissible_flag="1",
            now_utc="2026-02-13T13:10:00Z",
            min_clean_tests_for_confidence=5,
        )
        self.assertTrue(win_update.learning_updated)
        self.assertEqual(win_update.highest_delta_win_effective_gbp, "-0.05")
        self.assertEqual(win_update.valid_test_count, "1")
        self.assertEqual(win_update.delta_confidence, "0.2")

        loss_update = phase1_probe_engine.update_delta_memory(
            current_memory={
                "highest_delta_win_effective_gbp": win_update.highest_delta_win_effective_gbp,
                "lowest_delta_loss_effective_gbp": "",
                "valid_test_count": win_update.valid_test_count,
                "contaminated_test_count": win_update.contaminated_test_count,
                "last_valid_test_utc": win_update.last_valid_test_utc,
            },
            observed_delta_effective_gbp="0.08",
            observed_outcome="LOSS",
            oas_admissible_flag="1",
            now_utc="2026-02-13T13:25:00Z",
            min_clean_tests_for_confidence=5,
        )
        self.assertEqual(loss_update.lowest_delta_loss_effective_gbp, "0.08")
        self.assertEqual(loss_update.learned_delta_effective_gbp, "0.02")
        self.assertEqual(loss_update.valid_test_count, "2")
        self.assertEqual(loss_update.last_valid_test_utc, "2026-02-13T13:25:00Z")

        contaminated = phase1_probe_engine.update_delta_memory(
            current_memory={
                "highest_delta_win_effective_gbp": loss_update.highest_delta_win_effective_gbp,
                "lowest_delta_loss_effective_gbp": loss_update.lowest_delta_loss_effective_gbp,
                "valid_test_count": loss_update.valid_test_count,
                "contaminated_test_count": loss_update.contaminated_test_count,
                "last_valid_test_utc": loss_update.last_valid_test_utc,
            },
            observed_delta_effective_gbp="0.03",
            observed_outcome="UNKNOWN",
            oas_admissible_flag="0",
            now_utc="2026-02-13T13:40:00Z",
            min_clean_tests_for_confidence=5,
        )
        self.assertFalse(contaminated.learning_updated)
        self.assertEqual(contaminated.valid_test_count, "2")
        self.assertEqual(contaminated.contaminated_test_count, "1")

    def test_choose_next_price_floor_priority_when_ceiling_below_floor(self) -> None:
        decision = phase1_probe_engine.choose_next_price(
            state="REGAIN",
            current_price_gbp="5.99",
            hard_floor_gbp="6.12",
            final_ceiling_landed_gbp="5.97",
            max_step_down_gbp="0.20",
            max_step_up_gbp="0.20",
            max_daily_drop_gbp="0.60",
            daily_drop_used_gbp="0.00",
            highest_delta_win_effective_gbp="",
            lowest_delta_loss_effective_gbp="",
            best_rival_effective_price_gbp="6.00",
            stable_buffer_gbp="0.02",
        )
        self.assertEqual(decision.state, "REGAIN")
        self.assertEqual(decision.target_price_gbp, "6.12")
        self.assertTrue(decision.write_required)
        self.assertIn("FAIL_CEILING_BELOW_HARD_FLOOR", decision.reason_codes)
        self.assertIn("FLOOR_PRIORITY_CEILING_CONFLICT", decision.reason_codes)
        self.assertIn("FLOOR_PRIORITY_ENFORCED", decision.reason_codes)

        already_safe = phase1_probe_engine.choose_next_price(
            state="REGAIN",
            current_price_gbp="9.99",
            hard_floor_gbp="6.12",
            final_ceiling_landed_gbp="5.97",
            max_step_down_gbp="0.20",
            max_step_up_gbp="0.20",
            max_daily_drop_gbp="0.60",
            daily_drop_used_gbp="0.00",
            highest_delta_win_effective_gbp="",
            lowest_delta_loss_effective_gbp="",
            best_rival_effective_price_gbp="6.00",
            stable_buffer_gbp="0.02",
        )
        self.assertFalse(already_safe.write_required)
        self.assertEqual(already_safe.target_price_gbp, "9.99")
        self.assertIn("FLOOR_PRIORITY_ALREADY_SAFE_NO_WRITE", already_safe.reason_codes)


if __name__ == "__main__":
    unittest.main()
