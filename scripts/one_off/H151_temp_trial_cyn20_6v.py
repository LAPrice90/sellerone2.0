from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
ANALYSIS_REPORTS_DIR = OUT / "analysis_reports"
DEFAULT_SKU = "6V-EEC1-2S9Z"
DEFAULT_UNDERCUT_GBP = Decimal("0.05")
TRIAL_NAME = "temp trial"


@dataclass(frozen=True)
class TempTrialDecision:
    trial_name: str
    generated_utc: str
    source_combined_path: str
    sku: str
    asin: str
    current_price_gbp: str
    competitor_price_gbp: str
    undercut_gbp: str
    raw_target_gbp: str
    floor_gbp: str
    ceiling_gbp: str
    final_target_gbp: str
    action_status: str
    action_reason_codes: str


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def _money(value: Decimal | None) -> str:
    if value is None:
        return ""
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _to_decimal(value: object) -> Decimal | None:
    text = str(value or "").strip()
    if text == "":
        return None
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def _latest_combined_path() -> Path:
    candidates = sorted(ANALYSIS_REPORTS_DIR.glob("phase1_observation_combined_*.csv"))
    if not candidates:
        raise FileNotFoundError(f"no combined report files found in {ANALYSIS_REPORTS_DIR}")
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _load_row_by_sku(combined_path: Path, sku: str) -> dict[str, str]:
    with combined_path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames:
            raise ValueError(f"combined report has no headers: {combined_path}")
        for row in reader:
            row_sku = str(row.get("sku", "")).strip()
            if row_sku == sku:
                return {k: str(v or "").strip() for k, v in row.items()}
    raise ValueError(f"sku not found in combined report: sku={sku} path={combined_path}")


def build_temp_trial_decision(
    *,
    row: dict[str, str],
    combined_path: Path,
    undercut_gbp: Decimal,
) -> TempTrialDecision:
    sku = str(row.get("sku", "")).strip()
    asin = str(row.get("asin", "")).strip()
    current = _to_decimal(row.get("current_price_gbp", ""))
    competitor = _to_decimal(row.get("next_comp_gbp", ""))
    floor = _to_decimal(row.get("floor_gbp", ""))
    ceiling = _to_decimal(row.get("ceiling_gbp", ""))

    reasons: list[str] = []
    action_status = "READY"
    raw_target: Decimal | None = None
    final_target: Decimal | None = None

    if competitor is None:
        action_status = "BLOCKED"
        reasons.append("COMPETITOR_MISSING")
    else:
        raw_target = competitor - undercut_gbp
        final_target = raw_target
        if floor is not None and final_target < floor:
            final_target = floor
            reasons.append("FLOOR_CLAMPED")
        if ceiling is not None and final_target > ceiling:
            final_target = ceiling
            reasons.append("CEILING_CLAMPED")
        if current is not None and final_target == current:
            action_status = "NO_CHANGE"
            reasons.append("NO_CHANGE_REQUIRED")
        elif not reasons:
            reasons.append("UNDERCUT_APPLIED")

    if action_status == "READY" and final_target is None:
        action_status = "BLOCKED"
        reasons.append("FINAL_TARGET_UNRESOLVED")

    return TempTrialDecision(
        trial_name=TRIAL_NAME,
        generated_utc=_utc_now_iso(),
        source_combined_path=str(combined_path),
        sku=sku,
        asin=asin,
        current_price_gbp=_money(current),
        competitor_price_gbp=_money(competitor),
        undercut_gbp=_money(undercut_gbp),
        raw_target_gbp=_money(raw_target),
        floor_gbp=_money(floor),
        ceiling_gbp=_money(ceiling),
        final_target_gbp=_money(final_target),
        action_status=action_status,
        action_reason_codes="|".join(reasons),
    )


def _write_outputs(decision: TempTrialDecision) -> tuple[Path, Path]:
    ANALYSIS_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    json_path = ANALYSIS_REPORTS_DIR / f"temp_trial_6v_cyn20_{timestamp}.json"
    latest_json_path = ANALYSIS_REPORTS_DIR / "temp_trial_6v_cyn20_latest.json"
    csv_path = ANALYSIS_REPORTS_DIR / f"temp_trial_6v_cyn20_{timestamp}.csv"
    latest_csv_path = ANALYSIS_REPORTS_DIR / "temp_trial_6v_cyn20_latest.csv"

    payload = asdict(decision)
    json_blob = json.dumps(payload, ensure_ascii=True, indent=2)
    json_path.write_text(json_blob, encoding="utf-8")
    latest_json_path.write_text(json_blob, encoding="utf-8")

    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(payload.keys()))
        writer.writeheader()
        writer.writerow(payload)
    with latest_csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(payload.keys()))
        writer.writeheader()
        writer.writerow(payload)

    return latest_json_path, latest_csv_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="One-off temp trial for CYN20 6V: target competitor minus 0.05 GBP."
    )
    parser.add_argument("--sku", default=DEFAULT_SKU, help="SKU to evaluate (default CYN20 6V)")
    parser.add_argument("--combined-path", default="", help="Optional explicit combined report path")
    parser.add_argument(
        "--undercut-gbp",
        default=str(DEFAULT_UNDERCUT_GBP),
        help="GBP amount under competitor (default 0.05)",
    )
    args = parser.parse_args()

    sku = str(args.sku or "").strip() or DEFAULT_SKU
    undercut = _to_decimal(args.undercut_gbp)
    if undercut is None or undercut < Decimal("0"):
        raise ValueError(f"invalid --undercut-gbp: {args.undercut_gbp}")

    if str(args.combined_path or "").strip():
        combined_path = Path(args.combined_path).expanduser()
        if not combined_path.is_absolute():
            combined_path = ROOT / combined_path
    else:
        combined_path = _latest_combined_path()

    if not combined_path.exists():
        raise FileNotFoundError(f"combined report missing: {combined_path}")

    row = _load_row_by_sku(combined_path, sku)
    decision = build_temp_trial_decision(
        row=row,
        combined_path=combined_path,
        undercut_gbp=undercut,
    )
    latest_json_path, latest_csv_path = _write_outputs(decision)

    print(f"temp_trial_name={decision.trial_name}")
    print(f"temp_trial_sku={decision.sku}")
    print(f"temp_trial_status={decision.action_status}")
    print(f"temp_trial_current_gbp={decision.current_price_gbp}")
    print(f"temp_trial_competitor_gbp={decision.competitor_price_gbp}")
    print(f"temp_trial_raw_target_gbp={decision.raw_target_gbp}")
    print(f"temp_trial_final_target_gbp={decision.final_target_gbp}")
    print(f"temp_trial_reason_codes={decision.action_reason_codes}")
    print(f"temp_trial_latest_json={latest_json_path}")
    print(f"temp_trial_latest_csv={latest_csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

