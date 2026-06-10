# SO21 Team Throughput Recovery Plan

Updated: 2026-06-09 15:15 UK
Owner: Operations

## Plain-English Summary For Rep

Luke is right: SellerOne 2.1 was behaving too much like one cautious worker queue.

Operations has corrected the operating model to a multi-lane team board. F remains urgent, but F no longer freezes safe control, review, diagnosis, or planning work.

## Why The System Slowed Down

The slowdown had four causes:

- F became a live-runtime emergency, involving a stuck TD Synnex scanner state, stale process handling, Windows access-denied behavior, and Seller Central safety rules.
- Operations treated the F lane too much like the whole system, instead of isolating it as one blocked lane.
- Many approved packets were visible but not classified, so Luke saw a pile of work without a clear reason why each item was running, waiting, blocked, or parked.
- Reviewer/closure work was not being used aggressively enough to close completed work and free the board.

## What Changed Now

Operations now maintains:

- `CONTROL/SO21_ACTIVE_LANE_BOARD.md`
- `CONTROL/SO21_APPROVED_PACKET_LANE_CLASSIFICATION_20260609.csv`

Every approved packet in `tasks/approved` has a lane classification in the CSV:

- active now
- safe to start next
- waiting proof/review
- blocked with reason
- parked with reason

Current count:

- active now: `5`
- safe to start next: `57`
- waiting proof/review: `2`
- blocked with reason: `12`
- parked with reason: `143`

## Active Tonight

### Emergency F Recovery Lane

Goal:

- recover F enough to run one bounded proof window without a second owner or unsafe Seller Central behavior.

Current state:

- offline F status/login repair is applied
- focused tests passed
- stale PID `14740` is no longer visible in latest process check
- F must still not restart normal scanning
- F must still not attempt Seller Central proof while A/global maintenance ownership is active

Current blocker:

- global maintenance request is A-owned: `requested_by=A`, `pid=25284`, `reason=A_cycle_run`

What can be done tonight:

- wait for A/global maintenance to clear,
- then confirm no stale F owner/child remains,
- confirm repaired code is loaded,
- run one bounded F proof window through the single controller only.

What cannot happen:

- no second F owner
- no normal scanning restart
- no Seller Central login proof while global maintenance is A-owned
- no Amazon security bypass or repeated SMS/phone/code attempts

### Control Cleanup/Proof Lane

Active:

- `SO21-CONTROL-FLOW-CONFIRMATION`
- Worker thread: `019eacb8-d93b-7cf1-91cf-61a7b1fd0411`

Expected evidence:

- `CONTROL/SO21_CONTROL_FLOW_CONFIRMATION.md`

### Reviewer/Closure Lane

Closed tonight:

- `SO21-THREAD-ROLE-HYGIENE` -> `proved`
- `SO21-PROOF-CLOSURE-RULES` -> `proved`

Evidence:

- `CONTROL/SO21_THREAD_ROLE_HYGIENE_REVIEW.md`
- `CONTROL/SO21_PROOF_CLOSURE_RULES_REVIEW.md`

### Safe Planning/Report Lane

Active:

- `SO21-OPERATIONS-SHIFT-MANAGER-CONTROL`
- Worker thread: `019eacb9-3e11-7cd2-a000-26ba1e6e03f3`

Expected evidence:

- `CONTROL/SO21_OPERATIONS_SHIFT_MANAGER_CONTROL.md`

### Read-Only MOT/Diagnosis Lane

Status:

- safe to start next if active control/planning workers complete or stall

Candidates:

- B/H/O read-only MOT diagnosis packets
- no live runtime
- no business state mutation

## What Must Wait

F live proof must wait until:

- A/global maintenance ownership is clear or explicitly handled,
- no stale F owner or child exists,
- repaired code is the code being launched,
- one bounded proof window is available,
- and proof can show Dashboard Yes/No or clean logged-out parking/hold behavior past TD Synnex.

Protected or blocked packets must wait if they require:

- Amazon security action
- repeated SMS/phone/code attempt
- price change
- Sheet write
- database write/alignment
- output deletion
- permanent Task Scheduler change
- destructive cleanup
- second runtime owner
- unbounded restart

Parked packets remain parked when predecessor evidence is missing or when their packet says they wait for another proof/review/apply step.

## Evidence Luke Should Expect Tomorrow Morning

Rep should be able to show Luke:

- active lane board with current lanes and owners
- all-packet classification register
- F emergency lane status: recovered to proof, or still blocked with exact reason
- number of packets closed overnight
- number of packets moved to review
- which workers/reviewers are active
- which blockers are real and lane-specific
- confirmation that no extra manager chats were created

## Next Operations Standard

Every Operations pass must produce one of:

- waiting-proof item closed
- safe worker assigned
- reviewer assigned
- real blocker recorded
- Luke decision requested

Silent waiting is no longer acceptable for approved non-Luke work.

## Current Rep Message

What is active tonight:

- F emergency lane, blocked only by A/global maintenance before proof can run.
- Control-flow confirmation worker.
- Operations shift-manager control worker.
- Reviewer/closure lane already closed two packets tonight.

What is blocking automation:

- F cannot attempt Seller Central proof until the A-owned global maintenance request clears or is explicitly handled.
- Protected work cannot run just because it is approved; it needs the exact packet boundary and proof route.

What recovery action is required:

- Immediate F recovery action is now: wait for A/global maintenance clearance or get explicit Rep/Luke approval for cross-flow maintenance handling.
- The earlier elevated/admin F-only stop is no longer the immediate blocker because PID `14740` is no longer visible in the latest process check.
