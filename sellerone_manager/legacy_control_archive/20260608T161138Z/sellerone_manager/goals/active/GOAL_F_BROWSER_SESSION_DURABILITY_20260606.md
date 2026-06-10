# Goal

goal_id: GOAL_F_BROWSER_SESSION_DURABILITY_20260606

title: Make F keep its approved browser session where possible

plain_english_goal: Stop F from accidentally throwing away a good Amazon/BBP login session. Amazon may still force a fresh login sometimes, but F should not cause extra logouts by using the wrong browser profile, temporary cache, duplicated browser state, or cleanup that removes cookies.

flow: F Price List Manager

business_reason: F is now able to log in automatically, but Monday readiness depends on the scanner staying boring after login. If the browser session is being reset by our own startup or cleanup logic, the scanner will keep wasting time on avoidable login recovery.

current_status: F login controller rewrite is proved and F has auto-recovered at least one later BBP login. The next improvement is session durability: prove whether the scanner is preserving the correct Chrome profile and record exactly why a future login is needed.

success_definition: F has a written session-durability report showing whether the scanner-owned browser keeps the same approved profile, whether cookies/session cache are preserved, whether any local cleanup resets them, and what exact cause is recorded whenever login is needed again.

out_of_scope: Bypassing Amazon security, suppressing MFA, storing one-time codes, exposing credentials, opening separate Chrome workarounds, queue edits, output deletion, price changes, Sheets, local DB alignment, scanner restarts, or live worker cycles without a separate approved proof window.

approved_task:
- F-BROWSER-SESSION-DURABILITY

latest_decision: Luke asked for ideas and a task to reduce avoidable F logouts. The task is approved as read-only investigation plus safe F login/session code hardening only.

next_review: After F-BROWSER-SESSION-DURABILITY reports the browser-session cause map and tests prove the scanner keeps the intended profile.
