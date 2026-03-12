"""Subscription tier gating — enforce access control on premium endpoints."""

from datetime import date

from fastapi import HTTPException, Request

from backend.analysis.subscriptions import TIER_NAMES, get_tier_for_endpoint
from backend.core.config import settings
from backend.core.logger import get_logger

logger = get_logger("tier_gate")

# Route patterns to match against (normalized to API path templates)
_GATED_ROUTES = {
    "get_entity_fingerprint": "/entity/{entity_id}/fingerprint",
    "get_entity_reputation": "/entity/{entity_id}/reputation",
    "compare_entity_fingerprints": "/fingerprint/compare",
    "get_entity_narrative": "/entity/{entity_id}/narrative",
    "create_watch": "/watches",
    "create_battle_report": "/battle-report",
    "get_kill_graph": "/kill-graph",
}


def is_admin_wallet(wallet_address: str) -> bool:
    """Check if a wallet address has admin privileges."""
    if not wallet_address:
        return False
    return wallet_address.lower() in settings.admin_address_set


def check_tier_access(request: Request, route_name: str) -> None:
    """Check if request has sufficient subscription tier.

    Reads wallet address from X-Wallet-Address header.
    Admin wallets bypass all tier checks.
    Hackathon mode grants Spymaster to all users.
    Free-tier endpoints pass through without checks.

    Raises HTTPException(403) if insufficient tier.
    """
    # Hackathon mode — everyone gets full access until expiry date
    if settings.HACKATHON_MODE:
        try:
            ends = date.fromisoformat(settings.HACKATHON_ENDS)
            if date.today() <= ends:
                return
        except ValueError:
            pass  # Bad date format, fall through to normal gating

    endpoint_path = _GATED_ROUTES.get(route_name)
    if not endpoint_path:
        return  # Not a gated route

    required_tier = get_tier_for_endpoint(endpoint_path)
    if required_tier == 0:
        return  # Free tier, no gate

    wallet = request.headers.get("X-Wallet-Address", "")
    if not wallet:
        raise HTTPException(
            status_code=403,
            detail=(
                f"Wallet address required. "
                f"This endpoint requires {TIER_NAMES.get(required_tier, 'paid')} tier."
            ),
        )

    # Admin bypass — skip tier check entirely
    if is_admin_wallet(wallet):
        return

    from backend.analysis.subscriptions import check_subscription
    from backend.db.database import get_db

    db = get_db()
    sub = check_subscription(db, wallet)

    if not sub["active"] or sub["tier"] < required_tier:
        required_name = TIER_NAMES.get(required_tier, "paid")
        current_name = sub["tier_name"]
        raise HTTPException(
            status_code=403,
            detail=f"Insufficient tier. Requires: {required_name}. Current: {current_name}.",
        )
