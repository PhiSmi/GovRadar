from __future__ import annotations

import unittest

from bs4 import BeautifulSoup

from scraper.gets_scraper import _determine_status, _parse_closing_date, _parse_detail_page, _parse_listing_rows


class GetsScraperTests(unittest.TestCase):
    def test_parse_listing_rows_uses_fallback_table_detection(self):
        html = """
        <html>
            <body>
                <table>
                    <tr>
                        <th>RFX</th><th>Title</th><th>Type</th><th>Closes</th><th>Agency</th>
                    </tr>
                    <tr>
                        <td>204001</td>
                        <td><a href="/ExternalTenderDetails.htm?id=123">National Integration Platform</a></td>
                        <td>RFP</td>
                        <td>30 Mar 2026</td>
                        <td>Health NZ</td>
                    </tr>
                </table>
            </body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")

        rows = _parse_listing_rows(soup)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["title"], "National Integration Platform")
        self.assertEqual(rows[0]["agency"], "Health NZ")
        self.assertEqual(rows[0]["tender_type"], "RFP")
        self.assertEqual(rows[0]["rfx_id"], "204001")
        self.assertIn("ExternalTenderDetails.htm?id=123", rows[0]["gets_url"])

    def test_parse_detail_page_extracts_fields_and_attachments(self):
        html = """
        <html>
            <body>
                <div class="tenderOverview">
                    Procurement for an API integration and data migration programme.
                </div>
                <table>
                    <tr><th>Category</th><td>Information technology</td></tr>
                    <tr><th>Tender type</th><td>ROI</td></tr>
                    <tr><th>Estimated contract value</th><td>$2m</td></tr>
                    <tr><th>Close date</th><td>30 Mar 2026 5:00 PM</td></tr>
                    <tr><th>Agency</th><td>Ministry of Health</td></tr>
                    <tr><th>Status</th><td>Open</td></tr>
                </table>
                <a href="/documents/specification.pdf">Tender document</a>
            </body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")

        info = _parse_detail_page(soup)

        self.assertEqual(info["category"], "Information technology")
        self.assertEqual(info["tender_type"], "ROI")
        self.assertEqual(info["estimated_value"], "$2m")
        self.assertEqual(info["agency"], "Ministry of Health")
        self.assertEqual(info["status_label"], "Open")
        self.assertIn("API integration", info["description"])
        self.assertEqual(info["attachment_urls"], ["https://www.gets.govt.nz/documents/specification.pdf"])

    def test_parse_closing_date_and_status_rules(self):
        self.assertEqual(_parse_closing_date("30 Mar 2026 5:00 PM"), "2026-03-30")
        self.assertEqual(_determine_status("2020-01-01", None), "closed")
        self.assertEqual(_determine_status("2099-01-01", "Awarded"), "closed")
        self.assertEqual(_determine_status("2099-01-01", "Open"), "open")


if __name__ == "__main__":
    unittest.main()
