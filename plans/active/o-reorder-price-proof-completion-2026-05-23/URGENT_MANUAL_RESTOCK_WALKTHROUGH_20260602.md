# Urgent Manual Restock Walkthrough - 2026-06-02

Purpose: record Luke's second-check restock decisions one product at a time.

Rules for this note:
- Luke makes the buying decision.
- This note records evidence and reasoning only.
- Missing facts are written as `missing`.
- No Google Sheets writes from Codex.
- No price changes, queue edits, purchase orders, Amazon sends, or output deletion.

General restock learning notes:
- Luke is broadly looking for around 10 percent ROI, but history can change the decision.
- The system must learn from old products while it catches up to current reality.
- Live products should usually use Luke's own current sales velocity, not only old Sheet history.
- Supplier availability can change; O needs to detect missing, backorderable, and likely discontinued supplier states.
- A product becoming unavailable must not be hidden. O should surface it clearly so Luke can decide.
- Fresh own-sales data should outrank weak marketplace estimates when it exists.
- If own-sales data is missing, O may use BBP/competition/rank as clues, but should mark the decision as lower confidence.

## Existing Product Checks

### ABGee start check - 2026-06-02

What Luke asked:
- Check whether ABGee has products waiting for second checks.
- Check how many passed the scans.
- Check whether any were checked by AI title comparison.

Current local evidence:
- Luke's Sheet/system count: 10 ABGee items.
- ABGee old restock bridge rows: 9.
- ABGee draft PO rows waiting for Luke-style second check: 8 rows, 99 units, GBP 592.67 total.
- ABGee row parked outside the draft PO: 1 row, SKU `18-WD7G-J8U4`, Pokemon Paldea Battle Figure 4 Pack, because it still needs extra confidence before treating it as clean.
- Last ABGee supplier-feed batch found: `abgee_source_20260522T134758Z_fa74c131f665`.
- ABGee source rows in that batch: 8,745.
- ABGee rows ready to scan from that batch: 5,770.
- ABGee held rows from that batch: 2,975.
- Held reasons: 2,428 missing barcode; 547 invalid barcode format.
- ABGee completed scanner PASS rows found from that batch: 0.
- Important correction: this does not mean 5,770 ABGee rows scanned and failed.
- ABGee manager dashboard state shows ABGee as `Queued`, with 5,770 web-unprocessed rows, 0 web pass, 0 web fail, 0 second pass, and 0 second fail.
- Live scanner ownership is currently on TD Synnex, not ABGee.
- Plain-English cause: ABGee appears loaded and waiting, not completed by the new scanner.
- ABGee live second-check scanner rows found: 0 because ABGee has not reached completed scanner output yet.
- ABGee AI title-comparison review pack found: no ABGee AI review handoff folder found.

Plain-English note:
- For today's ABGee work, the useful pile is the old manual restock draft, not new scanner-passed products.
- The last ABGee feed had 5,770 rows ready to scan, but ABGee is still queued/unprocessed in the new manager flow.
- The AI title comparison has not checked ABGee rows in the review handoff evidence I found.

Products in ABGee draft PO for Luke second check:
- `12-749B-9EB5` - qty 2 - cost GBP 7.59 - Funko POP! TCM Leatherface.
- `7M-48OU-23X3` - qty 4 - cost GBP 7.59 - Funko POP! Freddy Krueger.
- `9C-ZLCN-WWGK` - qty 37 - cost GBP 7.59 - Funko POP! Harry Potter Severus Snape.
- `CJ-X0SS-QOUW` - qty 10 - cost GBP 4.16 - Snackles Small Sized 14 cm.
- `IZ-8NZ9-VXR2` - qty 5 - cost GBP 3.80 - Baby Annabell Lunch Time Trickbottle.
- `SC-LYFM-ORXK` - qty 21 - cost GBP 4.20 - Shaun the Sheep Plush Backpack Clip.
- `TE-Y18U-S2O1` - qty 10 - cost GBP 4.16 - World's Smallest Monopoly.
- `UR-Q7TM-1F3I` - qty 10 - cost GBP 7.59 - Funko POP! Bride of Chucky Tiffany Valentine-Ray.

### Product check - `12-749B-9EB5`

Product:
- SKU: `12-749B-9EB5`
- ASIN: `B084HZRR8G`
- Supplier: ABGee
- Supplier SKU: `985 49830`
- Barcode: `889698498302`
- Title: Funko POP! Movies: TCM - Leatherface.

Luke question:
- Luke's old Sheet system does not check current ROI.
- Check whether the new system has current ROI checking yet.
- Check whether we know the current sale price.

Local evidence found:
- New O profit-check function exists, but this SKU is not cleanly proved yet.
- Local Sheet-derived price shown: GBP 10.3224.
- Sell price basis: `LEGACY_PURCHASE_LIST_ROI_BACKSOLVE`.
- Correction from Luke: GBP 10.3224 is not the current sale price and must not be treated as live Amazon price.
- Luke checked current Amazon sale price: GBP 19.90.
- Supplier cost shown locally: GBP 7.59.
- Local forward ROI shown: 36 percent, but this is not reliable because it did not use the current Amazon sale price and does not prove VAT/fees properly.
- Local forward profit shown: GBP 2.7324 per unit, but this is not reliable for the same reason.
- Profit verdict: `needs_price_check`.
- Native shadow verdict: `do_not_buy_now`.
- Missing proof: fresh native market price, fee model/max safe cost, and current ABGee price-list match.
- Fresh ABGee price file pulled manually through the local Gmail/OAuth route during this check.
- Fresh file source email timestamp: 2026-06-01T14:47:13Z.
- Fresh local file: `C:\Users\Luke\Desktop\SellerOne Price Files\ABGee\inbox\ABGee_Stock_Feed_20260602T103226Z_f11a7d69a5.xlsx`.
- Fresh file result for supplier SKU `985 49830`: no match found.
- Fresh file result for barcode `889698498302`: no match found.
- Fresh file result for title terms `Leatherface` / `Texas Chainsaw`: exact Funko TCM Leatherface product not found.
- Similar ABGee row found: `222 NS5061` Texas Tubbx Boxed Leatherface, qty 2, cost GBP 8.74, but this is a different product and must not be treated as a match.
- Automation issue seen: normal FPM016 fetch path needs a worker fix because the saved ABGee status row can mix the Gmail label value with the local folder path.

