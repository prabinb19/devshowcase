"""API endpoints for managing post drafts."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models import Draft, DraftStatus
from app.routes.deps import AuthenticatedUser, verify_auth
from app.schemas.drafts import CreateDraftRequest, DraftResponse, UpdateDraftRequest

router = APIRouter(prefix="/drafts", tags=["drafts"])


@router.post("", status_code=201, response_model=DraftResponse)
async def create_draft(
    body: CreateDraftRequest,
    auth: AuthenticatedUser = Depends(verify_auth),
    session: AsyncSession = Depends(get_session),
) -> DraftResponse:
    """Create a new post draft."""
    draft = Draft(
        run_id=body.run_id,
        user_id=auth.db_user.id,  # always use authenticated user
        body=body.body,
        first_comment=body.first_comment,
        screenshot_urls=body.screenshot_urls,
        alt_texts=body.alt_texts,
    )
    session.add(draft)
    await session.commit()
    await session.refresh(draft)
    return DraftResponse.model_validate(draft)


@router.get("", response_model=list[DraftResponse])
async def list_drafts(
    status: DraftStatus | None = Query(None),
    auth: AuthenticatedUser = Depends(verify_auth),
    session: AsyncSession = Depends(get_session),
) -> list[DraftResponse]:
    """List drafts for the authenticated user, optionally filtered by status."""
    query = select(Draft).where(Draft.user_id == auth.db_user.id)
    if status is not None:
        query = query.where(Draft.status == status)
    result = await session.execute(query)
    drafts = result.scalars().all()
    return [DraftResponse.model_validate(d) for d in drafts]


@router.get("/{draft_id}", response_model=DraftResponse)
async def get_draft(
    draft_id: uuid.UUID,
    auth: AuthenticatedUser = Depends(verify_auth),
    session: AsyncSession = Depends(get_session),
) -> DraftResponse:
    """Get a single draft by ID."""
    result = await session.execute(select(Draft).where(Draft.id == draft_id))
    draft = result.scalar_one_or_none()
    if not draft:
        raise HTTPException(404, "Draft not found")
    if draft.user_id != auth.db_user.id:
        raise HTTPException(403, "Not authorized to access this draft")
    return DraftResponse.model_validate(draft)


@router.patch("/{draft_id}", response_model=DraftResponse)
async def update_draft(
    draft_id: uuid.UUID,
    body: UpdateDraftRequest,
    auth: AuthenticatedUser = Depends(verify_auth),
    session: AsyncSession = Depends(get_session),
) -> DraftResponse:
    """Update draft fields (only non-None values are applied)."""
    result = await session.execute(select(Draft).where(Draft.id == draft_id))
    draft = result.scalar_one_or_none()
    if not draft:
        raise HTTPException(404, "Draft not found")
    if draft.user_id != auth.db_user.id:
        raise HTTPException(403, "Not authorized to modify this draft")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(draft, field, value)

    await session.commit()
    await session.refresh(draft)
    return DraftResponse.model_validate(draft)


@router.delete("/{draft_id}", status_code=204)
async def delete_draft(
    draft_id: uuid.UUID,
    auth: AuthenticatedUser = Depends(verify_auth),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Delete a draft."""
    result = await session.execute(select(Draft).where(Draft.id == draft_id))
    draft = result.scalar_one_or_none()
    if not draft:
        raise HTTPException(404, "Draft not found")
    if draft.user_id != auth.db_user.id:
        raise HTTPException(403, "Not authorized to delete this draft")
    await session.delete(draft)
    await session.commit()
