import unittest
from unittest.mock import patch

from tests.helpers_test import make_admin, make_user
from common.exceptions import ForbiddenError, NotFoundError, UnauthorizedError
from data.models import UserPublic


class GetParticipantsShould(unittest.TestCase):

    @patch("services.participant_service.read_query")
    def test_topic_author_can_retrieve_participants(self, mock_rq):
        author = make_user(user_id=1)
        mock_rq.side_effect = [
            [(1,)],   # topic row — author_id = 1
            [(2, "Jane", "Doe", "janesmith", 0)],
        ]
        from services.participant_service import get_participants
        result = get_participants(topic_id=5, current_user=author)
        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], UserPublic)
        self.assertEqual(mock_rq.call_count, 2)

    @patch("services.participant_service.read_query")
    def test_admin_can_retrieve_participants_of_any_topic(self, mock_rq):
        admin = make_admin()
        mock_rq.side_effect = [
            [(10,)],
            [(2, "Jane", "Doe", "janesmith", 0)],
        ]
        from services.participant_service import get_participants
        result = get_participants(topic_id=5, current_user=admin)
        self.assertEqual(len(result), 1)

    @patch("services.participant_service.read_query")
    def test_accepted_participant_can_retrieve_list(self, mock_rq):
        participant = make_user(user_id=2)
        mock_rq.side_effect = [
            [(10,)],
            [(1,)],
            [(2, "Jane", "Doe", "janesmith", 0)],
        ]
        from services.participant_service import get_participants
        result = get_participants(topic_id=5, current_user=participant)
        self.assertEqual(len(result), 1)
        participant_call_params = mock_rq.call_args_list[1][0][1]
        self.assertIn(5, participant_call_params)
        self.assertIn(2, participant_call_params)

    @patch("services.participant_service.read_query")
    def test_outsider_raises_unauthorized(self, mock_rq):
        outsider = make_user(user_id=7)
        mock_rq.side_effect = [
            [(10,)],
            [],
        ]
        from services.participant_service import get_participants
        with self.assertRaises(UnauthorizedError):
            get_participants(topic_id=5, current_user=outsider)

    @patch("services.participant_service.read_query", return_value=[])
    def test_nonexistent_topic_raises_not_found(self, mock_rq):
        from services.participant_service import get_participants
        with self.assertRaises(NotFoundError):
            get_participants(topic_id=999, current_user=make_user())


class RemoveParticipantShould(unittest.TestCase):

    @patch("services.participant_service.delete_query")
    @patch("services.participant_service.read_query")
    def test_author_removes_participant_and_calls_delete(
        self, mock_rq, mock_dq
    ):
        author = make_user(user_id=1)
        mock_rq.side_effect = [
            [(1,)],
            [(1,)],
        ]
        from services.participant_service import remove_participant
        result = remove_participant(topic_id=5, user_id=3, current_user=author)
        self.assertTrue(result)
        mock_dq.assert_called_once()
        params = mock_dq.call_args[0][1]
        self.assertIn(5, params)
        self.assertIn(3, params)

    @patch("services.participant_service.delete_query")
    @patch("services.participant_service.read_query")
    def test_admin_can_remove_from_any_topic(self, mock_rq, mock_dq):
        admin = make_admin()
        mock_rq.side_effect = [[(10,)], [(1,)]]
        from services.participant_service import remove_participant
        result = remove_participant(5, user_id=3, current_user=admin)
        self.assertTrue(result)
        mock_dq.assert_called_once()

    @patch("services.participant_service.read_query", return_value=[])
    def test_nonexistent_topic_raises_not_found(self, mock_rq):
        from services.participant_service import remove_participant
        with self.assertRaises(NotFoundError):
            remove_participant(999, user_id=2, current_user=make_user(user_id=1))

    @patch("services.participant_service.read_query", return_value=[(10,)])
    def test_non_author_non_admin_raises_unauthorized(self, mock_rq):
        outsider = make_user(user_id=7)
        from services.participant_service import remove_participant
        with self.assertRaises(UnauthorizedError):
            remove_participant(5, user_id=3, current_user=outsider)

    @patch("services.participant_service.read_query", return_value=[(1,)])
    def test_removing_topic_author_raises_forbidden(self, mock_rq):
        author = make_user(user_id=1)
        from services.participant_service import remove_participant
        with self.assertRaises(ForbiddenError) as ctx:
            remove_participant(5, user_id=1, current_user=author)
        self.assertIn("author", ctx.exception.message)

    @patch("services.participant_service.read_query")
    def test_user_not_in_participant_list_raises_not_found(self, mock_rq):
        author = make_user(user_id=1)
        mock_rq.side_effect = [
            [(1,)],
            [],
        ]
        from services.participant_service import remove_participant
        with self.assertRaises(NotFoundError) as ctx:
            remove_participant(5, user_id=3, current_user=author)
        self.assertIn("participant", ctx.exception.message)


class LeaveTopicShould(unittest.TestCase):

    @patch("services.participant_service.delete_query")
    @patch("services.participant_service.read_query")
    def test_participant_leaves_topic_and_calls_delete(
        self, mock_rq, mock_dq
    ):
        participant = make_user(user_id=3)
        mock_rq.side_effect = [
            [(10,)],
            [(1,)],
        ]
        from services.participant_service import leave_topic
        result = leave_topic(topic_id=5, current_user=participant)
        self.assertTrue(result)
        mock_dq.assert_called_once()
        params = mock_dq.call_args[0][1]
        self.assertIn(5, params)
        self.assertIn(3, params)

    @patch("services.participant_service.read_query", return_value=[])
    def test_nonexistent_topic_raises_not_found(self, mock_rq):
        from services.participant_service import leave_topic
        with self.assertRaises(NotFoundError):
            leave_topic(999, make_user())

    @patch("services.participant_service.read_query", return_value=[(1,)])
    def test_topic_author_cannot_leave_raises_forbidden(self, mock_rq):
        author = make_user(user_id=1)
        from services.participant_service import leave_topic
        with self.assertRaises(ForbiddenError) as ctx:
            leave_topic(5, author)
        self.assertIn("author", ctx.exception.message)

    @patch("services.participant_service.read_query")
    def test_non_participant_raises_not_found(self, mock_rq):
        user = make_user(user_id=3)
        mock_rq.side_effect = [
            [(10,)],
            [],
        ]
        from services.participant_service import leave_topic
        with self.assertRaises(NotFoundError) as ctx:
            leave_topic(5, user)
        self.assertIn("participant", ctx.exception.message)


if __name__ == "__main__":
    unittest.main()
