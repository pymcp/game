"""Portal Realm environment — a shared ancient ruins map accessible via restored portals."""

import random

from src.config import (
    TREASURE_CHEST,
    PORTAL_FLOOR,
    PORTAL_WALL,
    PORTAL_ACTIVE,
    VOID_ORE,
    PORTAL_LAVA,
)
from src.world.environments.base import BaseEnvironment
from src.world.environments.utils import cellular_automata, connect_regions
from src.world.map import GameMap

# Each sector maps to a SLOT_SIZE×SLOT_SIZE tile block in the realm.
# The inner 4×4 floor is the discoverable chamber; 2-tile wall border on each side.
SLOT_SIZE = 8
INIT_BUFFER = 2  # slots in every direction from home sector for initial CA generation

# Tile padding outside the outermost slot — mirrors MAP_BORDER from config.py so
# the HUD never overlaps walkable tiles in the portal realm either.
REALM_PADDING = 10


def carve_chamber(world: list[list[int]], slot_col: int, slot_row: int) -> None:
    """Carve a 4×4 PORTAL_FLOOR chamber at the given slot top-left position."""
    for r in range(slot_row + 2, slot_row + SLOT_SIZE - 2):
        for c in range(slot_col + 2, slot_col + SLOT_SIZE - 2):
            world[r][c] = PORTAL_FLOOR
    # Scatter 2–4 VOID_ORE in the new chamber's floor
    floor_tiles = [
        (c, r)
        for r in range(slot_row + 2, slot_row + SLOT_SIZE - 2)
        for c in range(slot_col + 2, slot_col + SLOT_SIZE - 2)
    ]
    count = random.randint(2, 4)
    for fc, fr in random.sample(floor_tiles, min(count, len(floor_tiles))):
        world[fr][fc] = VOID_ORE


def _carve_lava_river(
    world: list[list[int]],
    rows: int,
    cols: int,
    spawn_col: int,
    spawn_row: int,
) -> None:
    """Carve a 4-tile-wide horizontal PORTAL_LAVA river across the portal realm.

    The river runs through the vertical midpoint of the map. A 12-tile gap is
    left around the spawn column so the player can always safely leave spawn.
    """
    mid_row = rows // 2
    safe_min = max(REALM_PADDING, spawn_col - 6)
    safe_max = min(cols - REALM_PADDING - 1, spawn_col + 6)
    for r in range(mid_row - 2, mid_row + 2):
        for c in range(REALM_PADDING, cols - REALM_PADDING):
            if safe_min <= c <= safe_max:
                continue  # preserve gap near spawn
            world[r][c] = PORTAL_LAVA


# ---------------------------------------------------------------------------
# Environment class
# ---------------------------------------------------------------------------


class PortalRealmEnvironment(BaseEnvironment):
    """Shared ancient-ruins portal realm — grows dynamically as islands are discovered."""

    TILESET = "portal_realm"

    def generate(self) -> GameMap:
        """Generate the initial portal realm map.

        Creates a cellular-automata ruined layout. The map is padded with
        REALM_PADDING solid-wall tiles on every side so that the first walkable
        tile is always beyond the HUD panels.  Slot positions are:
            slot_col = REALM_PADDING + ix * SLOT_SIZE
        which keeps ix=0 slots at exactly REALM_PADDING tiles from the map edge.
        """
        rng = random.Random()
        init_slots = INIT_BUFFER * 2 + 1  # = 5
        rows = init_slots * SLOT_SIZE + 2 * REALM_PADDING  # = 60
        cols = init_slots * SLOT_SIZE + 2 * REALM_PADDING  # = 60

        layout = cellular_automata(
            rng, rows, cols, density=0.32, iterations=4, border=REALM_PADDING
        )

        world = [
            [PORTAL_WALL if layout[r][c] else PORTAL_FLOOR for c in range(cols)]
            for r in range(rows)
        ]

        # Connectivity anchor: centre of the home island slot (ix=INIT_BUFFER=2)
        cx = REALM_PADDING + INIT_BUFFER * SLOT_SIZE + SLOT_SIZE // 2  # = 30
        cy = REALM_PADDING + INIT_BUFFER * SLOT_SIZE + SLOT_SIZE // 2  # = 30
        spawn_col, spawn_row = cx, cy

        # Find the nearest actual floor tile to the anchor
        for dist in range(1, 20):
            for dc in range(-dist, dist + 1):
                for dr in range(-dist, dist + 1):
                    if abs(dc) != dist and abs(dr) != dist:
                        continue
                    c, r = cx + dc, cy + dr
                    if 0 <= c < cols and 0 <= r < rows and world[r][c] == PORTAL_FLOOR:
                        spawn_col, spawn_row = c, r
                        break
                else:
                    continue
                break
            else:
                continue
            break

        connect_regions(
            world,
            rows,
            cols,
            spawn_col,
            spawn_row,
            {PORTAL_FLOOR, TREASURE_CHEST, PORTAL_ACTIVE},
            PORTAL_FLOOR,
            REALM_PADDING,
        )

        # No chests placed here — one chest is spawned per portal via Game._add_realm_portal().

        # Carve a lava river through the middle of the realm
        _carve_lava_river(world, rows, cols, spawn_col, spawn_row)

        # Scatter initial VOID_ORE on portal floor tiles
        floor_tiles = [
            (c, r)
            for r in range(REALM_PADDING, rows - REALM_PADDING)
            for c in range(REALM_PADDING, cols - REALM_PADDING)
            if world[r][c] == PORTAL_FLOOR
        ]
        ore_count = min(15, len(floor_tiles))
        for c, r in rng.sample(floor_tiles, ore_count):
            world[r][c] = VOID_ORE

        game_map = GameMap(world, tileset=self.TILESET)
        game_map.spawn_col = spawn_col
        game_map.spawn_row = spawn_row
        game_map.origin_sx = -INIT_BUFFER  # = -2
        game_map.origin_sy = -INIT_BUFFER  # = -2
        game_map.slot_size = SLOT_SIZE
        game_map.slot_padding = REALM_PADDING
        game_map.slot_cols = INIT_BUFFER * 2 + 1  # number of slot columns = 5
        game_map.slot_rows = INIT_BUFFER * 2 + 1  # number of slot rows    = 5
        game_map.portal_exits = {}  # (col, row) → dest map_key

        return game_map
