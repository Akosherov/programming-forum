from common.exceptions import NotFoundError, ForbiddenError, UnauthorizedError
from common.exceptions import AppError
from typing import Optional
from data.database import read_query, insert_query, update_query, delete_query
from data.models import InvitationStatus, InvitationCreate, InvitationUpdate
from data.models import InvitationResponse, InvitationListItem, UserRole
from data.models import BulkInvitationCreate, BulkInvitationResponse
from data.models import InvitationList


def _row_to_invitation(row) -> InvitationResponse:
    """
    Convert database row to InvitationResponse model.
    """
    (invitation_id, topic_id, invited_user_id, invited_by_id,
     invitation_status, created_at, topic_title, invited_username, 
     invited_by_username) = row

    return InvitationResponse(
        invitation_id=invitation_id,
        topic_id=topic_id,
        topic_title=topic_title,
        invited_user_id=invited_user_id,
        invited_username=invited_username,
        invited_by_id=invited_by_id,
        invited_by_username=invited_by_username,
        invitation_status=invitation_status,
        created_at=created_at
    )


def create_invitation(
    invitation_data: InvitationCreate,
    invited_by_id: int,
    invited_by_role_id: int
) -> InvitationResponse:

    topic = read_query(
        '''
        SELECT topic_id, is_private, author_id
        FROM topics
        WHERE topic_id = ?
        ''',
        (invitation_data.topic_id,)
    )

    if not topic:
        raise NotFoundError('Topic not found!')
    topic_id, is_private, author_id = topic[0]

    if not is_private:
        raise ForbiddenError('Cannot invite users to public topics!')

    is_admin = invited_by_role_id == UserRole.ADMIN
    if author_id != invited_by_id and not is_admin:
        raise UnauthorizedError('Only topic author or admin can send invitations!')

    invited_user = read_query(
        'SELECT user_id, is_blocked FROM users WHERE user_id = ?',
        (invitation_data.invited_user_id,)
    )

    if not invited_user:
        raise NotFoundError('Invited user not found!')

    if invited_user[0][1]:  # is_blocked
        raise ForbiddenError('Cannot invite blocked users!')

    existing = read_query(
        '''SELECT invitation_id
        FROM topic_invitations
        WHERE topic_id = ? AND invited_user_id = ?
        ''',
        (invitation_data.topic_id, invitation_data.invited_user_id)
    )

    if existing:
        raise ForbiddenError('User already invited to this topic!')

    sql = '''
        INSERT INTO topic_invitations 
        (topic_id, invited_user_id, invited_by_id, invitation_status)
        VALUES (?, ?, ?, ?)
        '''

    invitation_id = insert_query(
        sql,
        (invitation_data.topic_id, invitation_data.invited_user_id,
            invited_by_id, InvitationStatus.PENDING)
    )

    return get_invitation_by_id(invitation_id)


def get_invitation_by_id(invitation_id: int) -> InvitationResponse:
    """
    Get single invitation by ID with all details.
    """
    row = read_query(
        '''
        SELECT
        ti.invitation_id,
        ti.topic_id,
        ti.invited_user_id,
        ti.invited_by_id,
        ti.invitation_status,
        ti.created_at,
        t.title as topic_title,
        u_invited.username as invited_username,
        u_inviter.username as invited_by_username
        FROM topic_invitations ti
        JOIN topics t ON ti.topic_id = t.topic_id
        JOIN users u_invited ON ti.invited_user_id = u_invited.user_id
        JOIN users u_inviter ON ti.invited_by_id = u_inviter.user_id
        WHERE ti.invitation_id = ?
        ''',
        (invitation_id,)
    )

    if not row:
        raise NotFoundError('Invitation not found!')

    return _row_to_invitation(row[0])


