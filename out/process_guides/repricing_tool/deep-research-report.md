# Buy Box Suppression Strategy for an Automated Amazon Repricing Engine

## Buy Box Suppression Detection

Buy Box suppression is best treated as an **eligibility state** (Amazon will not feature any offer), not as “missing data”. If your engine waits for a visible Buy Box winner, it will freeze exactly in the situations where Amazon is implicitly telling you your *current price* is outside its acceptable range. This is the core architectural mistake to correct.

### What suppression is and why it happens

Amazon’s own policy language frames suppression as a customer-trust protection mechanism: it monitors prices (including shipping), uses statistical models based on historical offer prices, other-retailer prices, and sales data, and can remove the Featured Offer (“Buy Box”), remove the offer, or restrict shipping when pricing practices harm customer trust. citeturn16view0turn16view1

In Amazon’s pricing APIs/notifications, suppression is closely linked to **Featured Offer eligibility** and “pricing health”:

- A `PRICING_HEALTH` event is sent when an offer becomes **ineligible to be the Featured Offer** because of an uncompetitive price; the remediation described is to adjust *total price* (price + shipping − points) to be at/below the competitive price or aligned with provided reference prices. citeturn11view1turn11view0  
- Amazon explicitly distinguishes `PRICING_HEALTH` from “lost to a competitor”: `PRICING_HEALTH` means Amazon cannot select the offer as Featured Offer **at the current price regardless of competitors’ changes**. citeturn1view1

Separate from pricing-health suppression, Amazon also notes that a listing can show “All Buying Options” (no Featured Offer) for other reasons such as being out of stock, price too high, being a new seller, low product sales volume, or even category ineligibility. citeturn6view0

### Detection inputs your engine should rely on

Your current Phase Engine blueprint records that when the Buy Box/outcome is suppressed or unknown, the system **holds** and does not take price action; the enhancement you want is precisely to replace that hold-only behaviour with safe fallbacks. fileciteturn0file0

The strongest detection stack for automation is:

- **Event-led signals (preferred):** Subscribe to `PRICING_HEALTH` and `ANY_OFFER_CHANGED` via entity["organization","Selling Partner API","amazon sp-api"] and consume them off a queue such as entity["organization","Amazon Simple Queue Service","aws sqs"] (this is the workflow Amazon documents for reacting “near real-time”). citeturn11view0turn11view1turn1view1  
- **Snapshot confirmation (secondary):** When you refresh a SKU/ASIN, use competitive-summary/pricing endpoints to confirm whether `buyBoxPrices` exist and whether there are any `buyBoxEligibleOffers`. Amazon’s notification schema describes a summary containing `buyBoxEligibleOffers` and optional `buyBoxPrices`. citeturn14search6turn11view1  
- **Reference-price availability (critical):** Treat any available `competitivePriceThreshold` / “competitive price” / average selling price / WasPrice as *eligibility constraints*, not optional analytics. Amazon states these price points exist specifically to let sellers restore eligibility. citeturn11view1turn11view0turn1view1turn11view2  

### Required classification states (policy output)

Implement a deterministic classification so downstream logic is mechanical:

**Policy: Determine `buy_box_state` per SKU per refresh**
- If `inventory_active == false` → `buy_box_state = OOS` (do not run suppression probes; the causal signal is invalid).  
- Else if a `PRICING_HEALTH` notification is active for this offer with `issueType = BuyBoxDisqualification` → `buy_box_state = DISQUALIFIED_SELF_PRICE`. citeturn11view0turn11view1  
- Else if the latest competitive summary shows `buyBoxEligibleOffers == 0` **or** no Featured Offer price is present (`buyBoxPrices` missing) while offers exist → `buy_box_state = SUPPRESSED_ASIN`. citeturn14search6turn11view1  
- Else if a Featured Offer exists (featured buying option / Buy Box price present) but we are not the winner → `buy_box_state = LOST_TO_COMPETITOR`. citeturn17view0turn6view0  
- Else → `buy_box_state = UNKNOWN` (data outage / incomplete snapshot).  

**Policy: Action eligibility**
- If `buy_box_state in {DISQUALIFIED_SELF_PRICE, SUPPRESSED_ASIN}` → suppression strategy is allowed to run.
- If `buy_box_state == UNKNOWN` → do not probe; degrade to defensive cadence until signals recover (stale/partial data is how repricers create self-inflicted price wars). citeturn11view0turn1view1  

