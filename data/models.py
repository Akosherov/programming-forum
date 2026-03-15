from pydantic import BaseModel, EmailStr, Field, ConfigDict
from datetime import datetime


# -----------------  User Models -----------------


class UserRole:
    ADMIN = 1
    USER = 2


class UserCreate(BaseModel):
    first_name: str = Field(min_length=2, max_length=32)
    last_name: str = Field(min_length=2, max_length=32)
    email: EmailStr
    username: str = Field(min_length=2, max_length=16)
    password: str


class User(UserCreate):
    user_id: int
    is_blocked: bool = False
    is_deleted: bool = False
    role_id: int

    @classmethod
    def from_query_result(
        cls, user_id, first_name, last_name, email,
        username, password, is_blocked, is_deleted, role_id
    ):
        return cls(
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


class UserPublic(BaseModel):
    """ Public facing User representation. Hides sensitive fields. """
    user_id: int
    first_name: str
    last_name: str
    username: str
    is_deleted: bool = False

    @classmethod
    def from_user(cls, user: User):
        return cls(
            user_id=user.user_id,
            first_name=user.first_name,
            last_name=user.last_name,
            username=user.username,
            is_deleted=user.is_deleted
        )


class UserUpdate(BaseModel):
    # Optional so admins updating other user don't need to supply a password
    current_password: str | None = None
    first_name: str | None = Field(None, min_length=2, max_length=32)
    last_name: str | None = Field(None, min_length=2, max_length=32)
    email: EmailStr | None = None
    password: str | None = None


class UserDelete(BaseModel):
    """ Payload for self deletion, password required. """
    password: str
    reason: str | None = None


class UserListResponse(BaseModel):
    """ Paginated list of Users. """
    users: list[UserPublic]
    total: int
    page: int
    per_page: int


# -----------------  Topic Models -----------------


class TopicCreate(BaseModel):
    title: str = Field(min_length=16, max_length=128)
    content: str = Field(min_length=32, max_length=8192)
    is_private: bool = False  # False = public, True = private


class TopicUpdate(BaseModel):
    # All fields are optional so callers can update only what they need to.
    title: str | None = Field(None, min_length=16, max_length=128)
    content: str | None = Field(None, min_length=32, max_length=8192)
    is_private: bool | None = None


class TopicResponse(BaseModel):
    topic_id: int
    title: str
    content: str
    is_locked: bool
    is_private: bool
    created_at: datetime
    author_id: int
    author_username: str    # Joined from user table
    reply_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class TopicListItem(BaseModel):
    topic_id: int
    title: str
    is_locked: bool
    is_private: bool
    created_at: datetime
    author_username: str
    reply_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class TopicList(BaseModel):
    topics: list[TopicListItem]
    total: int
    page: int
    per_page: int


# -----------------  Reaction Models -----------------


class ReactionSummary(BaseModel):
    likes: int
    dislikes: int
    user_reaction: bool | None = None  # None if no reaction, True if Like, False if Dislike.


# -----------------  Invitation Models -----------------


class InvitationStatus:  # Update default in the db diagram to show 0
    PENDING = 0
    ACCEPTED = 1
    DECLINED = 2


class InvitationCreate(BaseModel):
    topic_id: int = Field(gt=0)
    invited_user_id: int = Field(gt=0)

    # This part isn't required but it's nice for documentation
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "topic_id": 5,
                "invited_user_id": 3
            }
        }
    )


class InvitationUpdate(BaseModel):
    invitation_status: int = Field(
        ge=0,
        le=2,
        description='Status: 0=PENDING, 1=ACCEPTED, 2=DECLINED'
    )


class InvitationResponse(BaseModel):
    invitation_id: int
    topic_id: int
    topic_title: str                        # Joined from topics table
    invited_user_id: int
    invited_username: str                   # Joined from users table
    invited_by_id: int
    invited_by_username: str                # Joined from users table
    invitation_status: int                  # 0=PENDING, 1=ACCEPTED, 2=DECLINED
    created_at: datetime | None = None

    @property
    def status_text(self) -> str:
        '''Human-readable status'''
        if self.invitation_status == InvitationStatus.PENDING:
            return 'Pending'
        elif self.invitation_status == InvitationStatus.ACCEPTED:
            return 'Accepted'
        elif self.invitation_status == InvitationStatus.DECLINED:
            return 'Declined'

        return 'Unknown'

    # This part isn't required but it's nice for documentation
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            'example': {
                'invitation_id': 1,
                'topic_id': 5,
                'topic_title': 'Python Basics',
                'invited_user_id': 3,
                'invited_username': 'pitbull',
                'invited_by_id': 1,
                'invited_by_username': 'britney_spears',
                'invitation_status': 0,
                'created_at': '2026-02-16T10:30:00'
            }
        }
    )


class InvitationListItem(BaseModel):
    invitation_id: int
    topic_id: int
    topic_title: str
    invited_by_username: str
    invitation_status: int
    created_at: datetime | None = None

    # This part isn't required but it's nice for documentation
    model_config = ConfigDict(from_attributes=True)


class InvitationList(BaseModel):
    # Paginated List of invitations
    invitations: list[InvitationListItem]
    total: int
    page: int
    per_page: int


# -----------------  Bulk Invitation Model -----------------


class BulkInvitationCreate(BaseModel):
    topic_id: int = Field(gt=0)
    invited_user_ids: list[int] = Field(
        min_length=1,
        max_length=50,
        description='List of user IDs to invite (max 50)'
    )

    # This part isn't required but it's nice for documentation
    model_config = ConfigDict(
        json_schema_extra={
            'example': {
                'topic_id': 5,
                'invited_user_ids': [2, 3, 4]
            }
        }
    )


class BulkInvitationResponse(BaseModel):
    topic_id: int
    successful_invitations: list[int]
    failed_invitations: list[dict]
    total_invited: int

    # This part isn't required but it's nice for documentation
    model_config = ConfigDict(
        json_schema_extra={
            'example': {
                'topic_id': 5,
                'successful_invitations': [2, 3],
                'failed_invitations': [
                    {'user_id': 4, 'reason': 'User already invited'}
                ],
                'total_invited': 2
            }
        }
    )


# -----------------  Reply Models -----------------


class ReplyCreate(BaseModel):
    topic_id: int = Field(gt=0)
    content: str = Field(min_length=2, max_length=8192)


class ReplyUpdate(BaseModel):
    content: str = Field(min_length=2, max_length=8192)


class ReplyResponse(BaseModel):
    id: int
    content: str
    author_id: int
    author_username: str
    likes: int
    dislikes: int
    created_at: datetime
    is_best: bool = False
    current_user_reaction: str | None = None  # 'like', 'dislike' or None

    model_config = ConfigDict(from_attributes=True)


class ReplyList(BaseModel):
    replies: list[ReplyResponse]
    total: int
    page: int
    per_page: int
