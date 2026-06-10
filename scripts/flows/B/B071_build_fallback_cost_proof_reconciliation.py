from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.core.safe_file_writes import safe_to_csv


OUT = Path("out")
B070_AUDIT = OUT / "systems" / "B" / "refunds" / "b_fallback_token_cost_audit.csv"
SHEET_MISMATCH = OUT / "systems" / "M" / "b_token_sheet_comparison" / "fallback_cost_mismatch_tokens.csv"
H_NEXT_AVAILABLE = OUT / "systems" / "M" / "b_token_sheet_comparison" / "h_next_available_cost_mismatch.csv"
RECON_OUT = OUT / "systems" / "B" / "refunds" / "b_fallback_cost_proof_reconciliation.csv"
SUMMARY_OUT = OUT / "systems" / "B" / "refunds" / "b_fallback_cost_proof_reconciliation_summary.csv"

RECON_COLUMNS = [
    "token_id",
    "seller_sku",
    "token_status",
    "b070_cost_proof_state",
    "b070_manager_label",
    "b070_cost_per_unit",
    "sheet_issue",
    "sheet_expected_prior_cost",
    "sheet_expected_row",
    "sheet_expected_intake_date",
    "latest_sheet_cost_any_date",
    "reconciliation_rule",
    "clean_h_o_trust_allowed",
    "manager_expectation",
    "bounded_worker_task",
    "retest_rule",
    "preview_live_write_allowed",
    "roi_or_restock_use_allowed",
    "protected_before_apply",
]
SUMMARY_COLUMNS = ["metric", "value"]


def _utc_now_text() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str).fillna("")


def _text(value: object) -> str:
    return str(value or "").strip()


def _classify(row: pd.Series) -> tuple[str, str, str, str, str]:
    issue = _text(row.get("issue", ""))
    b070_state = _text(row.get("cost_proof_state", ""))
    b070_label = _text(row.get("manager_label", ""))
    if issue == "fallback_cost_differs_from_latest_prior_sheet_cost":
        return (
            "requires_batch_link_proof",
            "0",
            "B070 can trace the cost to an older source token, but the Sheet comparison says a newer prior Sheet cost should be used before H/O trust it.",
            "Keep H/O clean trust blocked for this SKU until a batch-linked proof or protected correction decision exists.",
            "1",
        )
    if issue in {"no_sheet_cost_for_sku", "no_prior_sheet_cost_for_fallback_date"}:
        return (
            "requires_batch_link_proof",
            "0",
            "There is not enough Sheet cost history to treat this fallback token cost as clean business truth.",
            "Keep H/O clean trust blocked for this SKU until stronger source cost proof exists.",
            "1",
        )
    if b070_state == "fallback_cost_receipt_proved" or b070_label == "api_or_receipt_proved":
        return (
            "source_token_cost_is_valid",
            "1",
            "The fallback cost directly matches local receipt proof.",
            "No correction task from this reconciliation row.",
            "0",
        )
    if issue == "ok" and b070_label == "source_token_proved":
        return (
            "source_token_cost_is_valid",
            "1",
            "B070 source-token proof agrees with the latest prior Sheet cost comparison.",
            "No correction task from this reconciliation row.",
            "0",
        )
    return (
        "requires_batch_link_proof",
        "0",
        "The fallback cost proof is not strong enough for clean downstream trust.",
        "Keep clean H/O trust blocked until a stronger proof or protected decision exists.",
        "1",
    )


