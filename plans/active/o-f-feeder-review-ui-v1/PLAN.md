# Plan

## Goal
- Final outcome:
  - design a temporary feeder review page that sits inside the current operator UI style
  - let the user review new-product candidates in batches
  - capture `pass` / `fail` decisions plus notes
  - send those decisions back through a safe append-only path for later analysis

## Non-goals
- Do not do:
  - do not code the page in this ticket
  - do not bypass the existing F launch plan
  - do not write directly into PO handoff outputs
  - do not reuse O restock decision events for feeder review
  - do not expose raw reason-code clutter as the main user experience

## Current state
- What already exists:
  - The existing operator UI lives in `scripts/flows/O/O400_operator_ui.py`.
  - The restocker already uses a clear operator pattern:
    - tabbed navigation
    - supplier filters
    - row cards
    - inline editable controls
    - append-only event inbox on send
  - The new-product launch work already has review packs:
    - `out/analysis_reports/f_live_price_file_pass_review_latest.csv`
    - `out/analysis_reports/f_live_price_file_near_miss_review_latest.csv`
    - `out/analysis_reports/f_live_price_file_review_summary_latest.csv`
- Known gap:
  - Batch 003 of the current feeder launch plan still expects CSV-first review.
  - The user wants an operator-facing UI review step instead.

## Target state
- one temporary UI tab exists inside the operator UI
- one clear batch-review workflow exists for feeder candidates
- one append-only feeder review event inbox exists
- one review log and one analysis pack exist downstream
- the page uses commercial labels and simple controls, not engineering-style fields

## Systems touched
- Flow(s):
  - O flow for operator UI rendering
  - F flow for review event ingestion and analysis outputs
- Shared dependencies:
  - `scripts/flows/O/O400_operator_ui.py`
  - `out/analysis_reports/f_live_price_file_pass_review_latest.csv`
  - `out/analysis_reports/f_live_price_file_near_miss_review_latest.csv`
  - `out/analysis_reports/f_live_price_file_review_summary_latest.csv`
  - existing F launch plan at `plans/active/f-feeder-commercial-test-launch-v1/`
- Runtime or ownership concerns:
  - the page must not reuse `restock_decision_events.csv`
  - feeder review must have its own append-only intake path

## File and output ownership
| Item | Planned owner | Input or output | Path | Notes |
|---|---|---|---|---|
| UI tab rendering | `scripts/flows/O/O400_operator_ui.py` | future derived view | O operator UI | temporary tab in restocker style |
| Pass review source | existing F one-off output | input | `out/analysis_reports/f_live_price_file_pass_review_latest.csv` | current pass shortlist |
| Near-miss review source | existing F one-off output | input | `out/analysis_reports/f_live_price_file_near_miss_review_latest.csv` | current near-miss shortlist |
| Review summary source | existing F one-off output | input | `out/analysis_reports/f_live_price_file_review_summary_latest.csv` | top counts and batch counts |
| Feeder review event inbox | planned new F contract | output | `out/systems/F/inbox/feeder_review_events.csv` | append-only UI submissions |
| Feeder review log | planned new F contract | output | `out/systems/F/live/feeder_review_log.csv` | normalized reviewed decisions |
| Gap analysis pack | planned new F builder | output | `out/analysis_reports/f_feeder_review_gap_analysis_latest.csv` | note themes, reject reasons, missing-signal summary |

## UX design rules
- Use the existing O tabbed structure.
- Keep filters and batch controls at the top, as in the restocker.
- Group rows by review batch, not by raw file order.
- Show only the fields needed for commercial judgement.
- Keep the main user action binary for v1:
  - `Pass`
  - `Fail`
- Include a note box on every row.
- Add a visible external-link symbol next to the ASIN.
- Build the Amazon link as:
  - `https://www.amazon.co.uk/dp/<asin_padded_to_10_chars>`
- If the ASIN is shorter than 10 characters, left-pad with `0` until it reaches 10.

## Proposed page design

### Placement
- Add a temporary tab to `O400_operator_ui.py`.
- Recommended label:
  - `New Product Review`
- Recommended position:
  - immediately after `Reorder`
- Reason:
  - this keeps buying decisions together without mixing feeder review into Product DB or PO tabs

### Header area
- Top line:
  - `New Product Review`
- Caption:
  - `Review pass and near-miss candidates from the active supplier wave. Mark each row pass or fail, add a note, then send the batch back for analysis.`
- Summary cards:
  - Active supplier
  - Current pass rows
  - Current near-miss rows
  - Current hard rejects

### Control bar
- Filters:
  - supplier selector
  - lane selector:
    - `Passes`
    - `Near misses`
  - batch selector:
    - `pass_batch_001`, `pass_batch_002`, etc
    - `near_miss_batch_001`, `near_miss_batch_002`, etc
  - search box:
    - title / SKU / ASIN
  - optional toggle:
    - `Show only undecided rows`

