# F Cycle Backtest Working Notes

## Purpose

This file is the working home for the real design of the F cycle price history and backtesting system.

The goal is to define:
- what story we want the chart history to tell
- which settings must be changeable
- which functions the system must include
- how backtesting links to live repricing
- how this later becomes a practical build map

This is a planning file only.
No implementation decisions are final until they are proven and agreed.

## Core Direction

We want one shared settings model that powers:
- sourcing / new product checks
- historical backtesting
- live repricing behaviour

The main idea is:
- the market history gives us the evidence
- the settings define how we react to that evidence
- the backtest tells us what would have happened under those settings
- the live repricer then follows the same rules in real operation

That means the history tool and the repricer should not be separate logic systems.
They should use the same policy story.

## Plain-English Goal

Before we buy a product, we want to know:
- what the market has looked like
- how often the listing sat in good or bad ROI ranges
- whether the listing usually supports our normal target margin
- whether it only works as an exit / sell-off listing
- whether our repricing strategy would likely survive on that listing

After we already own stock, we want the same settings to guide:
- protection mode
- competitive mode
- compression mode
- exit mode
- liquidation mode

## First Principles

### 1) Separate raw history from judgement

We must keep these as separate layers:

- Layer 1: raw market history
- Layer 2: policy settings
- Layer 3: backtest result

Raw history means what actually happened in the chart.
Policy settings mean how we choose to react.
Backtest result means what our strategy would have done in that history.

We do not want to mix those together too early.

### 2) One shared policy story

If the sourcing tool says a listing is good, but the live repricer uses different rules, the system becomes misleading.

So the same policy must feed:
- sourcing checks
- scenario analysis
- repricing behaviour

### 2.5) Backtesting is insight, not control

Backtesting must not directly change live settings.

The correct model is:
- we control the settings
- the backtest reads those settings
- the backtest shows what would have happened
- we use that evidence to improve settings manually

So backtesting is a decision-support tool.
It is not an auto-controller.

### 3) Function first, design later

The UI matters, but the rules and calculations must be correct first.

The expectation is that this will later appear in the same interface area as restocking, with a dedicated section for backtest and pricing policy settings.

## Expected UI Direction

The expectation by the end of this project is:
- a UI section inside the interface we already use for restocking
- changeable settings for the pricing policy
- the ability to review history using the current live settings
- the ability to compare alternate settings before changing live behaviour

The important rule is:
- the UI should be changing policy inputs
- not inventing separate logic for backtesting vs repricing
- not auto-editing live settings from backtest results

## Main Question This System Must Answer

For any ASIN, SKU, or candidate product:

- if we had used our current pricing settings on this history, what story would the listing tell?

That story should include:
- margin opportunity
- capital risk
- time trapped in weak ranges
- time spent below floor
- likely need for exit behaviour
- likely compatibility with our repricing strategy

## Raw History Inputs We Want

These are the market facts we want to capture where available:

- Buy Box history
- lowest FBA history
- lowest FBM history
- Amazon price history
- who held the Buy Box if available
- offer count history
- BSR history
- review history where useful
- current break-even based on our cost model

## Policy Settings We Expect To Need

These are the kinds of settings we likely want to make changeable:

- entry target ROI
- working floor ROI
- exit floor ROI
- emergency floor ROI
- target ROI for normal selling
- minimum acceptable ROI
- break-even threshold
- tolerated low-ROI band
- tolerated loss band for controlled exit
- grace period after restock
- phase timings for repricing escalation
- fast-track conditions
- Amazon presence penalty
- FBA vs FBM weighting
- recency weighting
- streak sensitivity
- required recovery strength after a bad period

## Initial ROI Band Thinking

Current thinking:

- less than 0% = negative market state
- 0% to 10% = exit / low-risk capital recovery zone
- 10% to 20% = acceptable but weaker selling zone
- 20% plus = preferred working zone

Important note:
- these bands are not just pass/fail
- they tell us what type of listing this is

The deeper policy interpretation is likely:

- entry target ROI = the buy decision target
- working floor ROI = the normal operating floor
- exit floor ROI = the controlled capital recovery floor
- emergency floor ROI = the late live repricing damage-control floor

Important protection rule:
- late-stage repricing tolerance must not leak back into sourcing approval
- in plain English, we do not want weak listings to pass just because live repricing can eventually manage an ugly exit

Example:
- a listing that lives mostly in 10% to 20% may still be valid
- a listing that spends long periods below 10% may only be suitable as an exit-risk listing
- a listing that spends long periods below 0% is likely structurally dangerous

## Functions We Want To Include

### A) Market history view

Show the actual chart story:
- price history by channel
- Buy Box story
- competitor pressure
- Amazon presence
- BSR direction

### B) ROI range analysis

Translate the history into:
- days in each ROI band
- weighted time in each band
- longest streak in each band
- recent vs older comparison
- phase-aware interpretation of each band

### C) Backtest engine

Given a policy setting profile, replay the history and estimate:
- when we would protect margin
- when we would compete
- when we would compress margin
- when we would switch to exit logic
- when we would likely sit still and not sell
- probability of reaching key acceptable sell windows by phase

### D) Strategy compatibility score

Answer:
- does this listing suit our current repricing policy
- does it only work under more aggressive settings
- does it look unsafe regardless of settings

### E) Compression risk view

We should likely measure:
- ROI at Buy Box
- ROI at lowest FBA
- the gap between them

That gap is useful because a listing can look healthy at Buy Box price, but become unattractive once real FBA competition tightens.

So the Buy Box versus lowest FBA gap is an early signal of compression risk.

### F) Buy Box ceiling view

We should test whether the chart suggests a practical Buy Box ceiling.

Plain-English meaning:
- is there a price level where the Buy Box often disappears
- is there a price level where a certain seller type stops holding the Buy Box
- is there a price level where price can continue printing but Featured Offer visibility appears to cut off

If this is real, it could become a very useful automation input.

Example:
- if history shows that once price rises above a certain level the Buy Box regularly disappears, then that ceiling matters even if margin looks attractive on paper

This should be treated carefully as an evidence-based pattern, not assumed too early.

### G) Settings comparison

Compare:
- current live profile
- safer profile
- more aggressive profile

### H) Recommendation summary

Plain-English answer such as:
- good fit for normal strategy
- workable but needs looser margin settings
- only acceptable as a controlled exit listing
- avoid

## Questions We Still Need To Settle

- How much weight should Buy Box history get versus lowest FBA?
- When FBM is cheaper but not winning, how much should that matter?
- How do we treat Amazon being present?
- How do we reduce the weight of older Amazon behaviour without ignoring it?
- Do different seller types appear to hit different practical Buy Box ceilings?
- Does the Buy Box disappear above certain price levels or price gaps?
- Do we score by total days in band, longest streak, or both?
- How should we weight recent history against older history?
- How do we allow for inflation and rising market prices over time?
- Should we score by average opportunity or by worst-case risk?
- How do we represent likely sell-through rather than just price viability?
- How do we measure "sat there not selling" in a truthful way?

## Early Planning Shape

### Stage 1

Collect and define:
- the exact history inputs
- the exact policy settings
- the output questions we want answered

### Stage 2

