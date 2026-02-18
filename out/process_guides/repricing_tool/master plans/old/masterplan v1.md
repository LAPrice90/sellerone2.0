# Unified Master Plan - Repricing Intelligence (Single Source of Truth)

Status: Active Draft (Consolidated)
Date: 2026-02-12
Owner: Luke (business intent), Codex (execution support)

## 1) Canonical Rule
- This file is now the single working plan.
- All other plan files in `out/process_guides/live_plan` are reference material unless copied into this file.

## 2) Goal
- Build a repricing system that is seller-aware, delivery-aware, and profit-led.
- Learn from real Buy Box outcomes, not just visible lowest prices.
- Scale safely from one pilot SKU to full SKU coverage.

## 3) Core Principles
- Market-without-us is mandatory in analysis.
- Effective price is required: landed price plus delivery penalty.
- Strategy unit is SKU plus seller profile, not SKU alone.
- Learning is behavior-triggered (unknown delta or drift), not calendar-triggered.
- Guardrails always apply (hard floor, ceiling, max move, cooldown, risk caps).
- Execution must be explainable (reason codes, confidence, outcome logs).

## 4) Operating Model

### Head
- Sets daily boundaries and intent per SKU.
- Decides where to fight, where to hold, and risk budget.
- Does not execute price writes.

### Supervisor
- Chooses tactical state and allowed probe style.
- Selects seller of interest coverage.
- Approves exact action envelope for executioner.

### Executioner
- Executes approved actions only.
- Logs event and response windows.
- Updates seller learning memory from observed outcomes.

## 5) Pricing Logic (Merged)

### 5.1 Market Truth
- Capture all offer instances (do not collapse by seller only).
- Track seller-level memory and offer-instance observations separately.
- Detect buy box winner, channel, delivery posture, and rival set changes.

### 5.2 Learning Loop (Seller Delta Engine)
- Learning key: `SKU + seller_id`.
- Build and maintain:
- `highest_delta_win_gbp`
- `lowest_delta_loss_gbp`
- `learned_delta_gbp`
- `delta_confidence`
- `promo_suspected_flag`
- Learning process:
1. Start from current estimate vs focused rival.
2. Step down until first win.
3. Step up to find highest still-win.
4. Narrow remaining gap until practical convergence.
5. Apply learned delta while stable.
6. Re-enter learning immediately on drift.

### 5.3 Ceiling and Floor
- Floor must be profitability-protected and never breached.
- Ceiling uses layered inputs:
- eligibility ceiling (FOEP/CPT when available)
- market ceiling (competitive realism)
- policy/compliance ceiling
- Final executable price must stay within floor and ceiling.

### 5.4 Low/No Competition Behavior
- Margin-focused mode.
- Controlled upward steps toward ceiling.
- Immediate trigger to return to competitive mode on aggressor re-entry.

## 6) Data and Outputs (Merged Minimum Set)

### Required runtime outputs
- `out/h_executioner_action_log.csv`
- `out/h_worker_probe_event_log.csv`
- `out/h_worker_probe_response_log.csv`
- `out/h_seller_profiles.csv`
- `out/h_seller_of_interest.csv`
- `out/h_seller_delta_learning.csv`

### Required field themes
- price facts (our, rival, buy box, landed)
- delivery facts (min/max days, prime, channel)
- behavior facts (move direction, lag, persistence)
- decision facts (mode, reason codes, confidence, guardrail clamps)

## 7) Rollout Path

### Stage A - Pilot SKU live learning
- SKU: `JB-RGB6-LZOJ`
- Objective: stable behavior learning and controlled execution.
- Exit criteria:
- repeatable learning records
- no guardrail breaches
- consistent reason-coded actions

### Stage B - Profit-led decision layer
- Replace any implicit "lowest wins" default with objective-led selection under constraints.
- Keep pressure mode controlled and gated.

### Stage C - Eligibility intelligence
- Add FOEP and CompetitivePriceThreshold daily intake (read/assess path).
- Store in Product DB fields for ceiling guidance.

### Stage D - Pre-expansion notifications gate
- Implement `ANY_OFFER_CHANGED` and `PRICING_HEALTH` in listen-first mode.
- Use push events to trigger targeted refresh checks.
- Keep low-frequency safety polling fallback.
- Full SKU expansion is blocked until this gate passes.

## 8) Decisions Required (Conflicts to Resolve)

### D1 - Final price objective
Conflict:
- Some notes default to "minimum required winning price".
- Other notes require "maximize expected profit/day under constraints".
Decision needed:
- Choose one default objective and one optional override mode.

### D2 - Learning trigger basis
Conflict:
- Some notes say re-test once daily.
- Current intent says learning is behavior-triggered by unknown delta or drift.
Decision needed:
- Confirm behavior-triggered is primary.
- Decide if daily check is backup only.

### D3 - Nuclear/pressure automation level
Conflict:
- One stream allows controlled nuclear mode.
- Another recommends manual-approval only for pressure mode.
Decision needed:
- Choose whether pressure can be autonomous, supervised, or manual-only.

### D4 - Canonical planner file policy
Conflict:
- Multiple files currently contain active rules.
Decision needed:
- Confirm this file as the only authoritative source.
- Treat others as archive/reference only.

### D5 - Ceiling model precedence
Conflict:
- Ceiling currently mixes manual cap, ROI fallback, and planned FOEP/CPT.
Decision needed:
- Define strict precedence order and fallback reason codes.

## 9) Immediate Next Actions (No ambiguity)
1. Confirm decisions D1 to D5 in this file.
2. Update H runtime logic only after D1 to D3 are fixed.
3. Keep pilot SKU in controlled mode until Stage A exit criteria are met.
4. Do not expand SKU scope until Stage D gate passes.

## 10) Source Notes (Merged from)
- `out/process_guides/live_plan/Codex Master Working Plan - Competition Intelligence.md`
- `out/process_guides/live_plan/Repricing Manager Stack Plan - PPP Hybrid.md`
- `out/process_guides/live_plan/chatgpt_log.md`
- `out/process_guides/live_plan/My ideas.md`
- `out/process_guides/live_plan/improvements.md`
- `out/process_guides/live_plan/archived/phase_1_0_observation_schema.md`
- `out/process_guides/live_plan/archived/Head of Sales Manager — Phased Implementation Plan (Codex Runbook).md`
- `out/process_guides/live_plan/archived/Competition Data Capture & Daily Reports (Codex Runbook).md`
- `out/process_guides/live_plan/archived/Ideas to be incorperated/profit_optimisation.md`
