import unittest
from datetime import datetime
from unittest.mock import patch

from common.exceptions import ForbiddenError, NotFoundError, UnauthorizedError
from data.models import ReplyCreate, ReplyResponse, ReplyList, UserRole


def _reply_row(
    reply_id=1, topic_id=5, author_id=10,
    content="This is a valid reply content",
    like_count=0, dislike_count=0, is_best=0,
    created_at=None, username="johndoe", my_reaction=None
):
    return (reply_id, topic_id, author_id, content,
            like_count, dislike_count, is_best,
            created_at or datetime.now(), username, my_reaction)


def _make_reply_response(**kwargs):
    defaults = dict(
        id=1, content="Reply content here",
        author_username="johndoe", likes=0, dislikes=0,
        created_at=datetime.now(), is_best=False,
        current_user_reaction=None
    )
    defaults.update(kwargs)
    return ReplyResponse(**defaults)


class RowToReplyShould(unittest.TestCase):
    """
    Tests for the internal _row_to_reply helper.
    """
    def test_like_reaction_maps_to_like_string(self):
        from services.reply_service import _row_to_reply
        result = _row_to_reply(_reply_row(my_reaction=1))
        self.assertEqual(result.current_user_reaction, "like")

    def test_dislike_reaction_maps_to_dislike_string(self):
        from services.reply_service import _row_to_reply
        result = _row_to_reply(_reply_row(my_reaction=0))
        self.assertEqual(result.current_user_reaction, "dislike")

    def test_no_reaction_maps_to_none(self):
        from services.reply_service import _row_to_reply
        result = _row_to_reply(_reply_row(my_reaction=None))
        self.assertIsNone(result.current_user_reaction)

    def test_is_best_cast_to_bool(self):
        from services.reply_service import _row_to_reply
        self.assertTrue(_row_to_reply(_reply_row(is_best=1)).is_best)
        self.assertFalse(_row_to_reply(_reply_row(is_best=0)).is_best)


class CreateReplyShould(unittest.TestCase):

    @patch("services.reply_service.get_reply_by_id")
    @patch("services.reply_service.insert_query", return_value=1)
    @patch("services.reply_service.read_query")
    def test_creates_reply_for_public_unlocked_topic(self, mock_rq, mock_iq, mock_get):
        mock_rq.side_effect = [
            [(0,)],          # user not blocked
            [(5, 0, 0)],     # topic: id=5, not locked, not private
        ]
        mock_get.return_value = _make_reply_response()
        from services.reply_service import create_reply
        result = create_reply(ReplyCreate(topic_id=5, content="Valid reply content here"), author_id=1)
        mock_iq.assert_called_once()
        mock_get.assert_called_once_with(1, 1)
        self.assertIsInstance(result, ReplyResponse)

    @patch("services.reply_service.read_query", return_value=[])
    def test_user_not_found_raises_not_found(self, mock_rq):
        from services.reply_service import create_reply
        with self.assertRaises(NotFoundError):
            create_reply(ReplyCreate(topic_id=5, content="Valid reply content here"), author_id=999)

    @patch("services.reply_service.read_query", return_value=[(1,)])
    def test_blocked_user_raises_forbidden(self, mock_rq):
        from services.reply_service import create_reply
        with self.assertRaises(ForbiddenError) as ctx:
            create_reply(ReplyCreate(topic_id=5, content="Valid reply content here"), author_id=1)
        self.assertIn("Blocked", ctx.exception.message)

    @patch("services.reply_service.read_query")
    def test_topic_not_found_raises_not_found(self, mock_rq):
        mock_rq.side_effect = [
            [(0,)],  # user not blocked
            [],      # topic not found
        ]
        from services.reply_service import create_reply
        with self.assertRaises(NotFoundError):
            create_reply(ReplyCreate(topic_id=999, content="Valid reply content here"), author_id=1)

    @patch("services.reply_service.read_query")
    def test_locked_topic_raises_forbidden(self, mock_rq):
        mock_rq.side_effect = [
            [(0,)],          # user not blocked
            [(5, 1, 0)],     # topic: locked=1
        ]
        from services.reply_service import create_reply
        with self.assertRaises(ForbiddenError) as ctx:
            create_reply(ReplyCreate(topic_id=5, content="Valid reply content here"), author_id=1)
        self.assertIn("locked", ctx.exception.message)

    @patch("services.reply_service._has_access_to_private_topic", return_value=False)
    @patch("services.reply_service.read_query")
    def test_private_topic_without_access_raises_unauthorized(self, mock_rq, mock_access):
        mock_rq.side_effect = [
            [(0,)],          # user not blocked
            [(5, 0, 1)],     # topic: not locked, is_private=1
        ]
        from services.reply_service import create_reply
        with self.assertRaises(UnauthorizedError):
            create_reply(ReplyCreate(topic_id=5, content="Valid reply content here"), author_id=1)

    @patch("services.reply_service.get_reply_by_id")
    @patch("services.reply_service.insert_query", return_value=1)
    @patch("services.reply_service._has_access_to_private_topic", return_value=True)
    @patch("services.reply_service.read_query")
    def test_private_topic_with_access_creates_reply(self, mock_rq, mock_access, mock_iq, mock_get):
        mock_rq.side_effect = [
            [(0,)],         # user not blocked
            [(5, 0, 1)],    # private, not locked
        ]
        mock_get.return_value = _make_reply_response()
        from services.reply_service import create_reply
        create_reply(ReplyCreate(topic_id=5, content="Valid reply content here"), author_id=1)
        mock_iq.assert_called_once()