## Buy Box Reactivation Strategy

The design goal is: **restore Featured Offer eligibility with the minimum necessary price movement**, with strict floors, cooldowns, and a reversible ceiling clamp.

### Principle: use Amazon’s own “fail reason” data before guessing

Amazon’s docs are unusually explicit here: the remediation for Featured Offer disqualification is to adjust your offer’s **LandedPrice** (ListingPrice + Shipping − Points) so it matches or falls below the “competitive price” or aligns with provided reference prices; and `PRICING_HEALTH` may include multiple reference prices (including Buy Box price, external threshold, 60‑day average selling price, and more). citeturn11view0turn11view1

So the reactivation ladder should be:

**Policy: Compute `reactivation_target_landed` (strict priority order)**
1. If `PRICING_HEALTH.referencePrices` includes `competitivePriceThreshold` → use it as primary target (it is defined from other retailers and can disqualify offers even if all Amazon sellers are priced similarly). citeturn1view1turn11view1  
2. Else if competitive summary contains a “CompetitivePrice” reference (external reputable retailer price) → use it. This field was added explicitly to help determine Featured Offer eligibility versus external prices. citeturn11view2turn11view0  
3. Else if `PRICING_HEALTH.referencePrices` includes `averageSellingPrice` (60‑day; promotions excluded per Amazon docs) → use it as a conservative “recent price” proxy. citeturn1view1turn11view0  
4. Else if you can obtain FOEP (Featured Offer Expected Price) → use FOEP (it is literally “the computed listing price at or below which a seller can expect to become the featured offer”, before promotions). citeturn1view2turn1view1  
5. Else → fall back to controlled probing (next section).

**Policy: Apply a “win margin”**
- Set `reactivation_target_landed = target_reference_price − epsilon`, where `epsilon` is a minimal decrement intended to avoid equality edge cases (currency/rounding/points).  
- `epsilon` should be:  
  - Small-and-light / sub‑£10 style SKUs: a penny-level decrement.  
  - Higher-ticket: a minimal economically irrelevant decrement (you are not “undercutting”, you are clearing an eligibility threshold).  

### Why competitor prices can be irrelevant during suppression

A key reason your listed SKUs can all be “near competitor price” yet still suppressed is that the **Competitive Price Threshold is derived from other retailers, excluding other Amazon sellers**—so it can be below all in-market Amazon offers, producing “no Featured Offer” across the ASIN. citeturn1view1turn17view0

This is why a Buy Box winner signal can disappear without an obvious Amazon competitor move, and why “match competitor” logic can fail to reactivate eligibility.

### Reactivation execution policy

**Policy: Enter `STATE_SUPPRESSION_REACTIVATION` when either:**
- `buy_box_state = DISQUALIFIED_SELF_PRICE`, or
- `buy_box_state = SUPPRESSED_ASIN` for ≥ 2 consecutive refreshes (to avoid reacting to transient scrape gaps). citeturn11view1turn11view0  

**Policy: While in `STATE_SUPPRESSION_REACTIVATION`**
- Objective is **eligibility restoration**, not profit argmax.  
- Price moves must be floor-protected and cooldown-limited (see Guardrails).  
- Use the `reactivation_target_landed` if available; do not waste probes when Amazon already provided a threshold. citeturn11view0turn11view1  

**Policy: Exit conditions**
- Exit to normal optimisation state when BOTH are true:
  - competitive summary shows at least one Buy Box / Featured Offer price again OR Buy Box eligible offers > 0, and
  - our offer is no longer under an active BuyBoxDisqualification event (no active `PRICING_HEALTH` disqualification for our offer). citeturn14search6turn11view1turn11view0  

## Price Discovery Method

This section covers the “hard case”: the Buy Box is suppressed, and you lack a usable reference price (no CPT, no CompetitivePrice, FOEP unavailable/inapplicable), yet you still need to find the hidden clearing threshold.

Amazon’s own docs do not guarantee that all reference prices will exist for all ASINs/SKUs (CPT is explicitly “if available”, and FOEP has constraints). citeturn11view0turn1view2turn1view1

### Separate two different “thresholds” you may be encountering

In practice, suppressed listings often have two economically relevant breakpoints:

