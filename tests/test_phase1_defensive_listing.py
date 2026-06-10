from pathlib import Path

from scripts.phase1 import phase1_defensive_listing


def _write_config(path: Path, rows: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "sku,asin,enabled,mode,live_write_enabled,pressure_days,undercut_gbp,after_pressure_action,reset_after_absent_hours,min_margin_guard,notes\n"
        + "\n".join(rows)
        + "\n",
        encoding="utf-8",
    )


def test_defensive_listing_config_accepts_b06_and_rejects_unsafe_rows(tmp_path: Path) -> None:
    path = tmp_path / "h_defensive_listing_protection.csv"
    _write_config(
        path,
        [
            "6V-EEC1-2S9Z,B06WW79DX5,1,pressure_then_match,0,30,0.01,match,24,0.00,ok",
            "BAD1,ASINBAD,1,pressure_then_match,0,30,0.50,match,24,0.00,too aggressive",
            "BAD2,ASINBAD2,1,pressure_then_match,1,30,0.01,match,24,0.00,live outside allowlist",
            "BAD3,ASINBAD3,1,unknown,0,30,0.01,match,24,0.00,bad mode",
        ],
    )

    rules = phase1_defensive_listing.load_defensive_listing_rules(path)

    assert set(rules) == {"6V-EEC1-2S9Z"}
    assert rules["6V-EEC1-2S9Z"].mode == "pressure_then_match"
    assert rules["6V-EEC1-2S9Z"].live_write_enabled is False


def test_defensive_listing_stale_or_unproven_market_holds(tmp_path: Path) -> None:
    path = tmp_path / "h_defensive_listing_protection.csv"
    _write_config(path, ["6V-EEC1-2S9Z,B06WW79DX5,1,pressure_then_match,0,30,0.01,match,24,0.00,ok"])
    rule = phase1_defensive_listing.active_rule_for_sku(path, "6V-EEC1-2S9Z")
    assert rule is not None

    result = phase1_defensive_listing.evaluate_defensive_listing(
        rule=rule,
        memory={},
        event_ts_utc="2026-06-04T10:00:00Z",
        buy_box_state="LOST_TO_COMPETITOR",
        seller_count=1,
        lowest_rival_price_gbp="6.97",
        current_price_gbp="6.98",
        hard_floor_gbp="5.90",
        final_ceiling_gbp="10.64",
        max_step_down_gbp="0.20",
        max_step_up_gbp="0.20",
        observable=False,
        we_present=True,
    )

    assert result.state == "DEFENSIVE_LISTING_HOLD"
    assert result.override_decision is True
    assert result.write_required is False
    assert "DEFENSIVE_LISTING_HOLD_STALE_OR_UNPROVEN_MARKET" in result.reason_codes


def test_defensive_listing_fresh_rival_uses_one_p_undercut_inside_floor_and_ceiling(tmp_path: Path) -> None:
    path = tmp_path / "h_defensive_listing_protection.csv"
    _write_config(path, ["6V-EEC1-2S9Z,B06WW79DX5,1,pressure_then_match,0,30,0.01,match,24,0.00,ok"])
    rule = phase1_defensive_listing.active_rule_for_sku(path, "6V-EEC1-2S9Z")
    assert rule is not None

    result = phase1_defensive_listing.evaluate_defensive_listing(
        rule=rule,
        memory={},
        event_ts_utc="2026-06-04T10:00:00Z",
        buy_box_state="LOST_TO_COMPETITOR",
        seller_count=1,
        lowest_rival_price_gbp="6.97",
        current_price_gbp="6.98",
        hard_floor_gbp="5.90",
        final_ceiling_gbp="10.64",
        max_step_down_gbp="0.20",
        max_step_up_gbp="0.20",
        observable=True,
        we_present=True,
    )

    assert result.state == "DEFENSIVE_LISTING_BALANCED_DEFEND"
    assert result.override_decision is True
    assert result.target_price_gbp == "6.96"
    assert result.phase == "pressure_undercut"
    assert result.write_required is True
    assert result.live_write_enabled is False


