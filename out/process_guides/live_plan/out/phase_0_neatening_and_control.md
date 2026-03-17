# Phase 0 — Neatening and Control (As-Built → Deterministic → Safe to Refactor)

## Objective
Convert the current “loosely held together” system into a deterministic, explainable machine **without changing business logic**.
Phase 0 is complete when runs are repeatable, outputs are attributable, and changes can be made safely with confidence.

## Hard Rules (Non-Negotiable)
- No business-logic changes in Phase 0 (pricing, ROI, floors/ceilings, eligibility, parked rules, scoring).
- Only allowed entrypoints during Phase 0:
  - run_A_all.bat
  - run_B_cycle.bat
  - run_H_cycle.bat
  - run_E_all.bat
- No manual one-off scripts in daily operation.
- Any change must have: evidence + acceptance check + rollback step.

## Definition of Done (Phase 0)
- 10 consecutive clean runs (or “approved WARN-only”) across the cycles you run daily.
- Every run produces a manifest with:
  - run_id, cycle, step list, inputs, outputs, return code, duration
- Shared artifacts in out/ have:
  - single owner (writer), explicit readers, and schema/exists checks
- A “golden set” regression snapshot exists for 10 SKUs.
- A015 is enforced as publish gate: no publish on FAIL, WARN only if in approved list.

---

## Step 1 — Lock Down Operations (1 session)
### 1.1 Entrypoints policy
- Document that the only operational entrypoints are the 4 .bat files listed above.
- Add a short header comment at top of each .bat stating:
  - “Operational entrypoint — do not bypass; use for all runs.”

### 1.2 Stop ad-hoc execution
- Create: out/reviews/OPERATIONAL_RULES.md
  - list allowed entrypoints
  - forbid scripts/one_off/* in ops
  - require locks/maintenance handshake if present

Acceptance:
- You can point to one place that states “how we run this system” and it matches reality.

Rollback:
- Delete OPERATIONAL_RULES.md (no runtime impact).

---

## Step 2 — Freeze a Golden Set (1 session)
### 2.1 Select SKUs
- Choose 10 SKUs that represent:
  - normal sellers
  - low competition
  - high competition
  - at least one “weird” historical case
  - at least one parked candidate

### 2.2 Capture current truth outputs
- Create folder: out/golden_runs/YYYY-MM-DD/
- Run the normal cycle(s) you use for those SKUs.
- Save:
  - key outputs you rely on (the specific csv/json/sheets export files used in decisions)
  - logs for the run

Create:
- out/golden_runs/YYYY-MM-DD/README.md describing:
  - what was run
  - exact command/entrypoint
  - where the outputs live

Acceptance:
- You have a stable baseline snapshot to compare against later.

Rollback:
- Delete golden_runs folder (but do not unless needed).

---

## Step 3 — Add Deterministic Manifests (Phase 0 core) (1–2 sessions)
Goal: every cycle run emits a machine-readable manifest.

### 3.1 Manifest format
Create one canonical schema (json or csv) with:
- run_id (timestamp + short random suffix)
- cycle (A/B/H/E)
- start_time, end_time, duration
- steps: list of {name, script/function, inputs[], outputs[], rc, notes}
- health_summary: FAIL/WARN/OK counts (if available)

### 3.2 Where manifests are written
- out/manifests/{cycle}/{YYYY-MM-DD}/{run_id}.json

### 3.3 Implement in cycle runners
Update only the runners:
- run_A_all.py (or the script the .bat calls)
- run_B_cycle.py
- run_H_pricing_cycle.py (or equivalent)
- run_E_cycle.py

Do NOT change domain logic.

Acceptance:
- Each run produces a manifest file.
- Manifest includes at least:
  - run_id, cycle, step names, rc
  - list of key artifacts written by steps

Rollback:
- Feature-flag manifest writes behind an env var if needed, or revert runner changes.

---

## Step 4 — Build an Artifact Registry (1 session)
Create: out/reviews/ARTIFACT_REGISTRY.md

For each shared artifact in out/:
- Path
- Owner (single writer script)
- Readers
- Expected schema (if csv: column list; if json: keys)
- Freshness rule (how new it must be)
- Failure mode if missing/stale
- Lock/handshake notes

Acceptance:
- You can answer: “Who owns this file?” for every shared artifact.

Rollback:
- None required (documentation only).

---

## Step 5 — Enforce Gate Policy (1 session)
### 5.1 Gate definition
Set policy:
- no publish on any FAIL
- WARNs allowed only if in approved list (explicit list stored in config or in A015)

### 5.2 Make WARN list explicit
Create:
- out/reviews/APPROVED_WARN_LIST.md
Include:
- warn_name
- why allowed temporarily
- removal criteria

Acceptance:
- A015 output clearly explains why it did/did not publish.

Rollback:
- Revert gate tightening if it blocks operations unexpectedly.

---

## Step 6 — Burn-down Loop (ongoing, 30–60 mins per day)
- Each day, take the top 1–2 recurring WARN/FAIL classes.
- Fix only:
  - determinism issues
  - missing artifact writes
  - schema drift
  - ordering/lock issues
- Do not refactor domain logic yet.

Stop condition:
- 10 consecutive clean runs (or approved WARN-only).

---

## Exit Criteria → Phase 1
You may start Phase 1 (refactor/extract domain functions) only when:
- manifests are present and reliable
- golden set exists
- gate policy is enforced
- shared artifacts have clear ownership
- runs are stable enough to compare old vs new outputs
