from fastapi import APIRouter, Depends

from app.auth import get_current_user
from app.models import User
from app.schemas import CurrentUserRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=CurrentUserRead)
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user
