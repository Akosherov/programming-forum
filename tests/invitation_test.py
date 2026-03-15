import unittest
from datetime import datetime
from unittest.mock import patch

from common.exceptions import ForbiddenError, NotFoundError, UnauthorizedError
from data.models import (
    InvitationCreate, InvitationUpdate, InvitationResponse,
    InvitationList, BulkInvitationCreate, InvitationStatus, UserRole
)


def _invitation_row(
    invitation_id=1, topic_id=5, invited_user_id=3, invited_by_id=1,
    invitation_status=InvitationStatus.PENDING, created_at=None,
    topic_title="A Long Enough Topic Title", invited_username="janesmith",
    invited_by_username="johndoe"
):
    return (invitation_id, topic_id, invited_user_id, invited_by_id,
            invitation_status, created_at or datetime.now(),
            topic_title, invited_username, invited_by_username)


def _make_invitation_response(**kwargs):
    defaults = dict(
        invitation_id=1, topic_id=5,
        topic_title="A Long Enough Topic Title",
        invited_user_id=3, invited_username="janesmith",
        invited_by_id=1, invited_by_username="johndoe",
        invitation_status=InvitationStatus.PENDING,
        created_at=datetime.now()
    )
    defaults.update(kwargs)
    return InvitationResponse(**defaults)


class CreateInvitationShould(unittest.TestCase):

    @patch("services.invitation_service.get_invitation_by_id")
    @patch("services.invitation_service.insert_query", return_value=1)
    @patch("services.invitation_service.read_query")
    def test_topic_author_can_invite_user_to_private_topic(
        self, mock_rq, mock_iq, mock_get
    ):
        mock_rq.side_effect = [
            [(5, 1, 1)],   # topic: id=5, is_private=1, author_id=1
            [(3, 0)],      # invited user: id=3, not blocked
            [],            # no existing invitation
        ]
        mock_get.return_value = _make_invitation_response()
        from services.invitation_service import create_invitation
        result = create_invitation(
            InvitationCreate(topic_id=5, invited_user_id=3),
            invited_by_id=1,
            invited_by_role_id=UserRole.USER
        )
        mock_iq.assert_called_once()
        self.assertIsInstance(result, InvitationResponse)

    @patch("services.invitation_service.get_invitation_by_id")
    @patch("services.invitation_service.insert_query", return_value=1)
    @patch("services.invitation_service.read_query")
    def test_admin_can_invite_to_any_private_topic(
        self, mock_rq, mock_iq, mock_get
    ):
        mock_rq.side_effect = [
            [(5, 1, 10)],  # topic: author_id=10 (not admin)
            [(3, 0)],
            [],
        ]
        mock_get.return_value = _make_invitation_response()
        from services.invitation_service import create_invitation
        create_invitation(
            InvitationCreate(topic_id=5, invited_user_id=3),
            invited_by_id=99,
            invited_by_role_id=UserRole.ADMIN
        )
        mock_iq.assert_called_once()

    @patch("services.invitation_service.read_query", return_value=[])
    def test_missing_topic_raises_not_found(self, mock_rq):
        from services.invitation_service import create_invitation
        with self.assertRaises(NotFoundError):
            create_invitation(
                InvitationCreate(topic_id=999, invited_user_id=3),
                invited_by_id=1, invited_by_role_id=UserRole.USER
            )

    @patch("services.invitation_service.read_query", return_value=[(5, 0, 1)])  # public
    def test_public_topic_raises_forbidden(self, mock_rq):
        from services.invitation_service import create_invitation
        with self.assertRaises(ForbiddenError) as ctx:
            create_invitation(
                InvitationCreate(topic_id=5, invited_user_id=3),
                invited_by_id=1, invited_by_role_id=UserRole.USER
            )
        self.assertIn("public", ctx.exception.message)

    @patch("services.invitation_service.read_query")
    def test_non_author_regular_user_raises_unauthorized(self, mock_rq):
        mock_rq.return_value = [(5, 1, 10)]  # author=10, requester is 1
        from services.invitation_service import create_invitation
        with self.assertRaises(UnauthorizedError):
            create_invitation(
                InvitationCreate(topic_id=5, invited_user_id=3),
                invited_by_id=1, invited_by_role_id=UserRole.USER
            )

    @patch("services.invitation_service.read_query")
    def test_inviting_nonexistent_user_raises_not_found(self, mock_rq):
        mock_rq.side_effect = [
            [(5, 1, 1)],  # valid private topic, author=1
            [],           # invited user not found
        ]
        from services.invitation_service import create_invitation
        with self.assertRaises(NotFoundError):
            create_invitation(
                InvitationCreate(topic_id=5, invited_user_id=999),
                invited_by_id=1, invited_by_role_id=UserRole.USER
            )

    @patch("services.invitation_service.read_query")
    def test_inviting_blocked_user_raises_forbidden(self, mock_rq):
        mock_rq.side_effect = [
            [(5, 1, 1)],   # valid private topic
            [(3, 1)],      # invited user is blocked
        ]
        from services.invitation_service import create_invitation
        with self.assertRaises(ForbiddenError) as ctx:
            create_invitation(
                InvitationCreate(topic_id=5, invited_user_id=3),
                invited_by_id=1, invited_by_role_id=UserRole.USER
            )
        self.assertIn("blocked", ctx.exception.message)

    @patch("services.invitation_service.read_query")
    def test_duplicate_invitation_raises_forbidden(self, mock_rq):
        mock_rq.side_effect = [
            [(5, 1, 1)],    # valid private topic
            [(3, 0)],       # user not blocked
            [(1,)],         # existing invitation found
        ]
        from services.invitation_service import create_invitation
        with self.assertRaises(ForbiddenError) as ctx:
            create_invitation(
                InvitationCreate(topic_id=5, invited_user_id=3),
                invited_by_id=1, invited_by_role_id=UserRole.USER
            )
        self.assertIn("already invited", ctx.exception.message)


