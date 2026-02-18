# SellerOne 2.0 — Master Plan

## Purpose
Build a robust, explainable, and profit-focused Amazon FBA system that:
- Observes market behaviour before acting
- Treats competition as repeated games, not static price ladders
- Prioritises profit per day over raw velocity
- Automates only after human strategy is proven

This document defines the long-term structure and philosophy.
Execution details live in phase plans and Codex tasks.

---

## Core Principles (Non-Negotiable)

1. Observation before automation  
2. Evidence before thresholds  
3. Symmetric competition tracking (we are just another seller)  
4. Human-in-the-loop escalation  
5. Profit/day beats volume  
6. Systems must be explainable after the fact  
7. Aggression is time-boxed and justified, never default

---

## System Layers

**A — Data Collection**
- API-first, single-owner
- Snapshot + history
- No decisions

**B/C — Accounting Truth**
- Orders, COGS, VAT, fees
- Token system
- Source of financial truth

**E — Decision Intelligence**
- Computes facts, signals, and observations
- No execution
- No thresholds until evidence exists

**F — Execution**
- Manual → assisted → automated
- Guardrailed
- Always reversible

---

## Phased Roadmap

### Phase 0 — API-First Data Spine (Complete)
- Stable API collection
- Logged, throttled, observable
- E runs compute-only

---

### Phase 1 — Competition Observation & Behaviour Memory
Goal:
- Observe how sellers actually behave on listings
- Build memory of price, delivery, and persistence
- No strategy, no thresholds

Status:
- Complete - Phase 1.0 schema locked at `Locked v1.0` on 2026-02-09
- Lock document: `out/process_guides/live_plan/phase_1_0_observation_schema.md`

Includes:
- Seller price envelopes (min / max / median)
- Delivery promise observation
- Seller role signals (leader / follower / aggressor)
- Entry, exit, and re-entry patterns
- Symmetric tracking of our own behaviour

---

### Phase 2 — Forward Unit Economics
Goal:
- Move beyond historical ROI
- Enable decision-grade projections

Includes:
- Current unit cost basis
- Expected refund cost
- Forward profit and ROI at given prices
- Break-even and floor concepts (observed, not enforced yet)

---

### Phase 3 — Lane Selection (Attention Allocation)
Goal:
- Decide which SKUs deserve effort

Concept:
- Lane 0: Passive
- Lane 1: Managed
- Lane 2: Micro-managed

Driven by:
- Expected profit per day
- Competitive volatility
- Stock posture
- Opportunity, not emotion

---

### Phase 4 — SKU Micromanager (Decision Layer)
Goal:
- Treat each SKU as a managed business

Includes:
- State-based thinking (cooperate, probe, pressure, etc.)
- Time-boxed escalation
- Reason codes
- Expiry on aggressive states

No automation yet.

---

### Phase 5 — Assisted Execution (Human Approval)
Goal:
- System proposes actions
- Human approves

Includes:
- Target price
- Floors and ceilings
- Reasoning
- Confidence and expiry

---

### Phase 6 — Controlled Automation
Goal:
- Limited, reversible automation
- Only for proven SKUs and scenarios

Includes:
- Cooldowns
- Kill switches
- Hard guardrails
- Audit trails

---

## Explicit Non-Goals (Until Proven)

- No blind repricing
- No global thresholds without data
- No permanent aggression modes
- No price-only decision logic
- No automation without explainability

---

## Living Sections (Expected to Expand)

- Competition roles and scenarios
- Escalation framework
- Observation schemas
- Strategy playbooks (derived from evidence)

These expand incrementally via structured edits.
