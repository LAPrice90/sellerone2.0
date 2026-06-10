# Hometime Prompt

Use this prompt in a new Codex chat to complete the next open plan in hometime mode.

## Prompt

Ticket: `h-f-overlap-sample-strategy-v1`

Mode:
- Hometime mode
- quiet execution
- do the work end to end without routine checkpoint messages
- only interrupt if proof contradicts the plan, scope must change, or runtime approval becomes necessary

Goal:
- Complete `plans/archive/2026/h-f-overlap-sample-strategy-v1` through archive-ready state.
- Finish Phases 1 to 4.
- Do not start Phase 5 runtime work unless the plan evidence truly justifies it and an explicit approval gate exists.
- If Phases 1 to 4 are complete and the plan archive rule is met, archive the plan in the same ticket.

Read first:
- `plans/archive/2026/h-f-overlap-sample-strategy-v1/PLAN.md`
- `plans/archive/2026/h-f-overlap-sample-strategy-v1/CODING_PLAN.md`
- `plans/archive/2026/h-f-overlap-sample-strategy-v1/PLAN_STATUS.md`
- `plans/archive/2026/h-f-overlap-sample-strategy-v1/DATA_CONTRACTS.md`
- `plans/archive/2026/h-f-overlap-sample-strategy-v1/RUNBOOK.md`
- `plans/archive/2026/h-f-data-cleanup-2026-04-18/SIGNOFF_2026-04-18.md`

Root-cause order:
1. Build the overlap expansion and routing pack so zero overlap becomes actionable.
2. Build the tactic scorecard so thin-sample tactics cannot be misread as mature.
3. Build the strategy review pack so no-source blockers stay separate from true underperformance.
4. Build the shadow-only experiment queue with explicit gates and no live H effect.
5. Defer runtime work unless the plan's own thresholds clearly justify a later ticket.

Systems in scope:
- H/F one-off analysis builders
- optional shadow-only F handoff through `F080`
- read-only H, F, E, and B artifacts as evidence sources

Hard boundaries:
- no Google Sheets changes
- no local DB changes
- no ad-hoc A runs unless explicitly requested
- no overlapping manual B work
- no new scrape owner path
- no live H repricer rule change in this ticket
- no downstream smoothing to hide overlap or missing-baseline truth

Phase execution rules:
- Follow the coding plan in order.
- Stay inside the allowed files for the current phase.
- After each phase:
  - run the listed `py_compile` command
  - run the listed pytest pack
  - rerun the builder twice against unchanged inputs
  - record stable row counts, key buckets, and any source timestamps
  - update plan docs with factual proof before starting the next phase

Recommended clean-run target:
- Because this is builder-only work with no live runtime change, use `3 clean deterministic full-pack runs` at the end of Phase 4 on unchanged inputs.
- Treat a clean run as:
  - all targeted tests pass
  - each builder rerun is deterministic
  - output row counts and key buckets reconcile
  - queue remains shadow-only

Files expected to be created or completed:
- `scripts/one_off/HF010_build_scope_expansion_candidates.py`
- `tests/test_hf_scope_expansion_candidates.py`
- `scripts/one_off/HF011_build_strategy_scorecard.py`
- `tests/test_hf_strategy_scorecard.py`
- `scripts/one_off/HF012_build_strategy_review_pack.py`
- `tests/test_hf_strategy_review_pack.py`
- `scripts/one_off/HF013_build_strategy_experiment_queue.py`
- `tests/test_hf_strategy_experiment_queue.py`
- optional shadow-only `F080` adjustments if needed and justified

Outputs that must exist before archive:
- `out/analysis_reports/hf_scope_expansion_candidates_latest.csv`
- `out/analysis_reports/hf_scope_expansion_summary_latest.csv`
- `out/analysis_reports/hf_strategy_scorecard_latest.csv`
- `out/reports/hf_strategy_review_pack_latest.csv`
- `out/analysis_reports/hf_strategy_experiment_queue_latest.csv`

Archive rule for this ticket:
- archive only when:
  - overlap pack exists and makes the zero-overlap problem actionable
  - tactic scorecard exists with maturity gates
  - review pack exists and separates missing baseline from true underperformance
  - experiment queue exists in shadow-only mode
  - any H runtime follow-up is explicitly deferred with reasons and thresholds

Required final status language:
- `code fix applied`
- `isolated verification passed`
- `live loop verification not required for Phases 1 to 4`
- if runtime work stays deferred, say `runtime promotion not attempted in this ticket`

Proof standard:
- Root cause first.
- No masking downstream.
- Show counts and reconciliation from the generated outputs before calling the plan complete.
