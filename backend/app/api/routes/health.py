from typing import Any

from fastapi import APIRouter, Request


router = APIRouter()


@router.get("/health")
async def health(request: Request) -> dict[str, Any]:
    providers = getattr(request.app.state, "provider_configuration", {})
    mode = getattr(request.app.state, "provider_mode", "unconfigured")
    return {"status": "ok", "mode": mode, "providers": providers}
