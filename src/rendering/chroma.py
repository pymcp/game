"""Chroma-key stripping for sprite sheets.

Shared by SpriteRegistry (entity sheets) and TileSpriteRegistry (tile atlases
and standalone tiles).  Both registries load PNG files that use #CC33BB as a
solid background colour; this module converts those pixels to full transparency
at load-time so the engine never needs to carry the background at runtime.
"""

from __future__ import annotations

import pygame

# #CC33BB = RGB(204, 51, 187) — the background colour used on all sprite sheets.
# Tolerance expressed as a normalised distance (0–1) fed to PixelArray.replace().
# 40/255 ≈ 0.157 catches slight colour shifts from JPEG artefacts or rounding
# while staying well clear of any plausible sprite colour.
CHROMA_COLOR: tuple[int, int, int] = (204, 51, 187)
CHROMA_TOLERANCE: float = 40 / 255


def apply_chroma_key(sheet: pygame.Surface) -> pygame.Surface:
    """Return a copy of *sheet* with #CC33BB and near-colours made transparent.

    Any pixel whose distance from (204, 51, 187) is within CHROMA_TOLERANCE
    (using pygame's default luminance-weighted metric) is replaced with alpha 0.
    This lets sprite sheets use #CC33BB as a solid background and have it
    stripped automatically at load-time.

    Uses ``pygame.PixelArray.replace()`` (C-level) for performance.

    Args:
        sheet: Source sprite sheet surface (must support SRCALPHA).

    Returns:
        New SRCALPHA Surface with chroma pixels zeroed out.
    """
    result = sheet.copy()
    pa = pygame.PixelArray(result)
    pa.replace(CHROMA_COLOR, (0, 0, 0, 0), distance=CHROMA_TOLERANCE)
    del pa  # unlock the surface
    return result
