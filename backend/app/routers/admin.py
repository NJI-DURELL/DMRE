# =============================================================================
# backend/app/routers/admin.py
# Operational admin endpoints. Strictly count-and-aggregate; admins NEVER
# read another user's captured page contents through this router.
#
# Promote a user to admin from the shell:
#     cd backend && .venv\Scripts\python.exe -m app.cli grant-admin EMAIL
# =============================================================================

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.blockchain_record import BlockchainRecord
from app.models.memory import Memory
from app.models.query_log import QueryLog
from app.models.user import User
from app.schemas.admin import AdminStats, AdminUserRow

router = APIRouter()


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Reusable guard. Returns the user only if is_admin=true."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required.",
        )
    return current_user


@router.get(
    "/admin/stats",
    response_model=AdminStats,
    summary="Aggregate operational stats (no per-user data exposed).",
)
async def stats(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> AdminStats:
    now   = datetime.now(timezone.utc)
    day   = now - timedelta(days=1)
    week  = now - timedelta(days=7)

    async def scalar(stmt) -> int:
        return int((await db.execute(stmt)).scalar() or 0)

    return AdminStats(
        total_users          = await scalar(select(func.count()).select_from(User)),
        admins               = await scalar(select(func.count()).where(User.is_admin == True)),
        users_signed_up_24h  = await scalar(select(func.count()).where(User.created_at >= day)),
        users_signed_up_7d   = await scalar(select(func.count()).where(User.created_at >= week)),
        total_memories       = await scalar(select(func.count()).select_from(Memory)),
        memories_24h         = await scalar(select(func.count()).where(Memory.created_at >= day)),
        total_searches       = await scalar(select(func.count()).select_from(QueryLog)),
        searches_24h         = await scalar(select(func.count()).where(QueryLog.created_at >= day)),
        blockchain_anchored  = await scalar(select(func.count()).select_from(BlockchainRecord)),
    )


@router.get(
    "/admin/users",
    response_model=list[AdminUserRow],
    summary="Roster of registered users (no content access).",
)
async def list_users(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> list[AdminUserRow]:
    # Memory count per user — joined aggregate so we don't N+1.
    mem_count = (
        select(Memory.user_id, func.count(Memory.id).label("c"))
        .group_by(Memory.user_id)
        .subquery()
    )
    last_q = (
        select(QueryLog.user_id, func.max(QueryLog.created_at).label("ts"))
        .group_by(QueryLog.user_id)
        .subquery()
    )

    stmt = (
        select(User, mem_count.c.c, last_q.c.ts)
        .outerjoin(mem_count, User.id == mem_count.c.user_id)
        .outerjoin(last_q,    User.id == last_q.c.user_id)
        .order_by(desc(User.created_at))
        .limit(limit)
        .offset(offset)
    )
    rows = (await db.execute(stmt)).all()

    return [
        AdminUserRow(
            id=u.id,
            email=u.email,
            username=u.username,
            is_admin=u.is_admin,
            created_at=u.created_at,
            memory_count=int(c or 0),
            last_search_at=ts,
        )
        for (u, c, ts) in rows
    ]


@router.delete(
    "/admin/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Delete a user account (and ALL their data) — abuse / GDPR removals.",
)
async def admin_delete_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> None:
    if user_id == admin.id:
        # Admins must use /api/account to remove themselves so the act is intentional.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admins cannot delete themselves through this endpoint.",
        )

    target = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    # Best-effort vector cleanup before the cascade fires.
    from app.services import vector_store  # noqa: PLC0415
    mem_ids = [r[0] for r in (await db.execute(
        select(Memory.id).where(Memory.user_id == user_id)
    )).all()]
    for mid in mem_ids:
        try:
            vector_store.delete_memory_chunks(mid)
        except Exception:  # noqa: BLE001
            pass

    await db.delete(target)
