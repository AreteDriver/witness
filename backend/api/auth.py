"""Sui wallet authentication with signature verification.

Implements challenge-response wallet auth for EVE Frontier (Sui blockchain).
Frontend signs a challenge nonce via @mysten/dapp-kit signPersonalMessage,
server verifies the Ed25519/Secp256k1 signature and derives the address
from the public key.

Flow:
  1. POST /api/auth/wallet/challenge → get a nonce to sign
  2. POST /api/auth/wallet/connect   → submit signature, get session token
  3. GET  /api/auth/wallet/me        → return current session + tier info
  4. POST /api/auth/wallet/disconnect → clear session
"""

import base64
import hashlib
import re
import secrets
import time

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from backend.core.config import settings
from backend.core.logger import get_logger
from backend.db.database import get_db

logger = get_logger("auth")

router = APIRouter(prefix="/auth")

# Sui addresses: 0x + 64 hex chars (32 bytes)
SUI_ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{64}$")

# Session TTL: 7 days
SESSION_TTL = 7 * 86400

# Challenge nonce TTL: 5 minutes
CHALLENGE_TTL = 300

# Bounded in-memory challenge store (max 1000 pending challenges)
_pending_challenges: dict[str, float] = {}
MAX_PENDING_CHALLENGES = 1000

# Sui signature scheme bytes
SCHEME_ED25519 = 0x00
SCHEME_SECP256K1 = 0x01

# Sui PersonalMessage intent prefix: [IntentScope::PersonalMessage=3, version=0, app_id=0]
PERSONAL_MESSAGE_INTENT = bytes([3, 0, 0])


def _encode_uleb128(value: int) -> bytes:
    """Encode an integer as ULEB128 (used in BCS serialization)."""
    result = bytearray()
    while value >= 0x80:
        result.append((value & 0x7F) | 0x80)
        value >>= 7
    result.append(value)
    return bytes(result)


def _derive_sui_address(scheme_byte: int, public_key: bytes) -> str:
    """Derive Sui address from scheme byte + public key via Blake2b-256."""
    data = bytes([scheme_byte]) + public_key
    address_hash = hashlib.blake2b(data, digest_size=32).digest()
    return "0x" + address_hash.hex()


def _verify_sui_signature(message: bytes, signature_b64: str) -> str:
    """Verify a Sui personal message signature.

    Sui signPersonalMessage format:
      - Message is wrapped: Blake2b-256(intent || bcs_encode(message_bytes))
      - Signature is: scheme_byte || raw_sig || public_key (base64)

    Returns the derived Sui address on success.
    Raises ValueError on any verification failure.
    """
    try:
        sig_bytes = base64.b64decode(signature_b64)
    except Exception as e:
        raise ValueError(f"Invalid base64 signature: {e}") from e

    if len(sig_bytes) < 2:
        raise ValueError("Signature too short")

    scheme = sig_bytes[0]

    if scheme == SCHEME_ED25519:
        # Ed25519: 1 (scheme) + 64 (sig) + 32 (pubkey) = 97 bytes
        if len(sig_bytes) != 97:
            raise ValueError(f"Ed25519 signature wrong length: {len(sig_bytes)}")
        raw_sig = sig_bytes[1:65]
        public_key = sig_bytes[65:97]
    elif scheme == SCHEME_SECP256K1:
        # Secp256k1: 1 (scheme) + 64 (sig) + 33 (compressed pubkey) = 98 bytes
        if len(sig_bytes) != 98:
            raise ValueError(f"Secp256k1 signature wrong length: {len(sig_bytes)}")
        raise ValueError("Secp256k1 verification not implemented")
    else:
        raise ValueError(f"Unsupported signature scheme: {scheme}")

    # Reconstruct the signed message hash
    # BCS encode message bytes: ULEB128 length prefix + raw bytes
    bcs_message = _encode_uleb128(len(message)) + message
    intent_message = PERSONAL_MESSAGE_INTENT + bcs_message
    message_hash = hashlib.blake2b(intent_message, digest_size=32).digest()

    # Verify Ed25519 signature
    try:
        ed_key = Ed25519PublicKey.from_public_bytes(public_key)
        ed_key.verify(raw_sig, message_hash)
    except InvalidSignature:
        raise ValueError("Signature verification failed") from None
    except Exception as e:
        raise ValueError(f"Key/signature error: {e}") from e

    # Derive address from public key
    return _derive_sui_address(scheme, public_key)


def _prune_challenges() -> None:
    """Remove expired challenges and enforce max size."""
    now = time.time()
    expired = [k for k, v in _pending_challenges.items() if now - v > CHALLENGE_TTL]
    for k in expired:
        del _pending_challenges[k]
    # If still over limit, remove oldest
    if len(_pending_challenges) > MAX_PENDING_CHALLENGES:
        sorted_keys = sorted(_pending_challenges, key=_pending_challenges.get)
        for k in sorted_keys[: len(_pending_challenges) - MAX_PENDING_CHALLENGES]:
            del _pending_challenges[k]


class ChallengeResponse(BaseModel):
    nonce: str
    message: str


class WalletConnectRequest(BaseModel):
    wallet_address: str = Field(
        ...,
        pattern=r"^0x[a-fA-F0-9]{64}$",
        description="Sui wallet address (0x + 64 hex chars)",
    )
    signature: str = Field(
        ...,
        description="Base64-encoded Sui signature from signPersonalMessage",
    )
    message: str = Field(
        ...,
        description="The challenge message that was signed",
    )


class WalletConnectResponse(BaseModel):
    session_token: str
    wallet_address: str
    tier: int
    tier_name: str
    is_admin: bool


