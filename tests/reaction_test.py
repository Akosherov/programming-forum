import unittest
from unittest.mock import patch

from common.exceptions import ForbiddenError, NotFoundError, UnauthorizedError
from data.models import ReactionSummary


def _reply(reply_id=1, author_id=10, topic_id=5):
    return {"reply_id": reply_id, "author_id": author_id, "topic_id": topic_id}


class GetReplyInternalShould(unittest.TestCase):

    @patch("services.reaction_service.read_query", return_value=[(1, 10, 5)])
    def test_existing_reply_returns_dict_with_correct_keys(self, mock_rq):
        from services.reaction_service import _get_reply
        result = _get_reply(1)
        self.assertEqual(result, {"reply_id": 1, "author_id": 10, "topic_id": 5})
        mock_rq.assert_called_once()
        self.assertIn(1, mock_rq.call_args[0][1])

    @patch("services.reaction_service.read_query", return_value=[])
    def test_missing_reply_raises_not_found(self, mock_rq):
        from services.reaction_service import _get_reply
        with self.assertRaises(NotFoundError):
            _get_reply(999)


class GetTopicInfoInternalShould(unittest.TestCase):

    @patch("services.reaction_service.read_query", return_value=[(1, 42)])
    def test_returns_is_private_as_bool_and_author_id(self, mock_rq):
        from services.reaction_service import _get_topic_info
        is_private, author_id = _get_topic_info(5)
        self.assertIs(is_private, True)
        self.assertEqual(author_id, 42)
        mock_rq.assert_called_once()
        self.assertIn(5, mock_rq.call_args[0][1])

    @patch("services.reaction_service.read_query", return_value=[])
    def test_missing_topic_raises_not_found(self, mock_rq):
        from services.reaction_service import _get_topic_info
        with self.assertRaises(NotFoundError):
            _get_topic_info(999)


class EnsureReactionAllowedShould(unittest.TestCase):

    @patch("services.reaction_service._get_topic_info", return_value=(False, 99))
    def test_public_topic_non_author_passes_without_exception(self, mock_gti):
        from services.reaction_service import _ensure_reaction_allowed
        _ensure_reaction_allowed(_reply(author_id=10), user_id=1)
        mock_gti.assert_called_once_with(5)

    def test_reacting_to_own_reply_raises_forbidden(self):
        from services.reaction_service import _ensure_reaction_allowed
        with self.assertRaises(ForbiddenError) as ctx:
            _ensure_reaction_allowed(_reply(author_id=1), user_id=1)
        self.assertIn("own reply", ctx.exception.message)

    @patch("services.reaction_service._has_access_to_private_topic",
           return_value=False)
    @patch("services.reaction_service._get_topic_info", return_value=(True, 99))
    def test_private_topic_without_access_raises_unauthorized(
        self, mock_gti, mock_access
    ):
        from services.reaction_service import _ensure_reaction_allowed
        with self.assertRaises(UnauthorizedError):
            _ensure_reaction_allowed(_reply(author_id=10), user_id=1)
        mock_access.assert_called_once_with(5, 1)

    @patch("services.reaction_service._has_access_to_private_topic",
           return_value=True)
    @patch("services.reaction_service._get_topic_info", return_value=(True, 99))
    def test_private_topic_with_access_passes(self, mock_gti, mock_access):
        from services.reaction_service import _ensure_reaction_allowed
        _ensure_reaction_allowed(_reply(author_id=10), user_id=1)


class AddOrUpdateReactionShould(unittest.TestCase):

    @patch("services.reaction_service.insert_query")
    @patch("services.reaction_service.read_query", return_value=[])
    @patch("services.reaction_service._ensure_reaction_allowed")
    @patch("services.reaction_service._get_reply", return_value=_reply())
    def test_no_existing_reaction_calls_insert(
        self, mock_get, mock_ensure, mock_rq, mock_iq
    ):
        from services.reaction_service import add_or_update_reaction
        add_or_update_reaction(1, user_id=2, is_like=True)
        mock_iq.assert_called_once()
        params = mock_iq.call_args[0][1]
        self.assertIn(True, params)

    @patch("services.reaction_service.update_query")
    @patch("services.reaction_service.read_query", return_value=[(1,)])
    @patch("services.reaction_service._ensure_reaction_allowed")
    @patch("services.reaction_service._get_reply", return_value=_reply())
    def test_existing_reaction_calls_update_not_insert(
        self, mock_get, mock_ensure, mock_rq, mock_uq
    ):
        from services.reaction_service import add_or_update_reaction
        with patch("services.reaction_service.insert_query") as mock_iq:
            add_or_update_reaction(1, user_id=2, is_like=False)
            mock_uq.assert_called_once()
            mock_iq.assert_not_called()

    @patch("services.reaction_service._get_reply",
           side_effect=NotFoundError("Reply not found"))
    def test_missing_reply_propagates_not_found(self, mock_get):
        from services.reaction_service import add_or_update_reaction
        with self.assertRaises(NotFoundError):
            add_or_update_reaction(999, 1, True)