Define the practical logic:
- formulas
- state transitions
- thresholds
- scoring method

### Stage 3

Turn that into:
- a practical system map
- implementation plan
- UI plan

## Current Working View

The direction currently makes sense.

The key principle is:
- we want to check the market story using our live settings

That means:
- the backtest should read the same policy story as live repricing
- the repricer should not become detached from the sourcing and backtest logic

## Additional Takeaways From Extended Pro Thinking

These are the main extra points worth keeping from `ExtendedProThinking.md`.

### 1) Four-threshold policy structure

This is a useful refinement of the earlier ROI-band thinking.

The likely structure is:
- entry target ROI
- working floor ROI
- exit floor ROI
- emergency floor ROI

This is useful because it separates:
- buy discipline
- normal operation
- planned exit behaviour
- true damage control

### 2) Phase-hit rates should be core outputs

The backtester should not only produce scores.
It should show how the repricing policy would behave over time.

Useful outputs likely include:
- phase 2 hit rate
- phase 3 hit rate
- phase 4 hit rate
- median realised ROI
- median days to sale
- max adverse margin excursion
- capital days locked
- exit without loss rate

This is important because it ties the backtest directly to your existing H ladder.

### 3) Rolling start-date backtest method

This is an important practical point.

The best backtest structure is likely:
- pick a historical start date
- decide if the product would have passed on that date using only information available then
- if yes, simulate owning it from that point onward
- replay the pricing policy forward through the next period
- record outcome
- repeat across many historical start dates

This is much stronger than simply scoring the chart as one static block.

### 4) Capital lock-up should be a first-class output

This wording is useful and fits your business need well:
- capital days locked

That is clearer than speaking only about low ROI.

It helps the system answer:
- not just "was margin weak?"
- but "how long would our cash likely have been tied up?"

## Additional Takeaways From Pro Thinking

These are the main extra points worth keeping from `proThinking.md`.

### 1) Phase-aware ROI scoring

This is one of the best additions from the file.

The same ROI band should not mean exactly the same thing at every stage.

Example interpretation:
- 0% to 10% early in the holding period is usually weak
- 0% to 10% later in the lifecycle may be acceptable as an exit outcome

So ROI band meaning should depend on timing and phase, not only the raw percentage.

### 2) Outcome probabilities are better than static chart judgement

The backtest should ideally report outcome-style answers, not just a flat score.

Useful examples:
- probability of reaching 20% ROI by day 35
- probability of reaching 10% ROI by day 60
- probability of reaching break-even or better by day 90
- fast-track rate
- liquidation rate
- median days to first valid sell window

This is a stronger way to describe the market story than saying the chart average looked fine.

### 3) Seller-type weighting may matter

This file adds a useful detail:
- different seller types holding the Buy Box may need different interpretation weights

Potential examples:
- FBA holding Buy Box may be the strongest signal
- FBM holding Buy Box may still matter, but differently
- Amazon holding Buy Box may need a heavy risk haircut
- unclear or missing Buy Box may indicate uncertainty rather than a clear opportunity

This connects well to your new research question around seller-type behaviour and Buy Box cut-off patterns.

### 4) Walk-forward decisions should be based on outcomes, not just bands

The useful practical idea here is:
- band scoring can help internally
- but the final judgement should lean on simulated outcomes

That means the system should prefer answers like:
- how often would this have stayed healthy
- how often would this have needed fast-track exit
- how often would it have ended in liquidation pressure

### 5) Optimisation should be multi-objective later on

This mainly matters for a later phase, but it is worth keeping:
- optimisation should not chase gross profit alone

It should also consider:
- capital days locked
- forced exits
- negative ROI outcomes
- worst-case outcomes

## New Research Questions To Test Next

These are now important next-step research questions:

- how different seller types affect Buy Box behaviour
- whether there is evidence of a practical Buy Box ceiling
- whether the Buy Box disappears beyond certain price levels
- whether the ceiling changes depending on Amazon, FBA, or FBM presence
- whether a listing can look profitable on paper while being effectively ineligible for Featured Offer above a certain price
- how inflation and rising market prices over time should be handled so older history is not treated too literally

## Working Theory On Ceiling And Inflation

These are not confirmed rules yet, but they are important working ideas.

### Buy Box ceiling theory

There may be cases where:
- the listing can show higher market prices
- but the Buy Box stops appearing or stops being held above a certain level

If that pattern is real, then it could be a major sourcing and repricing input.

In plain English:
- a product might look like it can make margin at a higher price
- but if Amazon or the market effectively refuses to grant Featured Offer at that level, the apparent margin is not fully real

### Sellable price ceiling theory

There may also be a difference between:
- a price that appeared on the chart
- a price that still supported real sell-through

This matters because a listing can temporarily print a very high price and show a huge paper ROI, but that does not mean customers actually bought at that level.

So we likely need a "sellable ceiling" concept, not just a visible price ceiling.

### Inflation / price drift theory

Older prices cannot always be treated as directly comparable to current prices.

Reasons include:
- supplier cost inflation
- general market inflation
- changing fee environments
- gradual repricing of the whole listing over time

So later analysis may need:
- recency weighting
- rolling-window comparisons
- trend-aware ceiling logic
- a way to avoid treating old cheaper periods as the main truth when the whole market has moved upward

## Additional Treatment Rules We Are Likely To Need

### 1) Age-of-history should fade, not disappear

Older history still matters, but it should not be treated as equally serious as recent history.

Example:
- if Amazon was on the listing 8 months ago at a very low price, that is still a risk signal
- but it should not hit as hard as Amazon being active at that price in the last 30 to 90 days

The likely correct treatment is:
- recent history = strongest signal
- mid-age history = moderate signal
- old history = warning context, not equal-weight truth

In plain English:
- do not ignore old danger
- do not let old danger dominate recent reality

### 2) Amazon must be treated differently from FBA and FBM sellers

Amazon is not just another seller line.

Working assumption:
- Amazon does not behave like a normal competing seller
- Amazon may return at prices that normal FBA or FBM sellers would not sustain
- if Amazon returns at a low level, it can collapse the usable market very quickly

So Amazon should be treated as a separate risk actor, not just another price input.

### 3) Competing with Amazon is not the same as competing with FBA or FBM

With normal FBA or FBM competition, we may have room to:
- reprice
- probe
- compress margin
- hold position

With Amazon, the practical logic may be different:
- avoid assuming normal competitive response
- avoid undercutting strategies built for ordinary sellers
- apply a much higher risk haircut when Amazon has a history of returning below our floors

This means the system should likely distinguish between:
- ordinary market competition
- Amazon override risk

### 4) Amazon return risk should be part of the sourcing story

If Amazon previously sat on the listing at a price that would now put us into loss territory, that should remain part of the sourcing assessment even if it is older.

But the severity should likely depend on:
- how recent it was
- how long Amazon stayed
- how deep the price suppression was
- whether the market recovered after Amazon left

Important clarification:
- old Amazon pricing should not be treated as current target pricing
- but it should be treated as a meaningful warning if it would destroy our exit path

In plain English:
- if Amazon was at a small-loss or low-recovery level a long time ago, that may still be manageable as warning context
- if Amazon was at a deeply negative level such as around `-50% ROI`, that is a serious structural warning even if it was 11 months ago

