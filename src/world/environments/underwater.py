"""Underwater environment — generates a seafloor map accessible by diving from a boat."""

import random

from src.config import TILE, MAP_BORDER
from src.world.environments.base import BaseEnvironment
from src.world.environments.utils import (
    cellular_automata,
    connect_regions,
    find_floor_near_row,
)
from src.world.map import GameMap
from src.config import SAND, CORAL, REEF, DIVE_EXIT

# Sized so MAP_BORDER leaves a 20×26 walkable interior.
UNDERWATER_ROWS = 30
UNDERWATER_COLS = 36


# ---------------------------------------------------------------------------
# UnderwaterEnvironment
# ---------------------------------------------------------------------------


class UnderwaterEnvironment(BaseEnvironment):
    """Generates a unique underwater map seeded by the dive tile position.

    The map is a sandy seafloor dotted with coral formations and bounded by
    reef walls.  A DIVE_EXIT tile near the top lets the player surface.
    """

    TILESET = "underwater"

    def __init__(self, dive_col: int, dive_row: int) -> None:
        self.dive_col = dive_col
        self.dive_row = dive_row

    # -- public api --------------------------------------------------------

    def generate(self) -> GameMap:
        """Generate and return a fully configured underwater GameMap."""
        rng = random.Random(self.dive_col * 10_000 + self.dive_row)
        rows, cols = UNDERWATER_ROWS, UNDERWATER_COLS

        grid = cellular_automata(
            rng, rows, cols, density=0.40, iterations=4, border=MAP_BORDER
        )

        # Build tile world from layout grid
        world = [
            [REEF if grid[r][c] == 1 else SAND for c in range(cols)]
            for r in range(rows)
        ]

        # Collect sand tiles for scattering
        sand_tiles = [
            (c, r) for r in range(rows) for c in range(cols) if world[r][c] == SAND
        ]

        # Scatter coral clusters
        def scatter_coral(count: int, cluster_min: int, cluster_max: int) -> None:
            for _ in range(count):
                if not sand_tiles:
                    break
                cx, cy = rng.choice(sand_tiles)
                for _ in range(rng.randint(cluster_min, cluster_max)):
                    nx = cx + rng.randint(-2, 2)
                    ny = cy + rng.randint(-2, 2)
                    if 0 <= nx < cols and 0 <= ny < rows and world[ny][nx] == SAND:
                        world[ny][nx] = CORAL

        scatter_coral(count=8, cluster_min=3, cluster_max=8)

        # Place DIVE_EXIT near the top
        exit_col, exit_row = find_floor_near_row(
            world, rows, cols, rng, 3, SAND, border=MAP_BORDER
        )
        world[exit_row][exit_col] = DIVE_EXIT

        # Spawn point a few rows below the exit
        spawn_row = min(exit_row + 4, rows - 4)
        spawn_col = exit_col

        # Carve a clear corridor from exit down to spawn
        for r in range(exit_row, spawn_row + 1):
            for dc in range(-1, 2):
                cc = spawn_col + dc
                if 1 <= cc < cols - 1 and world[r][cc] == REEF:
                    world[r][cc] = SAND

        # Carve a 3×3 room around spawn
        for dr in range(-1, 2):
            for dc in range(-1, 2):
                rr, rc = spawn_row + dr, spawn_col + dc
                if 1 <= rr < rows - 1 and 1 <= rc < cols - 1:
                    if world[rr][rc] == REEF:
                        world[rr][rc] = SAND

        # Connect all isolated regions
        connect_regions(
            world,
            rows,
            cols,
            spawn_col,
            spawn_row,
            {SAND, DIVE_EXIT, CORAL},
            SAND,
            MAP_BORDER,
        )

        underwater_map = GameMap(world, tileset=self.TILESET)
        underwater_map.dive_col = self.dive_col
        underwater_map.dive_row = self.dive_row
        underwater_map.exit_col = exit_col
        underwater_map.exit_row = exit_row
        underwater_map.spawn_col = spawn_col
        underwater_map.spawn_row = spawn_row

        return underwater_map

    def spawn_creatures(
        self, game_map: GameMap, rng: random.Random | None = None
    ) -> list:
        """Return a list of Creature instances placed on SAND tiles."""
        from src.entities.creature import Creature

        if rng is None:
            rng = random.Random(self.dive_col * 10_000 + self.dive_row + 1)

        rows = game_map.rows
        cols = game_map.cols
        spawn_col = getattr(game_map, "spawn_col", cols // 2)
        spawn_row = getattr(game_map, "spawn_row", rows // 2)

        map_key = ("underwater", self.dive_col, self.dive_row)

        candidates = [
            (c, r)
            for r in range(rows)
            for c in range(cols)
            if game_map.world[r][c] == SAND
            and abs(c - spawn_col) + abs(r - spawn_row) >= 4
        ]

        creatures = []
        weights = [("fish", 0.5), ("dolphin", 0.3), ("jellyfish", 0.2)]
        kinds, probs = zip(*weights)

        for _ in range(rng.randint(5, 10)):
            if not candidates:
                break
            col, row = rng.choice(candidates)
            kind = rng.choices(kinds, weights=probs, k=1)[0]
            creatures.append(
                Creature(
                    col * TILE + TILE // 2,
                    row * TILE + TILE // 2,
                    kind,
                    map_key,
                )
            )

        return creatures
