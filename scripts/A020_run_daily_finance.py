"""
Run the daily finance and reporting steps once per day.

This is the heavy part of the old B cycle, moved here to keep the B loop fast.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"

RUN_ORDER = [
    "B003_run_financial_events_level3.py",
    "B008_apply_refunds_to_tokens.py",
    "B009_apply_stock_adjustments_to_tokens.py",
    "B012_build_token_events_append.py",
    "B010_build_token_ops_outputs.py",
    "D018_build_token_batch_report.py",
    "B013_build_token_weekly_drift.py",
    "B014_build_token_daily_checklist.py",
    "B021_build_token_proof_pack.py",
    "B005_run_financial_transactions_v2024.py",
    "D012_build_fee_vat_ledger.py",
    "D016_build_fee_detail_ledger_api.py",
    "D013_build_vat_report.py",
    "D017_audit_daily_guardrails.py",
    "D003_build_transaction_ledger.py",
    "D004_allocate_transaction_expenses.py",
    "D005_build_unallocated_expenses_ledger.py",
    "D006_build_transaction_expense_coverage.py",
    "B006_build_fx_ledgers.py",
    "D001_build_pnl_daily.py",
]


def main() -> int:
    for name in RUN_ORDER:
        path = SCRIPTS / name
        if not path.exists():
            print(f"[A_daily_finance] missing: {path}")
            return 1
    for name in RUN_ORDER:
        path = SCRIPTS / name
        print(f"[A_daily_finance] running: {name}")
        result = subprocess.run([sys.executable, str(path)])
        if result.returncode != 0:
            print(f"[A_daily_finance] failed: {name} (code {result.returncode})")
            return result.returncode
    print("[A_daily_finance] done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
