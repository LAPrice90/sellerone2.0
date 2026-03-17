# Approved WARN List

Use this list for temporary WARN allowance only. Any WARN not listed here is not approved.

| warn_name | Why allowed temporarily | Removal criteria |
|---|---|---|
| `b_cycle_recent_fail_lines` | Historical fail lines remain in the rolling window while recovery work is in progress. | Remove when unresolved count is 0 for 10 consecutive cycle checks. |
| `h_e_outputs_latest_asof` | E outputs can lag one day while cadence alignment is being stabilized. | Remove when expected asof date matches latest E outputs for 10 consecutive cycle checks. |

## Policy
- `FAIL` always blocks publish.
- `WARN` is allowed only when listed above.
- Keep this file short and explicit. Remove entries as soon as criteria are met.
