"""Underwater environment — generates a seafloor map accessible by diving from a boat."""

import collections
import random

from src.config import TILE
from src.world.environments.base import BaseEnvironment
from src.world.map import GameMap
from src.config import SAND, CORAL, REEF, DIVE_EXIT

UNDERWATER_ROWS = 40
UNDERWATER_COLS = 50


# ---------------------------------------------------------------------------
# Layout generator
# ---------------------------------------------------------------------------


def _cellular_automata(rng: random.Random, rows: int, cols: int) -> list[list[int]]:
    """Generate an open seafloor via cellular automata.

    Returns a binary grid: 1 = wall (REEF), 0 = floor (SAND).
    """
    # Lower initial density than caves so the seafloor is more open
    grid = [[1 if rng.random() < 0.40 else 0 for _ in range(cols)] for _ in range(rows)]

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


def _ensure_all_regions_connected(
    world: list[list[int]],
    rows: int,
    cols: int,
    spawn_col: int,
    spawn_row: int,
) -> None:
    """Connect every isolated SAND/DIVE_EXIT region to the spawn point via L-corridors."""
    passable = {SAND, DIVE_EXIT, CORAL}

    def bfs(start_c: int, start_r: int, candidate_set: set) -> set:
        region: set = set()
        queue: collections.deque = collections.deque([(start_c, start_r)])
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
        (c, r) for r in range(rows) for c in range(cols) if world[r][c] in passable
    }

    if (spawn_col, spawn_row) not in all_floor:
        return

    main = bfs(spawn_col, spawn_row, all_floor)
    remaining = all_floor - main

    while remaining:
        seed = next(iter(remaining))
        iso = bfs(seed[0], seed[1], remaining)

        best_dist = float("inf")
        best_main = best_iso = None
        for mc, mr in main:
            for ic, ir in iso:
                d = abs(mc - ic) + abs(mr - ir)
                if d < best_dist:
                    best_dist = d
                    best_main = (mc, mr)
                    best_iso = (ic, ir)

        c, r = best_iso
        tc, tr = best_main
        while c != tc:
            c += 1 if tc > c else -1
            if 1 <= c < cols - 1 and 1 <= r < rows - 1:
                world[r][c] = SAND
                all_floor.add((c, r))
                main.add((c, r))
        while r != tr:
            r += 1 if tr > r else -1
            if 1 <= c < cols - 1 and 1 <= r < rows - 1:
                world[r][c] = SAND
                all_floor.add((c, r))
                main.add((c, r))

        main |= iso
        remaining -= iso


def _find_floor_near_row(
    world: list[list[int]],
    rows: int,
    cols: int,
    rng: random.Random,
    target_row: int,
) -> tuple[int, int]:
    """Return (col, row) of a SAND tile at or near target_row."""
    for r in range(max(2, target_row - 2), min(rows - 2, target_row + 6)):
        candidates = [c for c in range(2, cols - 2) if world[r][c] == SAND]
        if candidates:
            return rng.choice(candidates), r
    all_floor = [
        (c, r)
        for r in range(2, rows - 2)
        for c in range(2, cols - 2)
        if world[r][c] == SAND
    ]
    if all_floor:
        return rng.choice(all_floor)
    # Last resort: carve one open
    world[target_row][cols // 2] = SAND
    return cols // 2, target_row


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

        grid = _cellular_automata(rng, rows, cols)

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
        exit_col, exit_row = _find_floor_near_row(world, rows, cols, rng, target_row=3)
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
        _ensure_all_regions_connected(world, rows, cols, spawn_col, spawn_row)

        underwater_map = GameMap(world, tileset=self.TILESET)
        underwater_map.dive_col = self.dive_col
        underwater_map.dive_row = self.dive_row
        underwater_map.exit_col = exit_col
        underwater_map.exit_row = exit_row
        underwater_map.spawn_col = spawn_col
        underwater_map.spawn_row = spawn_row

        return underwater_map

    def spawn_sea_creatures(
        self, game_map: GameMap, rng: random.Random | None = None
    ) -> list:
        """Return a list of SeaCreature instances placed on SAND tiles."""
        from src.entities.sea_creature import SeaCreature

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
                SeaCreature(
                    col * TILE + TILE // 2,
                    row * TILE + TILE // 2,
                    kind=kind,
                    home_map=map_key,
                )
            )

        return creatures