- **Eligibility threshold (Featured Offer reactivates):** the price at/below which Amazon will again feature an offer. This is what `PRICING_HEALTH` typically encodes. citeturn11view1turn11view0turn1view1  
- **Conversion threshold (sales start happening even without Featured Offer):** because customers can still buy via “All Buying Options”, a lower price may restore *some* conversion even if eligibility remains shaky. Amazon itself notes that even when it does not promote an offer as Featured Offer, the offer can remain available for customers to purchase. citeturn17view0turn6view0  

Your engine should explicitly decide which signal it is optimising for during discovery.

### Core probing design: bracket, don’t drift

A safe discovery method looks like “find any success, then tighten the bracket”, not “walk down forever”.

**Policy: Initialise a `suppression_probe_window`**
- Start when entering `STATE_SUPPRESSION_REACTIVATION` without a usable reference price.
- Record:
  - `probe_start_landed`, `hard_floor_landed`, `probe_floor_landed` (see Guardrails),
  - market structure signature (offer count, fulfilment mix), and
  - whether any promotions/coupons are suspected (because that contaminates inference). citeturn16view0turn11view1turn20view0  

**Policy: Define “success” for the probe window**
- Primary success: Featured Offer becomes available again OR `buyBoxEligibleOffers` rises above 0. citeturn14search6turn11view1  
- Secondary success (optional, only if you have clean order telemetry): sustained unit sales improvement in a fixed observation window, without major market structure drift. (This is an inference; Amazon does not publish a “sales threshold”, so treat it as your internal signal.) citeturn17view0  

### Step-down schedule (safe, fast enough, not reckless)

**Policy: Generate a bounded downward step plan**
- Let `gap = current_landed − probe_floor_landed`.  
- Choose step sizes that are larger when far from the floor, smaller near it:
  - Far zone: up to 5–10% of current price per step (capped by max daily cut).  
  - Near zone: tiny steps (pence-level for low-ticket; <1% for higher-ticket) to avoid overshooting the threshold and creating unnecessary low anchors. citeturn11view0turn16view0turn11view2  

**Policy: Hold and observe**
- After each downward step, hold price until you receive either:
  - a confirming refresh snapshot, or
  - a relevant notification (`PRICING_HEALTH` state change / `ANY_OFFER_CHANGED` external price change / Featured Offer change). Amazon documents both the event-driven workflow and that `ANY_OFFER_CHANGED` can be triggered by external price changes and Featured Offer changes. citeturn11view0turn11view1  

### Bracketing logic (what you store as you probe)

Treat eligibility as a step function: eligible at/below some threshold, disqualified above it.

**Policy: Maintain two bounds**
- `lowest_ineligible_landed` (LI): the lowest landed price you tried that was still disqualified/suppressed.  
- `highest_eligible_landed` (HE): the highest landed price you tried that restored eligibility / Featured Offer existence.  

**Policy: When you find HE**
- Stop the *downward* probe immediately (do not keep cutting just because you can).  
- Transition to “ceiling recon” (upward) to find the highest feasible price that remains eligible, using very small steps and long enough holds. This avoids permanently anchoring too low. citeturn11view2turn16view0turn20view0  

### When to declare the threshold “not discoverable safely”

Some suppressions are driven by erroneous or mismatched external price comparisons (seller community reports this frequently), and you can lose enormous margin chasing a phantom. Your automation must be able to refuse.

**Policy: Abort discovery and require manual review if any is true**
- `probe_floor_landed` reached and still suppressed/disqualified.  
- The implied threshold would force pricing below your hard floor or below a defined “anchor floor” by more than a small allowance (see Guardrails). citeturn16view0turn11view0  
- External threshold volatility is detected: the disqualification target swings materially across short windows (a sign the comparator is unstable or wrong). citeturn11view0turn11view1  

## Ceiling Adjustment Rules

Your own masterplan already separates three different ceilings—compliance, eligibility, and demand—and requires ceilings to clamp before optimisation. That separation is exactly what suppressed Buy Box handling needs: suppression is fundamentally an **eligibility ceiling crash**, and the engine should respond by tightening eligibility space, not by freezing. fileciteturn0file1

### Suppression should create a temporary eligibility ceiling

**Answer to the research question:** Yes—suppression should trigger a new temporary ceiling, because suppressions are frequently caused by pricing being above an implicit eligibility cap derived from external prices and/or recent price history. Amazon’s own docs define both the “robust statistical models” that use historical and external prices and the notification-level instruction to reprice to competitive/reference prices. citeturn16view0turn11view1turn11view0  