Reason:
- that kind of Amazon return can leave us trapped without a realistic exit strategy
- we may then be forced to wait months for recovery or sell far below acceptable recovery levels

### 5) Possible practical treatment model

One likely way to handle this later:

- recent Amazon activity = heavy penalty
- medium-age Amazon activity = moderate penalty
- old Amazon activity = warning penalty
- recent non-Amazon FBA/FBM pressure = normal competition penalty
- old non-Amazon competition = lower-weight context

This would let us keep the information without pretending all old events are equally important.

### 6) Variant relationship data should beat review-share estimates when available

If we can pull cleaner variant / child relationship data, we should use it.

Reason:
- review share is useful
- but review share is only an estimate
- it is not strong enough on its own to prove how much demand belongs to our exact child or offer

So the likely hierarchy should be:
- direct variant / child relationship data when available
- direct offer-level evidence when available
- review share as fallback context
- parent-level demand only as supporting evidence

### 7) Review share is a fallback, not the final truth

Review percentage can still help because it gives some clue about how much of the parent-level demand may belong to a variant.

But it has limits:
- reviews lag sales
- different products get reviewed at different rates
- one variant may attract review activity differently from another
- parent-level strength can mask weak demand on our exact child

So for planning purposes:
- keep review share
- use it as a confidence signal
- do not let it act as sole proof of likely sell-through

## Ceiling And Demand Response Thinking

### 1) A printed price is not automatically a usable price

We do not want the history to be washed out by extreme prices that were visible but not truly sellable.

Example:
- the item normally sells around GBP 10 with workable ROI
- the chart later shows GBP 40 or GBP 50
- that does not automatically mean the market accepted that higher price

So a high historical ROI number must not be trusted on its own.

### 2) We likely need a max usable ROI concept

This does not mean placing a random cap on ROI.
It means asking:
- at what point does price stop behaving like a realistic selling price?

That likely becomes a history-specific concept, not one global rule for every product.

### 3) BSR response may help identify the true ceiling

Your idea here is strong.

The ceiling may be estimated by looking at what happens after price jumps:
- if price rises sharply and BSR worsens quickly, that suggests demand fell away
- if price rises and BSR stays strong, the higher price may still be sellable
- if BSR worsens only slowly, we may be looking at lag rather than an immediate hard cutoff

So the useful question is not only:
- did price go above this level?

It is also:
- what happened to the demand signal after price moved there?

### 4) The ceiling may be gradual, not binary

This is likely important.

Instead of a simple yes/no cutoff, the system may need to detect:
- strong demand zone
- weakening demand zone
- collapse zone

In plain English:
- some products may lose demand gradually as price climbs
- other products may hit a sharp cliff where sellability drops hard

So we should think in terms of a response curve, not only a hard threshold.

### 5) Practical analysis idea

Later, the history engine may need to analyse:
- price level
- subsequent BSR movement
- rate of BSR deterioration
- duration spent at the higher price
- whether Buy Box remained visible
- which seller type held the Buy Box during that price

This could help classify:
- likely sellable price range
- stretched price range
- probable unsellable price range

### 5.5) Demand attribution risk must be handled carefully

A major danger is assuming that observed demand on the listing happened at our usable price.

Example:
- the listing may show strong overall sales activity
- low prices may be doing the real selling
- high prices may simply be appearing on the chart without converting

That means the system must avoid assuming sales were evenly distributed across all observed prices.

### 5.6) Parent ASIN / variation contamination risk

BSR can be useful, but it may not cleanly prove that our exact variant or offer sold at the observed price.

On variation listings, a false story could happen:
- another child variation sells well
- the parent-level rank stays strong
- our own child is overpriced and not converting
- the system wrongly believes the higher price is still sellable

So for planning, BSR should be treated as:
- supporting evidence
- not final proof of sellability at our exact price

Variation contamination should reduce confidence in any ceiling or sell-through conclusion.

### 6) Why this matters for sourcing and repricing

For sourcing:
- we do not want inflated historical price spikes to make a listing look better than it really is

For repricing:
- we do not want the engine drifting upward into a price zone that looks profitable on paper but is unlikely to win sales

### 7) Working direction

The likely correct direction is:
- do not use a binary ceiling only
- estimate a practical sellable ceiling using price plus demand response
- let BSR and Buy Box behaviour help decide whether a higher price was actually usable
- reduce confidence when parent-level or variation-level demand may be masking weak sell-through on our exact offer

## Open Notes

- Add ideas here as they come up.
- Add useful concepts from research files here.
- Promote repeated ideas into a later practical map once they are stable.

## Deep Research Takeaways

These points are the practical takeaways from `deepResearch.md`.

### 1) Price history and repricing must share one policy story

This is one of the strongest takeaways.

If price history is judged using one logic system, but live repricing uses another, the system becomes misleading.

So the correct direction is:
- one shared pricing policy
- one backtest that reads that policy
- one live repricer that reads that policy
- manual owner control over policy changes

### 2) The chart is not just a chart

The history should be treated as a market timeline, not just a list of prices.

That means we want to read:
- Buy Box behaviour
- FBA behaviour
- FBM behaviour
- Amazon presence
- BSR movement
- signs of demand strength or weakness

The value is in the story of the market, not just the average price.

### 3) Average ROI alone is not enough

The research supports a point that fits your own thinking:
- the danger is not only bad prices
- the danger is getting trapped in weak ranges for too long

So we should care about:
- percent of time in each ROI band
- longest streak below 10%
- longest streak below 0%
- recent weakness vs older weakness

This supports the idea that long bad streaks matter more than isolated bad days.

### 4) Buy Box matters most, but not alone

The deep research supports using Buy Box as the primary signal, but not the only signal.

Working interpretation:
- Buy Box = main market opportunity signal
- low FBA = strong competitive support signal
- low FBM = context signal
- Amazon presence = separate risk overlay

This means Amazon presence should probably be treated as a penalty or warning factor, not just another price line.

### 5) We need two headline scores, not one mystery score

This is one of the best practical simplifications from the research.

Instead of one unclear total score, we should likely think in two top-level outputs:

- Market Viability Score
- Exit Risk Score

Plain-English meaning:
- Market Viability Score = how often this listing supports our normal business model
- Exit Risk Score = how bad it gets when the market turns against us

This fits your thinking well because it separates:
- "can we sell this normally?"
- "if it goes wrong, how ugly is the escape path?"

### 6) Sell-through matters, not just margin

The research correctly points out that price viability is not the same as selling.

That matches your own concern:
- a listing may sit in weak ROI bands without actually moving

So later versions should try to include some form of sell-through logic.

For now, the planning position should be:
- v1 must be truthful about margin opportunity and trap risk
- later versions can estimate sell-through and expected liquidation time

### 7) Optimisation is a later phase, not the first phase

The research supports optimisation, but the practical lesson is:
- do not start there

The first version should do 3 things well:
- capture history correctly
- replay your chosen policy correctly
- report the results clearly

Only after that should we think about:
- comparing profiles in a deeper way
- parameter search
- optimisation

### 8) The UI should revolve around one Policy Profile

