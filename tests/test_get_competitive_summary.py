import json
import unittest
from unittest.mock import patch

from scripts.api import get_competitive_summary as cpt


class _DummyResponse:
    def __init__(self, status_code: int, payload: dict, text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text or json.dumps(payload)

    def json(self) -> dict:
        return self._payload


class GetCompetitiveSummaryTests(unittest.TestCase):
    @patch("scripts.api.get_competitive_summary.spapi_post_json")
    @patch("scripts.api.get_competitive_summary.get_lwa_access_token")
    @patch("scripts.api.get_competitive_summary.load_dotenv_if_missing")
    def test_http_200_with_no_cpt_value_maps_to_no_cpt(
        self,
        _load_env,
        mock_token,
        mock_post,
    ) -> None:
        mock_token.return_value = "token"
        mock_post.return_value = _DummyResponse(
            200,
            {
                "responses": [
                    {
                        "status": {"statusCode": 200},
                        "body": {"referencePrices": []},
                    }
                ]
            },
        )

        out = cpt.fetch_cpt_for_asin(
            asin="B000TEST01",
            marketplace_id="A1F83G8C2ARO7P",
            run_id="RID",
            script_name="A016_refresh_phase1_daily_intel",
        )
        self.assertEqual(out.get("cpt_status"), "NO_CPT")
        self.assertEqual(out.get("reason_codes"), ["CPT_NO_VALUE_200"])
        self.assertEqual(out.get("error_summary"), "")

    @patch("scripts.api.get_competitive_summary.spapi_post_json")
    @patch("scripts.api.get_competitive_summary.get_lwa_access_token")
    @patch("scripts.api.get_competitive_summary.load_dotenv_if_missing")
    def test_http_error_maps_to_error(
        self,
        _load_env,
        mock_token,
        mock_post,
    ) -> None:
        mock_token.return_value = "token"
        mock_post.return_value = _DummyResponse(503, {"message": "internal service failure"})

        out = cpt.fetch_cpt_for_asin(
            asin="B000TEST02",
            marketplace_id="A1F83G8C2ARO7P",
            run_id="RID",
            script_name="A016_refresh_phase1_daily_intel",
        )
        self.assertEqual(out.get("cpt_status"), "ERROR")
        self.assertEqual(out.get("reason_codes"), ["CPT_ERROR"])
        self.assertIn("http_503", str(out.get("error_summary", "")))

    @patch("scripts.api.get_competitive_summary.spapi_post_json")
    @patch("scripts.api.get_competitive_summary.get_lwa_access_token")
    @patch("scripts.api.get_competitive_summary.load_dotenv_if_missing")
    def test_batch_error_maps_to_error(
        self,
        _load_env,
        mock_token,
        mock_post,
    ) -> None:
        mock_token.return_value = "token"
        mock_post.return_value = _DummyResponse(
            200,
            {
                "responses": [
                    {
                        "status": {"statusCode": 500},
                        "body": {"errors": [{"code": "InternalError", "message": "boom"}]},
                    }
                ]
            },
        )

        out = cpt.fetch_cpt_for_asin(
            asin="B000TEST03",
            marketplace_id="A1F83G8C2ARO7P",
            run_id="RID",
            script_name="A016_refresh_phase1_daily_intel",
        )
        self.assertEqual(out.get("cpt_status"), "ERROR")
        self.assertEqual(out.get("reason_codes"), ["CPT_ERROR"])
        self.assertIn("batch_status_500", str(out.get("error_summary", "")))


if __name__ == "__main__":
    unittest.main()
