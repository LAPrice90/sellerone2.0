# Feeder Cycle Expectations

## Purpose
The feeder cycle is the new-product intake and qualification system. It converts supplier lists into approved, test-buy-ready candidates that can enter the main loop at Purchase Orders with clean token compatibility.

## SECTION 1 - Completion Definition
| Feature | Description | Status | Notes |
|---|---|---|---|
| Supplier list intake | Supplier files can be ingested with source metadata | Not Started | Baseline v1 scope |
| List normalization | Mixed supplier formats are converted to one canonical structure | Not Started | Baseline v1 scope |
| Barcode and identity validation | Candidate identity and barcode validation state are recorded | Not Started | Baseline starts with structural validation and match-state capture |
| Viability checks | Candidate viability status and reason codes are produced | Not Started | Baseline checklist output required |
| Profit and demand checks | Estimated margin/ROI and demand indicators are generated | Not Started | Baseline supports test-buy decisioning |
| Test-buy recommendation | Recommended test quantity is output per candidate | Not Started | Baseline requirement |
| Approval queue | Human decision queue supports approve/reject/watch/manual-review | Not Started | Baseline requirement |
| PO handoff package | Approved candidates can be handed off to Purchase Orders | Not Started | Main-loop entry point |
| Token-safe handoff checks | Approved candidates meet minimum token-compatibility prerequisites | Not Started | Required before downstream COGS/returns traceability |
| Dropped/discontinued handling | Dropped is recoverable, Discontinued is terminal | Not Started | Waste/output channel behavior |

## SECTION 2 - Reliability Measurement
Measure reliability over the last 10 completed feeder runs:
- Fails: ingestion failure, normalization breakage, invalid handoff package, or status-routing corruption.
- Warnings: partial parse, ambiguous identity match, incomplete checklist evidence, or manual-review overflow.
- Clean runs: full intake-to-handoff processing with valid status outputs and no handoff contract defects.

Before runtime exists:
- Reliability Score = `To Baseline`.

Suggested scoring baseline (post-implementation):
- Start at 100.
- Subtract 25 if any fail in window.
- Subtract 10 per warned run, up to 30.
- Subtract 20 if approved candidates fail PO/token handoff contract checks.

## SECTION 3 - Acceptance Criteria
- Replacement Complete:
- Feeder can intake supplier lists, normalize, classify candidates, output test-buy recommendation, and hand approved candidates into Purchase Orders.
- Dropped and Discontinued behavior is implemented with correct lifecycle meaning.
- Stable:
- No fail in last 10 feeder runs.
- At least 8 of last 10 runs are clean.
- No approved candidate fails handoff contract validation.
- Ready for expansion:
- Stable across 2 review windows.
- Extended intelligence checks can be added without breaking baseline outputs.

## SECTION 4 - Improvement Backlog
These do not affect Completion Score:
- Automated brand gating and restriction APIs.
- Advanced barcode-to-listing confidence scoring.
- Rank/rating/seller-count scoring models.
- Adaptive test-buy sizing with feedback learning.
- Multi-supplier dropped-product recovery intelligence.
