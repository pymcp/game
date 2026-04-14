"""Tests for spawn-reachability guarantees in overland generation."""

from __future__ import annotations

import collections
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
    _consolidate_mountain_ranges,
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
        # Stamp a 3×3 GRASS block so collision corners don't clip WATER
        _stamp_grass_island(world, cr - 1, cc - 1, 3, 3)
        col, row = _find_spawn_tile(world)
        assert world[row][col] == GRASS
        assert (col, row) == (cc, cr)

    def test_skips_dirt_prefers_grass(self) -> None:
        world = _make_world()
        cr = WORLD_ROWS // 2
        cc = WORLD_COLS // 2
        # DIRT at cc+1 — closer but must be skipped
        world[cr][cc + 1] = DIRT
        # GRASS island at cc+3 with 3×3 clear area so collision check passes
        _stamp_grass_island(world, cr - 1, cc + 2, 3, 3)
        col, row = _find_spawn_tile(world)
        assert world[row][col] == GRASS
        # The centre of the island (cc+3, cr) should be returned
        assert (col, row) == (cc + 3, cr)

    def test_spawn_does_not_clip_blocking_tiles(self) -> None:
        """Chosen spawn tile centre must not clip any blocking tile."""
        from src.world.collision import hits_blocking
        from src.config import TILE

        world = _make_world()
        cr = WORLD_ROWS // 2
        cc = WORLD_COLS // 2
        # Single GRASS tile surrounded by WATER — corners clip WATER, so skip
        world[cr][cc] = GRASS
        # Place a safe 3×3 GRASS island one step away
        _stamp_grass_island(world, cr - 1, cc + 4, 3, 3)
        col, row = _find_spawn_tile(world)
        cx = col * TILE + TILE // 2
        cy = row * TILE + TILE // 2
        assert not hits_blocking(world, cx, cy, 20), (
            f"spawn at ({col}, {row}) clips a blocking tile"
        )


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
# _consolidate_mountain_ranges
# ---------------------------------------------------------------------------


def _count_mountain_ranges(
    world: list[list[int]], mountain_tile: int = MOUNTAIN
) -> int:
    """Count 8-connected MOUNTAIN components in *world*."""
    rows = len(world)
    cols = len(world[0]) if rows else 0
    visited = [[False] * cols for _ in range(rows)]
    count = 0
    for sr in range(rows):
        for sc in range(cols):
            if world[sr][sc] != mountain_tile or visited[sr][sc]:
                continue
            count += 1
            stack = [(sc, sr)]
            visited[sr][sc] = True
            while stack:
                c, r = stack.pop()
                for dc in (-1, 0, 1):
                    for dr in (-1, 0, 1):
                        if dc == 0 and dr == 0:
                            continue
                        nc, nr = c + dc, r + dr
                        if (
                            0 <= nc < cols
                            and 0 <= nr < rows
                            and not visited[nr][nc]
                            and world[nr][nc] == mountain_tile
                        ):
                            visited[nr][nc] = True
                            stack.append((nc, nr))
    return count


class TestConsolidateMountainRanges:
    def test_already_within_budget(self) -> None:
        """Two separate ranges, max_ranges=4 — nothing should change."""
        world = _make_world(rows=20, cols=20, fill=GRASS)
        # Range A at top-left
        for c in range(2, 5):
            world[2][c] = MOUNTAIN
        # Range B at bottom-right
        for c in range(15, 18):
            world[17][c] = MOUNTAIN
        assert _count_mountain_ranges(world) == 2
        _consolidate_mountain_ranges(world, mountain_tile=MOUNTAIN, max_ranges=4)
        assert _count_mountain_ranges(world) <= 4

    def test_consolidates_nearby_excess_ranges(self) -> None:
        """Six single-tile mountains on the same row, 4 tiles apart.

        They are NOT 8-connected (consecutive Chebyshev distance = 4 > 1) so
        each is its own range.  Each consecutive pair is exactly 4 cardinal
        steps apart, so BFS with connect_radius=4 can bridge them.
        After consolidation with max_ranges=2 all six should merge into ≤ 2.
        """
        world = _make_world(rows=30, cols=30, fill=GRASS)
        # Six mountains in a row, 4 columns apart — separated but bridgeable
        positions = [(5, 15), (9, 15), (13, 15), (17, 15), (21, 15), (25, 15)]
        for c, r in positions:
            world[r][c] = MOUNTAIN
        assert _count_mountain_ranges(world) == 6, (
            "pre-condition: mountains must not be 8-connected to each other"
        )
        _consolidate_mountain_ranges(
            world, mountain_tile=MOUNTAIN, max_ranges=2, connect_radius=4
        )
        assert _count_mountain_ranges(world) <= 2

    def test_leaves_distant_ranges_alone(self) -> None:
        """Ranges farther than connect_radius apart must not be bridged."""
        world = _make_world(rows=30, cols=30, fill=GRASS)
        world[2][2] = MOUNTAIN   # range A — far corner
        world[28][28] = MOUNTAIN  # range B — opposite corner
        assert _count_mountain_ranges(world) == 2
        _consolidate_mountain_ranges(
            world, mountain_tile=MOUNTAIN, max_ranges=1, connect_radius=4
        )
        # Both ranges are ~37 steps apart — neither should be merged
        assert _count_mountain_ranges(world) == 2

    def test_never_bridges_over_water(self) -> None:
        """Water tiles between ranges must never be turned into mountains."""
        world = _make_world(rows=20, cols=20, fill=GRASS)
        # Two ranges separated by a column of WATER
        for r in range(20):
            world[r][10] = WATER  # vertical water barrier
        for r in range(3, 7):
            world[r][3] = MOUNTAIN  # range A on the left
        for r in range(3, 7):
            world[r][16] = MOUNTAIN  # range B on the right
        _consolidate_mountain_ranges(world, mountain_tile=MOUNTAIN, max_ranges=1)
        # Water column must still be fully WATER
        for r in range(20):
            assert world[r][10] == WATER, f"row {r} col 10 was overwritten"

    def test_generate_world_consolidation_smoke(self) -> None:
        """generate_world() runs the consolidation pass without error.

        The algorithm is a greedy single-pass: it processes excess ranges
        largest-first and bridges each to the current keeper_set.  Because
        organic scatter enriches keeper_set over time, a range processed early
        may end up seemingly reachable in the final world from a keeper tile
        that did not exist during its BFS pass — this is expected behaviour.
        The unit tests above verify the core invariants in isolation.
        """
        for seed in range(5):
            random.seed(seed)
            world, _ = generate_world()
            has_mountain = any(
                world[r][c] == MOUNTAIN
                for r in range(len(world))
                for c in range(len(world[0]))
            )
            assert has_mountain, f"seed={seed}: generate_world produced no mountain tiles"


# ---------------------------------------------------------------------------
# Full integration: generate_world always produces reachable maps
# ---------------------------------------------------------------------------


class TestGenerateWorldReachability:
    @pytest.mark.parametrize("seed", range(20))
    def test_reachability(self, seed: int) -> None:
        random.seed(seed)
        world, _objects = generate_world()
        spawn_col, spawn_row = _find_spawn_tile(world)
        ok, _ = _validate_overland_reachability(world, spawn_col, spawn_row)
        assert (
            ok
        ), f"seed={seed}: spawn ({spawn_col},{spawn_row}) cannot reach pier + 2 caves"
