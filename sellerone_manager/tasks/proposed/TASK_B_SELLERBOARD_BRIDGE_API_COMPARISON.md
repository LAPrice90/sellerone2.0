# B Sellerboard Bridge API Comparison Task

task_id: TASK_B_SELLERBOARD_BRIDGE_API_COMPARISON

linked_goal_id: GOAL_B_SELLERBOARD_BRIDGE_API_COMPARISON

title: Build read-only B Sellerboard bridge and MOT proof checks

worker_scope: Manager-side reporting and MOT proof only.

allowed_files: sellerone_manager app, hourly MOT, bridge report code, manager tests, B bridge blueprint, B brainstorm/job list, durable follow-up register.

forbidden_files: B worker business scripts, Google Sheets integrations, price writers, queue files, local database fact stores, live ROI outputs, token/order/refund business data.

acceptance_checks: Bridge report builds from a Sellerboard OrderList CSV; Sellerboard rows map to SellerOne SKUs where possible; summary, order reconciliation, and SKU gap outputs have stable schemas; B MOT detects missing shipped orders or missing SKU mapping as bounded work; refund/fee/ROI gaps are visible as bridge warnings; targeted manager tests pass; no B runtime is run.

stop_condition: Stop before any protected action: B run or restart, Sheets write, price or queue change, local DB alignment, output deletion, business data correction, or using Sellerboard bridge values inside live ROI.

manager_notes: Sellerboard bridge values are temporary outside proof while API access is incomplete. They must remain labelled and separate from final ROI truth.