### Row design
- Use the same broad visual language as reorder cards:
  - small image area or placeholder tile
  - identity block
  - metric block
  - decision block
- Identity block:
  - title
  - supplier SKU
  - ASIN
  - link icon opening Amazon PDP
- Metric block:
  - lane
  - lower / expected / upper band
  - expected profit
  - conservative starter qty
  - main rank
  - short commercial note
- Decision block:
  - radio or segmented control:
    - `Pass`
    - `Fail`
  - note text area:
    - placeholder example:
      - `Why did you pass or fail this? What feels missing, risky, or strong?`

### Submit area
- One batch-level primary button:
  - `Send Batch for Analysis`
- Secondary helper line:
  - `Only rows with a decision are sent.`
- Success notice after submit:
  - row count sent
  - batch id
  - when it was sent

## Data model design

### UI source model
- The UI reads directly from the existing F review-pack outputs.
- The UI should not edit those source packs.
- The UI may derive display-only helpers such as:
  - `asin_padded`
  - `amazon_dp_url`
  - `display_decision_label`

### Proposed event inbox contract
- Path:
  - `out/systems/F/inbox/feeder_review_events.csv`
- Behavior:
  - append-only
- Required fields:
  - `event_utc`
  - `event_id`
  - `active_supplier_id`
  - `active_run_id`
  - `review_pack_type`
  - `review_batch_id`
  - `candidate_id`
  - `supplier_sku`
  - `asin_raw`
  - `asin_padded`
  - `amazon_dp_url`
  - `review_decision`
  - `review_note`
  - `actor`
  - `source_reference`
- Notes:
  - `review_decision` in v1 is `pass` or `fail`
  - this inbox is separate from both:
    - `restock_decision_events.csv`
    - `feeder_approval_decisions_log.csv`

### Proposed applied review log
- Path:
  - `out/systems/F/live/feeder_review_log.csv`
- Purpose:
  - normalized current reviewed decisions from the UI
- Example fields:
  - `review_utc`
  - `event_id`
  - `review_pack_type`
  - `review_batch_id`
  - `candidate_id`
  - `supplier_sku`
  - `asin_padded`
  - `review_decision`
  - `review_note`
  - `actor`
  - `source_reference`

### Proposed gap analysis output
- Path:
  - `out/analysis_reports/f_feeder_review_gap_analysis_latest.csv`
- Purpose:
  - summarize what the user is repeatedly rejecting or approving
- Expected outputs:
  - top reject themes
  - top pass themes
  - repeated missing-signal complaints
  - rows where the model passed but the user failed
  - rows where near-miss rows were manually accepted

## Commercial language design
- Avoid raw contract names in the main surface.
- Preferred labels:
  - `Sales band`
  - `Profit outlook`
  - `Starter test qty`
  - `Why it passed`
  - `Why it nearly failed`
  - `Your decision`
  - `Your note`
- Avoid showing raw labels like:
  - `reason_codes`
  - `decision_state`
  - `source_reference`
  - `schema_status`
  on the main review surface

## Risks and mitigations
- Risk:
  - this page gets confused with restock decisions
  - Mitigation:
    - separate tab, separate inbox, separate action language
- Risk:
  - the page becomes a debug grid instead of a commercial review screen
  - Mitigation:
    - keep the visible field set small and plain-English
- Risk:
  - notes are captured but never turned into useful feedback
  - Mitigation:
    - design the gap-analysis output up front
- Risk:
  - a binary `pass` / `fail` choice is too simple
  - Mitigation:
    - keep v1 binary for speed, then add a later `watch` extension only if repeated use proves it is needed

## Phase list

### Phase 0 - design lock
- write the new UI task as a planning-only active folder
- lock the page purpose, placement, and event boundary

### Phase 1 - contract and wireframe implementation
- add the temporary UI tab
- add the feeder review event inbox contract
- render pass and near-miss review batches in restocker style

### Phase 2 - submit and analysis path
- implement the batch submit button
- persist feeder review events
- build applied review log and gap analysis pack

### Phase 3 - pilot with live review batches
- run the page against current `pass_batch_001`
- confirm operator flow is simple enough
- inspect whether notes reveal obvious missing fields or logic gaps

## Proof rules
- What counts as code fix applied:
  - planning files, UI design spec, and batch file exist in a new active plan folder
- What counts as isolated verification passed:
  - design clearly names:
    - page placement
    - visible row fields
    - submit path
    - analysis path
    - ASIN link rule
- What counts as live loop verification confirmed:
  - not applicable in this planning ticket

## Batch list
- Batch 001:
  - design lock, event-path decision, and UI wireframe
- Batch 002:
  - implement temporary operator review tab
- Batch 003:
  - implement event intake and analysis outputs
- Batch 004:
  - pilot the live review flow on current feeder batches

## Archive rule
- When this plan can move to archive:
  - after the UI design is either implemented in an approved follow-on ticket or explicitly replaced by a different operator-review approach
