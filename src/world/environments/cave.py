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
    TREASURE_CHEST,
    MAP_BORDER,
    BiomeType,
)
from src.data import ENEMY_TYPES, EnemyEnvironment, OBJECT_TILE_IDS
from src.world.environments.base import BaseEnvironment
from src.world.environments.utils import (
    cellular_automata,
    connect_regions,
    find_floor_near_row,
)
from src.world.map import GameMap

# Enemy pools derived from ENEMY_TYPES definitions
_MOUNTAIN_CAVE_ENEMIES = [
    k
    for k, v in ENEMY_TYPES.items()
    if EnemyEnvironment.CAVE_MOUNTAIN in v.environments
]
_HILL_CAVE_ENEMIES = [
    k
    for k, v in ENEMY_TYPES.items()
    if EnemyEnvironment.CAVE_HILL in v.environments
]

# Size chosen so the 5-tile MAP_BORDER leaves a 26×26 walkable interior.
CAVE_ROWS = 36
CAVE_COLS = 36


# ---------------------------------------------------------------------------
# Connectivity helpers
# ---------------------------------------------------------------------------


def _passable_neighbour_count(
    world: list[list[int]],
    rows: int,
    cols: int,
    col: int,
    row: int,
    passable: set[int],
) -> int:
    """Return how many cardinal neighbours of (col, row) are passable."""
    count = 0
    for dc, dr in ((0, 1), (0, -1), (1, 0), (-1, 0)):
        nc, nr = col + dc, row + dr
        if 0 <= nr < rows and 0 <= nc < cols and world[nr][nc] in passable:
            count += 1
    return count


def _seal_unreachable(
    world: list[list[int]],
    rows: int,
    cols: int,
    spawn_col: int,
    spawn_row: int,
    passable: set[int],
) -> None:
    """Flood-fill from spawn; convert any unreachable passable tiles to CAVE_WALL."""
    import collections as _collections

    reachable: set[tuple[int, int]] = set()
    q: _collections.deque[tuple[int, int]] = _collections.deque()
    q.append((spawn_col, spawn_row))
    reachable.add((spawn_col, spawn_row))
    while q:
        c, r = q.popleft()
        for dc, dr in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            nc, nr = c + dc, r + dr
            if (
                0 <= nr < rows
                and 0 <= nc < cols
                and (nc, nr) not in reachable
                and world[nr][nc] in passable
            ):
                reachable.add((nc, nr))
                q.append((nc, nr))

    for r in range(rows):
        for c in range(cols):
            if world[r][c] in passable and (c, r) not in reachable:
                world[r][c] = CAVE_WALL


# ---------------------------------------------------------------------------
# Layout generators  (return a 2-D grid: 1 = wall, 0 = floor)
# ---------------------------------------------------------------------------


