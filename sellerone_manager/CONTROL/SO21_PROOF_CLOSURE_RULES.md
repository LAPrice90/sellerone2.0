# SO21 Proof Closure Rules

Created: 2026-06-09
Job: `SO21-PROOF-CLOSURE-RULES`
Owner: Operations and Reviewer
Mode: control process only, no runtime change

## Plain-English Purpose

Proof closure is the step where SellerOne decides what a finished-looking ticket really means.

Think of it like signing off building work. A missing safety rail is not the same as a smudge on the paperwork. The safety rail stops the job. The smudge gets fixed without pretending the building failed.

These rules keep safety and real evidence strict, while stopping small report-format repairs from making safe business passes look blocked.

## Boundaries

This document does not approve:

- weaker safety checks
- automatic approval of missing proof
- business runtime changes
- Task Scheduler changes
- process kills
- worker restarts
- Amazon or security actions
- price changes
- Google Sheets writes
- Product DB or local DB alignment
- purchase, receiving, or send-to-Amazon actions
- output deletion, cleanup, archive apply, movement, compression, or purge

Proof closure may classify evidence and recommend the next queue action. It must not change protected business state to make proof pass.

## Proof Result Grades

| Grade | Meaning | Closes Business Proof? | Normal Next Action |
|---|---|---:|---|
| `pass` | The named proof route passed, required evidence exists, no safety issue exists, and no material gap remains. | Yes | Reviewer or proof owner may recommend `proved`. |
| `pass_minor_format_repair` | The business or safety proof passed, but the report has a harmless presentation problem such as a missing label, extra safe line, wording mismatch, typo, or non-material formatting issue. | Yes, if the proof evidence itself is complete | Close or recommend close, then open or assign a narrow format repair if the packet requires clean reporting. |
| `returned_material_gap` | Required evidence is missing, stale, contradictory, incomplete, or cannot prove the packet acceptance criteria. | No | Return to Builder as `retest_failed` or keep `fixed_needs_retest` only if a fresh Reviewer check is still actively underway. |
| `blocked_needs_luke` | The next step needs Luke or protected approval, or the proof touches a protected boundary. | No | Escalate through Rep with the exact decision needed. Do not let Builder guess. |
| `failed_safety` | The proof shows unsafe behavior, exposed secret risk, unauthorized protected action, runtime ownership conflict, security bypass risk, live data mutation risk, or a safety gate failure. | No | Stop the line, record the safety reason, and return or block according to the packet boundary. |
| `waiting_proof` | Work claims to be ready, but the named proof has not yet run or the natural proof window has not arrived. | No | Operations must track the wait condition, owner, and next check time. |

## Strict Safety Rule

Safety failures always outrank format repairs.

A ticket must not receive `pass_minor_format_repair` if any of these are true:

- the proof exposed or mishandled credentials, cookies, tokens, OTPs, MFA, or security state
- the proof used an Amazon/security workaround outside the approved path
- the proof changed prices, Sheets, databases, queues, purchases, receiving, send-to-Amazon state, or runtime outputs without approval
- the proof overlapped a live owner, stale lock, or active maintenance marker in a way the packet forbids
- the proof result is based on old health output from before the change
- the proof skipped the named acceptance route
- the proof hides a material row-count, status-code, file-existence, finalization, or freshness gap

If safety is uncertain, classify as `returned_material_gap` or `blocked_needs_luke`, not as a pass.

## Material Gap Rule

A material proof gap is a missing piece that changes whether the work really passed.

Examples:

- the required proof file does not exist
- the proof file is older than the fix or decision being checked
- the required status code, row count, marker, or final state is missing
- the report says passed but the underlying evidence says failed
- a required scoped flow gate still has an active FAIL
- the proof was run on the wrong packet, wrong flow, wrong file, or wrong time window
- the acceptance criteria mention a check that the Reviewer did not inspect

Material gaps must be returned or blocked. They must not be renamed as formatting.

## Minor Format Repair Rule

A minor format repair is safe only when the proof itself is complete and the remaining defect is about presentation.

Examples:

- report heading is slightly wrong
- job reference is present but not in the preferred place
- a safe extra line appears in a report
- wording is less clear than the control standard requires
- a table column label needs cleanup
- a proof summary is correct but needs clearer plain-English wording

