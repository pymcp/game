"""Armor and accessory definitions — materials, slots, effects, and piece data."""

from __future__ import annotations

from enum import Enum


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ArmorSlot(Enum):
    HELMET = "helmet"
    CHEST = "chest"
    LEGS = "legs"
    BOOTS = "boots"


class ArmorMaterial(Enum):
    STONE = "Stone"
    IRON = "Iron"
    GOLD = "Gold"
    DIAMOND = "Diamond"
    CORAL = "Coral"
    ANCIENT_STONE = "Ancient Stone"


class AccessorySlot(Enum):
    RING1 = "ring1"
    RING2 = "ring2"
    AMULET = "amulet"


class AccessoryEffect(Enum):
    XP_BOOST = "xp_boost"
    SPEED_BOOST = "speed_boost"
    DAMAGE_BOOST = "damage_boost"
    HP_BOOST = "hp_boost"


# ---------------------------------------------------------------------------
# Internal data tables
# ---------------------------------------------------------------------------

# Per-material properties: (defense_pct per piece, max durability, RGB color)
_MATERIAL_STATS: dict[ArmorMaterial, tuple[float, int, tuple[int, int, int]]] = {
    ArmorMaterial.STONE: (0.03, 15, (150, 150, 150)),
    ArmorMaterial.IRON: (0.07, 25, (186, 176, 166)),
    ArmorMaterial.GOLD: (0.11, 20, (230, 200, 60)),
    ArmorMaterial.DIAMOND: (0.16, 40, (90, 210, 240)),
    ArmorMaterial.CORAL: (0.09, 18, (240, 120, 130)),
    ArmorMaterial.ANCIENT_STONE: (0.20, 45, (140, 90, 200)),
}

# Slot display names
_SLOT_LABELS: dict[ArmorSlot, str] = {
    ArmorSlot.HELMET: "Helmet",
    ArmorSlot.CHEST: "Chest",
    ArmorSlot.LEGS: "Legs",
    ArmorSlot.BOOTS: "Boots",
}


# ---------------------------------------------------------------------------
# ARMOR_PIECES — 24 entries (6 materials × 4 slots)
# ---------------------------------------------------------------------------


def _build_armor_pieces() -> dict[str, dict]:
    pieces: dict[str, dict] = {}
    for mat in ArmorMaterial:
        defense_pct, durability, color = _MATERIAL_STATS[mat]
        for slot in ArmorSlot:
            name = f"{mat.value} {_SLOT_LABELS[slot]}"
            pieces[name] = {
                "slot": slot,
                "material": mat,
                "defense_pct": defense_pct,
                "durability": durability,
                "color": color,
            }
    return pieces


ARMOR_PIECES: dict[str, dict] = _build_armor_pieces()


# ---------------------------------------------------------------------------
# ACCESSORY_PIECES — rings and amulets (no durability)
# ---------------------------------------------------------------------------

ACCESSORY_PIECES: dict[str, dict] = {
    "Iron Ring": {
        "slot": AccessorySlot.RING1,  # compatible with both ring slots
        "effect": AccessoryEffect.XP_BOOST,
        "effect_value": 0.20,
        "color": (186, 176, 166),
        "label": "+20% XP",
    },
    "Gold Ring": {
        "slot": AccessorySlot.RING1,
        "effect": AccessoryEffect.SPEED_BOOST,
        "effect_value": 0.15,
        "color": (230, 200, 60),
        "label": "+15% Speed",
    },
    "Diamond Ring": {
        "slot": AccessorySlot.RING1,
        "effect": AccessoryEffect.DAMAGE_BOOST,
        "effect_value": 0.20,
        "color": (90, 210, 240),
        "label": "+20% Damage",
    },
    "Coral Amulet": {
        "slot": AccessorySlot.AMULET,
        "effect": AccessoryEffect.HP_BOOST,
        "effect_value": 30.0,
        "color": (240, 120, 130),
        "label": "+30 Max HP",
    },
    "Ancient Amulet": {
        "slot": AccessorySlot.AMULET,
        "effect": AccessoryEffect.XP_BOOST,
        "effect_value": 0.40,
        "color": (140, 90, 200),
        "label": "+40% XP",
    },
}

# Canonical slot order used by equipment menus
ARMOR_SLOT_ORDER: list[str] = [
    ArmorSlot.HELMET.value,
    ArmorSlot.CHEST.value,
    ArmorSlot.LEGS.value,
    ArmorSlot.BOOTS.value,
    AccessorySlot.RING1.value,
    AccessorySlot.RING2.value,
    AccessorySlot.AMULET.value,
]

# Human-readable labels for each slot key
SLOT_LABELS: dict[str, str] = {
    ArmorSlot.HELMET.value: "Helmet",
    ArmorSlot.CHEST.value: "Chest",
    ArmorSlot.LEGS.value: "Legs",
    ArmorSlot.BOOTS.value: "Boots",
    AccessorySlot.RING1.value: "Ring 1",
    AccessorySlot.RING2.value: "Ring 2",
    AccessorySlot.AMULET.value: "Amulet",
}


def item_fits_slot(item_name: str, slot_key: str) -> bool:
    """Return True if *item_name* can be equipped in *slot_key*.

    Armor pieces must exactly match their predefined slot.
    Accessories (rings and amulet) fit either ring slot or the amulet slot.
    """
    if item_name in ARMOR_PIECES:
        return ARMOR_PIECES[item_name]["slot"].value == slot_key
    if item_name in ACCESSORY_PIECES:
        acc_slot = ACCESSORY_PIECES[item_name]["slot"]
        # Rings fit ring1 or ring2; amulets fit amulet only
        if acc_slot == AccessorySlot.AMULET:
            return slot_key == AccessorySlot.AMULET.value
        # Ring items fit any ring slot
        return slot_key in (AccessorySlot.RING1.value, AccessorySlot.RING2.value)
    return False
