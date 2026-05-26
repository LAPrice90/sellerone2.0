# F Scanner Speed Production Plan

Date: 2026-05-01

## Purpose
Increase scanner production speed without increasing Amazon throttling risk, anti-bot risk, or restart/resume risk.

This is a planning document only. No code or live scanner settings were changed by this plan.

## Plain-English Summary
The safe way to speed this system up is not to make more noisy Amazon requests.

The safe way is:
- scan fewer rows that are already known to fail
- batch official SP-API calls where Amazon supports batching
- save reusable Amazon answers so repeated barcodes/ASINs do not re-query
- only open browser pages for rows that survive cheaper checks
- increase chunk size only after resume safety is proven

## Current Evidence
Local scanner evidence shows the active Entertainment Trading run is processing small chunks:
- active chunk size: `5`
- visible speed: about `85 rows/hour`
- F061 is using `price_source=legacy`
- current pricing interval: `30.0 seconds`
- catalog interval: `0.5 seconds`
- hazmat interval: `1.0 seconds`
- fees interval: `1.0 seconds`

Recent child logs show repeated pricing quota messages and large pricing waits. Example chunks show pricing wait totals around:
- `29 seconds`
- `57 seconds`
- `84 seconds`
- `86 seconds`
- `117 seconds`

Recent browser scrape evidence also shows slow or fragile page activity:
- Amazon page renderer timeout
- review page blocked/sign-in/captcha warnings
- scrape attempts on rows that later fail ROI, low sales, or other gates

## Official Amazon Constraints
Amazon SP-API uses a token-bucket rate limit model. If the bucket is empty, requests are throttled.

Amazon also says an operation can have several applicable rate limits, and the request is limited by whichever threshold is reached first.

Important official points:
- `x-amzn-RateLimit-Limit` can tell us the applied operation rate when available.
- Catalog Items v2022-04-01 defaults include `searchCatalogItems` at `2 requests/second` per account-application pair and `500 requests/second` per application.
- Product Pricing `getCompetitiveSummary` allows batched requests but defaults to `0.033 requests/second` with burst `1`.
- Product Pricing v0 `getCompetitivePricing` accepts up to `20` ASINs per request and defaults to `0.5 requests/second` with burst `1`.
- Product Fees batch `getMyFeesEstimates` defaults to `0.5 requests/second`, while single ASIN/SKU fee calls default to `1 request/second`.

## Non-Negotiable Rules
Do not:
- bypass throttles
- ignore 429 or retry-after behavior
- run multiple browser sessions against Amazon pages to multiply scrape pressure
- add proxy rotation, identity rotation, CAPTCHA bypass, or anything that looks like evasion
- raise chunk size blindly while restart/resume safety is still being proven
- hide failed requests or downstream-adjust results to look better

Do:
- obey official rate headers
- back off on 429s and browser block signals
- cache results by stable ASIN/barcode keys
- use batch endpoints where they reduce request count
- measure every change with rows/hour, API calls/row, browser pages/row, 429 count, scrape block count, and pass/fail mix

## Plan
### Phase 1 - Measure The Real Bottleneck
Add a scanner speed ledger that records one row per scanned product with:
- supplier_id
- run_id
- candidate_id
- barcode
- ASIN
- status_reason
- total_seconds
- catalog_seconds
- pricing_wait_seconds
- pricing_call_seconds
- fees_seconds
- hazmat_seconds
- browser_seconds
- browser_attempted_flag
- browser_blocked_flag
- api_429_count
- source_cache_hit_flags

Health checks:
- fail if the speed ledger is missing for a live run
- warn if browser blocked/sign-in/captcha signals appear
- warn if pricing wait is above 40 percent of total runtime

Reason:
We need proof before changing the machine. Right now we can see strong hints, but not enough structured timing to tune safely.

### Phase 2 - Stop Scanning Rows That Memory Already Knows
Extend the process-manager cooldown memory into the live handoff, not just test-mode planning.

Skip before F061 handoff when:
- exact barcode + supplier row is unchanged and still in cooldown
- previous status is long-term fail, such as hazmat, brand fail, history risk, or far-below ROI
- previous fail reason can only be fixed by cost changing, and cost has not changed
- barcode had no ASIN recently and the supplier row has not changed

Keep eligible:
- new barcode
- changed supplier cost
- cooldown expired
- previous result was scrape failure/rescan
- previous result was near threshold

Expected impact:
This should be the largest safe gain on repeat supplier files. It reduces Amazon calls rather than making calls faster.

### Phase 3 - Batch Official SP-API Calls
Move from row-by-row official API calls to staged batch calls where available.

Build the scanner as stages:
1. Barcode to ASIN/catalog stage.
2. Pricing stage.
3. Fees/hazmat stage.
4. Browser evidence stage only for survivors.

