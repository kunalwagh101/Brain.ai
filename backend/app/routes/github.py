from fastapi import APIRouter

from app.routes.github_backfill import router as backfill_router
from app.routes.github_oauth import router as oauth_router
from app.routes.github_webhooks import router as webhooks_router

router = APIRouter()
router.include_router(oauth_router)
router.include_router(backfill_router)
router.include_router(webhooks_router)