This is consistent with the direction already written in this file.

The interface should expose one policy profile that controls:
- sourcing acceptance logic
- backtest interpretation
- live repricing behaviour
- exit behaviour

The UI should not create a separate world for backtesting.

## Practical Build Meaning From Deep Research

If we turn the deep research into practical build direction, it means:

- build a shared policy model first
- keep raw history separate from scoring and simulation
- make Buy Box the main signal, with FBA/FBM/Amazon as supporting context
- measure trap duration, not just average ROI
- separate viability from exit risk
- keep optimisation and advanced demand modelling as later phases

## Output Pattern Findings From Subagent Pass

Date run: 2026-04-10 (UTC day)

This section records what we found from current outputs.

Important scope note:
- this pass is useful, but the evidence is still limited in key areas
- treat findings as directional until we widen coverage

### Dataset coverage reality

- `out/analysis_reports/f_scrape_history_review_latest.csv` currently has 4 rows (4 ASINs)
- `out/listing_offer_history.csv` has 2,007 rows (95 ASINs)
- `out/listing_offer_seller_observation_history.csv` has 10,510 rows (94 ASINs)

This means:
- ceiling and demand-response findings are currently based on a small f_scrape sample
- seller-type findings are stronger than ceiling findings because coverage is wider in offer-history outputs

### Ceiling and demand-response findings

From the f_scrape sample:
- no universal hard Buy Box cutoff was proven
- pattern looks like a soft ceiling, usually product-specific
- lagged BSR deterioration after higher price appears more common than same-day collapse

Directional metrics from this pass:
- 3 of 4 SKUs showed worse BSR in higher-price regime versus lower-price regime
- high-price regime median BSR was roughly 1.21x to 1.66x worse on those SKUs
- relationship appears gradual in many cases, not always a hard cliff

Practical implication:
- use a ceiling zone with confidence, not one hard global ceiling number

### Seller-type behavior findings

From listing offer history:
- recorded Buy Box wins are mostly FBA when Buy Box is present
- recorded Buy Box split (rows with Buy Box price): FBA 79.2%, FBM 20.6%
- `buy_box_channel` is missing on many rows, so confidence needs gating

From seller observation history:
- FBA offers are almost always Prime (about 99.9%)
- FBM offers are much less often Prime (about 13.8%)

Practical implication:
- treat FBA as main competitive reference by default
- treat FBM as secondary unless evidence suggests FBM is consistently winning in that listing
- apply confidence downgrade when Buy Box channel coverage is sparse

### Compression and recency findings

From the current f_scrape sample:
- Buy Box opportunity spread over floor is usually thin in this sample
- in most window comparisons, Buy Box and floor averages are equal or near-equal
- recent behavior looked weaker than prior window on most sampled SKUs

Directional weighting guidance from this pass:
- 30d as primary execution signal
- 90d as confirmation signal
- 180d as structural memory signal
- 365d as context signal only when fields are populated and reliable

Suggested starting weights:
- 30d / 90d / 180d / 365d = 50 / 30 / 15 / 5

### Demand attribution and variant risk findings

Current outputs are not enough to prove exact child-level sell-through.

Main gaps identified:
- no parent-child relationship fields in assessed outputs
- no clear child-level demand attribution chain in these files
- `listing_offer_history.csv` has no populated BSR values in current sample
- Buy Box and channel fields are often missing

Practical implication:
- current system can avoid obvious traps
- current system cannot claim exact child-level demand allocation with high confidence

### Confidence rules to carry forward

Use confidence layering in automation outputs:

- High confidence if:
- direct child/offer linkage exists
- Buy Box ownership and channel are known
- demand response supports sellability at that price

- Medium confidence if:
- listing-level signals are present
- child attribution is not direct

- Low confidence if:
- Buy Box/channel is sparse or missing
- BSR evidence is missing or noisy
- parent-variation contamination is likely

### Data additions now justified

Add these fields in future captures:
- parent_asin
- child_asin
- variation_theme
- variant_group_id
- buy_box_owner_seller_id
- buy_box_owner_channel
- buy_box_owner_is_amazon
- buy_box_owner_is_our_offer
- child_bsr
- bsr_7d_change
- bsr_14d_change
- post_price_jump_bsr_change
- review_share_variant
- review_share_parent
- variant_review_count
- parent_review_count
- ceiling_estimate
- ceiling_confidence
- price_jump_event_id
- demand_attribution_confidence

### Operational cautions from this pass

- do not claim Amazon-specific Buy Box behavior from this pass alone
- assessed buy_box_channel data currently has no direct Amazon winner rows
- do not set hard global thresholds from 4-row f_scrape sample
- use this pass to shape instrumentation and confidence logic first

## Patterns File Takeaways

Source reviewed:
- `reference/Backtest Strategy Ideas/patterns.md`

This file appears materially more useful than the earlier small-sample output pass because it reports:
- 50,287 ASIN-day points
- 146 ASINs

That makes it stronger for Buy Box behavior patterns than the 4-row `f_scrape` sample.

### 1) No universal hard Buy Box ceiling

The strongest new point is:
- there is no evidence of one universal hard Buy Box ceiling across all ASINs

The practical meaning is:
- do not build the system around one absolute maximum price rule
- a fixed ceiling like "Buy Box disappears above GBP X" is too simplistic

### 2) Relative price context matters more than absolute price

This is one of the most useful additions in the file.

The stronger model is:
- compare current lowest visible price against that ASIN's own recent reference range

The pattern described in the file suggests:
- Buy Box suppression becomes much more likely when current lowest visible price rises well above the trailing median for that same ASIN

Working implication:
- use relative spike logic
- not absolute price logic

### 3) Seller type materially changes suppression risk

This lines up well with your earlier thinking.

The file suggests:
- Amazon is the most resilient seller type
- FBA is next
- FBM is the most fragile

The most useful planning implication is:
- the same relative price spike should not be treated equally for Amazon, FBA, and FBM

If this holds up, the future system should likely model:
- Amazon-relative spike risk
- FBA-relative spike risk
- FBM-relative spike risk

### 4) Cheapest visible offer does not always equal Buy Box

This is another useful reinforcement.

The file reports that:
- the Buy Box does not always match the cheapest visible offer
- a small premium over the cheapest visible line can still hold the Buy Box

Practical implication:
- do not hard-code "lowest visible price = Buy Box price"
- allow for small premium tolerance, especially in FBA-led situations

### 5) Relative spike thresholds look more actionable than fixed ceilings

The file proposes a useful pattern:
- above about 1.5x of trailing 30-day median lowest visible price = major warning
- above about 2.0x = hard risk flag

These should not be treated as final laws yet, but they are useful starting candidates for automation logic.

### 6) Amazon dominance should likely become a reject-style signal

The file suggests a practical form such as:
- high Amazon presence
- high Amazon Buy Box share

This is useful because it pushes the model toward:
- not just "Amazon appeared"
- but "Amazon structurally dominates this listing"

That is a better sourcing risk concept than one-off Amazon presence.

### 7) Stable Buy Box plus low Amazon presence plus low volatility looks meaningful

This is one of the clearest screening-style patterns in the file.

