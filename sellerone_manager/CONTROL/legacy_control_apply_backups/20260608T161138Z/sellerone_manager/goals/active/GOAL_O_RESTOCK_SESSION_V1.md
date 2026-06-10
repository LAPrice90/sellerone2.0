# Goal - O Restock Session v1

goal_id: GOAL_O_RESTOCK_SESSION_V1

title: Complete restock review from one O UI session

plain_english_goal:
Let Luke complete second-check restocking from one O-controlled UI session instead of jumping between the old Purchase List, Product DB, supplier files, supplier websites, and manual notes.

flow:
O

business_reason:
Luke is currently caught between the old manual restocking method and the partly built O method. The business needs one safe restock review lane that gathers proof, blocks unsafe buys, records decisions clearly, and prepares supplier order batches without pretending the full operations loop is finished.

current_status:
Approved for bounded O construction work. O is ready for user-facing review and decision-shaping, but not ready for automatic purchase orders, receiving, send-to-Amazon, or closed-loop feedback.

success_definition:
- O shows one supplier-grouped restock session for current restock work.
- Every row clearly shows whether it came from native O, a legacy bridge, a feeder review handoff, or a manual walkthrough fixture.
- Every row shows the missing proof that blocks buying, not a silent zero or guessed answer.
- The UI supports reason-coded decisions such as order quantity, snooze, drop, likely discontinued, needs fresh scan, already ordered or paid, and backorder wait.
- Decision capture is local and auditable, and does not create real purchase orders or supplier/Amazon actions.
- Supplier batches can be reviewed with pack, MOQ, stock, cost, and order-value warnings before any real supplier order is placed.
- O remains labelled mid-build until the full restock -> approval -> purchase order -> receiving -> send-to-Amazon -> feedback loop is proven.

out_of_scope:
- No Google Sheets writes.
- No price changes.
- No queue edits.
- No local database alignment.
- No real purchase orders.
- No receiving actions.
- No send-to-Amazon actions.
- No H pause or market proof scan.
- No Product DB status changes from the manual walkthrough file.
- No automatic buying decisions.

proposed_batches:
- MGR_O_RESTOCK_SESSION_V1

latest_decision:
2026-06-02: Luke asked Codex to proceed after the urgent manual restock walkthrough showed the exact checks O must support.

next_review:
After the O Restock Session v1 task packet is implemented, retest with O UI tests and the O independent MOT. Review whether the UI can replace the manual second-check workspace while keeping final buying decisions protected.