def _drunkard_walk(rng: random.Random, rows: int, cols: int) -> list[list[int]]:
    """Labyrinth layout via a drunkard's walk with 2 walkers."""
    grid = [[1] * cols for _ in range(rows)]

    steps = int(rows * cols * 0.30)  # carve ~30 % of cells per walker
    for _ in range(2):
        r = rng.randint(rows // 4, 3 * rows // 4)
        c = rng.randint(cols // 4, 3 * cols // 4)
        for _ in range(steps):
            if (
                MAP_BORDER <= r < rows - MAP_BORDER
                and MAP_BORDER <= c < cols - MAP_BORDER
            ):
                grid[r][c] = 0
                # Occasionally widen the corridor
                if rng.random() < 0.3:
                    nr = max(
                        MAP_BORDER, min(rows - MAP_BORDER - 1, r + rng.randint(-1, 1))
                    )
                    nc = max(
                        MAP_BORDER, min(cols - MAP_BORDER - 1, c + rng.randint(-1, 1))
                    )
                    grid[nr][nc] = 0
            dr, dc = rng.choice([(0, 1), (0, -1), (1, 0), (-1, 0)])
            r = max(MAP_BORDER, min(rows - MAP_BORDER - 1, r + dr))
            c = max(MAP_BORDER, min(cols - MAP_BORDER - 1, c + dc))

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

    def __init__(
        self,
        cave_col: int,
        cave_row: int,
        cave_type: int = CAVE_MOUNTAIN,
        biome: BiomeType = BiomeType.STANDARD,
    ) -> None:
        self.cave_col = cave_col
        self.cave_row = cave_row
        self.cave_type = cave_type
        self.biome = biome

    # -- public api --------------------------------------------------------

    def generate(self) -> GameMap:
        """Generate and return a fully configured cave GameMap."""
        # Choose tileset based on the surface biome
        if self.biome == BiomeType.STANDARD:
            tileset = "cave"
        else:
            tileset = f"cave_{self.biome.value}"

        rng = random.Random(self.cave_col * 10_000 + self.cave_row)

        rows, cols = CAVE_ROWS, CAVE_COLS
        is_labyrinth = rng.random() < 0.30

        grid = (
            _drunkard_walk(rng, rows, cols)
            if is_labyrinth
            else cellular_automata(
                rng, rows, cols, density=0.45, iterations=5, border=MAP_BORDER
            )
        )

        # Build tile world from layout grid
        cave_world = [
            [CAVE_WALL if grid[r][c] == 1 else GRASS for c in range(cols)]
            for r in range(rows)
        ]

        # Separate objects layer for ores and other mineable deposits
        cave_objects: list[list[int | None]] = [[None] * cols for _ in range(rows)]

        # Scatter minerals only on floor tiles; mountain caves get more rare ore
        floor_tiles = [
            (c, r)
            for r in range(rows)
            for c in range(cols)
            if cave_world[r][c] == GRASS
        ]

        def scatter_ore(tile_id: int, count: int, cmin: int, cmax: int) -> None:
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
                        cave_objects[ny][nx] = tile_id

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
        exit_col, exit_row = find_floor_near_row(
            cave_world, rows, cols, rng, MAP_BORDER, GRASS, border=MAP_BORDER
        )
        cave_world[exit_row][exit_col] = CAVE_EXIT

        # Spawn point a few tiles below the exit
        spawn_row = min(exit_row + 5, rows - MAP_BORDER - 1)
        spawn_col = exit_col

        # Carve a guaranteed open corridor from exit down to spawn so the
        # player can always reach the exit, even in dense cellular-automata caves
        for r in range(exit_row, spawn_row + 1):
            for dc in range(-1, 2):  # 3-tile wide corridor
                cc = spawn_col + dc
                if (
                    MAP_BORDER <= cc < cols - MAP_BORDER
                    and cave_world[r][cc] == CAVE_WALL
                ):
                    cave_world[r][cc] = GRASS

        # Carve a 3×3 room around the spawn so the player has room to move
        for dr in range(-1, 2):
            for dc in range(-1, 2):
                rr, rc = spawn_row + dr, spawn_col + dc
                if (
                    MAP_BORDER <= rr < rows - MAP_BORDER
                    and MAP_BORDER <= rc < cols - MAP_BORDER
                ):
                    if cave_world[rr][rc] == CAVE_WALL:
                        cave_world[rr][rc] = GRASS

        # All tiles the player can walk on (ores are now in the objects layer)
        _PASSABLE = {GRASS, CAVE_EXIT}

        # Connect all isolated floor regions to the spawn/exit area.
        connect_regions(
            cave_world,
            rows,
            cols,
            spawn_col,
            spawn_row,
            _PASSABLE,
            GRASS,
            MAP_BORDER,
        )

        # Place treasure chest deep in the cave (opposite end from the exit).
        # TREASURE_CHEST is blocking, so only place it where at least 2
        # cardinal neighbours are passable — avoids sealing a chokepoint.
        chest_col, chest_row = find_floor_near_row(
            cave_world, rows, cols, rng, rows - MAP_BORDER - 1, GRASS, border=MAP_BORDER
        )
        if (
            _passable_neighbour_count(
                cave_world, rows, cols, chest_col, chest_row, _PASSABLE
            )
            >= 2
        ):
            cave_world[chest_row][chest_col] = TREASURE_CHEST
        else:
            # Fallback: scan nearby floor tiles for a safe spot
            placed = False
            for dr in range(-3, 4):
                for dc in range(-3, 4):
                    nr, nc = chest_row + dr, chest_col + dc
                    if (
                        MAP_BORDER <= nr < rows - MAP_BORDER
                        and MAP_BORDER <= nc < cols - MAP_BORDER
                        and cave_world[nr][nc] == GRASS
                        and _passable_neighbour_count(
                            cave_world, rows, cols, nc, nr, _PASSABLE
                        )
                        >= 2
                    ):
                        cave_world[nr][nc] = TREASURE_CHEST
                        chest_row, chest_col = nr, nc
                        placed = True
                        break
                if placed:
                    break
            if not placed:
                # Last resort — place it anyway (better than no chest)
                cave_world[chest_row][chest_col] = TREASURE_CHEST

        # Final validation: flood-fill from spawn and convert any
        # unreachable walkable tiles to walls so no area is visible
        # but inaccessible.
        _seal_unreachable(cave_world, rows, cols, spawn_col, spawn_row, _PASSABLE)

        cave_map = GameMap(cave_world, tileset=tileset)
        cave_map.exit_col = exit_col
        cave_map.exit_row = exit_row
        cave_map.spawn_col = spawn_col
        cave_map.spawn_row = spawn_row
        cave_map.chest_col = chest_col
        cave_map.chest_row = chest_row
        cave_map.entrance_col = self.cave_col
        cave_map.entrance_row = self.cave_row
        cave_map.cave_style = "labyrinth" if is_labyrinth else "cavern"

        # Populate objects layer so ores are on the correct layer
        for r in range(rows):
            for c in range(cols):
                if cave_objects[r][c] is not None:
                    cave_map.set_object(r, c, cave_objects[r][c])

        cave_map.enemies = self.spawn_enemies(cave_map, rng=rng)

        return cave_map

    def spawn_enemies(
        self, game_map: GameMap, rng: random.Random | None = None
    ) -> list:
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
            max_n = ENEMY_TYPES[key].maximum
            if spawn_count[key] >= max_n:
                continue
            enemies.append(Enemy(col * TILE + TILE // 2, row * TILE + TILE // 2, key))
            spawn_count[key] += 1

        return enemies
