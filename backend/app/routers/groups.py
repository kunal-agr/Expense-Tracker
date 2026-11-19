from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy import select, func, desc, and_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.group import Group, GroupMember
from app.models.notification import Notification
from app.schemas.group import (
    GroupCreate,
    GroupUpdate,
    GroupInviteRequest,
    GroupResponse,
    GroupDetailResponse,
    GroupMemberResponse,
)
from app.auth.dependencies import get_current_user
from app.services.block_service import is_user_blocked
from app.errors import AppException

router = APIRouter(prefix="/groups", tags=["Groups"])


@router.post("", response_model=GroupDetailResponse, status_code=status.HTTP_201_CREATED)
def create_group(
    payload: GroupCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new group (FR-073). Current user is creator and first active member."""
    now = datetime.now(timezone.utc)
    group = Group(
        name=payload.name.strip(),
        creator_id=current_user.id,
        created_at=now,
    )
    db.add(group)
    db.flush()

    member = GroupMember(
        group_id=group.id,
        user_id=current_user.id,
        joined_at=now,
        status="active",
    )
    db.add(member)
    db.commit()
    db.refresh(group)

    return GroupDetailResponse(
        id=group.id,
        name=group.name,
        creator_id=group.creator_id,
        creator_username=current_user.username,
        created_at=group.created_at,
        member_count=1,
        user_status="active",
        members=[
            GroupMemberResponse(
                id=member.id,
                user_id=current_user.id,
                username=current_user.username,
                joined_at=now,
                status="active",
                is_creator=True,
            )
        ],
    )


@router.get("", response_model=List[GroupResponse])
def list_groups(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all groups the current user is a member of or invited to (FR-073)."""
    stmt = (
        select(Group, GroupMember.status.label("user_status"), User.username.label("creator_name"))
        .join(GroupMember, GroupMember.group_id == Group.id)
        .outerjoin(User, User.id == Group.creator_id)
        .where(GroupMember.user_id == current_user.id)
        .order_by(desc(Group.created_at))
    )
    results = db.execute(stmt).all()

    response = []
    for grp, u_status, creator_name in results:
        m_count = db.scalar(
            select(func.count(GroupMember.id)).where(
                GroupMember.group_id == grp.id, GroupMember.status == "active"
            )
        ) or 0
        response.append(
            GroupResponse(
                id=grp.id,
                name=grp.name,
                creator_id=grp.creator_id,
                creator_username=creator_name,
                created_at=grp.created_at,
                member_count=m_count,
                user_status=u_status,
            )
        )
    return response


@router.get("/{group_id}", response_model=GroupDetailResponse)
def get_group(
    group_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve group details and active/invited members."""
    membership = db.scalar(
        select(GroupMember).where(
            GroupMember.group_id == group_id, GroupMember.user_id == current_user.id
        )
    )
    if not membership:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="GROUP_NOT_FOUND",
            message="Group not found or you are not a member.",
        )

    group = db.scalar(select(Group).where(Group.id == group_id))
    creator = db.scalar(select(User).where(User.id == group.creator_id)) if group.creator_id else None

    # Members list
    m_stmt = (
        select(GroupMember, User.username)
        .join(User, User.id == GroupMember.user_id)
        .where(GroupMember.group_id == group_id)
        .order_by(GroupMember.joined_at.asc().nulls_last())
    )
    m_results = db.execute(m_stmt).all()

    members_resp = [
        GroupMemberResponse(
            id=m.id,
            user_id=m.user_id,
            username=u_name,
            joined_at=m.joined_at,
            status=m.status,
            is_creator=(m.user_id == group.creator_id),
        )
        for m, u_name in m_results
    ]

    active_count = sum(1 for m in members_resp if m.status == "active")

    return GroupDetailResponse(
        id=group.id,
        name=group.name,
        creator_id=group.creator_id,
        creator_username=creator.username if creator else None,
        created_at=group.created_at,
        member_count=active_count,
        user_status=membership.status,
        members=members_resp,
    )


@router.patch("/{group_id}", response_model=GroupDetailResponse)
def rename_group(
    group_id: int,
    payload: GroupUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Rename group (creator only, FR-076)."""
    group = db.scalar(select(Group).where(Group.id == group_id))
    if not group:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="GROUP_NOT_FOUND",
            message="Group not found.",
        )

    if group.creator_id != current_user.id:
        raise AppException(
            status_code=status.HTTP_403_FORBIDDEN,
            code="CREATOR_ONLY",
            message="Only the group creator can rename this group.",
        )

    group.name = payload.name.strip()
    db.commit()
    return get_group(group_id, current_user, db)


@router.delete("/{group_id}", status_code=status.HTTP_200_OK)
def delete_group(
    group_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete group (creator only, FR-076). Past split history is untouched (FR-078)."""
    group = db.scalar(select(Group).where(Group.id == group_id))
    if not group:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="GROUP_NOT_FOUND",
            message="Group not found.",
        )

    if group.creator_id != current_user.id:
        raise AppException(
            status_code=status.HTTP_403_FORBIDDEN,
            code="CREATOR_ONLY",
            message="Only the group creator can delete this group.",
        )

    db.delete(group)
    db.commit()
    return {"message": "Group deleted successfully."}


@router.post("/{group_id}/invite", status_code=status.HTTP_200_OK)
def invite_member(
    group_id: int,
    payload: GroupInviteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Invite user by username to group (FR-074). Any active member can invite.
    Blocked users cannot be invited (generic error message, FR-072).
    """
    membership = db.scalar(
        select(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.user_id == current_user.id,
            GroupMember.status == "active",
        )
    )
    if not membership:
        raise AppException(
            status_code=status.HTTP_403_FORBIDDEN,
            code="NOT_ACTIVE_MEMBER",
            message="Only active members can invite users to this group.",
        )

    group = db.scalar(select(Group).where(Group.id == group_id))
    target_username = payload.username.strip().lower()
    target_user = db.scalar(select(User).where(User.username == target_username))

    # Generic failure if user not found or either party blocked (FR-072)
    if not target_user or is_user_blocked(db, current_user.id, target_user.id):
        raise AppException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="CANNOT_INVITE_USER",
            message="Unable to invite this user to the group.",
        )

    # Check if target is already member or invited
    existing_mem = db.scalar(
        select(GroupMember).where(
            GroupMember.group_id == group_id, GroupMember.user_id == target_user.id
        )
    )
    if existing_mem:
        if existing_mem.status == "active":
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="ALREADY_MEMBER",
                message="User is already an active member of this group.",
            )
        else:
            return {"message": "User already has a pending invitation."}

    new_member = GroupMember(
        group_id=group_id,
        user_id=target_user.id,
        joined_at=None,
        status="invited",
    )
    db.add(new_member)

    # Send in-app notification to invitee
    notif = Notification(
        user_id=target_user.id,
        type="group_invite",
        payload={
            "message": f"{current_user.username} invited you to join group '{group.name}'.",
            "group_id": group.id,
            "group_name": group.name,
            "inviter": current_user.username,
        },
        is_read=False,
    )
    db.add(notif)
    db.commit()

    return {"message": f"Invitation sent to {target_username}."}


