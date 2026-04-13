"""Cave environment — generates caverns with walls, ore, and cave-specific enemies."""

import collections
import math
import random

from src.config import (
    TILE,
    WORLD_COLS,
    GRASS,
    STONE,
    IRON_ORE,
    GOLD_ORE,
    DIAMOND_ORE,
    CAVE_MOUNTAIN,
    CAVE_EXIT,
    CAVE_WALL,
    TREASURE_CHEST,
)
from src.data import ENEMY_TYPES, EnemyEnvironment
from src.world.environments.base import BaseEnvironment
from src.world.map import GameMap

# Enemy pools derived from ENEMY_TYPES definitions
_MOUNTAIN_CAVE_ENEMIES = [
    k
    for k, v in ENEMY_TYPES.items()
    if EnemyEnvironment.CAVE_MOUNTAIN in v.get("environments", [])
]
_HILL_CAVE_ENEMIES = [
    k
    for k, v in ENEMY_TYPES.items()
    if EnemyEnvironment.CAVE_HILL in v.get("environments", [])
]

CAVE_ROWS = 50
CAVE_COLS = 50


# ---------------------------------------------------------------------------
# Layout generators  (return a 2-D grid: 1 = wall, 0 = floor)
# ---------------------------------------------------------------------------


def _cellular_automata(rng: random.Random, rows: int, cols: int) -> list[list[int]]:
    """Open-cavern layout via 5 rounds of cellular automata."""
    grid = [[1 if rng.random() < 0.45 else 0 for _ in range(cols)] for _ in range(rows)]

    # Force solid 2-tile border
    for r in range(rows):
        for c in range(cols):
            if r <= 1 or r >= rows - 2 or c <= 1 or c >= cols - 2:
                grid[r][c] = 1

    for _ in range(5):
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


