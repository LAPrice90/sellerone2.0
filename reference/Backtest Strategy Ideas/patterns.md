I reviewed the CSV and checked current Amazon Featured Offer guidance. Amazon’s own docs make clear that Featured Offer eligibility is not just “lowest item price”: Amazon considers competitive **total price** against external retail prices, fast/free delivery, seller performance, and inventory. Pricing Health / Fair Pricing can make an offer ineligible when it is not competitive or is significantly higher than recent prices on or off Amazon. FBA/Prime can improve odds, and Amazon also says strong FBM offers can compete when shipping is comparable. ([Sell on Amazon][1])

## Main answer

There is **no evidence of one universal hard Buy Box ceiling** in your file.

I collapsed the data to **50,287 ASIN-day points across 146 ASINs**. Buy Box was present on **84.9%** of all points, or **90.8%** of points where at least one Amazon/FBA/FBM price line existed.

The strongest evidence against a universal ceiling is this:

* Buy Box still appeared on some ASINs **above £100**.
* Of **83 ASINs** with enough mixed Buy Box / no-Buy-Box history to test for a threshold, only **2** showed a clean local cutoff.
* A direct contradiction exists: **Jimmy Choo Man Ice (B06XWD6G2N)** had **no Buy Box at £29.95** on some days, but **did have Buy Box at £99.99** later.

So the useful model is not “there is a fixed max Buy Box price.” The useful model is:

**Buy Box suppression is mostly relative to that ASIN’s own recent/reference price context, and it is heavily affected by seller type and fulfillment.**

## Seller-type behaviour in your file

The cleanest pattern is that **Amazon is the most resilient seller type**, **FBA is next**, and **FBM is the most fragile**.

* **Amazon-only days:** Buy Box rate **97.4%**
* **FBA-only days:** Buy Box rate **76.5%**
* **FBM-only days:** Buy Box rate **61.2%**

Looking at the **cheapest visible seller type** is even more useful:

* When **Amazon** was cheapest, Buy Box showed **97.7%** of the time, and matched Amazon **95.8%** of the time.
* When **FBA** was cheapest, Buy Box showed **86.8%** of the time, but matched FBA only **66.3%** of the time.
* When **FBM** was cheapest, Buy Box showed **84.1%** of the time, but matched FBM only **40.6%** of the time. In those same FBM-cheapest cases, **FBA still won outright 20.1%** of the time, and the Buy Box disappeared **15.9%** of the time.

That lines up with Amazon’s current guidance: Featured Offer is not a pure lowest-price auction; shipping speed, total delivered price, and service quality matter. ([Sell on Amazon][1])

Another important pattern: **the Buy Box does not always equal the cheapest visible offer**. In FBA+FBM situations, the Buy Box sat **above the lowest visible offer 38.9% of the time**. Across “unmatched” cases, the Buy Box premium over the cheapest visible line was typically small, but real: median about **2.3%**. That means an automation should not assume “min visible price = Buy Box price.”

## Does the Buy Box cut off when price spikes?

Not at one absolute number. It cuts off more often when price gets too far above that ASIN’s own recent range.

Using a simple per-ASIN reference of:

**current lowest visible price / trailing 30-day median lowest visible price**

the suppression pattern gets much clearer:

* At **1.5x to 2.0x** the recent median, Buy Box presence fell to **73.9%** overall, with **26.1%** no-Buy-Box.
* At **2.0x+**, Buy Box presence was **70.0%**, with **30.0%** no-Buy-Box.

But seller type changes that risk a lot:

* **Amazon cheapest + 1.5x–2.0x spike:** no Buy Box only **4.7%**
* **FBA cheapest + 1.5x–2.0x spike:** no Buy Box **33.5%**
* **FBM cheapest + 1.5x–2.0x spike:** no Buy Box **68.8%**

That is the biggest automation insight in the whole file:

**relative price spikes are dangerous, but they are much more dangerous for FBM than for Amazon.**

Two ASINs did show something close to a local ceiling:

* **B0038TVH3Y** — Buy Box present up to **£10.98**, absent from **£12.49** upward
* **B08Z9Y379G** — Buy Box present up to **£14.99**, absent from **£15.50** upward

Those are exceptions, not the rule.

## What looks useful for automation

For a screening bot, I would not use a fixed maximum price. I would use these rules instead.

1. **Use relative price, not absolute price.**
   Track `current_lowest_visible / trailing_30d_median_lowest`.
   Above **1.5x** should be a major warning. Above **2.0x** should be a hard risk flag.

2. **Model FBA and FBM separately.**
   The file shows FBM-cheapest offers are much less likely to hold the Buy Box than FBA-cheapest offers.

3. **Treat Amazon presence as a major negative.**
   A practical reject rule is:
   `amazon_presence > 60% and bb_amazon_share > 80%`
   That usually means Amazon dominates the ASIN.

4. **For FBM, test whether FBM actually wins when cheapest.**
   Useful rule:
   `fbm_low_bb_fbm_rate < 40%` → avoid for FBM
   In your file, more than half of ASINs with FBM-lowest history had FBM winning **under 40%** of the time.

5. **For FBA, check whether FBA gets rewarded when cheapest.**
   Useful rule:
   `fba_low_bb_fba_rate < 60%` → caution / avoid
   If FBA is cheapest and still not winning often, something structural is wrong.

6. **Watch volatility and suppression together.**
   Good filters:
   `buybox_rate < 85%`
   `no_buybox_rate > 15%`
   `price_cv > 0.20`
   `no_buybox_when_spike_1_5 > 25%`

Your own `phase_processed` labels back this up. The candidates that were profit-majority had:

* median Buy Box rate **97.0%** vs **93.7%** for the rest
* median Amazon presence **6%** vs **74%**
* lower price volatility, about **0.13** vs **0.20**

That is blunt, but useful: **stable Buy Box + low Amazon presence + low volatility** is much closer to a sellable product than “cheap today.”

One more practical signal: in your file, days with a Buy Box had median **BSR ~10.5k**, versus **~39.3k** when the Buy Box was absent. That is only correlation, but it strongly suggests recurring Buy Box loss is usually bad news for velocity.

## Files

ASIN-level report with flags and metrics: [buybox_asin_report.csv](sandbox:/mnt/data/buybox_asin_report.csv)

Markdown summary report: [buybox_report.md](sandbox:/mnt/data/buybox_report.md)

Reusable scoring script for future CSVs: [buybox_automation_score.py](sandbox:/mnt/data/buybox_automation_score.py)

One caution: this is **daily** chart data, so it hides intraday Buy Box flips, and it does not include offer-level shipping speed or seller metrics. That means it is very good for screening, but not enough by itself to explain every single Buy Box decision.

[1]: https://sell.amazon.com/blog/amazon-pricing-strategies "Amazon pricing strategies: How to price products to drive sales - Sell on Amazon"
