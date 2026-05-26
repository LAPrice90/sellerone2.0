import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.phase1 import phase1_storage


class Phase1StorageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.data_dir = self.root / "data"
        self.out_dir = self.root / "out"
        self.lock_path = self.root / "out" / "phase1.lock"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.data_patch = patch.object(phase1_storage, "DATA_DIR", self.data_dir)
        self.lock_patch = patch.object(phase1_storage, "LOCK_PATH", self.lock_path)
        self.suppression_cases_patch = patch.object(
            phase1_storage,
            "H_SUPPRESSION_CASES_PATH",
            self.out_dir / "h_suppression_cases.csv",
        )
        self.suppression_reactivation_patch = patch.object(
            phase1_storage,
            "H_SUPPRESSION_REACTIVATION_LOG_PATH",
            self.out_dir / "h_suppression_reactivation_log.csv",
        )
        self.strategy_daily_patch = patch.object(
            phase1_storage,
            "H_STRATEGY_OUTCOME_DAILY_PATH",
            self.out_dir / "h_strategy_outcome_daily.csv",
        )
        self.data_patch.start()
        self.lock_patch.start()
        self.suppression_cases_patch.start()
        self.suppression_reactivation_patch.start()
        self.strategy_daily_patch.start()

    def tearDown(self) -> None:
        self.strategy_daily_patch.stop()
        self.suppression_reactivation_patch.stop()
        self.suppression_cases_patch.stop()
        self.data_patch.stop()
        self.lock_patch.stop()
        self.tmpdir.cleanup()

    def test_atomic_write_overwrites_and_leaves_no_tmp_files(self) -> None:
        path = self.data_dir / "atomic.csv"
        schema = ["id", "value"]
        path.write_text("id,value\nold,1\n", encoding="utf-8")
        phase1_storage._atomic_write_rows(  # pylint: disable=protected-access
            path,
            [{"id": "new", "value": "2"}],
            schema,
        )
        rows = phase1_storage.read_table(path)
        self.assertEqual(rows, [{"id": "new", "value": "2"}])
        tmp_candidates = list(path.parent.glob(f".{path.name}.tmp.*"))
        self.assertEqual(tmp_candidates, [])

    def test_append_only_table_appends_without_overwrite(self) -> None:
        phase1_storage.append(
            "offer_snapshot_facts",
            [
                {
                    "sku": "SKU1",
                    "asin": "ASIN1",
                    "marketplace_id": "M1",
                    "seller_id_raw": "SELLER_A",
                    "seller_id_canonical": "seller_a",
                    "offer_variant_id": "VAR_A",
                    "is_our_offer": "1",
                    "promo_suspected_flag": "0",
                    "unknown_outcome_flag": "0",
                }
            ],
        )
        phase1_storage.append(
            "offer_snapshot_facts",
            [
                {
                    "sku": "SKU1",
                    "asin": "ASIN1",
                    "marketplace_id": "M1",
                    "seller_id_raw": "SELLER_B",
                    "seller_id_canonical": "seller_b",
                    "offer_variant_id": "VAR_B",
                    "is_our_offer": "0",
                    "promo_suspected_flag": "0",
                    "unknown_outcome_flag": "0",
                }
            ],
        )
        rows = phase1_storage.read_where("offer_snapshot_facts", {"sku": "SKU1"})
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["offer_variant_id"], "VAR_A")
        self.assertEqual(rows[1]["offer_variant_id"], "VAR_B")

    def test_upsert_dimension_offer_variants_updates_existing_row(self) -> None:
        phase1_storage.write_table(
            "offer_variants",
            [
                {
                    "offer_variant_id": "VAR_1",
                    "sku": "SKU1",
                    "seller_id_canonical": "seller_a",
                    "shipping_template": "std",
                    "variant_active_flag": "1",
                }
            ],
        )
        phase1_storage.write_table(
            "offer_variants",
            [
                {
                    "offer_variant_id": "VAR_1",
                    "sku": "SKU1",
                    "seller_id_canonical": "seller_a",
                    "shipping_template": "prime",
                    "variant_active_flag": "1",
                }
            ],
        )
        row = phase1_storage.read_by_keys("offer_variants", {"offer_variant_id": "VAR_1"})
        self.assertIsNotNone(row)
        self.assertEqual(row["shipping_template"], "prime")
        all_rows = phase1_storage.read_where("offer_variants", {"offer_variant_id": "VAR_1"})
        self.assertEqual(len(all_rows), 1)

    def test_upsert_memory_variant_delta_memory(self) -> None:
        phase1_storage.write_table(
            "variant_delta_memory",
            [
                {
                    "sku": "SKU1",
                    "rival_key": "BEST_RIVAL",
                    "delta_confidence": "0.2",
                    "valid_test_count": "1",
                    "contaminated_test_count": "0",
                }
            ],
        )
        phase1_storage.write_table(
            "variant_delta_memory",
            [
                {
                    "sku": "SKU1",
                    "rival_key": "BEST_RIVAL",
                    "delta_confidence": "0.9",
                    "valid_test_count": "5",
                    "contaminated_test_count": "1",
                }
            ],
        )
        row = phase1_storage.read_by_keys(
            "variant_delta_memory",
            {"sku": "SKU1", "rival_key": "BEST_RIVAL"},
        )
        self.assertIsNotNone(row)
        self.assertEqual(row["delta_confidence"], "0.9")
        self.assertEqual(row["valid_test_count"], "5")

    def test_read_latest_with_filter(self) -> None:
        phase1_storage.append(
            "execution_log",
            [
                {
                    "event_ts_utc": "2026-02-13T10:00:00Z",
                    "sku": "SKU1",
                    "state": "HOLD_OBSERVE",
                    "write_status": "NONE",
                    "final_ceiling_landed_gbp": "20",
                    "hard_floor_gbp": "10",
                    "reason_codes_json": "[]",
                },
                {
                    "event_ts_utc": "2026-02-13T11:00:00Z",
                    "sku": "SKU1",
                    "state": "REGAIN",
                    "write_status": "APPLIED",
                    "final_ceiling_landed_gbp": "20",
                    "hard_floor_gbp": "10",
                    "reason_codes_json": "[]",
                },
            ],
        )
        latest = phase1_storage.read_latest("execution_log", {"sku": "SKU1"})
        self.assertIsNotNone(latest)
        self.assertEqual(latest["state"], "REGAIN")

    def test_append_rejects_non_append_only_table(self) -> None:
        with self.assertRaises(ValueError):
            phase1_storage.append(
                "offer_variants",
                [
                    {
                        "offer_variant_id": "VAR_1",
                        "sku": "SKU1",
                        "seller_id_canonical": "seller_a",
                    }
                ],
            )

    def test_append_suppression_cases_fills_required_fields_when_blank(self) -> None:
        phase1_storage.append_suppression_cases(
            [
                {
                    "event_ts_utc": "2026-04-16T10:00:00Z",
                    "sku": "SKU_SUPP",
                    "asin": "ASIN_SUPP",
                    "suppression_case_id": "CASE1",
                    "buy_box_state": "SUPPRESSED_ASIN",
                    "suppression_target_source": "",
                    "suppression_reactivation_target_landed_gbp": "",
                    "suppression_ceiling_landed_temp": "",
                    "anchor_floor_price": "",
                }
            ]
        )
        rows = phase1_storage.read_table(phase1_storage.H_SUPPRESSION_CASES_PATH)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["suppression_target_source"], "NONE_UNAVAILABLE")
        self.assertEqual(rows[0]["suppression_ceiling_landed_temp"], "UNAVAILABLE")
        self.assertEqual(rows[0]["suppression_reactivation_target_landed_gbp"], "UNAVAILABLE")

    def test_append_suppression_reactivation_fills_required_fields_when_blank(self) -> None:
        phase1_storage.append_suppression_reactivation_log(
            [
                {
                    "event_ts_utc": "2026-04-16T10:01:00Z",
                    "sku": "SKU_SUPP",
                    "asin": "ASIN_SUPP",
                    "state": "STATE_SUPPRESSION_REACTIVATION",
                    "target_price_gbp": "9.99",
                    "suppression_target_source": "",
                    "suppression_reactivation_target_landed_gbp": "",
                    "suppression_ceiling_landed_temp": "",
                    "anchor_floor_price": "",
                }
            ]
        )
        rows = phase1_storage.read_table(phase1_storage.H_SUPPRESSION_REACTIVATION_LOG_PATH)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["suppression_target_source"], "NONE_UNAVAILABLE")
        self.assertEqual(rows[0]["suppression_ceiling_landed_temp"], "9.99")
        self.assertEqual(rows[0]["suppression_reactivation_target_landed_gbp"], "9.99")

    def test_strategy_outcome_daily_clamps_side_counts_to_decision(self) -> None:
        phase1_storage.upsert_h_strategy_outcome_daily(
            [
                {
                    "asof_date": "2026-04-16",
                    "scenario_type": "multi_seller_ladder_cap",
                    "chosen_tactic": "REGAIN_LADDER_CAP",
                    "decision_rows": "2",
                    "applied_rows": "1",
                    "no_write_rows": "1",
                    "resolved_rows": "2",
                    "pending_rows": "0",
                    "success_rows": "1",
                    "failed_rows": "0",
                    "expired_rows": "1",
                    "aborted_rows": "0",
                    "success_rate_pct": "100.00",
                    "failed_rate_pct": "0.00",
                    "sample_min_rows": "150",
                    "provisional_sample_flag": "1",
                    "avg_seller_count": "2.00",
                    "avg_price_gap_to_lowest_gbp": "0.05",
                    "below_break_even_rows": "5",
                    "at_floor_rows": "9",
                    "notes": "",
                }
            ]
        )
        row = phase1_storage.read_table(phase1_storage.H_STRATEGY_OUTCOME_DAILY_PATH)[0]
        self.assertEqual(row["decision_rows"], "2")
        self.assertEqual(row["below_break_even_rows"], "2")
        self.assertEqual(row["at_floor_rows"], "2")


if __name__ == "__main__":
    unittest.main()

