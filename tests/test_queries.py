from __future__ import annotations

import unittest
from unittest.mock import patch

from db.client import PostgrestError, QueryResult
from db.queries import _eq, _in, get_overview_stats, get_recent_tenders
from scraper.run import _dedupe_rows


class QueryHelpersTests(unittest.TestCase):
    def test_eq_filter_leaves_raw_value_for_requests_to_encode_once(self):
        self.assertEqual(_eq("https://example.com/a?x=1"), "eq.https://example.com/a?x=1")

    def test_in_filter_quotes_values_for_postgrest(self):
        filter_value = _in(["https://example.com/a?x=1", "https://example.com/b?x=2"])
        self.assertEqual(
            filter_value,
            'in.("https://example.com/a?x=1","https://example.com/b?x=2")',
        )

    def test_dedupe_rows_keeps_latest_row_per_url(self):
        rows = [
            {"gets_url": "https://example.com/1", "title": "Old"},
            {"gets_url": "https://example.com/2", "title": "Other"},
            {"gets_url": "https://example.com/1", "title": "New"},
        ]

        deduped = _dedupe_rows(rows)

        self.assertEqual(len(deduped), 2)
        self.assertEqual(deduped[0]["title"], "New")
        self.assertEqual(deduped[1]["title"], "Other")

    def test_recent_and_overview_fall_back_when_first_seen_column_is_missing(self):
        class FakeClient:
            def select(self, relation, *, params=None, count=None):
                if relation != "tenders":
                    raise AssertionError("unexpected relation")

                if params and "first_seen_at" in params:
                    raise PostgrestError("{'code': '42703', 'message': 'column does not exist'}")

                if params and "date_scraped" in params and count == "exact":
                    return QueryResult(data=[{"id": "1"}], count=3)

                if params and "date_scraped" in params:
                    return QueryResult(data=[{"id": "1", "title": "Fallback row"}], count=None)

                if params == {"select": "id"}:
                    return QueryResult(data=[{"id": "1"}], count=10)

                if params == {"select": "id", "status": _eq("open")}:
                    return QueryResult(data=[{"id": "1"}], count=6)

                if params == {"select": "id", "relevance_score": "gte.70"}:
                    return QueryResult(data=[{"id": "1"}], count=2)

                raise AssertionError(f"unexpected params: {params}")

        with patch("db.queries.get_read_client", return_value=FakeClient()):
            recent = get_recent_tenders(limit=5, days=14)
            stats = get_overview_stats()

        self.assertEqual(recent, [{"id": "1", "title": "Fallback row"}])
        self.assertEqual(stats["recent_new"], 3)
        self.assertEqual(stats["total"], 10)
        self.assertEqual(stats["open"], 6)
        self.assertEqual(stats["high_relevance"], 2)


if __name__ == "__main__":
    unittest.main()