class RemoveReactionShould(unittest.TestCase):

    @patch("services.reaction_service.delete_query")
    @patch("services.reaction_service._get_reply", return_value=_reply())
    def test_remove_calls_delete_with_correct_ids(self, mock_get, mock_dq):
        from services.reaction_service import remove_reaction
        remove_reaction(reply_id=1, user_id=2)
        mock_dq.assert_called_once()
        params = mock_dq.call_args[0][1]
        self.assertIn(1, params)
        self.assertIn(2, params)

    @patch("services.reaction_service._get_reply",
           side_effect=NotFoundError("Reply not found"))
    def test_missing_reply_propagates_not_found(self, mock_get):
        from services.reaction_service import remove_reaction
        with self.assertRaises(NotFoundError):
            remove_reaction(999, 1)


class GetReactionSummaryShould(unittest.TestCase):

    @patch("services.reaction_service.read_query", return_value=[(5, 2)])
    @patch("services.reaction_service._get_reply", return_value=_reply())
    def test_unauthenticated_summary_has_no_user_reaction(
        self, mock_get, mock_rq
    ):
        from services.reaction_service import get_reaction_summary
        result = get_reaction_summary(1)
        self.assertIsInstance(result, ReactionSummary)
        self.assertEqual(result.likes, 5)
        self.assertEqual(result.dislikes, 2)
        self.assertIsNone(result.user_reaction)
        mock_rq.assert_called_once()

    @patch("services.reaction_service.read_query")
    @patch("services.reaction_service._get_reply", return_value=_reply())
    def test_authenticated_user_with_like_returns_true(
        self, mock_get, mock_rq
    ):
        mock_rq.side_effect = [[(3, 1)], [(1,)]]
        from services.reaction_service import get_reaction_summary
        result = get_reaction_summary(1, user_id=2)
        self.assertIs(result.user_reaction, True)
        self.assertEqual(mock_rq.call_count, 2)

    @patch("services.reaction_service.read_query")
    @patch("services.reaction_service._get_reply", return_value=_reply())
    def test_authenticated_user_with_dislike_returns_false(
        self, mock_get, mock_rq
    ):
        mock_rq.side_effect = [[(0, 4)], [(0,)]]
        from services.reaction_service import get_reaction_summary
        result = get_reaction_summary(1, user_id=2)
        self.assertIs(result.user_reaction, False)

    @patch("services.reaction_service.read_query")
    @patch("services.reaction_service._get_reply", return_value=_reply())
    def test_authenticated_user_with_no_reaction_returns_none(
        self, mock_get, mock_rq
    ):
        mock_rq.side_effect = [[(0, 0)], []]
        from services.reaction_service import get_reaction_summary
        result = get_reaction_summary(1, user_id=2)
        self.assertIsNone(result.user_reaction)

    @patch("services.reaction_service.read_query", return_value=[(None, None)])
    @patch("services.reaction_service._get_reply", return_value=_reply())
    def test_null_db_counts_default_to_zero(self, mock_get, mock_rq):
        from services.reaction_service import get_reaction_summary
        result = get_reaction_summary(1)
        self.assertEqual(result.likes, 0)
        self.assertEqual(result.dislikes, 0)

    @patch("services.reaction_service._get_reply",
           side_effect=NotFoundError())
    def test_missing_reply_propagates_not_found(self, mock_get):
        from services.reaction_service import get_reaction_summary
        with self.assertRaises(NotFoundError):
            get_reaction_summary(999)


if __name__ == "__main__":
    unittest.main()
