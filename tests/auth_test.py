"""
Unit tests for common/auth.py

Volatile dependencies that ARE mocked (they touch the database):
  - user_service._get_user_by_username_internal
  - user_service._get_by_id_internal
  - verify_password  (wraps bcrypt; slow + non-deterministic output)

Stable dependencies that are NOT mocked:
  - jose.jwt  (deterministic, pure Python — the behaviour we are testing)
  - HTTPException, HTTPAuthorizationCredentials (FastAPI value objects)
  - UserRole constants (plain integers)

Every mock is followed by a behaviour-verification assertion
(assert_called_once_with / assert_not_called / assert_called_with)
so the test captures not only WHAT happened but HOW the unit interacted
with its collaborators.
"""

import os
import unittest

from unittest.mock import patch
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from tests.helpers_test import make_admin, make_user
from common.auth import authenticate_user
from common.auth import create_access_token
from common.auth import get_current_user, get_optional_user, get_current_admin
from jose import jwt


# Helpers


def _creds(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def _valid_token(user_id: int) -> str:
    from common.auth import create_access_token
    return create_access_token({"user_id": user_id})


# Authenticate User


class AuthentcateUserShould(unittest.TestCase):

    @patch("common.auth.verify_password", return_value=True)
    @patch("common.auth.user_service._get_user_by_username_internal")
    def test_valid_credentials_return_user(self, mock_get, mock_verify):
        user = make_user()
        mock_get.return_value = user

        result = authenticate_user("jdoe", "anypass")

        self.assertEqual(result, user)
        mock_get.assert_called_once_with("jdoe")
        mock_verify.assert_called_once_with("anypass", user.password)

    @patch("common.auth.user_service._get_user_by_username_internal",
           return_value=None)
    def test_unknown_username_returns_false(self, mock_get):
        self.assertFalse(authenticate_user("ghost", "pass"))
        mock_get.assert_called_once_with("ghost")

    @patch("common.auth.user_service._get_user_by_username_internal")
    def test_deleted_user_returns_false_without_checking_password(self, mock_get):
        mock_get.return_value = make_user(is_deleted=True)
        with patch("common.auth.verify_password") as mock_verify:
            result = authenticate_user("jdoe", "pass")
            self.assertFalse(result)
            mock_verify.assert_not_called()

    @patch("common.auth.user_service._get_user_by_username_internal")
    def test_blocked_user_returns_false_without_checking_password(self, mock_get):
        mock_get.return_value = make_user(is_blocked=True)
        with patch("common.auth.verify_password") as mock_verify:
            result = authenticate_user("jdoe", "pass")
            self.assertFalse(result)
            mock_verify.assert_not_called()

    @patch("common.auth.verify_password", return_value=False)
    @patch("common.auth.user_service._get_user_by_username_internal")
    def test_wrong_password_returns_false(self, mock_get, mock_verify):
        user = make_user()
        mock_get.return_value = user
        self.assertFalse(authenticate_user("jdoe", "wrong"))
        mock_verify.assert_called_once_with("wrong", user.password)


# Create Access Token


class CreateAccessTokenShould(unittest.TestCase):
    """
    jose.jwt is a stable, deterministic library — it is NOT mocked.
    We test that the token is a valid JWT containing the expected claims.
    """
    def test_returns_a_non_empty_string(self):
        token = create_access_token({"user_id": 42})
        self.assertIsInstance(token, str)
        self.assertGreater(len(token), 0)

    def test_token_contains_supplied_user_id(self):
        token = create_access_token({"user_id": 7})
        payload = jwt.decode(token, os.environ["SECRET_KEY"],
                             algorithms=[os.environ["ALGORITHM"]])
        self.assertEqual(payload["user_id"], 7)

    def test_token_contains_expiry_claim(self):
        token = create_access_token({"user_id": 1})
        payload = jwt.decode(token, os.environ["SECRET_KEY"],
                             algorithms=[os.environ["ALGORITHM"]])
        self.assertIn("exp", payload)

    def test_different_payloads_produce_different_tokens(self):
        self.assertNotEqual(
            create_access_token({"user_id": 1}),
            create_access_token({"user_id": 2})
        )


# Get Current User


class GetCurrentUserShould(unittest.TestCase):

    @patch("common.auth.user_service._get_by_id_internal")
    def test_valid_token_and_active_user_returns_user(self, mock_get):
        user = make_user(user_id=1)
        mock_get.return_value = user
        result = get_current_user(_creds(_valid_token(1)))
        self.assertEqual(result, user)
        mock_get.assert_called_once_with(1)

    def test_malformed_token_raises_401(self):
        with self.assertRaises(HTTPException) as ctx:
            get_current_user(_creds("not.a.real.token"))
        self.assertEqual(ctx.exception.status_code, 401)

    @patch("common.auth.user_service._get_by_id_internal", return_value=None)
    def test_token_for_nonexsitent_user_raises_401(self, mock_get):
        with self.assertRaises(HTTPException) as ctx:
            get_current_user(_creds(_valid_token(999)))
        self.assertEqual(ctx.exception.status_code, 401)
        mock_get.assert_called_once_with(999)

    @patch("common.auth.user_service._get_by_id_internal")
    def test_deleted_user_raises_401(self, mock_get):
        mock_get.return_value = make_user(is_deleted=True)
        with self.assertRaises(HTTPException) as ctx:
            get_current_user(_creds(_valid_token(1)))
        self.assertEqual(ctx.exception.status_code, 401)

    @patch("common.auth.user_service._get_by_id_internal")
    def test_blocked_user_raises_403(self, mock_get):
        mock_get.return_value = make_user(is_blocked=True)
        with self.assertRaises(HTTPException) as ctx:
            get_current_user(_creds(_valid_token(1)))
        self.assertEqual(ctx.exception.status_code, 403)

    def test_token_missing_user_id_claim_raises_401(self):
        token = create_access_token({"irrelevant": "data"})
        with self.assertRaises(HTTPException) as ctx:
            get_current_user(_creds(token))
        self.assertEqual(ctx.exception.status_code, 401)


# Get Optional User


class GetOptionalUserShould(unittest.IsolatedAsyncioTestCase):
    """
    Uses IsolatedAsyncioTestCase (stdlib, Python 3.8+) - no pytest-asyncio
    required.
    """

    async def test_no_credentials_returns_none(self):
        self.assertIsNone(await get_optional_user(None))

    async def test_invalid_token_returns_none_without_raising(self):
        self.assertIsNone(await get_optional_user(_creds("garbage.token.here")))

    @patch("common.auth.user_service._get_by_id_internal")
    async def test_valid_token_and_active_user_returns_user(self, mock_get):
        user = make_user(user_id=1)
        mock_get.return_value = user
        result = await get_optional_user(_creds(_valid_token(1)))
        self.assertEqual(result, user)
        mock_get.assert_called_once_with(1)

    @patch("common.auth.user_service._get_by_id_internal", return_value=None)
    async def test_token_for_nonexistent_user_return_none(self, mock_get):
        result = await get_optional_user(_creds(_valid_token(999)))
        self.assertIsNone(result)

    @patch("common.auth.user_service._get_by_id_internal")
    async def test_blocked_user_returns_none(self, mock_get):
        mock_get.return_value = make_user(is_blocked=True)
        self.assertIsNone(await get_optional_user(_creds(_valid_token(1))))

    @patch("common.auth.user_service._get_by_id_internal")
    async def test_deleted_user_returns_none(self, mock_get):
        mock_get.return_value = make_user(is_deleted=True)
        self.assertIsNone(await get_optional_user(_creds(_valid_token(1))))

    async def test_token_missing_user_id_claim_returns_none(self):
        token = create_access_token({"other": "data"})
        self.assertIsNone(await get_optional_user(_creds(token)))


# Get Current Admin


class GetCurrentAdminShould(unittest.TestCase):

    @patch("common.auth.user_service._get_by_id_internal")
    def test_admin_user_is_returned_unchanged(self, mock_get):
        admin = make_admin(user_id=1)
        mock_get.return_value = admin

        resolved = get_current_user(_creds(_valid_token(1)))
        result = get_current_admin(resolved)

        self.assertEqual(result, admin)
        mock_get.assert_called_once_with(1)

    @patch("common.auth.user_service._get_by_id_internal")
    def test_regular_user_raises_403_with_admin_message(self, mock_get):
        user = make_user(user_id=2)
        mock_get.return_value = user

        resolved = get_current_user(_creds(_valid_token(2)))

        with self.assertRaises(HTTPException) as ctx:
            get_current_admin(resolved)
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("Admin", ctx.exception.detail)


if __name__ == "__main__":
    unittest.main()
