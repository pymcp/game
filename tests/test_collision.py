"""Unit tests for src/world/collision.py.

Covers:
- tile_at
- pos_in_bounds_world / pos_in_bounds
- hits_blocking (including extra_passable)
- out_of_bounds
- check_object_collision
- try_spend
- compute_town_clusters
- xp_for_level
"""

from __future__ import annotations

import pytest

from src.config import TILE, GRASS, WATER, MOUNTAIN, HOUSE
from src.world.collision import (
    tile_at,
    pos_in_bounds_world,
    hits_blocking,
    out_of_bounds,
    try_spend,
    check_object_collision,
    compute_town_clusters,
    xp_for_level,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_world(rows: int, cols: int, fill: int = GRASS) -> list[list[int]]:
    """Return a uniform *rows*×*cols* world filled with *fill*."""
    return [[fill] * cols for _ in range(rows)]


def _set(world: list[list[int]], row: int, col: int, tile: int) -> None:
    world[row][col] = tile


# ---------------------------------------------------------------------------
# tile_at
# ---------------------------------------------------------------------------


class TestTileAt:
    def test_centre_of_tile(self) -> None:
        world = _make_world(5, 5)
        _set(world, 2, 3, MOUNTAIN)
        # Centre of tile (row=2, col=3) is at pixel (3*32+16, 2*32+16)
        px = 3 * TILE + TILE // 2
        py = 2 * TILE + TILE // 2
        assert tile_at(world, px, py) == MOUNTAIN

    def test_origin_corner(self) -> None:
        world = _make_world(5, 5)
        assert tile_at(world, 0.0, 0.0) == GRASS

    def test_out_of_bounds_returns_minus_one(self) -> None:
        world = _make_world(5, 5)
        assert tile_at(world, -1.0, 0.0) == -1
        assert tile_at(world, 0.0, -1.0) == -1
        assert tile_at(world, 5 * TILE + 1.0, 0.0) == -1
        assert tile_at(world, 0.0, 5 * TILE + 1.0) == -1

    def test_empty_world_returns_minus_one(self) -> None:
        assert tile_at([], 0.0, 0.0) == -1


# ---------------------------------------------------------------------------
# pos_in_bounds_world
# ---------------------------------------------------------------------------


class TestPosInBoundsWorld:
    def test_centre_is_in_bounds(self) -> None:
        world = _make_world(5, 5)
        assert pos_in_bounds_world(2.5 * TILE, 2.5 * TILE, world)

    def test_negative_coords_out_of_bounds(self) -> None:
        world = _make_world(5, 5)
        assert not pos_in_bounds_world(-1.0, 0.0, world)
        assert not pos_in_bounds_world(0.0, -1.0, world)

    def test_edge_just_inside(self) -> None:
        world = _make_world(5, 5)
        assert pos_in_bounds_world(5 * TILE - 1, 5 * TILE - 1, world)

    def test_edge_just_outside(self) -> None:
        world = _make_world(5, 5)
        assert not pos_in_bounds_world(5 * TILE, 5 * TILE, world)


# ---------------------------------------------------------------------------
# hits_blocking
# ---------------------------------------------------------------------------


HALF = 16  # standard COLLISION_HALF


class TestHitsBlocking:
    def test_centre_of_grass_is_clear(self) -> None:
        world = _make_world(5, 5)
        cx = 2 * TILE + TILE // 2
        cy = 2 * TILE + TILE // 2
        assert not hits_blocking(world, cx, cy, HALF)

    def test_mountain_blocks(self) -> None:
        world = _make_world(5, 5)
        _set(world, 2, 3, MOUNTAIN)
        # Position circle touching that tile from the left
        cx = 3 * TILE - HALF + 1  # just inside the mountain tile boundary
        cy = 2 * TILE + TILE // 2
        assert hits_blocking(world, cx, cy, HALF)

    def test_water_blocks_by_default(self) -> None:
        world = _make_world(5, 5)
        _set(world, 2, 2, WATER)
        cx = 2 * TILE + TILE // 2
        cy = 2 * TILE + TILE // 2
        assert hits_blocking(world, cx, cy, HALF)

    def test_water_passable_with_extra_passable(self) -> None:
        world = _make_world(5, 5)
        _set(world, 2, 2, WATER)
        cx = 2 * TILE + TILE // 2
        cy = 2 * TILE + TILE // 2
        assert not hits_blocking(world, cx, cy, HALF, extra_passable=frozenset({WATER}))

    def test_extra_passable_does_not_affect_other_blockers(self) -> None:
        world = _make_world(5, 5)
        _set(world, 2, 3, MOUNTAIN)
        cx = 3 * TILE - HALF + 1
        cy = 2 * TILE + TILE // 2
        # Water is passable but mountain is still blocking
        assert hits_blocking(world, cx, cy, HALF, extra_passable=frozenset({WATER}))

    def test_fully_surrounded_by_mountain_blocks(self) -> None:
        # 3×3 world, all MOUNTAIN — circle in the middle must always block
        world = [[MOUNTAIN] * 3 for _ in range(3)]
        cx = 1 * TILE + TILE // 2
        cy = 1 * TILE + TILE // 2
        assert hits_blocking(world, cx, cy, HALF)


# ---------------------------------------------------------------------------
# out_of_bounds
# ---------------------------------------------------------------------------


class TestOutOfBounds:
    def test_centre_is_in_bounds(self) -> None:
        world = _make_world(5, 5)
        cx = 2 * TILE + TILE // 2
        cy = 2 * TILE + TILE // 2
        assert not out_of_bounds(cx, cy, HALF, world)

    def test_negative_x_out_of_bounds(self) -> None:
        world = _make_world(5, 5)
        assert out_of_bounds(-HALF + 1, TILE, HALF, world)

    def test_beyond_right_edge_out_of_bounds(self) -> None:
        world = _make_world(5, 5)
        assert out_of_bounds(5 * TILE + HALF - 1, TILE, HALF, world)

    def test_circle_straddles_edge_is_out(self) -> None:
        world = _make_world(5, 5)
        # Circle centre 8px from left edge, half=16 → left corner at -8
        assert out_of_bounds(8, TILE, HALF, world)


# ---------------------------------------------------------------------------
# try_spend
# ---------------------------------------------------------------------------


class TestTrySpend:
    def test_exact_amount_succeeds(self) -> None:
        inv = {"Wood": 5, "Stone": 3}
        assert try_spend(inv, {"Wood": 5})
        assert "Wood" not in inv  # fully depleted entry is removed

    def test_partial_spend_leaves_remainder(self) -> None:
        inv = {"Wood": 10}
        assert try_spend(inv, {"Wood": 3})
        assert inv["Wood"] == 7

    def test_insufficient_funds_fails(self) -> None:
        inv = {"Wood": 2}
        result = try_spend(inv, {"Wood": 5})
        assert not result
        assert inv["Wood"] == 2  # unchanged

    def test_multi_item_all_or_nothing(self) -> None:
        inv = {"Wood": 10, "Stone": 1}
        # Stone is insufficient
        result = try_spend(inv, {"Wood": 3, "Stone": 3})
        assert not result
        assert inv == {"Wood": 10, "Stone": 1}

    def test_empty_cost_always_succeeds(self) -> None:
        inv = {"Wood": 5}
        assert try_spend(inv, {})
        assert inv == {"Wood": 5}

    def test_missing_item_fails(self) -> None:
        assert not try_spend({}, {"Diamond": 1})


# ---------------------------------------------------------------------------
# check_object_collision
# ---------------------------------------------------------------------------


class TestCheckObjectCollision:
    """Uses a minimal stub for WorldObject since it's not a pygame object."""

    class _FakeObj:
        def blocks_movement(self, cx: float, cy: float, r: float) -> bool:
            return False

    class _BlockingObj:
        def __init__(self, ox: float, oy: float, hitbox: float) -> None:
            self.ox = ox
            self.oy = oy
            self.hitbox = hitbox

        def blocks_movement(self, cx: float, cy: float, r: float) -> bool:
            dist_sq = (cx - self.ox) ** 2 + (cy - self.oy) ** 2
            return dist_sq < (r + self.hitbox) ** 2

    def test_no_objects_is_clear(self) -> None:
        assert not check_object_collision([], 100.0, 100.0, 16.0)

    def test_non_blocking_objects_clear(self) -> None:
        objs = [self._FakeObj()]
        assert not check_object_collision(objs, 100.0, 100.0, 16.0)  # type: ignore[arg-type]

    def test_overlapping_object_blocks(self) -> None:
        obj = self._BlockingObj(100.0, 100.0, 16.0)
        # Circle exactly at same position, radius 1 — definitely overlaps
        assert check_object_collision([obj], 100.0, 100.0, 1.0)  # type: ignore[arg-type]

    def test_far_object_does_not_block(self) -> None:
        obj = self._BlockingObj(500.0, 500.0, 16.0)
        assert not check_object_collision([obj], 100.0, 100.0, 16.0)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# compute_town_clusters
# ---------------------------------------------------------------------------


class TestComputeTownClusters:
    def test_no_houses_returns_empty(self) -> None:
        world = _make_world(5, 5)
        assert compute_town_clusters(world) == {}

    def test_single_house_cluster_size_one(self) -> None:
        world = _make_world(5, 5)
        _set(world, 2, 2, HOUSE)
        result = compute_town_clusters(world)
        assert result[(2, 2)] == 1

    def test_two_adjacent_houses_same_cluster(self) -> None:
        world = _make_world(5, 5)
        _set(world, 2, 2, HOUSE)
        _set(world, 2, 3, HOUSE)
        result = compute_town_clusters(world)
        assert result[(2, 2)] == 2
        assert result[(2, 3)] == 2

    def test_two_diagonal_houses_separate_clusters(self) -> None:
        world = _make_world(5, 5)
        _set(world, 1, 1, HOUSE)
        _set(world, 2, 2, HOUSE)
        result = compute_town_clusters(world)
        assert result[(1, 1)] == 1
        assert result[(2, 2)] == 1

    def test_l_shaped_cluster(self) -> None:
        world = _make_world(5, 5)
        _set(world, 0, 0, HOUSE)
        _set(world, 1, 0, HOUSE)
        _set(world, 1, 1, HOUSE)
        result = compute_town_clusters(world)
        assert result[(0, 0)] == 3
        assert result[(1, 0)] == 3
        assert result[(1, 1)] == 3

    def test_two_separate_clusters(self) -> None:
        world = _make_world(5, 5)
        # Cluster A
        _set(world, 0, 0, HOUSE)
        _set(world, 0, 1, HOUSE)
        # Cluster B — separated by a gap
        _set(world, 4, 4, HOUSE)
        result = compute_town_clusters(world)
        assert result[(0, 0)] == 2
        assert result[(0, 1)] == 2
        assert result[(4, 4)] == 1


# ---------------------------------------------------------------------------
# xp_for_level
# ---------------------------------------------------------------------------


class TestXpForLevel:
    def test_level_1_is_baseline(self) -> None:
        assert xp_for_level(1) == 20

    def test_level_2_increases(self) -> None:
        assert xp_for_level(2) > xp_for_level(1)

    def test_monotonically_increasing(self) -> None:
        levels = [xp_for_level(i) for i in range(1, 15)]
        assert all(levels[i] < levels[i + 1] for i in range(len(levels) - 1))

    def test_known_values(self) -> None:
        # Formula: 20 + 5*(lvl-1)*lvl//2
        # lvl=1: 20 + 0 = 20
        # lvl=2: 20 + 5 = 25
        # lvl=3: 20 + 15 = 35
        # lvl=4: 20 + 30 = 50
        assert xp_for_level(1) == 20
        assert xp_for_level(2) == 25
        assert xp_for_level(3) == 35
        assert xp_for_level(4) == 50