def test_defensive_listing_repeated_failed_defends_do_not_switch_to_slow_ladder(tmp_path: Path) -> None:
    path = tmp_path / "h_defensive_listing_protection.csv"
    _write_config(path, ["6V-EEC1-2S9Z,B06WW79DX5,1,pressure_then_match,0,30,0.01,match,24,0.00,ok"])
    rule = phase1_defensive_listing.active_rule_for_sku(path, "6V-EEC1-2S9Z")
    assert rule is not None

    result = phase1_defensive_listing.evaluate_defensive_listing(
        rule=rule,
        memory={"failed_defend_count": "3", "last_action": "DEFENSIVE_LISTING_BALANCED_DEFEND"},
        event_ts_utc="2026-06-04T10:00:00Z",
        buy_box_state="LOST_TO_COMPETITOR",
        seller_count=1,
        lowest_rival_price_gbp="6.97",
        current_price_gbp="6.98",
        hard_floor_gbp="5.90",
        final_ceiling_gbp="10.64",
        max_step_down_gbp="0.20",
        max_step_up_gbp="0.20",
        observable=True,
        we_present=True,
    )

    assert result.state == "DEFENSIVE_LISTING_BALANCED_DEFEND"
    assert result.override_decision is True
    assert result.write_required is True
    assert result.phase == "pressure_undercut"
    assert "DEFENSIVE_LISTING_SLOW_SHARE_HOLD" not in result.reason_codes


def test_defensive_listing_has_no_daily_write_cap(tmp_path: Path) -> None:
    path = tmp_path / "h_defensive_listing_protection.csv"
    _write_config(path, ["6V-EEC1-2S9Z,B06WW79DX5,1,pressure_then_match,1,30,0.01,match,24,0.00,ok"])
    rule = phase1_defensive_listing.active_rule_for_sku(path, "6V-EEC1-2S9Z")
    assert rule is not None

    result = phase1_defensive_listing.evaluate_defensive_listing(
        rule=rule,
        memory={"writes_date": "2026-06-04", "writes_today": "99"},
        event_ts_utc="2026-06-04T10:00:00Z",
        buy_box_state="LOST_TO_COMPETITOR",
        seller_count=1,
        lowest_rival_price_gbp="6.98",
        current_price_gbp="7.17",
        hard_floor_gbp="5.90",
        final_ceiling_gbp="10.64",
        max_step_down_gbp="0.20",
        max_step_up_gbp="0.20",
        observable=True,
        we_present=True,
    )

    assert result.phase == "pressure_undercut"
    assert result.target_price_gbp == "6.97"
    assert result.write_required is True
    assert "DEFENSIVE_LISTING_DAILY_WRITE_LIMIT_HOLD" not in result.reason_codes


def test_defensive_listing_rival_absence_returns_to_normal_h_control(tmp_path: Path) -> None:
    path = tmp_path / "h_defensive_listing_protection.csv"
    _write_config(path, ["6V-EEC1-2S9Z,B06WW79DX5,1,pressure_then_match,0,30,0.01,match,24,0.00,ok"])
    rule = phase1_defensive_listing.active_rule_for_sku(path, "6V-EEC1-2S9Z")
    assert rule is not None

    result = phase1_defensive_listing.evaluate_defensive_listing(
        rule=rule,
        memory={"last_seen_rival_utc": "2026-06-03T09:00:00Z"},
        event_ts_utc="2026-06-04T10:00:00Z",
        buy_box_state="NORMAL",
        seller_count=0,
        lowest_rival_price_gbp="",
        current_price_gbp="6.98",
        hard_floor_gbp="5.90",
        final_ceiling_gbp="7.05",
        max_step_down_gbp="0.20",
        max_step_up_gbp="0.20",
        observable=True,
        we_present=True,
    )

    assert result.state == "DEFENSIVE_LISTING_NOT_TRIGGERED"
    assert result.phase == "normal_h_control"
    assert result.override_decision is False
    assert result.target_price_gbp == ""
    assert result.write_required is False
    assert "DEFENSIVE_LISTING_RIVAL_ABSENT_NORMAL_H_CONTROL" in result.reason_codes


