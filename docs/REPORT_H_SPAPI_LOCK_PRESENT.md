# REPORT - h_spapi_lock_present

## 1) What file does A015 check?
- A015 checks exactly: `out/locks/spapi.lock`
- Code references:
  - [`scripts/flows/A/A015_build_system_health_check.py:70`](c:/Users/Luke/Desktop/SellerOne%202.0/scripts/flows/A/A015_build_system_health_check.py:70)
  - [`scripts/flows/A/A015_build_system_health_check.py:3598`](c:/Users/Luke/Desktop/SellerOne%202.0/scripts/flows/A/A015_build_system_health_check.py:3598)

## 2) Why does it WARN?
- Rule in A015:
  - if `out/locks/spapi.lock` does not exist -> `ok`
  - if it exists:
    - compute file age from mtime
    - `warn` when age is `<= 2.0` hours
    - `fail` when age is `> 2.0` hours
- Code reference:
  - [`scripts/flows/A/A015_build_system_health_check.py:3603`](c:/Users/Luke/Desktop/SellerOne%202.0/scripts/flows/A/A015_build_system_health_check.py:3603)

## 3) Which process writes the lock, and which should remove it?
- Lock writer:
  - `scripts/api/spapi_owner.py` via `acquire_spapi_lock(run_id, script_name)`
  - Called from `_spapi_request(...)` before SP-API request loop
  - Code references:
    - [`scripts/api/spapi_owner.py:247`](c:/Users/Luke/Desktop/SellerOne%202.0/scripts/api/spapi_owner.py:247)
    - [`scripts/api/spapi_owner.py:469`](c:/Users/Luke/Desktop/SellerOne%202.0/scripts/api/spapi_owner.py:469)
- Lock remover:
  - same module via `release_spapi_lock()`
  - guaranteed in `_spapi_request(...)` `finally` when lock was acquired
  - Code references:
    - [`scripts/api/spapi_owner.py:324`](c:/Users/Luke/Desktop/SellerOne%202.0/scripts/api/spapi_owner.py:324)
    - [`scripts/api/spapi_owner.py:623`](c:/Users/Luke/Desktop/SellerOne%202.0/scripts/api/spapi_owner.py:623)

## Lifecycle fix summary applied
- Added stale/dead/invalid global SP-API lock archiving to `out/locks/archive/spapi.lock.<timestamp>`
- Ensured lock release on clean exit path for acquired locks (request-level `try/finally`)
- Added safe handling for unreadable lock payloads (archive and retry)
