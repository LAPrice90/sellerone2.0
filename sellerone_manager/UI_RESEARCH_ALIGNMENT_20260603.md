# UI Research Alignment - 2026-06-03

## Plain English

The research changes the UI approach from "make better screens from the current tables" to "build a small decision pipeline, then render the approved decision state as simple screens".

This matters because the current Codex/Streamlit failure mode is table-first:

- read CSV
- show table
- add filters
- add warnings
- add buttons
- create clutter

That is not the UI Luke needs.

## What Changes

### 1. The UI Is A Rendered View, Not The Source Of Truth

The UI should not decide what is true by reading every cycle output directly.

Instead, O/UI should receive approved artifacts such as:

- `today_work_state`
- `restock_decision_cards`
- `product_truth_cards`
- `supplier_work_cards`
- `money_confidence_cards`
- `blocked_decision_cards`

The UI renders these simply.

The underlying manager/MOT/proof system remains the place where evidence is checked.

### 2. Raw Tables Move To Proof/Admin

Large CSV tables, scanner stats, row counts, and proof logs should not be the main business screen.

They stay available in:

- manager MOT
- Proof/Admin UI
- worker/debug files

Luke's working pages should show cards, statuses, next actions, and blocked reasons.

### 3. Build A UI Pipeline Before Building More UI Pages

The next UI builder should not start by adding more Streamlit pages.

It should first define:

- what artifact powers each screen
- what fields are allowed on that screen
- what status labels exist
- what blocks a row from being shown as ready
- what action is only a draft
- what action needs Luke

### 4. The Manager Stays As The Overseer

The main manager chat owns direction and safety.

A separate UI Builder chat should build only from this plan and should not invent business logic.

### 5. Sites Does Not Change The Immediate Plan

Sites may help later with hosting and access control.

It does not solve the main problem by itself.

The main problem is that the UI needs a contract-first decision layer before it needs better hosting.

## New UI Architecture

```text
A/B/E/F/H/O evidence
  -> manager/MOT proof checks
  -> O decision-state builder
  -> typed UI artifacts
  -> simple human UI screens
  -> Proof/Admin only when detail is needed
```

## First UI Builder Job

Do not code the visible UI first.

First build the contract for:

- `today_work_state`
- `restock_decision_cards`
- `blocked_decision_cards`

Then render:

- Today
- Restocking
- Product detail

## Success Rule

The UI is successful only when Luke can open it and answer:

- What should I look at today?
- What products can I manually consider?
- Why is this product blocked?
- What proof is missing?
- What decision is mine?

without reading raw cycle tables.

## Immediate Change To Current UI Plan

Do not continue table-first Streamlit expansion.

Continue with:

1. UI artifact contracts
2. Today state builder
3. Restock decision card builder
4. simple rendered screens
5. Proof/Admin for raw tables
