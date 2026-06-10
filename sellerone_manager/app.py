from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .b_marketplace_coverage import build_b_marketplace_coverage_report, write_b_marketplace_coverage_outputs
from .b_order_promotion import (
    apply_b_order_promotion,
    build_b_order_promotion_plan,
    write_b_order_promotion_outputs,
)
from .b_order_recovery import build_b_order_recovery_plan, write_b_order_recovery_outputs
from .b_order_recovery_scanner import run_b_order_recovery_scan
from .b_stock_receipt_intake_preview import (
    build_b_stock_receipt_intake_preview,
    write_b_stock_receipt_intake_preview_outputs,
)
from .ai_usage_report import format_ai_usage_report_status, write_ai_usage_report
from .automation_rebuild_plan import format_automation_rebuild_plan_status, write_automation_rebuild_plan
from .current_state import build_and_write_current_state, format_what_next
from .current_state_markdown import format_current_state_markdown_status, write_current_state_markdown
from .current_work_markdown import format_current_work_markdown_status, write_current_work_markdown
from .custodian_dry_run_manifest import (
    format_custodian_dry_run_manifest_status,
    write_custodian_dry_run_manifest,
)
from .dead_automation_scheduler_review import (
    format_dead_automation_scheduler_review_status,
    write_dead_automation_scheduler_review,
)
from .f_price_list_snapshot import (
    build_f_price_list_snapshot,
    output_headers_are_clean,
    update_codex_repair_task_status,
    write_f_price_list_outputs,
)
from .multi_flow import build_multi_flow_manager, write_multi_flow_outputs
from .hourly_mot import (
    build_all_hourly_mot,
    build_hourly_mot_for_flow,
    build_mot_rollup_result,
    update_mot_work_item_status,
    write_all_hourly_mot_outputs,
    write_hourly_mot_outputs,
)
from .hometime_mode import (
    format_hometime_status,
    preflight_hometime,
    pulse_hometime,
    start_hometime,
    status_hometime,
    stop_hometime,
)
from .manager_briefing import (
    build_and_write_manager_briefing,
    build_manager_briefing,
    format_manager_briefing_status,
)
from .paths import get_manager_paths
from .reporter import write_report
from .sellerboard_bridge import build_sellerboard_bridge_report, write_sellerboard_bridge_outputs
from .sellerboard_email_intake import (
    apply_sellerboard_email_cleanup,
    build_sellerboard_email_intake_report,
    write_sellerboard_email_intake_outputs,
)
from .sellerboard_email_fetch import fetch_latest_sellerboard_email_attachment
from .sellerboard_email_source_probe import build_sellerboard_email_source_proof
from .task_packets import claim_next_approved_task, refresh_approved_task_packets, update_approved_task_status
from .worker_utilisation import format_worker_utilisation_status, write_worker_utilisation_board
from scripts.flows.B.B038_build_refund_return_token_bridge import (
    build_refund_return_token_bridge,
    write_refund_return_token_bridge_outputs,
)
from scripts.flows.B.B039_pull_fba_customer_returns import pull_fba_customer_returns
from scripts.flows.B.B040_audit_refund_return_token_matching import (
    build_matching_audit,
    write_matching_audit_outputs,
)
from scripts.flows.B.B041_build_return_token_repair_preview import (
    build_return_token_repair_preview,
    write_return_token_repair_preview_outputs,
)
from scripts.flows.B.B042_build_refund_token_reproof_preview import (
    build_refund_token_reproof_preview,
    write_refund_token_reproof_preview_outputs,
)
from scripts.flows.B.B043_apply_refund_token_reproof import apply_refund_token_reproof
from scripts.flows.B.B044_apply_return_token_reuse_repair import apply_return_token_reuse_repair
from scripts.flows.B.B045_build_original_return_status_conflict_preview import (
    build_original_return_status_conflict_preview,
    write_original_return_status_conflict_preview_outputs,
)
from scripts.flows.B.B046_apply_original_return_status_repair import apply_original_return_status_repair
from scripts.flows.B.B063_build_original_return_status_apply_preview import (
    build_original_return_status_apply_preview,
    write_original_return_status_apply_preview_outputs,
)
from scripts.flows.B.B064_build_return_cogs_residual_review import (
    build_return_cogs_residual_review,
    write_return_cogs_residual_review_outputs,
)
from scripts.flows.B.B065_build_historical_replacement_stock_proof import (
    build_historical_replacement_stock_proof,
    write_historical_replacement_stock_proof_outputs,
)
from scripts.flows.B.B066_build_no_replacement_shortage_exception_review import (
    build_no_replacement_shortage_exception_review,
    write_no_replacement_shortage_exception_review_outputs,
)
from scripts.flows.B.B067_build_refund_fee_shipping_gap_review import (
    build_refund_fee_shipping_gap_review,
    write_refund_fee_shipping_gap_review_outputs,
)
from scripts.flows.B.B068_build_level3_fee_shipping_api_proof_map import (
    build_level3_fee_shipping_api_proof_map,
    write_level3_fee_shipping_api_proof_map_outputs,
)
from scripts.flows.B.B070_build_fallback_token_cost_audit import (
    build_fallback_token_cost_audit,
    write_fallback_token_cost_audit_outputs,
)
from scripts.flows.B.B071_build_fallback_cost_proof_reconciliation import (
    build_fallback_cost_proof_reconciliation,
    write_fallback_cost_proof_reconciliation_outputs,
)
from scripts.flows.B.B072_build_b008_token_ledger_gap_review import (
    build_b008_token_ledger_gap_review,
    write_b008_token_ledger_gap_review_outputs,
)
from scripts.flows.B.B047_build_token_shortage_repair_preview import (
    build_token_shortage_repair_preview,
    write_token_shortage_repair_preview_outputs,
)
from scripts.flows.B.B048_apply_token_shortage_repair import apply_token_shortage_repair
from scripts.flows.B.B049_build_legacy_baseline_gap_preview import (
    build_legacy_baseline_gap_preview,
    write_legacy_baseline_gap_preview_outputs,
)
from scripts.flows.B.B050_apply_legacy_baseline_gap_repair import apply_legacy_baseline_gap_repair
from scripts.flows.B.B051_build_refund_return_warning_workpack import (
    build_refund_return_warning_workpack,
    write_refund_return_warning_workpack_outputs,
)
from scripts.flows.B.B052_build_amazon_return_coverage_audit import (
    build_amazon_return_coverage_audit,
    write_amazon_return_coverage_audit_outputs,
)
from scripts.flows.B.B053_build_original_allocation_gap_audit import (
    build_original_allocation_gap_audit,
    write_original_allocation_gap_audit_outputs,
)
from scripts.flows.B.B054_build_original_order_recovery_proof import (
    build_original_order_recovery_proof,
    write_original_order_recovery_proof_outputs,
)
from scripts.flows.B.B055_fetch_original_orders_to_quarantine import (
    build_original_order_fetch_to_quarantine,
    write_original_order_fetch_outputs,
)
from scripts.flows.B.B056_build_original_sale_allocation_repair_preview import (
    build_original_sale_allocation_repair_preview,
    write_original_sale_allocation_repair_preview_outputs,
)
from scripts.flows.B.B057_apply_original_sale_allocation_repair import apply_original_sale_allocation_repair
from scripts.flows.B.B058_build_disposition_conflict_preview import (
    build_disposition_conflict_preview,
    write_disposition_conflict_preview_outputs,
)
from scripts.flows.B.B059_build_disposition_conflict_decision_preview import (
    build_disposition_conflict_decision_preview,
    write_disposition_conflict_decision_preview_outputs,
)
from scripts.flows.B.B060_build_disposition_correction_impact_preview import (
    build_disposition_correction_impact_preview,
    write_disposition_correction_impact_preview_outputs,
)
from scripts.flows.B.B061_build_disposition_correction_apply_preview import (
    build_disposition_correction_apply_preview,
    write_disposition_correction_apply_preview_outputs,
)
from scripts.flows.B.B062_apply_disposition_correction_swap import apply_disposition_correction_swap
from scripts.flows.B.B069_apply_disposition_cogs_correction import apply_disposition_cogs_correction