class GetReplyByIdShould(unittest.TestCase):

    @patch("services.reply_service.read_query")
    def test_existing_reply_returns_reply_response(self, mock_rq):
        mock_rq.return_value = [_reply_row()]
        from services.reply_service import get_reply_by_id
        result = get_reply_by_id(1)
        self.assertIsInstance(result, ReplyResponse)
        self.assertEqual(result.id, 1)

    @patch("services.reply_service.read_query", return_value=[])
    def test_missing_reply_raises_not_found(self, mock_rq):
        from services.reply_service import get_reply_by_id
        with self.assertRaises(NotFoundError):
            get_reply_by_id(999)

    @patch("services.reply_service.read_query")
    def test_current_user_id_passed_to_query(self, mock_rq):
        mock_rq.return_value = [_reply_row()]
        from services.reply_service import get_reply_by_id
        get_reply_by_id(1, current_user_id=42)
        params = mock_rq.call_args[0][1]
        self.assertIn(42, params)


class GetRepliesShould(unittest.TestCase):

    @patch("services.reply_service.read_query")
    def test_returns_paginated_reply_list_for_public_topic(self, mock_rq):
        mock_rq.side_effect = [
            [(5, 0)],          # topic exists, not private
            [(2,)],            # count=2
            [_reply_row(), _reply_row(reply_id=2)],
        ]
        from services.reply_service import get_replies
        result = get_replies(topic_id=5)
        self.assertIsInstance(result, ReplyList)
        self.assertEqual(result.total, 2)
        self.assertEqual(len(result.replies), 2)

    @patch("services.reply_service.read_query", return_value=[])
    def test_missing_topic_raises_not_found(self, mock_rq):
        from services.reply_service import get_replies
        with self.assertRaises(NotFoundError):
            get_replies(topic_id=999)

    @patch("services.reply_service.read_query", return_value=[(5, 1)])  # private
    def test_anonymous_user_on_private_topic_raises_unauthorized(self, mock_rq):
        from services.reply_service import get_replies
        with self.assertRaises(UnauthorizedError):
            get_replies(topic_id=5, current_user_id=None)

    @patch("services.reply_service._has_access_to_private_topic", return_value=False)
    @patch("services.reply_service.read_query", return_value=[(5, 1)])
    def test_user_without_access_to_private_topic_raises_unauthorized(self, mock_rq, mock_access):
        from services.reply_service import get_replies
        with self.assertRaises(UnauthorizedError):
            get_replies(topic_id=5, current_user_id=7)

    @patch("services.reply_service.read_query")
    def test_pagination_values_echoed_in_response(self, mock_rq):
        mock_rq.side_effect = [[(5, 0)], [(0,)], []]
        from services.reply_service import get_replies
        result = get_replies(topic_id=5, page=2, per_page=10)
        self.assertEqual(result.page, 2)
        self.assertEqual(result.per_page, 10)


