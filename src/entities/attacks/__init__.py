"""Attack pattern subclasses and factory function."""

from __future__ import annotations

from src.data.attack_patterns import AttackPattern, WeaponDef, WEAPON_REGISTRY
from src.entities.attack import Attack
from src.entities.attacks.linear import LinearAttack
from src.entities.attacks.melee_arc import MeleeArcAttack
from src.entities.attacks.boomerang import BoomerangAttack
from src.entities.attacks.aoe import AoEAttack
from src.entities.attacks.chain import ChainAttack
from src.entities.attacks.beam import BeamAttack
from src.entities.attacks.homing import HomingAttack
from src.entities.attacks.spiral import SpiralAttack

_PATTERN_MAP: dict[AttackPattern, type[Attack]] = {
    AttackPattern.LINEAR: LinearAttack,
    AttackPattern.MELEE_ARC: MeleeArcAttack,
    AttackPattern.BOOMERANG: BoomerangAttack,
    AttackPattern.AOE: AoEAttack,
    AttackPattern.CHAIN: ChainAttack,
    AttackPattern.BEAM: BeamAttack,
    AttackPattern.HOMING: HomingAttack,
    AttackPattern.SPIRAL: SpiralAttack,
}


def create_attack(
    weapon: WeaponDef,
    x: float,
    y: float,
    dir_x: float,
    dir_y: float,
    player_id: int = 1,
    map_key: str | tuple = "overland",
    damage_mult: float = 1.0,
) -> Attack:
    """Create the correct Attack subclass for a weapon definition."""
    cls = _PATTERN_MAP[weapon.pattern]
    return cls(
        x=x,
        y=y,
        dir_x=dir_x,
        dir_y=dir_y,
        weapon=weapon,
        player_id=player_id,
        map_key=map_key,
        damage_mult=damage_mult,
    )


__all__ = [
    "Attack",
    "LinearAttack",
    "MeleeArcAttack",
    "BoomerangAttack",
    "AoEAttack",
    "ChainAttack",
    "BeamAttack",
    "HomingAttack",
    "SpiralAttack",
    "create_attack",
]
