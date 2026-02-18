import json
import tempfile
import unittest
from pathlib import Path

from scripts import h_floor_policy


class HFloorPolicyTests(unittest.TestCase):
    def test_load_defaults_when_policy_file_missing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "missing.json"
            policy = h_floor_policy.load_h_floor_vat_policy(path=path)
            self.assertTrue(bool(policy.get("vat_registered", False)))
            self.assertTrue(bool(policy.get("recover_input_vat_on_cogs", False)))
            self.assertTrue(bool(policy.get("recover_input_vat_on_fees", False)))

    def test_load_policy_overrides_values(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "policy.json"
            path.write_text(
                json.dumps(
                    {
                        "vat_registered": False,
                        "recover_input_vat_on_cogs": False,
                        "recover_input_vat_on_fees": True,
                        "formula_version": "custom",
                    }
                ),
                encoding="utf-8",
            )
            policy = h_floor_policy.load_h_floor_vat_policy(path=path)
            self.assertFalse(bool(policy.get("vat_registered", True)))
            self.assertFalse(bool(policy.get("recover_input_vat_on_cogs", True)))
            self.assertTrue(bool(policy.get("recover_input_vat_on_fees", False)))
            self.assertEqual(str(policy.get("formula_version", "")), "custom")

    def test_cost_math_vat_registered_recover_input_vat(self) -> None:
        policy = {
            "vat_registered": True,
            "recover_input_vat_on_cogs": True,
            "recover_input_vat_on_fees": True,
        }
        self.assertEqual(h_floor_policy.cogs_cost_from_exvat(5.35, 0.2, policy), 5.35)
        self.assertEqual(h_floor_policy.fee_cost_from_exvat(3.05, 0.2, policy), 3.05)
        self.assertAlmostEqual(h_floor_policy.gross_from_exvat(10.0, 0.2, policy), 12.0, places=6)

    def test_cost_math_when_input_vat_not_recoverable(self) -> None:
        policy = {
            "vat_registered": True,
            "recover_input_vat_on_cogs": False,
            "recover_input_vat_on_fees": False,
        }
        self.assertAlmostEqual(h_floor_policy.cogs_cost_from_exvat(5.0, 0.2, policy), 6.0, places=6)
        self.assertAlmostEqual(h_floor_policy.fee_cost_from_exvat(2.5, 0.2, policy), 3.0, places=6)


if __name__ == "__main__":
    unittest.main()