def build_fallback_cost_proof_reconciliation(*, root: Path | str | None = None, observed_utc: str | None = None) -> dict[str, object]:
    root_path = Path(root or ".")
    observed = observed_utc or _utc_now_text()
    audit = _read_csv(root_path / B070_AUDIT)
    sheet = _read_csv(root_path / SHEET_MISMATCH)
    h_next = _read_csv(root_path / H_NEXT_AVAILABLE)
    if audit.empty:
        recon = pd.DataFrame(columns=RECON_COLUMNS)
    else:
        merged = audit.merge(sheet, on=["token_id", "seller_sku"], how="left", suffixes=("", "_sheet")).fillna("")
        rows: list[dict[str, str]] = []
        for _, row in merged.iterrows():
            rule, trust_allowed, expectation, task, protected = _classify(row)
            rows.append(
                {
                    "token_id": _text(row.get("token_id", "")),
                    "seller_sku": _text(row.get("seller_sku", "")),
                    "token_status": _text(row.get("status", "")) or _text(row.get("token_status", "")),
                    "b070_cost_proof_state": _text(row.get("cost_proof_state", "")),
                    "b070_manager_label": _text(row.get("manager_label", "")),
                    "b070_cost_per_unit": _text(row.get("cost_per_unit", "")),
                    "sheet_issue": _text(row.get("issue", "")) or "sheet_comparison_missing",
                    "sheet_expected_prior_cost": _text(row.get("expected_prior_sheet_cost", "")),
                    "sheet_expected_row": _text(row.get("expected_sheet_row", "")),
                    "sheet_expected_intake_date": _text(row.get("expected_sheet_intake_date", "")),
                    "latest_sheet_cost_any_date": _text(row.get("latest_sheet_cost_any_date", "")),
                    "reconciliation_rule": rule,
                    "clean_h_o_trust_allowed": trust_allowed,
                    "manager_expectation": expectation,
                    "bounded_worker_task": task,
                    "retest_rule": "Rerun B071 and B MOT; affected rows clear only when batch-linked proof agrees or a protected correction decision is approved.",
                    "preview_live_write_allowed": "0",
                    "roi_or_restock_use_allowed": "0",
                    "protected_before_apply": protected,
                }
            )
        recon = pd.DataFrame(rows, columns=RECON_COLUMNS).fillna("")

    requires = recon[recon["reconciliation_rule"].eq("requires_batch_link_proof")] if not recon.empty else recon
    valid = recon[recon["reconciliation_rule"].eq("source_token_cost_is_valid")] if not recon.empty else recon
    h_blocked_skus = sorted(
        set(
            h_next.loc[
                h_next.get("issue", pd.Series(dtype=str)).astype(str).str.strip().eq("h_next_available_cost_differs_from_latest_prior_sheet_cost"),
                "seller_sku",
            ].dropna().astype(str).tolist()
        )
    ) if not h_next.empty and "seller_sku" in h_next.columns else []
    summary = pd.DataFrame(
        [
            {"metric": "observed_utc", "value": observed},
            {"metric": "reconciliation_rows", "value": str(len(recon))},
            {"metric": "source_token_cost_is_valid_rows", "value": str(len(valid))},
            {"metric": "requires_batch_link_proof_rows", "value": str(len(requires))},
            {"metric": "blocked_clean_trust_skus", "value": str(len(set(requires["seller_sku"].astype(str))) if not requires.empty else 0)},
            {"metric": "h_next_available_blocked_skus", "value": ";".join(h_blocked_skus)},
            {"metric": "live_write_allowed_rows", "value": "0"},
            {"metric": "roi_or_restock_allowed_rows", "value": "0"},
            {"metric": "protected_before_apply_rows", "value": str(int((recon["protected_before_apply"] == "1").sum()) if not recon.empty else 0)},
        ],
        columns=SUMMARY_COLUMNS,
    )
    return {"reconciliation": recon, "summary": summary}


def write_fallback_cost_proof_reconciliation_outputs(result: dict[str, object], *, root: Path | str | None = None) -> dict[str, Path]:
    root_path = Path(root or ".")
    recon_path = root_path / RECON_OUT
    summary_path = root_path / SUMMARY_OUT
    safe_to_csv(result["reconciliation"], recon_path, index=False)
    safe_to_csv(result["summary"], summary_path, index=False)
    return {"reconciliation": recon_path, "summary": summary_path}


def main() -> None:
    result = build_fallback_cost_proof_reconciliation()
    paths = write_fallback_cost_proof_reconciliation_outputs(result)
    summary = {row["metric"]: row["value"] for _, row in result["summary"].iterrows()}
    print(
        {
            "status": "ok",
            "reconciliation_rows": summary.get("reconciliation_rows", "0"),
            "requires_batch_link_proof_rows": summary.get("requires_batch_link_proof_rows", "0"),
            "reconciliation": str(paths["reconciliation"]),
            "summary": str(paths["summary"]),
        }
    )


if __name__ == "__main__":
    main()
