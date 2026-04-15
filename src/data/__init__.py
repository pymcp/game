"""Game data: tiles, weapons, enemies, pickaxes."""

from src.data.tiles import (
    TILE_INFO,
    BLOCKING_TILES,
    OBJECT_TILE_IDS,
    WORLD_OBJECT_TILE_IDS,
)
from src.data.pickaxes import PICKAXES, UPGRADE_COSTS
from src.data.weapons import WEAPONS, WEAPON_UNLOCK_COSTS
from src.data.enemies import ENEMY_TYPES, EnemyEnvironment, EnemyTypeInfo, PortalQuestType
from src.data.creatures import CREATURE_TYPES, CreatureEnvironment
from src.data.recipes import RECIPES
from src.data.armor import (
    ArmorSlot,
    ArmorMaterial,
    AccessorySlot,
    AccessoryEffect,
    ARMOR_PIECES,
    ACCESSORY_PIECES,
    ARMOR_SLOT_ORDER,
    SLOT_LABELS,
    item_fits_slot,
)

__all__ = [
    "TILE_INFO",
    "BLOCKING_TILES",
    "OBJECT_TILE_IDS",
    "WORLD_OBJECT_TILE_IDS",
    "PICKAXES",
    "UPGRADE_COSTS",
    "WEAPONS",
    "WEAPON_UNLOCK_COSTS",
    "ENEMY_TYPES",
    "EnemyEnvironment",
    "EnemyTypeInfo",
    "PortalQuestType",
    "CREATURE_TYPES",
    "CreatureEnvironment",
    "RECIPES",
    "ArmorSlot",
    "ArmorMaterial",
    "AccessorySlot",
    "AccessoryEffect",
    "ARMOR_PIECES",
    "ACCESSORY_PIECES",
    "ARMOR_SLOT_ORDER",
    "SLOT_LABELS",
    "item_fits_slot",
]
