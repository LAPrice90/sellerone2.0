# SO21 Proposal Report Standard

Created: 2026-06-08
Status: standard

## Plain-English Purpose

When SellerOne suggests a meaningful improvement, Luke should receive a proper customer-style proposal, not a loose technical note.

The report should help Luke decide whether the change is worth doing.

## When To Use This Standard

Create a proposal report before major changes involving:

- automation
- storage cleanup
- data lifecycle
- maintenance mode
- runtime safety
- process redesign
- cost or time savings
- reliability improvements
- business workflow changes

Small fixes do not need a full proposal unless Luke asks for one.

## Standard Report Structure

### 1. One-Page Summary

Include:

- problem
- recommendation
- expected benefit
- risk
- decision needed

### 2. Current Situation

Explain what is happening now in plain English.

Use current evidence, not chat memory.

### 3. Proposed Change

Explain what would change and what would stay protected.

### 4. Business Case

Cover:

- time saved
- reliability improvement
- storage saved
- risk reduced
- operational simplicity

### 5. Options

Give practical options:

- do nothing
- small safe change
- full recommended change

### 6. Graphs And Visuals

Use simple charts where evidence exists.

Good chart types:

- storage by folder
- duplicate data by family
- active vs proved vs blocked tickets
- failure count by flow
- automation count before and after
- runtime risk by category
- estimated effort vs benefit

### 7. Risk And Guardrails

State:

- what could go wrong
- what is protected
- rollback route
- stop conditions

### 8. Success Measures

Define how we know the change worked.

Examples:

- storage reduced by X GB
- duplicate output reduced by X percent
- active tickets reduced from X to Y
- restart recovery confirmed after reboot
- no protected runtime changes occurred

### 9. Decision Box

End with one clear decision:

- approve
- hold
- reject
- needs more evidence

## Output Formats

Preferred formats:

- short Markdown report under `CONTROL/`
- optional HTML or PDF for presentation
- supporting CSV or chart image where useful

## Rules

- Do not exaggerate savings.
- Do not invent numbers.
- If evidence is missing, say so.
- Graphs should use real measured data where possible.
- Protected actions still need approval.
- A proposal is not permission to implement.
