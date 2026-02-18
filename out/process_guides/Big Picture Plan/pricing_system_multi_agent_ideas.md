# Multi‑Agent Pricing System – Working Ideas (Draft)

> **Status:** Living document / idea capture
> **Purpose:** Hold evolving concepts for the multi‑agent pricing system while the foundation plan (E‑cycle) is completed.
> This file is **not executable** and does **not override** any existing plans. It is a thinking space.

---

## High‑Level Goal
Build a pricing system where **different agents operate at different speeds and costs**, coordinating to maximise long‑term profit without micromanaging the entire catalogue.

Key principles:
- Not every SKU deserves attention
- Data freshness must match decision importance
- Expensive API calls are event‑driven, not constant
- Strategy is set slowly; execution reacts quickly

---

## Agent Hierarchy Overview

```
Top Manager (daily, strategic)
   ↓
Micro‑Managers (15–60 min, tactical)
   ↓
Workers (seconds–minutes, execution)
```

Each layer has **clear authority boundaries**.

---

## 1. Top Manager (Strategic Planner)

**Purpose**
- Sets *daily intent* and *global constraints*
- Allocates attention and risk across the catalogue

**Typical Run Time**
- Once per day (e.g. 03:00–04:00)
- Quiet trading hours

**Inputs (slow, broad, cheap)**
- Value per SKU (profit/day proxy)
- Stock posture (days cover, inbound timing)
- Operational traits (returns risk, packing ease, fragility)
- Yesterday’s micro‑manager summaries

**Decisions Made**
- SKU classification for the day:
  - REST (ignore)
  - WATCH
  - LIVE
- Global tolerances:
  - How many SKUs may operate below target ROI
  - Capital at risk
  - Aggression budget
- Default pricing posture per SKU

**Explicitly Does NOT**
- React to minute‑by‑minute price moves
- Call competitive pricing APIs repeatedly

---

## 2. Micro‑Managers (Tactical Supervisors)

**Purpose**
- Decide *attention level* and *rules* for assigned SKUs
- Act as the bridge between strategy and execution

**Typical Run Time**
- Every 15–60 minutes

**Inputs (medium cost)**
- Worker reports
- Delta effectiveness (is the current delta still working?)
- Condition changes:
  - Shipping speed / Prime eligibility
  - Depot / fulfilment changes
- Market stability signals

**Decisions Made**
- Promote SKU to LIVE
- Downgrade SKU to WATCH
- Freeze SKU (stable conditions)
- Escalate exception to Top Manager

**Explicitly Does NOT**
- Micro‑adjust prices
- Continuously poll full competitive context

---

## 3. Workers (Execution Agents)

**Purpose**
- Apply pricing actions within given bounds
- React in near‑real‑time

**Typical Run Time**
- Seconds to minutes
- Only for SKUs marked LIVE

Workers **do not think**. They execute rules.

---

## API Call Types (Critical Concept)

Different actions require different data depth.

### Call Type A – Full Competitive Snapshot (Expensive)

**Provides**
- Buy Box winner
- Fulfilment differences
- Offer counts
- Shipping advantage

**Used When**
- Entering LIVE mode
- Delta stops working
- Buy Box not achieved despite expected delta
- Conditions change (Prime, Amazon enters, shipping improves)

**Frequency**
- Event‑driven only

---

### Call Type B – Lightweight Price Check (Cheap)

**Provides**
- Current Buy Box price
- Price movement detection

**Used When**
- SKU is LIVE
- Known delta is being applied

**Frequency**
- Every 30–120 seconds (LIVE SKUs only)

---

### Call Type C – Delta Application (No API)

**Provides**
- Price action based on previously learned delta

**Used When**
- Conditions unchanged
- Buy Box success confirmed recently

This avoids unnecessary API calls.

---

## Delta‑Driven Behaviour Loop (Formalised)

1. Micro‑manager promotes SKU to LIVE
2. Worker performs **Full Snapshot**
3. Worker computes delta (e.g. −£0.30)
4. Worker enters delta mode:
   - Applies price = competitor − delta
   - Uses lightweight checks only
5. If Buy Box not achieved:
   - Escalate → Full Snapshot
   - Recompute delta
6. If competitor price stalls:
   - Worker reports "stable"
7. Micro‑manager downgrades SKU to WATCH
8. WATCH SKUs checked every 2–4 hours
9. Activity resumes → re‑promote to LIVE

No waiting until the next day.

---

## ROI Boundaries & Exceptions

- Workers **cannot** break hard floors
- Micro‑managers **can request** exceptions
- Top Manager **decides**:
  - Temporary lower ROI allowance
  - Which SKUs may breach targets

Favourable traits for exceptions:
- Easy to pack
- Low returns
- Fast stock recovery

---

## Catalogue Lanes (Attention Control)

- **Lane A – Strategic / Micro‑Managed**
  - High value
  - Volatile
  - Worth fighting

- **Lane B – Passive / Opportunistic**
  - Profitable but calm
  - Minimal attention

- **Lane C – Exit / Harvest**
  - Thin margin
  - Irrational competition
  - Capital redeployment

Only Lane A SKUs ever receive workers.

---

## Key Anchors (Do Not Drift)

- Managers think in **days**
- Micro‑managers think in **hours**
- Workers fight in **minutes**

- Not all SKUs deserve intelligence
- Expensive data is event‑driven
- Strategy first, reaction second

---

## Notes for Future Compilation

- This document feeds the **next formal plan**
- Ideas here are provisional and may change
- No implementation should reference this file directly

---

