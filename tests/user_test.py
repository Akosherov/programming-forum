
import unittest
from datetime import datetime
from unittest.mock import patch

from tests.helpers_test import make_admin, make_user, make_user_row
from common.exceptions import ForbiddenError, NotFoundError, UnauthorizedError
from data.models import (
    User, UserCreate, UserDelete, UserListResponse,
    UserPublic, UserRole, UserUpdate
)


class GetUserByUsernameInternalShould(unittest.TestCase):

    @patch("services.user_service.read_query")
    def test_existing_username_returns_user_object(self, mock_rq):
        mock_rq.return_value = [make_user_row()]
        from services.user_service import _get_user_by_username_internal
        result = _get_user_by_username_internal("jdoe")
        self.assertIsInstance(result, User)
        self.assertEqual(result.username, "jdoe")
        # behaviour: exactly one query was issued with the correct username
        mock_rq.assert_called_once()
        self.assertIn("jdoe", mock_rq.call_args[0][1])

    @patch("services.user_service.read_query", return_value=[])
    def test_unknown_username_returns_none(self, mock_rq):
        from services.user_service import _get_user_by_username_internal
        self.assertIsNone(_get_user_by_username_internal("ghost"))
        mock_rq.assert_called_once()


class GetByIdInternalShould(unittest.TestCase):

    @patch("services.user_service.read_query")
    def test_existing_id_returns_user_object(self, mock_rq):
        mock_rq.return_value = [make_user_row(user_id=5)]
        from services.user_service import _get_by_id_internal
        result = _get_by_id_internal(5)
        self.assertIsInstance(result, User)
        self.assertEqual(result.user_id, 5)
        mock_rq.assert_called_once()
        self.assertIn(5, mock_rq.call_args[0][1])

    @patch("services.user_service.read_query", return_value=[])
    def test_unknown_id_returns_none(self, mock_rq):
        from services.user_service import _get_by_id_internal
        self.assertIsNone(_get_by_id_internal(999))


class GetAllShould(unittest.TestCase):

    @patch("services.user_service.read_query")
    def test_returns_paginated_user_list_response(self, mock_rq):
        mock_rq.side_effect = [[(5,)], [make_user_row()]]
        from services.user_service import get_all
        result = get_all()
        self.assertIsInstance(result, UserListResponse)
        self.assertEqual(result.total, 5)
        self.assertEqual(len(result.users), 1)
        self.assertEqual(mock_rq.call_count, 2)

    @patch("services.user_service.read_query")
    def test_search_term_is_passed_as_wildcard_to_query(self, mock_rq):
        mock_rq.side_effect = [[(1,)], [make_user_row()]]
        from services.user_service import get_all
        get_all(search="alice")
        for c in mock_rq.call_args_list:
            params = c[0][1]
            self.assertTrue(any("%alice%" in str(p) for p in params))

    @patch("services.user_service.read_query")
    def test_empty_result_set_returns_zero_total(self, mock_rq):
        mock_rq.side_effect = [[(0,)], []]
        from services.user_service import get_all
        result = get_all()
        self.assertEqual(result.total, 0)
        self.assertEqual(result.users, [])

    @patch("services.user_service.read_query")
    def test_pagination_values_are_echoed_in_response(self, mock_rq):
        mock_rq.side_effect = [[(0,)], []]
        from services.user_service import get_all
        result = get_all(page=3, per_page=10)
        self.assertEqual(result.page, 3)
        self.assertEqual(result.per_page, 10)


class GetByIdShould(unittest.TestCase):

    @patch("services.user_service.read_query")
    def test_returns_public_user_not_full_user(self, mock_rq):
        mock_rq.return_value = [make_user_row()]
        from services.user_service import get_by_id
        result = get_by_id(1)
        self.assertIsInstance(result, UserPublic)
        self.assertEqual(result.user_id, 1)

    @patch("services.user_service.read_query", return_value=[])
    def test_missing_id_returns_none(self, mock_rq):
        from services.user_service import get_by_id
        self.assertIsNone(get_by_id(999))