def _drunkard_walk(rng: random.Random, rows: int, cols: int) -> list[list[int]]:
    """Labyrinth layout via a drunkard's walk with 2 walkers."""
    grid = [[1] * cols for _ in range(rows)]

    steps = int(rows * cols * 0.30)  # carve ~30 % of cells per walker
    for _ in range(2):
        r = rng.randint(rows // 4, 3 * rows // 4)
        c = rng.randint(cols // 4, 3 * cols // 4)
        for _ in range(steps):
            if 2 <= r < rows - 2 and 2 <= c < cols - 2:
                grid[r][c] = 0
                # Occasionally widen the corridor
                if rng.random() < 0.3:
                    nr = max(2, min(rows - 3, r + rng.randint(-1, 1)))
                    nc = max(2, min(cols - 3, c + rng.randint(-1, 1)))
                    grid[nr][nc] = 0
            dr, dc = rng.choice([(0, 1), (0, -1), (1, 0), (-1, 0)])
            r = max(2, min(rows - 3, r + dr))
            c = max(2, min(cols - 3, c + dc))

    return grid


def _ensure_all_regions_connected(cave_world: list[list[int]], rows: int, cols: int, spawn_col: int, spawn_row: int) -> None:
    """Connect every isolated GRASS/CAVE_EXIT region to the spawn point.

    After cellular-automata or drunkard-walk generation, open floor areas can
    be split into disconnected pockets.  This function finds those pockets and
    carves an L-shaped corridor between the closest pair of tiles linking each
    pocket to the main (spawn-reachable) region, guaranteeing the player can
    always walk from spawn to every open area.
    """
    passable = {GRASS, CAVE_EXIT}

    def bfs(start_c, start_r, candidate_set):
        region = set()
        queue = collections.deque([(start_c, start_r)])
        region.add((start_c, start_r))
        while queue:
            c, r = queue.popleft()
            for dc, dr in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                nc, nr = c + dc, r + dr
                if (nc, nr) not in region and (nc, nr) in candidate_set:
                    region.add((nc, nr))
                    queue.append((nc, nr))
        return region

    all_floor = {
        (c, r) for r in range(rows) for c in range(cols) if cave_world[r][c] in passable
    }

    if (spawn_col, spawn_row) not in all_floor:
        return  # spawn is on a non-passable tile — shouldn't happen

    main = bfs(spawn_col, spawn_row, all_floor)
    remaining = all_floor - main

    while remaining:
        # Pick next isolated region
        seed = next(iter(remaining))
        iso = bfs(seed[0], seed[1], remaining)

        # Find the closest tile pair (Manhattan) between main and iso regions
        best_dist = float("inf")
        best_main = best_iso = None
        for mc, mr in main:
            for ic, ir in iso:
                d = abs(mc - ic) + abs(mr - ir)
                if d < best_dist:
                    best_dist = d
                    best_main = (mc, mr)
                    best_iso = (ic, ir)

        # Carve an L-shaped corridor: horizontal first, then vertical
        c, r = best_iso
        tc, tr = best_main
        while c != tc:
            c += 1 if tc > c else -1
            if 1 <= c < cols - 1 and 1 <= r < rows - 1:
                cave_world[r][c] = GRASS
                all_floor.add((c, r))
                main.add((c, r))
        while r != tr:
            r += 1 if tr > r else -1
            if 1 <= c < cols - 1 and 1 <= r < rows - 1:
                cave_world[r][c] = GRASS
                all_floor.add((c, r))
                main.add((c, r))

        main |= iso
        remaining -= iso


# ---------------------------------------------------------------------------
# CaveEnvironment
# ---------------------------------------------------------------------------


class CaveEnvironment(BaseEnvironment):
    """Generates a unique cave map seeded by its overland entrance position.

    Two cave styles are possible (seeded-random, consistent per position):
      - Open cavern (70 %): cellular-automata organic chambers
      - Labyrinth   (30 %): drunkard's-walk winding passages

    Enemy pools differ by surface entrance type:
      - CAVE_MOUNTAIN: bats and cave trolls
      - CAVE_HILL:     goblins and cave spiders
    """

    TILESET = "cave"

    def __init__(self, cave_col: int, cave_row: int, cave_type: int = CAVE_MOUNTAIN) -> None:
        self.cave_col = cave_col
        self.cave_row = cave_row
        self.cave_type = cave_type

    # -- public api --------------------------------------------------------

    def generate(self) -> GameMap:
        """Generate and return a fully configured cave GameMap."""
        rng = random.Random(self.cave_col * 10_000 + self.cave_row)

        rows, cols = CAVE_ROWS, CAVE_COLS
        is_labyrinth = rng.random() < 0.30

        grid = (
            _drunkard_walk(rng, rows, cols)
            if is_labyrinth
            else _cellular_automata(rng, rows, cols)
        )

        # Build tile world from layout grid
        cave_world = [
            [CAVE_WALL if grid[r][c] == 1 else GRASS for c in range(cols)]
            for r in range(rows)
        ]

        # Scatter minerals only on floor tiles; mountain caves get more rare ore
        floor_tiles = [
            (c, r)
            for r in range(rows)
            for c in range(cols)
            if cave_world[r][c] == GRASS
        ]

        def scatter_ore(tile_id, count, cmin, cmax):
            for _ in range(count):
                if not floor_tiles:
                    break
                cx, cy = rng.choice(floor_tiles)
                for __ in range(rng.randint(cmin, cmax)):
                    nx = cx + rng.randint(-2, 2)
                    ny = cy + rng.randint(-2, 2)
                    if (
                        0 <= nx < cols
                        and 0 <= ny < rows
                        and cave_world[ny][nx] == GRASS
                    ):
                        cave_world[ny][nx] = tile_id

        if self.cave_type == CAVE_MOUNTAIN:
            scatter_ore(STONE, 20, 4, 8)
            scatter_ore(IRON_ORE, 12, 2, 5)
            scatter_ore(GOLD_ORE, 8, 1, 4)
            scatter_ore(DIAMOND_ORE, 6, 1, 3)
        else:
            scatter_ore(STONE, 25, 4, 8)
            scatter_ore(IRON_ORE, 15, 2, 5)
            scatter_ore(GOLD_ORE, 6, 1, 3)
            scatter_ore(DIAMOND_ORE, 3, 1, 2)

        # Place exit near the top; find a valid floor tile in upper rows
        exit_col, exit_row = self._find_floor_near_row(
            cave_world, rows, cols, rng, target_row=3
        )
        cave_world[exit_row][exit_col] = CAVE_EXIT

        # Spawn point a few tiles below the exit
        spawn_row = min(exit_row + 5, rows - 4)
        spawn_col = exit_col

        # Carve a guaranteed open corridor from exit down to spawn so the
        # player can always reach the exit, even in dense cellular-automata caves
        for r in range(exit_row, spawn_row + 1):
            for dc in range(-1, 2):  # 3-tile wide corridor
                cc = spawn_col + dc
                if 1 <= cc < cols - 1 and cave_world[r][cc] == CAVE_WALL:
                    cave_world[r][cc] = GRASS

        # Carve a 3×3 room around the spawn so the player has room to move
        for dr in range(-1, 2):
            for dc in range(-1, 2):
                rr, rc = spawn_row + dr, spawn_col + dc
                if 1 <= rr < rows - 1 and 1 <= rc < cols - 1:
                    if cave_world[rr][rc] == CAVE_WALL:
                        cave_world[rr][rc] = GRASS

        # Connect all isolated floor regions to the spawn/exit area
        _ensure_all_regions_connected(cave_world, rows, cols, spawn_col, spawn_row)

        # Place treasure chest deep in the cave (opposite end from the exit)
        chest_col, chest_row = self._find_floor_near_row(
            cave_world, rows, cols, rng, target_row=rows - 5
        )
        cave_world[chest_row][chest_col] = TREASURE_CHEST

        cave_map = GameMap(cave_world, tileset=self.TILESET)
        cave_map.exit_col = exit_col
        cave_map.exit_row = exit_row
        cave_map.spawn_col = spawn_col
        cave_map.spawn_row = spawn_row
        cave_map.chest_col = chest_col
        cave_map.chest_row = chest_row
        cave_map.entrance_col = self.cave_col
        cave_map.entrance_row = self.cave_row
        cave_map.cave_style = "labyrinth" if is_labyrinth else "cavern"
        cave_map.enemies = self.spawn_enemies(cave_map, rng=rng)

        return cave_map

    def spawn_enemies(self, game_map: GameMap, rng: random.Random | None = None) -> list:
        """Spawn cave-type enemies on floor tiles away from the spawn point."""
        from src.entities import Enemy

        if rng is None:
            rng = random.Random(self.cave_col * 10_000 + self.cave_row + 1)

        enemy_pool = (
            _MOUNTAIN_CAVE_ENEMIES
            if self.cave_type == CAVE_MOUNTAIN
            else _HILL_CAVE_ENEMIES
        )

        rows = game_map.rows
        cols = game_map.cols
        spawn_col = getattr(game_map, "spawn_col", cols // 2)
        spawn_row = getattr(game_map, "spawn_row", rows // 2)

        # Candidate positions: floor tiles at least 6 tiles from spawn
        candidates = [
            (c, r)
            for r in range(rows)
            for c in range(cols)
            if game_map.world[r][c] == GRASS
            and math.hypot(c - spawn_col, r - spawn_row) >= 6
        ]

        enemies = []
        spawn_count = {k: 0 for k in enemy_pool}

        for _ in range(20):
            if not candidates:
                break
            col, row = rng.choice(candidates)
            key = rng.choice(enemy_pool)
            max_n = ENEMY_TYPES[key].get("maximum", 5)
            if spawn_count[key] >= max_n:
                continue
            enemies.append(Enemy(col * TILE + TILE // 2, row * TILE + TILE // 2, key))
            spawn_count[key] += 1

        return enemies

    # -- helpers -----------------------------------------------------------

    def _find_floor_near_row(self, cave_world: list[list[int]], rows: int, cols: int, rng: random.Random, target_row: int) -> tuple[int, int]:
        """Return (col, row) of a floor tile at or near target_row."""
        for r in range(max(2, target_row - 2), min(rows - 2, target_row + 6)):
            candidates = [c for c in range(2, cols - 2) if cave_world[r][c] == GRASS]
            if candidates:
                return rng.choice(candidates), r
        # Fallback: any floor tile
        all_floor = [
            (c, r)
            for r in range(2, rows - 2)
            for c in range(2, cols - 2)
            if cave_world[r][c] == GRASS
        ]
        if all_floor:
            c, r = rng.choice(all_floor)
            return c, r
        # Last resort: carve one open
        cave_world[target_row][cols // 2] = GRASS
        return cols // 2, target_row
