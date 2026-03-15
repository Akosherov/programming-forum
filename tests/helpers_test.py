"""
Shared test helpers and model factories.
Sets the required environment variables BEFORE any application module is
imported so that common/auth.py and data/database.py do not raise on load.
Volatile dependencies (database, JWT, bcrypt) are mocked at the call site.
Stable dependencies (Pydantic models, custom exceptions, pure logic) are
used directly — they do not need to be isolated.
"""

import os
from data.models import User, UserRole


# Env variables must be set before any app import
os.environ.setdefault("SECRET_KEY", "test_only_secret_key_do_not_use_in_prod")
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "3306")
os.environ.setdefault("DB_NAME", "test_db")


# Model Factories


def make_user(
        user_id: int = 1,
        first_name: str = "John",
        last_name: str = "Doe",
        email: str = "john@example.com",
        username: str = "johndoe",
        password: str = "hashed_password",
        is_blocked: bool = False,
        is_deleted: bool = False,
        role_id: int = UserRole.USER,
) -> User:
    return User(
        user_id=user_id,
        first_name=first_name,
        last_name=last_name,
        email=email,
        username=username,
        password=password,
        is_blocked=is_blocked,
        is_deleted=is_deleted,
        role_id=role_id
    )


def make_admin(
        user_id: int = 99,
        username: str = "admin_user",
        **kwargs
) -> User:
    return make_user(
        user_id=user_id,
        username=username,
        role_id=UserRole.ADMIN,
        **kwargs
    )


def make_user_row(
        user_id=1,
        first_name="John",
        last_name="Doe",
        email="jdoe@example.com",
        username="jdoe",
        password="hashed",
        is_blocked=0,
        is_deleted=0,
        role_id=UserRole.USER
) -> tuple:
    """
    Raw DB row tuple matching the users table column order.
    """
    return (user_id, first_name, last_name, email, username,
            password, is_blocked, is_deleted, role_id)
