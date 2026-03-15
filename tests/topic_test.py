import unittest
from datetime import datetime
from unittest.mock import patch

from common.exceptions import ForbiddenError, NotFoundError, UnauthorizedError
from data.models import (
    TopicCreate, TopicUpdate, TopicResponse, TopicList, UserRole
)


def _topic_row(
    topic_id=1, title="A Long Enough Topic Title",
    content="Content that is long enough for tests here",
    is_locked=0, is_private=0,
    created_at=None, author_id=1, author_username="johndoe", reply_count=0
):
    return (topic_id, title, content, is_locked, is_private,
            created_at or datetime.now(), author_id, author_username, reply_count)


def _topic_list_row(
    topic_id=1, title="A Long Enough Topic Title",
    is_locked=0, is_private=0,
    created_at=None, author_username="johndoe", reply_count=0
):
    return (topic_id, title, is_locked, is_private,
            created_at or datetime.now(), author_username, reply_count)


def _make_topic_response(**kwargs):
    defaults = dict(
        topic_id=1, title="A Long Enough Topic Title",
        content="Content that is long enough for the tests here.",
        is_locked=False, is_private=False,
        created_at=datetime.now(), author_id=1,
        author_username="johndoe", reply_count=0
    )
    defaults.update(kwargs)
    return TopicResponse(**defaults)


class CreateTopicShould(unittest.TestCase):

    @patch("services.topic_service.get_topic_by_id")
    @patch("services.topic_service.insert_query", return_value=1)
    @patch("services.topic_service.read_query", return_value=[(0,)])
    def test_creates_public_topic_successfully(self, mock_rq, mock_iq, mock_get):
        mock_get.return_value = _make_topic_response()
        from services.topic_service import create_topic
        data = TopicCreate(
            title="A Long Enough Topic Title Here",
            content="Content that is long enough for the topic test.",
            is_private=False
        )
        result = create_topic(data, author_id=1)
        mock_rq.assert_called_once()
        mock_iq.assert_called_once()
        mock_get.assert_called_once_with(1, 1)
        self.assertIsInstance(result, TopicResponse)

    @patch("services.topic_service.get_topic_by_id")
    @patch("services.topic_service.insert_query", side_effect=[1, None])
    @patch("services.topic_service.read_query", return_value=[(0,)])
    def test_private_topic_adds_author_as_participant(self, mock_rq, mock_iq, mock_get):
        mock_get.return_value = _make_topic_response(is_private=True)
        from services.topic_service import create_topic
        data = TopicCreate(
            title="A Long Enough Topic Title Here",
            content="Content that is long enough for the topic test.",
            is_private=True
        )
        create_topic(data, author_id=1)
        # Second insert_query call should be for topic_participants
        self.assertEqual(mock_iq.call_count, 2)
        participant_call = mock_iq.call_args_list[1]
        self.assertIn(1, participant_call[0][1])  # topic_id=1, user_id=1

    @patch("services.topic_service.read_query", return_value=[])
    def test_unknown_user_raises_not_found(self, mock_rq):
        from services.topic_service import create_topic
        with self.assertRaises(NotFoundError):
            create_topic(TopicCreate(
                title="A Long Enough Topic Title Here",
                content="Content that is long enough for the topic test.",
            ), author_id=999)

    @patch("services.topic_service.read_query", return_value=[(1,)])
    def test_blocked_user_raises_forbidden(self, mock_rq):
        from services.topic_service import create_topic
        with self.assertRaises(ForbiddenError) as ctx:
            create_topic(TopicCreate(
                title="A Long Enough Topic Title Here",
                content="Content that is long enough for the topic test.",
            ), author_id=1)
        self.assertIn("Blocked", ctx.exception.message)


