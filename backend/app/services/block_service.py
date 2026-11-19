from sqlalchemy import select, or_, and_
from sqlalchemy.orm import Session
from app.models.block import Block


def is_user_blocked(db: Session, user_a_id: int, user_b_id: int) -> bool:
    """
    Check if either user has blocked the other (FR-072).
    A blocked user cannot send split requests or group invites to the blocker,
    and a blocker cannot interact with a blocked user.
    """
    if user_a_id == user_b_id:
        return False

    stmt = select(Block.id).where(
        or_(
            and_(Block.blocker_id == user_a_id, Block.blocked_id == user_b_id),
            and_(Block.blocker_id == user_b_id, Block.blocked_id == user_a_id),
        )
    ).limit(1)
    return db.scalar(stmt) is not None
