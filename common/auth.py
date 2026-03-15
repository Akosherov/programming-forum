from datetime import datetime, timedelta
from jose import JWTError, jwt
from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer, HTTPBearer, HTTPAuthorizationCredentials
from data.models import User, UserRole
from services import user_service
from common.security import verify_password
import os
from dotenv import load_dotenv


load_dotenv()


SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")
security = HTTPBearer(auto_error=False)


def authenticate_user(username: str, password: str):
    user = user_service._get_user_by_username_internal(username)
    if not user or user.is_deleted or user.is_blocked:
        return False
    if not verify_password(password, user.password):
        return False

    return user


def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
        credentials: HTTPAuthorizationCredentials = Depends(security)
) -> User:
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        user = user_service._get_by_id_internal(user_id)
        if not user or user.is_deleted:
            raise HTTPException(status_code=401, detail="User not found")
        if user.is_blocked:
            raise HTTPException(status_code=403, detail="User account is blocked")
        return user
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def get_optional_user(
        credentials: HTTPAuthorizationCredentials | None = Depends(security)
) -> User | None:
    """
    Get the current user if authentication is provided,
    otherwise return None. This is used for endpoints that work
    with and without authentication. Reactions counts are public
    but if authenticated we show users reaction as well
    Returns:
        User object if valid token provided
        None if no token provided or token is invalid
    """

    if not credentials:
        return None

    try:
        # Decode the token
        payload = jwt.decode(
            credentials.credentials,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )
        user_id: int | None = payload.get("user_id")

        if user_id is None:
            return None
        # Get user from DB
        user = user_service._get_by_id_internal(user_id)
        # Return none if user doesnt exist or is blocked or is deleted.
        if (
            user is None
            or user.is_blocked
            or user.is_deleted
        ):
            return None

        return user
    except JWTError:
        # Invalid token returns none instead of exception
        return None


def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    """
    Verify that the current user is an Admin
    Raises HTTP exception if not
    """
    if current_user.role_id != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )

    return current_user