Second-check note:
- Do not treat GBP 10.3224 as confirmed current sale price.
- Current Amazon sale price per Luke: GBP 19.90.
- The system did not prove the current listing price correctly for this SKU.
- Clean ROI still needs VAT, Amazon fees, and any refund/inbound drag before it can be trusted.
- Current supplier stock/cost for supplier SKU `985 49830`: not available in the fresh ABGee file.

E evidence summary:
- E support state: `manual_decision_only`.
- Stock signal: `missing` because this SKU is not present in the latest E restock signal output.
- Velocity/sales truth state: `missing` because this SKU is not present in latest E velocity, sales-truth, or daily-truth outputs.
- ROI/profit confidence: `missing` because this SKU is not present in latest E ROI or performance summary outputs.
- Refund proof state: `missing` because E has no SKU-level row to attach refund proof to this item.
- B money proof state: `bridge_labelled_money` at E-cycle level, so E ROI/restock proof is warning-labelled even where SKU rows exist.
- Latest price confidence: `missing_current_price` from E because there is no current E listing/price proof row for this SKU; Luke's manual Amazon check is separate evidence.
- Missing proof: E has no current SKU row, no ROI row, no sales-truth row, no restock row, no refund proof row, and no current supplier-file match.
- What E can support today: E supports the warning that the new system cannot prove this item cleanly today.
- What E cannot support today: E cannot support a buy recommendation, clean ROI, clean restock signal, clean refund-adjusted profit, or current price proof for this SKU.

Luke final manual decision:
- Marking this line as discontinued.
- Do not buy.

What O must learn:
- If a known supplier SKU/barcode is missing from the fresh supplier price file, O should flag `likely discontinued` or `supplier no longer lists this item`.
- O must not automatically discontinue the product by itself.
- The final discontinue decision stays with Luke.

### Product check - `SC-LYFM-ORXK`

Product:
- SKU: `SC-LYFM-ORXK`
- ASIN: `B07QXSDZJM`
- Supplier: ABGee
- Supplier SKU: `541 61176`
- Barcode: missing in local bridge row
- Title: Shaun the Sheep Plush 61176 Backpack Clip.

Status:
- Starting second check after `12-749B-9EB5`.

Fresh ABGee price-file check:
- Supplier SKU `541 61176`: found.
- Fresh ABGee title: Shaun The Sheep Keyclip.
- ABGee stock quantity: 21.
- ABGee unit code: EA.
- Fresh ABGee cost: GBP 4.60.
- ABGee listed RRP/sell guide: GBP 10.99.
- Fresh ABGee barcode: `5034566611764`.
- Fresh file row: ABGee Stock Feed row 3158.

Local restock comparison:
- Old Sheet/process cost: GBP 4.20.
- Fresh ABGee cost is GBP 0.40 higher than old cost.
- Old local suggested quantity: 21.
- Old local market/sale price shown: GBP 5.25, but this is Sheet-derived and not trusted as current Amazon price.
- O profit check verdict: `needs_price_check`.
- Reason: supplier list price is above the old max safe cost, so Luke needs current Amazon price and full fee/VAT check before buying.

Second-check note:
- Product is not discontinued in the fresh ABGee file.
- Supplier has exactly 21 available in the fresh file.
- Current Amazon sale price checked by Luke: GBP 10.48.

Luke manual reasoning:
- ABGee current cost: GBP 4.60.
- ABGee current stock: 21.
- Luke's old system suggested buying 21.
- BBP/history suggested around 8, so Luke initially considered a test order of 10.
- Seller/Amazon prompt showed invoice submission wording, but adding appeared unlocked anyway.
- Rank shown: about 55k, which is over the normal target, but there is sales history with the product.
- Luke then checked ROI/profit properly.
- Current price loses about GBP 0.20 per sale.
- History shows the product has mostly been losing money.

Luke final manual decision:
- Drop this product.
- Do not order.

What O must learn:
- Do not let old sales history override bad current ROI.
- If the current price loses money after fees/VAT/costs, O should recommend drop or no-buy even when supplier has stock.
- Test-order logic needs a profit floor. A product should not pass just because rank/history exists.
- O should compare old suggested quantity, BBP/history quantity, rank, and current ROI before suggesting any quantity.
- If invoice/submission wording appears but the listing is actually unlocked, record it as a listing-access note, not a buying reason.

### Product check - `9C-ZLCN-WWGK`

Product:
- SKU: `9C-ZLCN-WWGK`
- ASIN: `B00TQ5KPNC`
- Supplier: ABGee
- Supplier SKU: `985 5862`
- Barcode: `849803058623`
- Title: Funko POP! Movies: Harry Potter - Severus Snape.

Fresh ABGee price-file check:
- Supplier SKU `985 5862`: found.
- Fresh ABGee title: Pop! Vinyl - Harry Potter - Severus Snape.
- ABGee stock quantity: 0.
- ABGee unit code: EA.
- Fresh ABGee cost: GBP 7.59.
- ABGee listed guide/RRP: GBP 13.99.
- Fresh ABGee barcode: `849803058623`.
- Fresh file row: ABGee Stock Feed row 7007.

