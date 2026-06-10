# SellerOne UI System Plan - 2026-06-03

## Plain English

The UI is not currently good enough to be the main working surface. More cycle work will keep getting messy if the UI does not clearly show what Luke needs to decide, what is only proof, and what is unsafe.

## What The UI Must Become

The UI should be the business working surface.

The manager should stay as maintenance control.

That means:

- UI shows product, stock, supplier, order, refund, fee, and restock decision data.
- Manager watches whether the systems are working and creates repair/proof tasks.
- UI must not become another maintenance dashboard.
- Manager must not become the business data screen.

## Useful Codex/OpenAI Tools

### 1. Browser plugin

Use now.

Purpose:

- open the local UI
- inspect actual rendered pages
- click through workflows
- spot broken layout, missing buttons, confusing screens, and dead ends
- verify UI changes with screenshots/visual checks

This is the most useful immediate UI tool.

### 1A. Codex Chrome extension

Do not depend on this for SellerOne.

Reason:

- availability may vary by region, plan, and rollout
- Luke believes it is not available in the UK
- the local SellerOne UI can be reviewed with the Browser plugin instead

Use only if it becomes clearly available later.

SellerOne should not block UI progress waiting for it.

### 2. Build Web Apps / frontend skills

Use now.

Purpose:

- rebuild the UI shell
- create cleaner screens
- improve responsive layout
- add proper controls, tables, tabs, filters, badges, and decision states

### 3. Sites plugin

Use later if available.

Current public position:

- Sites is a Codex plugin for creating, saving, deploying, and inspecting hosted web apps.
- It is currently previewed for eligible Business and Enterprise workspaces.
- It is expected to roll out to more plans later.

SellerOne use:

- useful for hosting the finished internal interface
- useful for workspace sign-in and controlled access
- useful for internal tools that need saved records
- not a reason to delay the local UI rebuild

### 4. Apps/connectors for supplier work

Use later when the supplier pipeline is defined.

Likely useful:

- Gmail for supplier email history and outreach drafting
- Google Drive for documents, applications, price lists, and supplier terms
- Calendar for calls and follow-ups
- HubSpot/CRM style connector if available for sales pipeline management
- web/deep research for finding wholesalers and vetting supplier leads

This should be treated as a supplier pipeline, not a random sales plugin dependency.

## UI Rollout Plan

### Phase 1 - Stop The UI From Getting Messier

Goal:

- freeze random UI expansion
- define the main user jobs before more screens are added

Main user jobs:

- view product truth
- decide what to restock
- review refunds, fees, and ROI confidence
- manage supplier leads and supplier accounts
- manage price lists
- see blocked decisions
- approve staged actions

### Phase 2 - Inspect Current UI

Goal:

- open the current UI with Browser
- map every existing screen
- mark each screen as keep, fix, merge, or delete

Output:

- a short UI audit
- a clean navigation map
- a list of broken/confusing workflows

### Phase 3 - Build The Operator Shell

Goal:

- one clear app shell with left navigation
- no giant dashboards
- no duplicated data panels

Core sections:

- Today
- Products
- Restocking
- Suppliers
- Price Lists
- Orders and P&L
- Decisions
- Proof

### Phase 4 - Restocking Working Surface

Goal:

- help Luke manually restock safely before automation is trusted

Must show:

- product
- supplier
- current stock
- velocity
- refund drag
- fee confidence
- ROI confidence
- pack/MOQ
- proposed buy quantity
- missing data
- decision status

No automatic purchasing.

### Phase 5 - Supplier Pipeline

Goal:

- manage new supplier discovery like a sales pipeline

Stages:

- lead found
- website checked
- account requirement checked
- application needed
- contacted
- waiting reply
- approved
- rejected
- price list received
- price list scanner ready

### Phase 6 - B Money Truth Surface

Goal:

- make refunds, fees, shipping, and ROI understandable

Must show:

- API-proven money
- Sellerboard comparison only
- not proven
- suspected gap
- double-count risk

### Phase 7 - Deployment Decision

Goal:

- decide whether the UI stays local or moves to Sites/hosted internal app

Use Sites only when:

- the UI structure is stable
- access control is needed
- internal hosting is useful
- no secret values are committed
- save-before-deploy workflow is followed

## Next Manager Step

Start with a UI audit, then rebuild the operator shell before adding more O/B/F/H features into the screen.

## Current Audit

Audit completed:

- `sellerone_manager/UI_AUDIT_20260603.md`
- `sellerone_manager/UI_RESEARCH_ALIGNMENT_20260603.md`

Plain English result:

- The current Streamlit UI has useful parts, but it is too mixed together.
- The next build should not add more random screens or table-first pages.
- Continue with UI artifact contracts first, then the Today state builder, then restock decision cards, then simple rendered screens.
