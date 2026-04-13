"""Attack pattern definitions and weapon registry."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from src.config import TILE


class AttackPattern(Enum):
    """Determines how a weapon attack moves and hits."""

    LINEAR = "linear"
    MELEE_ARC = "melee_arc"
    BOOMERANG = "boomerang"
    AOE = "aoe"
    CHAIN = "chain"
    BEAM = "beam"
    HOMING = "homing"
    SPIRAL = "spiral"


@dataclass(frozen=True)
class WeaponDef:
    """Immutable definition for a weapon type."""

    weapon_id: str
    name: str
    damage: int
    cooldown: int
    color: tuple[int, int, int]
    knockback: float
    pattern: AttackPattern
    wall_collide: bool = True
    pierce: bool = False
    # Visual rendering hint: ("circle",), ("line", length, width), etc.
    draw: tuple[Any, ...] = ("circle",)
    # Pattern-specific parameters (keys depend on pattern type)
    pattern_config: dict[str, Any] = field(default_factory=dict)
    # Optional: weapon spawned when this attack dies (e.g. bomb → explosion)
    on_death_spawn: str | None = None


# ---------------------------------------------------------------------------
# Default pattern configs — used as fallback for any missing keys
# ---------------------------------------------------------------------------

_LINEAR_DEFAULTS: dict[str, Any] = {
    "speed": 5.0,
    "distance": TILE * 5,
    "size": 4,
}

_MELEE_ARC_DEFAULTS: dict[str, Any] = {
    "arc_degrees": 90,
    "radius": TILE * 1.5,
    "duration_frames": 12,
}

_BOOMERANG_DEFAULTS: dict[str, Any] = {
    "speed": 5.0,
    "max_distance": TILE * 6,
    "return_speed": 7.0,
    "size": 5,
}

_AOE_DEFAULTS: dict[str, Any] = {
    "radius": TILE * 2,
    "delay_frames": 0,
    "linger_frames": 15,
}

_CHAIN_DEFAULTS: dict[str, Any] = {
    "speed": 6.0,
    "max_bounces": 3,
    "bounce_range": TILE * 4,
    "damage_decay": 0.7,
    "size": 4,
}

_BEAM_DEFAULTS: dict[str, Any] = {
    "range": TILE * 8,
    "width": 6,
    "tick_rate": 10,
}

_HOMING_DEFAULTS: dict[str, Any] = {
    "speed": 4.0,
    "distance": TILE * 8,
    "turn_rate": 5.0,
    "acquire_cone": 60,
    "size": 4,
}

_SPIRAL_DEFAULTS: dict[str, Any] = {
    "radius_min": TILE * 0.5,
    "radius_max": TILE * 2.5,
    "angular_speed": 8.0,
    "duration": 90,
    "size": 4,
}

PATTERN_DEFAULTS: dict[AttackPattern, dict[str, Any]] = {
    AttackPattern.LINEAR: _LINEAR_DEFAULTS,
    AttackPattern.MELEE_ARC: _MELEE_ARC_DEFAULTS,
    AttackPattern.BOOMERANG: _BOOMERANG_DEFAULTS,
    AttackPattern.AOE: _AOE_DEFAULTS,
    AttackPattern.CHAIN: _CHAIN_DEFAULTS,
    AttackPattern.BEAM: _BEAM_DEFAULTS,
    AttackPattern.HOMING: _HOMING_DEFAULTS,
    AttackPattern.SPIRAL: _SPIRAL_DEFAULTS,
}


def get_pattern_config(weapon: WeaponDef) -> dict[str, Any]:
    """Return the merged pattern config (defaults + overrides) for a weapon."""
    defaults = PATTERN_DEFAULTS.get(weapon.pattern, {})
    merged = {**defaults, **weapon.pattern_config}
    return merged


# ---------------------------------------------------------------------------
# Weapon Registry
# ---------------------------------------------------------------------------

WEAPON_REGISTRY: dict[str, WeaponDef] = {}


def _register(w: WeaponDef) -> WeaponDef:
    WEAPON_REGISTRY[w.weapon_id] = w
    return w


# -- Starting weapons (migrated from old WEAPONS list) ---------------------

_register(WeaponDef(
    weapon_id="rock_throw",
    name="Rock Throw",
    damage=8,
    cooldown=25,
    color=(160, 150, 140),
    knockback=4,
    pattern=AttackPattern.LINEAR,
    wall_collide=True,
    pierce=False,
    draw=("circle",),
    pattern_config={"speed": 5.0, "distance": TILE * 5, "size": 4},
))

_register(WeaponDef(
    weapon_id="iron_dagger",
    name="Iron Dagger",
    damage=15,
    cooldown=18,
    color=(200, 190, 180),
    knockback=5,
    pattern=AttackPattern.LINEAR,
    wall_collide=True,
    pierce=False,
    draw=("line", 10, 2),
    pattern_config={"speed": 7.0, "distance": TILE * 3, "size": 3},
))

_register(WeaponDef(
    weapon_id="fire_bolt",
    name="Fire Bolt",
    damage=25,
    cooldown=35,
    color=(255, 120, 30),
    knockback=6,
    pattern=AttackPattern.LINEAR,
    wall_collide=True,
    pierce=True,
    draw=("circle",),
    pattern_config={"speed": 6.0, "distance": TILE * 7, "size": 5},
))

# -- New weapons -----------------------------------------------------------

_register(WeaponDef(
    weapon_id="iron_sword",
    name="Iron Sword",
    damage=18,
    cooldown=22,
    color=(190, 185, 175),
    knockback=6,
    pattern=AttackPattern.MELEE_ARC,
    wall_collide=False,
    pierce=True,
    draw=("arc",),
    pattern_config={"arc_degrees": 120, "radius": TILE * 1.8, "duration_frames": 10},
))

_register(WeaponDef(
    weapon_id="wooden_bow",
    name="Wooden Bow",
    damage=12,
    cooldown=20,
    color=(180, 140, 70),
    knockback=3,
    pattern=AttackPattern.LINEAR,
    wall_collide=True,
    pierce=False,
    draw=("line", 14, 2),
    pattern_config={"speed": 8.0, "distance": TILE * 8, "size": 2},
))

_register(WeaponDef(
    weapon_id="boomerang",
    name="Boomerang",
    damage=14,
    cooldown=30,
    color=(180, 120, 60),
    knockback=4,
    pattern=AttackPattern.BOOMERANG,
    wall_collide=True,
    pierce=True,
    draw=("line", 8, 3),
    pattern_config={"speed": 5.5, "max_distance": TILE * 6, "return_speed": 7.0, "size": 5},
))

_register(WeaponDef(
    weapon_id="bomb",
    name="Bomb",
    damage=10,
    cooldown=50,
    color=(80, 80, 80),
    knockback=2,
    pattern=AttackPattern.LINEAR,
    wall_collide=True,
    pierce=False,
    draw=("circle",),
    pattern_config={"speed": 4.0, "distance": TILE * 4, "size": 6},
    on_death_spawn="bomb_explosion",
))

_register(WeaponDef(
    weapon_id="bomb_explosion",
    name="Bomb Explosion",
    damage=30,
    cooldown=0,
    color=(255, 160, 40),
    knockback=10,
    pattern=AttackPattern.AOE,
    wall_collide=False,
    pierce=True,
    draw=("circle",),
    pattern_config={"radius": TILE * 2.5, "delay_frames": 0, "linger_frames": 12},
))

_register(WeaponDef(
    weapon_id="lightning_chain",
    name="Lightning Chain",
    damage=20,
    cooldown=40,
    color=(130, 180, 255),
    knockback=3,
    pattern=AttackPattern.CHAIN,
    wall_collide=False,
    pierce=True,
    draw=("line", 10, 2),
    pattern_config={"speed": 9.0, "max_bounces": 4, "bounce_range": TILE * 5, "damage_decay": 0.75, "size": 4},
))

_register(WeaponDef(
    weapon_id="ice_beam",
    name="Ice Beam",
    damage=6,
    cooldown=5,
    color=(140, 220, 255),
    knockback=1,
    pattern=AttackPattern.BEAM,
    wall_collide=True,
    pierce=True,
    draw=("line", 8, 6),
    pattern_config={"range": TILE * 7, "width": 8, "tick_rate": 8},
))

_register(WeaponDef(
    weapon_id="homing_orb",
    name="Homing Orb",
    damage=20,
    cooldown=35,
    color=(180, 100, 255),
    knockback=5,
    pattern=AttackPattern.HOMING,
    wall_collide=True,
    pierce=False,
    draw=("circle",),
    pattern_config={"speed": 4.5, "distance": TILE * 10, "turn_rate": 6.0, "acquire_cone": 90, "size": 5},
))

_register(WeaponDef(
    weapon_id="spirit_blade",
    name="Spirit Blade",
    damage=12,
    cooldown=45,
    color=(100, 255, 180),
    knockback=4,
    pattern=AttackPattern.SPIRAL,
    wall_collide=False,
    pierce=True,
    draw=("line", 12, 3),
    pattern_config={"radius_min": TILE * 0.6, "radius_max": TILE * 2.5, "angular_speed": 10.0, "duration": 80, "size": 5},
))

_register(WeaponDef(
    weapon_id="ancient_staff",
    name="Ancient Staff",
    damage=35,
    cooldown=45,
    color=(180, 120, 255),
    knockback=8,
    pattern=AttackPattern.LINEAR,
    wall_collide=True,
    pierce=True,
    draw=("circle",),
    pattern_config={"speed": 7.0, "distance": TILE * 10, "size": 7},
))

# -- Ordered default unlock list ------------------------------------------
# The first three match the old WEAPONS[0..2] for migration purposes.

DEFAULT_WEAPONS: list[str] = ["rock_throw", "iron_dagger", "fire_bolt"]

# Legacy migration: old weapon_level (0, 1, 2) → weapon_id
LEGACY_WEAPON_MAP: dict[int, str] = {
    0: "rock_throw",
    1: "iron_dagger",
    2: "fire_bolt",
}
