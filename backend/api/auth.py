"""EVE SSO (OAuth2) authentication routes.

Implements CCP's EVE Online SSO for character identity verification.
Users prove they own a character, which can then be cross-referenced
with on-chain EVE Frontier data.

Flow:
  1. GET /api/auth/eve/login  → redirect URL to CCP SSO
  2. GET /api/auth/eve/callback → exchange code for tokens, fetch character
  3. GET /api/auth/eve/me → return current session character info
  4. POST /api/auth/eve/logout → clear session
"""

import hashlib
import secrets
import time

import httpx
from fastapi import APIRouter, HTTPException, Query, Request

from backend.core.config import settings
from backend.core.logger import get_logger
from backend.db.database import get_db

logger = get_logger("auth")

router = APIRouter(prefix="/auth")

EVE_SSO_AUTH_URL = "https://login.eveonline.com/v2/oauth/authorize"
EVE_SSO_TOKEN_URL = "https://login.eveonline.com/v2/oauth/token"
EVE_SSO_VERIFY_URL = "https://esi.evetech.net/verify/"

# In-memory state store for CSRF protection (short-lived)
_pending_states: dict[str, float] = {}
STATE_TTL = 300  # 5 minutes


def _clean_expired_states() -> None:
    """Remove expired OAuth states."""
    now = time.time()
    expired = [k for k, v in _pending_states.items() if now - v > STATE_TTL]
    for k in expired:
        del _pending_states[k]


def _generate_session_token() -> str:
    """Generate a cryptographically secure session token."""
    return secrets.token_urlsafe(32)


@router.get("/eve/login")
async def eve_sso_login(
    redirect_uri: str = Query(default=""),
):
    """Generate EVE SSO authorization URL.

    Returns the URL the frontend should redirect to for CCP login.
    """
    if not settings.EVE_SSO_CLIENT_ID:
        raise HTTPException(
            status_code=503,
            detail="EVE SSO not configured. Set WITNESS_EVE_SSO_CLIENT_ID.",
        )

    state = secrets.token_urlsafe(32)
    _clean_expired_states()
    _pending_states[state] = time.time()

    callback_url = redirect_uri or settings.EVE_SSO_CALLBACK_URL
    if not callback_url:
        raise HTTPException(
            status_code=503,
            detail="EVE SSO callback URL not configured.",
        )

    params = {
        "response_type": "code",
        "redirect_uri": callback_url,
        "client_id": settings.EVE_SSO_CLIENT_ID,
        "scope": "publicData",
        "state": state,
    }
    auth_url = f"{EVE_SSO_AUTH_URL}?{'&'.join(f'{k}={v}' for k, v in params.items())}"

    return {"auth_url": auth_url, "state": state}


@router.get("/eve/callback")
async def eve_sso_callback(
    code: str = Query(...),
    state: str = Query(...),
):
    """Handle EVE SSO callback — exchange code for character info."""
    # Validate state (CSRF)
    _clean_expired_states()
    if state not in _pending_states:
        raise HTTPException(400, "Invalid or expired OAuth state.")
    del _pending_states[state]

    if not settings.EVE_SSO_CLIENT_ID or not settings.EVE_SSO_SECRET_KEY:
        raise HTTPException(503, "EVE SSO not fully configured.")

    # Exchange code for access token
    try:
        async with httpx.AsyncClient() as client:
            token_resp = await client.post(
                EVE_SSO_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": settings.EVE_SSO_CLIENT_ID,
                    "client_secret": settings.EVE_SSO_SECRET_KEY,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=10,
            )
            token_resp.raise_for_status()
            tokens = token_resp.json()

            # Verify token and get character info
            verify_resp = await client.get(
                EVE_SSO_VERIFY_URL,
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
                timeout=10,
            )
            verify_resp.raise_for_status()
            character = verify_resp.json()

    except httpx.HTTPStatusError as e:
        logger.error("EVE SSO token exchange failed: HTTP %d", e.response.status_code)
        raise HTTPException(502, "EVE SSO authentication failed.") from None
    except Exception as e:
        logger.error("EVE SSO error: %s", e)
        raise HTTPException(502, "EVE SSO authentication failed.") from None

    # Extract character data
    character_id = str(character.get("CharacterID", ""))
    character_name = character.get("CharacterName", "")

    if not character_id:
        raise HTTPException(502, "Could not verify character identity.")

    # Generate session token
    session_token = _generate_session_token()
    session_hash = hashlib.sha256(session_token.encode()).hexdigest()

    # Store session in DB
    db = get_db()
    db.execute(
        """INSERT INTO eve_sessions
           (session_hash, character_id, character_name, access_token, refresh_token, expires_at)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(session_hash) DO UPDATE SET
               character_id = excluded.character_id,
               character_name = excluded.character_name,
               access_token = excluded.access_token,
               refresh_token = excluded.refresh_token,
               expires_at = excluded.expires_at""",
        (
            session_hash,
            character_id,
            character_name,
            tokens.get("access_token", ""),
            tokens.get("refresh_token", ""),
            int(time.time()) + tokens.get("expires_in", 1200),
        ),
    )
    db.commit()

    logger.info("EVE SSO login: %s (%s)", character_name, character_id)

    return {
        "session_token": session_token,
        "character_id": character_id,
        "character_name": character_name,
    }


@router.get("/eve/me")
async def eve_sso_me(request: Request):
    """Return the character info for the current session."""
    session_token = request.headers.get("X-EVE-Session", "")
    if not session_token:
        raise HTTPException(401, "No EVE session. Login via /api/auth/eve/login.")

    session_hash = hashlib.sha256(session_token.encode()).hexdigest()
    db = get_db()
    row = db.execute(
        """SELECT character_id, character_name, created_at
           FROM eve_sessions WHERE session_hash = ? AND expires_at > ?""",
        (session_hash, int(time.time())),
    ).fetchone()

    if not row:
        raise HTTPException(401, "Session expired. Please log in again.")

    # Cross-reference with on-chain data
    entity = db.execute(
        """SELECT entity_id, display_name, kill_count, death_count, gate_count
           FROM entities WHERE display_name = ? OR entity_id = ?
           LIMIT 1""",
        (row["character_name"], row["character_id"]),
    ).fetchone()

    return {
        "character_id": row["character_id"],
        "character_name": row["character_name"],
        "logged_in_at": row["created_at"],
        "on_chain": dict(entity) if entity else None,
    }


@router.post("/eve/logout")
async def eve_sso_logout(request: Request):
    """Clear EVE SSO session."""
    session_token = request.headers.get("X-EVE-Session", "")
    if session_token:
        session_hash = hashlib.sha256(session_token.encode()).hexdigest()
        db = get_db()
        db.execute("DELETE FROM eve_sessions WHERE session_hash = ?", (session_hash,))
        db.commit()

    return {"status": "logged_out"}
