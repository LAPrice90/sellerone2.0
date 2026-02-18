# Codex Starter - Build E + H + F0 (Manual Pricing Manager)

Paste this into a NEW Codex chat for each task.

---

## 0) Operating rules

You must follow AGENTS.md exactly.

- Read these files first:
  - AGENTS.md
  - Blueprint_E_H_F0_v1.md
  - E_cycle_runbook_v2.md
  - E_cycle_decision_logging_spec_v2.md
  - H0_listing_offer_history_spec_v1.md
  - F0_manual_execution_runbook_v1.md

Rules:
- Root cause first (do not mask issues downstream).
- One task per thread. Do not refactor unrelated code.
- Do not implement anything unless I explicitly say PROCEED.
- If you change code: run the script(s) and show evidence (row counts, sample rows).
- Any new output file must have a schema check.
- Any loop step must be idempotent.
- Use ASCII hyphen only.

---

## 1) Task format (mandatory)

When I give you a task:
1) Restate the task in one sentence.
2) List the exact files you will read/change.
3) Propose a plan with validation steps.
4) Implement with minimal diffs.
5) Run verification and show outputs.

If any input data is missing, STOP and ask instead of inventing.

---

## 2) Common tasks (pick ONE per chat)

Examples:
- Add H001 daily offer snapshot script skeleton (writes CSV, schema check).
- Add f_training_set.csv support (only 5-10 SKUs) and wire H to it.
- Add import stub for BuyBotPro backfill (H002) with clear mapping and source tags.

End.