The practical interpretation is:
- stable Buy Box
- low Amazon presence
- lower volatility

is a much stronger sellability signal than a product simply looking cheap today.

### 8) Patterns file should carry more weight than earlier ceiling pass

Because this file is based on much broader coverage, it should currently carry more decision weight than the earlier small-sample ceiling observations.

That does not make it perfect, but it means:
- use the patterns file as the stronger directional evidence
- use the smaller passes as supporting detail and caution

## Decisions Still Open After Patterns Review

The core direction now looks strong, but these design choices still need to be settled:

### 1) Exact policy schema

We still need to lock the exact fields for the shared policy profile, especially:
- ROI thresholds
- recency weights
- seller-type penalties
- spike-risk thresholds
- exit and emergency logic

### 2) Exact recency treatment

We have directional support for:
- 30d primary
- 90d confirmation
- 180d memory
- 365d context

But we still need to decide:
- the exact weights
- when older history becomes warning-only
- how old Amazon suppression should decay

### 3) Ceiling model shape

We now have better support for:
- soft ceiling
- relative spike logic
- seller-type-specific ceiling behavior

But we still need to decide:
- whether the model outputs one ceiling zone or several
- how much BSR response is required before a spike becomes "unsellable"
- how to express confidence when demand attribution is weak

### 4) Amazon-specific treatment

We are directionally confident Amazon should be treated differently.

But we still need to settle:
- exact reject logic
- exact penalty logic
- whether Amazon dominance should hard-fail sourcing in some cases
- how much recent Amazon activity matters versus older Amazon history

Current direction:
- older Amazon history should decay for active pricing decisions
- older Amazon history should decay much less for deep-loss warning logic

Reason:
- an 11-month-old Amazon price may be stale as a live target
- but it is still highly relevant if that old Amazon level would put us into unrecoverable or near-unrecoverable territory today

### 5) Variant and attribution confidence

We already know current outputs are weak here.

We still need to decide:
- what minimum data is enough for medium confidence
- what conditions force low confidence
- when parent-level demand is too contaminated to trust

### 6) Final output structure

We still need to choose what the user-facing outputs actually are.

Most likely candidates now are:
- Market Viability Score
- Exit Risk Score
- Sellable Ceiling Zone
- Attribution Confidence
- Amazon Dominance Risk
- Compression Risk

### 7) What becomes a hard fail versus a warning

This is still open and important.

Examples still to decide:
- Amazon dominance threshold
- Buy Box suppression rate threshold
- FBM-cheapest but FBM-rarely-wins threshold
- spike-risk threshold
- data sparsity threshold

## BSR Response Study - Raw Daily File

Source used:
- `out/systems/F/live/feeder_legacy_chart_daily_raw_live.csv`

Run intent:
- measure how BSR reacts to price changes using ASIN-relative normalization
- avoid fixed global BSR thresholds

### Coverage

- total rows: 51,742
- ASINs: 146
- paired rows with BSR by channel:
- Amazon: 26,342 (99 ASINs)
- Buy Box: 43,319 (145 ASINs)
- FBA: 26,356 (141 ASINs)
- FBM: 31,176 (115 ASINs)

### Core result

The relationship is real but moderate:
- higher normalized price usually maps to worse normalized BSR
- effect is strongest when measured within each ASIN
- reaction is usually delayed, not purely same-day

Directional evidence:
- most ASINs show positive price-vs-BSR relationship
- lagged response is typically stronger than same-day response
- strongest reaction zone is generally around 1 to 7 days after shock

### Reaction-time findings

From event-style analysis on `price_chosen_processed`:
- upward shocks are typically followed by BSR worsening
- downward shocks are typically followed by BSR improvement
- bigger shocks produce bigger BSR response
- first clear response often appears around day 1 to 2
- stronger peak response often appears around day 7 to 9

Practical reading:
- BSR should be treated as a lagging response curve
- not as an instant reaction signal

### Channel strength differences

Current signal strength by channel:
- Amazon: high
- Buy Box: high
- FBA: medium-high
- FBM: medium-low

Interpretation:
- Amazon and Buy Box channels carry the strongest BSR response signal
- FBM signal is weaker/noisier and should be weighted lower unless coverage is strong

### Why fixed BSR numbers are wrong

A fixed threshold approach (for example one global rank number) is not robust because:
- ASINs live on very different natural rank scales
- one ASIN can move from 200 to 20,000 while another moves from 20,000 to 70,000
- comparable meaning comes from relative change inside each ASIN, not absolute rank alone

So the model should use ASIN-relative features:
- percent from ASIN rolling median
- range position within ASIN
- z-score or log-ratio style normalization

### Recommended v1 BSR-response features

Keep this compact:
- `price_to_median_30d`
- `price_position_in_range_30d`
- `bsr_to_median_30d`
- `bsr_position_in_range_30d`
- `price_change_1d`
- `price_change_2d`
- `price_change_3d`
- `future_bsr_change_2d`
- `future_bsr_change_3d`
- `future_bsr_change_7d`
- `price_shock_20pct_flag`
- `bsr_reaction_confidence`

### Confidence gates

Use minimum evidence rules before trusting channel-level reaction:
- at least around 30 paired days for ASIN-channel analysis
- enough shock events to estimate lag response
- downgrade confidence when channel data is sparse or mostly missing

### What this means for policy

- keep ASIN-relative normalization as mandatory
- treat BSR as delayed response, not immediate truth
- weight Amazon and Buy Box response higher than FBM by default
- use lag-aware features (2d to 7d especially) in automation logic

## V1 Feature Spec Direction

This section turns the current research into a practical first-pass input set.

The rule is:
- keep v1 compact
- prefer signals that are explainable
- avoid pretending weak attribution is precise

### Core price position features

These describe where current price sits inside the ASIN's own normal world:

- `price_to_median_30d`
- `price_to_median_90d`
- `price_position_in_range_30d`
- `price_position_in_range_90d`
- `price_position_in_range_180d`

Purpose:
- detect stretched pricing versus normal pricing
- support soft ceiling logic
- keep analysis relative to that ASIN, not global fixed numbers

### Core BSR position features

These describe where current demand proxy sits relative to the ASIN's own history:

- `bsr_to_median_30d`
- `bsr_to_median_90d`
- `bsr_position_in_range_30d`
- `bsr_position_in_range_90d`
- `bsr_position_in_range_180d`

Purpose:
- detect whether demand is healthy, weakening, or collapsing relative to the listing's normal pattern

### Price shock features

These describe whether price has moved enough to expect a meaningful response:

- `price_change_1d`
- `price_change_2d`
- `price_change_3d`
- `price_shock_20pct_flag`
- `price_shock_direction`

Purpose:
- capture significant price movement
- avoid overreacting to tiny daily noise

Current direction:
- a 20% shock is a better starting trigger than 10%

### Lagged BSR response features

These describe how the demand proxy reacted after a price move:

- `future_bsr_change_2d`
- `future_bsr_change_3d`
- `future_bsr_change_7d`
- `bsr_reaction_strength_2d`
- `bsr_reaction_strength_7d`
- `bsr_reaction_lag_peak`

Purpose:
- treat BSR as a delayed response signal
- separate instant noise from real reaction