def get_user_invitations(
    user_id: int,
    status_filter: Optional[int] = None,
    page: int = 1,
    per_page: int = 20
) -> InvitationList:

    # Base query
    where_clause = 'WHERE ti.invited_user_id = ?'
    params = [user_id]

    # Add status filter if provided
    if status_filter is not None:
        where_clause += ' AND ti.invitation_status = ?'
        params.append(status_filter)

    # Get total count
    count_query = f'''
        SELECT COUNT(*)
        FROM topic_invitations ti
        {where_clause}
    '''
    total = read_query(count_query, tuple(params))[0][0]

    offset = (page - 1) * per_page
    params.extend([per_page, offset])

    rows = read_query(
        f'''
        SELECT
            ti.invitation_id,
            ti.topic_id,
            t.title as topic_title,
            u.username as invited_by_username,
            ti.invitation_status,
            ti.created_at
        FROM topic_invitations ti
        JOIN topics t ON ti.topic_id = t.topic_id
        JOIN users u ON ti.invited_by_id = u.user_id
        {where_clause}
        ORDER BY ti.created_at DESC
        LIMIT ? OFFSET ?
        ''',
        tuple(params)
    )

    invitations = [
        InvitationListItem(
            invitation_id=row[0],
            topic_id=row[1],
            topic_title=row[2],
            invited_by_username=row[3],
            invitation_status=row[4],
            created_at=row[5]

        )
        for row in rows
    ]

    return InvitationList(
        invitations=invitations,
        total=total,
        page=page,
        per_page=per_page
    )


def update_invitation_status(
    invitation_id: int,
    user_id: int,
    status_update: InvitationUpdate
) -> InvitationResponse:

    # Only invited user can update their invitation

    invitation = read_query(
        '''
        SELECT invited_user_id, invitation_status, topic_id
        FROM topic_invitations
        WHERE invitation_id = ?
        ''',
        (invitation_id,)
    )

    if not invitation:
        raise NotFoundError('Invitation not found!')

    invited_user_id, current_status, topic_id = invitation[0]

    if invited_user_id != user_id:
        raise UnauthorizedError('Only invited user can update invitation status!')

    if current_status != InvitationStatus.PENDING:
        raise ForbiddenError('Can only update pending invitations!')

    # Update the status
    update_query(
        '''
        UPDATE topic_invitations
        SET invitation_status = ?
        WHERE invitation_id = ?
        ''',
        (status_update.invitation_status, invitation_id)
    )

    # If accepted add user to topic_participants

    if status_update.invitation_status == InvitationStatus.ACCEPTED:
        # Check if already a participant

        existing_participant = read_query(
            '''
            SELECT 1 FROM topic_participants
            WHERE topic_id = ? AND user_id = ?
            ''',
            (topic_id, user_id)
        )

        if not existing_participant:
            insert_query(
                'INSERT INTO topic_participants (topic_id, user_id) VALUES (?, ?)',
                (topic_id, user_id)
            )

    return get_invitation_by_id(invitation_id)


def delete_invitation(invitation_id: int, user_id: int, user_role_id: int) -> None:
    '''
    Delete an invitation.
    Only topic author can delete invitations.
    '''
    # Get invitation and topic info
    invitation = read_query(
        '''
        SELECT ti.topic_id, t.author_id
        FROM topic_invitations ti
        JOIN topics t on ti.topic_id = t.topic_id
        WHERE ti.invitation_id = ?
        ''',
        (invitation_id,)
    )

    if not invitation:
        raise NotFoundError('Invitation not found!')

    topic_id, author_id = invitation[0]

    # Check if user is topic author

    is_admin = user_role_id == UserRole.ADMIN
    if author_id != user_id and not is_admin:
        raise UnauthorizedError('Only topic author or admin can delete invitations!')

    delete_query(
        'DELETE FROM topic_invitations WHERE invitation_id = ?',
        (invitation_id, )
    )


def bulk_create_invitations(
    bulk_data: BulkInvitationCreate,
    invited_by_id: int,
    invited_by_role_id: int
) -> BulkInvitationResponse:
    '''
    Invite multiple users to a topic at once.
    Returns success / failure for each user
    '''
    successful = []
    failed = []

    for user_id in bulk_data.invited_user_ids:
        try:
            invitation_data = InvitationCreate(
                topic_id=bulk_data.topic_id,
                invited_user_id=user_id
            )
            create_invitation(invitation_data, invited_by_id, invited_by_role_id)
            successful.append(user_id)

        except AppError as e:
            failed.append({
                'user_id': user_id,
                'reason': e.message
            })

        except Exception:
            failed.append({
                'user_id': user_id,
                'reason': 'Unexpected Error'
            })

    return BulkInvitationResponse(
        topic_id=bulk_data.topic_id,
        successful_invitations=successful,
        failed_invitations=failed,
        total_invited=len(successful)
    )
