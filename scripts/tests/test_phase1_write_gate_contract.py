from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
OUT = ROOT / "out"
COMBINED_GLOB = "phase1_observation_combined_*.csv"

SAMPLE_SKUS = [
    "HS-R5IP-7E1C",  # included path
    "6V-EEC1-2S9Z",  # excluded path
    "JB-RGB6-LZOJ",
    "IJ-V0PQ-4CZ4",
    "W3-8FN7-FSP0",
]


def test_evaluate_live_write_gate_standard_phase1_allows_codex_h_when_phase_engine_live_flag_off():
    from scripts.phase1.phase1_write_gate import ALLOWED_REASON, evaluate_live_write_gate

    result = evaluate_live_write_gate(
        writer_mode="CODEX_H",
        phase_engine_enabled=False,
        phase_engine_behavior=False,
        phase_engine_live_writes=False,
        in_cohort=False,
        excluded=False,
    )

    assert result.write_allowed is True
    assert result.reason_codes == [ALLOWED_REASON]


def test_evaluate_live_write_gate_phase_engine_mode_still_requires_cohort_when_enabled():
    from scripts.phase1.phase1_write_gate import evaluate_live_write_gate

    blocked = evaluate_live_write_gate(
        writer_mode="CODEX_H",
        phase_engine_enabled=True,
        phase_engine_behavior=True,
        phase_engine_live_writes=True,
        in_cohort=False,
        excluded=False,
    )
    allowed = evaluate_live_write_gate(
        writer_mode="CODEX_H",
        phase_engine_enabled=True,
        phase_engine_behavior=True,
        phase_engine_live_writes=True,
        in_cohort=True,
        excluded=False,
    )

    assert blocked.write_allowed is False
    assert blocked.reason_codes == ["PHASE_LIVE_WRITE_BLOCKED_NOT_IN_COHORT"]
    assert allowed.write_allowed is True


def _load_reason_codes(value: object) -> list[str]:
    text = str(value or "").strip()
    if text == "":
        return []
    try:
        raw = json.loads(text)
    except Exception:
        return []
    if not isinstance(raw, list):
        return []
    return [str(item or "").strip() for item in raw if str(item or "").strip()]


def _latest_combined_path() -> Path:
    reports_dir = OUT / "analysis_reports"
    files = sorted(reports_dir.glob(COMBINED_GLOB), key=lambda p: p.stat().st_mtime)
    if not files:
        raise FileNotFoundError(f"no files matching {COMBINED_GLOB} under {reports_dir}")
    return files[-1]


def main() -> int:
    from scripts.phase1.phase1_write_gate import live_write_allowed_from_reason_codes

    # Keep contract data fresh before assertion.
    subprocess.run(
        [sys.executable, "scripts/flows/H/H130_build_phase1_observation_sheet.py"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    combined_path = _latest_combined_path()
    df = pd.read_csv(combined_path, dtype=str).fillna("")

    failures: list[str] = []
    checked = 0
    for sku in SAMPLE_SKUS:
        row_df = df.loc[df["sku"].astype(str).str.strip().eq(sku)]
        if row_df.empty:
            failures.append(f"missing sku in combined output: {sku}")
            continue
        row = row_df.iloc[0]
        reason_codes = _load_reason_codes(row.get("execution_reason_codes_json", ""))
        writer_allowed = live_write_allowed_from_reason_codes(
            reason_codes,
            fallback_write_effective=str(row.get("write_effective", "")).strip() == "1",
            fallback_writer_mode=str(row.get("writer_mode", "")).strip(),
        )
        status = str(row.get("automation_status", "")).strip().upper()
        sheet_allows = status == "WRITE"
        checked += 1
        if writer_allowed != sheet_allows:
            failures.append(
                f"sku={sku} writer_allowed={int(writer_allowed)} status={status or 'BLANK'} "
                f"reason_codes={','.join(reason_codes)}"
            )

    if failures:
        print("FAIL phase1_write_gate_contract")
        for item in failures:
            print(item)
        return 1

    print(f"PASS phase1_write_gate_contract checked={checked} file={combined_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
