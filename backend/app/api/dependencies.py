from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import Header, HTTPException


async def authenticated_user(authorization: str | None = Header(default=None)) -> UUID:
    """P2 development auth seam; production replaces this with verified Supabase JWT claims."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication is required.")
    token = authorization.removeprefix("Bearer ").strip()
    if not token.startswith("dev-") or len(token) > 200:
        raise HTTPException(status_code=401, detail="The development token is invalid.")
    identity = token.removeprefix("dev-")
    try:
        return UUID(identity)
    except ValueError:
        return uuid5(NAMESPACE_URL, token)
