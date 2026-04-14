"""Tests for creature mount speed system and wander FSM.

Verifies:
- mount_speed_mult defaults correctly for all creature types
- update_riding uses player_speed * mount_speed_mult (not creature speed)
- Wander speeds are slower than before
- mountable flag is set correctly from catalogue
- Save/load roundtrip preserves mount_speed_mult
- Backward compat: missing mount_speed_mult defaults to 1.5; old creature_class ignored
- Wander FSM: creatures start idle, transition correctly, rest between walks
"""

from __future__ import annotations

import math

import pytest

from src.config import GRASS, TILE
from src.entities.creature import Creature, WanderState


def _make_world(rows: int = 20, cols: int = 20) -> list[list[int]]:
    return [[GRASS] * cols for _ in range(rows)]


def _horse() -> Creature:
    return Creature(100, 100, "horse", "overland")


def _sea(kind: str) -> Creature:
    return Creature(100, 100, kind, ("underwater", 0, 0))


# ------------------------------------------------------------------
# mount_speed_mult defaults
# ------------------------------------------------------------------


class TestMountSpeedMultDefaults:
    def test_horse_default(self) -> None:
        assert _horse().mount_speed_mult == 1.5

    def test_dolphin_default(self) -> None:
        assert _sea("dolphin").mount_speed_mult == 1.5

    def test_fish_default(self) -> None:
        assert _sea("fish").mount_speed_mult == 1.5

    def test_jellyfish_default(self) -> None:
        assert _sea("jellyfish").mount_speed_mult == 1.5

    def test_grasshopper_default(self) -> None:
        c = Creature(100, 100, "grasshopper", "overland")
        assert c.mount_speed_mult == 1.8


# ------------------------------------------------------------------
# Mountable flag
# ------------------------------------------------------------------


class TestMountableFlag:
    def test_horse_mountable(self) -> None:
        assert _horse().mountable is True

    def test_grasshopper_mountable(self) -> None:
        assert Creature(100, 100, "grasshopper", "overland").mountable is True

    def test_dolphin_mountable(self) -> None:
        assert _sea("dolphin").mountable is True

    def test_fish_not_mountable(self) -> None:
        assert _sea("fish").mountable is False

    def test_jellyfish_not_mountable(self) -> None:
        assert _sea("jellyfish").mountable is False


# ------------------------------------------------------------------
# Creature catalogue completeness
# ------------------------------------------------------------------


class TestCreatureCatalogue:
    def test_all_types_present(self) -> None:
        from src.data.creatures import CREATURE_TYPES

        for kind in ("horse", "grasshopper", "dolphin", "fish", "jellyfish"):
            assert kind in CREATURE_TYPES

    def test_all_types_have_required_keys(self) -> None:
        from src.data.creatures import CREATURE_TYPES

        required = {"environment", "speed", "size", "color_fn", "mount_speed_mult", "mountable"}
        for kind, spec in CREATURE_TYPES.items():
            missing = required - set(spec.keys())
            assert not missing, f"{kind} missing keys: {missing}"

    def test_color_fn_returns_rgb_tuple(self) -> None:
        from src.data.creatures import CREATURE_TYPES

        for kind, spec in CREATURE_TYPES.items():
            color = spec["color_fn"]()
            assert isinstance(color, tuple) and len(color) == 3, f"{kind} color_fn bad"
            for ch in color:
                assert 0 <= ch <= 255, f"{kind} channel out of range"


# ------------------------------------------------------------------
# Wander speeds are slow
# ------------------------------------------------------------------


class TestWanderSpeedsSlow:
    def test_horse_wander_speed_below_player(self) -> None:
        assert _horse().speed < 0.5  # catalogue=0.3 ± 15%

    def test_dolphin_wander_speed_below_player(self) -> None:
        assert _sea("dolphin").speed < 1.5  # catalogue=0.9 ± 15%

    def test_fish_wander_speed_below_player(self) -> None:
        assert _sea("fish").speed < 1.5  # catalogue=1.0 ± 15%

    def test_jellyfish_wander_speed_slow(self) -> None:
        assert _sea("jellyfish").speed < 0.6  # catalogue=0.4 ± 15%


# ------------------------------------------------------------------
# update_riding uses player_speed * mount_speed_mult
# ------------------------------------------------------------------


