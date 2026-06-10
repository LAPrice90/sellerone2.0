# B Fee Shipping API Proof Design

## Plain English Summary
B067 proved that weak fee and shipping money is labelled and blocked from live ROI/restocking.

The next improvement should not hard-code Sellerboard values. It should use the API-backed financial event files that B already creates.

Current evidence says the main order-level proof source is `financial_events_level3_raw`, `financial_events_level3_summary`, and `financial_events_level3_official`.

The current `fee_detail_ledger_api` file is not the main order-fee proof source. It is built from Finances v2024 transaction breakdowns and currently filters for `ServiceFee` rows. The current transaction breakdown file has shipment/refund rows, not service-fee rows, so it produces 0 fee detail rows.

## Current Evidence
- Level 3 raw financial-event rows: 199,335
- Level 3 summary rows: 154,502
- Level 3 official order/SKU rows: 11,757
- Order Master rows: 11,503
- Refund rows in the refund bridge: 221 API-proved rows
- Fee detail ledger API rows: 0
- B067 current labels: 4 API-proved, 2 Sellerboard bridge estimates, 5 not yet proven

## Proof Map
| Money field | Best current source | Current label | Matching key | Manager expectation |
| --- | --- | --- | --- | --- |
| Refund money | `financial_events_refunds_official` and B037 refund bridge | `api_source_available` | order ID, SKU, posted date, amount type, currency | Keep refund money API-proved. Sellerboard remains a witness only. |
| Refund fee reversals | `financial_events_refunds` amount types such as `Refund_Commission`, `Refund_ShippingChargeback`, `Refund_FixedClosingFee` | `api_source_available` | order ID, SKU, refund posted date, amount type, currency | Keep refund fee reversals separate from customer refund money and stock recovery. |
| Commission | Level 3 raw amount type `Commission`, official field `Commission_ExVAT` | `api_source_available` | order ID, SKU, posted date, amount type, currency | Use Level 3 financial events as direct order-level API proof. |
| FBA fee | Level 3 raw amount type `FBAPerUnitFulfillmentFee`, official field `FBA_Fee_ExVAT` | `api_source_available` | order ID, SKU, posted date, amount type, currency | Use Level 3 financial events as direct order-level API proof. |
| Shipping income | Level 3 raw amount types `ShippingCharge` and `ShippingTax`, official field `Shipping_ExVAT` | `api_source_available` | order ID, SKU, posted date, amount type, currency | Treat customer shipping paid as income, not outbound cost. |
| Shipping fee or cost | Level 3 raw has `ShippingChargeback` and refund shipping amount types, but the current official/fee-detail proof does not expose a named shipping-cost field | `repo_path_unclear` | order ID, SKU, posted date, amount type, currency | Build a read-only proof map before deciding whether this belongs in order fees, refunds, or separate shipping-cost reporting. |
| Fee-detail ledger API | `fee_detail_ledger_api` from Finances v2024 transaction breakdowns | `repo_path_unclear` | transaction ID, posted date, fee type, currency | Do not use this empty file as proof that order commission/FBA fees are missing. It proves only that this transaction-breakdown path did not find service-fee rows. |
| E ROI money confidence | E performance summary | `not_yet_proven` until fee/shipping proof mapping is connected | SKU, window, proof labels | E can display weak proof but must not treat weak proof as business-ready. |
| O restock money confidence | O restock source view | `not_yet_proven` until fee/shipping proof mapping is connected | SKU, proof labels | O can display weak proof but must not let it drive restocking confidence. |

## Manager Expectation
The manager should prove fee and shipping through the Level 3 API-backed financial event outputs first.

It should not mark B fee/shipping complete just because `fee_detail_ledger_api` is empty or because Sellerboard has a number.

The right next proof is a read-only Level 3 fee/shipping proof map:
- count commission, FBA fee, shipping income, shipping chargeback, and refund fee reversal rows
- prove they have order ID, SKU, posted date, amount type, amount, and currency
- prove which fields already reach `financial_events_level3_official`, `order_master`, E performance, and O restock source
- keep shipping cost separate from shipping income
- keep Sellerboard as comparison only

## Bounded Worker Task
Build `B068` as a read-only Level 3 fee/shipping proof map.

Expected output:
- `out/systems/B/refunds/b_level3_fee_shipping_api_proof_map.csv`
- `out/systems/B/refunds/b_level3_fee_shipping_api_proof_map_summary.csv`

Rows should include:
- money field
- API source file
- source amount types
- source row count
- official/output row count
- required keys present
- proof label: `api_source_available`, `api_source_missing`, `repo_path_unclear`, or `protected_live_pull_required`
- whether live ROI/restocking use is allowed, always `0` in this packet
- retest rule
- protected stop rule

## MOT/Proof Check
Add a B MOT row only after B068 exists.

The row should:
- fail if schema is missing, labels are unrecognised, or live ROI/restocking use is allowed
- warn if any field remains `repo_path_unclear`, `api_source_missing`, or `protected_live_pull_required`
- clear only when all required fee/shipping fields are API-source-available and downstream confidence is safe

## Retest Rule
A future worker task is not proved by code edits.

Proof requires:
- B068 runs read-only
- B MOT runs read-only
- B067 still blocks weak values from ROI/restocking
- no B run, restart, Sheet write, local DB alignment, output deletion, price change, queue change, or live API pull happened

## Luke Decision Only If Protected
Stop before:
- live Amazon API pulling
- changing B outputs
- changing D/E/O ROI or restocking use
- writing Sheets
- aligning local DB facts
- deleting outputs
- running or restarting B
- treating Sellerboard as final truth
