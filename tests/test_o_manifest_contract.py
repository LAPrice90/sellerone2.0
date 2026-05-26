from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.cycles import run_O_cycle as runner_mod


def test_o_manifest_path_and_core_fields(tmp_path: Path) -> None:
    required_rel = "out/systems/O/live/manifest_contract_smoke.csv"

    def _smoke_step(root: Path, mode: str) -> None:
        target = root / required_rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("ok\n", encoding="utf-8")

    custom_plan = [
        runner_mod.OStepSpec(
            name="manifest_smoke_step",
            script_or_function="manifest_smoke.py",
            runner=_smoke_step,
            required_outputs=(required_rel,),
        )
    ]

    run_id = "O_TEST_MANIFEST_CONTRACT"
    rc, manifest, manifest_path = runner_mod.run_o_cycle(
        root=tmp_path,
        mode=runner_mod.LIVE_SAFE_MODE,
        verify_outputs=True,
        run_id=run_id,
        step_plan_override=custom_plan,
    )

    assert rc == 0
    assert manifest_path.exists()
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert payload["run_id"] == run_id
    assert payload["cycle"] == "O"
    assert payload["final_state"] == "completed"
    assert payload["mode"] == runner_mod.LIVE_SAFE_MODE
    assert payload["test_cost_feeder_enabled"] is False
    assert payload["verify_outputs"] is True
    assert payload["configured_step_count"] == 1
    assert payload["recorded_step_count"] == 1
    assert payload["verified_step_count"] == 1
    assert payload["health_summary"]["status"] == "not_applicable"

    step = payload["steps"][0]
    assert step["name"] == "manifest_smoke_step"
    assert step["script_or_function"] == "manifest_smoke.py"
    assert step["rc"] == 0
    assert step["outputs_verified"] is True
    assert step["step_status"] == "completed"
    assert required_rel in step["required_outputs"]
    assert required_rel in step["fresh_outputs"]
    assert step["missing_outputs"] == []

    # Path contract: out/manifests/O/<YYYY-MM-DD>/<run_id>.json
    expected_day = datetime.fromisoformat(payload["start_time"].replace("Z", "+00:00")).astimezone(timezone.utc).strftime("%Y-%m-%d")
    assert manifest_path.as_posix().endswith(f"/out/manifests/O/{expected_day}/{run_id}.json")