class TestUpdateRiding:
    def test_riding_speed_is_player_based(self) -> None:
        """Mounted speed should be based on player_speed, not creature speed."""
        c = _horse()
        world = _make_world()
        start_x = c.x

        dt = 1.0
        player_speed = 3.2
        c.update_riding(1.0, 0.0, dt, world, player_speed)

        distance = c.x - start_x
        expected = player_speed * c.mount_speed_mult * dt
        assert abs(distance - expected) < 0.01

    def test_riding_speed_scales_with_player_speed(self) -> None:
        """Faster player = faster mount."""
        c = Creature(TILE * 5, TILE * 5, "horse", "overland")
        world = _make_world()

        c.update_riding(1.0, 0.0, 1.0, world, 4.0)
        dist_fast = c.x - TILE * 5

        c2 = Creature(TILE * 5, TILE * 5, "horse", "overland")
        c2.update_riding(1.0, 0.0, 1.0, world, 2.0)
        dist_slow = c2.x - TILE * 5

        assert dist_fast > dist_slow

    def test_riding_speed_scales_with_mount_speed_mult(self) -> None:
        """Higher mount_speed_mult = faster mounted speed."""
        c1 = Creature(TILE * 5, TILE * 5, "horse", "overland")
        c1.mount_speed_mult = 2.0
        c2 = Creature(TILE * 5, TILE * 5, "horse", "overland")
        c2.mount_speed_mult = 1.0
        world = _make_world()

        c1.update_riding(1.0, 0.0, 1.0, world, 3.2)
        c2.update_riding(1.0, 0.0, 1.0, world, 3.2)

        assert c1.x > c2.x

    def test_riding_default_player_speed(self) -> None:
        """update_riding defaults to player_speed=3.2 for backward compat."""
        c = _horse()
        world = _make_world()
        start_x = c.x

        c.update_riding(1.0, 0.0, 1.0, world)

        distance = c.x - start_x
        expected = 3.2 * c.mount_speed_mult * 1.0
        assert abs(distance - expected) < 0.01

    def test_riding_no_movement_when_stationary(self) -> None:
        c = _horse()
        world = _make_world()
        start_x, start_y = c.x, c.y

        c.update_riding(0.0, 0.0, 1.0, world, 3.2)

        assert c.x == start_x
        assert c.y == start_y

    def test_mounted_speed_exceeds_player_speed(self) -> None:
        """At 1.5× mult, mounted speed should be faster than walking."""
        c = Creature(TILE * 5, TILE * 5, "horse", "overland")
        world = _make_world()
        player_speed = 3.2

        c.update_riding(1.0, 0.0, 1.0, world, player_speed)
        mount_distance = c.x - TILE * 5

        assert mount_distance > player_speed  # 4.8 > 3.2


# ------------------------------------------------------------------
# Save / load roundtrip
# ------------------------------------------------------------------


class TestSaveLoadMountSpeed:
    def test_serialize_includes_mount_speed_mult(self) -> None:
        from src.save import _serialize_creature

        c = _horse()
        data = _serialize_creature(c)
        assert "mount_speed_mult" in data
        assert data["mount_speed_mult"] == 1.5

    def test_serialize_no_creature_class(self) -> None:
        """New serializer should NOT include creature_class key."""
        from src.save import _serialize_creature

        data = _serialize_creature(_horse())
        assert "creature_class" not in data

    def test_deserialize_preserves_mount_speed_mult(self) -> None:
        from src.save import _serialize_creature, _deserialize_creature

        c = _horse()
        c.mount_speed_mult = 2.0
        data = _serialize_creature(c)
        loaded = _deserialize_creature(data)
        assert loaded.mount_speed_mult == 2.0

    def test_deserialize_backward_compat_defaults_1_5(self) -> None:
        """Old saves without mount_speed_mult should default to 1.5."""
        from src.save import _deserialize_creature

        data = {
            "creature_class": "overland",  # old field — should be ignored
            "x": 100,
            "y": 100,
            "kind": "horse",
            "speed": 0.6,
            "size": 0.9,
            "body_color": [139, 90, 43],
            "facing_direction": "right",
            "facing_right": True,
            "home_map": "overland",
        }
        c = _deserialize_creature(data)
        assert c.mount_speed_mult == 1.5

    def test_deserialize_old_creature_class_overland_ignored(self) -> None:
        """Old saves with creature_class='overland' should still load as Creature."""
        from src.save import _deserialize_creature

        data = {
            "creature_class": "overland",
            "x": 100,
            "y": 100,
            "kind": "horse",
            "speed": 0.3,
            "size": 0.9,
            "body_color": [139, 90, 43],
            "facing_direction": "right",
            "facing_right": True,
            "home_map": "overland",
            "mount_speed_mult": 1.5,
        }
        c = _deserialize_creature(data)
        assert isinstance(c, Creature)
        assert c.kind == "horse"

    def test_deserialize_old_creature_class_sea_ignored(self) -> None:
        """Old saves with creature_class='sea' should load as Creature."""
        from src.save import _deserialize_creature

        data = {
            "creature_class": "sea",
            "x": 200,
            "y": 200,
            "kind": "dolphin",
            "speed": 0.9,
            "size": 1.95,
            "body_color": [60, 130, 200],
            "facing_direction": "right",
            "facing_right": True,
            "home_map": "overland",
            "mount_speed_mult": 1.5,
        }
        c = _deserialize_creature(data)
        assert isinstance(c, Creature)
        assert c.kind == "dolphin"

    def test_sea_creature_backward_compat(self) -> None:
        """_deserialize_sea_creature backward compat wrapper still works."""
        from src.save import _deserialize_sea_creature

        data = {
            "x": 200,
            "y": 200,
            "kind": "dolphin",
            "speed": 0.9,
            "size": 1.95,
            "body_color": [60, 130, 200],
            "facing_right": True,
            "home_map": "overland",
            "mount_speed_mult": 1.5,
        }
        sc = _deserialize_sea_creature(data)
        assert sc.mount_speed_mult == 1.5
        assert isinstance(sc, Creature)


