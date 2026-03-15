from fastapi import APIRouter, Depends
from common.auth import get_current_user
from data.models import InvitationCreate, InvitationUpdate, InvitationStatus
from data.models import BulkInvitationCreate, User, UserRole
from services import invitation_service
from common.response import success
from common.exceptions import UnauthorizedError


invitations_router = APIRouter(prefix='/invitations', tags=['Invitations'])


@invitations_router.post('/')
def create_invitation(
    data: InvitationCreate,
    current_user: User = Depends(get_current_user),
):
    """
    Create new invitation to a private topic.
    Only the topic author can invite.
    """
    invitation = invitation_service.create_invitation(data, current_user.user_id, current_user.role_id)
    return success(data=invitation, message='Invitation sent', status_code=201)


@invitations_router.post('/bulk')
def create_bulk_invitations(
    data: BulkInvitationCreate,
    current_user: User = Depends(get_current_user)
):
    """
    Invite multiple users to a private topic at once.
    Only the topic author can send invitations.
    """
    result = invitation_service.bulk_create_invitations(data, current_user.user_id, current_user.role_id)
    return success(
        data=result,
        message=f'Sent {result.total_invited} invitations',
        status_code=201
    )


# -------------------- Get Invitations --------------------


@invitations_router.get('/')
def get_my_invitations(
    status: int | None = None,
    page: int = 1,
    per_page: int = 20,
    current_user: User = Depends(get_current_user)
):
    """
    Get all invitations for the current user.
    Optional status filter: 0 = PENDING, 1 = ACCEPTED, 2 = DECLINED.
    """
    result = invitation_service.get_user_invitations(
        current_user.user_id,
        status,
        page,
        per_page
    )
    return success(data=result, message='Invitations received')


@invitations_router.get('/{invitation_id}')
def get_invitation(
    invitation_id: int,
    current_user: User = Depends(get_current_user)
):
    """
    Get details of a specific invitation.
    """
    invitation = invitation_service.get_invitation_by_id(invitation_id)

    # Check if user is involved in this invitation
    is_admin = current_user.role_id == UserRole.ADMIN
    if (not is_admin
            and invitation.invited_user_id != current_user.user_id
            and invitation.invited_by_id != current_user.user_id):
        raise UnauthorizedError('Not authorized to view this invitation')

    return success(data=invitation, message='Invitation retrieved')


# -------------------- Update Invitations --------------------


@invitations_router.patch('/{invitation_id}')
def update_invitation(
    invitation_id: int,
    data: InvitationUpdate,
    current_user: User = Depends(get_current_user)
):
    """
    Accept or decline an invitation.
    Only the invited user can update the invitation status.
    """
    invitation = invitation_service.update_invitation_status(
        invitation_id,
        current_user.user_id,
        data
    )
    status_map = {
        InvitationStatus.ACCEPTED: "accepted",
        InvitationStatus.DECLINED: "declined",
        InvitationStatus.PENDING: "pending"
    }
    status_text = status_map.get(data.invitation_status, "updated")
    return success(
        data=invitation,
        message=f'Invitation {status_text}'
    )


# -------------------- Delete Invitations --------------------


@invitations_router.delete('/{invitation_id}')
def delete_invitation(
    invitation_id: int,
    current_user: User = Depends(get_current_user)
):
    """
    Delete an invitation.
    Only the topic author or admin   can delete invitations.
    """
    invitation_service.delete_invitation(
        invitation_id,
        current_user.user_id,
        current_user.role_id
    )
    return success(message='Invitation deleted!')