def test_defensive_listing_rival_present_keeps_single_strategy_control(tmp_path: Path) -> None:
    path = tmp_path / "h_defensive_listing_protection.csv"
    _write_config(path, ["6V-EEC1-2S9Z,B06WW79DX5,1,pressure_then_match,0,30,0.01,match,24,0.00,ok"])
    rule = phase1_defensive_listing.active_rule_for_sku(path, "6V-EEC1-2S9Z")
    assert rule is not None

    equal_result = phase1_defensive_listing.evaluate_defensive_listing(
        rule=rule,
        memory={},
        event_ts_utc="2026-06-04T10:00:00Z",
        buy_box_state="NORMAL",
        seller_count=1,
        lowest_rival_price_gbp="6.98",
        current_price_gbp="6.98",
        hard_floor_gbp="5.90",
        final_ceiling_gbp="10.64",
        max_step_down_gbp="0.20",
        max_step_up_gbp="0.20",
        observable=True,
        we_present=True,
    )

    assert equal_result.state == "DEFENSIVE_LISTING_BALANCED_DEFEND"
    assert equal_result.phase == "pressure_undercut"
    assert equal_result.override_decision is True
    assert equal_result.target_price_gbp == "6.97"
    assert equal_result.write_required is True

    hold_result = phase1_defensive_listing.evaluate_defensive_listing(
        rule=rule,
        memory={},
        event_ts_utc="2026-06-04T10:00:00Z",
        buy_box_state="NORMAL",
        seller_count=1,
        lowest_rival_price_gbp="6.98",
        current_price_gbp="6.97",
        hard_floor_gbp="5.90",
        final_ceiling_gbp="10.64",
        max_step_down_gbp="0.20",
        max_step_up_gbp="0.20",
        observable=True,
        we_present=True,
    )

    assert hold_result.state == "DEFENSIVE_LISTING_HOLD"
    assert hold_result.phase == "pressure_hold"
    assert hold_result.override_decision is True
    assert hold_result.target_price_gbp == "6.97"
    assert hold_result.write_required is False
    assert "DEFENSIVE_LISTING_SINGLE_STRATEGY_OWNS_RIVAL_PRESENT" in hold_result.reason_codes

    above_result = phase1_defensive_listing.evaluate_defensive_listing(
        rule=rule,
        memory={},
        event_ts_utc="2026-06-04T10:00:00Z",
        buy_box_state="NORMAL",
        seller_count=1,
        lowest_rival_price_gbp="7.50",
        current_price_gbp="6.98",
        hard_floor_gbp="5.90",
        final_ceiling_gbp="10.64",
        max_step_down_gbp="0.20",
        max_step_up_gbp="0.20",
        observable=True,
        we_present=True,
    )

    assert above_result.state == "DEFENSIVE_LISTING_HOLD"
    assert above_result.phase == "pressure_hold"
    assert above_result.override_decision is True
    assert above_result.target_price_gbp == "6.98"
    assert above_result.write_required is False
    assert "DEFENSIVE_LISTING_SINGLE_STRATEGY_OWNS_RIVAL_PRESENT" in above_result.reason_codes


def test_defensive_listing_after_pressure_window_matches_rival(tmp_path: Path) -> None:
    path = tmp_path / "h_defensive_listing_protection.csv"
    _write_config(path, ["6V-EEC1-2S9Z,B06WW79DX5,1,pressure_then_match,0,30,0.01,match,24,0.00,ok"])
    rule = phase1_defensive_listing.active_rule_for_sku(path, "6V-EEC1-2S9Z")
    assert rule is not None

    result = phase1_defensive_listing.evaluate_defensive_listing(
        rule=rule,
        memory={"campaign_started_utc": "2026-05-01T10:00:00Z"},
        event_ts_utc="2026-06-04T10:00:00Z",
        buy_box_state="LOST_TO_COMPETITOR",
        seller_count=1,
        lowest_rival_price_gbp="6.97",
        current_price_gbp="6.98",
        hard_floor_gbp="5.90",
        final_ceiling_gbp="10.64",
        max_step_down_gbp="0.20",
        max_step_up_gbp="0.20",
        observable=True,
        we_present=True,
    )

    assert result.state == "DEFENSIVE_LISTING_BALANCED_DEFEND"
    assert result.phase == "match_after_pressure"
    assert result.target_price_gbp == "6.97"
    assert result.write_required is True
    assert "DEFENSIVE_LISTING_AFTER_PRESSURE_MATCH" in result.reason_codes