# ------------------------------------------------------------------
# Wander FSM behaviour
# ------------------------------------------------------------------


class TestWanderFSM:
    def test_creature_starts_idle(self) -> None:
        assert _horse()._wander_state is WanderState.IDLE

    def test_idle_timer_initial_range(self) -> None:
        """Idle timer must fall in the expected rest range."""
        for _ in range(20):
            c = _horse()
            assert 3.0 <= c._idle_timer <= 8.0

    def test_idle_creature_does_not_move(self) -> None:
        """While IDLE the creature stays put regardless of remaining timer."""
        c = _horse()
        c._idle_timer = 5.0
        world = _make_world()
        start_x, start_y = c.x, c.y

        for _ in range(10):
            c.update(0.1, world)

        assert c.x == start_x
        assert c.y == start_y

    def test_idle_to_walking_transition(self) -> None:
        """When the idle timer expires the creature switches to WALKING."""
        c = _horse()
        c._idle_timer = 0.05
        world = _make_world()

        c.update(0.1, world)  # timer expires → should now be WALKING

        assert c._wander_state is WanderState.WALKING

    def test_walking_creature_moves(self) -> None:
        """A creature in WALKING state should have changed position after updates."""
        c = _horse()
        c._idle_timer = 0.0
        world = _make_world()
        # Trigger transition to WALKING
        c.update(0.01, world)
        assert c._wander_state is WanderState.WALKING

        start_x, start_y = c.x, c.y
        for _ in range(30):
            c.update(0.1, world)
            if c.x != start_x or c.y != start_y:
                break

        assert c.x != start_x or c.y != start_y

    def test_walking_to_idle_on_arrival(self) -> None:
        """Creature transitions back to IDLE once it reaches its destination."""
        c = _horse()
        world = _make_world()
        # Force into WALKING toward a very nearby dest so it arrives quickly
        c._wander_state = WanderState.WALKING
        c.dest_x = c.x + 2  # within arrival threshold of 4px
        c.dest_y = c.y

        c.update(0.1, world)

        assert c._wander_state is WanderState.IDLE

    def test_idle_timer_reset_on_arrival(self) -> None:
        """On arrival the idle timer is reset to a fresh rest interval."""
        c = _horse()
        world = _make_world()
        c._wander_state = WanderState.WALKING
        c.dest_x = c.x + 2
        c.dest_y = c.y
        c._idle_timer = 0.0

        c.update(0.1, world)

        assert 3.0 <= c._idle_timer <= 8.0

    def test_wander_dest_within_short_range(self) -> None:
        """Wander destinations should be no more than TILE * 4 from origin."""
        c = Creature(TILE * 10, TILE * 10, "horse", "overland")
        world = _make_world(rows=30, cols=30)
        # Force several destination picks and check range
        for _ in range(20):
            c._pick_wander_dest(30, 30)
            dist = math.hypot(c.dest_x - TILE * 10, c.dest_y - TILE * 10)
            assert dist <= TILE * 4 + 1  # +1 for float rounding

    def test_blocked_creature_returns_to_idle(self) -> None:
        """Creature blocked by a wall transitions back to IDLE."""
        from src.data.tiles import CAVE_WALL
        world = _make_world()
        # Fill a column of walls directly to the right of the creature
        cx, cy = TILE * 5, TILE * 5
        for r in range(len(world)):
            world[r][6] = CAVE_WALL

        c = Creature(cx, cy, "horse", "overland")
        c.speed = 10.0  # fast enough to reach the wall in a few ticks
        c._wander_state = WanderState.WALKING
        c.dest_x = cx + TILE * 3  # destination is past the wall
        c.dest_y = cy

        # Run until blocked or max iterations
        for _ in range(100):
            c.update(0.1, world)
            if c._wander_state is WanderState.IDLE:
                break

        assert c._wander_state is WanderState.IDLE
