"""SpriteRegistry — loads and caches entity sprite sheets at startup.

Usage
-----
At game start (after pygame.init()):

    from src.rendering.registry import SpriteRegistry
    SpriteRegistry.get_instance().load_all("assets/sprites")

Entity classes call:

    anim = SpriteRegistry.get_instance().make_animator("slime")
    # None → entity should use procedural fallback draw

Directory layout expected under *assets_dir*::

    assets/sprites/
        enemies/    <type_key>.png  +  <type_key>.json
        creatures/  <kind>.png      +  <kind>.json
        pets/       <kind>.png      +  <kind>.json
        workers/    worker.png      +  worker.json
"""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING

import pygame

from src.rendering.animator import Animator

if TYPE_CHECKING:
    pass

# ---------------------------------------------------------------------------
# Chroma-key stripping
# ---------------------------------------------------------------------------

# #CC33BB = RGB(204, 51, 187) — background colour Gemini uses on sprite sheets.
# Tolerance expressed as a normalised distance (0–1) fed to PixelArray.replace().
# 40/255 ≈ 0.157 catches slight colour shifts from JPEG artefacts or
# rounding while staying well clear of any plausible sprite colour.
_CHROMA_COLOR: tuple[int, int, int] = (204, 51, 187)
_CHROMA_TOLERANCE: float = 40 / 255


def _apply_chroma_key(sheet: pygame.Surface) -> pygame.Surface:
    """Return a copy of *sheet* with #CC33BB and near-colours made transparent.

    Any pixel whose distance from (204, 51, 187) is within _CHROMA_TOLERANCE
    (using pygame's default luminance-weighted metric) is replaced with alpha 0.
    This lets Gemini-generated sprite sheets use #CC33BB as a solid background
    and have it stripped automatically at load-time.

    Uses ``pygame.PixelArray.replace()`` (C-level) for performance.

    Args:
        sheet: Source sprite sheet surface.

    Returns:
        New SRCALPHA Surface with chroma pixels zeroed out.
    """
    result = sheet.copy()
    pa = pygame.PixelArray(result)
    pa.replace(_CHROMA_COLOR, (0, 0, 0, 0), distance=_CHROMA_TOLERANCE)
    del pa  # unlock the surface
    return result


class SpriteRegistry:
    """Singleton that holds loaded sprite-sheet data for every entity type."""

    _instance: SpriteRegistry | None = None

    def __init__(self) -> None:
        # Maps entity_id → (sheet Surface, manifest dict)
        self._cache: dict[str, tuple[pygame.Surface, dict]] = {}
        self._loaded: bool = False

    # ------------------------------------------------------------------
    # Singleton access
    # ------------------------------------------------------------------

    @classmethod
    def get_instance(cls) -> SpriteRegistry:
        if cls._instance is None:
            cls._instance = SpriteRegistry()
        return cls._instance

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load_all(self, assets_dir: str) -> None:
        """Walk *assets_dir* and load every .png / .json sprite pair found.

        Safe to call multiple times — subsequent calls are no-ops unless
        the registry has been cleared.
        """
        if self._loaded:
            return

        if not os.path.isdir(assets_dir):
            # No assets directory yet (bake script hasn't been run).
            # All entities will fall back to procedural rendering — that's fine.
            self._loaded = True
            return

        for root, _dirs, files in os.walk(assets_dir):
            for fname in files:
                if not fname.endswith(".png"):
                    continue
                json_path = os.path.join(root, fname.replace(".png", ".json"))
                if not os.path.isfile(json_path):
                    continue
                entity_id = os.path.splitext(fname)[0]
                try:
                    sheet = pygame.image.load(os.path.join(root, fname)).convert_alpha()
                    sheet = _apply_chroma_key(sheet)
                    with open(json_path) as fh:
                        manifest = json.load(fh)
                    self._cache[entity_id] = (sheet, manifest)
                except Exception:
                    # Bad file — skip silently; entity will use procedural draw.
                    pass

        self._loaded = True

    # ------------------------------------------------------------------
    # Look-up
    # ------------------------------------------------------------------

    def get(self, entity_id: str) -> tuple[pygame.Surface, dict] | None:
        """Return (sheet, manifest) for *entity_id* or *None* if not loaded."""
        return self._cache.get(entity_id)

    def make_animator(self, entity_id: str) -> Animator | None:
        """Construct and return a fresh :class:`Animator` for *entity_id*.

        Returns *None* when no sprite sheet has been loaded for the given ID,
        so callers should fall back to procedural rendering.
        """
        data = self._cache.get(entity_id)
        if data is None:
            return None
        sheet, manifest = data
        return Animator(sheet, manifest)

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Drop all cached data (useful for hot-reload in development)."""
        self._cache.clear()
        self._loaded = False
