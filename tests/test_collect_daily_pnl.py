import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "longbridge-assistant" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from collect import collect_daily_pnl  # noqa: E402


class FakeProvider:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, path, query):
        self.calls.append((path, query))
        return self.response


class CollectDailyPnlTests(unittest.TestCase):
    def test_uses_api_date_parameters_and_accepts_signed_usd_summary(self):
        report_day = "2026-10-01"
        provider = FakeProvider({
            "summary": {
                "currency": "USD",
                "sum_profit": "-12.34",
                "start_date": report_day,
                "end_date": report_day,
            }
        })

        result = collect_daily_pnl(provider, report_day)

        self.assertEqual(provider.calls, [(
            "/v1/portfolio/profit-analysis-summary",
            {"start_date": report_day, "end_date": report_day},
        )])
        self.assertEqual(result["status"], "完整")
        self.assertEqual(result["amount"], "-12.34")

    def test_rejects_summary_for_a_different_day(self):
        report_day = "2026-10-01"
        provider = FakeProvider({
            "summary": {
                "currency": "USD",
                "sum_profit": "12.34",
                "start_date": "2026-09-30",
                "end_date": "2026-09-30",
            }
        })

        result = collect_daily_pnl(provider, report_day)

        self.assertEqual(result["status"], "失败")
        self.assertIsNone(result["amount"])


if __name__ == "__main__":
    unittest.main()
