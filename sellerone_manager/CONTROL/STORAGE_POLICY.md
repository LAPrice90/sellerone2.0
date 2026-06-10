# SellerOne 2.1 Custodian Policy

Job: `SO21-CUSTODIAN-POLICY`

Created: 2026-06-08

## Plain-English Decision

SellerOne now has a named Custodian role.

The Custodian is the back-office keeper of disk, logs, archives, temporary files, old outputs, stale packets, dead automations, dead schedulers, stale locks, and high-cost repeated AI usage.

This policy does not clean anything yet. It creates the rulebook. The first move is always to measure and label. Deletion comes only after a manifest, a recovery path, and explicit approval when protected data could be touched.

## Why This Exists

The 2026-05-25 emergency cleanup found about 667 GB of removable buildup. That was not normal growth. It was a missing lifecycle.

The lesson is simple:

- every output family needs an owner
- every repeated backup needs a keep rule
- every temp/debug folder needs an expiry rule
- every cleanup needs a dry-run manifest before apply
- protected business data must never be silently deleted

## Custodian Ownership

Custodian owns:

- disk usage
- token and AI usage visibility
- logs
- archives
- temporary files
- old outputs
- stale approved packets
- stale blocked packets
- dead automations
- dead schedulers
- stale lock files
- cleanup manifests
- storage health summaries

Custodian does not own:

- price decisions
- queue edits
- Google Sheets writes
- Product DB or local DB alignment
- purchase orders
- receiving stock
- send-to-Amazon actions
- Amazon security workarounds

## Storage Classes

These are the SellerOne 2.1 retention classes.

| Class | Meaning | Default Rule |
|---|---|---|
| `manual_protected` | Human-created control, secrets-adjacent config, or business-critical files | Never auto-delete |
| `current_runtime` | Files needed by live scripts, active owners, locks, or current proof | Never delete while active |
| `state_rolling` | Current state snapshots with a small useful history | Keep latest plus fixed history |
| `rollback` | Backups or staged recovery folders | Fixed keep count, then archive or compress |
| `audit_history` | Proof, decisions, manifests, and governance records | Keep or archive; do not silently delete |
| `raw_import` | Supplier, browser, API, or source files | Keep canonical source proof; dedupe or archive by rule |
| `derived_report` | Reports that can be rebuilt from source evidence | Short history window |
| `temp_debug` | Test leftovers, debug traces, retry folders, browser scraps | Short expiry after investigation closes |
| `failed_partial` | Incomplete output from a failed run | Keep only while tied to active investigation |
| `code_protected` | Source code, tests, scripts, and Git history | No Custodian cleanup without a code-maintenance ticket |

These classes align with the existing `project_control/AGENT_NEW_CYCLE_STORAGE_RULES.md` storage rules. The 2.1 policy adds human ownership and approval boundaries on top.

## Allowed Without Luke Approval

Custodian may safely do these without changing runtime or business data:

- measure folder size
- count files
- classify folders
- write reports
- write dry-run cleanup manifests
- flag stale automations
- flag stale schedulers
- flag stale locks
- flag repeated backups
- flag high-cost repeated AI loops
- recommend a ticket

## Requires Explicit Approval

These require explicit approval before action:

- deleting outputs
- deleting backups
- deleting old task packets
- deleting old prompt folders
- deleting old automations
- deleting or changing lock files
- deleting or changing scheduler state
- changing business runtime files
- changing the local database
- changing Google Sheets

## Cleanup Proof Rule

Every cleanup must prove the same chain:

1. Dry-run manifest exists.
2. Manifest lists exact path, class, size, action, rule, and recovery route.
3. Protected classes are excluded.
4. Live owners and lock files are checked before apply.
5. Apply happens only at a safe boundary.
6. Post-cleanup proof confirms no current runtime or protected business file was removed.
7. Storage health is checked after the affected area.

If any step is missing, cleanup is not approved.

## No-Touch List

Custodian must not auto-delete:

- `sellerone_manager/CONTROL/`
- `sellerone_manager/tasks/`
- `sellerone_manager/AGENTS.md`
- root `AGENTS.md`
- `config/`
- `secrets/`
- `.git/`
- current live database files under `out/sql/`
- active locks under `out/locks/`
- active runtime proof under `out/systems/`
- current queue packets
- current MOT evidence
- Google Sheets data
- Product DB or local DB facts

## Disk Watermarks

SellerOne should treat disk pressure like a warehouse capacity warning:

| State | Trigger | Custodian Response |
|---|---|---|
| normal | less than 70 percent used | report only |
| watch | 70 to 80 percent used | open storage review ticket if growth is rising |
| restrict | 80 to 90 percent used | block non-essential raw dumps and propose cleanup manifest |
| urgent | more than 90 percent used | ask Luke before destructive cleanup unless an already-approved manifest exists |

## First 2.1 Cleanup Rule

The first SellerOne 2.1 cleanup must be preview-only.

It should produce:

- a top-level storage report
- an `out/` subtree storage index
- a dry-run cleanup manifest
- a protected-file exclusion list
- a recommended cleanup plan

It must not delete anything.

## Required Follow-Up Tickets

Recommended next Custodian tickets:

- `SO21-DEAD-AUTOMATION-AND-SCHEDULER-REVIEW`

## Current Status

Status: policy created, `out/` subtree index created, preview-only dry-run manifest created, no cleanup performed.

Next safe action: review dead automations and schedulers. Do not delete, move, compress, purge, restart, or re-enable anything during that review.
