# UI Design

## Page name
- `New Product Review`

## Placement
- inside the existing operator UI in `O400_operator_ui.py`
- position:
  - after `Reorder`
  - before `Product DB`

## User flow
1. Open `New Product Review`.
2. Pick a lane:
  - `Passes`
  - `Near misses`
3. Pick a batch:
  - `pass_batch_001`
  - `near_miss_batch_001`
  - etc
4. Read each row in a commercial card layout.
5. Mark each reviewed row:
  - `Pass`
  - `Fail`
6. Add a note.
7. Click:
  - `Send Batch for Analysis`
8. Review confirmation notice.

## Page sections

### 1. Summary strip
- active supplier
- active run id
- pass row count
- near-miss row count
- hard reject row count

### 2. Control bar
- lane selector
- batch selector
- supplier selector
- search box
- `Show only undecided rows`

### 3. Review cards
- left:
  - thumbnail or placeholder
- middle:
  - title
  - supplier SKU
  - ASIN
  - external link icon
  - short commercial metrics
- right:
  - `Pass` / `Fail`
  - note box

### 4. Batch submit bar
- row count selected
- primary button:
  - `Send Batch for Analysis`

## Row content

### Identity
- title
- supplier SKU
- ASIN
- Amazon link icon

### Commercial fields
- `Sales band`
  - lower / expected / upper
- `Profit outlook`
- `Starter test qty`
- `Rank`
- `Commercial note`

### Lane-specific helper text
- For pass rows:
  - `Why it passed`
- For near-miss rows:
  - `Why it nearly failed`
  - `Recovery hint`

## Decision controls

### Decision input
- binary segmented control:
  - `Pass`
  - `Fail`

### Note input
- multiline text box
- placeholder:
  - `Write your reasoning in plain English. Example: looks too seasonal, title too weak, good enough for a cautious test, Amazon risk not clear.`

## Submit behavior
- batch-level submit only
- only rows with a selected decision are submitted
- rows without a decision remain on screen
- after send:
  - show success message
  - keep the page in the same lane and batch
  - optionally hide rows already submitted if `Show only undecided rows` is on

## ASIN link rule
- source:
  - row ASIN from review pack
- display:
  - show visible ASIN text plus link symbol
- link construction:
  - uppercase the ASIN
  - if length is below 10, left-pad with `0` to length 10
  - build:
    - `https://www.amazon.co.uk/dp/<asin_padded>`
- example:
  - `B006SYGN9O` -> `https://www.amazon.co.uk/dp/B006SYGN9O`
  - `6SYGN9O` -> `https://www.amazon.co.uk/dp/0006SYGN9O`

## Visual tone
- same spacing and density family as reorder cards
- same tab and filter logic as the existing operator UI
- plain-English labels only
- no visible schema or contract terms on the main review surface

## What this page is for
- quick commercial judgement
- capturing your thought process
- feeding that thought process back into analysis

## What this page is not for
- editing feeder source data
- debugging scrape fields
- approving purchase orders directly