class GetTopicByIdShould(unittest.TestCase):

    @patch("services.topic_service.read_query")
    def test_returns_topic_response_for_public_topic(self, mock_rq):
        mock_rq.return_value = [_topic_row()]
        from services.topic_service import get_topic_by_id
        result = get_topic_by_id(1)
        self.assertIsInstance(result, TopicResponse)
        self.assertEqual(result.topic_id, 1)

    @patch("services.topic_service.read_query", return_value=[])
    def test_raises_not_found_for_missing_topic(self, mock_rq):
        from services.topic_service import get_topic_by_id
        with self.assertRaises(NotFoundError):
            get_topic_by_id(999)

    @patch("services.topic_service._has_access_to_private_topic", return_value=False)
    @patch("services.topic_service.read_query")
    def test_private_topic_without_access_raises_unauthorized(self, mock_rq, mock_access):
        mock_rq.return_value = [_topic_row(is_private=1)]
        from services.topic_service import get_topic_by_id
        with self.assertRaises(UnauthorizedError):
            get_topic_by_id(1, current_user_id=5)

    @patch("services.topic_service.read_query")
    def test_anonymous_user_on_private_topic_raises_unauthorized(self, mock_rq):
        mock_rq.return_value = [_topic_row(is_private=1)]
        from services.topic_service import get_topic_by_id
        with self.assertRaises(UnauthorizedError):
            get_topic_by_id(1, current_user_id=None)

    @patch("services.topic_service._has_access_to_private_topic", return_value=True)
    @patch("services.topic_service.read_query")
    def test_private_topic_with_access_returns_topic(self, mock_rq, mock_access):
        mock_rq.return_value = [_topic_row(is_private=1)]
        from services.topic_service import get_topic_by_id
        result = get_topic_by_id(1, current_user_id=1)
        self.assertIsInstance(result, TopicResponse)
        self.assertTrue(result.is_private)


class GetTopicsShould(unittest.TestCase):

    @patch("services.topic_service.read_query")
    def test_returns_topic_list_with_pagination(self, mock_rq):
        mock_rq.side_effect = [[(5,)], [_topic_list_row()]]
        from services.topic_service import get_topics
        result = get_topics()
        self.assertIsInstance(result, TopicList)
        self.assertEqual(result.total, 5)
        self.assertEqual(len(result.topics), 1)

    @patch("services.topic_service.read_query")
    def test_anonymous_user_only_sees_public_topics(self, mock_rq):
        mock_rq.side_effect = [[(0,)], []]
        from services.topic_service import get_topics
        get_topics(current_user_id=None)
        count_query = mock_rq.call_args_list[0][0][0]
        self.assertIn("is_private = 0", count_query)

    @patch("services.topic_service.read_query")
    def test_authenticated_user_can_see_private_topics_they_have_access_to(self, mock_rq):
        mock_rq.side_effect = [[(2,)], [_topic_list_row(), _topic_list_row(topic_id=2, is_private=1)]]
        from services.topic_service import get_topics
        result = get_topics(current_user_id=1)
        count_query = mock_rq.call_args_list[0][0][0]
        self.assertIn("topic_participants", count_query)
        self.assertEqual(len(result.topics), 2)

    @patch("services.topic_service.read_query")
    def test_search_term_is_applied_to_title_and_content(self, mock_rq):
        mock_rq.side_effect = [[(0,)], []]
        from services.topic_service import get_topics
        get_topics(search="python")
        for call_args in mock_rq.call_args_list:
            params = call_args[0][1]
            self.assertTrue(any("%python%" in str(p) for p in params))

    @patch("services.topic_service.read_query")
    def test_invalid_sort_field_falls_back_to_created_at(self, mock_rq):
        mock_rq.side_effect = [[(0,)], []]
        from services.topic_service import get_topics
        get_topics(sort_by="invalid_field")
        order_query = mock_rq.call_args_list[1][0][0]
        self.assertIn("t.created_at", order_query)

    @patch("services.topic_service.read_query")
    def test_sort_desc_produces_desc_order_clause(self, mock_rq):
        mock_rq.side_effect = [[(0,)], []]
        from services.topic_service import get_topics
        get_topics(sort_order="desc")
        order_query = mock_rq.call_args_list[1][0][0]
        self.assertIn("DESC", order_query)

    @patch("services.topic_service.read_query")
    def test_pagination_values_echoed_in_response(self, mock_rq):
        mock_rq.side_effect = [[(0,)], []]
        from services.topic_service import get_topics
        result = get_topics(page=3, per_page=5)
        self.assertEqual(result.page, 3)
        self.assertEqual(result.per_page, 5)


