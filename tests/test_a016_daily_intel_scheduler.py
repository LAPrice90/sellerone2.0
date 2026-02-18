import unittest

from scripts import A016_refresh_phase1_daily_intel as a016


class A016DailyIntelSchedulerTests(unittest.TestCase):
    def test_cpt_due_logic_by_tier(self) -> None:
        due_write, reasons_write, bucket_write = a016._cpt_age_due(
            tier="ACTIVE_WRITE",
            cpt_status="OK",
            last_refresh_utc="2026-02-16T00:00:00Z",
            now_utc="2026-02-17T01:00:00Z",
        )
        self.assertTrue(due_write)
        self.assertEqual(bucket_write, "DUE_STALE")
        self.assertIn("CPT_DUE_STALE_24H", reasons_write)

        due_readonly, reasons_readonly, bucket_readonly = a016._cpt_age_due(
            tier="ACTIVE_READONLY",
            cpt_status="OK",
            last_refresh_utc="2026-02-14T00:00:00Z",
            now_utc="2026-02-17T01:00:00Z",
        )
        self.assertTrue(due_readonly)
        self.assertEqual(bucket_readonly, "DUE_STALE")
        self.assertIn("CPT_DUE_STALE_72H", reasons_readonly)

        due_parked, reasons_parked, bucket_parked = a016._cpt_age_due(
            tier="PARKED",
            cpt_status="ERROR",
            last_refresh_utc="2026-02-10T00:00:00Z",
            now_utc="2026-02-17T01:00:00Z",
        )
        self.assertFalse(due_parked)
        self.assertEqual(bucket_parked, "SKIP")
        self.assertEqual(reasons_parked, ["CPT_SKIP_PARKED"])

    def test_cpt_due_logic_missing_or_error_retries_daily(self) -> None:
        due_missing_yesterday, reasons_yesterday, bucket_yesterday = a016._cpt_age_due(
            tier="ACTIVE_READONLY",
            cpt_status="MISSING",
            last_refresh_utc="2026-02-16T23:00:00Z",
            now_utc="2026-02-17T01:00:00Z",
        )
        self.assertTrue(due_missing_yesterday)
        self.assertEqual(bucket_yesterday, "DUE_MISSING_ERROR")
        self.assertIn("CPT_DUE_STATUS_RECOVERY_NEW_DAY", reasons_yesterday)

        due_missing_today, reasons_today, bucket_today = a016._cpt_age_due(
            tier="ACTIVE_READONLY",
            cpt_status="MISSING",
            last_refresh_utc="2026-02-17T00:30:00Z",
            now_utc="2026-02-17T01:00:00Z",
        )
        self.assertFalse(due_missing_today)
        self.assertEqual(bucket_today, "SKIP")
        self.assertIn("CPT_SKIP_STATUS_RECOVERY_ALREADY_RETRIED_TODAY", reasons_today)

        due_error_no_refresh, reasons_error, bucket_error = a016._cpt_age_due(
            tier="ACTIVE_WRITE",
            cpt_status="ERROR",
            last_refresh_utc="",
            now_utc="2026-02-17T01:00:00Z",
        )
        self.assertTrue(due_error_no_refresh)
        self.assertEqual(bucket_error, "DUE_MISSING_ERROR")
        self.assertIn("CPT_DUE_STATUS_RECOVERY_NO_LAST_REFRESH", reasons_error)

    def test_cpt_due_logic_no_cpt_rechecks_weekly(self) -> None:
        due_recent, reasons_recent, bucket_recent = a016._cpt_age_due(
            tier="ACTIVE_READONLY",
            cpt_status="NO_CPT",
            last_refresh_utc="2026-02-17T00:30:00Z",
            now_utc="2026-02-17T12:00:00Z",
            no_cpt_recheck_hours=168.0,
        )
        self.assertFalse(due_recent)
        self.assertEqual(bucket_recent, "SKIP_NO_CPT_WEEKLY")
        self.assertIn("CPT_SKIP_NO_CPT_WEEKLY_NOT_DUE", reasons_recent)

        due_old, reasons_old, bucket_old = a016._cpt_age_due(
            tier="ACTIVE_READONLY",
            cpt_status="NO_CPT",
            last_refresh_utc="2026-02-10T11:59:59Z",
            now_utc="2026-02-17T12:00:00Z",
            no_cpt_recheck_hours=168.0,
        )
        self.assertTrue(due_old)
        self.assertEqual(bucket_old, "DUE_NO_CPT_WEEKLY")
        self.assertIn("CPT_DUE_NO_CPT_WEEKLY", reasons_old)

    def test_cpt_risk_band_logic(self) -> None:
        high = a016._compute_cpt_risk(
            cpt_gbp="10.00",
            buy_box_gbp="11.00",
            high_pct=5.0,
            medium_pct=2.0,
        )
        self.assertEqual(high[0], "HIGH")
        self.assertEqual(high[1], "1.00")
        self.assertEqual(high[2], "10.00")

        low = a016._compute_cpt_risk(
            cpt_gbp="10.00",
            buy_box_gbp="10.10",
            high_pct=5.0,
            medium_pct=2.0,
        )
        self.assertEqual(low[0], "LOW")

        unknown = a016._compute_cpt_risk(
            cpt_gbp="",
            buy_box_gbp="10.10",
            high_pct=5.0,
            medium_pct=2.0,
        )
        self.assertEqual(unknown[0], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