class CreateUserShould(unittest.TestCase):

    @patch("services.user_service.insert_query", return_value=10)
    @patch("services.user_service.hash_password", return_value="hashed_pw")
    @patch("services.user_service.username_or_email_exists", return_value=False)
    def test_successful_creation_returns_user_with_hashed_password(
        self, mock_exists, mock_hash, mock_insert
    ):
        from services.user_service import create_user
        data = UserCreate(
            first_name="Alice", last_name="Smith",
            email="alice@example.com", username="alicesmith",
            password="plaintext"
        )
        result = create_user(data)

        self.assertIsInstance(result, User)
        self.assertEqual(result.user_id, 10)
        self.assertEqual(result.password, "hashed_pw")
        mock_hash.assert_called_once_with("plaintext")
        mock_exists.assert_called_once_with("alicesmith", "alice@example.com")
        mock_insert.assert_called_once()

    @patch("services.user_service.username_or_email_exists", return_value=True)
    def test_duplicate_username_or_email_raises_forbidden(self, mock_exists):
        from services.user_service import create_user
        with self.assertRaises(ForbiddenError):
            create_user(UserCreate(
                first_name="Bob", last_name="Jones",
                email="bob@example.com", username="bobjones",
                password="pass"
            ))
        with patch("services.user_service.insert_query") as mock_insert:
            mock_insert.assert_not_called()


class UsernameOrEmailExistsShould(unittest.TestCase):

    @patch("services.user_service.read_query", return_value=[(1,)])
    def test_existing_record_returns_true(self, mock_rq):
        from services.user_service import username_or_email_exists
        self.assertTrue(username_or_email_exists("taken", "taken@ex.com"))
        mock_rq.assert_called_once()

    @patch("services.user_service.read_query", return_value=[])
    def test_no_record_returns_false(self, mock_rq):
        from services.user_service import username_or_email_exists
        self.assertFalse(username_or_email_exists("free", "free@ex.com"))


class UpdateUserShould(unittest.TestCase):

    @patch("services.user_service.update_query")
    @patch("services.user_service.read_query")
    @patch("services.user_service.verify_password", return_value=True)
    def test_regular_user_can_update_own_first_name(
        self, mock_verify, mock_rq, mock_uq
    ):
        mock_rq.side_effect = [
            [make_user_row(password="hashed")],     # existing user fetch
            [make_user_row(first_name="Updated")],  # re-fetch after update
        ]
        from services.user_service import update_user
        result = update_user(1, UserUpdate(current_password="correct",
                                           first_name="Updated"), make_user())
        self.assertIsNotNone(result)
        self.assertEqual(result.first_name, "Updated")
        mock_verify.assert_called_once_with("correct", "hashed")
        mock_uq.assert_called_once()

    @patch("services.user_service.read_query", return_value=[])
    def test_user_not_found_returns_none(self, mock_rq):
        from services.user_service import update_user
        self.assertIsNone(update_user(999, UserUpdate(), make_user()))

    @patch("services.user_service.read_query")
    def test_missing_current_password_raises_unauthorized(self, mock_rq):
        mock_rq.return_value = [make_user_row()]
        from services.user_service import update_user
        with self.assertRaises(UnauthorizedError):
            update_user(1, UserUpdate(first_name="New"), make_user())

    @patch("services.user_service.verify_password", return_value=False)
    @patch("services.user_service.read_query")
    def test_wrong_current_password_raises_unauthorized(self, mock_rq, mock_verify):
        mock_rq.return_value = [make_user_row(password="hashed")]
        from services.user_service import update_user
        with self.assertRaises(UnauthorizedError):
            update_user(1, UserUpdate(current_password="wrong"), make_user())
        mock_verify.assert_called_once_with("wrong", "hashed")

    @patch("services.user_service.update_query")
    @patch("services.user_service.read_query")
    def test_admin_updates_other_user_without_password(self, mock_rq, mock_uq):
        mock_rq.side_effect = [
            [make_user_row()],                      # existing user fetch
            [make_user_row(first_name="ByAdmin")],  # re-fetch after update
        ]
        from services.user_service import update_user
        result = update_user(1, UserUpdate(first_name="ByAdmin"), make_admin())
        self.assertIsNotNone(result)
        mock_uq.assert_called_once()

    @patch("services.user_service.read_query")
    def test_duplicate_email_raises_forbidden(self, mock_rq):
        mock_rq.side_effect = [
            [make_user_row()],  # existing user fetch
            [(1,)],             # email already taken — raises before re-fetch
        ]
        from services.user_service import update_user
        with self.assertRaises(ForbiddenError) as ctx:
            update_user(1, UserUpdate(email="taken@example.com"), make_admin())
        self.assertIn("Email", str(ctx.exception.message))

    @patch("services.user_service.verify_password", return_value=True)
    @patch("services.user_service.read_query")
    def test_no_fields_provided_skips_update_query(self, mock_rq, mock_verify):
        mock_rq.side_effect = [[make_user_row()]]
        from services.user_service import update_user
        with patch("services.user_service.update_query") as mock_uq:
            update_user(1, UserUpdate(current_password="pass"), make_user())
            mock_uq.assert_not_called()

    @patch("services.user_service.update_query")
    @patch("services.user_service.hash_password", return_value="new_hashed")
    @patch("services.user_service.verify_password", return_value=True)
    @patch("services.user_service.read_query")
    def test_new_password_is_hashed_before_storing(
        self, mock_rq, mock_verify, mock_hash, mock_uq
    ):
        mock_rq.side_effect = [
            [make_user_row()],
            [make_user_row(password="new_hashed")],
        ]
        from services.user_service import update_user
        update_user(1, UserUpdate(current_password="old", password="newpass"),
                    make_user())
        mock_hash.assert_called_once_with("newpass")


