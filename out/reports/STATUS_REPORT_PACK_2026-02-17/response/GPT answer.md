You can step this up cleanly with the “tree” approach, but there are 3 hard problems you need to fix/lock down first (otherwise you’ll scale instability, not intelligence).

## 1) Immediate plan changes I recommend (based on your Phase 1 evidence)

### A) Enforce single-writer per SKU before *any* write expansion

Your pilot shows clear signs of writer contention (your note about Profit Protector Pro still running, plus “external price jump” events and a high `WRITE_NOT_APPLIED` rate). 
If you expand writes while another repricer can still touch those SKUs, you will:

* fail to apply raises (you already saw this pattern),
* corrupt learning windows,
* burn API calls,
* and end up “fighting yourself.”

This is already explicitly required in Masterplan v9 (“single-writer per SKU”). 
So the change isn’t philosophical — it’s operational: **make writer-mode a first-class, per-SKU gate in the Head output** (PPP vs CODEX_H vs READ_ONLY), and hard-block writes if not CODEX_H.

### B) Gate H-cycle when daily intel is missing (stop “blind operation”)

You have repeated “daily_intel missing for today” events in H-cycle logs (191 occurrences). 
That means you’re sometimes making decisions without the A-cycle ceiling/intel layer you designed.

Change required:

* If today’s A-cycle intel row is missing/stale for the SKU → **auto-run A-cycle refresh**; if still missing → **DEFENSIVE_HOLD / HOLD_OBSERVE** and block learning and probing.

This is consistent with the v9 architecture (A-cycle builds intelligence; H-cycle executes safely inside constraints). 

### C) Align CPT handling across docs (remove CPT-as-ceiling drift)

You explicitly called out CPT confusion earlier, and your status pack says you already updated behavior to “pin-and-observe,” not clamp. 
But your Phase 1 execution spec still contains a ladder step that uses CPT as part of eligibility ceiling resolution (`FOEP -> CPT -> MANUAL -> LAST_KNOWN_SAFE`). 

Masterplan v9 is clear: **CPT is risk telemetry in Phase 1; it should not be used as a deterministic ceiling clamp**. 
So: update the Phase 1 spec (and any code paths still doing `CPT*1.2`) to match v9:

* CPT: store, trend, classify risk; do not clamp targets unless you *explicitly* enable a separate empirical CPT ceiling mode later.

### D) Stop no-change write spam before scaling

Your Phase 1 logs show many “APPLIED” events where `old_price == new_price` at the hard floor, which strongly suggests you’re writing even when no change is required. (That’s API burn and noise, and it will get worse at portfolio scale.)  
Fix: **“no change” must be `NO_WRITE_REQUIRED`, not a write**.

---

## 2) Convert the “spider web” into a strict trunk → branches tree

What you described (“start with trunk, then branches like buy box within floor/ceiling…”) is exactly the right way to prevent idea sprawl. It also maps cleanly to v9’s state machine and ceilings model. 

### The trunk (routing gates) — always evaluated first

This is the non-negotiable “can we even act safely?” layer:

1. **Writer gate**
   If `pricing_writer_mode != CODEX_H` → READ_ONLY (collect data only; no learning updates from outcomes).

2. **Stock gate**
   If `available <= 0` → PARKED (no writes; low cadence; weekly intel unless restock candidate).

3. **Daily intel gate**
   If today’s A-cycle intel missing/stale → refresh; if still missing → DEFENSIVE_HOLD (no optimisation/probing).

4. **Outcome measurability gate**
   If Buy Box not present or winner unknown → HOLD_OBSERVE (no learning; conservative).

5. **Ceiling integrity gate**
   If `final_ceiling < hard_floor` → fail-safe (no action; escalate).

This trunk is consistent with your current Phase 1 spec constraints and v9’s “ceiling clamps before optimisation” principle.  

### Branch 1: Buy Box price zone vs your floors/ceilings (your “within/below/above” idea)

Define:

