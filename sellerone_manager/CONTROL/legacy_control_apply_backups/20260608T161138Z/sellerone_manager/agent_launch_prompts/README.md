# SellerOne Agent Launch Prompts

Generated from the manager board on 2026-05-30.

Use these files to start separate Codex chats without re-explaining the manager system.

Plain-English rule:
- The main manager is the front desk.
- Sub-managers make one cycle independently checkable.
- Worker agents only repair inside approved manager task packets.
- Luke should not manage task ids, file paths, proof rules, or repair sequencing.

## How To Use

Open a new Codex chat for the job you want, then paste the full contents of the relevant prompt file:

- `00_MAIN_MANAGER_COORDINATOR_PROMPT.md`
- `01_B_ORDER_TRUTH_MANAGER_PROMPT.md`
- `02_H_SAFETY_LAYER_MANAGER_PROMPT.md`
- `03_E_ANALYTICS_PROOF_MANAGER_PROMPT.md`
- `04_F_PRICE_LIST_MANAGER_PROMPT.md`
- `05_O_MID_BUILD_MANAGER_PROMPT.md`
- `06_A_WATCH_ONLY_MANAGER_PROMPT.md`

Only one chat should claim the same approved task packet at a time.

## Current Work Order

1. B first: B is the active blocker.
2. H second: H must get a stronger safety layer before broad repair.
3. E: proof and confidence coverage, not an emergency.
4. F: keep scanner/source proof clean without queue edits.
5. O: map mid-build status honestly, not as a finished cycle.
6. A: watch only unless the MOT changes.

## Protected Boundaries

All chats must stop before:

- price changes
- queue edits
- Google Sheets writes
- publishing
- local DB alignment
- output deletion
- worker restarts
- live worker cycles without an approved proof window
- scheduler ownership changes outside an approved controlled proof packet
- business decisions on uncertain rows

## Reply Style

Use this shape:

```text
Decision needed: yes/no

Plain-English status:
<short answer>

Codex-owned next step:
<what the agent will do next>

Interrupt Luke only if:
<specific protected decision>
```

Do not finish with `no further action needed now`.