Local restock comparison:
- Old Sheet/process suggested quantity: 37.
- Local PO draft quantity: 37.
- Old Sheet/process cost: GBP 7.59.
- Fresh ABGee cost: GBP 7.59.
- Old local sale/market number: GBP 10.2465, but this is Sheet-derived and not trusted as current Amazon price.
- Local O profit verdict: `needs_price_check`.
- Local O native shadow verdict: `do_not_buy_now`.
- Existing/open stock context from old local row: 20 open, available now 0, 30-day velocity 1.6.

Second-check note:
- Product matches the fresh ABGee file, but supplier stock is 0.
- ABGee zero stock does not automatically block ordering because some ABGee items can be backordered.
- Luke notes: ABGee site shows `Backorder` when backorder is possible; if there is no backorder wording, it may not be orderable.
- Current Amazon/BBP check from Luke: buy box display showed GBP 17.60, but actual MF Prime buy box price is GBP 16.99.
- Luke changed the price to GBP 16.99 to match the MF Prime buy box.
- ROI after Luke price change: 12.51 percent.
- Luke is questioning the sales amount.
- BBP thinks sales are 0, but the listing has many sellers including Amazon.
- MF Prime competitor stock currently observed by Luke: 34 units.

Luke current manual decision:
- Do not order today.
- Snooze/check back rather than drop immediately.

What O must learn:
- ABGee stock `0` does not always mean no-buy; O needs a backorder flag from the supplier site.
- If backorder is available, O should treat the row as `backorder_possible`, not `out_of_stock_blocked`.
- Buy box logic must identify the actual MF Prime/FBA price being competed against, not jump to the wrong FBA price when MF Prime owns the buy box.
- For uncertain sales, O should record competitor stock levels and re-check movement later.
- BBP zero-sales estimates should not be treated as final when there are many active sellers and visible stock.

Follow-up needed:
- Check again in one week for seller/stock movement and sales confidence before ordering.

### Product check - `UR-Q7TM-1F3I`

Product:
- SKU: `UR-Q7TM-1F3I`
- ASIN: `B072YZPBJ3`
- Supplier: ABGee
- Supplier SKU: `985 20117`
- Barcode: `889698201179`
- Title: Funko Pop! Movies: Bride Of Chucky - Tiffany Valentine-Ray.

Fresh ABGee price-file check:
- Supplier SKU `985 20117`: found.
- Fresh ABGee title: Pop! Vinyl - Bride of Chucky - Tiffany.
- ABGee stock quantity: 0.
- ABGee unit code: EA.
- Fresh ABGee cost: GBP 7.59.
- ABGee listed guide/RRP: GBP 13.99.
- Fresh ABGee barcode: `889698201179`.
- Fresh file row: ABGee Stock Feed row 6877.

Local restock comparison:
- Old Sheet/process suggested action: test restock.
- Old Sheet/process suggested quantity: 10.
- Local PO draft quantity: 10.
- Old Sheet/process cost: GBP 7.59.
- Fresh ABGee cost: GBP 7.59.
- Old local sale/market number: GBP 7.59, but this is Sheet-derived and not trusted as current Amazon price.
- Local O profit verdict: `test_only`.
- Local O native shadow verdict: `do_not_buy_now`.
- Demand status: missing or weak demand.

Second-check note:
- Product matches the fresh ABGee file.
- Supplier stock is 0, but ABGee zero stock may still allow backorder if the site shows `Backorder`.
- Current Amazon sale price, BBP movement, backorder availability, and real ROI still need checking before any order.

Luke manual check:
- Current Amazon price: GBP 15.95.
- Profit: GBP 0.37.
- ROI: 4.06 percent.
- Estimated sales: about 13 per month.
- History does not look great.
- Luke view: no need to chase a slow, low-profit item.

Luke final manual decision:
- Drop this product.
- Do not restock now.

What O must learn:
- Small positive profit is not enough by itself.
- O needs a minimum ROI/profit floor before recommending restock.
- Slow sales plus weak history plus low ROI should recommend drop/no-buy, even if the item is technically profitable.
- Backorder availability should not matter if ROI is below the buying floor.

### Product check - `H6-E7MP-EBPD`

Product:
- SKU: `H6-E7MP-EBPD`
- ASIN: `B00000IU72`
- Supplier: ABGee
- Supplier SKU from Luke/old Sheet: `542 33344`
- Barcode from old Product Database: `7312350333442`
- Title: BRIO 33344 Mechanical Switches Wooden Train Track.

Fresh ABGee price-file check:
- Supplier SKU `542 33344`: not found.
- Barcode `7312350333442`: not found.
- Title/product check: exact BRIO 33344 Mechanical Switches row not found.
- Similar nearby ABGee BRIO rows exist, but not this exact supplier SKU/barcode.
- Important false-match note: searching `33344` found an unrelated row where `33344` appeared inside another barcode, not as this supplier SKU.

Local restock comparison:
- Local O row exists, but not from the ABGee bridge list.
- Current O action: wait.
- O profit verdict: `needs_price_check`.
- O message: no current supplier price-list match; operator must confirm safe unit price.
- Current local sale price basis: OUR_PRICE GBP 17.73.
- Max safe cost shown locally: GBP 8.679545.
- Old Sheet purchase history: bought at GBP 8.45 in February 2025 and April 2025.
- Product Database old note: 10 percent ROI, GBP 0.05 profit, last status Restock.

Second-check note:
- Fresh ABGee file does not currently list this exact BRIO product.
- This should be treated as missing supplier proof, not buyable unless Luke finds it manually/backorderable on ABGee.
- If the supplier site shows a backorder option, record that separately before deciding.

Luke final manual decision:
- Looks like another discontinued product.
- Marking it down as discontinued.
- Do not order.

