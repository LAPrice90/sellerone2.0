from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F._review_intelligence import (
    CHECKLIST_COLUMNS,
    DECISION_COLUMNS,
    DEFAULT_CHECKLIST_OUTPUT_PATH,
    DEFAULT_DECISION_OUTPUT_PATH,
    DEFAULT_EVIDENCE_OUTPUT_PATH,
    DEFAULT_FAIL_CATEGORY_OUTPUT_PATH,
    DEFAULT_HEALTH_OUTPUT_PATH,
    DEFAULT_NEAR_MISS_REVIEW_PATH,
    DEFAULT_PASS_REVIEW_PATH,
    DEFAULT_RULE_SUGGESTION_OUTPUT_PATH,
    DEFAULT_SUMMARY_OUTPUT_PATH,
    DEFAULT_SUPPLIER_INBOX_DIR,
    DEFAULT_TITLE_MATCH_PATH,
    EVIDENCE_COLUMNS,
    F032Result,
    RULE_SUGGESTION_COLUMNS,
    VALID_F032_ACTIONS,
    build_review_intelligence_cycle,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build F032 Review Intelligence Cycle evidence and decisions.")
    parser.add_argument("--pass-review-path", type=Path, default=DEFAULT_PASS_REVIEW_PATH)
    parser.add_argument("--near-miss-review-path", type=Path, default=DEFAULT_NEAR_MISS_REVIEW_PATH)
    parser.add_argument("--title-match-path", type=Path, default=DEFAULT_TITLE_MATCH_PATH)
    parser.add_argument("--supplier-inbox-dir", type=Path, default=DEFAULT_SUPPLIER_INBOX_DIR)
    parser.add_argument("--evidence-output-path", type=Path, default=DEFAULT_EVIDENCE_OUTPUT_PATH)
    parser.add_argument("--decision-output-path", type=Path, default=DEFAULT_DECISION_OUTPUT_PATH)
    parser.add_argument("--fail-category-output-path", type=Path, default=DEFAULT_FAIL_CATEGORY_OUTPUT_PATH)
    parser.add_argument("--checklist-output-path", type=Path, default=DEFAULT_CHECKLIST_OUTPUT_PATH)
    parser.add_argument("--rule-suggestion-output-path", type=Path, default=DEFAULT_RULE_SUGGESTION_OUTPUT_PATH)
    parser.add_argument("--health-output-path", type=Path, default=DEFAULT_HEALTH_OUTPUT_PATH)
    parser.add_argument("--summary-output-path", type=Path, default=DEFAULT_SUMMARY_OUTPUT_PATH)
    parser.add_argument("--observed-utc", default="")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    result = build_review_intelligence_cycle(
        pass_review_path=args.pass_review_path,
        near_miss_review_path=args.near_miss_review_path,
        title_match_path=args.title_match_path,
        supplier_inbox_dir=args.supplier_inbox_dir,
        evidence_output_path=args.evidence_output_path,
        decision_output_path=args.decision_output_path,
        fail_category_output_path=args.fail_category_output_path,
        checklist_output_path=args.checklist_output_path,
        rule_suggestion_output_path=args.rule_suggestion_output_path,
        health_output_path=args.health_output_path,
        summary_output_path=args.summary_output_path,
        observed_utc=args.observed_utc or None,
    )
    print(json.dumps(result.report, indent=2, sort_keys=True))
    return 0 if result.report["health_fail_rows"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
