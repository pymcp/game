"""Shared procedural-generation utilities for enclosed environments.

All enclosed maps (cave, underwater, portal realm) share the same three
generation building-blocks that are extracted here to eliminate duplication:

  - cellular_automata   — produce a binary (wall/floor) layout grid
  - connect_regions     — guarantee full walkability via L-corridors
  - find_floor_near_row — locate a passable tile close to a target row
"""

from __future__ import annotations

import collections
import random


def cellular_automata(
    rng: random.Random,
    rows: int,
    cols: int,
    *,
    density: float = 0.45,
    iterations: int = 5,
    border: int = 2,
    threshold: int = 5,
) -> list[list[int]]:
    """Generate a binary layout grid via cellular automata.

    Returns a 2-D list: ``1`` = wall, ``0`` = floor.

    Args:
        rng: Seeded random instance (ensures deterministic maps).
        rows: Total row count of the grid.
        cols: Total column count of the grid.
        density: Initial probability that any cell starts as a wall.
        iterations: Number of smoothing passes to run.
        border: Tile-width of the solid wall forced around every edge.
        threshold: Neighbour count at-or-above which a cell becomes (stays) a wall.
    """
    grid = [
        [1 if rng.random() < density else 0 for _ in range(cols)] for _ in range(rows)
    ]

    # Force solid border so the HUD never overlaps walkable tiles.
    for r in range(rows):
        for c in range(cols):
            if r < border or r >= rows - border or c < border or c >= cols - border:
                grid[r][c] = 1

    for _ in range(iterations):
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
                new_grid[r][c] = 1 if wall_neighbours >= threshold else 0
        grid = new_grid

    return grid


def connect_regions(
    world: list[list[int]],
    rows: int,
    cols: int,
    spawn_col: int,
    spawn_row: int,
    passable: set[int],
    floor_tile: int,
    border: int = 2,
) -> None:
    """Connect every isolated floor region to the spawn point via L-corridors.

    Finds all disconnected pockets of passable tiles and carves the shortest
    L-shaped corridor from each pocket to the main (spawn-reachable) region,
    guaranteeing the player can always walk from spawn to every open area.

    Args:
        world: 2-D tile grid (mutated in place).
        rows: Row count of *world*.
        cols: Column count of *world*.
        spawn_col: Column of the guaranteed-passable anchor tile.
        spawn_row: Row of the guaranteed-passable anchor tile.
        passable: Set of tile IDs treated as walkable floor.
        floor_tile: Tile ID to write when carving new corridors.
        border: Tile-width of the solid edge; corridors are kept within it.
    """

    def _bfs(
        start_c: int, start_r: int, candidates: set[tuple[int, int]]
    ) -> set[tuple[int, int]]:
        region: set[tuple[int, int]] = set()
        q: collections.deque[tuple[int, int]] = collections.deque([(start_c, start_r)])
        region.add((start_c, start_r))
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

    main = _bfs(spawn_col, spawn_row, all_floor)
    remaining = all_floor - main

    while remaining:
        seed = next(iter(remaining))
        iso = _bfs(seed[0], seed[1], remaining)

        # Find the closest tile pair (Manhattan) between main and the isolated region.
        best_dist = float("inf")
        best_main = best_iso = None
        for mc, mr in main:
            for ic, ir in iso:
                d = abs(mc - ic) + abs(mr - ir)
                if d < best_dist:
                    best_dist = d
                    best_main = (mc, mr)
                    best_iso = (ic, ir)

        # Carve an L-shaped corridor: horizontal first, then vertical.
        c, r = best_iso  # type: ignore[assignment]
        tc, tr = best_main  # type: ignore[assignment]
        while c != tc:
            c += 1 if tc > c else -1
            if border <= c < cols - border and border <= r < rows - border:
                world[r][c] = floor_tile
                all_floor.add((c, r))
                main.add((c, r))
        while r != tr:
            r += 1 if tr > r else -1
            if border <= c < cols - border and border <= r < rows - border:
                world[r][c] = floor_tile
                all_floor.add((c, r))
                main.add((c, r))

        main |= iso
        remaining -= iso


def find_floor_near_row(
    world: list[list[int]],
    rows: int,
    cols: int,
    rng: random.Random,
    target_row: int,
    floor_tile: int,
    border: int = 2,
) -> tuple[int, int]:
    """Return ``(col, row)`` of a floor tile at or near *target_row*.

    Searches a ±2-row window around *target_row*, then falls back to any
    floor tile in the safe area, then (as a last resort) carves one open.

    Args:
        world: 2-D tile grid (may be mutated if no floor tile exists at all).
        rows: Row count of *world*.
        cols: Column count of *world*.
        rng: Seeded random instance for reproducible selection.
        target_row: Preferred row to search near.
        floor_tile: Tile ID to search for (and carve if none exists).
        border: Safe region boundary; search and carve stay within it.
    """
    search_min = max(border, target_row - 2)
    search_max = min(rows - border, target_row + 6)
    for r in range(search_min, search_max):
        candidates = [
            c for c in range(border, cols - border) if world[r][c] == floor_tile
        ]
        if candidates:
            return rng.choice(candidates), r

    all_floor = [
        (c, r)
        for r in range(border, rows - border)
        for c in range(border, cols - border)
        if world[r][c] == floor_tile
    ]
    if all_floor:
        return rng.choice(all_floor)

    # Last resort: carve one open tile.
    world[target_row][cols // 2] = floor_tile
    return cols // 2, target_row
