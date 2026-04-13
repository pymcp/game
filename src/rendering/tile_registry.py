"""TileSpriteRegistry — loads and caches tile atlas sprite sheets.

Tile atlases live under ``assets/tiles/``.  Each atlas is a ``.png`` +
``.json`` pair.  Standalone (non-adjacency) tiles live under
``assets/tiles/standalone/``.

Atlas layout
------------
Each tile type occupies **16 consecutive rows** (one per 4-bit adjacency
mask 0-15) × **4 columns** (animation frames).  Cell size is 64×64 px.

Adjacency encoding::

    bit 3 = North   (1 if same type)
    bit 2 = East
    bit 1 = South
    bit 0 = West

Atlas manifest (JSON)::

    {
      "cell_size": [64, 64],
      "cols": 4,
      "tiles": {
        "grass": { "start_row": 0,  "fps": 0   },
        "water": { "start_row": 16, "fps": 3.0 }
      }
    }

Standalone manifest (JSON)::

    {
      "frame_size": [64, 128],
      "frames": 4,
      "fps": 0,
      "draw_offset": [0, -64]
    }

Usage::

    from src.rendering.tile_registry import TileSpriteRegistry
    reg = TileSpriteRegistry.get_instance()
    reg.load_all("assets/tiles")
    frame = reg.get_frame("grass", adjacency=0b1010, frame_idx=0)
    frame_tinted = reg.get_frame("grass", adjacency=0b1010, frame_idx=0,
                                  tileset="cave")
"""

from __future__ import annotations

import json
import os
from enum import IntEnum
from typing import TYPE_CHECKING

import pygame

if TYPE_CHECKING:
    from src.world.map import GameMap

from src.config import (
    GRASS, DIRT, STONE, IRON_ORE, GOLD_ORE, DIAMOND_ORE,
    TREE, WATER, HOUSE, MOUNTAIN, CAVE_MOUNTAIN, CAVE_HILL,
    CAVE_EXIT, CAVE_WALL, PIER, BOAT, TREASURE_CHEST, SAND,
    CORAL, REEF, DIVE_EXIT, PORTAL_RUINS, PORTAL_ACTIVE,
    ANCIENT_STONE, PORTAL_WALL, PORTAL_FLOOR, WOOD_FLOOR,
    WOOD_WALL, WORKTABLE, HOUSE_EXIT, DIRT_PATH, COBBLESTONE,
    SETTLEMENT_HOUSE, STONE_PATH, ROAD, SNOW, ICE_PEAK,
    FROZEN_LAKE, FROST_CRYSTAL_ORE, ASH_GROUND, LAVA_POOL,
    MAGMA_STONE, MAGMA_ORE, DEAD_GRASS, RUINS_WALL, BONE_PILE,
    GRAVE, DESERT_CRYSTAL_ORE, SANDSTONE, CACTUS_TILE,
    VOID_ORE, PORTAL_LAVA, SIGN, BROKEN_LADDER, SKY_LADDER,
)

# Tile ID → sprite name used in atlas manifests & standalone lookups
TILE_ID_TO_NAME: dict[int, str] = {
    GRASS: "grass", DIRT: "dirt", STONE: "stone", SAND: "sand",
    SNOW: "snow", ASH_GROUND: "ash_ground", DEAD_GRASS: "dead_grass",
    DIRT_PATH: "dirt_path", COBBLESTONE: "cobblestone",
    STONE_PATH: "stone_path", ROAD: "road", SANDSTONE: "sandstone",
    TREE: "tree", WATER: "water", MOUNTAIN: "mountain",
    CACTUS_TILE: "cactus",
    IRON_ORE: "iron_ore", GOLD_ORE: "gold_ore", DIAMOND_ORE: "diamond_ore",
    FROST_CRYSTAL_ORE: "frost_crystal_ore", MAGMA_ORE: "magma_ore",
    DESERT_CRYSTAL_ORE: "desert_crystal_ore", VOID_ORE: "void_ore",
    MAGMA_STONE: "magma_stone",
    CAVE_WALL: "cave_wall", CAVE_EXIT: "cave_exit",
    CAVE_MOUNTAIN: "cave_mountain", CAVE_HILL: "cave_hill",
    CORAL: "coral", REEF: "reef", DIVE_EXIT: "dive_exit",
    PORTAL_WALL: "portal_wall", PORTAL_FLOOR: "portal_floor",
    PORTAL_RUINS: "portal_ruins", PORTAL_ACTIVE: "portal_active",
    PORTAL_LAVA: "portal_lava", ANCIENT_STONE: "ancient_stone",
    HOUSE: "house", PIER: "pier", BOAT: "boat",
    TREASURE_CHEST: "treasure_chest",
    WOOD_FLOOR: "wood_floor", WOOD_WALL: "wood_wall",
    WORKTABLE: "worktable", HOUSE_EXIT: "house_exit",
    SETTLEMENT_HOUSE: "settlement_house",
    ICE_PEAK: "ice_peak", FROZEN_LAKE: "frozen_lake",
    LAVA_POOL: "lava_pool", RUINS_WALL: "ruins_wall",
    BONE_PILE: "bone_pile", GRAVE: "grave",
    SIGN: "sign", BROKEN_LADDER: "broken_ladder", SKY_LADDER: "sky_ladder",
}