### Structural memory features

These keep older behavior in the model without letting it dominate:

- `price_to_median_180d`
- `price_to_median_365d`
- `amazon_old_range_overlap_flag`
- `buy_box_old_range_overlap_flag`
- `deep_loss_amazon_memory_flag`

Purpose:
- preserve long-memory risk
- especially preserve Amazon return risk
- support fallback logic when recent data is sparse

### Channel confidence features

These stop weak data from being treated like strong evidence:

- `amazon_signal_confidence`
- `buy_box_signal_confidence`
- `fba_signal_confidence`
- `fbm_signal_confidence`
- `demand_attribution_confidence`
- `history_coverage_confidence`

Purpose:
- express uncertainty honestly
- prevent overconfident passes or fails on sparse data

### Seller-type weighting direction

Current trust order:
- Amazon = high
- Buy Box = high
- FBA = medium-high
- FBM = medium-low

Practical meaning:
- if Amazon and Buy Box both support pressure, take that seriously
- if FBM alone suggests pressure, treat it more cautiously

### What should be warning-only in v1

These should inform the result, but not hard-fail on their own at first:

- single small BSR move
- single 10% price shock
- sparse FBM-only signal
- one-off price spike without lagged BSR deterioration

### What looks strong enough to matter in scoring

These look strong enough to matter meaningfully in v1 logic:

- sustained price stretch versus 30d and 90d median
- 20%+ price shock
- lagged BSR worsening over 2d to 7d
- repeated weak BSR position while price stays stretched
- strong Amazon memory signal

### Practical v1 principle

The system should not ask:
- "is BSR above or below one fixed number?"

It should ask:
- "relative to this ASIN's own normal pattern, did price stretch enough to matter, and did BSR weaken after a believable lag?"

## Finalisation 1 Takeaways

This section records the strongest v1 decisions from `finalisation1.md`.

### Main conclusion

The project is no longer short of ideas.

The main remaining risk is:
- too many knobs
- too many weak signals leaking into hard logic
- too much confidence in data that is only directional

So v1 should now be tightened around:
- a small editable policy profile
- a clear rule bucket system
- a compact result panel
- confidence limits that stop weak data from pretending to be strong

### V1 rule buckets

Do not force every signal into score vs fail.

Use 4 buckets:

- `score_input`
- `overlay_warning`
- `hard_fail`
- `no_grade_manual_review`

Practical meaning:
- `score_input` = strong, repeatable, close to outcome
- `overlay_warning` = useful context, but weaker attribution or causality
- `hard_fail` = evidence the listing is structurally incompatible with the policy
- `no_grade_manual_review` = not enough trustworthy evidence to score or fail cleanly

Important rule:
- sparse data is not automatically a fail
- sparse data is often `no_grade_manual_review`

### Lean v1 policy profile

The v1 schema should stay lean and keep only the settings we genuinely need to control.

Working direction:

```yaml
policy_profile_v1:
  roi_thresholds:
    entry_target_pct: 20
    working_floor_pct: 10
    exit_floor_pct: 0
    emergency_floor_pct: -5

  recency_weights:
    d30: 0.50
    d90: 0.30
    d180: 0.15
    d365: 0.05

  channel_weights:
    buy_box: 1.00
    fba: 0.70
    fbm: 0.30

  amazon_memory:
    decay_0_30d: 1.00
    decay_31_90d: 0.65
    decay_91_180d: 0.35
    decay_181_365d: 0.15
    deep_loss_floor_decay: 0.35

  amazon_risk_thresholds:
    recent_presence_warn_share: 0.20
    recent_presence_fail_share: 0.40

  ceiling_logic:
    stretch_warn_ratio_30d: 1.25
    stretch_red_ratio_30d: 1.50
    stretch_extreme_ratio_30d: 2.00
    shock_trigger_pct_1d: 20
    bsr_worsen_warn_pct_7d: 10
    bsr_worsen_red_pct_7d: 20

  confidence_gates:
    min_history_days_to_score: 90
    min_history_days_high: 180
    min_paired_price_bsr_days: 30
    min_paired_price_bsr_days_high: 90
    min_shock_events_for_bsr_reaction: 5
    min_buy_box_coverage_share: 0.30
    min_buy_box_coverage_share_high: 0.60

  exit_ladder:
    use_live_policy_defaults: true
```

### Derive, do not store

These should be derived from the core profile rather than duplicated as extra settings:

- break-even threshold = `0`
- tolerated low-ROI band = `working_floor_pct` to `entry_target_pct`
- tolerated loss band = `emergency_floor_pct` to `exit_floor_pct`
- minimum acceptable ROI = `working_floor_pct`
- normal target ROI = `entry_target_pct` unless live repricing already has a separate operating target

### What belongs in each bucket

#### Score input

Strong enough for v1 scoring:

- recency-weighted time in ROI bands
- longest streak below working floor
- longest streak below exit floor
- rolling-start backtest phase-hit rates
- capital days locked
- Buy Box versus FBA compression
- ceiling stretch zone when Buy Box and BSR confidence is adequate
- recent Amazon pressure

#### Overlay / warning

Useful context, but not strong enough to steer the model heavily on its own:

- FBM cheaper without clear evidence that FBM wins
- one-off spikes without lagged BSR damage
- Amazon history older than 180 days unless it hit deep-loss territory
- review-share hints
- sparse seller-type clues
- weak 365-day history outside deep-loss memory

#### Hard fail

Keep this short:

- recent market shows no practical path to break-even under current policy
- Amazon is recently dominant and its price pushes us at or below exit or emergency floor
- repeated extreme stretch with clear demand deterioration and no recovery
- backtest says the current policy is structurally incompatible with the listing

#### No-grade / manual review

Use this when evidence is too weak to trust a clean score:

- under 90 history days
- fewer than 30 paired price and BSR days in a primary channel
- weak Buy Box coverage
- parent or variation contamination
- ceiling logic based on sparse ownership or sparse BSR reaction data

### Confidence rules

Confidence should limit trust.
It should not act like a score booster.

#### High

- at least 180 history days
- at least 90 paired Buy Box and BSR days
- at least 5 meaningful shock events
- Buy Box coverage at least 60%
- no obvious attribution contamination

#### Medium

- at least 90 history days
- at least 30 paired days in Buy Box or FBA with BSR
- enough data to compute 30-day and 90-day windows
- listing-level evidence is usable even if ownership detail is not perfect

#### Low

- below the above thresholds
- or attribution is weak
- or parent contamination is likely
- or seller ownership signal is too sparse

Three lock rules:

- `365d` can raise risk but must not rescue viability
- deep-loss Amazon memory decays slower than normal Amazon memory
- low confidence should cap recommendation strength unless a hard fail is obvious

### Recommended result panel

The result panel should stay compact and readable.

Recommended v1 structure:

1. `Market Viability Score`
2. `Exit Risk Score`
3. `Capital Lock-up`
4. `Sellable Ceiling Zone`
5. `Amazon Risk`
6. `Compression Risk`
7. `Confidence`
8. `Recommendation`

Working recommendation states:

- `Normal fit`
- `Managed fit`
- `Exit-only`
- `Avoid`
- `Manual review`

