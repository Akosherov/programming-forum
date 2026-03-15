import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from main import app

client = TestClient(app, raise_server_exceptions=False)

_TOPIC_ROW = (1, "Best Python Topic Title", "techguru",
              "2026-01-01T00:00:00", 42)


class StatsEndpointShould(unittest.TestCase):

    @patch("routers.stats.read_query")
    def test_returns_200(self, mock_rq):
        mock_rq.side_effect = [[(100,)], [(50,)], [], []]
        response = client.get("/stats/")
        self.assertEqual(response.status_code, 200)

    @patch("routers.stats.read_query")
    def test_response_contains_all_expected_keys(self, mock_rq):
        mock_rq.side_effect = [[(0,)], [(0,)], [], []]
        data = client.get("/stats/").json()["data"]
        for key in ("total_users", "total_topics",
                    "top_10_most_replied", "top_10_most_recent"):
            self.assertIn(key, data)

    @patch("routers.stats.read_query")
    def test_user_and_topic_counts_match_db_values(self, mock_rq):
        mock_rq.side_effect = [[(42,)], [(17,)], [], []]
        data = client.get("/stats/").json()["data"]
        self.assertEqual(data["total_users"], 42)
        self.assertEqual(data["total_topics"], 17)

    @patch("routers.stats.read_query")
    def test_topic_rows_are_formatted_correctly(self, mock_rq):
        mock_rq.side_effect = [[(1,)], [(1,)], [_TOPIC_ROW], [_TOPIC_ROW]]
        data = client.get("/stats/").json()["data"]
        replied = data["top_10_most_replied"][0]
        self.assertEqual(replied["topic_id"], 1)
        self.assertEqual(replied["title"], "Best Python Topic Title")
        self.assertEqual(replied["author_username"], "techguru")
        self.assertEqual(replied["reply_count"], 42)

    @patch("routers.stats.read_query")
    def test_exactly_four_db_queries_are_issued(self, mock_rq):
        mock_rq.side_effect = [[(0,)], [(0,)], [], []]
        client.get("/stats/")
        self.assertEqual(mock_rq.call_count, 4)

    @patch("routers.stats.read_query")
    def test_endpoint_is_public_no_auth_required(self, mock_rq):
        mock_rq.side_effect = [[(0,)], [(0,)], [], []]
        response = client.get("/stats/")
        self.assertEqual(response.status_code, 200)

    @patch("routers.stats.read_query")
    def test_response_message_field(self, mock_rq):
        mock_rq.side_effect = [[(0,)], [(0,)], [], []]
        self.assertEqual(client.get("/stats/").json()["message"],
                         "Stats retrieved")

    @patch("routers.stats.read_query")
    def test_empty_topic_lists_are_returned_as_empty_arrays(self, mock_rq):
        mock_rq.side_effect = [[(0,)], [(0,)], [], []]
        data = client.get("/stats/").json()["data"]
        self.assertEqual(data["top_10_most_replied"], [])
        self.assertEqual(data["top_10_most_recent"], [])


if __name__ == "__main__":
    unittest.main()