* `BB` = Buy Box landed price (or best rival landed if BB missing but rivals exist)
* `HF` = hard floor
* `SF` = soft floor (ROI floor / target band)
* `CEIL` = final ceiling

Zones:

* **Z0: BB < HF** → cannot win profitably
  Action: hold HF / park / (optional) pressure recommendation only.
* **Z1: HF ≤ BB < SF** → winnable but below target ROI
  Action: choose “defend thin margin” vs “hold SF and give up BB” based on profit/day evidence.
* **Z2: SF ≤ BB ≤ CEIL** → normal profitable competitive space
  Action: profit-led optimisation, delta learning if confidence low.
* **Z3: BB > CEIL** → market is above your allowed cap
  Action: harvest upward toward CEIL (slow ladder), monitor.

This branch is the “tree trunk to first limbs” that prevents aggressive default behavior.

### Branch 2: Buy Box control bucket (your “start with what we control” rollout)

Use win-rate buckets computed from your snapshot facts:

* **B0 (Control):** win-rate ≥ 80%
* **B1 (Rotating):** 20–80%
* **B2 (Not winning):** < 20%

This bucket is what you use to decide rollout order:

* Start with **B0** SKUs (harvest mode, low risk).
* Then **B1** (stabilise + learn deltas).
* Only later **B2** (defend/ignore decisions).

Your status pack already proposes win-rate integration and gives the exact KPI definition. 

### “Binary code system” without overengineering

You don’t need a complex binary system yet — just a compact scenario code emitted every cycle, so every log line tells you which branch you’re in.

Example format:
`W{writer}S{stock}I{intel}O{outcome}Z{zone}B{bucket}`

So `W1S1I1O1Z2B0` means “safe to act, in stock, intel OK, outcome OK, profitable zone, we control BB.”

This gives you the “tree index” you wanted without building a spider web.

---

## 3) A phased step-up plan that matches your intent

Masterplan v9 already has a stage roadmap; what you’re missing is a **bridge plan** between “single SKU lab” and “portfolio repricing.” 
Here’s the phased plan I recommend, aligned to your current reality and your “leave glues alone” requirement.

### Phase 1.5 (mandatory hardening) — do this before expanding writes

Goal: make the trunk gates real, not aspirational.

Deliverables:

* **Writer-mode enforced per SKU** (PPP / CODEX_H / READ_ONLY). Hard block writes if not CODEX_H.  
* **Daily intel gate**: if missing → auto-refresh; else defensive_hold / hold_observe. 
* **No-change = no write**, plus cooldown + max writes/day actually enforced.
* **CPT policy aligned**: store + risk classify; stop using CPT*1.2 as a ceiling unless explicitly enabled later.  

If you skip this, you’ll scale write failures and false learning.

### Phase 2 (Head rollout across all listings) — safe, mostly read-only

Goal: fill the “Head” role across your catalogue so you can pick battles logically.

Outputs to build daily (stock-gated):

* **SKU config**: HF, SF, manual cap (demand proxy), strategy tag (SNL vs STANDARD), writer_mode, API cadence tier, do_not_touch flag (glues). 
* **Stock-gated candidate list** (available > 0) — you already started this. 
* **Buy Box evidence pack**: win-rate %, outcome-known %, price-gap distributions (Supervisor can’t make decisions without this). 
* **Restock overlay**: “projected ROI at feasible ceiling” so you stop reordering low-upside SKUs. 

Writes in Phase 2:

* Default: **no writes** (READ_ONLY), except a tiny allowlist of safe SKUs in Phase 3.

### Phase 3 (write expansion, only where you control BB) — your proposed step

Goal: do exactly what you said: start on products where you already control BB, and leave glues alone.

Eligibility gate (must all be true):

* writer_mode = CODEX_H (PPP off)
* in stock
* daily intel present
* outcome known is high (BB winner reliably measurable)
* win-rate bucket B0 (≥80%)
* not “do_not_touch” (glues)

Behavior:

