# Execution Batch 001 - Read-Only F Manager Slice

## Scope
Build the first manager slice for F price-list scanner monitoring only.

## Work
- Add the manager package and F manifest.
- Add read-only artifact readers and report writer.
- Add focused tests.
- Add project plan/runbook/data-contract files.

## Proof
- `python -m py_compile sellerone_manager\__init__.py sellerone_manager\paths.py sellerone_manager\schemas.py sellerone_manager\f_price_list_snapshot.py sellerone_manager\reporter.py sellerone_manager\app.py tests\test_sellerone_manager_control_plane.py`
- `pytest tests\test_sellerone_manager_control_plane.py -q`
- `python -m sellerone_manager.app --flow F_price_list_manager --read-only --write-report`

## Stop Conditions
- Stop if a test requires running F061 or any A/B/E/H owner.
- Stop if the manager needs to edit worker-owned files.
