# Repricing Manager Stack Plan - PPP Hybrid

Status: Active - Phase 0 Safe Mode
Date: 2026-02-11

## Goal
Build a practical repricing system that:
- Uses Profit Protector Pro (PPP) for broad day to day execution.
- Uses a small in house API lab to learn competitor behavior.
- Uses a manager stack so pricing actions are controlled and explainable.

## Why this approach
- We need results now, not a full rebuild first.
- Passive observation is not enough to detect aggressive competitors.
- Controlled probes on a small SKU set give high quality learning.
- PPP can continue handling most SKUs while we learn and improve.

## Manager stack
### Runtime architecture (official)
- The 3-role pricing system runs in its own dedicated loop process.
- It must not be bundled into `run_A_all.py`.
- It must not be bundled into `run_B_cycle.py`.
- Proposed runner name: `scripts/run_H_pricing_cycle.py`.
- Proposed runtime artifacts:
- lock file: `out/H_pricing_cycle.lock`
- cycle log: `out/H_pricing_cycle.log`
- state cache: `out/h_pricing_cycle_state.json`
- The loop internally schedules:
- Head task at 24 hour cadence
- Supervisor task at 4 hour cadence
- Executioner task at 15 minute cadence plus trigger overrides

### Head (daily strategy and boundaries)
Responsibilities:
- Set lane per SKU: Passive, Managed, Micro managed.
- Set hard boundaries: floor, ceiling, max move size, cooldown.
- Set risk limits: max probes per SKU per day, max active probe SKUs.
- Set which SKUs are in the lab cohort.

Output:
- Daily strategy config for each SKU.
- Allowed actions and safety limits.

Cadence:
- every 24 hours (morning review)

### Supervisor (4 hour tactical controller)
Responsibilities:
- Decide when a worker can run a probe.
- Choose probe type based on current state:
  - lower
  - match
  - raise
- Enforce cooldown, probe budget, and stop conditions.
- Escalate or downgrade SKU lane based on evidence.

Output:
- Approved worker actions with exact target price and expiry.
- Tactical status per SKU (stable, follower, aggressor candidate, unknown).

Cadence:
- every 4 hours baseline
- immediate run only on major triggers (buy box loss, aggressor re-entry, floor breach risk)

### Executioner (execution and logging)
Responsibilities:
- Execute approved price moves only.
- Pull response snapshots at set windows (5m, 15m, 60m, 4h).
- Record competitor response facts:
  - moved yes or no
  - direction
  - size
  - reaction time
- Never break boundaries set by Head.

Output:
- Clean event log and response log for each probe.
- No strategy decisions, execution only.

Cadence:
- every 15 minutes baseline
- event driven immediate checks for trigger events

## Phase rollout (fast start)
### Phase 0 - Week 1 Safe Mode repricer
- Purpose: go live now, gather data now, avoid aggressive risk.
- Rules:
- no battle plans
- no floor discovery ladders
- no rapid drop chains
- allowed behavior is simple follow or hold within boundaries
- Guardrails:
- hard floor and break-even protection
- max move size per cycle
- max daily down move per SKU
- cooldown between moves
- kill switch for anomalies

### Phase 0 pilot SKU (official first test)
- SKU: `JB-RGB6-LZOJ` (Loctite 319 Rear View Mirror Bonder 0.5ml)
- Pilot reason:
- not a heavy income dependency SKU
- enough live competition to generate useful behavior data
- enough on-hand stock for controlled observation
- Day 1 to Day 7 operating rules for this SKU:
- Safe Mode only
- no battle plans
- no floor-discovery ladders
- follow or hold only within boundaries
- Suggested starting limits:
- max move per cycle: 0.10 to 0.20 GBP
- max total down move per day: 0.50 GBP
- cooldown: 15 to 30 minutes
- hard floor: break-even protected (or better)
- Daily review fields:
- Buy Box owner changes
- competitor reaction lag
- chase depth hints
- delivery advantage pressure
- ROI guardrail compliance