Note:
- do not give attribution confidence its own tile in v1
- fold attribution issues into `Confidence` reason tags instead

### Finalisation order

The cleanest order from here is:

1. lock the 4-bucket taxonomy
2. lock the result panel
3. lock the lean editable schema
4. lock the default thresholds
5. run a small calibration set

Calibration set guidance:
- around 15 to 20 ASINs
- include obvious good, obvious bad, Amazon-risk, compression-risk, sparse-data, and ambiguous cases

### What to cut from v1

These ideas stay useful, but should not become core v1 logic yet:

- exact child-level demand attribution
- review-share-driven sell-through claims
- seller-type-specific ceiling curves
- explicit inflation modelling
- optimisation and parameter search

Practical reading:
- recency weighting plus ASIN-relative normalization already does most of the inflation handling v1 needs
- optimisation belongs later, after the first model is stable and explainable

## Failure Events Vs Temporary Suppression

This is a core correction to how Amazon and other bad-price periods should be read.

The model should not ask:
- "did Amazon ever appear at a bad ROI?"

The model should ask:
- "if we had owned stock during this period, what would the repricer have done?"
- "would it have waited safely, continued normal selling, or been forced into sell-off behavior?"
- "how often did that happen, how long did it last, and how severe was it?"

### Important rule

One bad window is not automatically a fail.

Example:
- if Amazon spent one week at a destructive ROI 11 months ago
- and the market then recovered cleanly
- that should usually be treated as warning or memory, not automatic fail

Reason:
- the repricer would not instantly panic-sell
- it would usually hold through a short bad window if recovery was normal

### What matters instead

The backtest should judge bad periods using 4 things:

1. `severity`
- how bad does ROI get during the bad window?

2. `duration`
- how long does that bad window last?

3. `frequency`
- how often do bad windows happen?

4. `recovery`
- does the listing usually recover back into workable selling conditions?

### Practical interpretation

- short bad period:
  - usually temporary suppression
  - often not a fail on its own

- repeated bad periods:
  - more serious
  - may mean the listing regularly loses usable pricing power

- long continuous bad period:
  - serious risk
  - more likely to trigger sell-off behavior

- bad period near break-even:
  - can be survivable if duration is limited
  - still an exit path exists

- bad period deep below break-even:
  - much more dangerous
  - exit path may be badly damaged or removed

### What failure should mean

Failure should not mean:
- "the chart once went into a bad zone"

Failure should mean something closer to:
- "the repricer would have had to abandon normal strategy for too long or too often"

That means the system should track:
- estimated time in normal selling
- estimated time in hold / wait mode
- estimated time in sell-off mode
- number of failure events
- longest failure streak
- recovery rate after bad periods
- sell-off severity

### Amazon-specific reading

Amazon pressure should be replayed as the repricer would feel it:

- short bad Amazon period:
  - warning / temporary suppression risk

- repeated Amazon suppression:
  - high risk

- long Amazon pressure below workable ROI:
  - likely exit-risk event

- deep-loss Amazon pressure with poor recovery:
  - strong fail candidate

### V1 design implication

Do not use a simple rule like:
- "Amazon at negative ROI = fail"

Use a repricer-simulation rule like:
- "Amazon created bad windows of a certain severity, duration, frequency, and recovery profile"

This keeps the model aligned with the real business question:
- if we had held stock during this period, would the repricer have managed it safely or been forced into a bad exit?

## Profit-First Backtest Logic

This is the main commercial backbone for the backtest.

The system should not mainly ask:
- "did anything ever go wrong?"

It should mainly ask:
- "if we had bought this product at a given time and let our repricer manage it, would the total outcome still have been good enough?"

### Main pass idea

The strongest v1 control is likely a user-changeable profit target.

Examples:
- `minimum_expected_monthly_profit`
- `minimum_total_profit_over_test_window`

Practical meaning:
- a listing can have some bad weeks
- it can even end in a sell-off loss
- but still be a pass if the full backtest result remains good enough overall

Example:
- purchased 8 months ago
- made about `GBP 100` per month during normal periods
- had some stagnant weeks
- later sold off at `GBP -20`
- overall result still acceptable

That should still be considered a pass if it clears the chosen minimum target and the risk profile is acceptable.

### What the backtest should replay

The model should simulate the product as the repricer would actually experience it:

1. estimate sellable periods from price history and channel conditions
2. estimate units sold using the sales signal already collected in F
3. apply policy logic across the timeline:
- normal selling
- hold / wait
- sell-off / exit
4. combine:
- ROI ranges
- BSR response
- ceiling behavior
- price compression
- Amazon pressure
- estimated sales share
5. calculate final financial outcome

### Main outputs from that replay

The core result should include:

- gross profit during normal selling
- low-sales or stagnant periods
- sell-off profit or loss
- total profit over the backtest window
- average monthly profit

These should then be compared against the user's chosen minimum target.

### Why this is better than simple fail logic

A listing should not fail just because:
- it had one bad window
- Amazon suppressed it briefly
- it had to exit once at a small loss

It should fail when:
- total profit is not good enough
- bad periods happen too often
- exit behavior is too damaging
- or catastrophic risk is too high

### Risk still matters

Profit should be the main driver.
But profit alone should not hide structurally bad risk.

So the system should still separately show:
- Amazon trap risk
- compression risk
- confidence level
- exit severity
- longest failure streak
- frequency of sell-off events

### Practical v1 principle

The backtest should answer:
- "would this have made enough money under our policy?"

And then explain:
- "how stable was that result?"
- "how often did it stall?"
- "how often did it need exit behavior?"
- "how ugly was the worst-case period?"

### Current direction

Working recommendation:
- use profit as the main pass condition
- use risk as the explanation and control layer
- allow a listing to pass even if it had some failure periods, as long as the full replay result is still acceptable and the exit path stayed realistic

## Seasonality Vs Recency

This is an important split in the model.

Do not use one recency rule for everything.

The system should treat:
- pricing and competition history
- demand and seasonality history

as related, but different.

### Core rule

Use recent data for price truth.
Use seasonal history for demand truth.

That means:
- recent windows should dominate current pricing and competition logic
- same-season history should still matter for expected demand

### Why this matters

Example:
- Christmas lights scanned in March

A shallow system may see:
- strong historical profit windows
- workable pricing
- good peak-season demand

and incorrectly assume:
- this will sell well now

But the real problem is:
- price may still look fine
- demand may be weak because it is out of season
- capital may get trapped for months before the next strong demand window

So the model must separately ask:
- what price world are we entering now?
- what demand world are we entering now?

### Two clocks

#### 1) Recent market clock

Use this for:
- current price reality
- current seller pressure
- current Buy Box behavior
- current Amazon risk

This should be dominated by:
- `30d`
- `90d`

Older pricing data should fade strongly here.

#### 2) Seasonal demand clock

Use this for:
- time-of-year demand
- same-month or same-season comparison
- expected near-term sales strength
- capital lock-up risk outside peak demand windows

This should compare:
- recent demand trend
- current month versus same period last year
- current BSR behavior versus seasonal windows

### Practical weighting direction

For pricing and competition:
- `30d` = high weight
- `90d` = medium weight
- `180d` = low weight
- `365d` = very low weight except Amazon deep-loss memory