class UpdateReplyShould(unittest.TestCase):

    @patch("services.reply_service.get_reply_by_id")
    @patch("services.reply_service.update_query")
    @patch("services.reply_service.read_query", return_value=[(10,)])  # author_id=10
    def test_author_can_update_own_reply(self, mock_rq, mock_uq, mock_get):
        mock_get.return_value = _make_reply_response(content="New content")
        from services.reply_service import update_reply
        result = update_reply(reply_id=1, user_id=10, new_content="New content")
        mock_uq.assert_called_once()
        mock_get.assert_called_once_with(1, 10)

    @patch("services.reply_service.read_query", return_value=[])
    def test_missing_reply_raises_not_found(self, mock_rq):
        from services.reply_service import update_reply
        with self.assertRaises(NotFoundError):
            update_reply(reply_id=999, user_id=1, new_content="Anything")

    @patch("services.reply_service.read_query", return_value=[(5,)])  # author=5
    def test_wrong_user_raises_unauthorized(self, mock_rq):
        from services.reply_service import update_reply
        with self.assertRaises(UnauthorizedError) as ctx:
            update_reply(reply_id=1, user_id=1, new_content="Anything")
        self.assertIn("your reply", ctx.exception.message)


class DeleteReplyShould(unittest.TestCase):

    @patch("services.reply_service.delete_query")
    @patch("services.reply_service.read_query", return_value=[(1, 5)])  # author=1, topic=5
    def test_author_can_delete_own_reply(self, mock_rq, mock_dq):
        from services.reply_service import delete_reply
        delete_reply(reply_id=1, user_id=1, user_role_id=UserRole.USER)
        mock_dq.assert_called_once()

    @patch("services.reply_service.delete_query")
    @patch("services.reply_service.read_query", return_value=[(5, 5)])  # different author
    def test_admin_can_delete_any_reply(self, mock_rq, mock_dq):
        from services.reply_service import delete_reply
        delete_reply(reply_id=1, user_id=99, user_role_id=UserRole.ADMIN)
        mock_dq.assert_called_once()

    @patch("services.reply_service.read_query", return_value=[])
    def test_missing_reply_raises_not_found(self, mock_rq):
        from services.reply_service import delete_reply
        with self.assertRaises(NotFoundError):
            delete_reply(reply_id=999, user_id=1, user_role_id=UserRole.USER)

    @patch("services.reply_service.read_query", return_value=[(5, 5)])  # author=5
    def test_non_author_non_admin_raises_unauthorized(self, mock_rq):
        from services.reply_service import delete_reply
        with self.assertRaises(UnauthorizedError):
            delete_reply(reply_id=1, user_id=1, user_role_id=UserRole.USER)