class GetInvitationByIdShould(unittest.TestCase):

    @patch("services.invitation_service.read_query")
    def test_existing_invitation_returns_response(self, mock_rq):
        mock_rq.return_value = [_invitation_row()]
        from services.invitation_service import get_invitation_by_id
        result = get_invitation_by_id(1)
        self.assertIsInstance(result, InvitationResponse)
        self.assertEqual(result.invitation_id, 1)

    @patch("services.invitation_service.read_query", return_value=[])
    def test_missing_invitation_raises_not_found(self, mock_rq):
        from services.invitation_service import get_invitation_by_id
        with self.assertRaises(NotFoundError):
            get_invitation_by_id(999)


class GetUserInvitationsShould(unittest.TestCase):

    @patch("services.invitation_service.read_query")
    def test_returns_paginated_invitation_list(self, mock_rq):
        now = datetime.now()
        mock_rq.side_effect = [
            [(2,)],
            [
                (1, 5, "Topic A", "johndoe", InvitationStatus.PENDING, now),
                (2, 6, "Topic B", "johndoe", InvitationStatus.ACCEPTED, now),
            ]
        ]
        from services.invitation_service import get_user_invitations
        result = get_user_invitations(user_id=3)
        self.assertIsInstance(result, InvitationList)
        self.assertEqual(result.total, 2)
        self.assertEqual(len(result.invitations), 2)

    @patch("services.invitation_service.read_query")
    def test_status_filter_is_included_in_query(self, mock_rq):
        mock_rq.side_effect = [[(0,)], []]
        from services.invitation_service import get_user_invitations
        get_user_invitations(user_id=3, status_filter=InvitationStatus.PENDING)
        count_query = mock_rq.call_args_list[0][0][0]
        params = mock_rq.call_args_list[0][0][1]
        self.assertIn("invitation_status", count_query)
        self.assertIn(InvitationStatus.PENDING, params)

    @patch("services.invitation_service.read_query")
    def test_pagination_values_echoed_in_response(self, mock_rq):
        mock_rq.side_effect = [[(0,)], []]
        from services.invitation_service import get_user_invitations
        result = get_user_invitations(user_id=3, page=2, per_page=5)
        self.assertEqual(result.page, 2)
        self.assertEqual(result.per_page, 5)