What O must learn:
- Missing from fresh supplier file after prior purchase history should raise `likely discontinued`.
- O should not auto-discontinue, but should make the likely discontinued state obvious for Luke.
- Old Product DB restock status must be challenged by fresh supplier evidence.

### Product check - `IZ-8NZ9-VXR2`

Product:
- SKU: `IZ-8NZ9-VXR2`
- ASIN: `B08XLT86GL`
- Supplier: ABGee
- Supplier SKU: `515 706404`
- Title: Baby Annabell Lunch Time Trickbottle, Pink.

Luke context:
- Already ordered 48.
- Luke spoke to ABGee and they have them stocked there.
- ABGee needs another order to cover the GBP 250 MOQ.
- These have already been paid for and only need to be shipped.
- Luke will not add any more.

Luke final manual decision:
- Do not add more units.
- Existing paid/order issue only: get current ordered stock shipped.
- Luke clicked snooze on this row in the working system.

What O must learn:
- If stock is already paid for or already ordered, O should not suggest adding more just because the product looks restockable.
- O needs an `already_ordered_or_paid` / `awaiting_supplier_shipment` state.
- Supplier MOQ/carton threshold can affect shipping even after a product is paid for.

### Product check - `7M-48OU-23X3`

Product:
- SKU: `7M-48OU-23X3`
- ASIN: `B004GFPFBO`
- Supplier: ABGee
- Supplier SKU: `985 2291`
- Barcode: `830395022918`
- Title: Funko POP! Movies - Freddy Krueger / Nightmare on Elm Street.

Fresh ABGee price-file check:
- Supplier SKU `985 2291`: found.
- Fresh ABGee title: Pop! Vinyl - Freddy Krueger.
- ABGee stock quantity: 0.
- ABGee unit code: EA.
- Fresh ABGee cost: GBP 7.59.
- ABGee listed guide/RRP: GBP 13.99.
- Fresh ABGee barcode: `830395022918`.
- Fresh file row: ABGee Stock Feed row 6880.

Local restock comparison:
- Old Sheet/process suggested action: full restock.
- Old Sheet/process suggested quantity: 4.
- Local PO draft quantity: 4.
- Old Sheet/process cost: GBP 7.59.
- Fresh ABGee cost: GBP 7.59.
- Old local sale/market number: GBP 9.3357, but this is Sheet-derived and not trusted as current Amazon price.
- Old local ROI: 23 percent, but this is not enough without current price proof.
- Local O profit verdict: `safe_to_review`.
- Local O native shadow verdict: `do_not_buy_now`.
- Demand signal: present but weak, velocity about 0.1 units/day.

Second-check note:
- Product matches the fresh ABGee file.
- Supplier stock is 0, but ABGee may allow backorder if the site shows `Backorder`.
- Current Amazon sale price, BBP movement, backorder availability, and real ROI still need checking before any order.

Luke manual check:
- Current Amazon sale price checked by Luke: GBP 18.53.
- Current ROI: 23 percent.
- Rank: under 50k.
- BBP estimated sales velocity: 72, but Luke thinks this sounds unrealistic.
- Luke notes product comes in packs of 6.

Luke final manual decision:
- Order 12 units.
- Order placed.

What O must learn:
- If supplier/backorder ordering works in packs, O must respect pack multiples.
- For this product, order quantity should be a multiple of 6.
- BBP estimated sales velocity can be too optimistic and should be sanity-checked against rank, own history, and competition.
- A product can be worth ordering when ROI is acceptable, rank is under target, and quantity is kept controlled.

### Product check - `TE-Y18U-S2O1`

Product:
- SKU: `TE-Y18U-S2O1`
- ASIN: `B08X1WM596`
- Supplier: ABGee
- Supplier SKU: `333 SI5038`
- Barcode: `810010991225`
- Title: World's Smallest Monopoly.

Fresh ABGee price-file check:
- Supplier SKU `333 SI5038`: found.
- Fresh ABGee title: World's Smallest - Monopoly.
- ABGee stock quantity: 586.
- ABGee unit code: EA.
- Fresh ABGee cost: GBP 4.16.
- ABGee listed guide/RRP: GBP 9.99.
- Fresh ABGee barcode: `810010991225`.
- Fresh file row: ABGee Stock Feed row 1838.

Local restock comparison:
- Old Sheet/process suggested action: full restock.
- Old Sheet/process suggested quantity: 10.
- Local PO draft quantity: 10.
- Old Sheet/process cost: GBP 4.16.
- Fresh ABGee cost: GBP 4.16.
- Old local sale/market number: GBP 4.6176, but this is Sheet-derived and not trusted as current Amazon price.
- Old local ROI: 11 percent, but the current expected cost was above max safe cost.
- Local O profit verdict: `do_not_buy_now`.
- Local O price status: `over_max_snooze_candidate`.
- Local O recommended one-week snooze had already been suggested.
- Demand signal: present but weak, velocity about 0.3 units/day.

Second-check note:
- Product matches fresh ABGee file and has plenty of stock.
- Current Amazon sale price and real ROI need checking.
- Local O is already cautious because expected cost is above its max safe cost.

Luke manual check:
- Current economics are losing money.
- Sales are low.

Luke final manual decision:
- Drop this product.
- Do not order.

What O must learn:
- Supplier stock availability must not override loss-making current economics.
- Low sales plus negative profit should recommend drop/no-buy.
- O should catch this before creating a restock quantity.

### Product check - `CJ-X0SS-QOUW`

Product:
- SKU: `CJ-X0SS-QOUW`
- ASIN: `B0CG234KW1`
- Supplier: ABGee
- Supplier SKU: `777 77510GQ1-A`
- Barcode: `193052060655`
- Title: Snackles Small Sized 14 cm by ZURU.