Batch opportunities to verify and then implement:
- Catalog: use `searchCatalogItems` in the most efficient supported identifier shape for barcode/ASIN lookup.
- Pricing: test `getCompetitivePricing` v0 with up to `20` ASINs per request against the data we actually need.
- Pricing alternative: test native `getCompetitiveSummary` batch, but because default rate is low, use only if it gives data we cannot get from v0 pricing.
- Fees: use `getMyFeesEstimates` batch for rows that survive pricing/ROI pre-checks.

Important:
Batching must reduce request count. It must not increase request frequency beyond Amazon's returned rate headers.

Expected impact:
If pricing is currently waiting 30 seconds per row or per small group, batching can turn one wait into many ASINs processed. This is the cleanest possible speed improvement.

### Phase 4 - Push Browser Scrape Later
Browser checks should be the expensive final stage, not a default early step.

Only run browser evidence when:
- catalog match is strong enough
- hazmat is acceptable or unknown-but-allowed
- pricing and fees leave possible profit
- sales/rank signal is not already a hard fail
- the row is not blocked by known memory cooldown

If the cheap checks already prove a fail, save the fail and do not open Amazon/BuyBotPro browser pages.

Expected impact:
This reduces Amazon page views and lowers anti-bot risk. It may also improve rows/hour more than any raw timeout tweak.

### Phase 5 - Adaptive Browser Safety
Add browser safety controls:
- if a page shows blocked/sign-in/captcha evidence, stop browser scraping for that run window
- mark affected rows as `RESCAN` or `SCRAPE_COOLDOWN`
- add a browser cooldown clock before trying more browser pages
- cap browser retries per ASIN
- record blocked/signed-in/captcha as health WARN, not as a silent fail

Timeout tuning:
- keep the default page timeout conservative
- allow shorter timeout only after we know which selectors are optional
- do not retry the same blocked page repeatedly in the same run

Expected impact:
Fewer stuck browser sessions and fewer repeated failed page loads.

### Phase 6 - Increase Chunk Size Carefully
Current chunk size is safe but inefficient because each chunk restarts the child process and browser setup.

Controlled rollout:
1. Keep `5` rows until current restart/resume proof is stable.
2. Test `10` rows in an isolated window.
3. If resume markers and drain behavior remain correct, test `20`.
4. Do not go past `50` until the scanner writes per-row progress safely inside a long child run.

Success criteria:
- no duplicate rows after restart
- no lost completed rows after restart
- child process exits cleanly at drain boundary
- UI progress matches active run file
- rows/hour improves without a rise in 429s or browser block warnings

Expected impact:
Chunk increase mostly removes process setup overhead. It does not solve Amazon throttling by itself.

### Phase 7 - Safer Queue Ordering
Process rows in an order that gives faster learning and avoids expensive checks too early.

Recommended order:
1. new/changed rows with clean barcodes
2. rows where supplier cost changed enough to matter
3. previous near-threshold rows
4. previous technical rescan rows
5. long-cooldown or repeated fail rows only when due

Avoid feeding thousands of likely-fail rows through full browser checks when the cheap evidence can reject them.

### Phase 8 - Produce A Speed Dashboard
Add UI fields:
- rows/hour current
- rows/hour last 1 hour
- API calls per completed row
- browser pages per completed row
- 429 count last hour
- browser blocked count last hour
- average seconds by stage
- projected finish time using current speed and last-hour speed

This should sit in the active scanner details area, with only rows/hour and ETA visible on the compact card.

## Suggested Build Order
1. Speed ledger and health checks.
2. Live cooldown skip before F061 handoff.
3. Browser-last staging.
4. Batch pricing proof on a fixed 100-row sample.
5. Batch fee proof on the same sample.
6. Dynamic chunk size trial from 5 to 10 to 20.
7. UI speed dashboard.

## Proof Windows
For every speed change, run a controlled proof with:
- fixed supplier sample
- fixed row count
- old-mode baseline
- new-mode test
- compare rows/hour
- compare PASS/FAIL/RESCAN mix
- compare API calls/row
- compare 429 count
- compare scrape blocked count
- confirm no duplicate or skipped active-run rows

Do not declare success from speed alone. A faster run with more throttles or more browser blocks is not a real improvement.

## Expected Safe Gains
Conservative target:
- Phase 2 and Phase 4: reduce wasted browser/API work, likely meaningful on repeat lists.
- Phase 3 batching: likely the biggest structural gain if pricing/fees data matches current logic.
- Phase 6 chunk size: moderate gain by reducing process/browser setup overhead.

Initial target after Phase 1-4:
- improve from about `85 rows/hour` to `150-250 rows/hour` without increasing 429s or browser block warnings.

Longer-term target after batching and cooldown maturity:
- supplier-dependent, but large repeat files should be much faster because unchanged and long-fail rows should not reach full scan.

## Decision Needed Before Coding
The first coding phase should be:
- build the speed ledger and health checks
- do not change scanner speed yet

After that, use the ledger to choose between:
- batching first
- cooldown skip first
- browser-last first

My recommendation is speed ledger first, then cooldown/browser-last, then batching.
