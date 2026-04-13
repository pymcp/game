"""Cave environment — generates caverns with walls, ore, and cave-specific enemies."""

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
)
from src.world.environments.base import BaseEnvironment
from src.world.map import GameMap

# Enemy pools keyed by cave entrance type
_MOUNTAIN_CAVE_ENEMIES = ["bat", "cave_troll"]
_HILL_CAVE_ENEMIES = ["goblin", "cave_spider"]

CAVE_ROWS = 50
CAVE_COLS = 50


# ---------------------------------------------------------------------------
# Layout generators  (return a 2-D grid: 1 = wall, 0 = floor)
# ---------------------------------------------------------------------------


def _cellular_automata(rng, rows, cols):
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


def _drunkard_walk(rng, rows, cols):
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

    def __init__(self, cave_col, cave_row, cave_type=CAVE_MOUNTAIN):
        self.cave_col = cave_col
        self.cave_row = cave_row
        self.cave_type = cave_type

    # -- public api --------------------------------------------------------

    def generate(self):
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

        # Spawn point a few tiles below the exit (carve it open if needed)
        spawn_col, spawn_row = exit_col, exit_row + 4
        spawn_row = min(spawn_row, rows - 3)
        if cave_world[spawn_row][spawn_col] == CAVE_WALL:
            cave_world[spawn_row][spawn_col] = GRASS

        cave_map = GameMap(cave_world, tileset=self.TILESET)
        cave_map.exit_col = exit_col
        cave_map.exit_row = exit_row
        cave_map.spawn_col = spawn_col
        cave_map.spawn_row = spawn_row
        cave_map.entrance_col = self.cave_col
        cave_map.entrance_row = self.cave_row
        cave_map.cave_style = "labyrinth" if is_labyrinth else "cavern"
        cave_map.enemies = self.spawn_enemies(cave_map, rng=rng)

        return cave_map

    def spawn_enemies(self, game_map, rng=None):
        """Spawn cave-type enemies on floor tiles away from the spawn point."""
        from src.entities import Enemy
        from src.data import ENEMY_TYPES

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

    def _find_floor_near_row(self, cave_world, rows, cols, rng, target_row):
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