# Standalone tile IDs (not in adjacency atlases)
STANDALONE_TILE_IDS: frozenset[int] = frozenset({SIGN, BROKEN_LADDER, SKY_LADDER})


# ---------------------------------------------------------------------------
# Adjacency helpers
# ---------------------------------------------------------------------------

class AdjBit(IntEnum):
    """Bit positions for the 4-bit cardinal adjacency mask."""
    NORTH = 3
    EAST = 2
    SOUTH = 1
    WEST = 0


def compute_adjacency(game_map: GameMap, row: int, col: int, tile_id: int) -> int:
    """Return a 4-bit adjacency mask for *tile_id* at *(row, col)*.

    Each bit is 1 when the cardinal neighbour is the same tile type.
    """
    n: int = 1 if game_map.get_tile(row - 1, col) == tile_id else 0
    e: int = 1 if game_map.get_tile(row, col + 1) == tile_id else 0
    s: int = 1 if game_map.get_tile(row + 1, col) == tile_id else 0
    w: int = 1 if game_map.get_tile(row, col - 1) == tile_id else 0
    return (n << 3) | (e << 2) | (s << 1) | w


# ---------------------------------------------------------------------------
# Tileset tinting
# ---------------------------------------------------------------------------

# Each tileset maps to (r_mult, g_mult, b_mult, r_add, g_add, b_add).
# Final channel = clamp(base * mult + add, 0, 255)
TILESET_TINTS: dict[str, tuple[float, float, float, int, int, int]] = {
    "cave":          (0.70, 0.80, 0.60,  0,  0,  0),
    "underwater":    (0.65, 0.90, 1.30,  0,  0,  0),
    "portal_realm":  (0.80, 0.70, 1.10, 15,  0, 20),
    "cave_tundra":   (0.65, 0.75, 1.10, 20, 20, 40),
    "cave_volcano":  (0.90, 0.55, 0.45, 40,  0,  0),
    "cave_zombie":   (0.55, 0.75, 0.50,  0, 15,  0),
    "cave_desert":   (0.85, 0.75, 0.50, 35, 15,  0),
}


def _tint_surface(
    surf: pygame.Surface,
    r_mult: float, g_mult: float, b_mult: float,
    r_add: int, g_add: int, b_add: int,
) -> pygame.Surface:
    """Return a tinted copy of *surf* using per-channel multiply + add."""
    tinted = surf.copy()
    # Step 1: multiplicative tint
    mult_color = (
        max(0, min(255, int(255 * r_mult))),
        max(0, min(255, int(255 * g_mult))),
        max(0, min(255, int(255 * b_mult))),
    )
    tinted.fill(mult_color, special_flags=pygame.BLEND_RGB_MULT)
    # Step 2: additive offset (only when non-zero)
    if r_add or g_add or b_add:
        tinted.fill(
            (max(0, min(255, r_add)),
             max(0, min(255, g_add)),
             max(0, min(255, b_add))),
            special_flags=pygame.BLEND_RGB_ADD,
        )
    return tinted


# ---------------------------------------------------------------------------
# TileAtlas  — one loaded atlas sheet
# ---------------------------------------------------------------------------