def run_manager(
    *,
    root: Path | str | None = None,
    flow: str = "F_price_list_manager",
    read_only: bool = True,
    write_report_flag: bool = True,
    observed_utc: str | None = None,
) -> dict[str, object]:
    if not read_only:
        raise ValueError("SellerOne manager v1 is read-only only")
    if flow not in {"F_price_list_manager", "all"}:
        raise ValueError(f"unsupported flow for manager v1: {flow}")

    paths = get_manager_paths(root)
    output_paths: dict[str, Path] = {}
    status = "ok"

    f_result = build_f_price_list_snapshot(root=paths.root, observed_utc=observed_utc, module_id="F_price_list_manager")
    output_paths.update(write_f_price_list_outputs(f_result, paths.output_dir))
    if write_report_flag:
        report_path = paths.output_dir / "latest_f_price_list_manager_report.md"
        write_report(report_path, f_result)
        output_paths["report"] = report_path
    if f_result["snapshot_rows"][0]["status"] in {"fail", "blocked", "needs_user"}:
        status = f_result["snapshot_rows"][0]["status"]

    if flow == "all":
        multi_result = build_multi_flow_manager(root=paths.root, observed_utc=observed_utc)
        output_paths.update(write_multi_flow_outputs(multi_result, paths.output_dir))
        if any(row.get("status") == "blocked" for row in multi_result["flow_rows"]):
            status = "blocked"
        elif status == "ok" and any(row.get("status") in {"warn", "not_checked"} for row in multi_result["flow_rows"]):
            status = "warn"

    header_errors = output_headers_are_clean([path for path in output_paths.values() if path.suffix == ".csv"])
    summary = {
        "status": status,
        "manager_execution_errors": 0,
        "header_errors": header_errors,
        "outputs": {name: str(path) for name, path in output_paths.items()},
    }
    if header_errors:
        summary["status"] = "fail"
        summary["manager_execution_errors"] = len(header_errors)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only SellerOne manager control plane")
    parser.add_argument("--flow", default="F_price_list_manager")
    parser.add_argument("--root", default=None)
    parser.add_argument("--read-only", action="store_true", default=True)
    parser.add_argument("--write-report", action="store_true", default=False)
    parser.add_argument("--observed-utc", default=None)
    parser.add_argument("--task-status", default=None, help="Codex-only repair task id to update")
    parser.add_argument("--status", default=None, help="New repair task status")
    parser.add_argument("--note", default="", help="Short status change note")
    parser.add_argument("--actor", default="Codex", help="Status change actor")
    parser.add_argument("--what-next", action="store_true", help="Print the manager front-door operating state")
    parser.add_argument("--current-state-md", action="store_true", help="Generate the human-readable SellerOne 2.1 current state")
    parser.add_argument("--current-work-md", action="store_true", help="Generate SellerOne 2.1 current tickets and backlog")
    parser.add_argument("--ai-usage-report", action="store_true", help="Generate the SellerOne 2.1 AI usage-pressure report")
    parser.add_argument("--automation-rebuild-plan", action="store_true", help="Generate the SellerOne 2.1 automation rebuild plan")
    parser.add_argument("--custodian-dry-run-manifest", action="store_true", help="Generate the preview-only SellerOne 2.1 cleanup manifest")
    parser.add_argument("--dead-automation-scheduler-review", action="store_true", help="Generate the SellerOne 2.1 dead automation and scheduler review")
    parser.add_argument("--scheduler-snapshot-file", default=None, help="Optional CSV fixture for --dead-automation-scheduler-review")
    parser.add_argument("--hourly-mot", action="store_true", help="Run the no-token independent hourly MOT")
    parser.add_argument("--mot-flow", default="A", help="Flow to check with --hourly-mot")
    parser.add_argument("--mot-task-status", default=None, help="MOT work item id to update")
    parser.add_argument("--refresh-approved-tasks", action="store_true", help="Create or refresh manager-approved task packets")
    parser.add_argument("--claim-approved-task", action="store_true", help="Claim the next manager-approved task packet for Codex")
    parser.add_argument("--approved-task-status", default=None, help="Approved manager task id or unique job_ref to update")
    parser.add_argument("--worker-utilisation-board", action="store_true", help="Generate the worker sign-in/out utilisation board")
    parser.add_argument("--hometime-start", action="store_true", help="Open a Hometime Mode manager session")
    parser.add_argument("--hometime-preflight", action="store_true", help="List known Hometime permission needs before evening work starts")
    parser.add_argument("--hometime-pulse", action="store_true", help="Run one Hometime Mode manager pulse")
    parser.add_argument("--hometime-stop", action="store_true", help="Stop the current Hometime Mode manager session")
    parser.add_argument("--hometime-status", action="store_true", help="Print the current Hometime Mode manager status")
    parser.add_argument("--manager-briefing-build", action="store_true", help="Build the private read-only manager communications briefing")
    parser.add_argument("--manager-briefing-status", action="store_true", help="Print the current manager communications briefing status")
    parser.add_argument(
        "--manager-briefing-publish-github",
        action="store_true",
        help="Prepare the private manager briefing markdown files and GitHub connector publish manifest",
    )
    parser.add_argument("--b-sellerboard-bridge", action="store_true", help="Build the read-only B Sellerboard bridge comparison pack")
    parser.add_argument("--b-sellerboard-email-intake", action="store_true", help="Build the read-only B Sellerboard email attachment intake report")
    parser.add_argument("--b-sellerboard-email-source-proof", action="store_true", help="Build read-only B Sellerboard local Gmail source metadata proof")
    parser.add_argument("--b-sellerboard-email-fetch", action="store_true", help="Copy the latest Sellerboard OrderList Gmail attachment into the B manager intake folder")
    parser.add_argument("--b-sellerboard-email-cleanup", action="store_true", help="Apply the approved local Sellerboard intake cleanup policy")
    parser.add_argument("--dry-run", action="store_true", help="Preview cleanup without deleting files")
    parser.add_argument("--b-marketplace-coverage", action="store_true", help="Build the read-only B marketplace coverage report")
    parser.add_argument("--b-order-recovery-plan", action="store_true", help="Build the read-only B backdate recovery and future cursor proof plan")
    parser.add_argument("--b-order-recovery-scan", action="store_true", help="Run the read-only B recovery scanner into quarantine and cursor proof outputs")
    parser.add_argument("--b-order-promotion-preview", action="store_true", help="Build the protected B order promotion preview")
    parser.add_argument("--b-stock-receipt-intake-preview", action="store_true", help="Build the read-only B stock receipt intake decision preview")
    parser.add_argument("--b-order-promotion-apply", action="store_true", help="Apply API-proved B order promotion after explicit protected approval")
    parser.add_argument("--approve-protected-promotion", action="store_true", help="Confirms Luke approved the protected live B order promotion repair window")
    parser.add_argument("--b-refund-return-token-bridge", action="store_true", help="Build the read-only B refund return token proof bridge")
    parser.add_argument("--b-fba-customer-returns-pull", action="store_true", help="Pull the read-only B FBA customer returns proof report")
    parser.add_argument("--b-return-token-matching-audit", action="store_true", help="Build the read-only B refund return token matching audit")
    parser.add_argument("--b-return-token-repair-preview", action="store_true", help="Build the read-only B return token repair preview")
    parser.add_argument("--b-refund-return-warning-workpack", action="store_true", help="Build the read-only B refund return warning workpack")
    parser.add_argument("--b-amazon-return-coverage-audit", action="store_true", help="Build the read-only B Amazon return coverage audit")
    parser.add_argument("--b-original-allocation-gap-audit", action="store_true", help="Build the read-only B original allocation gap audit")
    parser.add_argument("--b-original-order-recovery-proof", action="store_true", help="Build the read-only B original order recovery proof")
    parser.add_argument("--b-original-order-recovery-fetch-preview", action="store_true", help="Preview B original order API fetch-to-quarantine targets without calling Amazon")
    parser.add_argument("--b-original-order-recovery-fetch-apply", action="store_true", help="Fetch B original orders from Amazon API into quarantine after explicit approval")
    parser.add_argument("--b-original-sale-allocation-repair-preview", action="store_true", help="Build the read-only B original sale allocation repair preview")
    parser.add_argument("--b-original-sale-allocation-repair-apply", action="store_true", help="Apply approved local B original sale allocation repair from the B056 preview")
    parser.add_argument("--b-refund-token-reproof-preview", action="store_true", help="Build the read-only B008 refund token reproof preview")
    parser.add_argument("--b-original-return-status-conflict-preview", action="store_true", help="Build the read-only B original returned-token live-status conflict preview")
    parser.add_argument("--b-original-return-status-apply-preview", action="store_true", help="Build the read-only B original returned-token protected apply preview")
    parser.add_argument("--b-return-cogs-residual-review", action="store_true", help="Build the read-only B return COGS residual safety review")
    parser.add_argument("--b-disposition-conflict-preview", action="store_true", help="Build the read-only B non-sellable return reusable-token conflict preview")
    parser.add_argument("--b-disposition-conflict-decision-preview", action="store_true", help="Build the read-only B non-sellable return correction/exception decision preview")
    parser.add_argument("--b-disposition-correction-impact-preview", action="store_true", help="Build the read-only B downstream correction impact preview")
    parser.add_argument("--b-disposition-correction-apply-preview", action="store_true", help="Build the read-only B protected correction apply preview")
    parser.add_argument("--b-historical-replacement-stock-proof", action="store_true", help="Build the read-only B historical replacement stock proof")
    parser.add_argument("--b-no-replacement-shortage-exception-review", action="store_true", help="Build the read-only B no-replacement shortage/exception review")
    parser.add_argument("--b-refund-fee-shipping-gap-review", action="store_true", help="Build the read-only B refund fee shipping gap review")
    parser.add_argument("--b-level3-fee-shipping-api-proof-map", action="store_true", help="Build the read-only B Level 3 fee shipping API proof map")
    parser.add_argument("--b-fallback-token-cost-audit", action="store_true", help="Build the read-only B fallback token cost audit")
    parser.add_argument("--b-fallback-cost-proof-reconciliation", action="store_true", help="Build the read-only B fallback cost proof reconciliation")
    parser.add_argument("--b-b008-token-ledger-gap-review", action="store_true", help="Build the read-only B008 token-ledger gap review")
    parser.add_argument("--b-disposition-correction-swap-apply", action="store_true", help="Apply approved local B non-sellable return replacement-token swap")
    parser.add_argument("--b-disposition-cogs-correction-apply", action="store_true", help="Apply approved local B non-sellable return COGS correction tokens")
    parser.add_argument("--b-original-return-status-conflict-apply", action="store_true", help="Apply approved local B original returned-token lifecycle status repair")
    parser.add_argument("--b-token-shortage-repair-preview", action="store_true", help="Build the read-only B protected token-shortage repair preview")
    parser.add_argument("--b-token-shortage-repair-apply", action="store_true", help="Apply approved local B protected token-shortage repair")
    parser.add_argument("--b-legacy-baseline-gap-preview", action="store_true", help="Build the read-only B legacy baseline token gap preview")
    parser.add_argument("--b-legacy-baseline-gap-apply", action="store_true", help="Apply approved local B legacy baseline token gap repair")
    parser.add_argument("--b-refund-token-reproof-apply", action="store_true", help="Apply approved local B008 refund token reproof repair")
    parser.add_argument("--approve-protected-b008-repair", action="store_true", help="Confirms Luke approved the protected local B008 refund-token repair window")
    parser.add_argument("--b-return-token-reuse-apply", action="store_true", help="Apply approved local B009 order-aware returned-token reuse repair")
    parser.add_argument("--approve-protected-b009-repair", action="store_true", help="Confirms Luke approved the protected local B009 return-token repair window")
    parser.add_argument("--approve-protected-original-return-status-repair", action="store_true", help="Confirms Luke approved the protected local original returned-token status repair window")
    parser.add_argument("--approve-protected-token-shortage-repair", action="store_true", help="Confirms Luke approved the protected local token-shortage repair window")
    parser.add_argument("--approve-protected-legacy-baseline-repair", action="store_true", help="Confirms Luke approved the protected local legacy baseline repair window")
    parser.add_argument("--approve-protected-original-sale-allocation-repair", action="store_true", help="Confirms Luke approved the protected local B057 original sale allocation repair window")
    parser.add_argument("--approve-protected-disposition-correction-swap", action="store_true", help="Confirms Luke approved the protected local B062 non-sellable return correction swap window")
    parser.add_argument("--approve-protected-disposition-cogs-correction", action="store_true", help="Confirms Luke approved the protected local B069 non-sellable return COGS correction window")
    parser.add_argument("--approve-original-order-quarantine-fetch", action="store_true", help="Confirms Luke approved the API original-order fetch into quarantine only")
    parser.add_argument("--b-maintenance-request-id", default=None, help="Expected B maintenance request id for protected local B repair windows")
    parser.add_argument("--return-report-lookback-days", type=int, default=90, help="Lookback days for --b-fba-customer-returns-pull")
    parser.add_argument("--return-report-lag-hours", type=int, default=24, help="Lag hours for --b-fba-customer-returns-pull")
    parser.add_argument("--return-report-marketplace-ids", default=None, help="Comma-separated marketplace IDs for --b-fba-customer-returns-pull")
    parser.add_argument("--cursor-lookback-hours", type=float, default=48.0, help="Lookback window for B per-marketplace cursor proof")
    parser.add_argument("--max-pages-per-marketplace", type=int, default=1, help="Maximum order pages to read for each B marketplace cursor check")
    parser.add_argument("--orders-api-lag-minutes", type=float, default=5.0, help="Delay the B cursor proof end time so Amazon Orders API can serve the window")
    parser.add_argument("--skip-missing-order-fetch", action="store_true", help="Do not fetch Sellerboard missing order detail into quarantine")
    parser.add_argument("--skip-marketplace-cursor-check", action="store_true", help="Do not build per-marketplace cursor proof")
    parser.add_argument("--sellerboard-file", default=None, help="Sellerboard OrderList CSV to compare against SellerOne")
    parser.add_argument("--window-start", default=None, help="Optional UTC purchase-window start, for example 2026-05-20")
    parser.add_argument("--window-end", default=None, help="Optional UTC purchase-window end date, inclusive when passed as YYYY-MM-DD")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.refresh_approved_tasks:
        paths = get_manager_paths(args.root)
        if (paths.root / "config" / "manager" / "modules").exists():
            run_manager(
                root=args.root,
                flow="all",
                read_only=True,
                write_report_flag=True,
                observed_utc=args.observed_utc,
            )
        result = refresh_approved_task_packets(root=args.root, observed_utc=args.observed_utc)
        print(f"approved_count={result['approved_count']}")
        print(f"blocked_count={result['blocked_count']}")
        print(f"index_path={result['index_path']}")
        return 0

    if args.claim_approved_task:
        row = claim_next_approved_task(root=args.root, observed_utc=args.observed_utc)
        print(f"job_ref={row.get('job_ref', '')}")
        print(f"task_id={row['task_id']}")
        print(f"status={row['status']}")
        print(f"packet_path={row['packet_path']}")
        print(f"authority={row['authority']}")
        return 0

    if args.approved_task_status:
        if not args.status:
            parser.error("--status is required with --approved-task-status")
        row = update_approved_task_status(
            root=args.root,
            task_id=args.approved_task_status,
            status=args.status,
            note=args.note,
            observed_utc=args.observed_utc,
        )
        print(f"job_ref={row.get('job_ref', '')}")
        print(f"task_id={row['task_id']}")
        print(f"status={row['status']}")
        print(f"packet_path={row['packet_path']}")
        return 0

    if args.worker_utilisation_board:
        result = write_worker_utilisation_board(root=args.root, generated_utc=args.observed_utc)
        print(format_worker_utilisation_status(result))
        return 0

    if args.hometime_start or args.hometime_preflight or args.hometime_pulse or args.hometime_stop or args.hometime_status:
        if args.hometime_start:
            result = start_hometime(root=args.root, observed_utc=args.observed_utc, dry_run=args.dry_run)
        elif args.hometime_preflight:
            result = preflight_hometime(root=args.root, observed_utc=args.observed_utc, dry_run=args.dry_run)
        elif args.hometime_pulse:
            result = pulse_hometime(root=args.root, observed_utc=args.observed_utc, dry_run=args.dry_run)
        elif args.hometime_stop:
            result = stop_hometime(root=args.root, observed_utc=args.observed_utc, dry_run=args.dry_run)
        else:
            result = status_hometime(root=args.root, observed_utc=args.observed_utc, dry_run=args.dry_run)
        print(format_hometime_status(result))
        return 0

    if args.manager_briefing_build or args.manager_briefing_publish_github:
        briefing, result = build_and_write_manager_briefing(
            root=args.root,
            observed_utc=args.observed_utc,
            write_github_snapshot=args.manager_briefing_publish_github,
        )
        print(format_manager_briefing_status(briefing, result))
        if args.manager_briefing_publish_github:
            print("github_publish_status=prepared_for_connector")
        return 0

    if args.manager_briefing_status:
        briefing = build_manager_briefing(root=args.root, observed_utc=args.observed_utc)
        print(format_manager_briefing_status(briefing))
        return 0

    if args.current_state_md:
        result = write_current_state_markdown(root=args.root, generated_utc=args.observed_utc)
        print(format_current_state_markdown_status(result))
        return 0

    if args.current_work_md:
        result = write_current_work_markdown(root=args.root, generated_utc=args.observed_utc)
        print(format_current_work_markdown_status(result))
        return 0

    if args.ai_usage_report:
        result = write_ai_usage_report(root=args.root, observed_utc=args.observed_utc)
        print(format_ai_usage_report_status(result))
        return 0

    if args.automation_rebuild_plan:
        result = write_automation_rebuild_plan(root=args.root, generated_utc=args.observed_utc)
        print(format_automation_rebuild_plan_status(result))
        return 0

    if args.custodian_dry_run_manifest:
        result = write_custodian_dry_run_manifest(root=args.root, generated_utc=args.observed_utc)
        print(format_custodian_dry_run_manifest_status(result))
        return 0

    if args.dead_automation_scheduler_review:
        result = write_dead_automation_scheduler_review(
            root=args.root,
            generated_utc=args.observed_utc,
            scheduler_snapshot_path=args.scheduler_snapshot_file,
        )
        print(format_dead_automation_scheduler_review_status(result))
        return 0

    if args.what_next:
        paths = get_manager_paths(args.root)
        if (paths.root / "config" / "manager" / "modules").exists():
            run_manager(
                root=args.root,
                flow="all",
                read_only=True,
                write_report_flag=True,
                observed_utc=args.observed_utc,
            )
        refresh_approved_task_packets(root=args.root, observed_utc=args.observed_utc)
        state, _path = build_and_write_current_state(root=args.root, generated_utc=args.observed_utc)
        print(format_what_next(state))
        return 1 if state.get("manager_execution_errors") else 0

    if args.hourly_mot:
        mot_flow = str(args.mot_flow).upper()
        if mot_flow not in {"A", "B", "E", "H", "F", "O", "ALL"}:
            parser.error("hourly MOT currently supports A, B, E, H, F, O, and all only")
        paths = get_manager_paths(args.root)
        if mot_flow == "ALL":
            results = build_all_hourly_mot(root=paths.root, observed_utc=args.observed_utc)
            output_paths = write_all_hourly_mot_outputs(results, paths.output_dir)
            rollup_rows = []
            for item in results:
                rollup_rows.extend(item.get("rows", []))
            result = build_mot_rollup_result(rollup_rows, observed_utc=args.observed_utc)
        else:
            result = build_hourly_mot_for_flow(mot_flow, root=paths.root, observed_utc=args.observed_utc)
            output_paths = write_hourly_mot_outputs(result, paths.output_dir)
        print(f"status={result['status']}")
        print(f"fail_count={result['fail_count']}")
        print(f"warn_count={result['warn_count']}")
        for name, path in sorted(output_paths.items()):
            print(f"{name}={path}")
        return 0

    if args.b_sellerboard_bridge:
        paths = get_manager_paths(args.root)
        result = build_sellerboard_bridge_report(
            root=paths.root,
            sellerboard_path=args.sellerboard_file,
            observed_utc=args.observed_utc,
            window_start=args.window_start,
            window_end=args.window_end,
        )
        output_paths = write_sellerboard_bridge_outputs(result, paths.output_dir)
        print(f"status={result.status}")
        print(f"source_path={result.source_path}")
        for name, path in sorted(output_paths.items()):
            print(f"{name}={path}")
        return 0

    if args.b_sellerboard_email_intake:
        paths = get_manager_paths(args.root)
        result = build_sellerboard_email_intake_report(
            root=paths.root,
            observed_utc=args.observed_utc,
        )
        output_paths = write_sellerboard_email_intake_outputs(result, paths.output_dir)
        print(f"status={result.status}")
        for name, path in sorted(output_paths.items()):
            print(f"{name}={path}")
        return 0

    if args.b_sellerboard_email_source_proof:
        result = build_sellerboard_email_source_proof(
            root=args.root,
            observed_utc=args.observed_utc,
        )
        print(f"proof_status={result.get('proof_status', '')}")
        print(f"auth_status={result.get('auth_status', '')}")
        print(f"latest_message_seen={1 if result.get('latest_message_seen') else 0}")
        print(f"latest_attachment_filename={result.get('latest_attachment_filename', '')}")
        print(f"source_proof_path={result.get('source_proof_path', '')}")
        return 0

    if args.b_sellerboard_email_fetch:
        result = fetch_latest_sellerboard_email_attachment(
            root=args.root,
            observed_utc=args.observed_utc,
        )
        print(f"status={result.status}")
        print(f"filename={result.filename}")
        print(f"size_bytes={result.size_bytes}")
        print(f"manifest_path={result.manifest_path}")
        return 0

    if args.b_sellerboard_email_cleanup:
        result = apply_sellerboard_email_cleanup(
            root=args.root,
            observed_utc=args.observed_utc,
            dry_run=args.dry_run,
        )
        print(f"deleted_count={result.deleted_count}")
        print(f"deleted_bytes={result.deleted_bytes}")
        print(f"skipped_count={result.skipped_count}")
        print(f"manifest_path={result.manifest_path}")
        return 0

    if args.b_marketplace_coverage:
        paths = get_manager_paths(args.root)
        result = build_b_marketplace_coverage_report(
            root=paths.root,
            observed_utc=args.observed_utc,
        )
        output_paths = write_b_marketplace_coverage_outputs(result, paths.output_dir)
        print(f"status={result.status}")
        for name, path in sorted(output_paths.items()):
            print(f"{name}={path}")
        return 0

    if args.b_order_recovery_plan:
        paths = get_manager_paths(args.root)
        result = build_b_order_recovery_plan(
            root=paths.root,
            observed_utc=args.observed_utc,
        )
        output_paths = write_b_order_recovery_outputs(result, paths.output_dir)
        print(f"status={result.status}")
        for name, path in sorted(output_paths.items()):
            print(f"{name}={path}")
        return 0

    if args.b_stock_receipt_intake_preview:
        paths = get_manager_paths(args.root)
        result = build_b_stock_receipt_intake_preview(
            root=paths.root,
            observed_utc=args.observed_utc,
        )
        output_paths = write_b_stock_receipt_intake_preview_outputs(result, root=paths.root)
        summary = {row["metric"]: row["value"] for row in result.summary_rows}
        print(f"status={summary.get('status', '')}")
        print(f"preview_rows={summary.get('preview_rows', '0')}")
        print(f"protected_decision_rows={summary.get('protected_decision_rows', '0')}")
        print(f"tokens_processor_would_create_total={summary.get('tokens_processor_would_create_total', '0')}")
        print(f"orders_shipment_rows={summary.get('orders_shipment_rows', '0')}")
        print(f"orders_shipment_local_gap_rows={summary.get('orders_shipment_local_gap_rows', '0')}")
        print(f"local_orders_file_stale={summary.get('local_orders_file_stale', '0')}")
        print(f"orders_staged_refresh_rows={summary.get('orders_staged_refresh_rows', '0')}")
        for name, path in sorted(output_paths.items()):
            print(f"{name}={path}")
        return 0

    if args.b_order_recovery_scan:
        result = run_b_order_recovery_scan(
            root=args.root,
            observed_utc=args.observed_utc,
            fetch_missing_orders=not args.skip_missing_order_fetch,
            check_marketplace_cursors=not args.skip_marketplace_cursor_check,
            cursor_lookback_hours=args.cursor_lookback_hours,
            max_pages_per_marketplace=args.max_pages_per_marketplace,
            orders_api_lag_minutes=args.orders_api_lag_minutes,
        )
        print(f"status={result.status}")
        print(f"quarantine_rows_written={result.quarantine_rows_written}")
        print(f"cursor_rows_written={result.cursor_rows_written}")
        print(f"manifest_path={result.manifest_path}")
        return 0

    if args.b_order_promotion_preview:
        paths = get_manager_paths(args.root)
        result = build_b_order_promotion_plan(
            root=paths.root,
            observed_utc=args.observed_utc,
        )
        output_paths = write_b_order_promotion_outputs(result, paths.output_dir)
        print(f"status={result.status}")
        for name, path in sorted(output_paths.items()):
            print(f"{name}={path}")
        return 0

    if args.b_order_promotion_apply:
        result = apply_b_order_promotion(
            root=args.root,
            observed_utc=args.observed_utc,
            approve_protected_promotion=args.approve_protected_promotion,
        )
        paths = get_manager_paths(args.root)
        output_paths = write_b_order_promotion_outputs(result, paths.output_dir)
        print(f"status={result.status}")
        print(f"manifest_status={result.manifest.get('status', '')}")
        for name, path in sorted(output_paths.items()):
            print(f"{name}={path}")
        return 0

    if args.b_refund_return_token_bridge:
        paths = get_manager_paths(args.root)
        result = build_refund_return_token_bridge(root=paths.root, observed_utc=args.observed_utc)
        output_paths = write_refund_return_token_bridge_outputs(result)
        bridge = result["bridge"]
        summary_df = result["summary"]
        warning_rows = "0"
        if not summary_df.empty:
            values = summary_df.loc[summary_df["metric"] == "warning_rows", "value"].tolist()
            warning_rows = values[0] if values else "0"
        print(f"bridge_rows={len(bridge)}")
        print(f"warning_rows={warning_rows}")
        for name, path in sorted(output_paths.items()):
            print(f"{name}={path}")
        return 0

    if args.b_fba_customer_returns_pull:
        result = pull_fba_customer_returns(
            root=args.root,
            marketplace_ids=args.return_report_marketplace_ids,
            lookback_days=args.return_report_lookback_days,
            lag_hours=args.return_report_lag_hours,
        )
        print(f"status={result.status}")
        print(f"rows_raw={result.rows_raw}")
        print(f"rows_normalized={result.rows_normalized}")
        print(f"marketplace_count={len(result.marketplace_ids)}")
        print(f"normalized={result.normalized_path}")
        print(f"summary={result.summary_path}")
        return 0

    if args.b_return_token_matching_audit:
        paths = get_manager_paths(args.root)
        result = build_matching_audit(root=paths.root)
        output_paths = write_matching_audit_outputs(result)
        audit = result["audit"]
        summary_df = result["summary"]
        diagnosis_count = "0"
        if not summary_df.empty:
            values = summary_df.loc[summary_df["metric"] == "diagnosis_count", "value"].tolist()
            diagnosis_count = values[0] if values else "0"
        print(f"audit_rows={len(audit)}")
        print(f"diagnosis_count={diagnosis_count}")
        for name, path in sorted(output_paths.items()):
            print(f"{name}={path}")
        return 0

    if args.b_return_token_repair_preview:
        paths = get_manager_paths(args.root)
        result = build_return_token_repair_preview(root=paths.root)
        output_paths = write_return_token_repair_preview_outputs(result)
        preview = result["preview"]
        summary_df = result["summary"]
        unclassified_rows = "0"
        b009_order_aware_rows = "0"
        if not summary_df.empty:
            values = {row["metric"]: row["value"] for _, row in summary_df.iterrows()}
            unclassified_rows = values.get("unclassified_rows", "0")
            b009_order_aware_rows = values.get("b009_order_aware_rows", "0")
        print(f"preview_rows={len(preview)}")
        print(f"unclassified_rows={unclassified_rows}")
        print(f"b009_order_aware_rows={b009_order_aware_rows}")
        for name, path in sorted(output_paths.items()):
            print(f"{name}={path}")
        return 0

    if args.b_refund_return_warning_workpack:
        paths = get_manager_paths(args.root)
        result = build_refund_return_warning_workpack(root=paths.root, observed_utc=args.observed_utc)
        output_paths = write_refund_return_warning_workpack_outputs(result, root=paths.root)
        workpack = result["workpack"]
        summary_df = result["summary"]
        values = {row["metric"]: row["value"] for _, row in summary_df.iterrows()} if not summary_df.empty else {}
        print(f"status={values.get('status', '')}")
        print(f"preview_rows={values.get('preview_rows', '0')}")
        print(f"workpack_lanes={len(workpack)}")
        print(f"unclassified_rows={values.get('unclassified_rows', '0')}")
        print(f"protected_rows={values.get('protected_rows', '0')}")
        for name, path in sorted(output_paths.items()):
            print(f"{name}={path}")
        return 0 if values.get("status", "") not in {"fail"} else 1

    if args.b_amazon_return_coverage_audit:
        paths = get_manager_paths(args.root)
        result = build_amazon_return_coverage_audit(root=paths.root, observed_utc=args.observed_utc)
        output_paths = write_amazon_return_coverage_audit_outputs(result, root=paths.root)
        audit = result["audit"]
        summary_df = result["summary"]
        values = {row["metric"]: row["value"] for _, row in summary_df.iterrows()} if not summary_df.empty else {}
        print(f"status={values.get('status', '')}")
        print(f"audit_rows={len(audit)}")
        print(f"exact_customer_return_matched_rows={values.get('exact_customer_return_matched_rows', '0')}")
        print(f"stock_adjustment_without_customer_return_rows={values.get('stock_adjustment_without_customer_return_rows', '0')}")
        print(f"unclassified_rows={values.get('unclassified_rows', '0')}")
        for name, path in sorted(output_paths.items()):
            print(f"{name}={path}")
        return 0 if values.get("status", "") not in {"fail"} else 1

    if args.b_fallback_token_cost_audit:
        paths = get_manager_paths(args.root)
        result = build_fallback_token_cost_audit(root=paths.root, observed_utc=args.observed_utc)
        output_paths = write_fallback_token_cost_audit_outputs(result, root=paths.root)
        audit = result["audit"]
        summary_df = result["summary"]
        values = {row["metric"]: row["value"] for _, row in summary_df.iterrows()} if not summary_df.empty else {}
        print(f"fallback_token_rows={len(audit)}")
        print(f"weak_or_unproved_rows={values.get('weak_or_unproved_rows', '0')}")
        for name, path in sorted(output_paths.items()):
            print(f"{name}={path}")
        return 0

    if args.b_fallback_cost_proof_reconciliation:
        paths = get_manager_paths(args.root)
        result = build_fallback_cost_proof_reconciliation(root=paths.root, observed_utc=args.observed_utc)
        output_paths = write_fallback_cost_proof_reconciliation_outputs(result, root=paths.root)
        reconciliation = result["reconciliation"]
        summary_df = result["summary"]
        values = {row["metric"]: row["value"] for _, row in summary_df.iterrows()} if not summary_df.empty else {}
        print(f"reconciliation_rows={len(reconciliation)}")
        print(f"requires_batch_link_proof_rows={values.get('requires_batch_link_proof_rows', '0')}")
        for name, path in sorted(output_paths.items()):
            print(f"{name}={path}")
        return 0

    if args.b_original_allocation_gap_audit:
        paths = get_manager_paths(args.root)
        result = build_original_allocation_gap_audit(root=paths.root, observed_utc=args.observed_utc)
        output_paths = write_original_allocation_gap_audit_outputs(result, root=paths.root)
        audit = result["audit"]
        summary_df = result["summary"]
        values = {row["metric"]: row["value"] for _, row in summary_df.iterrows()} if not summary_df.empty else {}
        print(f"status={values.get('status', '')}")
        print(f"audit_rows={len(audit)}")
        print(f"refund_money_without_original_order_rows={values.get('refund_money_without_original_order_rows', '0')}")
        print(f"order_seen_allocation_missing_rows={values.get('order_seen_allocation_missing_rows', '0')}")
        print(f"unclassified_rows={values.get('unclassified_rows', '0')}")
        for name, path in sorted(output_paths.items()):
            print(f"{name}={path}")
        return 0 if values.get("status", "") not in {"fail"} else 1

    if args.b_original_order_recovery_proof:
        paths = get_manager_paths(args.root)
        result = build_original_order_recovery_proof(root=paths.root, observed_utc=args.observed_utc)
        output_paths = write_original_order_recovery_proof_outputs(result, root=paths.root)
        proof = result["proof"]
        summary_df = result["summary"]
        values = {row["metric"]: row["value"] for _, row in summary_df.iterrows()} if not summary_df.empty else {}
        print(f"status={values.get('status', '')}")
        print(f"proof_rows={len(proof)}")
        print(f"needs_api_original_order_fetch_rows={values.get('needs_api_original_order_fetch_rows', '0')}")
        print(f"api_quarantine_original_order_rows={values.get('api_quarantine_original_order_rows', '0')}")
        print(f"unclassified_rows={values.get('unclassified_rows', '0')}")
        for name, path in sorted(output_paths.items()):
            print(f"{name}={path}")
        return 0 if values.get("status", "") not in {"fail"} else 1

    if args.b_original_order_recovery_fetch_preview or args.b_original_order_recovery_fetch_apply:
        paths = get_manager_paths(args.root)
        apply_fetch = bool(args.b_original_order_recovery_fetch_apply)
        if apply_fetch and not args.approve_original_order_quarantine_fetch:
            parser.error("--approve-original-order-quarantine-fetch is required with --b-original-order-recovery-fetch-apply")
        result = build_original_order_fetch_to_quarantine(
            root=paths.root,
            observed_utc=args.observed_utc,
            apply_fetch=apply_fetch,
        )
        output_paths = write_original_order_fetch_outputs(result, root=paths.root, write_quarantine=apply_fetch)
        values = {row["metric"]: row["value"] for _, row in result.summary.iterrows()} if not result.summary.empty else {}
        print(f"status={values.get('status', '')}")
        print(f"source_rows={values.get('source_rows', '0')}")
        print(f"planned_api_fetch_rows={values.get('planned_api_fetch_rows', '0')}")
        print(f"fetched_api_proved_rows={values.get('fetched_api_proved_rows', '0')}")
        print(f"api_fetch_failed_rows={values.get('api_fetch_failed_rows', '0')}")
        print(f"duplicate_blocked_rows={values.get('duplicate_blocked_rows', '0')}")
        for name, path in sorted(output_paths.items()):
            print(f"{name}={path}")
        return 0 if values.get("status", "") not in {"fail"} else 1

    if args.b_original_sale_allocation_repair_preview:
        paths = get_manager_paths(args.root)
        result = build_original_sale_allocation_repair_preview(root=paths.root, observed_utc=args.observed_utc)
        output_paths = write_original_sale_allocation_repair_preview_outputs(result, root=paths.root)
        preview = result["preview"]
        summary_df = result["summary"]
        values = {row["metric"]: row["value"] for _, row in summary_df.iterrows()} if not summary_df.empty else {}
        print(f"status={values.get('status', '')}")
        print(f"preview_rows={len(preview)}")
        print(f"legacy_baseline_candidate_rows={values.get('legacy_baseline_candidate_rows', '0')}")
        print(f"runtime_adjustment_candidate_rows={values.get('runtime_adjustment_candidate_rows', '0')}")
        print(f"unclassified_rows={values.get('unclassified_rows', '0')}")
        for name, path in sorted(output_paths.items()):
            print(f"{name}={path}")
        return 0 if values.get("status", "") not in {"fail"} else 1

    if args.b_original_sale_allocation_repair_apply:
        result = apply_original_sale_allocation_repair(
            root=args.root,
            approve_protected_original_sale_allocation_repair=args.approve_protected_original_sale_allocation_repair,
            observed_utc=args.observed_utc,
            maintenance_request_id=args.b_maintenance_request_id,
        )
        print(f"status={result.status}")
        print(f"preview_rows={result.preview_rows}")
        print(f"created_token_rows={result.created_token_rows}")
        print(f"allocated_token_rows={result.allocated_token_rows}")
        print(f"cogs_rows={result.cogs_rows}")
        print(f"shortage_rows_removed={result.shortage_rows_removed}")
        print(f"missing_order_rows_removed={result.missing_order_rows_removed}")
        print(f"runtime_adjustment_deferred_rows={result.runtime_adjustment_deferred_rows}")
        print(f"blocked_rows={result.blocked_rows}")
        print(f"snapshot_dir={result.snapshot_dir or ''}")
        print(f"applied={result.applied_path}")
        print(f"manifest={result.manifest_path}")
        return 0 if result.status == "applied" else 1

    if args.b_refund_token_reproof_preview:
        paths = get_manager_paths(args.root)
        result = build_refund_token_reproof_preview(root=paths.root)
        output_paths = write_refund_token_reproof_preview_outputs(result)
        preview = result["preview"]
        summary_df = result["summary"]
        ready_order = "0"
        ready_state = "0"
        unclassified_rows = "0"
        if not summary_df.empty:
            values = {row["metric"]: row["value"] for _, row in summary_df.iterrows()}
            ready_order = values.get("ready_b008_order_sku_reproof_rows", "0")
            ready_state = values.get("ready_b008_state_reproof_rows", "0")
            unclassified_rows = values.get("unclassified_rows", "0")
        print(f"preview_rows={len(preview)}")
        print(f"unclassified_rows={unclassified_rows}")
        print(f"ready_b008_order_sku_reproof_rows={ready_order}")
        print(f"ready_b008_state_reproof_rows={ready_state}")
        for name, path in sorted(output_paths.items()):
            print(f"{name}={path}")
        return 0

    if args.b_b008_token_ledger_gap_review:
        paths = get_manager_paths(args.root)
        result = build_b008_token_ledger_gap_review(root=paths.root)
        output_paths = write_b008_token_ledger_gap_review_outputs(result, root=paths.root)
        review = result["review"]
        summary_df = result["summary"]
        values = {row["metric"]: row["value"] for _, row in summary_df.iterrows()} if not summary_df.empty else {}
        print(f"status={values.get('status', '')}")
        print(f"review_rows={len(review)}")
        print(f"protected_ledger_alignment_rows={values.get('protected_ledger_alignment_rows', '0')}")
        print(f"not_yet_proven_rows={values.get('not_yet_proven_rows', '0')}")
        print(f"unclassified_rows={values.get('unclassified_rows', '0')}")
        for name, path in sorted(output_paths.items()):
            print(f"{name}={path}")
        return 0 if values.get("status", "") != "fail" else 1

    if args.b_original_return_status_conflict_preview:
        paths = get_manager_paths(args.root)
        result = build_original_return_status_conflict_preview(root=paths.root)
        output_paths = write_original_return_status_conflict_preview_outputs(result)
        preview = result["preview"]
        summary_df = result["summary"]
        with_duplicates = "0"
        without_duplicates = "0"
        if not summary_df.empty:
            values = {row["metric"]: row["value"] for _, row in summary_df.iterrows()}
            with_duplicates = values.get("with_reusable_duplicate_rows", "0")
            without_duplicates = values.get("without_reusable_duplicate_rows", "0")
        print(f"preview_rows={len(preview)}")
        print(f"with_reusable_duplicate_rows={with_duplicates}")
        print(f"without_reusable_duplicate_rows={without_duplicates}")
        for name, path in sorted(output_paths.items()):
            print(f"{name}={path}")
        return 0

    if args.b_original_return_status_apply_preview:
        paths = get_manager_paths(args.root)
        result = build_original_return_status_apply_preview(root=paths.root)
        output_paths = write_original_return_status_apply_preview_outputs(result)
        summary_df = result["summary"]
        values = {row["metric"]: row["value"] for _, row in summary_df.iterrows()} if not summary_df.empty else {}
        print(f"status={values.get('status', '')}")
        print(f"preview_rows={values.get('preview_rows', '0')}")
        print(f"ready_apply_rows={values.get('ready_apply_rows', '0')}")
        print(f"blocked_rows={values.get('blocked_rows', '0')}")
        for name, path in sorted(output_paths.items()):
            print(f"{name}={path}")
        return 0 if values.get("status", "") != "fail" else 1

    if args.b_return_cogs_residual_review:
        paths = get_manager_paths(args.root)
        result = build_return_cogs_residual_review(root=paths.root, observed_utc=args.observed_utc)
        output_paths = write_return_cogs_residual_review_outputs(result, root=paths.root)
        summary_df = result["summary"]
        values = {row["metric"]: row["value"] for _, row in summary_df.iterrows()} if not summary_df.empty else {}
        print(f"status={values.get('status', '')}")
        print(f"review_rows={values.get('review_rows', '0')}")
        print(f"blocked_rows={values.get('blocked_rows', '0')}")
        print(f"unsafe_rows={values.get('unsafe_rows', '0')}")
        for name, path in sorted(output_paths.items()):
            print(f"{name}={path}")
        return 0 if values.get("status", "") != "fail" else 1

    if args.b_disposition_conflict_preview:
        paths = get_manager_paths(args.root)
        result = build_disposition_conflict_preview(root=paths.root)
        output_paths = write_disposition_conflict_preview_outputs(result)
        preview = result["preview"]
        summary_df = result["summary"]
        values = {row["metric"]: row["value"] for _, row in summary_df.iterrows()} if not summary_df.empty else {}
        print(f"status={values.get('status', '')}")
        print(f"preview_rows={len(preview)}")
        print(f"with_reusable_token_rows={values.get('with_reusable_token_rows', '0')}")
        print(f"with_return_cogs_rows={values.get('with_return_cogs_rows', '0')}")
        for name, path in sorted(output_paths.items()):
            print(f"{name}={path}")
        return 0 if values.get("status", "") != "fail" else 1

    if args.b_disposition_conflict_decision_preview:
        paths = get_manager_paths(args.root)
        result = build_disposition_conflict_decision_preview(root=paths.root)
        output_paths = write_disposition_conflict_decision_preview_outputs(result)
        preview = result["preview"]
        summary_df = result["summary"]
        values = {row["metric"]: row["value"] for _, row in summary_df.iterrows()} if not summary_df.empty else {}
        print(f"status={values.get('status', '')}")
        print(f"preview_rows={len(preview)}")
        print(f"protected_decision_rows={values.get('protected_decision_rows', '0')}")
        print(f"downstream_allocated_rows={values.get('downstream_allocated_rows', '0')}")
        for name, path in sorted(output_paths.items()):
            print(f"{name}={path}")
        return 0 if values.get("status", "") != "fail" else 1

    if args.b_disposition_correction_impact_preview:
        paths = get_manager_paths(args.root)
        result = build_disposition_correction_impact_preview(root=paths.root)
        output_paths = write_disposition_correction_impact_preview_outputs(result)
        preview = result["preview"]
        summary_df = result["summary"]
        values = {row["metric"]: row["value"] for _, row in summary_df.iterrows()} if not summary_df.empty else {}
        print(f"status={values.get('status', '')}")
        print(f"preview_rows={len(preview)}")
        print(f"protected_decision_rows={values.get('protected_decision_rows', '0')}")
        print(f"downstream_allocated_rows={values.get('downstream_allocated_rows', '0')}")
        print(f"downstream_item_match_rows={values.get('downstream_item_match_rows', '0')}")
        for name, path in sorted(output_paths.items()):
            print(f"{name}={path}")
        return 0 if values.get("status", "") != "fail" else 1

    if args.b_disposition_correction_apply_preview:
        paths = get_manager_paths(args.root)
        result = build_disposition_correction_apply_preview(root=paths.root)
        output_paths = write_disposition_correction_apply_preview_outputs(result)
        preview = result["preview"]
        summary_df = result["summary"]
        values = {row["metric"]: row["value"] for _, row in summary_df.iterrows()} if not summary_df.empty else {}
        print(f"status={values.get('status', '')}")
        print(f"preview_rows={len(preview)}")
        print(f"replacement_swap_preview_ready_rows={values.get('replacement_swap_preview_ready_rows', '0')}")
        print(f"no_replacement_rows={values.get('no_replacement_rows', '0')}")
        for name, path in sorted(output_paths.items()):
            print(f"{name}={path}")
        return 0 if values.get("status", "") != "fail" else 1

    if args.b_historical_replacement_stock_proof:
        paths = get_manager_paths(args.root)
        result = build_historical_replacement_stock_proof(root=paths.root, observed_utc=args.observed_utc)
        output_paths = write_historical_replacement_stock_proof_outputs(result, root=paths.root)
        summary_df = result["summary"]
        values = {row["metric"]: row["value"] for _, row in summary_df.iterrows()} if not summary_df.empty else {}
        print(f"status={values.get('status', '')}")
        print(f"proof_rows={values.get('proof_rows', '0')}")
        print(f"date_valid_currently_available_rows={values.get('date_valid_currently_available_rows', '0')}")
        print(f"date_valid_but_already_used_later_rows={values.get('date_valid_but_already_used_later_rows', '0')}")
        print(f"replacement_arrived_after_sale_rows={values.get('replacement_arrived_after_sale_rows', '0')}")
        print(f"missing_date_proof_rows={values.get('missing_date_proof_rows', '0')}")
        print(f"not_yet_proven_rows={values.get('not_yet_proven_rows', '0')}")
        for name, path in sorted(output_paths.items()):
            print(f"{name}={path}")
        return 0 if values.get("status", "") != "fail" else 1

    if args.b_no_replacement_shortage_exception_review:
        paths = get_manager_paths(args.root)
        result = build_no_replacement_shortage_exception_review(root=paths.root, observed_utc=args.observed_utc)
        output_paths = write_no_replacement_shortage_exception_review_outputs(result, root=paths.root)
        summary_df = result["summary"]
        values = {row["metric"]: row["value"] for _, row in summary_df.iterrows()} if not summary_df.empty else {}
        print(f"status={values.get('status', '')}")
        print(f"review_rows={values.get('review_rows', '0')}")
        print(f"true_no_replacement_shortage_rows={values.get('true_no_replacement_shortage_rows', '0')}")
        print(f"replacement_mapping_gap_rows={values.get('replacement_mapping_gap_rows', '0')}")
        print(f"date_valid_but_already_used_later_rows={values.get('date_valid_but_already_used_later_rows', '0')}")
        print(f"replacement_arrived_after_sale_rows={values.get('replacement_arrived_after_sale_rows', '0')}")
        print(f"missing_date_proof_rows={values.get('missing_date_proof_rows', '0')}")
        print(f"not_yet_proven_rows={values.get('not_yet_proven_rows', '0')}")
        for name, path in sorted(output_paths.items()):
            print(f"{name}={path}")
        return 0 if values.get("status", "") != "fail" else 1

    if args.b_refund_fee_shipping_gap_review:
        paths = get_manager_paths(args.root)
        result = build_refund_fee_shipping_gap_review(root=paths.root, observed_utc=args.observed_utc)
        output_paths = write_refund_fee_shipping_gap_review_outputs(result, root=paths.root)
        summary_df = result["summary"]
        values = {row["metric"]: row["value"] for _, row in summary_df.iterrows()} if not summary_df.empty else {}
        print(f"status={values.get('status', '')}")
        print(f"review_rows={values.get('review_rows', '0')}")
        print(f"api_proved_rows={values.get('api_proved_rows', '0')}")
        print(f"sellerboard_bridge_estimate_rows={values.get('sellerboard_bridge_estimate_rows', '0')}")
        print(f"not_yet_proven_rows={values.get('not_yet_proven_rows', '0')}")
        print(f"bridge_values_safe_for_live_roi={values.get('bridge_values_safe_for_live_roi', '')}")
        for name, path in sorted(output_paths.items()):
            print(f"{name}={path}")
        return 0 if values.get("status", "") != "fail" else 1

    if args.b_level3_fee_shipping_api_proof_map:
        paths = get_manager_paths(args.root)
        result = build_level3_fee_shipping_api_proof_map(root=paths.root, observed_utc=args.observed_utc)
        output_paths = write_level3_fee_shipping_api_proof_map_outputs(result, root=paths.root)
        summary_df = result["summary"]
        values = {row["metric"]: row["value"] for _, row in summary_df.iterrows()} if not summary_df.empty else {}
        print(f"status={values.get('status', '')}")
        print(f"proof_rows={values.get('proof_rows', '0')}")
        print(f"api_source_available_rows={values.get('api_source_available_rows', '0')}")
        print(f"repo_path_unclear_rows={values.get('repo_path_unclear_rows', '0')}")
        print(f"api_source_missing_rows={values.get('api_source_missing_rows', '0')}")
        for name, path in sorted(output_paths.items()):
            print(f"{name}={path}")
        return 0 if values.get("status", "") != "fail" else 1

    if args.b_disposition_correction_swap_apply:
        result = apply_disposition_correction_swap(
            root=args.root,
            approve_protected_disposition_correction_swap=args.approve_protected_disposition_correction_swap,
            observed_utc=args.observed_utc,
            maintenance_request_id=args.b_maintenance_request_id,
        )
        print(f"status={result.status}")
        print(f"eligible_rows={result.eligible_rows}")
        print(f"applied_rows={result.applied_rows}")
        print(f"token_rows_updated={result.token_rows_updated}")
        print(f"allocation_rows_updated={result.allocation_rows_updated}")
        print(f"cogs_rows_updated={result.cogs_rows_updated}")
        print(f"blocked_rows={result.blocked_rows}")
        print(f"snapshot_dir={result.snapshot_dir or ''}")
        print(f"applied={result.applied_path}")
        print(f"manifest={result.manifest_path}")
        return 0 if result.status == "applied" else 1

    if args.b_disposition_cogs_correction_apply:
        result = apply_disposition_cogs_correction(
            root=args.root,
            approve_protected_disposition_cogs_correction=args.approve_protected_disposition_cogs_correction,
            observed_utc=args.observed_utc,
            maintenance_request_id=args.b_maintenance_request_id,
        )
        print(f"status={result.status}")
        print(f"eligible_rows={result.eligible_rows}")
        print(f"approved_rows={result.approved_rows}")
        print(f"applied_rows={result.applied_rows}")
        print(f"created_token_rows={result.created_token_rows}")
        print(f"token_rows_updated={result.token_rows_updated}")
        print(f"allocation_rows_updated={result.allocation_rows_updated}")
        print(f"cogs_rows_updated={result.cogs_rows_updated}")
        print(f"blocked_rows={result.blocked_rows}")
        print(f"snapshot_dir={result.snapshot_dir or ''}")
        print(f"applied={result.applied_path}")
        print(f"manifest={result.manifest_path}")
        return 0 if result.status == "applied" else 1

    if args.b_original_return_status_conflict_apply:
        result = apply_original_return_status_repair(
            root=args.root,
            approve_protected_original_return_status_repair=args.approve_protected_original_return_status_repair,
            observed_utc=args.observed_utc,
            maintenance_request_id=args.b_maintenance_request_id,
        )
        print(f"status={result.status}")
        print(f"eligible_rows={result.eligible_rows}")
        print(f"applied_rows={result.applied_rows}")
        print(f"token_rows_updated={result.token_rows_updated}")
        print(f"blocked_rows={result.blocked_rows}")
        print(f"snapshot_dir={result.snapshot_dir or ''}")
        print(f"applied={result.applied_path}")
        print(f"manifest={result.manifest_path}")
        return 0 if result.status == "applied" else 1

    if args.b_token_shortage_repair_preview:
        paths = get_manager_paths(args.root)
        result = build_token_shortage_repair_preview(root=paths.root)
        output_paths = write_token_shortage_repair_preview_outputs(result, root=paths.root)
        preview = result["preview"]
        summary_df = result["summary"]
        values = {row["metric"]: row["value"] for _, row in summary_df.iterrows()} if not summary_df.empty else {}
        print(f"status={values.get('status', '')}")
        print(f"preview_rows={len(preview)}")
        print(f"sale_token_rows={values.get('sale_token_rows', '0')}")
        print(f"adjustment_token_rows={values.get('adjustment_token_rows', '0')}")
        for name, path in sorted(output_paths.items()):
            print(f"{name}={path}")
        return 0 if values.get("status", "") != "blocked" else 1

    if args.b_token_shortage_repair_apply:
        result = apply_token_shortage_repair(
            root=args.root,
            approve_protected_token_shortage_repair=args.approve_protected_token_shortage_repair,
            observed_utc=args.observed_utc,
            maintenance_request_id=args.b_maintenance_request_id,
        )
        print(f"status={result.status}")
        print(f"preview_rows={result.preview_rows}")
        print(f"created_token_rows={result.created_token_rows}")
        print(f"allocated_token_rows={result.allocated_token_rows}")
        print(f"disposed_token_rows={result.disposed_token_rows}")
        print(f"stock_event_rows={result.stock_event_rows}")
        print(f"shortage_rows_removed={result.shortage_rows_removed}")
        print(f"missing_order_rows_removed={result.missing_order_rows_removed}")
        print(f"blocked_rows={result.blocked_rows}")
        print(f"snapshot_dir={result.snapshot_dir or ''}")
        print(f"applied={result.applied_path}")
        print(f"manifest={result.manifest_path}")
        return 0 if result.status == "applied" else 1

    if args.b_legacy_baseline_gap_preview:
        paths = get_manager_paths(args.root)
        result = build_legacy_baseline_gap_preview(root=paths.root, observed_utc=args.observed_utc)
        output_paths = write_legacy_baseline_gap_preview_outputs(result, root=paths.root)
        preview = result["preview"]
        summary_df = result["summary"]
        values = {row["metric"]: row["value"] for _, row in summary_df.iterrows()} if not summary_df.empty else {}
        print(f"status={values.get('status', '')}")
        print(f"preview_rows={len(preview)}")
        print(f"decision_ready_rows={values.get('decision_ready_rows', '0')}")
        print(f"blocked_rows={values.get('blocked_rows', '0')}")
        print(f"active_b_owner_seen={values.get('active_b_owner_seen', '0')}")
        for name, path in sorted(output_paths.items()):
            print(f"{name}={path}")
        return 0 if values.get("status", "") != "blocked" else 1

    if args.b_legacy_baseline_gap_apply:
        result = apply_legacy_baseline_gap_repair(
            root=args.root,
            approve_protected_legacy_baseline_repair=args.approve_protected_legacy_baseline_repair,
            observed_utc=args.observed_utc,
            maintenance_request_id=args.b_maintenance_request_id,
        )
        print(f"status={result.status}")
        print(f"preview_rows={result.preview_rows}")
        print(f"created_token_rows={result.created_token_rows}")
        print(f"allocated_token_rows={result.allocated_token_rows}")
        print(f"cogs_rows={result.cogs_rows}")
        print(f"shortage_rows_removed={result.shortage_rows_removed}")
        print(f"missing_order_rows_removed={result.missing_order_rows_removed}")
        print(f"blocked_rows={result.blocked_rows}")
        print(f"snapshot_dir={result.snapshot_dir or ''}")
        print(f"applied={result.applied_path}")
        print(f"manifest={result.manifest_path}")
        return 0 if result.status == "applied" else 1

    if args.b_refund_token_reproof_apply:
        result = apply_refund_token_reproof(
            root=args.root,
            approve_protected_b008_repair=args.approve_protected_b008_repair,
            observed_utc=args.observed_utc,
            maintenance_request_id=args.b_maintenance_request_id,
        )
        print(f"status={result.status}")
        print(f"eligible_rows={result.eligible_rows}")
        print(f"applied_rows={result.applied_rows}")
        print(f"token_rows_updated={result.token_rows_updated}")
        print(f"refund_event_rows_updated={result.refund_event_rows_updated}")
        print(f"blocked_rows={result.blocked_rows}")
        print(f"snapshot_dir={result.snapshot_dir or ''}")
        print(f"applied={result.applied_path}")
        print(f"manifest={result.manifest_path}")
        return 0 if result.status == "applied" else 1

    if args.b_return_token_reuse_apply:
        result = apply_return_token_reuse_repair(
            root=args.root,
            approve_protected_b009_repair=args.approve_protected_b009_repair,
            observed_utc=args.observed_utc,
            maintenance_request_id=args.b_maintenance_request_id,
        )
        print(f"status={result.status}")
        print(f"eligible_rows={result.eligible_rows}")
        print(f"applied_rows={result.applied_rows}")
        print(f"token_rows_updated={result.token_rows_updated}")
        print(f"created_token_rows={result.created_token_rows}")
        print(f"return_ledger_rows={result.return_ledger_rows}")
        print(f"stock_event_rows={result.stock_event_rows}")
        print(f"blocked_rows={result.blocked_rows}")
        print(f"snapshot_dir={result.snapshot_dir or ''}")
        print(f"applied={result.applied_path}")
        print(f"manifest={result.manifest_path}")
        return 0 if result.status == "applied" else 1

    if args.mot_task_status:
        if not args.status:
            parser.error("--status is required with --mot-task-status")
        paths = get_manager_paths(args.root)
        row = update_mot_work_item_status(
            output_dir=paths.output_dir,
            work_item_id=args.mot_task_status,
            status=args.status,
            note=args.note,
            observed_utc=args.observed_utc,
        )
        print(f"work_item_id={row['work_item_id']}")
        print(f"status={row['status']}")
        print(f"updated_utc={row['updated_utc']}")
        print(f"retest_command={row['retest_command']}")
        return 0

    if args.task_status:
        if not args.status:
            parser.error("--status is required with --task-status")
        paths = get_manager_paths(args.root)
        result = update_codex_repair_task_status(
            output_dir=paths.output_dir,
            task_id=args.task_status,
            status=args.status,
            note=args.note,
            actor=args.actor,
            observed_utc=args.observed_utc,
        )
        print(f"task_id={result['task_id']}")
        print(f"old_status={result['old_status']}")
        print(f"new_status={result['new_status']}")
        print(f"queue_path={result['queue_path']}")
        print(f"event_path={result['event_path']}")
        return 0

    summary = run_manager(
        root=args.root,
        flow=args.flow,
        read_only=args.read_only,
        write_report_flag=args.write_report,
        observed_utc=args.observed_utc,
    )
    print(f"status={summary['status']}")
    print(f"manager_execution_errors={summary['manager_execution_errors']}")
    for name, path in sorted(summary["outputs"].items()):
        print(f"{name}={path}")
    return 1 if summary["manager_execution_errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
