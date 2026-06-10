import sys
import tempfile
import time
import unittest
import inspect
import os
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from cycles import run_H_pricing_cycle_guarded as h_guard
from cycles import run_H_pricing_cycle as h_cycle
from scripts.flows.H import H110_run_phase1_h_pilot as h110


class HWorkerLifecycleContractTests(unittest.TestCase):
    def test_h_failure_classifier_preserves_progressing_timeout(self) -> None:
        code, detail = h_cycle._classify_h_failure_event(
            failure_code="RuntimeError",
            failure_detail=(
                "RuntimeError:phase1 pilot step timeout reason=max_runtime "
                "elapsed_seconds=1802.20 stalled_seconds=5.03 progress_tail=advanced_count=50"
            ),
            loop_rc="1",
        )

        self.assertEqual(code, "TIMEOUT_PROGRESSING")
        self.assertIn("reason=max_runtime", detail)
        self.assertIn("progress_tail", detail)

    def test_h_failure_classifier_preserves_stalled_timeout(self) -> None:
        code, detail = h_cycle._classify_h_failure_event(
            failure_code="RuntimeError",
            failure_detail=(
                "RuntimeError:phase1 pilot step timeout reason=stall "
                "elapsed_seconds=901.00 stalled_seconds=300.00"
            ),
            loop_rc="1",
        )

        self.assertEqual(code, "TIMEOUT_STALLED")
        self.assertIn("reason=stall", detail)

    def test_snapshot_worker_mode_defaults_inline(self) -> None:
        with mock.patch.dict("os.environ", {}, clear=False):
            self.assertFalse(h_cycle._snapshot_worker_mode_enabled())

    def test_snapshot_worker_mode_can_be_explicitly_enabled(self) -> None:
        with mock.patch.dict("os.environ", {"H_SNAPSHOT_WORKER_MODE": "1"}, clear=False):
            self.assertTrue(h_cycle._snapshot_worker_mode_enabled())

    def test_phase1_pilot_watchdog_allows_bounded_progress_grace(self) -> None:
        extension_seconds, reason = h_cycle._phase1_pilot_progress_grace_extension_seconds(
            elapsed=900.1,
            max_runtime_seconds=900.0,
            stalled_seconds=5.0,
            stall_timeout_seconds=300.0,
            progress_tail="2026-05-11T06:37:05Z market_payload_post_iterrows_zero_row_branch_after sku=SKU1",
            progress_grace_used_seconds=0.0,
            progress_grace_chunk_seconds=300.0,
            progress_grace_max_seconds=900.0,
        )

        self.assertEqual(extension_seconds, 300.0)
        self.assertEqual(reason, "recent_progress")

    def test_phase1_pilot_watchdog_does_not_extend_true_stall(self) -> None:
        extension_seconds, reason = h_cycle._phase1_pilot_progress_grace_extension_seconds(
            elapsed=900.1,
            max_runtime_seconds=900.0,
            stalled_seconds=300.0,
            stall_timeout_seconds=300.0,
            progress_tail="2026-05-11T06:00:00Z older progress",
            progress_grace_used_seconds=0.0,
            progress_grace_chunk_seconds=300.0,
            progress_grace_max_seconds=900.0,
        )

        self.assertEqual(extension_seconds, 0.0)
        self.assertEqual(reason, "stall_timeout_reached")

    def test_phase1_pilot_watchdog_progress_grace_is_capped(self) -> None:
        extension_seconds, reason = h_cycle._phase1_pilot_progress_grace_extension_seconds(
            elapsed=1700.1,
            max_runtime_seconds=1700.0,
            stalled_seconds=10.0,
            stall_timeout_seconds=300.0,
            progress_tail="2026-05-11T06:37:05Z still progressing",
            progress_grace_used_seconds=800.0,
            progress_grace_chunk_seconds=300.0,
            progress_grace_max_seconds=900.0,
        )

        self.assertEqual(extension_seconds, 100.0)
        self.assertEqual(reason, "recent_progress")

    def test_phase1_pilot_watchdog_extends_after_old_grace_cap_when_progressing(self) -> None:
        extension_seconds, reason = h_cycle._phase1_pilot_progress_grace_extension_seconds(
            elapsed=1800.1,
            max_runtime_seconds=1800.0,
            stalled_seconds=61.0,
            stall_timeout_seconds=300.0,
            progress_tail="2026-05-18T11:39:41Z advanced_count=50 status=ok",
            progress_grace_used_seconds=900.0,
            progress_grace_chunk_seconds=300.0,
            progress_grace_max_seconds=2700.0,
        )

        self.assertEqual(extension_seconds, 300.0)
        self.assertEqual(reason, "recent_progress")

    def test_snapshot_refresh_defaults_item_offers_to_subprocess_boundary(self) -> None:
        sig = inspect.signature(h_cycle._refresh_offer_snapshots)
        default_value = sig.parameters["item_offers_subprocess_boundary"].default
        self.assertTrue(default_value)

    def test_item_offers_rc0_missing_output_uses_inline_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            live_dir = Path(td) / "live"
            runtime_status = live_dir / "H_runtime_status.json"
            runtime_status_text = live_dir / "H_runtime_status.txt"
            parent_trace = live_dir / "H_parent_trace.log"
            log_path = live_dir / "H_pricing_cycle.log"
            cycle_log = live_dir / "H_cycle.log"
            legacy_cycle_log = live_dir / "legacy_H_cycle.log"

            def fake_lookup(**_kwargs):
                return (
                    {"ASIN1": {"buy_box_price": "9.99"}},
                    [{"asin": "ASIN1", "seller_id": "S1"}],
                    {"ASIN1": {"detail_status": h_cycle.DETAIL_STATUS_OK}},
                )

            with mock.patch.object(h_cycle, "H_LIVE_DIR", live_dir), \
                mock.patch.object(h_cycle, "H_RUNTIME_STATUS_PATH", runtime_status), \
                mock.patch.object(h_cycle, "H_RUNTIME_STATUS_TEXT_PATH", runtime_status_text), \
                mock.patch.object(h_cycle, "H_PARENT_TRACE_PATH", parent_trace), \
                mock.patch.object(h_cycle, "LOG_PATH", log_path), \
                mock.patch.object(h_cycle, "H_CYCLE_LOG_PATH", cycle_log), \
                mock.patch.object(h_cycle, "LEGACY_H_CYCLE_LOG_PATH", legacy_cycle_log), \
                mock.patch.object(h_cycle, "H_ITEM_OFFERS_OUTPUT_VISIBILITY_WAIT_SECONDS", 0.01), \
                mock.patch.object(h_cycle, "H_ITEM_OFFERS_LOOKUP_RC0_RECOVERY_RETRIES", 0), \
                mock.patch.object(h_cycle, "H_ITEM_OFFERS_LOOKUP_RC0_INLINE_FALLBACK_ENABLED", True), \
                mock.patch.object(
                    h_cycle,
                    "_run_subprocess_with_watchdog_redirected",
                    return_value=subprocess.CompletedProcess(["helper"], 0, "", ""),
                ), \
                mock.patch.object(h_cycle, "run_market_context_lookup_with_offers_detail", side_effect=fake_lookup):
                bb_map, offer_rows, detail_meta = h_cycle._run_item_offers_lookup_guarded(
                    sku_asins=[("SKU1", "ASIN1")],
                    marketplace_id="A1F83G8C2ARO7P",
                    snapshot_ts="2026-05-11T10:00:00Z",
                    snapshot_date="2026-05-11",
                    run_id="RID",
                    script_name="unit_test",
                    subprocess_boundary=True,
                    timeout_seconds=1,
                )

                self.assertEqual(bb_map["ASIN1"]["buy_box_price"], "9.99")
                self.assertEqual(bb_map["SKU1"]["buy_box_price"], "9.99")
                self.assertEqual(offer_rows[0]["seller_id"], "S1")
                self.assertEqual(detail_meta["ASIN1"]["detail_status"], h_cycle.DETAIL_STATUS_OK)
                self.assertIn(
                    "item_offers_missing_output_inline_fallback_done",
                    parent_trace.read_text(encoding="utf-8"),
                )

    def test_main_dispatches_inline_full_worker_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cfg_path = Path(td) / "pilot.yaml"
            cfg_path.write_text("marketplace_id: A1F83G8C2ARO7P\n", encoding="utf-8")
            result_path = Path(td) / "result.json"
            marker_path = Path(td) / "marker.json"
            argv = [
                "H110_run_phase1_h_pilot.py",
                "--phase1-config",
                str(cfg_path),
                "--run-id",
                "RID",
            ]
            old_result = h110.PHASE1_RESULT_PATH
            old_marker = h110.PHASE1_COMPLETION_MARKER_PATH
            try:
                h110.PHASE1_RESULT_PATH = result_path
                h110.PHASE1_COMPLETION_MARKER_PATH = marker_path
                with mock.patch.object(sys, "argv", argv):
                    with mock.patch.object(h110, "_run_full_worker_supervisor", return_value=0) as supervisor:
                        rc = h110.main()
            finally:
                h110.PHASE1_RESULT_PATH = old_result
                h110.PHASE1_COMPLETION_MARKER_PATH = old_marker
            self.assertEqual(rc, 0)
            supervisor.assert_called_once()

    def test_full_worker_supervisor_uses_inline_owner_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cfg_path = Path(td) / "pilot.yaml"
            cfg_path.write_text("marketplace_id: A1F83G8C2ARO7P\n", encoding="utf-8")
            with mock.patch.dict("os.environ", {}, clear=False):
                with mock.patch.object(h110, "_run_market_payload_owner_runtime", return_value=0) as market_owner:
                    rc = h110._run_full_worker_supervisor(
                        cfg_path=cfg_path,
                        run_id="RID",
                        read_only=False,
                        now_utc_arg="",
                    )
            self.assertEqual(rc, 0)
            market_owner.assert_called_once()

    def test_probe_boundary_subcall_exit_is_inconclusive_when_output_path_known(self) -> None:
        allowed, output_path = h110._probe_boundary_failure_is_inconclusive_for_read_boundary(
            failed_reason="subcall_exited_during_probe",
            probe_boundary_payload={
                "subcall_output_path": "C:/tmp/subcall.out.json",
            },
        )
        self.assertTrue(allowed)
        self.assertEqual(output_path, "C:/tmp/subcall.out.json")

    def test_probe_boundary_subcall_exit_without_output_path_is_not_inconclusive(self) -> None:
        allowed, output_path = h110._probe_boundary_failure_is_inconclusive_for_read_boundary(
            failed_reason="subcall_exited_during_probe",
            probe_boundary_payload={},
        )
        self.assertFalse(allowed)
        self.assertEqual(output_path, "")

    def test_probe_boundary_non_matching_failure_remains_terminal(self) -> None:
        allowed, output_path = h110._probe_boundary_failure_is_inconclusive_for_read_boundary(
            failed_reason="probe_boundary_read_invalid",
            probe_boundary_payload={
                "subcall_output_path": "C:/tmp/subcall.out.json",
            },
        )
        self.assertFalse(allowed)
        self.assertEqual(output_path, "")

    def test_owner_wait_enter_exit_emits_resolved_state(self) -> None:
        h110._owner_wait_mark_enter(
            run_id="RID",
            sku="SKU1",
            subcall_pid="123",
            helper_pid="456",
            timeout_seconds=30,
        )
        unresolved = h110._owner_wait_unresolved_reason(run_id="RID")
        self.assertTrue(unresolved.startswith("owner_wait_unresolved:"))
        h110._owner_wait_mark_exit(
            run_id="RID",
            sku="SKU1",
            state="wait_returned",
            reason="read_boundary_helper_wait_returned_rc_0",
            worker_rc="0",
            output_exists="1",
        )
        self.assertEqual(h110._owner_wait_unresolved_reason(run_id="RID"), "")

    def test_owner_wait_unresolved_reason_ignores_other_run_id(self) -> None:
        h110._owner_wait_mark_enter(
            run_id="RID_A",
            sku="SKU1",
            subcall_pid="123",
            helper_pid="456",
            timeout_seconds=30,
        )
        try:
            self.assertEqual(h110._owner_wait_unresolved_reason(run_id="RID_B"), "")
            self.assertTrue(h110._owner_wait_unresolved_reason(run_id="RID_A").startswith("owner_wait_unresolved:"))
        finally:
            h110._owner_wait_mark_exit(
                run_id="RID_A",
                sku="SKU1",
                state="abandoned",
                reason="test_cleanup",
                worker_rc="",
                output_exists="0",
            )

    def test_owner_wait_unresolved_reason_matches_child_run_id_suffix(self) -> None:
        h110._owner_wait_mark_enter(
            run_id="RID_PARENT_01",
            sku="SKU1",
            subcall_pid="123",
            helper_pid="456",
            timeout_seconds=30,
        )
        try:
            unresolved = h110._owner_wait_unresolved_reason(run_id="RID_PARENT")
            self.assertTrue(unresolved.startswith("owner_wait_unresolved:"))
            self.assertIn("RID_PARENT_01", unresolved)
        finally:
            h110._owner_wait_mark_exit(
                run_id="RID_PARENT_01",
                sku="SKU1",
                state="abandoned",
                reason="test_cleanup",
                worker_rc="",
                output_exists="0",
            )

    def test_market_payload_read_boundary_fails_fast_when_owner_is_lost(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            input_path = tmp / "in.json"
            output_path = tmp / "out.json"
            subcall_output_path = tmp / "subcall.out.json"
            input_payload = {
                "run_id": "RID",
                "sku": "SKU1",
                "owner_pid": "4242",
                "subcall_pid": "0",
                "subcall_output_path": str(subcall_output_path),
                "timeout_seconds": "20",
            }
            input_path.write_text(h110.json.dumps(input_payload) + "\n", encoding="utf-8")

            with mock.patch.object(h110, "_pid_alive", return_value=False):
                started = time.monotonic()
                rc = h110._run_market_payload_read_boundary_mode(
                    input_path=input_path,
                    output_path=output_path,
                )
                elapsed = time.monotonic() - started

            self.assertEqual(rc, 1)
            self.assertLess(elapsed, 3.0)
            raw = h110.json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(raw.get("contract_status"), "failed")
            self.assertEqual(raw.get("checkpoint_last"), "market_payload_read_boundary_owner_lost")
            self.assertIn("owner_lost_before_boundary_settle", str(raw.get("reason", "")))

    def test_invoke_market_payload_read_boundary_includes_owner_pid_in_helper_request(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            old_live = h110.H_LIVE_DIR
            try:
                h110.H_LIVE_DIR = tmp
                seen_owner_pid: list[str] = []

                def _capture_req_and_stop(path: Path, text: str) -> None:
                    payload = h110.json.loads(text)
                    seen_owner_pid.append(str(payload.get("owner_pid", "")))
                    raise RuntimeError("stop_after_req_capture")

                with mock.patch.object(h110.os, "getpid", return_value=1111):
                    with mock.patch.object(h110, "_atomic_write_text", side_effect=_capture_req_and_stop):
                        with self.assertRaises(RuntimeError) as exc:
                            h110._invoke_market_payload_read_boundary(
                                run_id="RID",
                                sku="SKU1",
                                subcall_spawn_contract={
                                    "subcall_output_path": str(tmp / "missing.json"),
                                    "subcall_pid": "0",
                                    "timeout_seconds": "20",
                                },
                            )
                self.assertIn("stop_after_req_capture", str(exc.exception))
                self.assertEqual(seen_owner_pid, ["1111"])
            finally:
                h110.H_LIVE_DIR = old_live

    def test_invoke_market_payload_read_boundary_uses_inline_mode(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            old_live = h110.H_LIVE_DIR
            try:
                h110.H_LIVE_DIR = tmp
                seen_helper_pid: list[str] = []

                def _fake_mode(*, input_path: Path, output_path: Path) -> int:
                    req = h110.json.loads(input_path.read_text(encoding="utf-8"))
                    payload = {
                        "run_id": req.get("run_id", ""),
                        "sku": req.get("sku", ""),
                        "contract_status": "ok",
                        "reason": "ok",
                        "subcall_output_path": req.get("subcall_output_path", ""),
                        "parsed_payload": {"ok": True},
                        "listings_observed_price": "",
                        "checkpoint_last": "market_payload_read_boundary_valid",
                        "error_class": "",
                    }
                    output_path.write_text(h110.json.dumps(payload) + "\n", encoding="utf-8")
                    return 0

                def _capture_enter(*, run_id: str, sku: str, subcall_pid: str, helper_pid: str, timeout_seconds: object) -> None:
                    seen_helper_pid.append(str(helper_pid))

                with mock.patch.object(h110, "_run_market_payload_read_boundary_mode", side_effect=_fake_mode):
                    with mock.patch.object(h110, "_owner_wait_mark_enter", side_effect=_capture_enter):
                        with mock.patch.object(h110, "_owner_wait_mark_exit", return_value=None):
                            # Force deterministic inline fallback in unit test.
                            with mock.patch.object(h110, "_popen_hidden", side_effect=PermissionError("unit_test_inline_fallback")):
                                contract = h110._invoke_market_payload_read_boundary(
                                    run_id="RID",
                                    sku="SKU1",
                                    subcall_spawn_contract={
                                        "subcall_output_path": str(tmp / "subcall.out.json"),
                                        "subcall_pid": "999",
                                        "timeout_seconds": "20",
                                    },
                                )
                self.assertEqual(contract.get("contract_status"), "ok")
                self.assertEqual(contract.get("checkpoint_last"), "market_payload_read_boundary_valid")
                self.assertEqual(seen_helper_pid, ["subprocess"])
            finally:
                h110.H_LIVE_DIR = old_live

    def test_post_exit_terminalizer_pid_reuse_writes_failed_marker(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            marker = tmp / "marker.json"
            result = tmp / "result.json"
            marker.write_text(
                '{"utc":"2026-03-20T00:00:00Z","status":"started","run_id":"RID","reason":"run_started","result_path":"x","result_ok":"0"}\n',
                encoding="utf-8",
            )
            old_live = h110.H_LIVE_DIR
            old_progress = h110.PHASE1_PROGRESS_PATH
            try:
                h110.H_LIVE_DIR = tmp
                h110.PHASE1_PROGRESS_PATH = None

                calls = {"n": 0}

                def _fake_pid_alive(_pid: int) -> bool:
                    calls["n"] += 1
                    if calls["n"] <= 2:
                        return False
                    return True

                with mock.patch.dict(
                    "os.environ",
                    {
                        "H110_TERMINALIZER_FALSE_FAIL_GUARD_SECONDS": "1",
                        "H110_TERMINALIZER_FALSE_FAIL_GUARD_INTERVAL_SECONDS": "0.1",
                        "H110_TERMINALIZER_FALSE_FAIL_GUARD_ACTIVITY_WINDOW_SECONDS": "0.1",
                    },
                    clear=False,
                ):
                    with mock.patch.object(h110, "_pid_alive", side_effect=_fake_pid_alive):
                        rc = h110._run_post_exit_terminalizer(
                            run_id="RID",
                            parent_pid=12345,
                            marker_path=marker,
                            result_path=result,
                            checkpoint_path=None,
                            wait_seconds=0.1,
                        )
                self.assertEqual(rc, 0)
                marker_raw = marker.read_text(encoding="utf-8")
                self.assertIn('"status": "failed"', marker_raw)
            finally:
                h110.H_LIVE_DIR = old_live
                h110.PHASE1_PROGRESS_PATH = old_progress

    def test_post_exit_terminalizer_does_not_mutate_h_run_state(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            marker = tmp / "marker.json"
            result = tmp / "result.json"
            run_state = tmp / "H_run_state.json"
            marker.write_text(
                '{"utc":"2026-03-20T00:00:00Z","status":"started","run_id":"RID","reason":"run_started","result_path":"x","result_ok":"0"}\n',
                encoding="utf-8",
            )
            initial_run_state = (
                '{"run_id":"RID","state":"pilot_started","stage":"phase1_pilot","publish_status":"not_started"}\n'
            )
            run_state.write_text(initial_run_state, encoding="utf-8")
            old_live = h110.H_LIVE_DIR
            old_progress = h110.PHASE1_PROGRESS_PATH
            old_run_state = h110.H_RUN_STATE_PATH
            try:
                h110.H_LIVE_DIR = tmp
                h110.PHASE1_PROGRESS_PATH = None
                h110.H_RUN_STATE_PATH = run_state
                with mock.patch.dict(
                    "os.environ",
                    {
                        "H110_TERMINALIZER_FALSE_FAIL_GUARD_SECONDS": "1",
                        "H110_TERMINALIZER_FALSE_FAIL_GUARD_INTERVAL_SECONDS": "0.1",
                        "H110_TERMINALIZER_FALSE_FAIL_GUARD_ACTIVITY_WINDOW_SECONDS": "0.1",
                    },
                    clear=False,
                ):
                    with mock.patch.object(h110, "_pid_alive", return_value=False):
                        rc = h110._run_post_exit_terminalizer(
                            run_id="RID",
                            parent_pid=12345,
                            marker_path=marker,
                            result_path=result,
                            checkpoint_path=None,
                            wait_seconds=0.1,
                        )
                self.assertEqual(rc, 0)
                self.assertEqual(run_state.read_text(encoding="utf-8"), initial_run_state)
            finally:
                h110.H_LIVE_DIR = old_live
                h110.PHASE1_PROGRESS_PATH = old_progress
                h110.H_RUN_STATE_PATH = old_run_state

    def test_owner_exit_evidence_requires_explicit_run_binding(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            live = Path(td)
            capture_path = live / "H_core_parent_exit_capture.1234.20260402T000000Z.json"
            capture_payload = {
                "target_pid": "1234",
                "observed": {},
                "observed_end": {},
                "authoritative_linkage": {
                    "attribution_possible": "1",
                    "security_process_audit": {
                        "attribution_possible": "1",
                        "candidates": [
                            {
                                "event_class": "process_exit",
                                "contains_target_pid": "1",
                                "record_id": "100",
                            }
                        ],
                    },
                },
            }
            capture_path.write_text(json.dumps(capture_payload, ensure_ascii=True) + "\n", encoding="utf-8")
            old_live = h_cycle.H_LIVE_DIR
            try:
                h_cycle.H_LIVE_DIR = live
                evidence = h_cycle._classify_stale_owner_exit_evidence("RID", 1234)
            finally:
                h_cycle.H_LIVE_DIR = old_live
            self.assertEqual(evidence.get("usable"), "0")
            self.assertEqual(evidence.get("reason"), "owner_exit_capture_not_matched_for_run")

    def test_owner_exit_evidence_accepts_same_run_binding(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            live = Path(td)
            capture_path = live / "H_core_parent_exit_capture.1234.20260402T000100Z.json"
            capture_payload = {
                "target_pid": "1234",
                "observed": {
                    "run_id_current_start": "RID",
                },
                "observed_end": {
                    "run_id_current_end": "RID",
                },
                "authoritative_linkage": {
                    "attribution_possible": "1",
                    "security_process_audit": {
                        "attribution_possible": "1",
                        "candidates": [
                            {
                                "event_class": "process_exit",
                                "contains_target_pid": "1",
                                "record_id": "101",
                            }
                        ],
                    },
                },
            }
            capture_path.write_text(json.dumps(capture_payload, ensure_ascii=True) + "\n", encoding="utf-8")
            old_live = h_cycle.H_LIVE_DIR
            try:
                h_cycle.H_LIVE_DIR = live
                evidence = h_cycle._classify_stale_owner_exit_evidence("RID", 1234)
            finally:
                h_cycle.H_LIVE_DIR = old_live
            self.assertEqual(evidence.get("usable"), "1")
            self.assertEqual(evidence.get("reason"), "owner_exit_capture_matched")
            self.assertEqual(evidence.get("record_id"), "101")

    def test_owner_exit_evidence_accepts_capture_window_transition_binding(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            live = Path(td)
            capture_path = live / "H_core_parent_exit_capture.1234.20260402T203602Z.json"
            capture_payload = {
                "target_pid": "1234",
                "observed": {
                    "capture_start_utc": "2026-04-02T20:36:02Z",
                    "run_id_current_start": "RID_OLD",
                },
                "observed_end": {
                    "run_id_current_end": "RID",
                    "run_id_in_progress_end": "RID",
                    "runtime_status_end": {"run_id": "RID", "error": "RUN_STATE_NOT_TERMINAL"},
                },
                "liveness": {
                    "disappearance_utc": "2026-04-02T20:37:59Z",
                },
                "authoritative_linkage": {
                    "attribution_possible": "1",
                    "security_process_audit": {
                        "attribution_possible": "1",
                        "candidates": [
                            {
                                "event_class": "process_exit",
                                "contains_target_pid": "1",
                                "record_id": "102",
                            }
                        ],
                    },
                },
            }
            capture_path.write_text(json.dumps(capture_payload, ensure_ascii=True) + "\n", encoding="utf-8")
            old_live = h_cycle.H_LIVE_DIR
            try:
                h_cycle.H_LIVE_DIR = live
                evidence = h_cycle._classify_stale_owner_exit_evidence(
                    "RID",
                    1234,
                    run_state_utc="2026-04-02T20:37:34Z",
                )
            finally:
                h_cycle.H_LIVE_DIR = old_live
            self.assertEqual(evidence.get("usable"), "1")
            self.assertEqual(evidence.get("reason"), "owner_exit_capture_matched")
            self.assertEqual(evidence.get("start_binding_mode"), "capture_window_transition")

    def test_owner_exit_evidence_rejects_transition_binding_without_run_state_time(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            live = Path(td)
            capture_path = live / "H_core_parent_exit_capture.1234.20260402T203602Z.json"
            capture_payload = {
                "target_pid": "1234",
                "observed": {
                    "capture_start_utc": "2026-04-02T20:36:02Z",
                    "run_id_current_start": "RID_OLD",
                },
                "observed_end": {
                    "run_id_current_end": "RID",
                    "run_id_in_progress_end": "RID",
                },
                "liveness": {
                    "disappearance_utc": "2026-04-02T20:37:59Z",
                },
                "authoritative_linkage": {
                    "attribution_possible": "1",
                    "security_process_audit": {
                        "attribution_possible": "1",
                        "candidates": [
                            {
                                "event_class": "process_exit",
                                "contains_target_pid": "1",
                                "record_id": "103",
                            }
                        ],
                    },
                },
            }
            capture_path.write_text(json.dumps(capture_payload, ensure_ascii=True) + "\n", encoding="utf-8")
            old_live = h_cycle.H_LIVE_DIR
            try:
                h_cycle.H_LIVE_DIR = live
                evidence = h_cycle._classify_stale_owner_exit_evidence("RID", 1234)
            finally:
                h_cycle.H_LIVE_DIR = old_live
            self.assertEqual(evidence.get("usable"), "0")
            self.assertEqual(evidence.get("reason"), "owner_exit_capture_not_matched_for_run")

    def test_pilot_reconcile_eligibility_started_marker_can_settle(self) -> None:
        allowed, reason = h_cycle._phase1_pilot_contract_reconcile_eligibility(
            contract_class="completion_marker_not_success",
            marker_status="started",
            marker_reason="run_started",
            payload_present=False,
            marker_result_ok="0",
        )
        self.assertTrue(allowed)
        self.assertIn("owner_handoff", reason)

    def test_pilot_reconcile_eligibility_failed_marker_is_terminal(self) -> None:
        allowed, reason = h_cycle._phase1_pilot_contract_reconcile_eligibility(
            contract_class="completion_marker_not_success",
            marker_status="failed",
            marker_reason="runtime_error",
            payload_present=False,
            marker_result_ok="0",
        )
        self.assertFalse(allowed)
        self.assertEqual(reason, "marker_failed_is_terminal")

    def test_pilot_reconcile_eligibility_missing_payload_without_success_marker_blocks(self) -> None:
        allowed, reason = h_cycle._phase1_pilot_contract_reconcile_eligibility(
            contract_class="result_payload_missing",
            marker_status="started",
            marker_reason="run_started",
            payload_present=False,
            marker_result_ok="0",
        )
        self.assertFalse(allowed)
        self.assertEqual(reason, "payload_missing_without_success_marker_is_terminal")

    def test_normal_success_requires_finalizer_and_worker_terminal(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            run_id = "20260320T100000Z"
            old_publish = h_cycle.H_CYCLE_LAST_PUBLISH_RUN_PATH
            old_completed = h_cycle.H_CYCLE_LAST_COMPLETED_RUN_PATH
            old_finalized = h_cycle.H_LAST_FINALIZED_RUN_ID_PATH
            old_run_state = h_cycle.H_RUN_STATE_PATH
            old_worker = h_cycle.H_WORKER_LIFECYCLE_PATH
            old_run_ctx = h_cycle._context_run_id()
            try:
                h_cycle.H_CYCLE_LAST_PUBLISH_RUN_PATH = root / "H_cycle_last_publish_run_id.txt"
                h_cycle.H_CYCLE_LAST_COMPLETED_RUN_PATH = root / "H_cycle_last_completed_run_id.txt"
                h_cycle.H_LAST_FINALIZED_RUN_ID_PATH = root / "H_last_finalized_run_id.txt"
                h_cycle.H_RUN_STATE_PATH = root / "H_run_state.json"
                h_cycle.H_WORKER_LIFECYCLE_PATH = root / "H_worker_lifecycle.json"
                h_cycle.H_CYCLE_LAST_PUBLISH_RUN_PATH.write_text(f"{run_id}\n", encoding="utf-8")
                h_cycle.H_CYCLE_LAST_COMPLETED_RUN_PATH.write_text(f"{run_id}\n", encoding="utf-8")
                h_cycle.H_LAST_FINALIZED_RUN_ID_PATH.write_text(f"{run_id}\n", encoding="utf-8")
                h_cycle.H_RUN_STATE_PATH.write_text(
                    '{"run_id":"%s","state":"finalized","publish_status":"ok"}\n' % run_id,
                    encoding="utf-8",
                )
                h_cycle.H_WORKER_LIFECYCLE_PATH.write_text(
                    '{"run_id":"%s","state":"succeeded","heartbeat_utc":"2026-03-20T10:00:00Z"}\n' % run_id,
                    encoding="utf-8",
                )
                h_cycle._set_run_context(run_id)
                ok, missing = h_cycle._verify_h_success_outputs(run_id)
                self.assertTrue(ok)
                self.assertEqual(missing, [])
                self.assertEqual(h_cycle._promote_zero_exit_without_finalizer(0), 0)
            finally:
                h_cycle.H_CYCLE_LAST_PUBLISH_RUN_PATH = old_publish
                h_cycle.H_CYCLE_LAST_COMPLETED_RUN_PATH = old_completed
                h_cycle.H_LAST_FINALIZED_RUN_ID_PATH = old_finalized
                h_cycle.H_RUN_STATE_PATH = old_run_state
                h_cycle.H_WORKER_LIFECYCLE_PATH = old_worker
                h_cycle._set_run_context(old_run_ctx)

    def test_missing_outputs_force_contract_failure(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            run_id = "20260320T110000Z"
            old_publish = h_cycle.H_CYCLE_LAST_PUBLISH_RUN_PATH
            old_completed = h_cycle.H_CYCLE_LAST_COMPLETED_RUN_PATH
            old_finalized = h_cycle.H_LAST_FINALIZED_RUN_ID_PATH
            old_run_state = h_cycle.H_RUN_STATE_PATH
            try:
                h_cycle.H_CYCLE_LAST_PUBLISH_RUN_PATH = root / "H_cycle_last_publish_run_id.txt"
                h_cycle.H_CYCLE_LAST_COMPLETED_RUN_PATH = root / "H_cycle_last_completed_run_id.txt"
                h_cycle.H_LAST_FINALIZED_RUN_ID_PATH = root / "H_last_finalized_run_id.txt"
                h_cycle.H_RUN_STATE_PATH = root / "H_run_state.json"
                h_cycle.H_CYCLE_LAST_PUBLISH_RUN_PATH.write_text(f"{run_id}\n", encoding="utf-8")
                # completed/finalized/run_state intentionally missing
                ok, missing = h_cycle._verify_h_success_outputs(run_id)
                self.assertFalse(ok)
                self.assertIn("H_cycle_last_completed_run_id_mismatch", missing)
                self.assertIn("H_last_finalized_run_id_mismatch", missing)
                self.assertIn("H_run_state_not_finalized_for_run", missing)
            finally:
                h_cycle.H_CYCLE_LAST_PUBLISH_RUN_PATH = old_publish
                h_cycle.H_CYCLE_LAST_COMPLETED_RUN_PATH = old_completed
                h_cycle.H_LAST_FINALIZED_RUN_ID_PATH = old_finalized
                h_cycle.H_RUN_STATE_PATH = old_run_state

    def test_zero_exit_is_promoted_when_worker_terminal_missing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            run_id = "20260320T120000Z"
            old_finalized = h_cycle.H_LAST_FINALIZED_RUN_ID_PATH
            old_worker = h_cycle.H_WORKER_LIFECYCLE_PATH
            old_run_ctx = h_cycle._context_run_id()
            try:
                h_cycle.H_LAST_FINALIZED_RUN_ID_PATH = root / "H_last_finalized_run_id.txt"
                h_cycle.H_WORKER_LIFECYCLE_PATH = root / "H_worker_lifecycle.json"
                h_cycle.H_LAST_FINALIZED_RUN_ID_PATH.write_text(f"{run_id}\n", encoding="utf-8")
                h_cycle.H_WORKER_LIFECYCLE_PATH.write_text(
                    '{"run_id":"%s","state":"running","heartbeat_utc":"2026-03-20T12:00:00Z"}\n' % run_id,
                    encoding="utf-8",
                )
                h_cycle._set_run_context(run_id)
                self.assertEqual(h_cycle._promote_zero_exit_without_finalizer(0), 3)
            finally:
                h_cycle.H_LAST_FINALIZED_RUN_ID_PATH = old_finalized
                h_cycle.H_WORKER_LIFECYCLE_PATH = old_worker
                h_cycle._set_run_context(old_run_ctx)

    def test_worker_lifecycle_run_change_clears_stale_terminal_fields(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            lifecycle_path = root / "H_worker_lifecycle.json"
            lifecycle_path.write_text(
                (
                    "{"
                    "\"run_id\":\"20260320T090000Z\","
                    "\"state\":\"failed\","
                    "\"heartbeat_utc\":\"2026-03-20T09:10:00Z\","
                    "\"pending_utc\":\"2026-03-20T09:00:00Z\","
                    "\"running_utc\":\"2026-03-20T09:01:00Z\","
                    "\"terminal_utc\":\"2026-03-20T09:10:00Z\","
                    "\"terminal_outcome\":\"failed\","
                    "\"reason_code\":\"LOOP_RC_3\","
                    "\"reason_detail\":\"old_failure\","
                    "\"failure_code\":\"STARTUP_STALE_OWNER_LOCK_ARCHIVE_HARD_PROOF\","
                    "\"failure_detail\":\"old_archive_failure\","
                    "\"archive_marker_path\":\"C:/tmp/H_failed_run_archived.20260320T090000Z.json\","
                    "\"expected_outputs_ok\":\"0\","
                    "\"expected_outputs_missing\":\"H_cycle_last_publish_run_id_mismatch\""
                    "}\n"
                ),
                encoding="utf-8",
            )
            old_worker = h_cycle.H_WORKER_LIFECYCLE_PATH
            old_ctx = h_cycle._context_run_id()
            old_cache = dict(h_cycle._WORKER_LIFECYCLE_CACHE)
            try:
                h_cycle.H_WORKER_LIFECYCLE_PATH = lifecycle_path
                h_cycle._WORKER_LIFECYCLE_CACHE.clear()
                h_cycle._set_run_context("20260320T100000Z")
                ok = h_cycle._transition_h_worker_lifecycle(
                    "20260320T100000Z",
                    "pending",
                    emit_log=False,
                )
                self.assertTrue(ok)
                payload = h_cycle._read_h_worker_lifecycle()
                self.assertEqual(payload.get("run_id"), "20260320T100000Z")
                self.assertEqual(payload.get("state"), "pending")
                self.assertNotEqual(payload.get("pending_utc", ""), "")
                self.assertEqual(payload.get("running_utc", ""), "")
                self.assertEqual(payload.get("terminal_utc", ""), "")
                self.assertEqual(payload.get("terminal_outcome", ""), "")
                self.assertEqual(payload.get("reason_code", ""), "")
                self.assertEqual(payload.get("reason_detail", ""), "")
                self.assertEqual(payload.get("failure_code", ""), "")
                self.assertEqual(payload.get("failure_detail", ""), "")
                self.assertEqual(payload.get("archive_marker_path", ""), "")
                self.assertEqual(payload.get("expected_outputs_ok", ""), "")
                self.assertEqual(payload.get("expected_outputs_missing", ""), "")
            finally:
                h_cycle.H_WORKER_LIFECYCLE_PATH = old_worker
                h_cycle._set_run_context(old_ctx)
                h_cycle._WORKER_LIFECYCLE_CACHE.clear()
                h_cycle._WORKER_LIFECYCLE_CACHE.update(old_cache)

    def test_worker_lifecycle_success_transition_clears_stale_archive_fields(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            lifecycle_path = root / "H_worker_lifecycle.json"
            run_id = "20260320T100000Z"
            lifecycle_path.write_text(
                (
                    "{"
                    f"\"run_id\":\"{run_id}\","
                    "\"state\":\"running\","
                    "\"heartbeat_utc\":\"2026-03-20T10:00:00Z\","
                    "\"failure_code\":\"STARTUP_STALE_OWNER_LOCK_ARCHIVE_HARD_PROOF\","
                    "\"failure_detail\":\"old_archive_failure\","
                    "\"archive_marker_path\":\"C:/tmp/H_failed_run_archived.20260320T090000Z.json\""
                    "}\n"
                ),
                encoding="utf-8",
            )
            old_worker = h_cycle.H_WORKER_LIFECYCLE_PATH
            old_ctx = h_cycle._context_run_id()
            old_cache = dict(h_cycle._WORKER_LIFECYCLE_CACHE)
            try:
                h_cycle.H_WORKER_LIFECYCLE_PATH = lifecycle_path
                h_cycle._WORKER_LIFECYCLE_CACHE.clear()
                h_cycle._set_run_context(run_id)
                ok = h_cycle._transition_h_worker_lifecycle(
                    run_id,
                    "succeeded",
                    terminal_outcome="succeeded",
                    expected_outputs_ok="1",
                    emit_log=False,
                )
                self.assertTrue(ok)
                payload = h_cycle._read_h_worker_lifecycle()
                self.assertEqual(payload.get("run_id"), run_id)
                self.assertEqual(payload.get("state"), "succeeded")
                self.assertEqual(payload.get("terminal_outcome"), "succeeded")
                self.assertEqual(payload.get("expected_outputs_ok"), "1")
                self.assertEqual(payload.get("failure_code", ""), "")
                self.assertEqual(payload.get("failure_detail", ""), "")
                self.assertEqual(payload.get("archive_marker_path", ""), "")
            finally:
                h_cycle.H_WORKER_LIFECYCLE_PATH = old_worker
                h_cycle._set_run_context(old_ctx)
                h_cycle._WORKER_LIFECYCLE_CACHE.clear()
                h_cycle._WORKER_LIFECYCLE_CACHE.update(old_cache)

    def test_stale_pilot_reconcile_defers_when_wrapper_handover_active_with_current_run_marker(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            run_id = "20260329T090243Z"
            run_state_utc = (datetime.now(timezone.utc) - timedelta(seconds=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
            run_state_path = root / "H_run_state.json"
            runtime_status_path = root / "H_runtime_status.json"
            run_in_progress_path = root / "H_run_in_progress.txt"
            current_run_path = root / "H_cycle_current_run_id.txt"
            run_state_path.write_text(
                (
                    "{"
                    f"\"run_id\":\"{run_id}\","
                    "\"state\":\"started\","
                    "\"owner_pid\":\"111\","
                    "\"publish_status\":\"not_started\","
                    f"\"utc\":\"{run_state_utc}\""
                    "}\n"
                ),
                encoding="utf-8",
            )
            runtime_status_path.write_text(
                (
                    "{"
                    f"\"run_id\":\"{run_id}\","
                    "\"mode\":\"RUNNING\","
                    "\"stage\":\"child_wait\","
                    "\"pid\":\"222\","
                    "\"detail\":\"child_pid=333\""
                    "}\n"
                ),
                encoding="utf-8",
            )
            current_run_path.write_text(f"{run_id}\n", encoding="utf-8")
            old_run_state = h_cycle.H_RUN_STATE_PATH
            old_runtime_status = h_cycle.H_RUNTIME_STATUS_PATH
            old_run_in_progress = h_cycle.H_RUN_IN_PROGRESS_PATH
            old_current_run = h_cycle.H_CYCLE_CURRENT_RUN_PATH
            try:
                h_cycle.H_RUN_STATE_PATH = run_state_path
                h_cycle.H_RUNTIME_STATUS_PATH = runtime_status_path
                h_cycle.H_RUN_IN_PROGRESS_PATH = run_in_progress_path
                h_cycle.H_CYCLE_CURRENT_RUN_PATH = current_run_path
                with mock.patch.object(h_cycle.os, "getpid", return_value=333):
                    with mock.patch.object(
                        h_cycle,
                        "_pid_alive",
                        side_effect=lambda pid: int(pid) in {222, 333},
                    ):
                        with mock.patch.object(h_cycle, "_write_h_run_state") as write_state:
                            with mock.patch.object(h_cycle, "_clear_run_in_progress") as clear_marker:
                                with mock.patch.object(h_cycle, "_read_latest_phase1_pilot_terminal_artifacts", return_value={"success_ok": "0"}):
                                    with mock.patch.object(h_cycle, "_lock_probe_paths", return_value=[]):
                                        h_cycle._reconcile_stale_pilot_started_dead_owner()
                write_state.assert_not_called()
                clear_marker.assert_not_called()
            finally:
                h_cycle.H_RUN_STATE_PATH = old_run_state
                h_cycle.H_RUNTIME_STATUS_PATH = old_runtime_status
                h_cycle.H_RUN_IN_PROGRESS_PATH = old_run_in_progress
                h_cycle.H_CYCLE_CURRENT_RUN_PATH = old_current_run

    def test_stale_pilot_reconcile_observe_only_when_handover_window_expired(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            run_id = "20260329T090243Z"
            run_state_utc = (datetime.now(timezone.utc) - timedelta(seconds=600)).strftime("%Y-%m-%dT%H:%M:%SZ")
            run_state_path = root / "H_run_state.json"
            runtime_status_path = root / "H_runtime_status.json"
            run_in_progress_path = root / "H_run_in_progress.txt"
            current_run_path = root / "H_cycle_current_run_id.txt"
            run_state_path.write_text(
                (
                    "{"
                    f"\"run_id\":\"{run_id}\","
                    "\"state\":\"started\","
                    "\"owner_pid\":\"111\","
                    "\"publish_status\":\"not_started\","
                    f"\"utc\":\"{run_state_utc}\""
                    "}\n"
                ),
                encoding="utf-8",
            )
            runtime_status_path.write_text(
                (
                    "{"
                    f"\"run_id\":\"{run_id}\","
                    "\"mode\":\"RUNNING\","
                    "\"stage\":\"child_wait\","
                    "\"pid\":\"222\","
                    "\"detail\":\"child_pid=333\""
                    "}\n"
                ),
                encoding="utf-8",
            )
            current_run_path.write_text(f"{run_id}\n", encoding="utf-8")
            old_run_state = h_cycle.H_RUN_STATE_PATH
            old_runtime_status = h_cycle.H_RUNTIME_STATUS_PATH
            old_run_in_progress = h_cycle.H_RUN_IN_PROGRESS_PATH
            old_current_run = h_cycle.H_CYCLE_CURRENT_RUN_PATH
            try:
                h_cycle.H_RUN_STATE_PATH = run_state_path
                h_cycle.H_RUNTIME_STATUS_PATH = runtime_status_path
                h_cycle.H_RUN_IN_PROGRESS_PATH = run_in_progress_path
                h_cycle.H_CYCLE_CURRENT_RUN_PATH = current_run_path
                with mock.patch.object(h_cycle.os, "getpid", return_value=333):
                    with mock.patch.object(
                        h_cycle,
                        "_pid_alive",
                        side_effect=lambda pid: int(pid) in {222, 333},
                    ):
                        with mock.patch.object(h_cycle, "_write_h_run_state") as write_state:
                            with mock.patch.object(h_cycle, "_read_latest_phase1_pilot_terminal_artifacts", return_value={"success_ok": "0"}):
                                with mock.patch.object(h_cycle, "_lock_probe_paths", return_value=[]):
                                    h_cycle._reconcile_stale_pilot_started_dead_owner()
                write_state.assert_not_called()
            finally:
                h_cycle.H_RUN_STATE_PATH = old_run_state
                h_cycle.H_RUNTIME_STATUS_PATH = old_runtime_status
                h_cycle.H_RUN_IN_PROGRESS_PATH = old_run_in_progress
                h_cycle.H_CYCLE_CURRENT_RUN_PATH = old_current_run

    def test_stale_pilot_reconcile_observe_only_when_current_run_marker_mismatches(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            run_id = "20260329T090243Z"
            run_state_path = root / "H_run_state.json"
            runtime_status_path = root / "H_runtime_status.json"
            run_in_progress_path = root / "H_run_in_progress.txt"
            current_run_path = root / "H_cycle_current_run_id.txt"
            run_state_path.write_text(
                (
                    "{"
                    f"\"run_id\":\"{run_id}\","
                    "\"state\":\"started\","
                    "\"owner_pid\":\"111\","
                    "\"publish_status\":\"not_started\","
                    "\"utc\":\"2026-03-29T08:30:00Z\""
                    "}\n"
                ),
                encoding="utf-8",
            )
            runtime_status_path.write_text(
                (
                    "{"
                    f"\"run_id\":\"{run_id}\","
                    "\"mode\":\"RUNNING\","
                    "\"stage\":\"child_wait\","
                    "\"pid\":\"222\","
                    "\"detail\":\"child_pid=333\""
                    "}\n"
                ),
                encoding="utf-8",
            )
            current_run_path.write_text("OTHER_RUN\n", encoding="utf-8")
            old_run_state = h_cycle.H_RUN_STATE_PATH
            old_runtime_status = h_cycle.H_RUNTIME_STATUS_PATH
            old_run_in_progress = h_cycle.H_RUN_IN_PROGRESS_PATH
            old_current_run = h_cycle.H_CYCLE_CURRENT_RUN_PATH
            try:
                h_cycle.H_RUN_STATE_PATH = run_state_path
                h_cycle.H_RUNTIME_STATUS_PATH = runtime_status_path
                h_cycle.H_RUN_IN_PROGRESS_PATH = run_in_progress_path
                h_cycle.H_CYCLE_CURRENT_RUN_PATH = current_run_path
                with mock.patch.object(h_cycle.os, "getpid", return_value=333):
                    with mock.patch.object(
                        h_cycle,
                        "_pid_alive",
                        side_effect=lambda pid: int(pid) in {222, 333},
                    ):
                        with mock.patch.object(h_cycle, "_write_h_run_state") as write_state:
                            with mock.patch.object(h_cycle, "_read_latest_phase1_pilot_terminal_artifacts", return_value={"success_ok": "0"}):
                                with mock.patch.object(h_cycle, "_lock_probe_paths", return_value=[]):
                                    h_cycle._reconcile_stale_pilot_started_dead_owner()
                write_state.assert_not_called()
            finally:
                h_cycle.H_RUN_STATE_PATH = old_run_state
                h_cycle.H_RUNTIME_STATUS_PATH = old_runtime_status
                h_cycle.H_RUN_IN_PROGRESS_PATH = old_run_in_progress
                h_cycle.H_CYCLE_CURRENT_RUN_PATH = old_current_run

    def test_classify_stale_owner_exit_evidence_matches_same_run_capture(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            run_id = "20260402T160531Z"
            owner_pid = 9884
            capture_path = root / "H_core_parent_exit_capture.9884.20260402T160356Z.json"
            capture_payload = {
                "authoritative_linkage": {
                    "attribution_possible": "1",
                    "attribution_level": "best_effort",
                    "security_process_audit": {
                        "attribution_possible": "1",
                        "candidates": [
                            {
                                "event_class": "process_exit",
                                "contains_target_pid": "1",
                                "record_id": "5975949",
                            }
                        ],
                    },
                },
                "observed_end": {
                    "run_id_current_end": run_id,
                    "runtime_status_end": {
                        "run_id": run_id,
                        "error": "RUN_STATE_NOT_TERMINAL",
                    },
                },
                "liveness": {"disappearance_utc": "2026-04-02T16:05:52Z"},
                "correlation": {
                    "security_4688_4689": {
                        "events": [
                            {
                                "record_id": "5975949",
                                "message_excerpt": (
                                    "A process has exited.\r\n"
                                    "Process Information:\r\n"
                                    "\tProcess ID:\t0x269C\r\n"
                                    "\tProcess Name:\tC:\\Users\\Luke\\AppData\\Local\\Programs\\Python\\Python312\\python.exe\r\n"
                                    "\tExit Status:\t0x0"
                                ),
                            }
                        ]
                    }
                },
            }
            capture_path.write_text(json.dumps(capture_payload) + "\n", encoding="utf-8")

            old_live_dir = h_cycle.H_LIVE_DIR
            try:
                h_cycle.H_LIVE_DIR = root
                evidence = h_cycle._classify_stale_owner_exit_evidence(run_id, owner_pid)
            finally:
                h_cycle.H_LIVE_DIR = old_live_dir

            self.assertEqual(evidence.get("usable"), "1")
            self.assertEqual(evidence.get("reason"), "owner_exit_capture_matched")
            self.assertEqual(evidence.get("record_id"), "5975949")
            self.assertEqual(evidence.get("exit_status"), "0x0")
            self.assertEqual(evidence.get("runtime_end_error"), "RUN_STATE_NOT_TERMINAL")

    def test_classify_stale_owner_exit_evidence_reads_utf16_capture_payload(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            run_id = "20260402T160531Z"
            owner_pid = 9884
            capture_path = root / "H_core_parent_exit_capture.9884.20260402T160356Z.json"
            capture_payload = {
                "authoritative_linkage": {
                    "attribution_possible": "1",
                    "security_process_audit": {
                        "attribution_possible": "1",
                        "candidates": [
                            {
                                "event_class": "process_exit",
                                "contains_target_pid": "1",
                                "record_id": "5975949",
                            }
                        ],
                    },
                },
                "observed_end": {
                    "run_id_current_end": run_id,
                    "runtime_status_end": {
                        "run_id": run_id,
                        "error": "RUN_STATE_NOT_TERMINAL",
                    },
                },
                "correlation": {
                    "security_4688_4689": {
                        "events": [
                            {
                                "record_id": "5975949",
                                "message_excerpt": "A process has exited. Process ID: 0x269C Exit Status: 0x0",
                            }
                        ]
                    }
                },
            }
            capture_path.write_text(json.dumps(capture_payload), encoding="utf-16")

            old_live_dir = h_cycle.H_LIVE_DIR
            try:
                h_cycle.H_LIVE_DIR = root
                evidence = h_cycle._classify_stale_owner_exit_evidence(run_id, owner_pid)
            finally:
                h_cycle.H_LIVE_DIR = old_live_dir

            self.assertEqual(evidence.get("usable"), "1")
            self.assertEqual(evidence.get("reason"), "owner_exit_capture_matched")
            self.assertEqual(evidence.get("record_id"), "5975949")
            self.assertEqual(evidence.get("exit_status"), "0x0")

    def test_stale_pilot_reconcile_terminalizes_stale_run_when_owner_exit_evidence_is_hard(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            run_id = "20260402T160531Z"
            run_state_path = root / "H_run_state.json"
            runtime_status_path = root / "H_runtime_status.json"
            run_in_progress_path = root / "H_run_in_progress.txt"
            current_run_path = root / "H_cycle_current_run_id.txt"

            run_state_path.write_text(
                (
                    "{"
                    f"\"run_id\":\"{run_id}\","
                    "\"state\":\"started\","
                    "\"owner_pid\":\"111\","
                    "\"publish_status\":\"not_started\","
                    "\"utc\":\"2026-04-02T16:05:31Z\""
                    "}\n"
                ),
                encoding="utf-8",
            )
            runtime_status_path.write_text("{}\n", encoding="utf-8")
            run_in_progress_path.write_text(f"{run_id}\n", encoding="utf-8")
            current_run_path.write_text(f"{run_id}\n", encoding="utf-8")

            old_run_state = h_cycle.H_RUN_STATE_PATH
            old_runtime_status = h_cycle.H_RUNTIME_STATUS_PATH
            old_run_in_progress = h_cycle.H_RUN_IN_PROGRESS_PATH
            old_current_run = h_cycle.H_CYCLE_CURRENT_RUN_PATH
            try:
                h_cycle.H_RUN_STATE_PATH = run_state_path
                h_cycle.H_RUNTIME_STATUS_PATH = runtime_status_path
                h_cycle.H_RUN_IN_PROGRESS_PATH = run_in_progress_path
                h_cycle.H_CYCLE_CURRENT_RUN_PATH = current_run_path
                with mock.patch.object(h_cycle, "_pid_alive", side_effect=lambda pid: int(pid) != 111):
                    with mock.patch.object(h_cycle, "_wrapper_child_wait_handover_active", return_value=(False, "runtime_status_missing")):
                        with mock.patch.object(h_cycle, "_read_latest_phase1_pilot_terminal_artifacts", return_value={"success_ok": "0"}):
                            with mock.patch.object(
                                h_cycle,
                                "_classify_stale_owner_exit_evidence",
                                return_value={
                                    "usable": "1",
                                    "reason": "owner_exit_capture_matched",
                                    "capture_path": "C:/tmp/H_core_parent_exit_capture.111.json",
                                    "record_id": "5975949",
                                    "exit_status": "0x0",
                                    "runtime_end_error": "RUN_STATE_NOT_TERMINAL",
                                },
                            ):
                                def _fake_write_h_run_state(
                                    state: str,
                                    *,
                                    run_id: str = "",
                                    stage: str = "",
                                    publish_status: str = "",
                                    failure_code: str = "",
                                    failure_detail: str = "",
                                ) -> None:
                                    run_state_path.write_text(
                                        json.dumps(
                                            {
                                                "run_id": run_id,
                                                "state": state,
                                                "utc": "2026-04-02T16:09:00Z",
                                                "owner_pid": "999",
                                                "stage": stage,
                                                "publish_status": publish_status,
                                                "failure_code": failure_code,
                                                "failure_detail": failure_detail,
                                            }
                                        )
                                        + "\n",
                                        encoding="utf-8",
                                    )

                                with mock.patch.object(h_cycle, "_write_h_run_state", side_effect=_fake_write_h_run_state) as write_state:
                                    with mock.patch.object(h_cycle, "_transition_h_worker_lifecycle") as write_worker:
                                        with mock.patch.object(h_cycle, "_transition_h_batch_state") as write_batch:
                                            with mock.patch.object(h_cycle, "_clear_run_in_progress") as clear_marker:
                                                with mock.patch.object(h_cycle, "_lock_probe_paths", return_value=[]):
                                                    outcome = h_cycle._reconcile_stale_pilot_started_dead_owner()
                self.assertEqual(outcome.get("applied"), "1")
                self.assertEqual(outcome.get("blocked"), "0")
                self.assertEqual(outcome.get("reason"), "stale_owner_hard_proof_terminalized_by_core")
                self.assertEqual(outcome.get("run_id"), run_id)
                self.assertEqual(outcome.get("failure_code"), "STALE_OWNER_EXIT_HARD_PROOF")
                write_state.assert_called_once()
                write_worker.assert_called_once()
                write_batch.assert_called_once()
                clear_marker.assert_called_once()
            finally:
                h_cycle.H_RUN_STATE_PATH = old_run_state
                h_cycle.H_RUNTIME_STATUS_PATH = old_runtime_status
                h_cycle.H_RUN_IN_PROGRESS_PATH = old_run_in_progress
                h_cycle.H_CYCLE_CURRENT_RUN_PATH = old_current_run

    def test_h_owner_pid_alive_rejects_reused_non_h_windows_pid(self) -> None:
        with mock.patch.object(h_cycle, "_pid_alive", return_value=True):
            with mock.patch.object(
                h_cycle,
                "_windows_process_identity",
                return_value={"name": "svchost.exe", "command_line": ""},
            ):
                self.assertFalse(h_cycle._h_owner_pid_alive(1320))

    def test_stale_pilot_reconcile_terminalizes_when_owner_pid_is_reused_by_non_h_process(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            run_id = "20260501T012125Z"
            run_state_path = root / "H_run_state.json"
            worker_path = root / "H_worker_lifecycle.json"
            run_in_progress_path = root / "H_run_in_progress.txt"
            current_run_path = root / "H_cycle_current_run_id.txt"
            stale_heartbeat = (datetime.now(timezone.utc) - timedelta(seconds=900)).strftime("%Y-%m-%dT%H:%M:%SZ")

            run_state_path.write_text(
                json.dumps(
                    {
                        "run_id": run_id,
                        "state": "started",
                        "owner_pid": "1320",
                        "publish_status": "not_started",
                        "utc": "2026-05-01T01:21:25Z",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            worker_path.write_text(
                json.dumps(
                    {
                        "run_id": run_id,
                        "state": "running",
                        "heartbeat_utc": stale_heartbeat,
                        "heartbeat_stale_after_seconds": "120",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            run_in_progress_path.write_text(f"{run_id}\n", encoding="utf-8")
            current_run_path.write_text(f"{run_id}\n", encoding="utf-8")

            old_run_state = h_cycle.H_RUN_STATE_PATH
            old_worker = h_cycle.H_WORKER_LIFECYCLE_PATH
            old_run_in_progress = h_cycle.H_RUN_IN_PROGRESS_PATH
            old_current_run = h_cycle.H_CYCLE_CURRENT_RUN_PATH
            try:
                h_cycle.H_RUN_STATE_PATH = run_state_path
                h_cycle.H_WORKER_LIFECYCLE_PATH = worker_path
                h_cycle.H_RUN_IN_PROGRESS_PATH = run_in_progress_path
                h_cycle.H_CYCLE_CURRENT_RUN_PATH = current_run_path
                with mock.patch.object(h_cycle, "_pid_alive", return_value=True):
                    with mock.patch.object(
                        h_cycle,
                        "_windows_process_identity",
                        return_value={"name": "svchost.exe", "command_line": ""},
                    ):
                        with mock.patch.object(
                            h_cycle,
                            "_wrapper_child_wait_handover_active",
                            return_value=(False, "runtime_status_missing"),
                        ):
                            def _fake_write_h_run_state(
                                state: str,
                                *,
                                run_id: str = "",
                                stage: str = "",
                                publish_status: str = "",
                                failure_code: str = "",
                                failure_detail: str = "",
                            ) -> None:
                                run_state_path.write_text(
                                    json.dumps(
                                        {
                                            "run_id": run_id,
                                            "state": state,
                                            "utc": "2026-05-01T09:05:00Z",
                                            "owner_pid": "1320",
                                            "stage": stage,
                                            "publish_status": publish_status,
                                            "failure_code": failure_code,
                                            "failure_detail": failure_detail,
                                        }
                                    )
                                    + "\n",
                                    encoding="utf-8",
                                )

                            with mock.patch.object(h_cycle, "_write_h_run_state", side_effect=_fake_write_h_run_state) as write_state:
                                with mock.patch.object(h_cycle, "_transition_h_worker_lifecycle") as write_worker:
                                    with mock.patch.object(h_cycle, "_transition_h_batch_state") as write_batch:
                                        with mock.patch.object(h_cycle, "_clear_run_in_progress") as clear_marker:
                                            outcome = h_cycle._reconcile_stale_pilot_started_dead_owner()

                self.assertEqual(outcome.get("applied"), "1")
                self.assertEqual(outcome.get("blocked"), "0")
                self.assertEqual(outcome.get("reason"), "stale_owner_identity_terminalized_by_core")
                self.assertEqual(outcome.get("failure_code"), "STALE_OWNER_IDENTITY_MISMATCH")
                write_state.assert_called_once()
                write_worker.assert_called_once()
                write_batch.assert_called_once()
                clear_marker.assert_called_once()
            finally:
                h_cycle.H_RUN_STATE_PATH = old_run_state
                h_cycle.H_WORKER_LIFECYCLE_PATH = old_worker
                h_cycle.H_RUN_IN_PROGRESS_PATH = old_run_in_progress
                h_cycle.H_CYCLE_CURRENT_RUN_PATH = old_current_run

    def test_stale_pilot_reconcile_terminalizes_stale_run_when_pilot_terminal_failure_is_hard(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            run_id = "20260402T191722Z"
            run_state_path = root / "H_run_state.json"
            runtime_status_path = root / "H_runtime_status.json"
            run_in_progress_path = root / "H_run_in_progress.txt"
            current_run_path = root / "H_cycle_current_run_id.txt"

            run_state_path.write_text(
                (
                    "{"
                    f"\"run_id\":\"{run_id}\","
                    "\"state\":\"pilot_started\","
                    "\"owner_pid\":\"28000\","
                    "\"publish_status\":\"not_started\","
                    "\"utc\":\"2026-04-02T19:18:45Z\""
                    "}\n"
                ),
                encoding="utf-8",
            )
            runtime_status_path.write_text("{}\n", encoding="utf-8")
            run_in_progress_path.write_text(f"{run_id}\n", encoding="utf-8")
            current_run_path.write_text(f"{run_id}\n", encoding="utf-8")

            old_run_state = h_cycle.H_RUN_STATE_PATH
            old_runtime_status = h_cycle.H_RUNTIME_STATUS_PATH
            old_run_in_progress = h_cycle.H_RUN_IN_PROGRESS_PATH
            old_current_run = h_cycle.H_CYCLE_CURRENT_RUN_PATH
            try:
                h_cycle.H_RUN_STATE_PATH = run_state_path
                h_cycle.H_RUNTIME_STATUS_PATH = runtime_status_path
                h_cycle.H_RUN_IN_PROGRESS_PATH = run_in_progress_path
                h_cycle.H_CYCLE_CURRENT_RUN_PATH = current_run_path
                with mock.patch.object(h_cycle, "_pid_alive", side_effect=lambda pid: int(pid) != 28000):
                    with mock.patch.object(h_cycle, "_wrapper_child_wait_handover_active", return_value=(False, "runtime_status_missing")):
                        with mock.patch.object(
                            h_cycle,
                            "_read_latest_phase1_pilot_terminal_artifacts",
                            return_value={
                                "marker_status": "failed",
                                "result_exists": "1",
                                "marker_path": "C:/tmp/phase1_pilot_step.complete.RID.json",
                                "result_path": "C:/tmp/phase1_pilot_step.result.RID.json",
                                "result_terminal_reason": "parent_cycle_dead_before_pilot_terminal",
                                "success_ok": "0",
                            },
                        ):
                            with mock.patch.object(
                                h_cycle,
                                "_classify_stale_owner_exit_evidence",
                                return_value={"usable": "0", "reason": "missing_owner_exit_capture"},
                            ):
                                def _fake_write_h_run_state(
                                    state: str,
                                    *,
                                    run_id: str = "",
                                    stage: str = "",
                                    publish_status: str = "",
                                    failure_code: str = "",
                                    failure_detail: str = "",
                                ) -> None:
                                    run_state_path.write_text(
                                        json.dumps(
                                            {
                                                "run_id": run_id,
                                                "state": state,
                                                "utc": "2026-04-02T19:22:00Z",
                                                "owner_pid": "999",
                                                "stage": stage,
                                                "publish_status": publish_status,
                                                "failure_code": failure_code,
                                                "failure_detail": failure_detail,
                                            }
                                        )
                                        + "\n",
                                        encoding="utf-8",
                                    )

                                with mock.patch.object(h_cycle, "_write_h_run_state", side_effect=_fake_write_h_run_state) as write_state:
                                    with mock.patch.object(h_cycle, "_transition_h_worker_lifecycle") as write_worker:
                                        with mock.patch.object(h_cycle, "_transition_h_batch_state") as write_batch:
                                            with mock.patch.object(h_cycle, "_clear_run_in_progress") as clear_marker:
                                                with mock.patch.object(h_cycle, "_lock_probe_paths", return_value=[]):
                                                    outcome = h_cycle._reconcile_stale_pilot_started_dead_owner()
                self.assertEqual(outcome.get("applied"), "1")
                self.assertEqual(outcome.get("blocked"), "0")
                self.assertEqual(outcome.get("reason"), "stale_pilot_hard_proof_terminalized_by_core")
                self.assertEqual(outcome.get("run_id"), run_id)
                self.assertEqual(outcome.get("failure_code"), "STALE_PILOT_TERMINAL_FAILED_HARD_PROOF")
                write_state.assert_called_once()
                write_worker.assert_called_once()
                write_batch.assert_called_once()
                clear_marker.assert_called_once()
            finally:
                h_cycle.H_RUN_STATE_PATH = old_run_state
                h_cycle.H_RUNTIME_STATUS_PATH = old_runtime_status
                h_cycle.H_RUN_IN_PROGRESS_PATH = old_run_in_progress
                h_cycle.H_CYCLE_CURRENT_RUN_PATH = old_current_run

    def test_stale_pilot_reconcile_blocks_startup_without_hard_owner_exit_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            run_id = "20260402T160531Z"
            run_state_path = root / "H_run_state.json"
            runtime_status_path = root / "H_runtime_status.json"
            run_in_progress_path = root / "H_run_in_progress.txt"
            current_run_path = root / "H_cycle_current_run_id.txt"

            run_state_path.write_text(
                (
                    "{"
                    f"\"run_id\":\"{run_id}\","
                    "\"state\":\"started\","
                    "\"owner_pid\":\"9884\","
                    "\"publish_status\":\"not_started\","
                    "\"utc\":\"2026-04-02T16:05:31Z\""
                    "}\n"
                ),
                encoding="utf-8",
            )
            runtime_status_path.write_text("{}\n", encoding="utf-8")
            run_in_progress_path.write_text(f"{run_id}\n", encoding="utf-8")
            current_run_path.write_text(f"{run_id}\n", encoding="utf-8")

            old_run_state = h_cycle.H_RUN_STATE_PATH
            old_runtime_status = h_cycle.H_RUNTIME_STATUS_PATH
            old_run_in_progress = h_cycle.H_RUN_IN_PROGRESS_PATH
            old_current_run = h_cycle.H_CYCLE_CURRENT_RUN_PATH
            try:
                h_cycle.H_RUN_STATE_PATH = run_state_path
                h_cycle.H_RUNTIME_STATUS_PATH = runtime_status_path
                h_cycle.H_RUN_IN_PROGRESS_PATH = run_in_progress_path
                h_cycle.H_CYCLE_CURRENT_RUN_PATH = current_run_path
                with mock.patch.object(h_cycle, "_pid_alive", side_effect=lambda pid: int(pid) != 9884):
                    with mock.patch.object(h_cycle, "_wrapper_child_wait_handover_active", return_value=(False, "runtime_status_missing")):
                        with mock.patch.object(h_cycle, "_read_latest_phase1_pilot_terminal_artifacts", return_value={"success_ok": "0"}):
                            with mock.patch.object(
                                h_cycle,
                                "_classify_stale_owner_exit_evidence",
                                return_value={
                                    "usable": "0",
                                    "reason": "missing_owner_exit_capture",
                                },
                            ):
                                with mock.patch.object(h_cycle, "_write_h_run_state") as write_state:
                                    with mock.patch.object(h_cycle, "_transition_h_worker_lifecycle") as write_worker:
                                        with mock.patch.object(h_cycle, "_transition_h_batch_state") as write_batch:
                                            with mock.patch.object(h_cycle, "_clear_run_in_progress") as clear_marker:
                                                with mock.patch.object(h_cycle, "_lock_probe_paths", return_value=[]):
                                                    outcome = h_cycle._reconcile_stale_pilot_started_dead_owner()
                self.assertEqual(outcome.get("blocked"), "1")
                self.assertEqual(outcome.get("reason"), "stale_owner_nonterminal_without_hard_proof")
                self.assertEqual(outcome.get("run_id"), run_id)
                write_state.assert_not_called()
                write_worker.assert_not_called()
                write_batch.assert_not_called()
                clear_marker.assert_not_called()
            finally:
                h_cycle.H_RUN_STATE_PATH = old_run_state
                h_cycle.H_RUNTIME_STATUS_PATH = old_runtime_status
                h_cycle.H_RUN_IN_PROGRESS_PATH = old_run_in_progress
                h_cycle.H_CYCLE_CURRENT_RUN_PATH = old_current_run

    def test_stale_pilot_reconcile_skips_handover_defer_for_terminal_failed_state(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            run_id = "20260402T160531Z"
            run_state_utc = (datetime.now(timezone.utc) - timedelta(seconds=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
            run_state_path = root / "H_run_state.json"
            runtime_status_path = root / "H_runtime_status.json"
            run_in_progress_path = root / "H_run_in_progress.txt"
            current_run_path = root / "H_cycle_current_run_id.txt"
            run_state_path.write_text(
                (
                    "{"
                    f"\"run_id\":\"{run_id}\","
                    "\"state\":\"failed\","
                    "\"owner_pid\":\"9884\","
                    "\"publish_status\":\"not_started\","
                    f"\"utc\":\"{run_state_utc}\""
                    "}\n"
                ),
                encoding="utf-8",
            )
            runtime_status_path.write_text(
                (
                    "{"
                    f"\"run_id\":\"{run_id}\","
                    "\"mode\":\"RUNNING\","
                    "\"stage\":\"child_wait\","
                    "\"pid\":\"222\","
                    "\"detail\":\"child_pid=333\""
                    "}\n"
                ),
                encoding="utf-8",
            )
            run_in_progress_path.write_text(f"{run_id}\n", encoding="utf-8")
            current_run_path.write_text(f"{run_id}\n", encoding="utf-8")

            old_run_state = h_cycle.H_RUN_STATE_PATH
            old_runtime_status = h_cycle.H_RUNTIME_STATUS_PATH
            old_run_in_progress = h_cycle.H_RUN_IN_PROGRESS_PATH
            old_current_run = h_cycle.H_CYCLE_CURRENT_RUN_PATH
            try:
                h_cycle.H_RUN_STATE_PATH = run_state_path
                h_cycle.H_RUNTIME_STATUS_PATH = runtime_status_path
                h_cycle.H_RUN_IN_PROGRESS_PATH = run_in_progress_path
                h_cycle.H_CYCLE_CURRENT_RUN_PATH = current_run_path
                with mock.patch.object(h_cycle, "_wrapper_child_wait_handover_active") as handover_active:
                    outcome = h_cycle._reconcile_stale_pilot_started_dead_owner()
                self.assertEqual(outcome.get("blocked"), "0")
                self.assertEqual(outcome.get("reason"), "already_terminal_state")
                handover_active.assert_not_called()
            finally:
                h_cycle.H_RUN_STATE_PATH = old_run_state
                h_cycle.H_RUNTIME_STATUS_PATH = old_runtime_status
                h_cycle.H_RUN_IN_PROGRESS_PATH = old_run_in_progress
                h_cycle.H_CYCLE_CURRENT_RUN_PATH = old_current_run

    def test_guard_marks_terminal_on_stale_heartbeat(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            worker_path = root / "H_worker_lifecycle.json"
            worker_path.write_text(
                (
                    '{'
                    '"run_id":"20260320T130000Z",'
                    '"state":"running",'
                    '"heartbeat_utc":"2000-01-01T00:00:00Z"'
                    '}\n'
                ),
                encoding="utf-8",
            )
            before = h_guard._read_h_worker_lifecycle(worker_path)
            age = h_guard._worker_heartbeat_age_seconds(before)
            self.assertIsNotNone(age)
            self.assertGreater(age or 0.0, 120.0)
            after = h_guard._mark_worker_terminal(
                worker_path,
                run_id="20260320T130000Z",
                state="abandoned",
                reason_code="WORKER_HEARTBEAT_STALE",
                reason_detail="heartbeat timeout",
            )
            self.assertEqual(after.get("state"), "abandoned")
            self.assertEqual(after.get("terminal_outcome"), "abandoned")
            self.assertEqual(after.get("reason_code"), "WORKER_HEARTBEAT_STALE")

    def test_no_publish_terminal_ok_is_disabled_in_wrapper(self) -> None:
        with mock.patch.dict(h_guard.os.environ, {"H_ALLOW_NO_PUBLISH_TERMINAL_OK": "0"}, clear=False):
            self.assertFalse(h_guard._allow_no_publish_terminal_ok("0"))

    def test_no_publish_terminal_ok_is_disabled_even_with_env_opt_in(self) -> None:
        with mock.patch.dict(h_guard.os.environ, {"H_ALLOW_NO_PUBLISH_TERMINAL_OK": "1"}, clear=False):
            self.assertFalse(h_guard._allow_no_publish_terminal_ok("1"))
            self.assertFalse(h_guard._allow_no_publish_terminal_ok("0"))

    def test_parent_terminal_handoff_entered_grace_uses_parent_heartbeat_contract(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            handoff_path = Path(td) / "phase1_pilot_parent_handoff.RID.123.json"
            handoff_path.write_text(
                h110.json.dumps(
                    {
                        "run_id": "RID",
                        "parent_pid": "123",
                        "status": "pilot_wait_entered",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            now_ts = time.time()
            os.utime(handoff_path, (now_ts, now_ts))

            with mock.patch.object(h110, "PHASE1_PARENT_HANDOFF_PATH", handoff_path):
                with mock.patch.dict(
                    h110.os.environ,
                    {"H_PHASE1_PARENT_HANDOFF_HEARTBEAT_SECONDS": "30"},
                    clear=False,
                ):
                    active, reason = h110._parent_terminal_handoff_grace_active(
                        run_id="RID",
                        parent_cycle_pid=123,
                    )
                    self.assertTrue(active)
                    self.assertTrue(reason.startswith("handoff_status=pilot_wait_entered:"))

                    stale_ts = time.time() - 45.0
                    os.utime(handoff_path, (stale_ts, stale_ts))
                    active_stale, reason_stale = h110._parent_terminal_handoff_grace_active(
                        run_id="RID",
                        parent_cycle_pid=123,
                    )
                    self.assertFalse(active_stale)
                    self.assertTrue(reason_stale.startswith("handoff_grace_expired:"))

    def test_parent_terminal_handoff_entered_grace_override_is_not_capped(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            handoff_path = Path(td) / "phase1_pilot_parent_handoff.RID.123.json"
            handoff_path.write_text(
                h110.json.dumps(
                    {
                        "run_id": "RID",
                        "parent_pid": "123",
                        "status": "pilot_wait_entered",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            stale_ts = time.time() - 45.0
            os.utime(handoff_path, (stale_ts, stale_ts))
            with mock.patch.object(h110, "PHASE1_PARENT_HANDOFF_PATH", handoff_path):
                with mock.patch.dict(
                    h110.os.environ,
                    {"H110_PARENT_TERMINAL_HANDOFF_WAIT_ENTER_GRACE_SECONDS": "9999"},
                    clear=False,
                ):
                    active, reason = h110._parent_terminal_handoff_grace_active(
                        run_id="RID",
                        parent_cycle_pid=123,
                    )
                    self.assertTrue(active)
                    self.assertIn("grace_seconds=", reason)

    def test_parent_terminal_handoff_heartbeat_status_is_grace_eligible(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            handoff_path = Path(td) / "phase1_pilot_parent_handoff.RID.123.json"
            handoff_path.write_text(
                h110.json.dumps(
                    {
                        "run_id": "RID",
                        "parent_pid": "123",
                        "status": "pilot_wait_heartbeat",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            now_ts = time.time()
            os.utime(handoff_path, (now_ts, now_ts))
            with mock.patch.object(h110, "PHASE1_PARENT_HANDOFF_PATH", handoff_path):
                active, reason = h110._parent_terminal_handoff_grace_active(
                    run_id="RID",
                    parent_cycle_pid=123,
                )
                self.assertTrue(active)
                self.assertTrue(reason.startswith("handoff_status=pilot_wait_heartbeat:"))


if __name__ == "__main__":
    unittest.main()