### Phase 1 - Controlled live probes on pilot only
- Keep pilot-only scope.
- Enable controlled live repricing writes on `JB-RGB6-LZOJ` within Head and Supervisor guardrails.
- Run probe types that actually test market reaction (not passive observation only).
- Compare planned action vs executed action vs market response.

### Phase 1 learning extension - seller delta engine
- Goal: learn real Buy Box winning margin per seller, including hidden discount conditions.
- Learning key: `SKU + seller_id`.
- Method:
1. Start with initial estimate around rival visible price.
2. Test every 15 minutes using controlled step downs until first Buy Box win.
3. After first win, step up in small increments to find highest still-winning delta.
4. Record bracket:
- `highest_delta_win_gbp`
- `lowest_delta_loss_gbp`
5. Narrow bracket until no meaningful untested delta remains.
6. Use learned daily delta for follow actions against that seller.
7. Re-test once per day, or sooner on win-loss drift.
- Rival movement rule:
- if rival moves during tests, re-anchor to new rival price and continue bracket search, do not restart from zero.
- Hidden sale rule:
- if observed Buy Box outcomes repeatedly mismatch visible price logic, set `promo_suspected` for that seller and use smaller steps with tighter checks.
- Safety:
- never breach hard floor or break-even guard
- keep cooldown and max daily move controls active
- stop and escalate when confidence is low or outcomes unstable

### Phase 2 - Pilot hardening (still single SKU)
- Continue probes on pilot SKU only.
- Tune thresholds from evidence (reaction lag, floor confidence, guardrail behavior).
- Prove repeatability across multiple days and sessions.

### Phase 3 - Gate for expansion decision
- Decide if the full 3-role process is validated end-to-end on the pilot.
- Expansion to additional SKUs is forbidden unless this gate is explicitly passed and approved.
- Keep strict limits and rollback path.

## PPP plus API lab model
### Production lane (most SKUs)
- PPP remains primary executor.
- Uses existing safe min and max controls.
- Safe Mode rules apply during first week.
- No custom high frequency experiments during Phase 0.
- A cycle remains data/health focused and is not the long-running pricing scheduler.

### Lab lane (small SKU set)
- In house API execution for controlled tests only.
- Suggested start size: 1 SKU only (official pilot) until explicit expansion approval.
- Focus: discover competitor behavior and test tactical responses.

## Probe framework
For each selected SKU:
1. Run one probe action (lower, match, or raise) within limits.
2. Collect competitor response snapshots at fixed windows.
3. Log results and classify behavior trend.
4. Wait cooldown before next probe.

Classification rules (initial):
- Aggressor candidate:
  - fast repeated downward reaction after our move.
- Follower:
  - reacts slower and less consistently.
- Stable:
  - little or no reaction over repeated probes.

Note:
- One probe is not enough to classify.
- Require repeated outcomes across different times and days.

## Guardrails
- Hard floor and ceiling per SKU.
- Max price changes per SKU per day.
- Minimum cooldown between worker actions.
- Global kill switch for lab execution.
- Stop probing SKU if risk triggers (margin risk, low stock risk, instability).

## Data we need to collect now
- Time series of market snapshots for probe SKUs.
- Executioner action log (what we changed, when, why).
- Competitor response log (how they moved and how fast).
- Basic outcome markers after probe windows (buy box status changes, short term sales signal if available).
- Seller delta learning fields:
- `seller_id`
- `rival_visible_price_gbp`
- `our_test_price_gbp`
- `observed_buy_box_owner`
- `observed_buy_box_price_gbp`
- `delta_vs_rival_gbp`
- `highest_delta_win_gbp`
- `lowest_delta_loss_gbp`
- `delta_confidence`
- `promo_suspected_flag`

## Future phase - Buy Box eligibility intelligence (daily A-side)

### Objective
- Discover a realistic Buy Box ceiling using Amazon eligibility signals, not only reactive probes.
- Use this as a ceiling input for SKU strategy, especially in low or no competition mode.

### Signals to add
- `Featured Offer Expected Price (FOEP)` from `getFeaturedOfferExpectedPriceBatch`.
- `CompetitivePriceThreshold` from pricing APIs (external retail benchmark).