### How to set the temporary ceiling mechanically

**Policy: Create `suppression_ceiling_landed_temp`**
- If you have a reference price from `PRICING_HEALTH` / competitive summary / FOEP:
  - `suppression_ceiling_landed_temp = reference_price` (not “reference + margin”; this ceiling is a compliance/eligibility boundary, not a target).
- If you only have a learned HE/LI bracket from probing:
  - `suppression_ceiling_landed_temp = HE` (highest eligible price observed).
- Always clamp it by:
  - `suppression_ceiling_landed_temp ≤ existing_final_ceiling_landed` (do not widen space during a suppression event). fileciteturn0file1  

**Policy: Make the ceiling expire**
- Set `suppression_ceiling_expiry_utc` (recommended: 3–7 days depending on SKU cadence), because external thresholds can change when other-retailer prices change. Amazon explicitly ties eligibility to external competitive prices and provides notifications for such changes. citeturn11view0turn1view1  

### Post-reactivation ceiling behaviour (avoid immediate re-suppression)

A common failure mode is: lower price → regain eligibility → optimisation immediately lifts price → re-triggers suppression.

**Policy: Apply a “suppression cool-off band” after reactivation**
- For a fixed window (e.g., 24–72 hours), do not allow the optimiser to price above:
  - `min(suppression_ceiling_landed_temp, suppression_reactivation_price + small_uplift_step)`
- The uplift step must be strategy-tag dependent (your v9 plan already requires segmentation, and low-ticket SKUs should step more cautiously). fileciteturn0file1  

## Safe Guardrails

Suppression handling is one of the easiest places for repricers to create long-term damage (anchors, yo-yo, margin collapse). Guardrails are not optional.

### Policy and compliance constraints

**Policy: Hard floor is absolute**
- Never breach your hard floor, even in suppression mode. (Your programme’s governance already treats the hard floor as “sacred”.) fileciteturn0file1  

**Policy: Respect “customer trust” triggers**
- Avoid behaviours Amazon names as harmful to customer trust: prices significantly higher than recent prices on/off Amazon, excessive shipping fees, misleading reference prices, and per-unit pack pricing anomalies. citeturn16view0turn16view1  

### Anchor protection (the thing most repricers get wrong)

Amazon’s pricing systems rely on historical purchase prices in multiple ways. For example, Amazon introduced “WasPrice” (90‑day median price paid by customers) as a reference price in pricing APIs to support promotions and discounts, which is an explicit acknowledgement that past realised prices become future benchmarks. citeturn11view2  

Separately, Amazon’s promotions guidance warns that deal/discount eligibility is tied to the past 30‑day low and that current promotions can influence future promotional benchmarks (i.e., you can race to the bottom against yourself). citeturn4search20  

**Policy: Define an “anchor floor” distinct from your hard floor**
- `anchor_floor_landed = max(hard_floor_landed, lowest_landed_price_last_30d − allowance)`  
- In suppression probes, do not go below `anchor_floor_landed` without an explicit “override reason code” (manual review / capital strategy). This directly reduces the risk of permanently resetting benchmarks and harming future ceiling recovery. citeturn11view2turn4search20turn16view0  

### Rate, step size, and cooldown safety

Amazon itself documents event-driven workflows; probe logic should therefore be driven by **state changes**, not a rapid-fire cadence that burns API budget and creates volatility. citeturn11view0turn1view1  

**Policy: Downward movement caps**
- Set:
  - `max_step_down_per_move` (hard clamp),
  - `max_step_down_per_day` (hard clamp),
  - `min_cooldown_between_moves`.  
- In suppression mode, you may allow slightly faster descent than normal *only if* you are still above the anchor floor and above any ROI-loss constraints you have set for that phase. (Your current Phase Engine explicitly avoids artificial throttles in competitive descent; do not replace them with uncontrolled probing.) fileciteturn0file0  

### Category and fulfilment differences (and why they matter here)

Amazon states Featured Offer eligibility criteria can vary by category, and that delivery speed and shipping posture are key. citeturn6view0turn17view0  
FOEP explicitly notes that Featured Offer is not guaranteed and can depend on fulfilment capabilities for a specific customer, implying segment-level variation. citeturn1view2turn1view1  

**Policy: Store suppression thresholds by offer posture**
- At minimum, key “suppression memory” separately for:
  - fulfilment channel (FBA vs FBM),
  - shipping price model (if FBM),
  - condition (New vs other).  
