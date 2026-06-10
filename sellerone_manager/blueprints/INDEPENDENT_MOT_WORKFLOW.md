# Independent MOT Workflow

## Plain-English Purpose
The independent MOT is the outside inspector.

A worker cycle can say it is running or finished, but that is not enough. If the worker dies before it reports the problem, the system can lie by accident.

The MOT avoids that by checking the proof directly:
- did the file get updated
- is the file too old
- does it contain rows
- did a required producer step get skipped
- is a lock stale
- does the database table have the expected data
- is the same failure already known

## Current Position
The new manager MOT is the future direction.

Do not delete the old system-wide morning MOT yet. It still contains useful restart, ownership, due-check, and post-A checks. Keep it as a safety net until the manager MOT has copied or replaced those checks and proved it can run reliably.

## How The Chain Is Tested
The test must use the real automation path, not hand-made output.

For A, the proof chain is:

1. Trigger Windows task `SellerOne Manager Hourly MOT`.
2. Confirm the task result is `0`.
3. Confirm `out/systems/M/mot/mot_history.jsonl` received a new row.
4. Confirm `out/systems/M/mot/mot_worklist.csv` contains the active A blockage.
5. Run the manager front door.
6. Confirm the manager shows a Codex task and does not ask Luke for technical work.

## A Blockage Rule
The current A blockage is not fixed by editing the MOT.

The real problem was that A001, A002, and A004 local refresh proof went stale because those producer steps were skipped with the legacy Sheet-output switch.

The repair should separate local source-fact refresh from legacy Sheet writing.

Allowed direction:
- keep legacy Sheet writing disabled unless Luke explicitly approves it
- restore local CSV or local database refresh where the A flow owns it
- prove the result by rerunning the MOT against real refreshed outputs

Forbidden direction:
- hand-edit MOT files
- hand-edit output files to make row counts look fresh
- change the local database just to match another source
- run a live worker cycle unless the flow-owned proof window is approved

Current proof status:
- code splits for A001, A002, and A004 can be applied and tested without opening Sheets
- the MOT should still show A failures until a real A-owned run refreshes the output files
- do not mark the worklist rows `proved` until the same MOT checks clear after real output refresh

## Worker Bee Rule
Future repair agents must work from manager-approved worklist rows or approved manager task files.

They may inspect code, make bounded code repairs, run isolated tests, and request a retest.

They may not mark a job complete themselves. The MOT must retest the same proof and the manager must mark it `proved`.

## Future Cycle Rule
When adding B, E, H, F, or O to this pattern, start with independent proof checks first.

Do not start by asking Luke to remember how the cycle works. Read the expectation file, read the existing proof files, build the MOT checks, then let the manager create bounded tasks from failures.