class UpdateInvitationStatusShould(unittest.TestCase):

    @patch("services.invitation_service.get_invitation_by_id")
    @patch("services.invitation_service.read_query")
    @patch("services.invitation_service.update_query")
    def test_invited_user_can_accept_pending_invitation(
        self, mock_uq, mock_rq, mock_get
    ):
        mock_rq.side_effect = [
            [(3, InvitationStatus.PENDING, 5)],  # invitation row
            [],                                  # not yet a participant
        ]
        mock_get.return_value = _make_invitation_response(
            invitation_status=InvitationStatus.ACCEPTED
        )
        from services.invitation_service import update_invitation_status
        with patch("services.invitation_service.insert_query") as mock_iq:
            result = update_invitation_status(
                invitation_id=1, user_id=3,
                status_update=InvitationUpdate(invitation_status=InvitationStatus.ACCEPTED)
            )
            # Accepting should add user to participants
            mock_iq.assert_called_once()
        mock_uq.assert_called_once()
        self.assertEqual(result.invitation_status, InvitationStatus.ACCEPTED)

    @patch("services.invitation_service.get_invitation_by_id")
    @patch("services.invitation_service.read_query")
    @patch("services.invitation_service.update_query")
    def test_invited_user_can_decline_pending_invitation(
        self, mock_uq, mock_rq, mock_get
    ):
        mock_rq.return_value = [(3, InvitationStatus.PENDING, 5)]
        mock_get.return_value = _make_invitation_response(
            invitation_status=InvitationStatus.DECLINED
        )
        from services.invitation_service import update_invitation_status
        with patch("services.invitation_service.insert_query") as mock_iq:
            update_invitation_status(
                invitation_id=1, user_id=3,
                status_update=InvitationUpdate(invitation_status=InvitationStatus.DECLINED)
            )
            # Declining should NOT add user to participants
            mock_iq.assert_not_called()

    @patch("services.invitation_service.read_query", return_value=[])
    def test_missing_invitation_raises_not_found(self, mock_rq):
        from services.invitation_service import update_invitation_status
        with self.assertRaises(NotFoundError):
            update_invitation_status(
                invitation_id=999, user_id=3,
                status_update=InvitationUpdate(invitation_status=InvitationStatus.ACCEPTED)
            )

    @patch("services.invitation_service.read_query", return_value=[(5, InvitationStatus.PENDING, 5)])
    def test_wrong_user_raises_unauthorized(self, mock_rq):
        from services.invitation_service import update_invitation_status
        with self.assertRaises(UnauthorizedError) as ctx:
            update_invitation_status(
                invitation_id=1, user_id=1,  # user 1 was not invited
                status_update=InvitationUpdate(invitation_status=InvitationStatus.ACCEPTED)
            )
        self.assertIn("invited user", ctx.exception.message)

    @patch("services.invitation_service.read_query",
           return_value=[(3, InvitationStatus.ACCEPTED, 5)])  # already accepted
    def test_non_pending_invitation_raises_forbidden(self, mock_rq):
        from services.invitation_service import update_invitation_status
        with self.assertRaises(ForbiddenError) as ctx:
            update_invitation_status(
                invitation_id=1, user_id=3,
                status_update=InvitationUpdate(invitation_status=InvitationStatus.DECLINED)
            )
        self.assertIn("pending", ctx.exception.message)

    @patch("services.invitation_service.get_invitation_by_id")
    @patch("services.invitation_service.insert_query")
    @patch("services.invitation_service.read_query")
    @patch("services.invitation_service.update_query")
    def test_accepting_when_already_participant_skips_insert(
        self, mock_uq, mock_rq, mock_iq, mock_get
    ):
        mock_rq.side_effect = [
            [(3, InvitationStatus.PENDING, 5)],
            [(1,)],  # already a participant
        ]
        mock_get.return_value = _make_invitation_response(
            invitation_status=InvitationStatus.ACCEPTED
        )
        from services.invitation_service import update_invitation_status
        update_invitation_status(
            invitation_id=1, user_id=3,
            status_update=InvitationUpdate(invitation_status=InvitationStatus.ACCEPTED)
        )
        mock_iq.assert_not_called()