Fresh ABGee price-file check:
- Supplier SKU `777 77510GQ1-A`: found.
- Fresh ABGee title: *SINGLE* Snackles S1 Capsule 5in - Single Capsule.
- ABGee stock quantity: 69.
- ABGee unit code: EA.
- Fresh ABGee cost: GBP 3.00.
- ABGee listed guide/RRP: GBP 9.99.
- Fresh ABGee barcode: `193052060655`.
- Fresh file row: ABGee Stock Feed row 4895.

Local restock comparison:
- Old Sheet/process suggested action: test restock.
- Old Sheet/process suggested quantity: 10.
- Local PO draft quantity: 10.
- Old Sheet/process cost: GBP 4.16.
- Fresh ABGee cost: GBP 3.00.
- Fresh ABGee cost is GBP 1.16 cheaper than old cost.
- Old local sale/market number: GBP 4.16, but this is Sheet-derived and not trusted as current Amazon price.
- Old local ROI: 0 percent.
- Local O profit verdict: `test_only`.
- Local O price status: `max_safe_cost_missing`.
- Demand signal: missing or weak.

Second-check note:
- Product matches fresh ABGee file and has stock.
- Fresh supplier cost is materially better than old cost.
- Current Amazon sale price, current ROI, BBP movement, and listing competition still need checking before any test order.
- This is a good example where new supplier file data may change the decision, but O still needs current market proof.

Luke manual check:
- Supplier cost ex VAT: GBP 3.00.
- Supplier cost inc VAT: GBP 3.60.
- Current sell price: GBP 10.63.
- Profit: GBP 1.27.
- ROI: 35.28 percent.
- BSR: 1 percent.
- Estimated sales: 0.
- ROI looks good, but sales look low or uncertain.
- Current top seller: UK Toy Deals, normal MF, 6-day delivery.

Competition snapshot from Luke:
- Seller 1: 19 in stock, GBP 10.19, GBP 0.97 profit, 26 percent ROI, 8 Jun, rank/sales note 94.
- Seller 2: 33 in stock, GBP 10.63, GBP 1.27 profit, 35 percent ROI, 5 Jun, note 7.
- Seller 3: 1 in stock, GBP 10.99, GBP 1.52 profit, 42 percent ROI, 5 Jun, note 0.
- Seller 4: 511 in stock, GBP 11.49, GBP 1.85 profit, 51 percent ROI, 4 Jun, note 26k.

Luke final manual decision:
- Snooze.
- Do not order today.
- Check back in one week against competition stock and movement.

What O must learn:
- Good ROI alone is not enough when sales estimate is 0 or uncertain.
- O should capture competitor stock, price, fulfilment type, and delivery promise when deciding whether to test a slow item.
- O should re-check whether competitor stock moves before recommending a buy.
- MF delivery speed matters; a top MF seller with slow delivery may still affect the buy box differently from FBA or MF Prime.

### Product check - `18-WD7G-J8U4`

Product:
- SKU: `18-WD7G-J8U4`
- ASIN: `B0B32365PH`
- Supplier: ABGee
- Supplier SKU: `888 PKW3402`
- Barcode: `191726507185`
- Title: Pokemon Paldea Battle Figure 4 Pack - Pikachu, Fuecoco, Sprigatito, and Quaxly.

Fresh ABGee price-file check:
- Supplier SKU `888 PKW3402`: not found.
- Barcode `191726507185`: not found.
- Exact title/product: not found.
- Similar Pokemon rows exist in the fresh file, but not this exact supplier SKU/barcode/product.

Local restock comparison:
- Old Sheet/process suggested action: test restock.
- Old Sheet/process suggested quantity: 10.
- Old Sheet/process cost: missing/0.
- Local O profit verdict: `missing_profit_inputs`.
- Local O current sell price: GBP 12.99 from Product DB live listing price.
- Local O missing inputs: missing supplier cost and missing max safe cost.
- Local O native shadow verdict: `do_not_buy_now`.
- Demand signal: missing or weak.

Second-check note:
- Product is not proved buyable from fresh ABGee file.
- Do not match this against other Pokemon rows.
- This needs Luke decision: likely discontinued/unavailable, or manually verify ABGee site/backorder if still interested.

Luke final manual decision:
- Marked as discontinued.
- Do not order.

What O must learn:
- Similar brand/title rows are not enough. O must match exact supplier SKU/barcode/title before using a supplier cost.
- If no supplier cost exists and no fresh supplier-file match exists, O should block any test order.
- New/no-data test candidates need current supplier proof before appearing as orderable.

E evidence summary:
- E support state: `manual_decision_only`.
- Stock signal: `stock_signal_only` is not active. E shows available stock `0`, total quantity `16`, but reorder flag `no` because latest 30-day velocity is `0.0`.
- Velocity/sales truth state: `velocity_only`; E has a velocity row, but no ROI-backed sales-truth row and no daily-truth row for this SKU.
- ROI/profit confidence: `missing`; E marks `profit_confidence` as `profit_missing`.
- Refund proof state: `not_yet_proven`; E shows expected refund cost `0.0`, but refund proof is not yet proven and must not be treated as clean.
- B money proof state: `bridge_labelled_money` at E-cycle level, so E ROI/restock proof is warning-labelled even where SKU rows exist.
- Latest price confidence: `missing_current_price`; E marks `latest_price_confidence` as `listing_price_unproven`.
- Restock business readiness: `manual_decision_only`; E marks `restock_business_ready` as `no`.
- Missing proof: `missing_roi_profit_proof;listing_price_unproven`; also missing ROI-backed sales truth, daily truth, and clean refund proof.
- What E can support today: E can say the SKU exists in the latest E performance/study output and has no recent sales velocity in the 30-day window.
- What E cannot support today: E cannot prove clean ROI, current sale price, refund-adjusted profit, or an automatic reorder-ready state.

## New Product Candidate Checks

No new-product candidates recorded yet.