@router.post("/{group_id}/accept", status_code=status.HTTP_200_OK)
def accept_group_invite(
    group_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Accept group invitation to become an active member (FR-074)."""
    membership = db.scalar(
        select(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.user_id == current_user.id,
            GroupMember.status == "invited",
        )
    )
    if not membership:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="INVITATION_NOT_FOUND",
            message="No pending invitation found for this group.",
        )

    membership.status = "active"
    membership.joined_at = datetime.now(timezone.utc)
    db.commit()
    return {"message": "Group invitation accepted."}


@router.post("/{group_id}/leave", status_code=status.HTTP_200_OK)
def leave_group(
    group_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Leave group (FR-075).
    - If creator leaves: earliest-joined remaining active member becomes creator (FR-077).
    - If last member leaves: group is deleted automatically (FR-078).
    - Pending split requests remain valid (FR-079).
    """
    membership = db.scalar(
        select(GroupMember).where(
            GroupMember.group_id == group_id, GroupMember.user_id == current_user.id
        )
    )
    if not membership:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="NOT_MEMBER",
            message="You are not a member of this group.",
        )

    group = db.scalar(select(Group).where(Group.id == group_id))
    db.delete(membership)
    db.flush()

    # Check remaining active members
    remaining_members = db.scalars(
        select(GroupMember)
        .where(GroupMember.group_id == group_id, GroupMember.status == "active")
        .order_by(GroupMember.joined_at.asc(), GroupMember.id.asc())
    ).all()

    if not remaining_members:
        # Last member left: auto-delete group (FR-078)
        db.delete(group)
        db.commit()
        return {"message": "You left the group. The group had no remaining members and was deleted."}

    # If leaving member was creator: transfer to earliest-joined active remaining member (FR-077)
    if group.creator_id == current_user.id:
        group.creator_id = remaining_members[0].user_id

    db.commit()
    return {"message": "You have left the group."}