class WalletMeResponse(BaseModel):
    wallet_address: str
    tier: int
    tier_name: str
    is_admin: bool
    connected_at: int


def _is_admin(wallet_address: str) -> bool:
    """Check if wallet address is in the admin set."""
    return wallet_address.lower() in settings.admin_address_set


@router.post("/wallet/challenge")
async def wallet_challenge() -> ChallengeResponse:
    """Generate a challenge nonce for wallet signature verification."""
    _prune_challenges()

    nonce = secrets.token_urlsafe(32)
    message = f"WatchTower authentication: {nonce}"

    _pending_challenges[nonce] = time.time()

    return ChallengeResponse(nonce=nonce, message=message)


@router.post("/wallet/connect")
async def wallet_connect(body: WalletConnectRequest) -> WalletConnectResponse:
    """Verify wallet signature and create a session.

    Frontend must first call /challenge, sign the message with
    signPersonalMessage via @mysten/dapp-kit, then submit here.
    """
    wallet_address = body.wallet_address.lower()

    if not SUI_ADDRESS_RE.match(body.wallet_address):
        raise HTTPException(400, "Invalid Sui wallet address format.")

    # Validate the challenge nonce is pending and not expired
    # Extract nonce from message format "WatchTower authentication: <nonce>"
    prefix = "WatchTower authentication: "
    if not body.message.startswith(prefix):
        raise HTTPException(400, "Invalid challenge message format.")

    nonce = body.message[len(prefix) :]
    if nonce not in _pending_challenges:
        raise HTTPException(400, "Challenge expired or not found. Request a new one.")

    issued_at = _pending_challenges[nonce]
    if time.time() - issued_at > CHALLENGE_TTL:
        del _pending_challenges[nonce]
        raise HTTPException(400, "Challenge expired. Request a new one.")

    # Consume the nonce (one-time use)
    del _pending_challenges[nonce]

    # Verify signature and derive address
    try:
        derived_address = _verify_sui_signature(
            body.message.encode("utf-8"),
            body.signature,
        )
    except ValueError as e:
        logger.warning("Signature verification failed for %s: %s", wallet_address[:16], e)
        raise HTTPException(401, f"Signature verification failed: {e}") from None

    # Confirm derived address matches claimed address
    if derived_address.lower() != wallet_address:
        logger.warning(
            "Address mismatch: claimed %s, derived %s",
            wallet_address[:16],
            derived_address[:16],
        )
        raise HTTPException(401, "Wallet address does not match signature.")

    # Generate session token
    session_token = secrets.token_urlsafe(32)
    session_hash = hashlib.sha256(session_token.encode()).hexdigest()

    expires_at = int(time.time()) + SESSION_TTL

    db = get_db()

    # Store session
    db.execute(
        """INSERT INTO wallet_sessions (session_hash, wallet_address, expires_at)
           VALUES (?, ?, ?)""",
        (session_hash, wallet_address, expires_at),
    )
    db.commit()

    # Get subscription tier
    from backend.analysis.subscriptions import check_subscription

    sub = check_subscription(db, wallet_address)
    is_admin = _is_admin(wallet_address)

    logger.info(
        "Wallet verified and connected: %s (admin=%s, tier=%d)",
        wallet_address[:16],
        is_admin,
        sub["tier"],
    )

    return WalletConnectResponse(
        session_token=session_token,
        wallet_address=wallet_address,
        tier=sub["tier"],
        tier_name=sub["tier_name"],
        is_admin=is_admin,
    )


def _get_session_wallet(request: Request) -> str | None:
    """Extract wallet address from session header.

    Checks X-Session header, falls back to X-EVE-Session for backwards compat.
    """
    session_token = request.headers.get("X-Session", request.headers.get("X-EVE-Session", ""))
    if not session_token:
        return None

    session_hash = hashlib.sha256(session_token.encode()).hexdigest()
    db = get_db()
    row = db.execute(
        """SELECT wallet_address FROM wallet_sessions
           WHERE session_hash = ? AND expires_at > ?""",
        (session_hash, int(time.time())),
    ).fetchone()

    if not row:
        return None
    return row["wallet_address"]


@router.get("/wallet/me")
async def wallet_me(request: Request) -> WalletMeResponse:
    """Return wallet info for the current session."""
    session_token = request.headers.get("X-Session", request.headers.get("X-EVE-Session", ""))
    if not session_token:
        raise HTTPException(401, "No session. Connect wallet first.")

    session_hash = hashlib.sha256(session_token.encode()).hexdigest()
    db = get_db()
    row = db.execute(
        """SELECT wallet_address, created_at FROM wallet_sessions
           WHERE session_hash = ? AND expires_at > ?""",
        (session_hash, int(time.time())),
    ).fetchone()

    if not row:
        raise HTTPException(401, "Session expired. Please reconnect wallet.")

    from backend.analysis.subscriptions import check_subscription

    wallet_address = row["wallet_address"]
    sub = check_subscription(db, wallet_address)

    return WalletMeResponse(
        wallet_address=wallet_address,
        tier=sub["tier"],
        tier_name=sub["tier_name"],
        is_admin=_is_admin(wallet_address),
        connected_at=row["created_at"],
    )


@router.post("/wallet/disconnect")
async def wallet_disconnect(request: Request):
    """Clear wallet session."""
    session_token = request.headers.get("X-Session", request.headers.get("X-EVE-Session", ""))
    if session_token:
        session_hash = hashlib.sha256(session_token.encode()).hexdigest()
        db = get_db()
        db.execute(
            "DELETE FROM wallet_sessions WHERE session_hash = ?",
            (session_hash,),
        )
        db.commit()

    return {"status": "disconnected"}