## Bliss Distribution - second-check starting point

- Supplier checked after ABGee walkthrough.
- Current Bliss first-check evidence: 19 rows passed the raw first checks.
- Current Bliss legacy second-check file: 0 rows written there.
- Review handoff evidence initially showed one clean operator/AI pass candidate from the latest Bliss handoff.
- Follow-up patch-through check found the 19 first-check rows are accounted for across two Bliss handoffs, not lost.
- Clean AI/operator pass candidates across those handoffs: 4.
- Read-only investigation on 2026-06-02 found the 19 raw first-check PASS rows did not all become clean AI pass rows by design:
  - 4 reached AI/operator pass.
  - 15 were held as near-miss/manual rows before the clean AI pass list.
  - Held reasons: 10 history-risk conflicts, 4 weak UK-review/manual-review signals, and 1 demand-range conflict.
  - The old legacy second-check file still has 0 rows because the useful path is now the F review handoff/O New Product Review path, not that old file.
  - In O, New Product Review can reach the Bliss rows through the Review pack dropdown as `Bliss Distribution - 3 passes to review` and `Bliss Distribution - 1 pass to review`.
  - The operator problem is visibility: Bliss is split across two handoffs and not shown as one combined Bliss second-check queue.

AI/operator pass candidate:
- Supplier SKU: `KONKKS`
- ASIN: `B09HKZWBDN`
- Product: Yu-Gi-Oh! Kuriboh Kollection Card Sleeves
- Brand: Yu-Gi-Oh!
- Main rank: 43,073
- Expected units next 30 days: 11
- Estimated monthly profit: GBP 18.60
- Profit per unit: GBP 1.24
- Conservative starter quantity: 2
- ROI evidence: 54.63 percent
- AI title/pack check: passed. Amazon evidence confirmed each pack contains 50 card sleeves, matching the supplier 50-pack title.
- AI confidence: high.

Other Bliss review evidence:
- 10 near-miss rows exist, but these are not clean second-check items yet.
- Across the 19 raw first-check PASS rows, 15 are held rows, not missing rows:
  - History-risk conflict: `ATMDSH11160`, `ATMDSH11821`, `ATMDSH11822`, `ATMDSH12125`, `ATMDSH13101`, `ATMDSH30651`, `D38980000`, `KONDHCS`, `KONKKGM`, `TAPBF4115`.
  - Weak UK-review/manual-review signal: `ATMDSH30724`, `ATMDSH30735`, `ATMDSH30751`, `KONRERE`.
  - Demand-range conflict: `ATMDSH16127`.

Additional clean AI/operator pass candidates from earlier Bliss handoff:
- `KONYKSL` / `B0CGX83HHK` - YGO Yugi & Kaiba Quarter Century Card Sleeves (100). Rank 44,512. Expected units next 30 days: 16. Estimated monthly profit: GBP 39.76. Conservative starter quantity: 3.
- `ATMDSH12124` / `B0DBVJSGJC` - Dragon Shield Brushed Art Sleeves Spirit Animals Burnbug 100 CT. Rank 6,524. Expected units next 30 days: 5. Estimated monthly profit: GBP 19.48. Conservative starter quantity: 1.
- `ATMDSH13004` / `B0FZLQ2FX1` - Dragon Shield Standard Perfect Fit Thick Inner Sleeves 100 Sleeves Clear. Rank 14,731. Expected units next 30 days: 6. Estimated monthly profit: GBP 8.96. Conservative starter quantity: 2.

What O must learn:
- The system needs to clearly separate raw first-check passes, AI-reviewed pass candidates, and rows actually written into the second-check workflow.
- The operator should not have to reconcile three different meanings of "passed".
- The manual walkthrough view should show clean AI/operator pass candidates across relevant handoffs, or clearly state when it is only showing the latest handoff.
- Acceptance flow note: the system has an approval queue and PO handoff structure, but the latest checked PO handoff proof is stale and showed 0 approved handoff rows. During this walkthrough, accepted products must be treated as manual order decisions unless the PO handoff is freshly proven live.
- System lesson: the operator view must clearly say what an "accept" action does: records approval only, creates PO handoff row, or actually places/adds an order. These are different business actions and must not be hidden behind the same word.
- Future build request: add a finished acceptance-to-order workflow so accepted products can move into the correct supplier order/PO process automatically when safe. This must still show the operator exactly what happened and must not silently place or change orders without the approved business rules.

## Bliss Distribution - Product Database setup after batch sent

Luke sent the accepted Bliss batch manually, then asked whether the products needed adding to Amazon/inventory.

Manual sheet update performed:
- Target workbook: Amazon Supplier Process.
- Target tab: Product Database.
- Rows updated: 596 to 598.
- Existing fields already present: ASIN and Supplier.
- Fields filled: Name, Barcode, Supply Code.

Rows filled:
- `B0CGX83HHK` / `KONYKSL`
  - Name: YGO Yugi & Kaiba Quarter Century Card Sleeves (100)
  - Barcode: `4012927165775`
  - Supply Code: `KONYKSL`
- `B0DBVJSGJC` / `ATMDSH12124`
  - Name: Dragon Shield | Brushed Art Sleeves | Spirit Animals - Burnbug | 100 CT
  - Barcode: `5706569121242`
  - Supply Code: `ATMDSH12124`
- `B0FZLQ2FX1` / `ATMDSH13004`
  - Name: Dragon Shield - Standard Perfect Fit Thick Inner Sleeves - (100 Sleeves) - Clear
  - Barcode: `5706569130046`
  - Supply Code: `ATMDSH13004`

What O must learn:
- After a new-product batch is sent, the workflow must check whether each accepted ASIN is already set up in Product Database/Amazon inventory.
- If the row exists with only ASIN and supplier, the system should fill or prompt for Name, Barcode, and Supply Code.
- This must be recorded as part of the acceptance/order workflow, not left as a separate memory task in chat.
- Future build request: accepted products should feed into a clear inventory setup step before or alongside supplier ordering.

