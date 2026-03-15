from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from common.auth import authenticate_user, create_access_token
from common.response import success
from common.exceptions import UnauthorizedError
from data.models import UserCreate, UserPublic
from services import user_service


auth_router = APIRouter(prefix='/auth', tags=['Auth'])


@auth_router.post('/register')
def register_user(user: UserCreate):
    created_user = user_service.create_user(user)
    return success(
        data=UserPublic.from_user(created_user),
        message="User created",
        status_code=201
    )


@auth_router.post('/login')
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise UnauthorizedError("Invalid credentials")

    access_token = create_access_token({'user_id': user.user_id})
    return success(
        data={'access_token': access_token, 'token_type': 'bearer'},
        message="Login successful"
    )
