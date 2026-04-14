"""Tests for the chroma-key stripping logic in SpriteRegistry.

Verifies that #CC33BB (204, 51, 187) and near-colours are converted to
alpha 0 when a sprite sheet is loaded, while unrelated colours are untouched.
"""

from __future__ import annotations

import pygame
import pytest

from src.rendering.registry import _apply_chroma_key

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _solid_surface(
    color: tuple[int, int, int, int], w: int = 4, h: int = 4
) -> pygame.Surface:
    """Return a small SRCALPHA surface filled with *color*."""
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    surf.fill(color)
    return surf


def _pixel(surf: pygame.Surface, x: int = 0, y: int = 0) -> tuple[int, int, int, int]:
    return surf.get_at((x, y))


# ---------------------------------------------------------------------------
# Exact chroma colour
# ---------------------------------------------------------------------------


class TestExactChromaKey:
    def test_exact_chroma_becomes_transparent(self) -> None:
        surf = _solid_surface((204, 51, 187, 255))
        result = _apply_chroma_key(surf)
        r, g, b, a = _pixel(result)
        assert a == 0

    def test_original_surface_unmodified(self) -> None:
        """_apply_chroma_key must not mutate the source surface."""
        surf = _solid_surface((204, 51, 187, 255))
        _apply_chroma_key(surf)
        r, g, b, a = _pixel(surf)
        assert a == 255  # original still opaque


# ---------------------------------------------------------------------------
# Near-chroma colours (within tolerance of 40 per channel)
# ---------------------------------------------------------------------------


class TestNearChromaKey:
    def test_slightly_lighter_chroma_stripped(self) -> None:
        surf = _solid_surface((220, 70, 200, 255))  # +16 R, +19 G, +13 B
        result = _apply_chroma_key(surf)
        assert _pixel(result)[3] == 0

    def test_slightly_darker_chroma_stripped(self) -> None:
        surf = _solid_surface((180, 30, 160, 255))  # -24 R, -21 G, -27 B
        result = _apply_chroma_key(surf)
        assert _pixel(result)[3] == 0

    def test_boundary_within_tolerance_stripped(self) -> None:
        """Pixel exactly at tolerance boundary (±40 on each channel) is stripped."""
        surf = _solid_surface((204 + 40, 51 + 40, 187 + 40, 255))
        result = _apply_chroma_key(surf)
        assert _pixel(result)[3] == 0

    def test_boundary_just_outside_tolerance_kept(self) -> None:
        """Pixel well outside the tolerance distance is kept."""
        # Green difference of 70 (>>52 needed to exceed weighted tolerance)
        surf = _solid_surface((204, 51 + 70, 187, 255))
        result = _apply_chroma_key(surf)
        assert _pixel(result)[3] == 255


# ---------------------------------------------------------------------------
# Non-chroma colours are untouched
# ---------------------------------------------------------------------------


class TestNonChromaPreserved:
    def test_red_pixel_kept(self) -> None:
        surf = _solid_surface((255, 0, 0, 255))
        result = _apply_chroma_key(surf)
        r, g, b, a = _pixel(result)
        assert a == 255
        assert r == 255

    def test_green_pixel_kept(self) -> None:
        surf = _solid_surface((0, 200, 0, 255))
        result = _apply_chroma_key(surf)
        assert _pixel(result)[3] == 255

    def test_white_pixel_kept(self) -> None:
        surf = _solid_surface((255, 255, 255, 255))
        result = _apply_chroma_key(surf)
        assert _pixel(result)[3] == 255

    def test_black_pixel_kept(self) -> None:
        surf = _solid_surface((0, 0, 0, 255))
        result = _apply_chroma_key(surf)
        assert _pixel(result)[3] == 255

    def test_transparent_pixel_stays_transparent(self) -> None:
        surf = _solid_surface((0, 0, 0, 0))
        result = _apply_chroma_key(surf)
        assert _pixel(result)[3] == 0

    def test_sprite_colour_close_to_chroma_red_kept(self) -> None:
        """A sprite red (e.g. lava glow #CC4422) must not be stripped."""
        surf = _solid_surface((204, 68, 34, 255))  # #CC4422 — 17 off in G, 153 off in B
        result = _apply_chroma_key(surf)
        assert _pixel(result)[3] == 255


# ---------------------------------------------------------------------------
# Mixed surface — chroma background with sprite pixels
# ---------------------------------------------------------------------------


class TestMixedSurface:
    def test_mixed_surface_strips_background_keeps_sprite(self) -> None:
        """Background pixels stripped, sprite pixels intact."""
        surf = pygame.Surface((2, 1), pygame.SRCALPHA)
        surf.set_at((0, 0), (204, 51, 187, 255))  # chroma background
        surf.set_at((1, 0), (100, 150, 200, 255))  # sprite pixel

        result = _apply_chroma_key(surf)

        assert result.get_at((0, 0))[3] == 0  # background gone
        assert result.get_at((1, 0))[3] == 255  # sprite pixel kept
        assert result.get_at((1, 0))[:3] == (100, 150, 200)  # colour unchanged
