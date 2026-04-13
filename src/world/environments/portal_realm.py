"""Portal Realm environment — a shared ancient ruins map accessible via restored portals."""

import collections
import random

from src.config import TILE, TREASURE_CHEST, GRASS
from src.config import PORTAL_FLOOR, PORTAL_WALL, PORTAL_ACTIVE
from src.world.environments.base import BaseEnvironment
from src.world.map import GameMap

REALM_ROWS = 50
REALM_COLS = 60


# ---------------------------------------------------------------------------
# Layout generator
# ---------------------------------------------------------------------------


def _cellular_automata(rng: random.Random, rows: int, cols: int) -> list[list[int]]:
    """Generate a ruined-chamber layout via cellular automata.

    Returns a binary grid: 1 = wall (PORTAL_WALL), 0 = floor (PORTAL_FLOOR).
    ~30% initial wall density produces open rooms with thick ancient walls.
    """
    grid = [[1 if rng.random() < 0.32 else 0 for _ in range(cols)] for _ in range(rows)]

    # Force solid 2-tile border
    for r in range(rows):
        for c in range(cols):
            if r <= 1 or r >= rows - 2 or c <= 1 or c >= cols - 2:
                grid[r][c] = 1

    for _ in range(4):
        new_grid = [[0] * cols for _ in range(rows)]
        for r in range(rows):
            for c in range(cols):
                if r <= 1 or r >= rows - 2 or c <= 1 or c >= cols - 2:
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
        (c, r)
        for r in range(rows)
        for c in range(cols)
        if world[r][c] in passable
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


# ---------------------------------------------------------------------------
# Environment class
# ---------------------------------------------------------------------------


class PortalRealmEnvironment(BaseEnvironment):
    """Shared ancient-ruins portal realm."""

    TILESET = "portal_realm"

    def generate(self) -> GameMap:
        """Generate the portal realm map."""
        rng = random.Random()  # Uses global random state; caller controls seeding

        layout = _cellular_automata(rng, REALM_ROWS, REALM_COLS)

        world = [
            [PORTAL_WALL if layout[r][c] else PORTAL_FLOOR for c in range(REALM_COLS)]
            for r in range(REALM_ROWS)
        ]

        # Spawn point: find a floor tile near the map centre
        cx, cy = REALM_COLS // 2, REALM_ROWS // 2
        spawn_col, spawn_row = cx, cy
        for dist in range(1, 20):
            for dc in range(-dist, dist + 1):
                for dr in range(-dist, dist + 1):
                    if abs(dc) != dist and abs(dr) != dist:
                        continue
                    c, r = cx + dc, cy + dr
                    if 0 <= c < REALM_COLS and 0 <= r < REALM_ROWS and world[r][c] == PORTAL_FLOOR:
                        spawn_col, spawn_row = c, r
                        break
                else:
                    continue
                break
            else:
                continue
            break

        _connect_regions(world, REALM_ROWS, REALM_COLS, spawn_col, spawn_row)

        # Scatter TREASURE_CHESTs in floor tiles far from spawn
        floor_tiles = [
            (c, r)
            for r in range(REALM_ROWS)
            for c in range(REALM_COLS)
            if world[r][c] == PORTAL_FLOOR
            and abs(c - spawn_col) + abs(r - spawn_row) >= 8
        ]
        rng.shuffle(floor_tiles)
        chest_count = rng.randint(8, 12)
        placed_chests: list[tuple[int, int]] = []
        for c, r in floor_tiles:
            if all(abs(c - ec) + abs(r - er) >= 4 for ec, er in placed_chests):
                world[r][c] = TREASURE_CHEST
                placed_chests.append((c, r))
                if len(placed_chests) >= chest_count:
                    break

        # Place the realm exit portal near the spawn point (south side)
        exit_col, exit_row = spawn_col, min(REALM_ROWS - 3, spawn_row + 6)
        while exit_row < REALM_ROWS - 2 and world[exit_row][exit_col] != PORTAL_FLOOR:
            exit_row -= 1
        world[exit_row][exit_col] = PORTAL_ACTIVE

        game_map = GameMap(world, tileset=self.TILESET)
        game_map.spawn_col = spawn_col
        game_map.spawn_row = spawn_row
        game_map.exit_col = exit_col
        game_map.exit_row = exit_row

        return game_map