class UpdateTopicShould(unittest.TestCase):

    @patch("services.topic_service.get_topic_by_id")
    @patch("services.topic_service.update_query")
    @patch("services.topic_service.read_query", return_value=[(1, 0)])
    def test_author_can_update_own_topic(self, mock_rq, mock_uq, mock_get):
        mock_get.return_value = _make_topic_response(title="Updated Title Here")
        from services.topic_service import update_topic
        result = update_topic(1, TopicUpdate(title="Updated Title Here Long Enough"),
                              current_user_id=1, current_user_role_id=UserRole.USER)
        mock_uq.assert_called_once()
        mock_get.assert_called_once()

    @patch("services.topic_service.get_topic_by_id")
    @patch("services.topic_service.update_query")
    @patch("services.topic_service.read_query", return_value=[(5, 0)])
    def test_admin_can_update_any_topic(self, mock_rq, mock_uq, mock_get):
        mock_get.return_value = _make_topic_response()
        from services.topic_service import update_topic
        update_topic(1, TopicUpdate(title="Admin Updated Title Here"),
                     current_user_id=99, current_user_role_id=UserRole.ADMIN)
        mock_uq.assert_called_once()

    @patch("services.topic_service.read_query", return_value=[])
    def test_missing_topic_raises_not_found(self, mock_rq):
        from services.topic_service import update_topic
        with self.assertRaises(NotFoundError):
            update_topic(999, TopicUpdate(title="New Title Here Long Enough"),
                         current_user_id=1, current_user_role_id=UserRole.USER)

    @patch("services.topic_service.read_query", return_value=[(5, 0)])
    def test_non_author_non_admin_raises_unauthorized(self, mock_rq):
        from services.topic_service import update_topic
        with self.assertRaises(UnauthorizedError):
            update_topic(1, TopicUpdate(title="New Title Here Long Enough"),
                         current_user_id=1, current_user_role_id=UserRole.USER)

    @patch("services.topic_service.read_query", return_value=[(1, 1)])
    def test_locked_topic_raises_forbidden_for_non_admin(self, mock_rq):
        from services.topic_service import update_topic
        with self.assertRaises(ForbiddenError):
            update_topic(1, TopicUpdate(title="New Title Here Long Enough"),
                         current_user_id=1, current_user_role_id=UserRole.USER)

    @patch("services.topic_service.get_topic_by_id")
    @patch("services.topic_service.update_query")
    @patch("services.topic_service.read_query", return_value=[(1, 1)])
    def test_admin_can_update_locked_topic(self, mock_rq, mock_uq, mock_get):
        mock_get.return_value = _make_topic_response()
        from services.topic_service import update_topic
        update_topic(1, TopicUpdate(title="Admin Can Update Locked"),
                     current_user_id=99, current_user_role_id=UserRole.ADMIN)
        mock_uq.assert_called_once()

    @patch("services.topic_service.get_topic_by_id")
    @patch("services.topic_service.read_query", return_value=[(1, 0)])
    def test_no_fields_skips_update_query(self, mock_rq, mock_get):
        mock_get.return_value = _make_topic_response()
        from services.topic_service import update_topic
        with patch("services.topic_service.update_query") as mock_uq:
            update_topic(1, TopicUpdate(),
                         current_user_id=1, current_user_role_id=UserRole.USER)
            mock_uq.assert_not_called()