For demand and seasonality:
- recent trend still matters
- same-season historical demand remains relevant
- old seasonal demand can matter more than old seller pricing

### What old data should still do

Old data should not have one single role.

#### Old seller pricing

- low weight
- mostly context
- should not strongly control today's price logic

#### Old Amazon destructive pricing

- still meaningful as structural warning
- especially if it would destroy the exit path

#### Old same-season demand

- still important
- especially for highly seasonal listings

### V1 design implication

A listing should not pass just because:
- price history looks profitable in general

It should also be asked:
- is demand likely to exist in the time window we are actually entering?

So for seasonal products the system may conclude:
- price looks viable
- but near-term demand is weak
- capital lock-up risk is high
- recommendation should be softer, delayed, or avoided for now

### Practical reading

For this project the right principle is:
- recent for pricing
- seasonal for demand
- old seller prices fade
- old same-season demand still matters

## Threshold Sign-Off And Calibration Recommendation

This section captures the recommended way to finish v1 planning without over-tuning the model.

### Main principle

Do not try to perfect the algorithm before build.

The better approach is:
- keep user controls small
- keep most of the logic data-driven
- use a small calibration set to catch obvious bad assumptions

The goal is not:
- endless threshold tuning

The goal is:
- stop the model from being obviously too soft or too harsh

### Recommended user controls

The user should control only a small number of commercial settings.

Recommended v1 controls:
- `minimum_expected_profit`
- `entry_target_roi`
- `working_floor_roi`
- `exit_floor_roi`
- `emergency_floor_roi`

Possible later control:
- `risk_appetite_mode`

But not needed for first version.

### Recommended locked system defaults

These should mostly stay system-controlled in v1:
- recency weighting
- confidence rules
- ceiling stretch logic
- Amazon memory logic
- seasonality handling
- BSR-response handling

Reason:
- too many editable settings will make the system unstable and hard to trust

### Suggested first thresholds

#### Pricing and competition recency

Keep:
- `30d / 90d / 180d / 365d`

Default weighting:
- `50 / 30 / 15 / 5`

Special rule:
- old destructive Amazon memory should carry more warning value than normal old seller pricing

#### Ceiling stretch zones

Keep:
- warning at `1.25x`
- red at `1.50x`
- extreme at `2.00x`

Reason:
- this matches the strongest soft-ceiling evidence from the daily file

#### BSR shock trigger

Keep:
- `20%` one-day shock as the main v1 trigger

Reason:
- `10%` looks too noisy
- `20%` gives stronger signal without waiting for only extreme events

#### Confidence levels

Keep:
- `High` at about `180+` history days and `90+` paired price+BSR days
- `Medium` at about `90+` history days and `30+` paired days
- `Low` below that

Rule:
- sparse data should lead to `Manual review`, not automatic fail

### Calibration approach

Do not treat calibration like model training.

It is only a reality check.

Recommended small set:
- around `15 to 20` ASINs

Include:
- obvious winners
- obvious losers
- Amazon suppression cases
- seasonal cases
- compression-risk cases
- sparse-data cases
- shared-demand / crowded-competition cases

For each ASIN, ask:
- would we actually buy this?
- would it likely sell in the period we care about?
- would Amazon force a bad exit?
- would competition dilute sales too much?
- does the replay look too harsh or too generous?

### Most important remaining blind spot

The biggest remaining risk in the model is competition-adjusted sales share.

Right now, a naive replay can overestimate profit because it assumes:
- listing demand belongs to us

That is not safe.

In reality:
- Amazon may take much of the demand
- several FBA sellers may split demand
- FBM may be visible but not actually win much

So the backtest must not assume:
- `100%` of listing sales are ours

### Recommended v1 competition haircut model

Do not try to solve exact share perfectly in v1.

Use a simple sales-share haircut layer.

Working direction:

- Amazon present and active:
  - strong haircut

- multiple FBA sellers near the Buy Box:
  - medium haircut

- FBM-only pressure:
  - smaller haircut

- clean Buy Box and light competition:
  - little or no haircut

Practical purpose:
- estimate "our likely share of listing sales"
- avoid inflated profit projections

### Commercial interpretation

The main trade-off should be understood like this:

- higher minimums:
  - fewer sales
  - higher ROI
  - stronger safety
  - less capital tied up

- lower minimums:
  - more sales
  - lower ROI
  - weaker safety
  - more capital tied up

There is likely a vague tipping point between:
- being too fussy and missing good stock
- being too loose and staying busy on weak profit

That tipping point is not something we can know perfectly in advance.

So v1 should aim for:
- sensible minimum-profit targeting
- ROI guardrails
- realistic competition haircuts
- risk explanation, not false precision

### Final recommendation

The cleanest finish from here is:

1. lock the small user-control set
2. lock the system defaults above
3. include competition-adjusted sales-share logic in the replay
4. run one small calibration set
5. make one adjustment pass only
6. freeze v1 and move to coding plan

## Provisional V1 Sales Share Assumption

This section defines the temporary sales-share logic for v1.

### Main principle

Do not pretend we know exact sales share.

For v1:
- use simple market scenarios
- apply a provisional share assumption
- later compare that assumption against real live Buy Box win percentage by scenario

This means the first version should be:
- simple
- explainable
- easy to replace with measured evidence later

### Scenario method

Use a small number of market states.

Working direction:
- `solo_or_no_meaningful_competition`
- `sharing_with_amazon`
- `sharing_with_fba`
- `sharing_with_amazon_and_fba`

These should be based on:
- whether Amazon is present in the active trading zone
- whether competitive FBA is present in the active trading zone
- whether we are matching the relevant market price

### Important rule

Only apply shared-sales assumptions when we are matching the relevant trading price.

Do not use the same share assumption when:
- our simulated price is above the live trading zone
- we are outside the usable ceiling zone
- we have effectively lost the active price match

Reason:
- if we are above the price that matters, the issue is not shared sales
- the issue is that we may not be selling much at all

### Temporary v1 default

To keep v1 simple, use this provisional default:

- `solo_or_no_meaningful_competition` = `100%` assumed share
- `sharing_with_amazon` = `50%` assumed share
- `sharing_with_fba` = `50%` assumed share
- `sharing_with_amazon_and_fba` = `50%` assumed share for now

This is intentionally simple.

It is not claiming:
- that Amazon always splits evenly
- that FBA always splits evenly
- that the real world is exactly 50/50

It is only a temporary placeholder until live measured Buy Box share by scenario is available.

### Why this is acceptable for v1

This works as a first step because:
- it avoids pretending all listing sales are ours
- it keeps the replay logic simple
- it can be checked later against live operating data

### Planned validation path

Later, these placeholder shares should be replaced or adjusted using live evidence.

The validation question should be:
- when we are matching price in this scenario, how often do we actually win the Buy Box?

That should then be measured for each scenario, using only price-matching periods so the results are not muddied by us sitting above market price.

### Practical reading

For now:
- use simple scenario states
- use `50/50` as the provisional shared-sales rule
- assume much lower sales when we are not matching the relevant price
- return later and tighten the share logic using live Buy Box win percentages