## Bliss Distribution - supplier SKU migration from barcode match

Luke reported that Bliss Distribution changed their SKU format, so old Product Database supply codes may no longer work.

Manual sheet update performed:
- Target workbook: Amazon Supplier Process.
- Target tab: Product Database.
- Match method: exact barcode match from the latest local Bliss price file.
- Source price file: Bliss Distribution / Processed / In Stock List 18.05.26.
- Rule used: update Supply Code only where the barcode matched exactly and the new Bliss SKU was a clear one-to-one match.
- Rows with no barcode match in the current Bliss in-stock file were left unchanged.

Supply Code updates applied:
- Row 62: `AT-15052` -> `ATMDSH15052`
- Row 76: `E-84517` -> `UPR84517`
- Row 96: `AT-11006` -> `ATMDSH11006`
- Row 97: `AT-15061` -> `ATMDSH15061`
- Row 98: `AT-15063` -> `ATMDSH15063`
- Row 101: `CP3003` -> `TAPCP3003`

Verification note:
- Google Sheets write response confirmed the new values were applied.
- A follow-up read-back hit a temporary Google Sheets rate limit, so verification is based on the successful write response.

What O must learn:
- Supplier SKU changes need a barcode-led migration tool.
- The tool should show: old supply code, matched barcode, new supplier SKU, source price file, and whether the match is safe.
- The tool must not update rows where the barcode is missing, duplicated, or absent from the current supplier file.
- The operator should see a summary before and after update, especially for supplier system migrations.
- The migration must also check the current Purchase List, not just Product Database, because live order rows may still carry stale supplier codes.

## Bliss Distribution - Purchase List SKU migration from barcode match

Luke also asked for the current Purchase List tab to be updated after the Product Database SKU migration.

Manual sheet update performed:
- Target workbook: Amazon Supplier Process.
- Target tab: Purchase List.
- Match method: exact barcode match from the latest local Bliss price file.
- Source price file: Bliss Distribution / Processed / In Stock List 18.05.26.
- Rule used: update Supply Code only where the barcode matched exactly and the new Bliss SKU was a clear one-to-one match.

Supply Code update applied:
- Row 4: `E-84517` -> `UPR84517`

Rows checked but left unchanged:
- Row 3 `E-82225`: no safe barcode match in the current Bliss in-stock file.
- Row 5 `E-15146`: no safe barcode match in the current Bliss in-stock file.
- Row 6 `E-83648`: no safe barcode match in the current Bliss in-stock file.
- Row 7 `85683`: no safe barcode match in the current Bliss in-stock file.
- Row 8 `FLFFLW01`: barcode matched and the supplier SKU was already correct.
- Row 9 `KONYKSL`: no safe update needed from the current Purchase List row.
- Row 10 `ATMDSH12124`: no safe update needed from the current Purchase List row.
- Row 11 `ATMDSH13004`: no safe update needed from the current Purchase List row.

What O must learn:
- Supplier SKU migration should check both Product Database and active order working lists in the same workflow.
- The operator needs a simple "updated / already correct / no safe match" result for each affected row.
- No supplier code should be guessed from a similar-looking SKU. Barcode match should be the proof.

## Bliss Distribution - order placed

Luke placed the Bliss order after confirming the selected items were in profit range.

Order proof:
- File: Sales OrderEX 033121.pdf.
- Supplier: Bliss Distribution Ltd.
- Order number: `033121`.
- Order date: `02/06/2026`.
- Currency: GBP.
- Sales total: `2,094.29`.
- VAT total: `323.85`.
- Order total: `2,418.14`.

Ordered lines:
- `ATMDSH12124` - Dragon Shield Brushed Art Standard Size Sleeves 100pk - The Burnbug - quantity 20 - unit price `6.25`.
- `ATMDSH13004` - Dragon Shield Perfect Fit Thick Sleeves 100pk - Clear - quantity 20 - unit price `3.30`.
- `FLFFLW01` - Mork Borg Core Rulebook Hardcover - quantity 29 - unit price `16.38`.
- `KONYKSL` - Yu-Gi-Oh! Yugi & Kaiba Quarter Century Sleeves 100 Pack - quantity 15 - unit price `3.69`.
- `UPR15146` - Ultra Pro Eclipse 9 Pocket Pro Binder - Apple Red - quantity 12 - unit price `8.61`.
- `UPR82225` - Ultra Pro Comic Bags Current Size Re-Sealable 100 Bags - quantity 60 - unit price `3.44`.
- `UPR83648` - Ultra Pro 3 x 4 Inch Toploaders & Sleeves 100 Pack - quantity 140 - unit price `6.48`.
- `UPR84517` - Ultra Pro Standard Pro Matte Card Sleeves 100 pack - Green - quantity 30 - unit price `3.44`.
- `UPR85683` - Ultra Pro Eclipse Pro 100+ Deck Box - Jet Black - quantity 30 - unit price `1.76`.

What O must learn:
- Once an order is placed, the system should attach or reference the supplier order proof against the restock batch.
- The system should reconcile accepted/restocked rows against the actual supplier order lines, quantities, costs, VAT treatment, and order total.
- The order workflow should confirm that the supplier SKU migration has reached the final order document, not only the internal sheets.

## CLF - supplier stock API check during restock

Luke supplied 14 CLF restock rows and noted that CLF often does not have enough stock available to cover orders.

Live CLF API check performed:
- Checked at: `2026-06-02T15:31:36+01:00`.
- API method used for availability: `GetProductStock`.
- Product data method checked first: `GetProductData`.
- Important finding: the normal CLF price-list conversion keeps SKU, title, barcode, cost, and VAT, but it is not currently filling `stock_available`.
- Root process gap: CLF stock exists in a separate API method and is not yet being joined into the normal supplier report.

