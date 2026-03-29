from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scraper.notifications import build_run_summary, send_slack_summary, write_run_summary


class NotificationsTests(unittest.TestCase):
    def test_build_run_summary_includes_counts_and_top_rows(self):
        rows = [
            {
                "title": "Integration Delivery Partner",
                "agency": "Health NZ",
                "relevance_score": 88,
                "estimated_seek_timeline": "3 months",
                "status": "open",
            },
            {
                "title": "ERP Refresh",
                "agency": "Inland Revenue",
                "relevance_score": 65,
                "estimated_seek_timeline": "6 months",
                "status": "closed",
            },
        ]

        summary = build_run_summary(rows, new_count=1, errors=["Minor parse issue"])

        self.assertIn("Tenders processed: 2", summary)
        self.assertIn("New tenders: 1", summary)
        self.assertIn("High relevance (70+): 1", summary)
        self.assertIn("Integration Delivery Partner | Health NZ | score 88 | 3 months", summary)
        self.assertIn("Minor parse issue", summary)

    def test_write_run_summary_creates_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "reports" / "summary.md"
            written = write_run_summary("# Summary\n", path=str(path))

            self.assertEqual(written, str(path))
            self.assertEqual(path.read_text(encoding="utf-8"), "# Summary\n")

    @patch.dict("os.environ", {}, clear=False)
    def test_send_slack_summary_returns_false_without_webhook(self):
        self.assertFalse(send_slack_summary("summary"))


if __name__ == "__main__":
    unittest.main()
