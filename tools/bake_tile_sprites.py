#!/usr/bin/env python3
"""Bake procedural tile art into atlas sprite sheets.

Generates one atlas PNG + JSON manifest per terrain group under
``assets/tiles/``.  Each tile type gets 16 adjacency variants (4-bit
cardinal mask) × 4 animation frames at 64×64 px cells.

Also generates standalone sprites for SIGN, BROKEN_LADDER, SKY_LADDER
under ``assets/tiles/standalone/``.

Usage::

    python tools/bake_tile_sprites.py
"""

from __future__ import annotations

import json
import math
import os
import random
import sys

# Allow importing src.* from repository root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

pygame.init()
# Dummy display required by convert_alpha
_DUMMY = pygame.display.set_mode((1, 1))

from src.config import (  # noqa: E402
    TILE,
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
from src.data.tiles import TILE_INFO  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CELL = 64  # must match TILE
COLS = 4   # animation frames per variant
ROWS_PER_TILE = 16  # one per adjacency mask

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "assets", "tiles")
STANDALONE_DIR = os.path.join(OUT_DIR, "standalone")

# ---------------------------------------------------------------------------
# Tile name mapping  (tile_id → sprite name used in the atlas manifest)
# ---------------------------------------------------------------------------

TILE_NAMES: dict[int, str] = {
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

# Terrain group definitions: atlas_name → list of tile IDs
TERRAIN_GROUPS: dict[str, list[int]] = {
    "terrain_basic": [
        GRASS, DIRT, STONE, SAND, SNOW, ASH_GROUND, DEAD_GRASS,
        DIRT_PATH, COBBLESTONE, STONE_PATH, ROAD, SANDSTONE,
    ],
    "terrain_nature": [TREE, WATER, MOUNTAIN, CACTUS_TILE],
    "terrain_ore": [
        IRON_ORE, GOLD_ORE, DIAMOND_ORE, FROST_CRYSTAL_ORE,
        MAGMA_ORE, DESERT_CRYSTAL_ORE, VOID_ORE, MAGMA_STONE,
    ],
    "terrain_cave": [CAVE_WALL, CAVE_EXIT, CAVE_MOUNTAIN, CAVE_HILL],
    "terrain_water": [CORAL, REEF, DIVE_EXIT],
    "terrain_portal": [
        PORTAL_WALL, PORTAL_FLOOR, PORTAL_RUINS, PORTAL_ACTIVE,
        PORTAL_LAVA, ANCIENT_STONE,
    ],
    "terrain_settlement": [
        HOUSE, PIER, BOAT, TREASURE_CHEST, WOOD_FLOOR, WOOD_WALL,
        WORKTABLE, HOUSE_EXIT, SETTLEMENT_HOUSE,
    ],
    "terrain_biome": [
        ICE_PEAK, FROZEN_LAKE, LAVA_POOL, RUINS_WALL, BONE_PILE, GRAVE,
    ],
}

# FPS per tile (0 = static).  Tiles not listed default to 0.
TILE_FPS: dict[int, float] = {
    WATER: 3.0, LAVA_POOL: 2.0, PORTAL_LAVA: 2.0,
    PORTAL_ACTIVE: 2.0, CAVE_EXIT: 1.5, DIVE_EXIT: 1.5,
    CORAL: 1.0, FROZEN_LAKE: 0.5,
}

# Standalone tiles (not in adjacency atlases)
STANDALONE_TILES: list[int] = [SIGN, BROKEN_LADDER, SKY_LADDER]


# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------

def _base_color(tid: int) -> tuple[int, int, int]:
    """Get the base color for a tile ID."""
    info = TILE_INFO.get(tid, {})
    return info.get("color", (100, 100, 100))


def _darken(color: tuple[int, int, int], amount: int = 25) -> tuple[int, int, int]:
    return (max(0, color[0] - amount), max(0, color[1] - amount),
            max(0, color[2] - amount))


def _lighten(color: tuple[int, int, int], amount: int = 25) -> tuple[int, int, int]:
    return (min(255, color[0] + amount), min(255, color[1] + amount),
            min(255, color[2] + amount))


def _edge_borders(
    surf: pygame.Surface, color: tuple[int, int, int], adj: int, width: int = 3,
) -> None:
    """Draw darker edge borders on sides where there is NO same-type neighbor."""
    dark = _darken(color, 35)
    c = CELL
    if not (adj & 0b1000):  # no north neighbor
        pygame.draw.rect(surf, dark, (0, 0, c, width))
    if not (adj & 0b0100):  # no east neighbor
        pygame.draw.rect(surf, dark, (c - width, 0, width, c))
    if not (adj & 0b0010):  # no south neighbor
        pygame.draw.rect(surf, dark, (0, c - width, c, width))
    if not (adj & 0b0001):  # no west neighbor
        pygame.draw.rect(surf, dark, (0, 0, width, c))


def _noise_texture(
    surf: pygame.Surface, color: tuple[int, int, int], rng: random.Random,
    density: float = 0.08, var: int = 15,
) -> None:
    """Add subtle pixel noise texture to a surface."""
    c = CELL
    n = int(c * c * density)
    for _ in range(n):
        x = rng.randint(0, c - 1)
        y = rng.randint(0, c - 1)
        d = rng.randint(-var, var)
        nc = (max(0, min(255, color[0] + d)),
              max(0, min(255, color[1] + d)),
              max(0, min(255, color[2] + d)))
        surf.set_at((x, y), nc)


# ---------------------------------------------------------------------------
# Per-tile-type rendering functions
# ---------------------------------------------------------------------------
# Each function signature: (surf, adj, frame, rng) → None
# surf: 64×64 SRCALPHA surface (already filled with base color)
# adj: 4-bit adjacency mask
# frame: animation frame index (0-3)
# rng: seeded Random for deterministic noise

def _draw_flat(surf: pygame.Surface, tid: int, adj: int, frame: int,
               rng: random.Random) -> None:
    """Generic flat terrain tile (grass, dirt, sand, etc.) with texture."""
    color = _base_color(tid)
    _noise_texture(surf, color, rng, density=0.06)
    _edge_borders(surf, color, adj, width=2)


def _draw_tree(surf: pygame.Surface, tid: int, adj: int, frame: int,
               rng: random.Random) -> None:
    """Tree tile: trunk + canopy; adjacency-interior shows dense canopy."""
    color = _base_color(tid)
    canopy_green = (30, 130, 30)
    trunk_brown = (100, 70, 30)
    c = CELL
    h = c // 2  # 32

    if adj == 0xF:
        # Interior: dense canopy covers entire tile
        pygame.draw.rect(surf, canopy_green, (0, 0, c, c))
        _noise_texture(surf, canopy_green, rng, density=0.1, var=20)
    else:
        # Trunk
        tw, th = 8, 20
        tx = (c - tw) // 2
        ty = c - th - 4
        pygame.draw.rect(surf, trunk_brown, (tx, ty, tw, th))
        # Canopy circle
        cr = 20 + (frame % 2)  # subtle sway
        pygame.draw.circle(surf, canopy_green, (h, h - 4), cr)
        _noise_texture(surf, canopy_green, rng, density=0.04, var=15)
        # Adjacency: extend canopy toward connected edges
        if adj & 0b1000:  # north
            pygame.draw.rect(surf, canopy_green, (h - 14, 0, 28, 10))
        if adj & 0b0100:  # east
            pygame.draw.rect(surf, canopy_green, (c - 10, h - 14, 10, 28))
        if adj & 0b0010:  # south
            pygame.draw.rect(surf, canopy_green, (h - 14, c - 10, 28, 10))
        if adj & 0b0001:  # west
            pygame.draw.rect(surf, canopy_green, (0, h - 14, 10, 28))
    _edge_borders(surf, color, adj, width=2)


def _draw_water(surf: pygame.Surface, tid: int, adj: int, frame: int,
                rng: random.Random) -> None:
    """Water tile with animated wave lines and shore edges."""
    color = _base_color(tid)
    c = CELL
    # Wave lines
    wave_c = (60, 150, 230)
    for wy in range(12, c - 8, 16):
        offset = frame * 4
        for wx in range(0, c, 4):
            dy = int(math.sin((wx + offset) * 0.15) * 3)
            pygame.draw.rect(surf, wave_c, (wx, wy + dy, 3, 2))
    # Shore edges (sandy border on non-water sides)
    shore = (180, 165, 110)
    bw = 6
    if not (adj & 0b1000):
        pygame.draw.rect(surf, shore, (0, 0, c, bw))
    if not (adj & 0b0100):
        pygame.draw.rect(surf, shore, (c - bw, 0, bw, c))
    if not (adj & 0b0010):
        pygame.draw.rect(surf, shore, (0, c - bw, c, bw))
    if not (adj & 0b0001):
        pygame.draw.rect(surf, shore, (0, 0, bw, c))


def _draw_mountain(surf: pygame.Surface, tid: int, adj: int, frame: int,
                   rng: random.Random) -> None:
    """Mountain tile: isolated = single peak, interior = ridge texture."""
    color = _base_color(tid)
    c = CELL
    h = c // 2

    if adj == 0xF:
        # Interior: rocky ridge texture
        ridge = _lighten(color, 15)
        _noise_texture(surf, color, rng, density=0.12, var=20)
        # Subtle horizontal ridge lines
        for ry in range(10, c, 14):
            pygame.draw.line(surf, ridge, (4, ry), (c - 4, ry), 1)
    else:
        # Draw a peak triangle
        pygame.draw.polygon(surf, _lighten(color, 20),
                            [(8, c - 4), (h, 4), (c - 8, c - 4)])
        # Snow cap
        pygame.draw.polygon(surf, (230, 230, 240),
                            [(h - 8, 16), (h, 4), (h + 8, 16)])
        # Ridge crack details
        pygame.draw.line(surf, _darken(color, 20), (h - 6, 28), (h - 2, 18), 1)
        pygame.draw.line(surf, _darken(color, 20), (h + 6, 30), (h + 8, 20), 1)
    _edge_borders(surf, color, adj, width=2)


def _draw_ore(surf: pygame.Surface, tid: int, adj: int, frame: int,
              rng: random.Random) -> None:
    """Ore tile: host rock with bright ore vein dots; denser when grouped."""
    info = TILE_INFO.get(tid, {})
    color = _base_color(tid)
    bright = _lighten(color, 80)
    c = CELL
    _noise_texture(surf, color, rng, density=0.06, var=10)
    # Ore sparkle dots — more when surrounded
    num_dots = 4 + bin(adj).count("1") * 2
    for _ in range(num_dots):
        ox = rng.randint(6, c - 6)
        oy = rng.randint(6, c - 6)
        sz = rng.randint(2, 4)
        pygame.draw.rect(surf, bright, (ox, oy, sz, sz))
    _edge_borders(surf, color, adj, width=2)


def _draw_cave_wall(surf: pygame.Surface, tid: int, adj: int, frame: int,
                    rng: random.Random) -> None:
    """Cave wall with rough rock texture and edge seams."""
    color = _base_color(tid)
    _noise_texture(surf, color, rng, density=0.12, var=20)
    # Crack lines
    dark = _darken(color, 30)
    for _ in range(3):
        x1 = rng.randint(4, CELL - 4)
        y1 = rng.randint(4, CELL - 4)
        x2 = x1 + rng.randint(-12, 12)
        y2 = y1 + rng.randint(-12, 12)
        pygame.draw.line(surf, dark, (x1, y1), (x2, y2), 1)
    _edge_borders(surf, color, adj, width=3)


def _draw_cave_entrance(surf: pygame.Surface, tid: int, adj: int, frame: int,
                        rng: random.Random) -> None:
    """Cave entrance (mountain or hill style)."""
    color = _base_color(tid)
    c = CELL
    # Dark opening
    shadow = _darken(color, 30)
    pygame.draw.rect(surf, color, (8, 16, 48, 40))
    pygame.draw.polygon(surf, shadow,
                        [(16, 24), (48, 24), (40, 40), (20, 40)])
    # Rock detail
    rock = _lighten(color, 20)
    pygame.draw.circle(surf, rock, (24, 30), 4)
    pygame.draw.circle(surf, rock, (40, 28), 4)
    pygame.draw.circle(surf, rock, (32, 40), 4)
    _edge_borders(surf, color, adj, width=2)


def _draw_cave_exit(surf: pygame.Surface, tid: int, adj: int, frame: int,
                    rng: random.Random) -> None:
    """Cave exit: glowing ladder."""
    c = CELL
    pulse = int(math.sin(frame * 1.5) * 20 + 40)
    glow = (pulse + 40, pulse + 80, pulse + 40)
    pygame.draw.rect(surf, glow, (8, 4, 48, 56))
    # Ladder
    rung = (120, 90, 50)
    for ry in range(12, 56, 12):
        pygame.draw.line(surf, rung, (16, ry), (48, ry), 4)
    pygame.draw.line(surf, rung, (16, 8), (16, 56), 4)
    pygame.draw.line(surf, rung, (48, 8), (48, 56), 4)


def _draw_pier(surf: pygame.Surface, tid: int, adj: int, frame: int,
               rng: random.Random) -> None:
    """Wooden dock planks."""
    c = CELL
    plank = (155, 115, 50)
    edge = (100, 75, 30)
    pygame.draw.rect(surf, plank, (4, 4, 56, 56))
    # Plank lines
    for lx in range(12, 58, 14):
        pygame.draw.line(surf, edge, (lx, 4), (lx, 60), 1)
    pygame.draw.rect(surf, edge, (4, 4, 56, 56), 1)
    _edge_borders(surf, _base_color(tid), adj, width=2)


def _draw_boat(surf: pygame.Surface, tid: int, adj: int, frame: int,
               rng: random.Random) -> None:
    """Small moored boat."""
    c = CELL
    # Hull
    pygame.draw.polygon(surf, (120, 80, 40),
                        [(8, 36), (56, 36), (48, 56), (16, 56)])
    # Mast
    pygame.draw.line(surf, (80, 55, 25), (32, 8), (32, 36), 4)
    # Sail
    pygame.draw.polygon(surf, (235, 225, 195),
                        [(34, 10), (34, 34), (54, 22)])
    # Cabin
    pygame.draw.rect(surf, (160, 110, 55), (20, 24, 16, 14))
    pygame.draw.rect(surf, (180, 220, 255), (24, 26, 6, 6))


def _draw_treasure(surf: pygame.Surface, tid: int, adj: int, frame: int,
                   rng: random.Random) -> None:
    """Treasure chest with shimmer."""
    c = CELL
    body = (185, 130, 40)
    band = (230, 180, 60)
    dark = (120, 85, 25)
    # Body
    pygame.draw.rect(surf, body, (8, 28, 48, 28))
    # Lid
    pygame.draw.rect(surf, body, (8, 16, 48, 16))
    # Band
    pygame.draw.rect(surf, band, (8, 32, 48, 6))
    # Lock
    pygame.draw.rect(surf, dark, (26, 34, 12, 10))
    pygame.draw.ellipse(surf, dark, (26, 28, 12, 12))
    # Shimmer
    sp = int(math.sin(frame * 1.5) * 4) + 4
    pygame.draw.line(surf, (255, 240, 130),
                     (16, 8 + sp), (22, 2 + sp), 1)


def _draw_coral(surf: pygame.Surface, tid: int, adj: int, frame: int,
                rng: random.Random) -> None:
    """Coral formation with branching arms."""
    info = TILE_INFO.get(tid, {})
    color = info.get("color", (240, 80, 130))
    bright = _lighten(color, 60)
    c = CELL
    h = c // 2
    sway = int(math.sin(frame * 1.2) * 2)
    # Central stalk
    pygame.draw.line(surf, color, (h, c - 8), (h + sway, h - 4), 4)
    # Left branch
    pygame.draw.line(surf, color, (h + sway, h + 4), (h - 16 + sway, h - 12), 4)
    pygame.draw.circle(surf, bright, (h - 16 + sway, h - 13), 6)
    # Right branch
    pygame.draw.line(surf, color, (h + sway, h), (h + 16 + sway, h - 16), 4)
    pygame.draw.circle(surf, bright, (h + 16 + sway, h - 17), 6)
    # Top
    pygame.draw.circle(surf, bright, (h + sway, h - 6), 6)


def _draw_dive_exit(surf: pygame.Surface, tid: int, adj: int, frame: int,
                    rng: random.Random) -> None:
    """Dive exit: upward chevrons with bubbles."""
    c = CELL
    pulse = int(math.sin(frame * 1.5) * 15 + 40)
    glow = (pulse, pulse + 80, min(255, pulse + 120))
    pygame.draw.rect(surf, glow, (8, 4, 48, 56))
    arrow = (200, 240, 255)
    pygame.draw.polygon(surf, arrow, [(32, 12), (20, 28), (44, 28)])
    pygame.draw.polygon(surf, arrow, [(32, 28), (20, 44), (44, 44)])
    # Bubble
    bub = int(math.sin(frame * 1.2 + 1.5) * 6)
    pygame.draw.circle(surf, (180, 230, 255), (48, 20 + bub), 4)


def _draw_portal_wall(surf: pygame.Surface, tid: int, adj: int, frame: int,
                      rng: random.Random) -> None:
    """Ancient stone brick pattern."""
    color = _base_color(tid)
    mortar = _darken(color, 20)
    c = CELL
    # Horizontal mortar lines
    pygame.draw.line(surf, mortar, (0, 20), (c, 20), 1)
    pygame.draw.line(surf, mortar, (0, 44), (c, 44), 1)
    # Vertical mortar (offset pattern)
    pygame.draw.line(surf, mortar, (32, 0), (32, 20), 1)
    pygame.draw.line(surf, mortar, (16, 20), (16, 44), 1)
    pygame.draw.line(surf, mortar, (48, 20), (48, 44), 1)
    pygame.draw.line(surf, mortar, (32, 44), (32, c), 1)
    _edge_borders(surf, color, adj, width=2)


def _draw_portal_floor(surf: pygame.Surface, tid: int, adj: int, frame: int,
                       rng: random.Random) -> None:
    """Portal floor with engraved cross/circle."""
    color = _base_color(tid)
    c = CELL
    h = c // 2
    etch = _darken(color, 12)
    pygame.draw.circle(surf, etch, (h, h), 16, 1)
    pygame.draw.line(surf, etch, (h, 16), (h, 48), 1)
    pygame.draw.line(surf, etch, (16, h), (48, h), 1)
    _edge_borders(surf, color, adj, width=2)


def _draw_portal_ruins(surf: pygame.Surface, tid: int, adj: int, frame: int,
                       rng: random.Random) -> None:
    """Crumbled stone ring."""
    c = CELL
    stone = (90, 80, 95)
    moss = (60, 80, 55)
    pygame.draw.rect(surf, stone, (8, 48, 48, 10))
    pygame.draw.rect(surf, stone, (8, 20, 10, 28))
    pygame.draw.rect(surf, stone, (46, 28, 10, 20))
    pygame.draw.rect(surf, stone, (20, 12, 10, 36))
    pygame.draw.rect(surf, moss, (8, 20, 6, 6))
    pygame.draw.rect(surf, moss, (46, 28, 6, 4))
    pygame.draw.rect(surf, (25, 20, 30), (20, 28, 24, 20))


def _draw_portal_active(surf: pygame.Surface, tid: int, adj: int, frame: int,
                        rng: random.Random) -> None:
    """Glowing portal ring with pulsing energy."""
    c = CELL
    h = c // 2
    pulse = math.sin(frame * 1.5)
    stone = (110, 95, 125)
    pygame.draw.rect(surf, stone, (8, 48, 48, 10))
    pygame.draw.rect(surf, stone, (8, 12, 10, 36))
    pygame.draw.rect(surf, stone, (46, 12, 10, 36))
    pygame.draw.rect(surf, stone, (20, 8, 24, 8))
    # Energy
    er = max(0, min(255, int(140 + pulse * 30)))
    eg = max(0, min(255, int(50 + pulse * 20)))
    eb = max(0, min(255, int(220 + pulse * 35)))
    pygame.draw.ellipse(surf, (er, eg, eb), (18, 16, 28, 32))
    ib = max(0, min(255, int(200 + pulse * 55)))
    pygame.draw.ellipse(surf, (255, 200, ib), (24, 22, 16, 20))


def _draw_ancient_stone(surf: pygame.Surface, tid: int, adj: int, frame: int,
                        rng: random.Random) -> None:
    """Stone obelisk."""
    c = CELL
    h = c // 2
    stone = (120, 110, 100)
    pygame.draw.rect(surf, stone, (22, 24, 20, 32))
    pygame.draw.polygon(surf, stone, [(22, 24), (42, 24), (h, 12)])
    # Rune markings
    pygame.draw.line(surf, (80, 72, 65), (28, 28), (36, 28), 1)
    pygame.draw.line(surf, (80, 72, 65), (28, 36), (36, 36), 1)
    _edge_borders(surf, _base_color(tid), adj, width=2)


def _draw_house(surf: pygame.Surface, tid: int, adj: int, frame: int,
                rng: random.Random) -> None:
    """House tile with adjacency-aware walls/roof."""
    c = CELL
    wall = (160, 82, 45)
    roof = (140, 50, 50)
    window = (180, 220, 255)
    n = bool(adj & 0b1000)
    e = bool(adj & 0b0100)
    s = bool(adj & 0b0010)
    w = bool(adj & 0b0001)
    # Wall fill
    pygame.draw.rect(surf, wall, (0, 0, c, c))
    # Roof on top edge if no north neighbor
    if not n:
        pygame.draw.rect(surf, roof, (0, 0, c, 12))
        # Ridge line
        pygame.draw.line(surf, _darken(roof, 20), (0, 11), (c, 11), 1)
    # Door on south edge if no south neighbor
    if not s:
        pygame.draw.rect(surf, (100, 60, 30), (24, c - 18, 16, 18))
        pygame.draw.circle(surf, (200, 180, 50), (36, c - 10), 2)
    # Window if isolated enough
    if not (n and s):
        pygame.draw.rect(surf, window, (12, 20, 12, 12))
        pygame.draw.rect(surf, window, (40, 20, 12, 12))
        # Cross pane
        pygame.draw.line(surf, wall, (18, 20), (18, 31), 1)
        pygame.draw.line(surf, wall, (12, 26), (23, 26), 1)
        pygame.draw.line(surf, wall, (46, 20), (46, 31), 1)
        pygame.draw.line(surf, wall, (40, 26), (51, 26), 1)
    # Edge seams
    if not e:
        pygame.draw.line(surf, _darken(wall, 25), (c - 1, 0), (c - 1, c), 1)
    if not w:
        pygame.draw.line(surf, _darken(wall, 25), (0, 0), (0, c), 1)


def _draw_cactus(surf: pygame.Surface, tid: int, adj: int, frame: int,
                 rng: random.Random) -> None:
    """Cactus tile: single cactus or denser when grouped."""
    color = _base_color(tid)
    c = CELL
    h = c // 2
    cactus_g = (45, 150, 80)
    dark_g = (35, 120, 60)
    if adj == 0xF:
        # Dense cactus patch
        for cx, cy in [(16, 16), (44, 20), (28, 44), (48, 48)]:
            pygame.draw.rect(surf, cactus_g, (cx - 4, cy, 8, 20))
            pygame.draw.rect(surf, dark_g, (cx - 8, cy + 6, 6, 4))
            pygame.draw.rect(surf, dark_g, (cx + 4, cy + 4, 6, 4))
    else:
        # Single cactus
        pygame.draw.rect(surf, cactus_g, (h - 4, 12, 8, 40))
        pygame.draw.rect(surf, dark_g, (h - 12, 22, 8, 6))
        pygame.draw.rect(surf, dark_g, (h + 4, 18, 8, 6))
    _edge_borders(surf, color, adj, width=2)


def _draw_lava(surf: pygame.Surface, tid: int, adj: int, frame: int,
               rng: random.Random) -> None:
    """Lava or portal-lava tile with animated glow."""
    color = _base_color(tid)
    c = CELL
    bright = _lighten(color, 60)
    for wy in range(8, c - 4, 12):
        offset = frame * 6
        for wx in range(0, c, 6):
            dy = int(math.sin((wx + offset) * 0.12) * 3)
            clr = bright if (wx + wy) % 12 < 6 else color
            pygame.draw.rect(surf, clr, (wx, wy + dy, 5, 4))
    _edge_borders(surf, color, adj, width=3)


def _draw_frozen_lake(surf: pygame.Surface, tid: int, adj: int, frame: int,
                      rng: random.Random) -> None:
    """Frozen lake with ice crack texture."""
    color = _base_color(tid)
    c = CELL
    _noise_texture(surf, color, rng, density=0.04, var=8)
    crack = _darken(color, 30)
    # A few crack lines
    rng2 = random.Random(adj * 1000 + 42)
    for _ in range(2):
        x1 = rng2.randint(8, c - 8)
        y1 = rng2.randint(8, c - 8)
        x2 = x1 + rng2.randint(-20, 20)
        y2 = y1 + rng2.randint(-20, 20)
        pygame.draw.line(surf, crack, (x1, y1), (x2, y2), 1)
    # Glint animation
    gx = 16 + frame * 12
    pygame.draw.rect(surf, _lighten(color, 30), (gx, 20, 3, 3))
    _edge_borders(surf, color, adj, width=2)


# Dispatch table: tile_id → draw function
# Tiles not listed use _draw_flat
DRAW_DISPATCH: dict[int, type] = {
    TREE: _draw_tree,
    WATER: _draw_water,
    MOUNTAIN: _draw_mountain,
    CACTUS_TILE: _draw_cactus,
    IRON_ORE: _draw_ore, GOLD_ORE: _draw_ore, DIAMOND_ORE: _draw_ore,
    FROST_CRYSTAL_ORE: _draw_ore, MAGMA_ORE: _draw_ore,
    DESERT_CRYSTAL_ORE: _draw_ore, VOID_ORE: _draw_ore,
    MAGMA_STONE: _draw_ore,
    CAVE_WALL: _draw_cave_wall,
    CAVE_MOUNTAIN: _draw_cave_entrance, CAVE_HILL: _draw_cave_entrance,
    CAVE_EXIT: _draw_cave_exit,
    PIER: _draw_pier, BOAT: _draw_boat,
    TREASURE_CHEST: _draw_treasure,
    CORAL: _draw_coral, DIVE_EXIT: _draw_dive_exit,
    PORTAL_WALL: _draw_portal_wall, PORTAL_FLOOR: _draw_portal_floor,
    PORTAL_RUINS: _draw_portal_ruins, PORTAL_ACTIVE: _draw_portal_active,
    ANCIENT_STONE: _draw_ancient_stone,
    HOUSE: _draw_house,
    LAVA_POOL: _draw_lava, PORTAL_LAVA: _draw_lava,
    FROZEN_LAKE: _draw_frozen_lake,
    REEF: _draw_cave_wall,  # reuse rocky texture
}


# ---------------------------------------------------------------------------
# Standalone tile baking
# ---------------------------------------------------------------------------

def _bake_standalone(tid: int, name: str) -> tuple[pygame.Surface, dict]:
    """Bake a standalone tile sprite (e.g. sign, ladder)."""
    from src.rendering.registry import SpriteRegistry

    # Try to load existing entity sprite for this tile
    reg = SpriteRegistry.get_instance()
    data = reg.get(name)
    if data is not None:
        sheet, manifest = data
        fw, fh = manifest["frame_size"]
        state = manifest["states"].get("idle")
        if state is not None:
            row = state["row"]
            frames = state.get("frames", 1)
            out_w = fw * frames
            out = pygame.Surface((out_w, fh), pygame.SRCALPHA)
            for f in range(frames):
                src_rect = pygame.Rect(f * fw, row * fh, fw, fh)
                out.blit(sheet.subsurface(src_rect), (f * fw, 0))
            mf: dict = {
                "frame_size": [fw, fh],
                "frames": frames,
                "fps": state.get("fps", 0),
                "draw_offset": [0, -(fh - CELL)],
            }
            return out, mf

    # Fallback: simple colored rect
    color = _base_color(tid)
    w, h = CELL, CELL * 2 if tid in (BROKEN_LADDER, SKY_LADDER) else CELL
    out = pygame.Surface((w, h), pygame.SRCALPHA)
    out.fill(color)
    mf = {
        "frame_size": [w, h],
        "frames": 1,
        "fps": 0,
        "draw_offset": [0, -(h - CELL)],
    }
    return out, mf


# ---------------------------------------------------------------------------
# Atlas baking
# ---------------------------------------------------------------------------

def _bake_atlas(atlas_name: str, tile_ids: list[int]) -> None:
    """Bake one atlas PNG + JSON for a terrain group."""
    num_tiles = len(tile_ids)
    total_rows = num_tiles * ROWS_PER_TILE
    width = COLS * CELL  # 256
    height = total_rows * CELL

    atlas = pygame.Surface((width, height), pygame.SRCALPHA)
    atlas.fill((0, 0, 0, 0))

    manifest_tiles: dict[str, dict] = {}

    for tile_idx, tid in enumerate(tile_ids):
        name = TILE_NAMES.get(tid)
        if name is None:
            continue
        start_row = tile_idx * ROWS_PER_TILE
        fps = TILE_FPS.get(tid, 0.0)
        manifest_tiles[name] = {"start_row": start_row, "fps": fps}

        draw_fn = DRAW_DISPATCH.get(tid, _draw_flat)

        for adj in range(16):
            for frame in range(COLS):
                surf = pygame.Surface((CELL, CELL), pygame.SRCALPHA)
                # Fill with base color
                base = _base_color(tid)
                surf.fill((*base, 255))
                # Deterministic RNG per (tile, adj, frame)
                rng = random.Random(tid * 10000 + adj * 100 + frame)
                draw_fn(surf, tid, adj, frame, rng)
                # Place into atlas
                col_px = frame * CELL
                row_px = (start_row + adj) * CELL
                atlas.blit(surf, (col_px, row_px))

    # Write files
    os.makedirs(OUT_DIR, exist_ok=True)
    png_path = os.path.join(OUT_DIR, f"{atlas_name}.png")
    json_path = os.path.join(OUT_DIR, f"{atlas_name}.json")

    pygame.image.save(atlas, png_path)
    manifest: dict = {
        "cell_size": [CELL, CELL],
        "cols": COLS,
        "tiles": manifest_tiles,
    }
    with open(json_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"  {atlas_name}: {width}×{height} px, {num_tiles} tile types → {png_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("Baking tile atlases...")

    # Pre-load existing entity sprites for standalone reuse
    from src.rendering.registry import SpriteRegistry
    sprites_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "assets", "sprites",
    )
    SpriteRegistry.get_instance().load_all(sprites_dir)

    # Bake each terrain group atlas
    for atlas_name, tile_ids in TERRAIN_GROUPS.items():
        _bake_atlas(atlas_name, tile_ids)

    # Bake standalone tiles
    os.makedirs(STANDALONE_DIR, exist_ok=True)
    for tid in STANDALONE_TILES:
        name = TILE_NAMES.get(tid)
        if name is None:
            continue
        sheet, mf = _bake_standalone(tid, name)
        png_path = os.path.join(STANDALONE_DIR, f"{name}.png")
        json_path = os.path.join(STANDALONE_DIR, f"{name}.json")
        pygame.image.save(sheet, png_path)
        with open(json_path, "w") as f:
            json.dump(mf, f, indent=2)
        print(f"  standalone: {name} → {png_path}")

    print("Done!")


if __name__ == "__main__":
    main()
