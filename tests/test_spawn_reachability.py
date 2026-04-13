"""Tests for spawn-reachability guarantees in overland generation."""

from __future__ import annotations

import random
import pytest

from src.config import (
    WORLD_COLS,
    WORLD_ROWS,
    GRASS,
    DIRT,
    WATER,
    MOUNTAIN,
    PIER,
    BOAT,
    CAVE_MOUNTAIN,
    CAVE_HILL,
)
from src.world.generation import (
    generate_world,
    _find_spawn_tile,
    _bfs_reachable,
    _validate_overland_reachability,
    _pick_ground_tile,
    _carve_path,
    _fixup_reachability,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_world(
    rows: int = WORLD_ROWS, cols: int = WORLD_COLS, fill: int = WATER
) -> list[list[int]]:
    """Create a blank world grid filled with *fill*."""
    return [[fill] * cols for _ in range(rows)]


def _stamp_grass_island(
    world: list[list[int]], top: int, left: int, height: int, width: int
) -> None:
    """Stamp a rectangle of GRASS into *world*."""
    for r in range(top, min(top + height, len(world))):
        for c in range(left, min(left + width, len(world[0]))):
            world[r][c] = GRASS


# ---------------------------------------------------------------------------
# _find_spawn_tile
# ---------------------------------------------------------------------------


class TestFindSpawnTile:
    def test_finds_grass_at_center(self) -> None:
        world = _make_world()
        cr = WORLD_ROWS // 2
        cc = WORLD_COLS // 2
        world[cr][cc] = GRASS
        col, row = _find_spawn_tile(world)
        assert world[row][col] in (GRASS, DIRT)
        assert (col, row) == (cc, cr)

    def test_finds_dirt_when_center_is_water(self) -> None:
        world = _make_world()
        # Place DIRT a few tiles away from center
        cr = WORLD_ROWS // 2
        cc = WORLD_COLS // 2 + 3
        world[cr][cc] = DIRT
        col, row = _find_spawn_tile(world)
        assert world[row][col] == DIRT
        assert (col, row) == (cc, cr)


# ---------------------------------------------------------------------------
# _bfs_reachable
# ---------------------------------------------------------------------------


class TestBfsReachable:
    def test_simple_connected(self) -> None:
        world = _make_world(rows=10, cols=10)
        for c in range(3, 7):
            world[5][c] = GRASS
        reachable = _bfs_reachable(world, 3, 5)
        assert (3, 5) in reachable
        assert (6, 5) in reachable
        assert len(reachable) == 4

    def test_blocked_by_water(self) -> None:
        world = _make_world(rows=10, cols=10)
        world[5][3] = GRASS
        # world[5][4] is WATER (default)
        world[5][5] = GRASS
        reachable = _bfs_reachable(world, 3, 5)
        assert (3, 5) in reachable
        assert (5, 5) not in reachable


# ---------------------------------------------------------------------------
# _validate_overland_reachability
# ---------------------------------------------------------------------------


class TestValidateReachability:
    def test_passes_with_pier_and_caves(self) -> None:
        world = _make_world(rows=20, cols=20)
        _stamp_grass_island(world, 5, 5, 10, 10)
        world[6][6] = PIER
        world[7][7] = CAVE_MOUNTAIN
        world[8][8] = CAVE_HILL
        ok, reachable = _validate_overland_reachability(world, 10, 10)
        assert ok is True

    def test_fails_without_pier(self) -> None:
        world = _make_world(rows=20, cols=20)
        _stamp_grass_island(world, 5, 5, 10, 10)
        world[7][7] = CAVE_MOUNTAIN
        world[8][8] = CAVE_HILL
        ok, _ = _validate_overland_reachability(world, 10, 10)
        assert ok is False

    def test_fails_with_only_one_cave(self) -> None:
        world = _make_world(rows=20, cols=20)
        _stamp_grass_island(world, 5, 5, 10, 10)
        world[6][6] = PIER
        world[7][7] = CAVE_MOUNTAIN
        ok, _ = _validate_overland_reachability(world, 10, 10)
        assert ok is False


# ---------------------------------------------------------------------------
# _pick_ground_tile
# ---------------------------------------------------------------------------


class TestPickGroundTile:
    def test_mostly_grass_neighbors(self) -> None:
        """7 GRASS neighbors + 1 DIRT neighbor → GRASS picked majority of the time."""
        world = _make_world(rows=5, cols=5, fill=GRASS)
        world[0][0] = DIRT  # one DIRT neighbor of (1,1)
        results = [_pick_ground_tile(world, 1, 1) for _ in range(200)]
        grass_pct = results.count(GRASS) / len(results)
        assert grass_pct > 0.60

    def test_mostly_dirt_neighbors(self) -> None:
        world = _make_world(rows=5, cols=5, fill=DIRT)
        world[0][0] = GRASS
        results = [_pick_ground_tile(world, 1, 1) for _ in range(200)]
        dirt_pct = results.count(DIRT) / len(results)
        assert dirt_pct > 0.60

    def test_no_ground_neighbors_defaults_grass(self) -> None:
        world = _make_world(rows=5, cols=5, fill=WATER)
        assert _pick_ground_tile(world, 2, 2) == GRASS


# ---------------------------------------------------------------------------
# _carve_path
# ---------------------------------------------------------------------------


class TestCarvePath:
    def test_carves_through_mountain(self) -> None:
        world = _make_world(rows=10, cols=10)
        # GRASS at (2,5), MOUNTAIN wall at cols 3-6, PIER at (7,5)
        world[5][2] = GRASS
        for c in range(3, 7):
            world[5][c] = MOUNTAIN
        world[5][7] = PIER
        reachable: set[tuple[int, int]] = {(2, 5)}
        _carve_path(world, reachable, 7, 5)
        # Mountains along the path should now be GRASS or DIRT
        for c in range(3, 7):
            assert world[5][c] in (GRASS, DIRT), f"col {c} not carved"

    def test_never_replaces_water(self) -> None:
        world = _make_world(rows=10, cols=10)
        world[5][2] = GRASS
        world[5][3] = WATER  # should stay WATER
        world[5][4] = MOUNTAIN
        world[5][5] = PIER
        reachable: set[tuple[int, int]] = {(2, 5)}
        _carve_path(world, reachable, 5, 5)
        assert world[5][3] == WATER


# ---------------------------------------------------------------------------
# _fixup_reachability
# ---------------------------------------------------------------------------


class TestFixupReachability:
    def test_carves_to_pier(self) -> None:
        world = _make_world(rows=20, cols=20)
        _stamp_grass_island(world, 5, 5, 10, 10)
        # Wall off the pier with mountains
        for r in range(5, 15):
            world[r][12] = MOUNTAIN
        world[10][15] = PIER
        world[10][16] = BOAT
        world[6][6] = CAVE_MOUNTAIN
        world[7][7] = CAVE_HILL
        reachable = _bfs_reachable(world, 8, 8)
        assert (15, 10) not in reachable
        _fixup_reachability(world, 8, 8, reachable)
        # Re-check: pier should now be reachable
        reachable2 = _bfs_reachable(world, 8, 8)
        assert (15, 10) in reachable2

    def test_force_places_caves(self) -> None:
        world = _make_world(rows=20, cols=20)
        _stamp_grass_island(world, 5, 5, 10, 10)
        world[6][6] = PIER
        # No caves at all
        reachable = _bfs_reachable(world, 8, 8)
        _fixup_reachability(world, 8, 8, reachable)
        # Count caves on the island
        cave_count = sum(
            1
            for r in range(20)
            for c in range(20)
            if world[r][c] in (CAVE_MOUNTAIN, CAVE_HILL)
        )
        assert cave_count >= 2


# ---------------------------------------------------------------------------
# Full integration: generate_world always produces reachable maps
# ---------------------------------------------------------------------------


class TestGenerateWorldReachability:
    @pytest.mark.parametrize("seed", range(20))
    def test_reachability(self, seed: int) -> None:
        random.seed(seed)
        world = generate_world()
        spawn_col, spawn_row = _find_spawn_tile(world)
        ok, _ = _validate_overland_reachability(world, spawn_col, spawn_row)
        assert (
            ok
        ), f"seed={seed}: spawn ({spawn_col},{spawn_row}) cannot reach pier + 2 caves"