class TileAtlas:
    """One loaded tile atlas (PNG + manifest)."""

    __slots__ = ("sheet", "cell_w", "cell_h", "cols", "tiles")

    def __init__(self, sheet: pygame.Surface, manifest: dict) -> None:
        cw, ch = manifest["cell_size"]
        self.sheet: pygame.Surface = sheet
        self.cell_w: int = cw
        self.cell_h: int = ch
        self.cols: int = manifest["cols"]
        # tiles[name] = {"start_row": int, "fps": float}
        self.tiles: dict[str, dict] = manifest["tiles"]

    def get_frame(
        self, tile_name: str, adjacency: int, frame_idx: int,
    ) -> pygame.Surface | None:
        """Extract a single frame for *tile_name* at *adjacency* mask."""
        entry = self.tiles.get(tile_name)
        if entry is None:
            return None
        row = entry["start_row"] + (adjacency & 0xF)
        col = frame_idx % self.cols
        x = col * self.cell_w
        y = row * self.cell_h
        return self.sheet.subsurface(pygame.Rect(x, y, self.cell_w, self.cell_h))

    def get_fps(self, tile_name: str) -> float:
        """Return the FPS for a tile type (0 = static)."""
        entry = self.tiles.get(tile_name)
        return entry["fps"] if entry else 0.0


# ---------------------------------------------------------------------------
# StandaloneTile — a single non-atlas tile sprite
# ---------------------------------------------------------------------------

class StandaloneTile:
    """A standalone tile sprite (e.g. tall signs/ladders)."""

    __slots__ = ("sheet", "frame_w", "frame_h", "num_frames", "fps", "draw_offset")

    def __init__(self, sheet: pygame.Surface, manifest: dict) -> None:
        fw, fh = manifest["frame_size"]
        self.sheet: pygame.Surface = sheet
        self.frame_w: int = fw
        self.frame_h: int = fh
        self.num_frames: int = manifest.get("frames", 1)
        self.fps: float = manifest.get("fps", 0.0)
        dx, dy = manifest.get("draw_offset", [0, 0])
        self.draw_offset: tuple[int, int] = (dx, dy)

    def get_frame(self, frame_idx: int) -> pygame.Surface:
        """Return animation frame *frame_idx* (wraps)."""
        col = frame_idx % self.num_frames
        return self.sheet.subsurface(
            pygame.Rect(col * self.frame_w, 0, self.frame_w, self.frame_h)
        )


# ---------------------------------------------------------------------------
# TileSpriteRegistry  — the singleton
# ---------------------------------------------------------------------------

