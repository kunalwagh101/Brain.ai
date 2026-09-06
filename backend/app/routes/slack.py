from fastapi import APIRouter

from app.routes.slack_channels import router as channels_router
from app.routes.slack_oauth import router as oauth_router
from app.routes.slack_webhooks import router as webhooks_router

router = APIRouter()
router.include_router(oauth_router)
router.include_router(channels_router)
router.include_router(webhooks_router)