Availability returned by CLF:
- `CGC23` - stock `25`.
- `CGC27` - stock `22`.
- `CGC39` - stock `25`.
- `COE12` - stock `0`, out-of-stock reason `SUP`.
- `MOO62` - stock `425`.
- `RO-0717` - stock `6`.
- `SE66` - stock `9`.
- `SPLT28` - stock `105`.
- `TSD84` - stock `25`.

Supplier codes not present in CLF's current live product-code list:
- `HIM57`
- `OCN6`
- `BEAN10`
- `AVA-9110`
- `PE4`

What O must learn:
- CLF restocking cannot rely on price/cost rows alone.
- The CLF workflow must call `GetProductStock` for the same supplier SKUs and join stock into the restock decision screen.
- If a SKU is missing from CLF's live product-code list, O should show this as likely unavailable/discontinued or supplier-code changed, not as blank stock.
- If stock is below the intended order quantity or MOQ, the system should warn before Luke places the order.

Luke added manual review notes in Purchase List column X:
- `SPLT28`: low sales and losing money.
- `TSD84`: losing money.
- `COE12`: out of stock.
- `SE66`: brand selling.
- `CGC27`: brand selling.
- `CGC23`: brand selling.
- `CGC39`: ROI `-3.50%`.

Order/check notes from the sheet at this point:
- `MOO62`: order text shows `MOO62 x 10`.
- `RO-0717`: order text shows `RO-0717 x 6`.
- Several CLF rows were marked done/drop/discontinued manually after checking profit, stock, or brand risk.

What O must learn from the notes:
- Operator notes in the Purchase List are part of the decision record and must be imported into the restock workflow.
- Stock alone is not enough: O also needs to preserve human rejection reasons such as low sales, losing money, brand selling, and negative ROI.
- The UI should make these reasons selectable and reportable, not leave them only as free-text notes in a sheet.

CLF order outcome:
- Luke could not place the CLF order because the remaining orderable value was not enough.
- The remaining two order lines in the sheet were `MOO62 x 10` and `RO-0717 x 6`.
- Luke decided to snooze these and try again after the next CLF price-list scan.

What O must learn from this outcome:
- The restock workflow needs a supplier-order viability check, not just per-product ROI checks.
- If only a small number of products survive review, O should show whether the order is worth placing before Luke reaches the supplier order step.
- Snoozed CLF rows should reappear after a fresh CLF scan with updated stock, cost, MOQ, and ROI evidence.

## Culpitt - snoozed pending supplier price-list scan

Luke reviewed `6L-SDA9-P13J`.

Decision:
- Snooze for now.

Reason:
- A fresh Culpitt supplier price-list scan is needed before this product can be trusted for ordering.

What O must learn:
- If the supplier price-list evidence is stale or missing, the reorder workflow should show "needs fresh supplier scan" rather than pushing the operator toward an order decision.
- Snoozed rows caused by missing supplier scan evidence should return after the next successful supplier price-list scan.

## DHB - passed products waiting for check

Luke asked whether DHB has passed products to check.

Latest DHB pass handoff found:
- Source: latest DHB scanner/review handoff.
- Passed rows: 2.
- Both rows were also present in the AI/operator pass review file.

Passed products:
- `PDL504` / `B001AI8AKI` - TePe Interdental Brush Blue 0.6mm Pack of 6.
- `TEP084` / `B0853KGR7X` - TePe Good Compact Toothbrush, Soft, Assorted Colours, 1pc.

What O must learn:
- The operator view should clearly separate current Purchase List restock rows from newly passed scanner handoff rows.
- When Luke asks "what passed from supplier X", O should show the latest passed handoff products and whether they are already in the Purchase List.

`B001AI8AKI` manual review issue:
- Luke questioned why this passed because the product has many child variants, does not clearly show 50+ sales per month, and should be judged against the new-product benchmark of around GBP 20/month profit.
- Evidence found:
  - Review handoff says likely units next 30 days: `10`.
  - Sales band: `5..16`.
  - Profit per unit: `0.80`.
  - Last completed BBP month basis: `10` units.
  - Current month sales shown: `0`.
  - System profit figure shown: `40`.
  - System demand note: `amazon_missing_bbp_capped_to_50`.
- Why it passed:
  - The pass logic appears to have used a capped demand value of `50` units to calculate GBP 40 estimated monthly profit.
  - That conflicts with the actual likely units value of `10`, which would be around GBP 8/month profit at GBP 0.80 per unit.
- Operator conclusion:
  - This should not be treated as a clean pass under the GBP 20/month new-product benchmark.

What O must learn from this issue:
- The profit-floor check must use the same demand figure shown to the operator.
- If demand is capped or inferred because Amazon/BBP evidence is weak, O should show that as borderline/manual review, not a clean pass.
- Child-variant review/rating noise must not make a weak child ASIN look stronger than it is.

DHB review-pack dropdown issue:
- Luke noticed multiple dropdown entries saying `DHB - 1 pass to review`.
- Evidence found:
  - Several old DHB handoff folders exist from the same DHB scan period.
  - The same ASINs repeat across those folders:
    - `B001AI8AKI`
    - `B0853KGR7X`
  - One folder has 1 pass and several folders have 2 passes, but they are mostly the same products.
- Root issue:
  - The operator dropdown is listing historical DHB handoff folders separately instead of showing one current deduplicated DHB review pack.

What O must learn from the dropdown issue:
- Review packs should be deduplicated by supplier and ASIN before being shown to the operator.
- Old handoff folders should either be hidden, marked superseded, or grouped under history.
- The UI should show "DHB - 2 unique passes to review" instead of repeating several DHB entries.