class DeleteInvitationShould(unittest.TestCase):

    @patch("services.invitation_service.delete_query")
    @patch("services.invitation_service.read_query", return_value=[(5, 1)])  # author=1
    def test_topic_author_can_delete_invitation(self, mock_rq, mock_dq):
        from services.invitation_service import delete_invitation
        delete_invitation(invitation_id=1, user_id=1, user_role_id=UserRole.USER)
        mock_dq.assert_called_once()
        self.assertIn(1, mock_dq.call_args[0][1])

    @patch("services.invitation_service.delete_query")
    @patch("services.invitation_service.read_query", return_value=[(5, 10)])  # author=10
    def test_admin_can_delete_any_invitation(self, mock_rq, mock_dq):
        from services.invitation_service import delete_invitation
        delete_invitation(invitation_id=1, user_id=99, user_role_id=UserRole.ADMIN)
        mock_dq.assert_called_once()

    @patch("services.invitation_service.read_query", return_value=[])
    def test_missing_invitation_raises_not_found(self, mock_rq):
        from services.invitation_service import delete_invitation
        with self.assertRaises(NotFoundError):
            delete_invitation(invitation_id=999, user_id=1, user_role_id=UserRole.USER)

    @patch("services.invitation_service.read_query", return_value=[(5, 10)])  # author=10
    def test_non_author_non_admin_raises_unauthorized(self, mock_rq):
        from services.invitation_service import delete_invitation
        with self.assertRaises(UnauthorizedError) as ctx:
            delete_invitation(invitation_id=1, user_id=1, user_role_id=UserRole.USER)
        self.assertIn("author or admin", ctx.exception.message)


class BulkCreateInvitationsShould(unittest.TestCase):

    @patch("services.invitation_service.create_invitation")
    def test_all_successful_invitations_returned(self, mock_create):
        mock_create.return_value = _make_invitation_response()
        from services.invitation_service import bulk_create_invitations
        result = bulk_create_invitations(
            BulkInvitationCreate(topic_id=5, invited_user_ids=[2, 3, 4]),
            invited_by_id=1, invited_by_role_id=UserRole.USER
        )
        self.assertEqual(result.total_invited, 3)
        self.assertEqual(result.successful_invitations, [2, 3, 4])
        self.assertEqual(result.failed_invitations, [])

    @patch("services.invitation_service.create_invitation")
    def test_failed_invitations_collected_without_raising(self, mock_create):
        mock_create.side_effect = [
            _make_invitation_response(),
            ForbiddenError("User already invited"),
            _make_invitation_response(),
        ]
        from services.invitation_service import bulk_create_invitations
        result = bulk_create_invitations(
            BulkInvitationCreate(topic_id=5, invited_user_ids=[2, 3, 4]),
            invited_by_id=1, invited_by_role_id=UserRole.USER
        )
        self.assertEqual(result.total_invited, 2)
        self.assertEqual(len(result.failed_invitations), 1)
        self.assertEqual(result.failed_invitations[0]["user_id"], 3)
        self.assertIn("already invited", result.failed_invitations[0]["reason"])

    @patch("services.invitation_service.create_invitation")
    def test_unexpected_exception_is_caught_as_failed(self, mock_create):
        mock_create.side_effect = [RuntimeError("DB is down")]
        from services.invitation_service import bulk_create_invitations
        result = bulk_create_invitations(
            BulkInvitationCreate(topic_id=5, invited_user_ids=[2]),
            invited_by_id=1, invited_by_role_id=UserRole.USER
        )
        self.assertEqual(result.total_invited, 0)
        self.assertEqual(result.failed_invitations[0]["reason"], "Unexpected Error")

    @patch("services.invitation_service.create_invitation")
    def test_all_failed_returns_zero_total_invited(self, mock_create):
        mock_create.side_effect = ForbiddenError("Blocked")
        from services.invitation_service import bulk_create_invitations
        result = bulk_create_invitations(
            BulkInvitationCreate(topic_id=5, invited_user_ids=[2, 3]),
            invited_by_id=1, invited_by_role_id=UserRole.USER
        )
        self.assertEqual(result.total_invited, 0)
        self.assertEqual(len(result.failed_invitations), 2)


if __name__ == "__main__":
    unittest.main()
