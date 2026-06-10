# Goal

goal_id: GOAL_F001_one_flow_maintenance_lane

title: Work through SellerOne maintenance one flow at a time

plain_english_goal: Build a paced maintenance plan where each SellerOne flow gets its own small inspection card before any wider system work is attempted. The first flow is F Price List Manager because it is the active manager flow and has a safe Codex-owned batch already identified.

flow: F Price List Manager first; other flows only after Luke explicitly asks to move on

business_reason: Luke needs steady progress without being overloaded by the whole system at once. Each flow should have clear maintenance rails, goals, proof checks, and a stop point before the next flow starts.

current_status: Active manager state shows F Price List Manager is running with 0 manager execution errors and no active manager incident. The control gap is that more F worker-like scripts need manager manifests so the manager can read and explain them without touching worker logic.

success_definition: For the current F phase, Codex creates manager manifests for the next ranked F scripts, proves the manager can read them, and does not edit worker logic, run worker cycles, change queues, write Sheets, change pricing, or expand beyond F.

out_of_scope: Full cross-system walkthrough, A/B/E/H worker repair, Google Sheets writes, pricing changes, F061 queue edits, local database alignment, output deletion, or automatic dispatching.

proposed_batches:
- TASK_F001_register_next_f_manager_manifests

latest_decision: Work one flow at a time at Luke's pace. Start with F Price List Manager only.

next_review: After TASK_F001_register_next_f_manager_manifests is either approved, completed, or rejected.