class TileSpriteRegistry:
    """Singleton that holds loaded tile atlas data and standalone tile sprites."""

    _instance: TileSpriteRegistry | None = None

    def __init__(self) -> None:
        # atlas_name → TileAtlas (base, untinted)
        self._atlases: dict[str, TileAtlas] = {}
        # tile_name → atlas_name (reverse lookup)
        self._tile_to_atlas: dict[str, str] = {}
        # standalone tile_name → StandaloneTile
        self._standalone: dict[str, StandaloneTile] = {}
        # (atlas_name, tileset) → tinted TileAtlas sheet surface
        self._tint_cache: dict[tuple[str, str], pygame.Surface] = {}
        self._loaded: bool = False

    # ------------------------------------------------------------------
    # Singleton
    # ------------------------------------------------------------------

    @classmethod
    def get_instance(cls) -> TileSpriteRegistry:
        if cls._instance is None:
            cls._instance = TileSpriteRegistry()
        return cls._instance

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load_all(self, tiles_dir: str) -> None:
        """Load all tile atlases and standalone sprites from *tiles_dir*.

        Safe to call multiple times — subsequent calls are no-ops.
        """
        if self._loaded:
            return

        # --- atlases (top-level .png + .json pairs) ---
        if os.path.isdir(tiles_dir):
            for fname in os.listdir(tiles_dir):
                if not fname.endswith(".png"):
                    continue
                json_path = os.path.join(tiles_dir, fname.replace(".png", ".json"))
                if not os.path.isfile(json_path):
                    continue
                atlas_name = os.path.splitext(fname)[0]
                try:
                    sheet = pygame.image.load(
                        os.path.join(tiles_dir, fname)
                    ).convert_alpha()
                    with open(json_path) as fh:
                        manifest = json.load(fh)
                    atlas = TileAtlas(sheet, manifest)
                    self._atlases[atlas_name] = atlas
                    for tile_name in atlas.tiles:
                        self._tile_to_atlas[tile_name] = atlas_name
                except Exception:
                    pass  # skip bad files — tiles fall back gracefully

        # --- standalone sprites ---
        standalone_dir = os.path.join(tiles_dir, "standalone")
        if os.path.isdir(standalone_dir):
            for fname in os.listdir(standalone_dir):
                if not fname.endswith(".png"):
                    continue
                json_path = os.path.join(
                    standalone_dir, fname.replace(".png", ".json")
                )
                if not os.path.isfile(json_path):
                    continue
                tile_name = os.path.splitext(fname)[0]
                try:
                    sheet = pygame.image.load(
                        os.path.join(standalone_dir, fname)
                    ).convert_alpha()
                    with open(json_path) as fh:
                        manifest = json.load(fh)
                    self._standalone[tile_name] = StandaloneTile(sheet, manifest)
                except Exception:
                    pass

        self._loaded = True

    # ------------------------------------------------------------------
    # Atlas frame lookup
    # ------------------------------------------------------------------

    def get_frame(
        self,
        tile_name: str,
        adjacency: int,
        frame_idx: int,
        tileset: str = "overland",
    ) -> pygame.Surface | None:
        """Return a 64×64 tile frame, tinted for *tileset*.

        Returns ``None`` when no atlas has been loaded for *tile_name*.
        """
        atlas_name = self._tile_to_atlas.get(tile_name)
        if atlas_name is None:
            return None
        atlas = self._atlases[atlas_name]

        # Pick the (possibly tinted) sheet
        if tileset != "overland" and tileset in TILESET_TINTS:
            sheet = self._get_tinted_sheet(atlas_name, tileset)
        else:
            sheet = atlas.sheet

        # Compute rect the same way TileAtlas.get_frame does, but on the
        # correct (tinted or base) sheet surface.
        entry = atlas.tiles.get(tile_name)
        if entry is None:
            return None
        row = entry["start_row"] + (adjacency & 0xF)
        col = frame_idx % atlas.cols
        x = col * atlas.cell_w
        y = row * atlas.cell_h
        return sheet.subsurface(pygame.Rect(x, y, atlas.cell_w, atlas.cell_h))

    def get_fps(self, tile_name: str) -> float:
        """Return the animation FPS for *tile_name* (0 = static)."""
        atlas_name = self._tile_to_atlas.get(tile_name)
        if atlas_name is None:
            return 0.0
        return self._atlases[atlas_name].get_fps(tile_name)

    # ------------------------------------------------------------------
    # Standalone tile lookup
    # ------------------------------------------------------------------

    def get_standalone(
        self,
        tile_name: str,
        frame_idx: int,
        tileset: str = "overland",
    ) -> tuple[pygame.Surface, tuple[int, int]] | None:
        """Return ``(frame_surface, (dx, dy))`` for a standalone tile.

        Returns ``None`` if the tile name is not loaded as a standalone.
        """
        st = self._standalone.get(tile_name)
        if st is None:
            return None
        frame = st.get_frame(frame_idx)
        # Tint standalone frame on-the-fly (cheap — single tile)
        if tileset != "overland" and tileset in TILESET_TINTS:
            rm, gm, bm, ra, ga, ba = TILESET_TINTS[tileset]
            frame = _tint_surface(frame, rm, gm, bm, ra, ga, ba)
        return frame, st.draw_offset

    def get_standalone_fps(self, tile_name: str) -> float:
        """Return the animation FPS for a standalone tile (0 = static)."""
        st = self._standalone.get(tile_name)
        return st.fps if st else 0.0

    # ------------------------------------------------------------------
    # Tint cache
    # ------------------------------------------------------------------

    def _get_tinted_sheet(self, atlas_name: str, tileset: str) -> pygame.Surface:
        """Return a cached tinted copy of the atlas sheet for *tileset*."""
        key = (atlas_name, tileset)
        if key not in self._tint_cache:
            base_sheet = self._atlases[atlas_name].sheet
            rm, gm, bm, ra, ga, ba = TILESET_TINTS[tileset]
            self._tint_cache[key] = _tint_surface(
                base_sheet, rm, gm, bm, ra, ga, ba
            )
        return self._tint_cache[key]

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def has_tile(self, tile_name: str) -> bool:
        """Return True if *tile_name* is available (atlas or standalone)."""
        return tile_name in self._tile_to_atlas or tile_name in self._standalone

    def clear(self) -> None:
        """Drop all cached data (useful for hot-reload in development)."""
        self._atlases.clear()
        self._tile_to_atlas.clear()
        self._standalone.clear()
        self._tint_cache.clear()
        self._loaded = False
