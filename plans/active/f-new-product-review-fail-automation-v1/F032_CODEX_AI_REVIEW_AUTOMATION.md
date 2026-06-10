# F032 Codex AI Review Automation

Date: 2026-05-20

## Plain English Aim

Codex should review the small F032 product queue before the user sees the products in the review UI.

The scanner builds the evidence. Codex makes the judgement. The UI only shows rows after the Codex decision file exists and FPM155 has published the AI-gated manifest.

## Daily Automation Job

Mandatory guide files:

- `plans/active/f-new-product-review-fail-automation-v1/FAIL_REASON_REVIEW_CHECKLIST.md`
- `plans/active/f-new-product-review-fail-automation-v1/F032_CODEX_AI_REVIEW_AUTOMATION.md`

The fail-reason checklist is not background reading. Codex must apply it to each queue row before deciding whether the row can be shown to the user.

The daily automation should do this:

1. Run `python scripts\one_off\F035_refresh_f032_ai_review_queues.py`.
2. Find every `ai_review_queue.csv` under `out/systems/F/price_list_manager/review_handoffs/*/*/`.
3. For each queue, check whether `codex_ai_review_decisions.csv` exists and covers every `f032_decision_id`.
4. For missing decisions, read the queue row evidence and apply the New Product Review Fail Reason Checklist one category at a time.
   - Use supplier title, Amazon title, Amazon product description, Amazon feature bullets, product detail text, ROI/profit, seller evidence, demand evidence, and review evidence when present.
   - If description or bullet text proves the pack count or product identity, cite that evidence in `codex_ai_evidence`.
5. Write or update `codex_ai_review_decisions.csv`.
6. Run `python scripts\one_off\F035_refresh_f032_ai_review_queues.py` again.
7. Confirm the handoff either:
   - published an AI-gated `manifest.csv`, or
   - stayed pending/failed with a clear health reason.

## Decision Actions

Allowed actions:

- `allow_if_other_checks_pass`
- `manual_review`
- `rescan_needed`
- `remove_from_clean_pass`

Decision rules:

- clear good match = `allow_if_other_checks_pass`
- same broad brand but product identity is uncertain = `manual_review`
- missing title, missing Amazon evidence, or evidence too weak = `rescan_needed`
- clear wrong product, device-vs-accessory mismatch, pack-size mismatch, or high ROI plus suspicious title = `remove_from_clean_pass`

## Fail Reason Checklist Mapping

Codex must check these categories for every queued product:

- wrong product match: compare supplier title, Amazon title, brand, model, pack size, variant, and device-vs-accessory meaning
- seller-controlled or risky seller situation: review seller-history signals and brand-owner/Amazon/dominant-seller risk
- profit looks better than it really is: review ROI, unit cost, sell price, profit quality, and high-profit warning signs
- demand evidence is too weak: review rank, expected units, sales range, missing demand evidence, and demand conflicts
- UK review or variant risk: review UK review signals, variant/review mismatch, and weak UK-specific evidence
- feedback too vague to learn from: use a specific decision bucket and reason, not a vague note
- empty or missing evidence: rescan when required evidence is missing or the evidence window is not trustworthy

For each row, `codex_ai_reason` must name the strongest checklist reason in plain English.

For manual-review rows, `codex_ai_reason` should be written as a short operator note whenever possible. Example:

- `Check the Amazon listing really contains 50 card sleeves.`

For each row, `codex_ai_decision_bucket` should use a stable bucket such as:

- `wrong_product_title_or_pack_mismatch`
- `seller_control_risk`
- `profit_or_roi_suspicion`
- `weak_demand_evidence`
- `uk_review_or_variant_risk`
- `missing_evidence_rescan_needed`
- `manual_identity_guidance_needed`
- `codex_review_clear`

Low confidence rule:

- low confidence must not go to clean Pass
- low confidence must go to `manual_review` or `rescan_needed`

## Required Decision File Columns

The file must be named:

- `codex_ai_review_decisions.csv`

Required columns:

- `f032_decision_id`
- `codex_ai_action`
- `codex_ai_decision_bucket`
- `codex_ai_fail_category`
- `codex_ai_confidence`
- `codex_ai_needs_user_guidance`
- `codex_ai_rescan_needed`
- `codex_ai_reason`
- `codex_ai_evidence`
- `codex_ai_reviewed_utc`
- `codex_ai_reviewer`

## Success Criteria

The automation is working when:

- every queued row has one Codex decision
- every decision has a valid action
- every decision has a plain-English reason
- FPM155 publishes `manifest.csv` only after decisions are complete
- `manifest.csv` has `ai_gate_status=passed`
- `manifest.csv` has `operator_ready_flag=1`
- every visible row has `f032_decision_id`
- every visible row has `codex_ai_action`

## Human Review Learning

Later, user decisions should be compared back to Codex decisions:

- Codex allowed but user failed = possible false clear
- Codex blocked but user later accepted = possible false block
- Codex manual review = training case
- repeated patterns = possible future rule so Codex has less work

This is how the system can later decide which work can be taken off Codex safely.
