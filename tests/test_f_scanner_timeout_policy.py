from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F.f_scanner_timeout_policy import (
    KNOWN_FAIL_AND_RETRY_CODES,
    default_timeout_policy_df,
    read_timeout_policy_df,
    resolve_timeout_policy_row,
    should_skip_for_timeout_policy,
    timeout_policy_health_rows,
    timeout_policy_path,
    timeout_until_utc_for_policy,
)


def test_default_policy_file_can_be_created_and_read(tmp_path: Path) -> None:
    policy_path = timeout_policy_path(tmp_path)
    assert not policy_path.exists()

    policy = read_timeout_policy_df(
        root=tmp_path,
        create_if_missing=True,
        observed_utc="2026-05-01T10:00:00Z",
    )

    assert policy_path.exists()
    assert len(policy.index) == len(KNOWN_FAIL_AND_RETRY_CODES)
    assert set(policy["fail_code"].tolist()) == set(KNOWN_FAIL_AND_RETRY_CODES)
    assert policy.loc[policy["fail_code"] == "NOASIN", "timeout_mode"].iloc[0] == "fixed_days"


def test_every_known_fail_and_retry_code_has_policy_row() -> None:
    policy = default_timeout_policy_df("2026-05-01T10:00:00Z")
    counts = policy["fail_code"].value_counts().to_dict()

    for code in KNOWN_FAIL_AND_RETRY_CODES:
        assert counts.get(code) == 1


def test_default_policy_uses_approved_values() -> None:
    policy = default_timeout_policy_df("2026-05-01T10:00:00Z").set_index("fail_code")

    assert policy.loc["NOASIN", "timeout_days"] == "90"
    assert policy.loc["OVER50K", "timeout_days"] == "90"
    assert policy.loc["HAZMATFAIL", "timeout_days"] == "365"
    assert policy.loc["NOCOST", "timeout_mode"] == "until_cost_changes"
    assert policy.loc["NOCOST", "max_timeout_days"] == "90"
    assert policy.loc["NOCOST", "cost_change_resets_flag"] == "1"
    assert policy.loc["ROIFAIL", "max_timeout_days"] == "90"
    assert policy.loc["LOWROI", "max_timeout_days"] == "60"
    assert policy.loc["SCRAPEFAIL", "timeout_days"] == "30"
    assert policy.loc["SELLERHISTORYFAIL", "timeout_days"] == "180"
    assert policy.loc["PRICEHISTORYFAIL", "timeout_days"] == "180"
    assert policy.loc["RESCAN", "enabled"] == "1"
    assert policy.loc["RESCAN", "timeout_mode"] == "disabled"
    assert policy.loc["RESCAN", "timeout_days"] == ""
    assert policy.loc["RESCAN", "max_timeout_days"] == "0"
    assert policy.loc["FAIL", "timeout_days"] == "90"


def test_rescan_policy_never_creates_timeout_skip() -> None:
    policy = default_timeout_policy_df("2026-05-01T10:00:00Z")

    timeout_until = timeout_until_utc_for_policy(
        observed_utc="2026-05-01T00:00:00Z",
        fail_code="RESCAN",
        policy_df=policy,
    )
    decision = should_skip_for_timeout_policy(
        fail_code="RESCAN",
        policy_df=policy,
        last_scanned_at_utc="2026-05-01T00:00:00Z",
        observed_utc="2026-05-02T00:00:00Z",
    )

    assert timeout_until == ""
    assert decision.skip is False
    assert decision.reason == "policy_disabled"