Operations may treat this grade as a safe business pass only when the Reviewer clearly states:

- what evidence passed
- why the remaining issue is format-only
- that no safety issue exists
- that no material acceptance criterion is missing

## Luke Decision Rule

Use `blocked_needs_luke` when the proof needs a real human choice.

Examples:

- approval to touch prices, Sheets, databases, queues, purchases, receiving, send-to-Amazon, Amazon/security, scheduler ownership, cleanup apply, or worker restart
- a business tradeoff that cannot be decided from the packet
- a packet boundary conflict where continuing would widen scope
- a protected recovery path where the safest next step needs explicit approval

The blocker must name the exact choice. It must not say only "needs Luke" without explaining what Luke is deciding.

## Waiting-Proof No-Idle Rule

Waiting-proof items must not sit idle just because they are not Builder work.

Operations must review each waiting-proof item on every control pass and record one of these outcomes:

- proof exists and grade is `pass`
- proof exists and grade is `pass_minor_format_repair`
- proof exists but grade is `returned_material_gap`
- proof is blocked and grade is `blocked_needs_luke`
- proof failed safety and grade is `failed_safety`
- proof is not ready and grade remains `waiting_proof` with an exact wait condition

For every `waiting_proof` item, Operations must keep four facts visible:

- job reference
- proof owner or next role
- exact proof file, command, scheduled run, or natural flow boundary being waited on
- next check condition or time

If no owner, no proof route, or no next check condition can be named, the item is not healthy waiting proof. Operations must create or recommend a narrow repair, proof-mapping, or blocker packet instead of leaving it parked in silence.

## Closure Workflow

1. Read the packet acceptance proof first.
2. Read the latest direct proof artifact named by the packet or control file.
3. Check whether any safety boundary was touched.
4. Check whether every material acceptance point is proved by fresh evidence.
5. Assign one proof result grade.
6. Choose the narrowest next action:
   - `pass`: recommend `proved`
   - `pass_minor_format_repair`: recommend `proved` for the business result and create or assign only the narrow format repair if still needed
   - `returned_material_gap`: return to Builder for the exact missing proof
   - `blocked_needs_luke`: send the exact decision to Rep
   - `failed_safety`: stop closure and return or block with the exact safety reason
   - `waiting_proof`: keep the wait condition, owner, and next check visible
7. Do not start new Builder work while older waiting-proof work has no grade, owner, or next check condition.

## Operations Reporting Standard

Operations reports should use this short shape:

| Field | Required Content |
|---|---|
| `job_ref` | The packet job reference. |
| `proof_grade` | One of the six grades in this document. |
| `passed_evidence` | The exact proof artifact, command result, status code, row count, timestamp, or file inspected. |
| `remaining_issue` | `none`, `minor_format_repair`, `material_gap`, `Luke_decision`, `safety_failure`, or `waiting_condition`. |
| `next_action` | The one narrow action that should happen next. |
| `protected_boundary_touched` | `yes` or `no`. If yes, explain and stop. |

## Examples

### Safe Pass With Minor Format Repair

Evidence:

- Amazon credential status check returned HTTP/status code 200.
- Reviewer found no secret exposure.
- The only issue was an extra safe report line.

Grade:

- `pass_minor_format_repair`

Closure:

- The business proof can close.
- The report cleanup is a narrow format repair, not a material blocker.

### Material Gap

Evidence:

- The document exists, but the acceptance proof required a named status code and no status code was checked.

Grade:

- `returned_material_gap`

Closure:

- Return to Builder or Reviewer for the missing proof. Do not close as pass.

### Failed Safety

Evidence:

- The proof required read-only inspection, but the run changed a queue, Sheet, database, scheduler, or Amazon/security state.

Grade:

- `failed_safety`

Closure:

- Stop the line and escalate according to the packet boundary.

## Acceptance Check For This Rule

This control document is valid only if:

- safety failures stay strict
- material proof gaps cannot be hidden as formatting
- Luke decisions are separated from technical proof failures
- minor format repairs have a clear narrow lane
- waiting-proof items must carry an owner, route, and next check condition

## Recommended Use

Use this document with `CONTROL/SO21_QUEUE_MOVEMENT_BOARD.md` so Operations can show which proof items are closed, waiting, returned, blocked, or format-only repairs.
