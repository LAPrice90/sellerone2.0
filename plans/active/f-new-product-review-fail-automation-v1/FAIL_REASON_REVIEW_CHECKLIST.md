# New Product Review Fail Reason Checklist

Purpose:
- Use this file to review each fail reason one at a time.
- Mark each item as reviewed only after the behavior makes sense in plain English.
- Keep this file as the simple tracking list so we do not lose the thread in chat.

Current overall status:
- Code fix applied: yes
- Isolated proof passed: yes
- Full live rebuild proof: not yet proven
- Reason: the F live process was actively running, so the final live rebuild must wait for a safe F-owned proof window.

## 1. Wrong Product Match

Review status:
- [x] Needs user review
- [ ] Accepted
- [x] Needs correction

What was failing:
- The supplier item and the Amazon item can share the same barcode because the Amazon product is found from that barcode.
- That means barcode match alone is not useful proof that the opportunity is safe.
- The real risk is that the barcode can point to the wrong pack, wrong variant, wrong bundle, wrong size, or wrong listing context.

What was changed:
- Current fix status: not good enough yet.
- The first pass used existing identity warning codes, including barcode conflict and weak match codes.
- After review, barcode-based identity is not enough because the system already searches by barcode.
- This fail reason needs a second correction focused on non-barcode evidence.

Expected automatic behavior:
- Same barcode but wrong pack, variant, size, quantity, bundle, or title meaning = remove from clean Pass or manual review.
- Barcode-only confidence must not be treated as enough proof.
- The system needs to compare practical listing details, not just barcode match.

Proof status:
- Current barcode/identity gate tests passed, but they do not fully solve this fail reason.
- Needs follow-up correction before this item can be marked accepted.

Correction needed:
- Build a non-barcode product identity check using available fields such as supplier title, Amazon title, brand, pack size, quantity, model, and variant wording.
- Route clear pack/variant/title conflicts out of clean Pass.
- Route uncertain pack/variant/title conflicts to manual review.
- Keep barcode as a lookup clue, not as final proof.
- Use the dedicated title-match agent plan:
  - `plans/active/f-new-product-review-fail-automation-v1/TITLE_MATCH_AGENT_PLAN.md`
- Use the current sample collection:
  - `plans/active/f-new-product-review-fail-automation-v1/TITLE_MATCH_AGENT_SAMPLE_COLLECTION.csv`
- Current checker status:
  - read-only checker built
  - F019 clean-Pass routing wired
  - seed examples handled correctly
  - 9 seed rows checked
  - 0 seed mismatches
- This item still cannot be fully accepted until live-loop proof confirms the F-owned rebuild uses the new routing safely.

Rule agreed on 2026-05-20:
- Similar title alone should not automatically fail.
- Suspicious title plus extreme ROI/profit should automatically fail.
- Suspicious title without extreme ROI/profit should go to user guidance.

F032 cycle link:
- `plans/active/f-new-product-review-fail-automation-v1/F032_REVIEW_INTELLIGENCE_CYCLE.md`

## 2. Seller-Controlled Or Risky Seller Situation

Review status:
- [ ] Needs user review
- [ ] Accepted
- [ ] Needs correction

What was failing:
- Some Amazon listings may be controlled by the brand, Amazon, or a dominant seller.
- These products can look profitable but still be bad opportunities because we may not realistically win the sale.

What was changed:
- The seller-risk check was moved into the main decision order.
- It now acts as a top-level reason for removing or reviewing a product.

Expected automatic behavior:
- Strong seller-control risk = remove from clean Pass.
- Unclear seller-control risk = review instead of automatic approval.
- No seller-control risk = allowed to continue to the next checks.

Proof status:
- Existing seller-risk logic is still active.
- Priority order was corrected.
- Live rebuild proof still pending.

## 3. Profit Looks Better Than It Really Is

Review status:
- [ ] Needs user review
- [ ] Accepted
- [ ] Needs correction

What was failing:
- Some products could appear profitable because the final number looked good.
- The deeper calculation could still be weak, inflated, or based on fragile cost logic.

What was changed:
- The system now checks profit quality before allowing clean Pass.
- Weak or suspicious profit is routed out earlier.

Expected automatic behavior:
- Clearly weak profit = remove from clean Pass.
- Suspicious or borderline profit = manual review.
- Solid profit = allowed to continue to the next checks.

