# F0 Training Set Selection v1 (Pick 5-10 SKUs)

Goal:
- Choose a small set of SKUs that will teach the system the most.
- Do not choose 50. The point is learning with controlled risk.

---

## 1) Selection rules

Pick SKUs that satisfy:
- Shared listing (multiple sellers)
- Meaningful velocity (units/day), not just one-off spikes
- Stable enough demand to observe patterns
- You can tolerate mistakes (not life-or-death cashflow)
- You can get the relevant signals (price, buy box, offers, BSR if possible)

Avoid:
- 1-off slow movers with no patterns
- SKUs with missing costs (until fixed)
- SKUs where Amazon Retail is crushing price below any floor (until you have a separate policy for that)

---

## 2) Recommended mix (example)

- 2 "strategic asset" candidates
  - high velocity
  - recurring demand
  - you want to own the box if possible

- 2-3 medium value SKUs
  - normal competition
  - useful for learning COOPERATE/DEFENSIVE

- 1-2 edge case SKUs
  - hazmat / delivery disadvantage
  - known weird buy box behaviour
  - listing that forces manual pricing today

- 1 liquidation candidate
  - you want to exit or reduce exposure
  - useful to learn LIQUIDATE behaviour

---

## 3) Data you must capture for each training SKU

- sku and ASIN
- cost basis (token COGS must exist)
- current token cost must be available in E outputs
- current stock + inbound
- current buy box price and lowest offers
- BSR trend (if available)

---

## 4) Output file

Create:
- config/f_training_set.csv

Columns:
- sku
- asin
- marketplace (UK/DE/etc)
- notes
- enabled (yes/no)

This file lets H and later F focus only on the training set.

End.
