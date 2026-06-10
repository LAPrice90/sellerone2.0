# B Sellerboard Bridge API Comparison Goal

goal_id: GOAL_B_SELLERBOARD_BRIDGE_API_COMPARISON

title: B Sellerboard bridge and API comparison proof

plain_english_goal: Use Sellerboard as a temporary outside check so B can prove the 7-day order picture and expose refund, shipping, fee, and ROI gaps without changing live business data.

flow: B

business_reason: B feeds the ROI information used for restocking. If refunds, shipping costs, fees, or return effects are missing from SKU-level proof, restocking can look better than reality.

current_status: Active manager extension. Manual Sellerboard OrderList export is available for first-format proof. Automated email proof is waiting for the first Monday email.

success_definition: A read-only bridge report compares Sellerboard against SellerOne, maps rows to SKUs, separates shipped/unshipped/cancelled/return rows, labels all values as API proved, Sellerboard bridge estimate, or not yet proven, and B MOT turns real outside-proof failures into bounded work items.

out_of_scope: No B run, no B restart, no Sheets write, no price or queue change, no local DB alignment, no data correction, no output deletion, and no live ROI replacement.

proposed_batches: Build read-only bridge report, add B MOT checks, run targeted manager tests, then check the first emailed Sellerboard file format on Monday.

latest_decision: Sellerboard may be used as a temporary bridge only. It must not become permanent source truth without Luke.

next_review: Check first emailed Sellerboard export on Monday 2026-06-01 and compare its format against the manual file.

