"""API endpoints for managing post drafts."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models import Draft, DraftStatus
from app.schemas.drafts import CreateDraftRequest, DraftResponse, UpdateDraftRequest

router = APIRouter(prefix="/drafts", tags=["drafts"])


@router.post("", status_code=201, response_model=DraftResponse)
async def create_draft(
    body: CreateDraftRequest,
    session: AsyncSession = Depends(get_session),
) -> DraftResponse:
    """Create a new post draft."""
    draft = Draft(
        run_id=body.run_id,
        user_id=body.user_id,
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
    user_id: uuid.UUID = Query(...),
    status: DraftStatus | None = Query(None),
    session: AsyncSession = Depends(get_session),
) -> list[DraftResponse]:
    """List drafts for a given user, optionally filtered by status."""
    query = select(Draft).where(Draft.user_id == user_id)
    if status is not None:
        query = query.where(Draft.status == status)
    result = await session.execute(query)
    drafts = result.scalars().all()
    return [DraftResponse.model_validate(d) for d in drafts]


@router.get("/{draft_id}", response_model=DraftResponse)
async def get_draft(
    draft_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> DraftResponse:
    """Get a single draft by ID."""
    result = await session.execute(select(Draft).where(Draft.id == draft_id))
    draft = result.scalar_one_or_none()
    if not draft:
        raise HTTPException(404, "Draft not found")
    return DraftResponse.model_validate(draft)


@router.patch("/{draft_id}", response_model=DraftResponse)
async def update_draft(
    draft_id: uuid.UUID,
    body: UpdateDraftRequest,
    session: AsyncSession = Depends(get_session),
) -> DraftResponse:
    """Update draft fields (only non-None values are applied)."""
    result = await session.execute(select(Draft).where(Draft.id == draft_id))
    draft = result.scalar_one_or_none()
    if not draft:
        raise HTTPException(404, "Draft not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(draft, field, value)

    await session.commit()
    await session.refresh(draft)
    return DraftResponse.model_validate(draft)


@router.delete("/{draft_id}", status_code=204)
async def delete_draft(
    draft_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Delete a draft."""
    result = await session.execute(select(Draft).where(Draft.id == draft_id))
    draft = result.scalar_one_or_none()
    if not draft:
        raise HTTPException(404, "Draft not found")
    await session.delete(draft)
    await session.commit()
