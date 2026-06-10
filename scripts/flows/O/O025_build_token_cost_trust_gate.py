from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

BOOT_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BOOT_ROOT) not in sys.path:
    sys.path.insert(0, str(BOOT_ROOT))

from scripts.flows.O._contract_io import write_o_contract_df
from scripts.flows.O._paths import ensure_o_directories


B_FALLBACK_AUDIT_REL = Path("out") / "systems" / "B" / "refunds" / "b_fallback_token_cost_audit.csv"
B_FALLBACK_RECON_REL = Path("out") / "systems" / "B" / "refunds" / "b_fallback_cost_proof_reconciliation.csv"
SKU_PERFORMANCE_REL = Path("out") / "sku_performance_summary.csv"
TOKEN_LEDGER_REL = Path("out") / "token_ledger_live.csv"
WEAK_B_LABELS = {"weak_fallback_cost", "not_yet_proven"}
WEAK_B_STATES = {"fallback_cost_weak_latest_token", "fallback_cost_unproved"}
WEAK_RECON_RULES = {"requires_batch_link_proof", "requires_luke_business_decision"}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _text(value: object) -> str:
    return str(value or "").strip()


def _norm_sku(value: object) -> str:
    return _text(value).upper()


def _num(value: object) -> float:
    raw = _text(value).replace(",", "")
    if not raw:
        return 0.0
    try:
        return float(raw)
    except ValueError:
        return 0.0


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _weak_b_skus(audit_df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    if audit_df.empty or "seller_sku" not in audit_df.columns:
        return {}
    work = audit_df.copy()
    for column in ("manager_label", "cost_proof_state", "roi_or_restock_use_allowed"):
        if column not in work.columns:
            work[column] = ""
    work["sku_norm"] = work["seller_sku"].map(_norm_sku)
    weak = work[
        work["manager_label"].map(lambda value: _text(value).lower()).isin(WEAK_B_LABELS)
        | work["cost_proof_state"].map(lambda value: _text(value).lower()).isin(WEAK_B_STATES)
        | work["roi_or_restock_use_allowed"].map(_text).eq("0")
    ].copy()
    return {sku: group.copy() for sku, group in weak.groupby("sku_norm") if sku}


def _reconciliation_blocked_skus(recon_df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    if recon_df.empty or "seller_sku" not in recon_df.columns:
        return {}
    work = recon_df.copy()
    for column in ("reconciliation_rule", "clean_h_o_trust_allowed"):
        if column not in work.columns:
            work[column] = ""
    work["sku_norm"] = work["seller_sku"].map(_norm_sku)
    blocked = work[
        work["reconciliation_rule"].map(lambda value: _text(value).lower()).isin(WEAK_RECON_RULES)
        | work["clean_h_o_trust_allowed"].map(_text).ne("1")
    ].copy()
    return {sku: group.copy() for sku, group in blocked.groupby("sku_norm") if sku}


def _token_ledger_counts(ledger_df: pd.DataFrame) -> dict[str, int]:
    if ledger_df.empty or "seller_sku" not in ledger_df.columns:
        return {}
    work = ledger_df.copy()
    if "source" not in work.columns:
        work["source"] = ""
    if "notes" not in work.columns:
        work["notes"] = ""
    if "token_id" not in work.columns:
        work["token_id"] = ""
    work["sku_norm"] = work["seller_sku"].map(_norm_sku)
    work["is_fallback"] = (
        work["source"].map(_text).eq("stock_adjustment_fallback")
        | work["notes"].astype(str).str.contains("adjustment_fallback_create:", na=False)
        | work["token_id"].astype(str).str.startswith("ADJ-")
    )
    counts = work[work["is_fallback"]].groupby("sku_norm").size().to_dict()
    return {str(key): int(value) for key, value in counts.items() if str(key)}


def build_token_cost_trust_gate(
    root: Path | str | None = None,
    *,
    proof_utc: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    root_path = Path(root) if root is not None else Path(__file__).resolve().parents[3]
    ensure_o_directories(root=root_path)
    observed = proof_utc or _utc_now_iso()

    performance_path = root_path / SKU_PERFORMANCE_REL
    audit_path = root_path / B_FALLBACK_AUDIT_REL
    recon_path = root_path / B_FALLBACK_RECON_REL
    ledger_path = root_path / TOKEN_LEDGER_REL
    performance_df = _read_csv(performance_path)
    audit_df = _read_csv(audit_path)
    recon_df = _read_csv(recon_path)
    ledger_df = _read_csv(ledger_path)
    weak_by_sku = _weak_b_skus(audit_df)
    recon_blocked_by_sku = _reconciliation_blocked_skus(recon_df)
    fallback_counts = _token_ledger_counts(ledger_df)

    rows: list[dict[str, str]] = []
    if not performance_df.empty:
        for column in ("sku", "seller_sku", "current_token_cost_gbp", "asof_date"):
            if column not in performance_df.columns:
                performance_df[column] = ""
        for _, perf in performance_df.iterrows():
            sku = _text(perf.get("sku", "")) or _text(perf.get("seller_sku", ""))
            sku_norm = _norm_sku(sku)
            token_cost = _text(perf.get("current_token_cost_gbp", ""))
            blockers: list[str] = []
            if _num(token_cost) <= 0:
                state = "missing_token_cost"
                basis = "sku_performance_summary_missing_or_zero_token_cost"
                blockers.append("missing_token_cost")
            elif not audit_path.exists() or audit_df.empty:
                state = "not_verified"
                basis = "b_fallback_token_cost_audit_missing"
                blockers.append("missing_b_fallback_token_cost_audit")
            elif recon_path.exists() and sku_norm in recon_blocked_by_sku:
                state = "weak_fallback_cost"
                blocked_rows = recon_blocked_by_sku[sku_norm]
                basis = "b_fallback_cost_reconciliation_requires_batch_link_proof"
                blockers.append("fallback_cost_batch_link_proof_needed")
                blockers.extend(
                    sorted(
                        {
                            _text(value).lower()
                            for value in blocked_rows.get("reconciliation_rule", pd.Series(dtype=str)).tolist()
                            if _text(value)
                        }
                    )
                )
            elif sku_norm in weak_by_sku:
                state = "weak_fallback_cost"
                weak_rows = weak_by_sku[sku_norm]
                basis = "b_fallback_token_cost_audit_blocks_roi_or_restock"
                blockers.append("weak_fallback_token_cost")
                blockers.extend(
                    sorted(
                        {
                            _text(value).lower()
                            for value in weak_rows.get("cost_proof_state", pd.Series(dtype=str)).tolist()
                            if _text(value)
                        }
                    )
                )
            else:
                state = "trusted"
                basis = "no_b_fallback_cost_risk_for_sku"

            rows.append(
                {
                    "proof_utc": observed,
                    "seller_sku": sku,
                    "current_token_cost_gbp": token_cost,
                    "token_cost_trust_state": state,
                    "token_cost_trust_basis": basis,
                    "token_cost_trust_source": str(audit_path if audit_path.exists() else performance_path),
                    "token_cost_trust_blockers": "|".join(dict.fromkeys(blockers)),
                    "b_fallback_audit_rows": str(len(audit_df.index)),
                    "b_fallback_reconciliation_rows": str(len(recon_df.index)),
                    "b_reconciliation_blocked_rows_for_sku": str(len(recon_blocked_by_sku.get(sku_norm, pd.DataFrame()).index)),
                    "b_weak_fallback_rows_for_sku": str(len(weak_by_sku.get(sku_norm, pd.DataFrame()).index)),
                    "token_ledger_fallback_rows_for_sku": str(fallback_counts.get(sku_norm, 0)),
                    "safe_for_clean_buy": "1" if state == "trusted" else "0",
                    "safe_for_po": "1" if state == "trusted" else "0",
                    "source_path": str(performance_path),
                    "notes": "Read-only token-cost trust gate. It does not correct tokens or approve buying.",
                }
            )

    live_df = write_o_contract_df(root_path, "restock_token_cost_trust_gate_live", pd.DataFrame(rows))
    not_trusted_rows = int((live_df["token_cost_trust_state"] != "trusted").sum()) if not live_df.empty else 0
    weak_rows = int((live_df["token_cost_trust_state"] == "weak_fallback_cost").sum()) if not live_df.empty else 0
    missing_cost_rows = int((live_df["token_cost_trust_state"] == "missing_token_cost").sum()) if not live_df.empty else 0
    not_verified_rows = int((live_df["token_cost_trust_state"] == "not_verified").sum()) if not live_df.empty else 0
    health_status = "ok" if not_trusted_rows == 0 else "warn"
    if not performance_path.exists():
        health_status = "fail"

    health_rows = [
        {
            "proof_utc": observed,
            "check": "token_cost_trust_gate_rows",
            "status": health_status,
            "value": (
                f"rows={len(live_df.index)};not_trusted={not_trusted_rows};"
                f"weak_fallback={weak_rows};missing_token_cost={missing_cost_rows};not_verified={not_verified_rows}"
            ),
            "notes": "Token cost must be trusted before O can call expected profit clean.",
            "source_path": f"{performance_path};{audit_path};{recon_path}",
        },
        {
            "proof_utc": observed,
            "check": "buy_safety",
            "status": "ok",
            "value": f"safe_for_clean_buy_rows={int((live_df['safe_for_clean_buy'] == '1').sum()) if not live_df.empty else 0};safe_for_po_rows={int((live_df['safe_for_po'] == '1').sum()) if not live_df.empty else 0}",
            "notes": "The trust gate only reports whether token cost may be used by O; it does not buy, correct tokens, or create PO rows.",
            "source_path": str(root_path / "out" / "systems" / "O" / "live" / "restock_token_cost_trust_gate_live.csv"),
        },
    ]
    health_df = write_o_contract_df(root_path, "restock_token_cost_trust_gate_health", pd.DataFrame(health_rows))
    return live_df, health_df


def main() -> int:
    live_df, health_df = build_token_cost_trust_gate()
    print(f"token_cost_trust_rows={len(live_df.index)}")
    if not health_df.empty:
        print(str(health_df.iloc[0]["value"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
