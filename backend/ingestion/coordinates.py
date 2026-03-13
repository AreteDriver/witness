"""EVE Frontier coordinate utilities.

Coordinate systems (per frontier.scetrov.live/develop/coordinate_systems/):
- On-chain Location Table: uint256 with 1 << 255 offset added. Subtract for rendering.
  Offset is irrelevant for distance calculations (cancels out).
- CCP axis orientation: non-standard. Convert (x, y, z) → (x, z, -y) for rendering
  (−90° rotation about X-axis).
- World API Smart Assemblies: relative to local star center, double precision.
- World API Solar Systems: absolute (galactic center), double precision.

Python handles arbitrary-precision integers natively, so 1 << 255 is safe here.
JavaScript requires BigInt — see frontend notes if parsing on-chain coords in JS.
"""

# On-chain coordinates have this offset baked in (uint256 bias).
# Python handles arbitrary-precision ints natively — no overflow risk.
ONCHAIN_OFFSET = 1 << 255


def subtract_onchain_offset(val: str | int) -> int:
    """Remove the 1 << 255 bias from an on-chain coordinate component.

    On-chain location table stores coordinates as uint256 with ONCHAIN_OFFSET added.
    Subtract it for absolute galactic coordinates suitable for rendering.
    """
    try:
        return int(val) - ONCHAIN_OFFSET
    except (ValueError, TypeError):
        return 0


def eve_to_render(x: float | None, y: float | None, z: float | None) -> tuple:
    """Apply CCP axis swap: (x, y, z) → (x, z, -y).

    CCP uses a non-standard axis orientation. This −90° rotation about the
    X-axis converts to standard rendering coordinates.
    """
    if x is None or y is None or z is None:
        return (x, y, z)
    return (x, z, -y)


def safe_coord(val) -> float | None:
    """Safely convert a coordinate value to float, returning None on failure.

    Handles None, non-numeric strings, lists, and other bad types.
    """
    try:
        return float(val) if val is not None else None
    except (TypeError, ValueError):
        return None