class DeleteUserShould(unittest.TestCase):

    @patch("services.user_service.update_query")
    @patch("services.user_service.verify_password", return_value=True)
    @patch("services.user_service.read_query")
    def test_user_can_self_delete_with_correct_password(
        self, mock_rq, mock_verify, mock_uq
    ):
        mock_rq.return_value = [make_user_row(password="hashed")]
        from services.user_service import delete_user
        result = delete_user(1, UserDelete(password="correct"), make_user())
        self.assertTrue(result)
        mock_verify.assert_called_once_with("correct", "hashed")
        mock_uq.assert_called_once()
        self.assertIn("is_deleted", mock_uq.call_args[0][0])

    @patch("services.user_service.read_query", return_value=[])
    def test_nonexistent_user_returns_false(self, mock_rq):
        from services.user_service import delete_user
        self.assertFalse(delete_user(999, UserDelete(password="x"), make_user()))

    @patch("services.user_service.read_query")
    def test_already_deleted_user_returns_false(self, mock_rq):
        mock_rq.return_value = [make_user_row(is_deleted=1)]
        from services.user_service import delete_user
        self.assertFalse(delete_user(1, UserDelete(password="x"),
                                     make_user(is_deleted=True)))

    @patch("services.user_service.read_query")
    def test_regular_user_cannot_delete_another_user(self, mock_rq):
        mock_rq.return_value = [make_user_row(user_id=1)]
        from services.user_service import delete_user
        with self.assertRaises(ForbiddenError):
            delete_user(1, UserDelete(password="x"),
                        make_user(user_id=2, username="other"))

    @patch("services.user_service.verify_password", return_value=False)
    @patch("services.user_service.read_query")
    def test_wrong_self_delete_password_raises_unauthorized(
        self, mock_rq, mock_verify
    ):
        mock_rq.return_value = [make_user_row(password="hashed")]
        from services.user_service import delete_user
        with self.assertRaises(UnauthorizedError):
            delete_user(1, UserDelete(password="wrong"), make_user())

    @patch("services.user_service.update_query")
    @patch("services.user_service.read_query")
    def test_admin_deletes_another_user_without_password(self, mock_rq, mock_uq):
        mock_rq.return_value = [make_user_row(user_id=5)]
        from services.user_service import delete_user
        result = delete_user(5, UserDelete(password=""), make_admin())
        self.assertTrue(result)
        mock_uq.assert_called_once()