class DeleteTopicShould(unittest.TestCase):

    @patch("services.topic_service.delete_query")
    @patch("services.topic_service.read_query", return_value=[(1,)])
    def test_author_can_delete_own_topic(self, mock_rq, mock_dq):
        from services.topic_service import delete_topic
        delete_topic(1, current_user_id=1, current_user_role_id=UserRole.USER)
        mock_dq.assert_called_once()
        self.assertIn(1, mock_dq.call_args[0][1])

    @patch("services.topic_service.delete_query")
    @patch("services.topic_service.read_query", return_value=[(5,)])
    def test_admin_can_delete_any_topic(self, mock_rq, mock_dq):
        from services.topic_service import delete_topic
        delete_topic(1, current_user_id=99, current_user_role_id=UserRole.ADMIN)
        mock_dq.assert_called_once()

    @patch("services.topic_service.read_query", return_value=[])
    def test_missing_topic_raises_not_found(self, mock_rq):
        from services.topic_service import delete_topic
        with self.assertRaises(NotFoundError):
            delete_topic(999, current_user_id=1, current_user_role_id=UserRole.USER)

    @patch("services.topic_service.read_query", return_value=[(5,)])
    def test_non_author_non_admin_raises_unauthorized(self, mock_rq):
        from services.topic_service import delete_topic
        with self.assertRaises(UnauthorizedError):
            delete_topic(1, current_user_id=1, current_user_role_id=UserRole.USER)


class HasAccessToPrivateTopicShould(unittest.TestCase):

    @patch("services.topic_service.read_query", return_value=[(1,)])
    def test_admin_always_has_access(self, mock_rq):
        from services.topic_service import _has_access_to_private_topic
        self.assertTrue(_has_access_to_private_topic(1, user_id=99))
        mock_rq.assert_called_once()

    @patch("services.topic_service.read_query")
    def test_topic_author_has_access(self, mock_rq):
        mock_rq.side_effect = [[], [(1,)]]
        from services.topic_service import _has_access_to_private_topic
        self.assertTrue(_has_access_to_private_topic(1, user_id=1))

    @patch("services.topic_service.read_query")
    def test_participant_has_access(self, mock_rq):
        mock_rq.side_effect = [[], [], [(1,)]]
        from services.topic_service import _has_access_to_private_topic
        self.assertTrue(_has_access_to_private_topic(1, user_id=2))

    @patch("services.topic_service.read_query", return_value=[])
    def test_outsider_has_no_access(self, mock_rq):
        from services.topic_service import _has_access_to_private_topic
        self.assertFalse(_has_access_to_private_topic(1, user_id=7))


class LockUnlockTopicShould(unittest.TestCase):

    @patch("services.topic_service.get_topic_by_id")
    @patch("services.topic_service.update_query")
    @patch("services.topic_service.read_query", return_value=[(1,)])
    def test_lock_topic_issues_correct_update(self, mock_rq, mock_uq, mock_get):
        mock_get.return_value = _make_topic_response(is_locked=True)
        from services.topic_service import lock_topic
        result = lock_topic(1, admin_user_id=99)
        mock_uq.assert_called_once()
        self.assertIn("is_locked = 1", mock_uq.call_args[0][0])

    @patch("services.topic_service.read_query", return_value=[])
    def test_lock_missing_topic_raises_not_found(self, mock_rq):
        from services.topic_service import lock_topic
        with self.assertRaises(NotFoundError):
            lock_topic(999, admin_user_id=99)

    @patch("services.topic_service.get_topic_by_id")
    @patch("services.topic_service.update_query")
    @patch("services.topic_service.read_query", return_value=[(1,)])
    def test_unlock_topic_issues_correct_update(self, mock_rq, mock_uq, mock_get):
        mock_get.return_value = _make_topic_response(is_locked=False)
        from services.topic_service import unlock_topic
        result = unlock_topic(1, admin_user_id=99)
        mock_uq.assert_called_once()
        self.assertIn("is_locked = 0", mock_uq.call_args[0][0])

    @patch("services.topic_service.read_query", return_value=[])
    def test_unlock_missing_topic_raises_not_found(self, mock_rq):
        from services.topic_service import unlock_topic
        with self.assertRaises(NotFoundError):
            unlock_topic(999, admin_user_id=99)


if __name__ == "__main__":
    unittest.main()
