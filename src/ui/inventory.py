"""Inventory UI state and helpers.

Data-only module — no pygame imports.  All rendering happens in game.py
using the state objects defined here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.entities.player import Player

from src.data.armor import (
    ARMOR_PIECES,
    ACCESSORY_PIECES,
    AccessorySlot,
)
from src.data.weapons import WEAPONS, WEAPON_UNLOCK_COSTS
from src.data.pickaxes import PICKAXES, UPGRADE_COSTS
from src.data.recipes import RECIPES

# ---------------------------------------------------------------------------
# Tab enum
# ---------------------------------------------------------------------------


class InventoryTab(IntEnum):
    ARMOR = 0
    WEAPONS = 1
    PICKAXES = 2
    MATERIALS = 3
    ACCESSORIES = 4
    RECIPES = 5


TAB_LABELS: list[str] = [
    "Armor",
    "Weapons",
    "Pickaxes",
    "Materials",
    "Accessories",
    "Recipes",
]

TAB_SPRITE_IDS: list[str] = [
    "tab_armor",
    "tab_weapons",
    "tab_pickaxes",
    "tab_materials",
    "tab_accessories",
    "tab_recipes",
]

NUM_TABS: int = len(InventoryTab)


# ---------------------------------------------------------------------------
# Character doll layout
# ---------------------------------------------------------------------------

# 9 equippable slots in top-to-bottom navigation order.
DOLL_SLOTS: list[str] = [
    "helmet",
    "amulet",
    "chest",
    "ring1",
    "ring2",
    "legs",
    "boots",
    "weapon",
    "pickaxe",
]

# Top-left (x, y) of each 40×40 slot square, relative to the doll panel origin.
# The doll panel is 280 px wide; figure is centered on x=140.
DOLL_SLOT_POSITIONS: dict[str, tuple[int, int]] = {
    "helmet": (100, 68),
    "amulet": (100, 122),
    "chest": (100, 158),
    "ring1": (42, 163),
    "ring2": (198, 163),
    "legs": (100, 210),
    "boots": (100, 262),
    "weapon": (196, 210),
    "pickaxe": (44, 210),
}

# Slots that correspond to weapon / pickaxe progression (read-only on doll)
DOLL_VIRTUAL_SLOTS: frozenset[str] = frozenset({"weapon", "pickaxe"})

# Slot → which InventoryTab to jump to when the user presses confirm on a
# virtual doll slot.
DOLL_VIRTUAL_SLOT_TABS: dict[str, "InventoryTab"] = {
    "weapon": InventoryTab.WEAPONS,
    "pickaxe": InventoryTab.PICKAXES,
}


# ---------------------------------------------------------------------------
# Sprite ID helpers
# ---------------------------------------------------------------------------


def item_sprite_id(item_name: str) -> str:
    """Normalise an item name to its sprite registry key.

    Matches the filenames produced by tools/bake_item_sprites.py.
    """
    return item_name.lower().replace(" ", "_")


# ---------------------------------------------------------------------------
# Item sets (used for tab filtering)
# ---------------------------------------------------------------------------

_ALL_EQUIPPABLE: frozenset[str] = frozenset(
    list(ARMOR_PIECES.keys()) + list(ACCESSORY_PIECES.keys())
)


# ---------------------------------------------------------------------------
# State dataclass
# ---------------------------------------------------------------------------


@dataclass
class InventoryState:
    tab: InventoryTab = InventoryTab.ARMOR
    grid_idx: int = 0  # cursor position within the current tab's list
    doll_focus: bool = False  # True when navigating the character doll
    doll_slot_idx: int = 0  # index into DOLL_SLOTS
    scroll_offset: int = 0  # rows scrolled off the top of the grid
    # Ring-disambiguation sub-state
    ring_pick_item: str | None = None  # item being equipped (None = inactive)
    ring_pick_choice: int = 0  # 0 = replace ring1, 1 = replace ring2
    # Transient message shown in the tooltip area
    message: str = ""
    message_timer: float = 0.0


# ---------------------------------------------------------------------------
# Tab item list builder
# ---------------------------------------------------------------------------


def get_tab_items(player: "Player", tab: InventoryTab) -> list[dict]:
    """Return the display item list for *tab*.

    Each entry is a dict with at least:
      "type"  : str   — one of: armor | weapon | pickaxe | material | accessory | recipe
      "name"  : str   — display name
      "count" : int   — inventory quantity (0 for non-stackable rows)
    Plus type-specific fields documented below.
    """
    inv = player.inventory
    items: list[dict] = []

    if tab == InventoryTab.ARMOR:
        for name, data in ARMOR_PIECES.items():
            count = inv.get(name, 0)
            if count > 0:
                items.append(
                    {
                        "type": "armor",
                        "name": name,
                        "count": count,
                        "slot": data["slot"].value,
                        "defense_pct": data["defense_pct"],
                        "durability": data["durability"],
                        "color": data["color"],
                    }
                )

    elif tab == InventoryTab.WEAPONS:
        max_level = len(WEAPONS) - 1
        for i, wpn in enumerate(WEAPONS):
            is_current = i == player.weapon_level
            is_past = i < player.weapon_level
            # A weapon is upgradeable if it is the very next tier and the
            # player can afford the cost.
            if i == player.weapon_level + 1 and player.weapon_level < len(
                WEAPON_UNLOCK_COSTS
            ):
                cost = WEAPON_UNLOCK_COSTS[player.weapon_level]
                can_upgrade = all(inv.get(k, 0) >= v for k, v in cost.items())
                upgrade_cost: dict = cost
            else:
                can_upgrade = False
                upgrade_cost = {}
            is_locked = (i > player.weapon_level) and not can_upgrade
            items.append(
                {
                    "type": "weapon",
                    "name": wpn["name"],
                    "count": 0,
                    "level": i,
                    "is_current": is_current,
                    "is_past": is_past,
                    "is_locked": is_locked,
                    "can_upgrade": can_upgrade,
                    "upgrade_cost": upgrade_cost,
                    "weapon_data": wpn,
                }
            )

    elif tab == InventoryTab.PICKAXES:
        for i, pick in enumerate(PICKAXES):
            is_current = i == player.pick_level
            is_past = i < player.pick_level
            if i == player.pick_level + 1 and player.pick_level < len(UPGRADE_COSTS):
                cost = UPGRADE_COSTS[player.pick_level]
                can_upgrade = all(inv.get(k, 0) >= v for k, v in cost.items())
                upgrade_cost = cost
            else:
                can_upgrade = False
                upgrade_cost = {}
            is_locked = (i > player.pick_level) and not can_upgrade
            items.append(
                {
                    "type": "pickaxe",
                    "name": pick["name"],
                    "count": 0,
                    "level": i,
                    "is_current": is_current,
                    "is_past": is_past,
                    "is_locked": is_locked,
                    "can_upgrade": can_upgrade,
                    "upgrade_cost": upgrade_cost,
                    "pick_data": pick,
                }
            )

    elif tab == InventoryTab.MATERIALS:
        for name, count in sorted(inv.items()):
            if count > 0 and name not in _ALL_EQUIPPABLE:
                items.append(
                    {
                        "type": "material",
                        "name": name,
                        "count": count,
                    }
                )

    elif tab == InventoryTab.ACCESSORIES:
        for name, data in ACCESSORY_PIECES.items():
            count = inv.get(name, 0)
            if count > 0:
                items.append(
                    {
                        "type": "accessory",
                        "name": name,
                        "count": count,
                        "slot": data["slot"].value,
                        "label": data["label"],
                        "color": data["color"],
                    }
                )

    elif tab == InventoryTab.RECIPES:
        for recipe in RECIPES:
            can_afford = all(inv.get(k, 0) >= v for k, v in recipe["cost"].items())
            items.append(
                {
                    "type": "recipe",
                    "name": recipe["name"],
                    "count": 0,
                    "cost": recipe["cost"],
                    "result": recipe["result"],
                    "min_tier": recipe["min_tier"],
                    "can_afford": can_afford,
                }
            )

    return items


def auto_equip_slot(item: dict, player: "Player") -> str | None:
    """Return the best slot key for *item*, or None if no slot is available.

    For armor the slot is fixed.  For rings, prefers an empty ring slot;
    returns None to trigger ring-disambiguation if both are filled.
    """
    if item["type"] == "armor":
        return item["slot"]

    if item["type"] == "accessory":
        slot_val = item["slot"]
        # Rings can go in ring1 or ring2
        if slot_val in (AccessorySlot.RING1.value, AccessorySlot.RING2.value):
            if player.equipment.get("ring1") is None:
                return "ring1"
            if player.equipment.get("ring2") is None:
                return "ring2"
            return None  # both occupied → disambiguation needed
        # Amulet has only one slot
        return AccessorySlot.AMULET.value

    return None
