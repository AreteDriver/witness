"""Lightweight in-memory error tracking for unhandled exceptions.

Captures the last 100 unhandled errors into a ring buffer (deque).
Exposes via GET /admin/errors (admin-gated, same pattern as /admin/analytics).
"""

import time
import traceback
from collections import deque
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from backend.api.rate_limit import limiter
from backend.api.tier_gate import is_admin_wallet

router = APIRouter()

# Ring buffer — last 100 errors, no database, no external deps
_error_buffer: deque[dict[str, Any]] = deque(maxlen=100)


def capture_error(request: Request, exc: Exception) -> None:
    """Record an unhandled exception into the ring buffer."""
    tb_lines = traceback.format_exception(type(exc), exc, exc.__traceback__)
    _error_buffer.append(
        {
            "timestamp": int(time.time()),
            "path": str(request.url.path),
            "method": request.method,
            "error_type": type(exc).__name__,
            "message": str(exc),
            "traceback": "".join(tb_lines[-5:]),
        }
    )


def get_errors() -> list[dict[str, Any]]:
    """Return all captured errors (most recent last)."""
    return list(_error_buffer)


@router.get("/admin/errors")
@limiter.limit("30/minute")
async def get_admin_errors(request: Request):
    """Recent unhandled exceptions — admin only."""
    wallet = request.headers.get("X-Wallet-Address", "")
    if not wallet or not is_admin_wallet(wallet):
        raise HTTPException(403, "Admin access required.")
    errors = get_errors()
    return {"count": len(errors), "errors": errors}