* **Harvest mode** (not “match mode”): raise slowly until you see evidence of BB loss or velocity drop, then step back.
* Step sizes:

  * SNL: +£0.10 to +£0.20
  * STANDARD: +£0.50 to +£1.00
    (This is already consistent with the SNL/Standard guidance in v9.) 

### Phase 4 (write expansion into contested-but-profitable SKUs)

Goal: start “defend” mode only where BB is inside your feasible profit zone (Z2) and the economics justify duelling.

Eligibility gate:

* zone Z2 (BB between SF and CEIL)
* expected profit/day above threshold
* volatility/health acceptable
* budget tier assigned

Behavior:

* regain + delta learning (effective-price space with delivery value)
* conservative ladder depth while confidence is low

### Phase 5 (seller behaviour intelligence + pressure recommendations only)

This is where your “game of chess per seller” idea becomes real, safely. 
Masterplan v9 already supports:

* variant-level seller memory (reaction speed, persistence, floor confidence),
* seller priority,
* pressure as recommendation + manual approval only. 

Do **not** automate pressure execution until you’ve got a serious case history (v9 already sets that expectation). 

### Phase 6 (scale hardening)

Notifications + refresh orchestration + budgets + portfolio governor become mandatory before broad rollout. 
Until then, keep portfolio coverage mostly read-only with selective writes.

---

## 4) Your “roll out Head now + reprice BB-controlled items, skip glues” idea — what I’d change

### Keep the intent, change the execution:

* ✅ Yes: **roll out Head now** (safe, high leverage).
* ✅ Yes: **start writes only on BB-control SKUs** first.
* ✅ Yes: **exclude glues** (tag them do_not_touch; keep PPP on them for cashflow stability).
* ❌ Change: don’t call it “repricing matching.”
  If you already control BB, the money is usually in **harvesting upward** until you see BB/velocity resistance, not “matching.”

Also: you cannot do Phase 3 safely until Phase 1.5 writer-lock is enforced, because your pilot logs strongly suggest price raises won’t stick while another repricer is involved. 

---

## 5) Concrete evidence from your current 12-SKU pack (so you can pick Phase 3 candidates)

From your dataset pack (12 SKUs currently in the stock-gated list) , here’s the joined summary I generated (current BB gap + win-rate):

* One SKU appears to be true “BB control” in this dataset window (100% win-rate).
* Most others are 0–25% win-rate, meaning they’re not Phase 3 “harvest” candidates yet; they’re Phase 4 (defend) or read-only.

I saved the joined file for you here:
[Download head_candidates_2026-02-17_summary.csv](sandbox:/mnt/data/head_candidates_2026-02-17_summary.csv)

---

## 6) I wrote you a patch you can paste into Masterplan v9 (tree + scenario codes + phased rollout)

This is designed to stop idea sprawl: it formalises trunk gates, buy box vs floor/ceiling zones, BB-control buckets, and the next phases.

[Download v9_patch_tree_phased_rollout_2026-02-17.md](sandbox:/mnt/data/v9_patch_tree_phased_rollout_2026-02-17.md)

It is written as a new section you can append (similar to your existing “v9 patch” style). 

---

## 7) What to do next, in order (no extra complexity)

1. **Phase 1.5 hardening**

   * Writer-mode per SKU enforced.
   * Daily-intel missing = hold/defensive, not normal execution.
   * No-change writes eliminated.

2. **Head rollout (Phase 2)**

   * Generate HF/SF/cap + strategy tag + do_not_touch + cadence tier per SKU.
   * Output daily supervisor evidence pack (win-rate + gap + outcome-known %).

3. **Phase 3 enablement**

   * Only B0 SKUs (BB control) move into harvest writes.
   * Glues stay PPP (read-only monitoring only).

4. **Only after that** start defending contested SKUs (Phase 4), because that’s where you’ll accidentally recreate the “aggressive start” if you don’t have the tree + evidence gates.

This keeps the system as a tree: trunk first, one branch at a time, each branch earning its right to exist with data.
