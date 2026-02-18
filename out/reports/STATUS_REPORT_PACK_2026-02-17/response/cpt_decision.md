Good. This is exactly the right place to tighten things.

Right now CPT is:

* Called in **A-cycle**
* Called again in **H-cycle**
* Sometimes used as ceiling
* Sometimes just observed
* Sometimes limited to “one call”

That’s architectural drift. You need one clear policy.

---

# Step 1 — Decide what CPT *is*

Before we decide when to call it, define its role.

From your evolution so far:

* CPT is **compliance telemetry**
* CPT is **not a pricing strategy input**
* CPT is **not your demand proxy**
* CPT is **not your profit ceiling**
* CPT is **a suppression risk signal**

If you don’t lock that in, every future branch will reintroduce confusion.

So I’m going to be blunt:

> CPT should not be used in H-cycle optimisation logic at all.
> It should never influence target price directly in Phase 1–3.

If you want empirical ceilings later, that’s a separate module.

---

# Step 2 — Separate the concerns

Right now CPT is being used in two places:

## A-cycle

Intelligence building.
Ceiling detection.
Snapshot building.

## H-cycle

Execution.
Sometimes fallback ceiling.
Sometimes reactive check.

This is wrong layering.

---

# Step 3 — Clean Architecture for CPT

## Rule 1 — CPT is A-cycle only.

H-cycle should **never call CPT directly**.

Why?

Because:

* H-cycle runs frequently.
* CPT is slow and rate-limited.
* CPT state should be stable per “day”.
* You want one authoritative CPT reading per SKU per day.

If H calls CPT opportunistically you create:

* Inconsistent ceilings
* Intra-day drift
* Rate burn
* Branch instability

---

# Step 4 — When should A-cycle call CPT?

Not “one call per run”.

It should be:

### CPT Call Policy

Call CPT in A-cycle if ALL are true:

1. SKU is in stock.
2. SKU is write-enabled (CODEX_H or PPP off for this SKU).
3. Last CPT call > 24h ago OR

   * Suppression detected
   * Ceiling breach event
   * Large price delta event
4. SKU is not parked.
5. SKU is not do_not_touch (glues under PPP).

That’s it.

No global “one CPT call”.
No random H-cycle call.

---

# Step 5 — What A-cycle should do with CPT

When CPT is called:

Store:

* `cpt_price`
* `cpt_status`
* `cpt_delta_vs_buybox`
* `cpt_risk_flag`
* `cpt_timestamp`

Then derive:

* `cpt_risk_band` (LOW / MEDIUM / HIGH)

Example logic:

If Buy Box > CPT by > X% → risk HIGH
If Buy Box within small delta → risk LOW
If CPT missing → risk UNKNOWN

But crucially:

**Do not clamp CEIL here.**

Instead:

CEIL continues to be:

* FOEP
* Manual cap
* Demand proxy
* Last known safe
* etc.

CPT becomes:

```
risk_overlay = cpt_risk_band
```

And H-cycle only reads `risk_overlay`.

---

# Step 6 — What H-cycle does with CPT (read-only)

H-cycle should only:

* Read `cpt_risk_band`
* If HIGH → enter DEFENSIVE mode
* If LOW → normal
* If UNKNOWN → hold or reduce aggression

It should never:

* Call CPT
* Modify ceiling based on CPT
* Recalculate target from CPT

This keeps trunk stable.

---

# Step 7 — Why your current setup feels messy

Because CPT is currently:

* Part ceiling.
* Part telemetry.
* Part fallback.
* Part reactive.
* Sometimes single-call limited.
* Sometimes opportunistic.

That’s not a tree.
That’s a web.

---

# Step 8 — Concrete Decision Tree (CPT simplified)

## A-cycle

For each eligible SKU:

```
if eligible_for_cpt_call:
    call CPT
    store result
    compute risk_band
else:
    reuse last CPT result
```

## H-cycle

```
risk = read cpt_risk_band

if risk == HIGH:
    restrict upward moves
    slow ladder
elif risk == UNKNOWN:
    avoid aggressive moves
else:
    normal execution
```

No CPT calls in H.
No ceiling mutation.
No fallback CPT as CEIL.

---

# Step 9 — Which SKUs get CPT calls?

Not all of them.

Tier them:

### Tier 1 — Active Write SKUs

(Phase 3+ SKUs)
→ Daily CPT allowed.

### Tier 2 — Read-only but in stock

→ CPT every 3–7 days.

### Tier 3 — Parked / OOS

→ No CPT.

### Tier 4 — Do_not_touch (glues under PPP)

→ CPT only for monitoring (optional weekly).

This avoids burning calls on SKUs that cannot act.

---

# Step 10 — What you should remove immediately

1. Any CPT*1.2 ceiling logic.
2. Any H-cycle CPT call.
3. Any “single global CPT call per run” rule.
4. Any CPT fallback in eligibility ladder.

Replace with:

* Structured CPT scheduling inside A-cycle.

---

# Final Answer to Your Core Question

> We need to decide how and when CPT is called and for what SKUs.

Decision:

* CPT is A-cycle only.
* CPT is telemetry only.
* CPT never defines CEIL in current architecture.
* CPT is called per SKU based on eligibility + staleness.
* H-cycle reads risk state only.
* SKUs are tiered by activity to control API load.

---

If you want next:

I can write:

* A clean `CPT_POLICY.md`
* A small state diagram for trunk integration
* Or a Codex-ready patch section for v9

Tell me which direction you want.