class GetMyTopicsShould(unittest.TestCase):

    @patch("services.user_service.read_query")
    def test_returns_topic_list_for_user(self, mock_rq):
        now = datetime.now()
        mock_rq.side_effect = [
            [(2,)],
            [
                (1, "A Long Enough Topic Title Here", 0, 0, now, "johndoe", 3),
                (2, "Another Long Enough Title Here", 1, 0, now, "johndoe", 1),
            ],
        ]
        from services.user_service import get_my_topics
        result = get_my_topics(user_id=1)
        self.assertEqual(result.total, 2)
        self.assertEqual(len(result.topics), 2)
        for c in mock_rq.call_args_list:
            self.assertIn(1, c[0][1])

    @patch("services.user_service.read_query")
    def test_empty_topics_list(self, mock_rq):
        mock_rq.side_effect = [[(0,)], []]
        from services.user_service import get_my_topics
        result = get_my_topics(1)
        self.assertEqual(result.topics, [])


class GetMyRepliesShould(unittest.TestCase):

    @patch("services.user_service.read_query")
    def test_like_reaction_mapped_correctly(self, mock_rq):
        now = datetime.now()
        mock_rq.side_effect = [
            [(1,)],
            [(1, 1, "Content", "johndoe", 2, 0, now, 0, 1)],  # reaction=1 → like
        ]
        from services.user_service import get_my_replies
        result = get_my_replies(1)
        self.assertEqual(result.replies[0].current_user_reaction, "like")

    @patch("services.user_service.read_query")
    def test_dislike_reaction_mapped_correctly(self, mock_rq):
        now = datetime.now()
        mock_rq.side_effect = [
            [(1,)],
            [(1, 0,  "Content", "johndoe", 0, 3, now, 0, 0)],  # reaction=0 → dislike
        ]
        from services.user_service import get_my_replies
        result = get_my_replies(1)
        self.assertEqual(result.replies[0].current_user_reaction, "dislike")

    @patch("services.user_service.read_query")
    def test_no_reaction_mapped_to_none(self, mock_rq):
        now = datetime.now()
        mock_rq.side_effect = [
            [(1,)],
            [(1, 10, "Content", "johndoe", 1, 1, now, 0, None)],
        ]
        from services.user_service import get_my_replies
        result = get_my_replies(1)
        self.assertIsNone(result.replies[0].current_user_reaction)


class BlockUnblockUserShould(unittest.TestCase):

    @patch("services.user_service.update_query")
    @patch("services.user_service.read_query")
    def test_block_user_issues_correct_update(self, mock_rq, mock_uq):
        mock_rq.return_value = [make_user_row(user_id=5)]
        from services.user_service import block_user
        result = block_user(5, make_admin())
        self.assertTrue(result)
        mock_uq.assert_called_once()
        sql = mock_uq.call_args[0][0]
        self.assertIn("is_blocked", sql)
        self.assertIn(5, mock_uq.call_args[0][1])

    @patch("services.user_service.read_query", return_value=[])
    def test_block_nonexistent_user_raises_not_found(self, mock_rq):
        from services.user_service import block_user
        with self.assertRaises(NotFoundError):
            block_user(999, make_admin())

    @patch("services.user_service.read_query")
    def test_admin_cannot_block_themselves(self, mock_rq):
        admin = make_admin(user_id=99)
        mock_rq.return_value = [make_user_row(user_id=99)]
        from services.user_service import block_user
        with self.assertRaises(ForbiddenError) as ctx:
            block_user(99, admin)
        self.assertIn("yourself", ctx.exception.message)

    @patch("services.user_service.update_query")
    @patch("services.user_service.read_query")
    def test_unblock_user_issues_correct_update(self, mock_rq, mock_uq):
        mock_rq.return_value = [make_user_row(user_id=5)]
        from services.user_service import unblock_user
        result = unblock_user(5, make_admin())
        self.assertTrue(result)
        sql = mock_uq.call_args[0][0]
        self.assertIn("is_blocked", sql)

    @patch("services.user_service.read_query", return_value=[])
    def test_unblock_nonexistent_user_raises_not_found(self, mock_rq):
        from services.user_service import unblock_user
        with self.assertRaises(NotFoundError):
            unblock_user(999, make_admin())

    @patch("services.user_service.read_query")
    def test_admin_cannot_unblock_themselves(self, mock_rq):
        admin = make_admin(user_id=99)
        mock_rq.return_value = [make_user_row(user_id=99)]
        from services.user_service import unblock_user
        with self.assertRaises(ForbiddenError):
            unblock_user(99, admin)


