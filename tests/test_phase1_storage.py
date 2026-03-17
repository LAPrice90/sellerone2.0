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
        self.lock_path = self.root / "out" / "phase1.lock"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.data_patch = patch.object(phase1_storage, "DATA_DIR", self.data_dir)
        self.lock_patch = patch.object(phase1_storage, "LOCK_PATH", self.lock_path)
        self.data_patch.start()
        self.lock_patch.start()

    def tearDown(self) -> None:
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


if __name__ == "__main__":
    unittest.main()

