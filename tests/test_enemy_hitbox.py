"""Tests for enemy hitbox radius system."""

from __future__ import annotations

import math

import pygame
import pytest

from src.config import TILE
from src.data.enemies import ENEMY_TYPES, _compute_hitbox_radius
from src.entities.enemy import Enemy, _PLAYER_COLLISION_HALF

# ---------------------------------------------------------------------------
# _compute_hitbox_radius unit tests
# ---------------------------------------------------------------------------


class TestComputeHitboxRadius:
    def test_single_circle(self) -> None:
        cmds = [("circle", (0, 0, 0), 0, 0, 10)]
        # extent = abs(0) + 10 = 10, scaled by TILE//32
        assert _compute_hitbox_radius(cmds) == 10 * (TILE // 32)

    def test_offset_circle(self) -> None:
        cmds = [("circle", (0, 0, 0), 5, 0, 8)]
        # extent = abs(5) + 8 = 13 (radius >= 5 so not skipped)
        assert _compute_hitbox_radius(cmds) == 13 * (TILE // 32)

    def test_small_circle_skipped(self) -> None:
        # If a large rect exists, the small circle extent is ignored
        cmds = [
            ("circle", (0, 0, 0), 20, 0, 3),  # area ~28, extent 23
            ("rect", (0, 0, 0), -5, -5, 10, 10),  # area 100, extent 5
        ]
        # Largest area is the rect → extent 5
        assert _compute_hitbox_radius(cmds) == 5 * (TILE // 32)

    def test_rect(self) -> None:
        cmds = [("rect", (0, 0, 0), -10, -5, 20, 10)]
        # max(|-10|, |-10+20|, |-5|, |-5+10|) = 10
        assert _compute_hitbox_radius(cmds) == 10 * (TILE // 32)

    def test_ellipse(self) -> None:
        cmds = [("ellipse", (0, 0, 0), -14, -6, 28, 20)]
        # max(14, 14, 6, 14) = 14
        assert _compute_hitbox_radius(cmds) == 14 * (TILE // 32)

    def test_polygon_body(self) -> None:
        # Large polygons counted as body shapes (e.g. boss body)
        cmds = [
            (
                "polygon",
                (0, 0, 0),
                [(-12, -10), (0, -14), (12, -10), (10, 10), (-10, 10)],
            )
        ]
        # max of abs values: 14
        assert _compute_hitbox_radius(cmds) == 14 * (TILE // 32)

    def test_polygon_small_loses_to_rect(self) -> None:
        # A small polygon (hat) loses to a large rect (body)
        cmds = [
            ("polygon", (0, 0, 0), [(-4, -20), (0, -26), (4, -20)]),  # area ~24
            ("rect", (0, 0, 0), -7, -7, 14, 14),  # area 196, extent 7
        ]
        assert _compute_hitbox_radius(cmds) == 7 * (TILE // 32)

    def test_line_skipped(self) -> None:
        # Lines are limbs/decorative and should be skipped
        cmds = [("line", (0, 0, 0), -5, -20, 5, 20, 2)]
        assert _compute_hitbox_radius(cmds) == 4  # minimum

    def test_small_rect_skipped_by_area(self) -> None:
        # A larger-area shape wins over a smaller one with wider extent
        cmds = [
            ("rect", (0, 0, 0), -2, -2, 4, 4),  # area 16, extent 2
            ("ellipse", (0, 0, 0), -10, -5, 20, 10),  # area 200, extent 10
        ]
        assert _compute_hitbox_radius(cmds) == 10 * (TILE // 32)

    def test_multiple_commands_takes_max(self) -> None:
        cmds = [
            ("circle", (0, 0, 0), 0, 0, 5),  # extent = 5
            ("rect", (0, 0, 0), -15, -3, 30, 6),  # extent = 15
        ]
        assert _compute_hitbox_radius(cmds) == 15 * (TILE // 32)

    def test_minimum_radius(self) -> None:
        # Tiny shape should still get minimum 4px
        cmds = [("circle", (0, 0, 0), 0, 0, 1)]
        result = _compute_hitbox_radius(cmds)
        assert result >= 4


# ---------------------------------------------------------------------------
# ENEMY_TYPES population
# ---------------------------------------------------------------------------


class TestEnemyTypesHitbox:
    def test_all_types_have_hitbox_radius(self) -> None:
        for type_key, info in ENEMY_TYPES.items():
            assert hasattr(info, "hitbox_radius"), f"{type_key} missing hitbox_radius"
            assert isinstance(
                info.hitbox_radius, int
            ), f"{type_key} hitbox_radius not int"
            assert info.hitbox_radius > 0, f"{type_key} hitbox_radius <= 0"

    def test_large_enemies_have_larger_hitbox(self) -> None:
        slime_r = ENEMY_TYPES["slime"].hitbox_radius
        troll_r = ENEMY_TYPES["cave_troll"].hitbox_radius
        assert troll_r > slime_r, "cave_troll should have larger hitbox than slime"

    def test_small_enemies_have_smaller_hitbox(self) -> None:
        bat_r = ENEMY_TYPES["bat"].hitbox_radius
        sentinel_r = ENEMY_TYPES["stone_sentinel"].hitbox_radius
        assert bat_r < sentinel_r, "bat should have smaller hitbox than stone_sentinel"


# ---------------------------------------------------------------------------
# Enemy instance
# ---------------------------------------------------------------------------


class TestEnemyInstance:
    def test_hitbox_radius_on_instance(self) -> None:
        enemy = Enemy(100.0, 100.0, "slime")
        assert enemy.hitbox_radius == ENEMY_TYPES["slime"].hitbox_radius

    def test_hitbox_radius_varies_by_type(self) -> None:
        slime = Enemy(100.0, 100.0, "slime")
        troll = Enemy(100.0, 100.0, "cave_troll")
        assert troll.hitbox_radius > slime.hitbox_radius


# ---------------------------------------------------------------------------
# Enemy melee uses hitbox_radius
# ---------------------------------------------------------------------------


class TestEnemyMelee:
    def test_try_attack_within_hitbox_plus_player(self) -> None:
        enemy = Enemy(100.0, 100.0, "slime")
        enemy.state = "attack"
        enemy.cooldown = 0
        # Place player just within attack range
        attack_range = enemy.hitbox_radius + _PLAYER_COLLISION_HALF
        px = 100.0 + attack_range - 1
        py = 100.0
        dmg = enemy.try_attack(px, py)
        assert dmg > 0

    def test_try_attack_outside_range(self) -> None:
        enemy = Enemy(100.0, 100.0, "slime")
        enemy.state = "attack"
        enemy.cooldown = 0
        attack_range = enemy.hitbox_radius + _PLAYER_COLLISION_HALF
        px = 100.0 + attack_range + 10
        py = 100.0
        dmg = enemy.try_attack(px, py)
        assert dmg == 0

    def test_large_enemy_attacks_from_further(self) -> None:
        slime = Enemy(100.0, 100.0, "slime")
        troll = Enemy(100.0, 100.0, "cave_troll")
        slime.state = "attack"
        troll.state = "attack"
        slime.cooldown = 0
        troll.cooldown = 0
        # Distance between slime max range and troll max range
        slime_range = slime.hitbox_radius + _PLAYER_COLLISION_HALF
        troll_range = troll.hitbox_radius + _PLAYER_COLLISION_HALF
        # Place at a distance where troll can hit but slime can't
        mid_dist = (slime_range + troll_range) / 2
        px = 100.0 + mid_dist
        py = 100.0
        assert troll.try_attack(px, py) > 0
        assert slime.try_attack(px, py) == 0
