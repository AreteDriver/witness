"""Tests for EVE Frontier coordinate utilities."""

from backend.ingestion.coordinates import (
    ONCHAIN_OFFSET,
    eve_to_render,
    safe_coord,
    subtract_onchain_offset,
)


class TestOnchainOffset:
    """On-chain uint256 offset subtraction."""

    def test_offset_is_correct_256bit_value(self):
        """1 << 255 must be the correct 256-bit value, not a 32-bit overflow."""
        expected = 57896044618658097711785492504343953926634992332820282019728792003956564819968
        assert ONCHAIN_OFFSET == expected

    def test_subtract_offset_string_input(self):
        """On-chain coords arrive as strings from Sui JSON."""
        raw = str(ONCHAIN_OFFSET + 12345)
        assert subtract_onchain_offset(raw) == 12345

    def test_subtract_offset_int_input(self):
        assert subtract_onchain_offset(ONCHAIN_OFFSET + 999) == 999

    def test_subtract_offset_zero(self):
        """Value equal to offset should yield 0."""
        assert subtract_onchain_offset(str(ONCHAIN_OFFSET)) == 0

    def test_subtract_offset_negative_result(self):
        """Coordinates can be negative after offset removal."""
        assert subtract_onchain_offset(str(ONCHAIN_OFFSET - 100)) == -100

    def test_subtract_offset_bad_string(self):
        assert subtract_onchain_offset("not-a-number") == 0

    def test_subtract_offset_none(self):
        assert subtract_onchain_offset(None) == 0

    def test_subtract_offset_empty_string(self):
        assert subtract_onchain_offset("") == 0


class TestAxisSwap:
    """CCP axis conversion: (x, y, z) → (x, z, -y)."""

    def test_basic_swap(self):
        assert eve_to_render(1.0, 2.0, 3.0) == (1.0, 3.0, -2.0)

    def test_negative_values(self):
        assert eve_to_render(-5.0, 10.0, -15.0) == (-5.0, -15.0, -10.0)

    def test_zero_values(self):
        assert eve_to_render(0.0, 0.0, 0.0) == (0.0, 0.0, 0.0)

    def test_none_passthrough(self):
        """If any component is None, return unchanged (no partial swap)."""
        assert eve_to_render(None, 2.0, 3.0) == (None, 2.0, 3.0)
        assert eve_to_render(1.0, None, 3.0) == (1.0, None, 3.0)
        assert eve_to_render(1.0, 2.0, None) == (1.0, 2.0, None)

    def test_all_none(self):
        assert eve_to_render(None, None, None) == (None, None, None)

    def test_large_coordinates(self):
        """EVE coords can be ~1e18 scale."""
        x, y, z = 1.5e18, -3.2e17, 8.9e16
        rx, ry, rz = eve_to_render(x, y, z)
        assert rx == x
        assert ry == z
        assert rz == -y


class TestSafeCoord:
    """Defensive coordinate parsing."""

    def test_float_input(self):
        assert safe_coord(3.14) == 3.14

    def test_int_input(self):
        assert safe_coord(42) == 42.0

    def test_string_float(self):
        assert safe_coord("1.5e8") == 1.5e8

    def test_string_int(self):
        assert safe_coord("12345") == 12345.0

    def test_none_returns_none(self):
        assert safe_coord(None) is None

    def test_bad_string(self):
        assert safe_coord("not-a-number") is None

    def test_list_returns_none(self):
        assert safe_coord([1, 2, 3]) is None

    def test_dict_returns_none(self):
        assert safe_coord({"x": 1}) is None

    def test_empty_string(self):
        """Empty string should return None (not 0)."""
        assert safe_coord("") is None

    def test_large_on_chain_value(self):
        """Post-offset-subtraction values should still convert to float."""
        val = 1234567890123456
        assert safe_coord(val) == float(val)
