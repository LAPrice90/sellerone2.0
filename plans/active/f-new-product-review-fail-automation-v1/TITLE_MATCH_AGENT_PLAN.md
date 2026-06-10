# Title Match Agent Plan

Purpose:
- Build a morning review agent that checks whether the supplier price-file title and Amazon title describe the same sellable item.
- Treat barcode as the lookup route only, not as proof that the Amazon listing is the correct product.
- Use ROI as a warning light, especially when the title match looks too good to be true.

## Why This Exists

The real product-identity problem is title meaning.

Examples:
- Supplier says filter cartridge, Amazon says full filter device.
- Supplier says one perfume, Amazon says a different perfume.
- Supplier says phone/tablet rig, Amazon says memory card.
- Supplier says one can, Amazon says pack of 24.

The barcode can still lead us to an Amazon ASIN, but the title can reveal that the ASIN is not the right selling opportunity.

## Current Sample Collection

Sample file:
- `plans/active/f-new-product-review-fail-automation-v1/TITLE_MATCH_AGENT_SAMPLE_COLLECTION.csv`

Current seed rows:
- 9 real feedback examples pulled from existing review data.

The sample file includes:
- supplier SKU
- ASIN
- supplier title where available
- Amazon title
- user review note
- first training label
- expected agent action
- ROI/profit clue where available

Known examples already included:
- Fluval filter cartridge vs Fluval 307 external filter device
- Calvin Klein perfume vs Carolina Herrera perfume
- Joby phone/tablet rig vs Lexar memory card
- MrBeast title match clear, with review risk handled elsewhere
- TePe item where the product was not clearly present on the price file
- Plus-Plus title match clear, with seller risk handled elsewhere
- Kensington Orbit passed title match
- JVC boombox passed title match
- Embryolisse 40 ml passed title match

Important calibration correction:
- The Fluval row is not treated as a title-only automatic fail.
- It is treated as `suspicious title + extreme ROI/profit = automatic fail`.
- The found economics were:
  - supplier cost: `3.05`
  - estimated profit per unit: `123.72`
  - estimated monthly profit: `5196.24`
  - approximate profit-on-cost: `4056%`

## Agent Decision Buckets

The morning agent must classify each backlog item into one of these buckets:

- `clear_breach_remove_from_clean_pass`
  - The supplier title and Amazon title clearly describe different products.
  - Example: filter cartridge vs full filter device.

- `pack_size_or_quantity_breach`
  - The supplier title appears to be one unit, but Amazon appears to be a multi-pack or case.
  - Example: supplier can cost looks like one can, Amazon listing is pack of 24.

- `pack_size_or_quantity_needs_user_guidance`
  - The title contains numbers such as 4 pack, 6 pack, 8 pack, 24 pack, pieces, pcs, sachets, capsules, cans, bottles, refills, filters, cartridges, or set.
  - The wording could mean a true multi-pack, or it could mean a normal retail set.
  - Example: "8 piece gift set" does not automatically mean the supplier must send 8 separate products.

- `accessory_or_consumable_vs_device_breach`
  - One title describes a part, refill, cartridge, filter, case, cable, adapter, cover, blade, head, or accessory.
  - The other title describes the main device, machine, kit, console, printer, shaver, appliance, or full unit.

- `same_brand_different_product_breach`
  - The brand may be the same, but the actual product type or product name is different.
  - Same brand is not enough to pass.

- `high_roi_identity_suspicion`
  - ROI or expected profit is unusually high and the titles are not a clean match.
  - High ROI does not prove a bad match, but it should push the item into review.

- `needs_user_guidance`
  - The agent cannot make a confident decision from titles alone.
  - These rows must stay out of clean Pass until reviewed.

- `title_match_clear`
  - The supplier title and Amazon title appear to describe the same sellable item.
  - This does not pass the whole product by itself. It only clears the title-match check.

## Morning Backlog Workflow

Each morning the agent should:

1. Read the title-match backlog.
2. Compare supplier title against Amazon title.
3. Check ROI/profit clues for suspiciously high upside.
4. Put each item into one decision bucket.
5. Save a review output with status, reason, and confidence.
6. Mark rows as checked only when the agent has written a clear decision.
7. Leave uncertain rows for user guidance.

The agent must not write to Google Sheets.
The agent must not change the local product database.
The agent must not promote a row into clean Pass.
It can only mark title-match risk status for the upstream review process.

## Backlog Output Needed

The system needs a durable backlog file before the morning automation is switched on.

Required backlog fields:
- observed UTC
- supplier ID
- active run ID
- supplier SKU
- ASIN
- supplier title
- Amazon title
- supplier brand
- Amazon brand
- supplier unit cost
- Amazon sell price
- ROI or profit clue
- source file
- current review status
- agent status
- agent decision bucket
- agent explanation
- user override status

## CLF Extension

When CLF runs, extend this sample collection with CLF examples.

Expected CLF-heavy cases:
- food multi-packs
- drink cans and bottle packs
- cartons and cases
- multipack toiletries
- replacement filters or cartridges
- same-brand wrong variant
- gift sets where the number in the title is not a purchase multiplier

The CLF phase must not be accepted until these examples are added to the sample collection.

## Automation Status

Status:
- checker built
- F019 clean-Pass routing wired
- not switched on as morning automation yet

Reason:
- the checker and durable backlog now exist.
- the remaining step is choosing the morning automation time and extending this into the broader F032 Review Intelligence Cycle.

Do not switch on the morning Codex automation until:
- at least the current 9 seed examples are used as calibration checks
- the user confirms the morning review time
- the broader F032 checklist scope is confirmed

Target automation:
- morning title-match backlog review

Expected schedule:
- every morning during the normal morning review window

Success condition:
- new backlog rows are classified into clear breach, pack-size issue, needs user guidance, or clear title match
- high-ROI suspicious rows are not silently accepted
- uncertain rows remain reviewable instead of becoming clean Pass

Failure condition:
- missing supplier title
- missing Amazon title when an ASIN exists
- blank ROI/profit clue where it should exist
- agent output has unchecked rows without a reason
- agent promotes products directly instead of only flagging risk

## Built Outputs - 2026-05-20

Script:
- `scripts/one_off/F031_build_title_match_agent_backlog.py`

Test:
- `tests/test_f031_build_title_match_agent_backlog.py`

Latest outputs:
- `out/analysis_reports/f_title_match_agent_backlog_latest.csv`
- `out/analysis_reports/f_title_match_agent_decisions_latest.csv`
- `out/analysis_reports/f_title_match_agent_health_latest.csv`
- `out/analysis_reports/f_title_match_agent_sample_calibration_latest.csv`
- `out/analysis_reports/f_title_match_agent_summary_latest.md`

Latest proof:
- backlog rows: `1603`
- decision rows: `1603`
- remove from clean Pass decisions: `7`
- manual review decisions: `259`
- allow if other checks pass decisions: `1337`
- seed calibration rows: `9`
- seed calibration mismatches: `0`
- missing Amazon title with ASIN rows: `0`
- focused pytest: `4 passed`

Remaining integration:
- switch on the morning Codex automation after the user chooses the time
- extend the title-match checker into the broader `F032 Review Intelligence Cycle`
