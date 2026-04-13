"""Portal Realm environment — a shared ancient ruins map accessible via restored portals."""

import collections
import random

from src.config import TREASURE_CHEST, PORTAL_FLOOR, PORTAL_WALL, PORTAL_ACTIVE
from src.world.environments.base import BaseEnvironment
from src.world.map import GameMap

# Each sector maps to a SLOT_SIZE×SLOT_SIZE tile block in the realm.
# The inner 4×4 floor is the discoverable chamber; 2-tile wall border on each side.
SLOT_SIZE = 8
INIT_BUFFER = 2   # slots in every direction from home sector for initial CA generation

# Tile padding outside the outermost slot — mirrors MAP_BORDER from config.py so
# the HUD never overlaps walkable tiles in the portal realm either.
REALM_PADDING = 10


# ---------------------------------------------------------------------------
# Layout helpers
# ---------------------------------------------------------------------------


def _cellular_automata(rng: random.Random, rows: int, cols: int, border: int = 2) -> list[list[int]]:
    """Generate a ruined-chamber layout via cellular automata.

    Returns a binary grid: 1 = wall (PORTAL_WALL), 0 = floor (PORTAL_FLOOR).
    ~30% initial wall density produces open rooms with thick ancient walls.
    """
    grid = [[1 if rng.random() < 0.32 else 0 for _ in range(cols)] for _ in range(rows)]

    # Force solid border
    for r in range(rows):
        for c in range(cols):
            if r < border or r >= rows - border or c < border or c >= cols - border:
                grid[r][c] = 1

    for _ in range(4):
        new_grid = [[0] * cols for _ in range(rows)]
        for r in range(rows):
            for c in range(cols):
                if r < border or r >= rows - border or c < border or c >= cols - border:
                    new_grid[r][c] = 1
                    continue
                wall_neighbours = sum(
                    grid[r + dr][c + dc]
                    for dr in (-1, 0, 1)
                    for dc in (-1, 0, 1)
                    if 0 <= r + dr < rows and 0 <= c + dc < cols
                )
                new_grid[r][c] = 1 if wall_neighbours >= 5 else 0
        grid = new_grid

    return grid


def _connect_regions(
    world: list[list[int]],
    rows: int,
    cols: int,
    spawn_col: int,
    spawn_row: int,
) -> None:
    """Connect every isolated floor region to the spawn point."""
    passable = {PORTAL_FLOOR, TREASURE_CHEST, PORTAL_ACTIVE}

    def bfs(sc: int, sr: int, candidates: set) -> set:
        region: set = set()
        q: collections.deque = collections.deque([(sc, sr)])
        region.add((sc, sr))
        while q:
            c, r = q.popleft()
            for dc, dr in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                nc, nr = c + dc, r + dr
                if (nc, nr) not in region and (nc, nr) in candidates:
                    region.add((nc, nr))
                    q.append((nc, nr))
        return region

    all_floor = {
        (c, r) for r in range(rows) for c in range(cols) if world[r][c] in passable
    }

    if not all_floor or (spawn_col, spawn_row) not in all_floor:
        return

    spawn_region = bfs(spawn_col, spawn_row, all_floor)
    remaining = all_floor - spawn_region

    while remaining:
        tgt = next(iter(remaining))
        tc, tr = tgt

        # Carve an L-shaped corridor from spawn_region to the target
        ref = min(spawn_region, key=lambda p: abs(p[0] - tc) + abs(p[1] - tr))
        rc, rr = ref

        # Horizontal then vertical
        step_c = 1 if tc > rc else -1
        for c in range(rc, tc + step_c, step_c):
            world[rr][c] = PORTAL_FLOOR
            all_floor.add((c, rr))
        step_r = 1 if tr > rr else -1
        for r in range(rr, tr + step_r, step_r):
            world[r][tc] = PORTAL_FLOOR
            all_floor.add((tc, r))

        spawn_region = bfs(spawn_col, spawn_row, all_floor)
        remaining = all_floor - spawn_region


def carve_chamber(world: list[list[int]], slot_col: int, slot_row: int) -> None:
    """Carve a 4×4 PORTAL_FLOOR chamber at the given slot top-left position."""
    for r in range(slot_row + 2, slot_row + SLOT_SIZE - 2):
        for c in range(slot_col + 2, slot_col + SLOT_SIZE - 2):
            world[r][c] = PORTAL_FLOOR


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
        init_slots = INIT_BUFFER * 2 + 1                       # = 5
        rows = init_slots * SLOT_SIZE + 2 * REALM_PADDING      # = 60
        cols = init_slots * SLOT_SIZE + 2 * REALM_PADDING      # = 60

        layout = _cellular_automata(rng, rows, cols, border=REALM_PADDING)

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

        _connect_regions(world, rows, cols, spawn_col, spawn_row)

        # No chests placed here — one chest is spawned per portal via Game._add_realm_portal().

        game_map = GameMap(world, tileset=self.TILESET)
        game_map.spawn_col   = spawn_col
        game_map.spawn_row   = spawn_row
        game_map.origin_sx   = -INIT_BUFFER   # = -2
        game_map.origin_sy   = -INIT_BUFFER   # = -2
        game_map.slot_size   = SLOT_SIZE
        game_map.slot_padding = REALM_PADDING
        game_map.slot_cols   = INIT_BUFFER * 2 + 1   # number of slot columns = 5
        game_map.slot_rows   = INIT_BUFFER * 2 + 1   # number of slot rows    = 5
        game_map.portal_exits = {}            # (col, row) → dest map_key

        return game_map


