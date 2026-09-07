"""Auth-adjacent helpers for the HTTP API.

Right now we don't own an identity provider; the API accepts an opaque
``X-User-Id`` header instead. The header is treated as a stable per-user
key and is threaded through every read / write path so datasets stay
isolated between users. Absence of the header preserves the old
"single-tenant" behaviour \u2014 zero disruption to existing clients.

When we wire a real identity provider later (JWT-in-Authorization-Bearer,
Supabase Auth, etc.), only this file needs to change: swap the header
parsing for a signature verification step and return the resolved
subject. Everything downstream keeps working unchanged.
"""

from __future__ import annotations

from typing import Optional

from fastapi import Header


async def get_optional_user_id(
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
) -> Optional[str]:
    """FastAPI dependency \u2014 returns the caller's user id if present.

    Currently reads ``X-User-Id`` verbatim. When empty / missing we return
    ``None`` and the request runs in unscoped mode (backward compatible).
    """
    if x_user_id is None:
        return None
    value = x_user_id.strip()
    return value or None