Proof status:
- Isolated tests passed.
- Live rebuild proof still pending.

## 4. Demand Evidence Is Too Weak

Review status:
- [ ] Needs user review
- [ ] Accepted
- [ ] Needs correction

What was failing:
- Some products did not have enough evidence that they sell well enough.
- Missing evidence could make the product look more certain than it really was.

What was changed:
- The demand gate remains active.
- Missing demand evidence is treated as an evidence gap, not hidden or guessed.

Expected automatic behavior:
- Weak demand = remove from clean Pass.
- Missing demand evidence = review or rescan path.
- Strong demand = allowed to continue to the next checks.

Proof status:
- Existing demand logic remains active.
- Live rebuild proof still pending.

## 5. UK Review Or Variant Risk

Review status:
- [ ] Needs user review
- [ ] Accepted
- [ ] Needs correction

What was failing:
- Some listings have UK review or variant signals that make them riskier than they look.
- These risks could be buried behind other checks.

What was changed:
- The UK review gate remains active.
- It now sits in a clearer priority order so review risk is not hidden behind lower-priority reasons.

Expected automatic behavior:
- Clear UK review or variant risk = remove from clean Pass or manual review.
- No clear risk = allowed to continue.

Proof status:
- Existing UK review logic remains active.
- Live rebuild proof still pending.

## 6. Feedback Was Too Vague To Learn From

Review status:
- [ ] Needs user review
- [ ] Accepted
- [ ] Needs correction

What was failing:
- Manual review feedback was too free-form.
- The system could not reliably group the reasons you rejected products.

What was changed:
- Structured feedback reasons were added:
  - wrong product
  - seller controlled
  - profit too weak
  - demand too weak
  - review or variant risk
  - missing evidence
  - other

Expected automatic behavior:
- Future manual review decisions should be saved with a clear reason.
- The feedback report can group those reasons and show what the system needs to learn next.

Proof status:
- Review contract passed.
- Feedback theme report built successfully.
- Existing old feedback does not yet contain the new reason codes because it was created before this change.

## 7. Empty Source Window Could Wipe Good Outputs

Review status:
- [ ] Needs user review
- [ ] Accepted
- [ ] Needs correction

What was failing:
- The review builder could rebuild from an empty or stale source window.
- That could overwrite good review files with blank output.

What was changed:
- A safety stop was added.
- If the selected source window is empty but existing review files contain data, the system blocks the rebuild.
- It preserves the existing files instead of replacing them with empty files.

Expected automatic behavior:
- Empty source window + existing review data = block rebuild and preserve files.
- Valid source window with rows = allow rebuild.

Proof status:
- Guard test passed.
- Live guard check preserved:
  - Pass rows: 3
  - Near-miss rows: 1600

## Current Evidence

Latest proof results:
- F019 focused tests: 45 passed
- F020 review contract: pass
- F020 review rows: 21
- F020 invalid reason-code rows: 0
- F021 triage rows: 2337
- F021 pass rows caught: 31
- F021 unclassified rows: 0
- F030 feedback rows: 21
- F030 manual fail rows: 18
- F030 manual pass rows: 3
- F030 unclassified manual fail rows: 0

Protected current review output counts:
- Clean Pass rows: 3
- Near-miss rows: 1600

## Final Live Proof Still Needed

Why it is still pending:
- The F live process was actively running and writing files.
- A full live rebuild should not be run over the top of that process.

Safe trigger:
- Run live proof only when `out/systems/F/price_list_manager/live/live_cycle.lock` is absent or FPM130 reaches a safe maintenance boundary.

Files to check during live proof:
- `out/analysis_reports/f_live_price_file_launch_baseline_latest.csv`
- `out/systems/F/live/f_screening_row_state_live.csv`
- `out/analysis_reports/f_live_price_file_review_summary_latest.csv`
- `out/analysis_reports/f_live_price_file_pass_review_latest.csv`
- `out/analysis_reports/f_live_price_file_near_miss_review_latest.csv`

Success condition:
- The source window has real rows.
- The review builder does not replace good outputs with blank files.
- The summary separates identity, seller-risk, profit, demand, and UK-review reasons.
- F020, F021, and F030 still pass after the rebuild.
