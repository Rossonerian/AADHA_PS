"""HTTP endpoints for user profile updates and onboarding completion."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import User, current_user
from app.core.db import get_db
from app.profiles.schemas import ProfileResponse, ProfileUpdateRequest, UserProfileOut
from app.profiles.service import complete_onboarding, update_profile

router = APIRouter(tags=["profiles"])


@router.patch("/me/profile", response_model=ProfileResponse)
def patch_my_profile(
    payload: ProfileUpdateRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ProfileResponse:
    """Update the authenticated user's profile preferences."""
    record = update_profile(db, user.id, payload)
    return ProfileResponse(
        profile=UserProfileOut.model_validate(record),
        onboarding_completed=record.onboarding_completed_at is not None,
        data_origin="real",
    )


@router.post("/me/onboarding/complete", response_model=ProfileResponse)
def complete_my_onboarding(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ProfileResponse:
    """Mark the authenticated user's first-run onboarding as completed."""
    record = complete_onboarding(db, user.id)
    return ProfileResponse(
        profile=UserProfileOut.model_validate(record),
        onboarding_completed=True,
        data_origin="real",
    )