### Daily cadence proposal
- Run once per day as an A-side data collection step.
- Output to local files first, then upsert into Product DB fields.
- Do not execute repricing from this step; this is intelligence input only.

### Product DB fields (planned)
- `foep_price_gbp`
- `foep_last_seen_utc`
- `competitive_price_threshold_gbp`
- `competitive_threshold_last_seen_utc`
- `buy_box_eligibility_ceiling_gbp`
- `eligibility_confidence`

### Initial ceiling rule (planned)
- If FOEP exists, use FOEP as primary eligibility ceiling candidate.
- If Competitive Price Threshold exists and is lower than FOEP, clamp ceiling to threshold.
- Final ceiling still respects Head policy and margin floor rules.

### Health and safety
- Add schema checks for new output file(s) and Product DB fields.
- Add alert if eligibility data is stale beyond 48 hours.
- Keep this process read and assess only; no direct price writes.

## What we do with returned prices
- Check against boundaries first.
- Detect scenario from response pattern.
- Select next tactical state through Supervisor.
- Approve or reject next worker action.
- Update seller behavior score and confidence.

## Tomorrow start plan
1. Confirm lab SKU list (start with 1 official pilot SKU).
2. Confirm top manager boundary template fields.
3. Define middle manager tactical decision table.
4. Define worker probe event schema and response schema.
5. Start Safe Mode on pilot SKU only.
6. Run first controlled probes on pilot SKU only after Safe Mode baseline is stable.
7. Review logs and adjust thresholds before expansion decision.

## Definition of a good first milestone
- Manager stack is in place (Head, Supervisor, Executioner roles clear).
- Executioner executes only approved actions.
- At least 3 probe cycles completed on the pilot SKU.
- Logs are readable and support behavior classification.
- No boundary breaches.

## Clarification update - seller strategy and ceiling game
Date: 2026-02-12

### Strategy unit definition
- Pricing is not SKU-only.
- Runtime strategy unit is:
- SKU profile (listing-level rules) plus
- SKU-seller profiles (one per `seller_id` on that SKU).

### New listing start behavior (official)
- New listings start in `launch` mode, not aggressive competition mode.
- In launch mode:
- enforce break-even floor and ceiling
- gather seller behavior evidence
- keep random low-threat FBM sellers as background only
- promote to active seller-game only after evidence threshold

### Dual decision outputs per cycle
- Output A (seller game funnel):
- per seller compute required price to win that seller
- combine selected seller outputs into one low-side target
- Output B (SKU ceiling game):
- compute max realistic sell price from SKU-level ceiling
- temporary source is manual BBP max sold price
- Final target is clamped between floor and ceiling.

### Low/no-competition mode
- This mode is margin-focused, not inactive.
- Rules:
- raise toward ceiling in controlled steps
- lower API/check cadence
- keep immediate trigger for known aggressor re-entry
- if aggressor reappears, switch back to active competition mode

### Current temporary ceiling policy
- Use manually maintained competitive ceiling per SKU.
- Store ceiling as official live input for now.
- Later replace with automated ceiling model after evidence and validation.

## Pre-expansion gate - real-time notifications backbone (must pass before full SKU rollout)

### Purpose
- Reduce expensive pull calls and throttling risk before scaling to full SKU count.
- Move from constant checking to event-led checks on listings that actually changed.

### Scope (phase order)
1. Build push intake in listen-only mode first:
- `ANY_OFFER_CHANGED`
- `PRICING_HEALTH`
2. Store events to local logs and link events to SKU and seller profiles.
3. Use events to trigger targeted refresh checks for changed SKUs only.
4. Keep low-frequency safety polling as fallback.
5. Only after stable proof, allow expansion from pilot cohort to full SKU list.

### Minimum pass criteria for this gate
- Notifications are received reliably for pilot SKUs over multiple days.
- Event to action latency is measured and within agreed target.
- No missed critical pricing-health alerts in validation window.
- Pull call volume per SKU is materially reduced versus baseline.
- Health checks added for notification freshness, schema, and backlog age.

### Non-negotiable boundary
- Full SKU logic expansion is blocked until this notification gate is marked passed.
