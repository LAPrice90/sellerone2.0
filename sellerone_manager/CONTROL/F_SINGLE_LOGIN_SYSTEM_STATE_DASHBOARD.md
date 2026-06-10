# F Single Login System State Dashboard

Updated UTC: 2026-06-09T10:30:00Z
Job: `F-SINGLE-LOGIN-SYSTEM-REBUILD`
Source: redacted code inspection, focused tests, and read-only F MOT evidence.

## Current Redacted State

| Field | Current value |
|---|---|
| Dashboard Yes/No | Not proved in this worker pass. Live proof readiness remains blocked. |
| Current login mode | `holding` from `f061_login_mode.requested`. |
| Login attempt freeze | Active through Seller Central attempt control: latest proof rows show `disabled / normal_scan_only` with `attempted_flag=0`. |
| Browser profile owner | Scanner-owned F061/BBP browser path: `F061_BBP_USER_DATA_DIR` and `F061_BBP_PROFILE_DIR`; no separate Chrome workaround approved or used. |
| Browser visibility | `hidden`, auth state `SELLER_CENTRAL_ELIGIBILITY_LOGIN_REQUIRED`, reason `seller_central_eligibility_login_waiting_parked`. |
| Cooldown/manual challenge | No new manual challenge was live-proved by this worker. Current state is frozen/normal scan only. |
| Held price files | Current live active-run files were not directly readable from the expected live contract path during this pass. |
| Second-check rows | Login mode request shows `selected_login_rows=24` and `selected_bbp_login_rows=24`. |
| Next safe action | Continue code-level containment and Reviewer retest. Do not start live Seller Central proof. |

## Login Entry Point Map

| Entry point | Browser route | Owner after this pass | Containment result |
|---|---|---|---|
| Operator UI login button | Does not open Chrome directly. Writes `f061_login_mode.requested`. | Single login controller request writer. | Routed through `write_login_controller_request`; request file includes `controller_owner=F_LOGIN_CONTROLLER_REWRITE_V1`. |
| FPM130 login-mode child launch | Starts scanner child with `F061_LOGIN_MODE=1` and scanner-owned browser env when request is active. | Single login controller request reader. | Reads request through `read_login_controller_request`; reactivation writes through controller request writer. |
| F061 scanner Chrome route | Opens scanner-owned BBP Chrome and date-support Chrome. | F061 scanner path only. | Browser route remains scanner-owned; no separate Chrome workaround was added. |
| Old BBP auto-login | Uses existing scanner driver/page and records to controller. | Controller records proof. | Still inside scanner-owned path; BBP proof records via `record_login_controller_attempt`. |
| Seller Central auto-login | Uses BBP dashboard handoff and scanner-owned browser context. | Controller attempt control and controller proof records. | Pre-click freeze now blocks BBP Seller Central login-control click when attempt mode is not allowed. |
| Seller Central recovery after context exists | Uses scanner-owned browser context. | Controller attempt control and controller proof records. | Existing recovery gate still blocks credential/code work outside `login_attempt_mode`, cooldown, or manual-challenge boundaries. |

## Gate View

- Gate 1 containment audit: pass for mapped live code paths.
- Gate 2 login attempt freeze: pass for code-level freeze; active runtime evidence still shows normal-scan-only disabled rows, not successful login proof.
- Gate 3 state dashboard: pass; this file is the redacted state dashboard.
- Gate 4 logged-out continuation: pass at focused row-flow level; tests prove normal rows continue while login-required rows remain pending for login backtrack.
- Gate 5 human-assist path: pass at request-routing level; UI button calls the controller request writer and does not open Chrome.
- Gate 6 live proof readiness: blocked. No live Seller Central proof attempt is allowed from this worker pass.

## Maintenance Pause Position

No F runtime pause or restart was performed.

No named F-only maintenance pause request is raised by this worker because the visible evidence shows the scanner-owned path and normal-scan-only disabled login rows, not a separate Chrome workaround or a non-controller login owner. If a later observer sees repeated attempted login rows, SMS/code requests, or Chrome opening outside the scanner-owned path, Operations should raise an F-only maintenance pause request before any live proof.