This avoids learning a threshold in one posture and applying it incorrectly to another. citeturn6view0turn1view2turn11view1  

### Explicit “do not chase phantom thresholds” rule

Third-party monitoring tools and seller community reports acknowledge a recurring pattern: suppression can be triggered by external price comparisons, and promotional activity followed by returning to regular price can re-trigger suppression; this is consistent with Amazon’s emphasis on external prices and historical benchmarks. citeturn20view0turn16view0turn1view1  

**Policy: Phantom threshold detection**
- If:
  - the implied eligibility price is economically impossible (below fees/cost floor by a large margin), or
  - the implied external price moves erratically across short windows,
- then:
  - freeze at `max(hard_floor, anchor_floor)` and emit `MANUAL_REVIEW_REQUIRED_EXTERNAL_PRICE_SUSPECT`.  
This avoids automated margin suicide.

## Learning Logic

Your v9 masterplan already includes a strong learning-integrity principle: optimise aggressively if you must, but do not learn aggressively; and it introduces a truth-filter (Outcome Admissibility) concept to prevent corrupting memory during unstable conditions. fileciteturn0file1  

Suppression handling needs its own learning channel: you do want to learn the eligibility threshold, but you must keep it quarantined from competitor-delta learning and profit-curve learning.

### What to log (minimum viable, but decision-grade)

**Policy: Every suppression episode creates a `suppression_case_id` with:**
- `start_utc`, `end_utc`, `sku`, `asin`, `marketplace`,
- `buy_box_state` sequence over time,
- all reference prices observed (typed: CPT, CompetitivePrice, averageSellingPrice, WasPrice, retailOfferPrice, FOEP),
- price actions taken (landed), with reason codes,
- probe outcomes (eligible/ineligible) and observation windows,
- market structure summary (offer count, fulfilment mix) to detect drift.

This is essential because Amazon’s own systems can change the benchmark inputs (external prices, sales-derived WasPrice, etc.). citeturn11view0turn11view2turn16view0  

### How to update “suppression threshold memory”

**Policy: Maintain a bracketed estimate**
- Fields:
  - `suppression_HE_landed` (highest eligible),
  - `suppression_LI_landed` (lowest ineligible),
  - `suppression_threshold_est_landed` (derived midpoint or HE),
  - `confidence`,
  - `source` (`CPT|CompetitivePrice|FOEP|ProbeBracket|CarryForward`),
  - `last_validated_utc`.

**Policy: Confidence rules**
- Highest confidence: CPT / CompetitivePrice / PRICING_HEALTH-provided reference prices (direct Amazon signals). citeturn11view1turn11view0turn1view1  
- Medium confidence: FOEP (useful but not guaranteed; customer/segment dependent). citeturn1view2turn1view1  
- Lowest confidence: probe-derived brackets (because market structure can drift and because some suppressions are driven by erroneous external comparisons).

### Retest cadence (answering the “how often” question)

**Policy: Retest triggers (event-led, not calendar-led)**
- Immediate retest when:
  - `ANY_OFFER_CHANGED` indicates external price or Featured Offer changed (Amazon’s workflow guide includes external price changes and Featured Offer changes as triggers). citeturn11view0turn1view1  
  - a new `PRICING_HEALTH` disqualification arrives. citeturn11view1turn11view0  

**Policy: Scheduled retest (fallback)**
- If no events arrive:
  - High-value / high-cadence SKUs: validate suppression ceiling daily (A-cycle style).  
  - Low-value / stable SKUs: validate weekly.  
Reason: competitive external prices can change outside Amazon at any time, and Amazon explicitly bases disqualification on those external prices and recent prices. citeturn1view1turn16view0turn11view2  

### Interaction with your broader learning systems

Your masterplan’s learning integrity spec treats Buy Box suppression as a hard contaminant for general causal learning (because the market outcome signal is structurally altered). Keep that: do **not** update seller reaction/delta learning or demand-ceiling learning with windows that include suppression, except for the suppression-threshold model itself. fileciteturn0file1  

**Policy: Learning update gates**
- If suppression is active at any time in a learning window:
  - Block: competitor delta updates, aggressor classification updates, demand elasticity updates.  
  - Allow: suppression threshold bracket update, but only if market structure did not materially change during the probe window and no promotions are contaminating the price paid signal. citeturn11view1turn4search20turn11view2