class MarkAsBestReplyShould(unittest.TestCase):

    @patch("services.reply_service.get_reply_by_id")
    @patch("services.reply_service.update_query")
    @patch("services.reply_service.read_query")
    def test_topic_author_can_mark_best_reply(self, mock_rq, mock_uq, mock_get):
        mock_rq.side_effect = [
            [(5, 2)],   # reply: topic_id=5, reply_author_id=2
            [(1,)],     # topic author_id=1
        ]
        mock_get.return_value = _make_reply_response(is_best=True)
        from services.reply_service import mark_as_best_reply
        result = mark_as_best_reply(reply_id=1, user_id=1)
        # Two updates: clear old best, then set new best
        self.assertEqual(mock_uq.call_count, 2)
        self.assertTrue(result.is_best)

    @patch("services.reply_service.read_query", return_value=[])
    def test_missing_reply_raises_not_found(self, mock_rq):
        from services.reply_service import mark_as_best_reply
        with self.assertRaises(NotFoundError):
            mark_as_best_reply(reply_id=999, user_id=1)

    @patch("services.reply_service.read_query")
    def test_missing_topic_raises_not_found(self, mock_rq):
        mock_rq.side_effect = [[(5, 2)], []]  # reply found, topic not
        from services.reply_service import mark_as_best_reply
        with self.assertRaises(NotFoundError):
            mark_as_best_reply(reply_id=1, user_id=1)

    @patch("services.reply_service.read_query")
    def test_non_topic_author_raises_unauthorized(self, mock_rq):
        mock_rq.side_effect = [
            [(5, 2)],   # reply
            [(1,)],     # topic author=1
        ]
        from services.reply_service import mark_as_best_reply
        with self.assertRaises(UnauthorizedError) as ctx:
            mark_as_best_reply(reply_id=1, user_id=7)  # user 7 is not topic author
        self.assertIn("topic author", ctx.exception.message)

    @patch("services.reply_service.read_query")
    def test_cannot_mark_own_reply_as_best(self, mock_rq):
        mock_rq.side_effect = [
            [(5, 1)],   # reply author = 1 (same as topic author)
            [(1,)],     # topic author = 1
        ]
        from services.reply_service import mark_as_best_reply
        with self.assertRaises(ForbiddenError) as ctx:
            mark_as_best_reply(reply_id=1, user_id=1)
        self.assertIn("own reply", ctx.exception.message)

    @patch("services.reply_service.get_reply_by_id")
    @patch("services.reply_service.update_query")
    @patch("services.reply_service.read_query")
    def test_marking_new_best_clears_previous_best(self, mock_rq, mock_uq, mock_get):
        mock_rq.side_effect = [[(5, 2)], [(1,)]]
        mock_get.return_value = _make_reply_response(is_best=True)
        from services.reply_service import mark_as_best_reply
        mark_as_best_reply(reply_id=1, user_id=1)
        # First update clears old best (topic level), second sets new
        first_update_sql = mock_uq.call_args_list[0][0][0]
        self.assertIn("is_best = 0", first_update_sql)
        second_update_sql = mock_uq.call_args_list[1][0][0]
        self.assertIn("is_best = 1", second_update_sql)


class UnmarkBestReplyShould(unittest.TestCase):

    @patch("services.reply_service.get_reply_by_id")
    @patch("services.reply_service.update_query")
    @patch("services.reply_service.read_query")
    def test_topic_author_can_unmark_best_reply(self, mock_rq, mock_uq, mock_get):
        mock_rq.side_effect = [
            [(5, 1)],   # reply: topic_id=5, is_best=1
            [(1,)],     # topic author_id=1
        ]
        mock_get.return_value = _make_reply_response(is_best=False)
        from services.reply_service import unmark_best_reply
        result = unmark_best_reply(reply_id=1, user_id=1)
        mock_uq.assert_called_once()
        self.assertFalse(result.is_best)

    @patch("services.reply_service.read_query", return_value=[])
    def test_missing_reply_raises_not_found(self, mock_rq):
        from services.reply_service import unmark_best_reply
        with self.assertRaises(NotFoundError):
            unmark_best_reply(reply_id=999, user_id=1)

    @patch("services.reply_service.read_query", return_value=[(5, 0)])  # is_best=0
    def test_reply_not_marked_as_best_raises_forbidden(self, mock_rq):
        from services.reply_service import unmark_best_reply
        with self.assertRaises(ForbiddenError) as ctx:
            unmark_best_reply(reply_id=1, user_id=1)
        self.assertIn("not marked", ctx.exception.message)

    @patch("services.reply_service.read_query")
    def test_missing_topic_raises_not_found(self, mock_rq):
        mock_rq.side_effect = [[(5, 1)], []]  # reply is best, topic missing
        from services.reply_service import unmark_best_reply
        with self.assertRaises(NotFoundError):
            unmark_best_reply(reply_id=1, user_id=1)

    @patch("services.reply_service.read_query")
    def test_non_topic_author_raises_unauthorized(self, mock_rq):
        mock_rq.side_effect = [[(5, 1)], [(1,)]]  # topic author=1
        from services.reply_service import unmark_best_reply
        with self.assertRaises(UnauthorizedError):
            unmark_best_reply(reply_id=1, user_id=7)


if __name__ == "__main__":
    unittest.main()