def test_unknown_fail_code_falls_back_to_fail_and_warns(tmp_path: Path) -> None:
    policy = default_timeout_policy_df("2026-05-01T10:00:00Z")
    row, effective_code, fallback_used = resolve_timeout_policy_row(policy, "ODDFAIL")
    assert effective_code == "FAIL"
    assert fallback_used is True
    assert row["fail_code"] == "FAIL"

    health = timeout_policy_health_rows(
        policy_df=policy,
        policy_exists=True,
        policy_path=timeout_policy_path(tmp_path),
        screening_state_df=pd.DataFrame([{"fail_code": "ODDFAIL"}]),
        observed_utc="2026-05-01T10:00:00Z",
    )
    unknown_row = next(row for row in health if row["check"] == "f_scanner_timeout_policy_unknown_fail_codes")
    assert unknown_row["status"] == "warn"
    assert unknown_row["value"] == "1"
    assert "fallback_FAIL_for=ODDFAIL" in unknown_row["notes"]


def test_fixed_days_calculates_timeout_until_utc() -> None:
    policy = default_timeout_policy_df("2026-05-01T10:00:00Z")
    policy.loc[policy["fail_code"] == "FAIL", "timeout_days"] = "2"

    timeout_until = timeout_until_utc_for_policy(
        observed_utc="2026-05-01T00:00:00Z",
        fail_code="FAIL",
        policy_df=policy,
    )

    assert timeout_until == "2026-05-03T00:00:00Z"


def test_until_cost_changes_skips_only_when_cost_is_unchanged() -> None:
    policy = default_timeout_policy_df("2026-05-01T10:00:00Z")
    mask = policy["fail_code"] == "NOCOST"
    policy.loc[mask, "timeout_mode"] = "until_cost_changes"
    policy.loc[mask, "timeout_days"] = ""
    policy.loc[mask, "max_timeout_days"] = "30"
    policy.loc[mask, "cost_change_resets_flag"] = "1"

    unchanged = should_skip_for_timeout_policy(
        fail_code="NOCOST",
        policy_df=policy,
        last_scanned_at_utc="2026-05-01T00:00:00Z",
        observed_utc="2026-05-05T00:00:00Z",
        previous_unit_cost="5.00",
        current_unit_cost="5.00",
    )
    changed = should_skip_for_timeout_policy(
        fail_code="NOCOST",
        policy_df=policy,
        last_scanned_at_utc="2026-05-01T00:00:00Z",
        observed_utc="2026-05-05T00:00:00Z",
        previous_unit_cost="5.00",
        current_unit_cost="4.50",
    )

    assert unchanged.skip is True
    assert unchanged.reason == "timeout_active"
    assert changed.skip is False
    assert changed.reason == "cost_changed_reset"


def test_until_source_changes_resets_when_source_hash_changes() -> None:
    policy = default_timeout_policy_df("2026-05-01T10:00:00Z")
    mask = policy["fail_code"] == "NOASIN"
    policy.loc[mask, "timeout_mode"] = "until_source_changes"
    policy.loc[mask, "timeout_days"] = ""
    policy.loc[mask, "max_timeout_days"] = "30"
    policy.loc[mask, "source_change_resets_flag"] = "1"

    changed = should_skip_for_timeout_policy(
        fail_code="NOASIN",
        policy_df=policy,
        last_scanned_at_utc="2026-05-01T00:00:00Z",
        observed_utc="2026-05-05T00:00:00Z",
        previous_source_hash="old",
        current_source_hash="new",
    )

    assert changed.skip is False
    assert changed.reason == "source_changed_reset"


def test_manual_review_blocks_automatic_rescan() -> None:
    policy = default_timeout_policy_df("2026-05-01T10:00:00Z")
    mask = policy["fail_code"] == "BRANDFAIL"
    policy.loc[mask, "timeout_mode"] = "manual_review"
    policy.loc[mask, "manual_review_required_flag"] = "1"

    decision = should_skip_for_timeout_policy(
        fail_code="BRANDFAIL",
        policy_df=policy,
        last_scanned_at_utc="2026-05-01T00:00:00Z",
        observed_utc="2026-06-01T00:00:00Z",
    )

    assert decision.skip is True
    assert decision.reason == "manual_review_required"