class PromoteDemoteUserShould(unittest.TestCase):

    @patch("services.user_service.update_query")
    @patch("services.user_service.read_query")
    def test_promote_regular_user_to_admin(self, mock_rq, mock_uq):
        mock_rq.return_value = [make_user_row(user_id=5, role_id=UserRole.USER)]
        from services.user_service import promote_user
        result = promote_user(5, make_admin())
        self.assertTrue(result)
        mock_uq.assert_called_once()
        params = mock_uq.call_args[0][1]
        self.assertIn(UserRole.ADMIN, params)

    @patch("services.user_service.read_query", return_value=[])
    def test_promote_nonexistent_user_raises_not_found(self, mock_rq):
        from services.user_service import promote_user
        with self.assertRaises(NotFoundError):
            promote_user(999, make_admin())

    @patch("services.user_service.read_query")
    def test_admin_cannot_promote_themselves(self, mock_rq):
        admin = make_admin(user_id=99)
        mock_rq.return_value = [make_user_row(user_id=99)]
        from services.user_service import promote_user
        with self.assertRaises(ForbiddenError) as ctx:
            promote_user(99, admin)
        self.assertIn("yourself", ctx.exception.message)

    @patch("services.user_service.read_query")
    def test_promote_existing_admin_raises_forbidden(self, mock_rq):
        mock_rq.return_value = [make_user_row(user_id=5, role_id=UserRole.ADMIN)]
        from services.user_service import promote_user
        with self.assertRaises(ForbiddenError) as ctx:
            promote_user(5, make_admin())
        self.assertIn("already", ctx.exception.message)

    @patch("services.user_service.update_query")
    @patch("services.user_service.read_query")
    def test_demote_admin_when_others_remain(self, mock_rq, mock_uq):
        mock_rq.side_effect = [
            [make_user_row(user_id=5, role_id=UserRole.ADMIN)],
            [(1,)],   # one other admin remains
        ]
        from services.user_service import demote_user
        result = demote_user(5, make_admin())
        self.assertTrue(result)
        mock_uq.assert_called_once()
        params = mock_uq.call_args[0][1]
        self.assertIn(UserRole.USER, params)

    @patch("services.user_service.read_query", return_value=[])
    def test_demote_nonexistent_user_raises_not_found(self, mock_rq):
        from services.user_service import demote_user
        with self.assertRaises(NotFoundError):
            demote_user(999, make_admin())

    @patch("services.user_service.read_query")
    def test_demote_regular_user_raises_forbidden(self, mock_rq):
        mock_rq.return_value = [make_user_row(user_id=5, role_id=UserRole.USER)]
        from services.user_service import demote_user
        with self.assertRaises(ForbiddenError) as ctx:
            demote_user(5, make_admin())
        self.assertIn("not an Admin", ctx.exception.message)

    @patch("services.user_service.read_query")
    def test_demoting_last_admin_raises_forbidden(self, mock_rq):
        mock_rq.side_effect = [
            [make_user_row(user_id=5, role_id=UserRole.ADMIN)],
            [(0,)],   # no other admins
        ]
        from services.user_service import demote_user
        with self.assertRaises(ForbiddenError) as ctx:
            demote_user(5, make_admin())
        self.assertIn("last admin", ctx.exception.message)


if __name__ == "__main__":
    unittest.main()
