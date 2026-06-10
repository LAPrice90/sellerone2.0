# SellerOne Manager Control Plane V1 - Project Brief

## Problem
SellerOne has many worker scripts and many status files. The work itself is split across flows, but the operating story is still hard to read. A supplier can look like the problem when the real blocker is earlier in the pipeline.

Current example:
- The F price-list dashboard says CLF is the recommended next scan.
- The live F owner status says the manager is blocked by storage drift.
- Therefore CLF is not the root problem. The scanner cannot reach CLF until storage drift is fixed.

## Goal
Build a read-only control tower that reads existing worker evidence and writes one clear report.

The first version covers only the F price-list manager.

## Success
- Manager code reads current F artifacts without running workers.
- Manager writes a normalized snapshot, health file, incident file, self-organisation report, and plain-English report under `out/systems/M/`.
- Manager explains the earliest blocker first.
- The dry-run command exits cleanly with 0 manager execution errors.

## Boundaries
- No Google Sheets writes.
- No local DB alignment.
- No F061 live queue edits.
- No A, B, E, or H runs.
- No worker restarts.
- No LLM calls in v1.
