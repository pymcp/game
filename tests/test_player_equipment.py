"""Unit tests for Player equipment: equip, unequip, durability, and cycle_weapon."""

from __future__ import annotations

import pytest

from src.data.armor import ARMOR_PIECES, ACCESSORY_PIECES, ArmorSlot
from src.entities.player import Player, CONTROL_SCHEME_PLAYER1


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_IRON_HELMET = "Iron Helmet"
_IRON_CHEST = "Iron Chest"
_IRON_LEGS = "Iron Legs"
_IRON_BOOTS = "Iron Boots"
_STONE_HELMET = "Stone Helmet"


def _player_with_item(item_name: str, qty: int = 1) -> Player:
    """Return a fresh Player with *qty* of *item_name* in inventory."""
    p = Player(320.0, 320.0, player_id=1, control_scheme=CONTROL_SCHEME_PLAYER1)
    p.inventory[item_name] = qty
    return p


# ---------------------------------------------------------------------------
# equip_item
# ---------------------------------------------------------------------------


class TestEquipItem:
    def test_equip_armor_reduces_inventory(self) -> None:
        p = _player_with_item(_IRON_HELMET)
        result = p.equip_item("helmet", _IRON_HELMET)
        assert result is True
        assert p.inventory.get(_IRON_HELMET, 0) == 0
        assert p.equipment["helmet"] == _IRON_HELMET

    def test_equip_requires_item_in_inventory(self) -> None:
        p = Player(320.0, 320.0, player_id=1, control_scheme=CONTROL_SCHEME_PLAYER1)
        result = p.equip_item("helmet", _IRON_HELMET)
        assert result is False
        assert p.equipment.get("helmet") is None

    def test_equip_wrong_slot_fails(self) -> None:
        p = _player_with_item(_IRON_HELMET)
        result = p.equip_item("chest", _IRON_HELMET)
        assert result is False
        assert p.inventory.get(_IRON_HELMET, 0) == 1

    def test_equip_sets_durability(self) -> None:
        p = _player_with_item(_IRON_HELMET)
        p.equip_item("helmet", _IRON_HELMET)
        expected = ARMOR_PIECES[_IRON_HELMET]["durability"]
        assert p.durability[_IRON_HELMET] == expected

    def test_equip_replaces_existing_item(self) -> None:
        p = _player_with_item(_IRON_HELMET)
        p.inventory[_STONE_HELMET] = 1
        p.equip_item("helmet", _STONE_HELMET)
        p.inventory[_IRON_HELMET] = 1
        p.equip_item("helmet", _IRON_HELMET)
        # Stone helmet should be returned to inventory
        assert p.inventory.get(_STONE_HELMET, 0) == 1
        assert p.equipment["helmet"] == _IRON_HELMET


# ---------------------------------------------------------------------------
# unequip_item
# ---------------------------------------------------------------------------


class TestUnequipItem:
    def test_unequip_returns_item_to_inventory(self) -> None:
        p = _player_with_item(_IRON_HELMET)
        p.equip_item("helmet", _IRON_HELMET)
        p.unequip_item("helmet")
        assert p.equipment.get("helmet") is None
        assert p.inventory.get(_IRON_HELMET, 0) == 1

    def test_unequip_empty_slot_is_safe(self) -> None:
        p = Player(320.0, 320.0, player_id=1, control_scheme=CONTROL_SCHEME_PLAYER1)
        # Should not raise
        p.unequip_item("helmet")

    def test_unequip_clears_durability(self) -> None:
        p = _player_with_item(_IRON_HELMET)
        p.equip_item("helmet", _IRON_HELMET)
        p.unequip_item("helmet")
        assert _IRON_HELMET not in p.durability

    def test_broken_armor_destroyed_on_unequip(self) -> None:
        p = _player_with_item(_IRON_HELMET)
        p.equip_item("helmet", _IRON_HELMET)
        # Manually zero the durability to simulate a broken piece
        p.durability[_IRON_HELMET] = 0
        p.unequip_item("helmet")
        # Item should NOT be returned to inventory
        assert p.inventory.get(_IRON_HELMET, 0) == 0
        assert p.equipment.get("helmet") is None


# ---------------------------------------------------------------------------
# Durability tick
# ---------------------------------------------------------------------------


class TestDurabilityTick:
    def test_durability_decrements(self) -> None:
        p = _player_with_item(_IRON_HELMET)
        p.equip_item("helmet", _IRON_HELMET)
        initial = p.durability[_IRON_HELMET]
        p._tick_durability(floats=[], map_key=None)
        assert p.durability[_IRON_HELMET] == initial - 1

    def test_broken_armor_auto_removed(self) -> None:
        p = _player_with_item(_IRON_HELMET)
        p.equip_item("helmet", _IRON_HELMET)
        # Set durability to 1 so next tick destroys it
        p.durability[_IRON_HELMET] = 1
        p._tick_durability(floats=[], map_key=None)
        assert p.equipment.get("helmet") is None
        assert _IRON_HELMET not in p.durability

    def test_broken_armor_not_returned_to_inventory(self) -> None:
        p = _player_with_item(_IRON_HELMET)
        p.equip_item("helmet", _IRON_HELMET)
        p.durability[_IRON_HELMET] = 1
        p._tick_durability(floats=[], map_key=None)
        assert p.inventory.get(_IRON_HELMET, 0) == 0

    def test_tick_only_affects_armor_slots(self) -> None:
        """Accessories (rings, amulets) have no durability — tick should not crash."""
        p = Player(320.0, 320.0, player_id=1, control_scheme=CONTROL_SCHEME_PLAYER1)
        p.inventory["Iron Ring"] = 1
        p.equip_item("ring1", "Iron Ring")
        # Should complete without raising
        p._tick_durability(floats=[], map_key=None)

    def test_multiple_pieces_tick_independently(self) -> None:
        p = Player(320.0, 320.0, player_id=1, control_scheme=CONTROL_SCHEME_PLAYER1)
        for item in (_IRON_HELMET, _IRON_CHEST):
            p.inventory[item] = 1
            slot = "helmet" if item == _IRON_HELMET else "chest"
            p.equip_item(slot, item)
        initial_helmet = p.durability[_IRON_HELMET]
        initial_chest = p.durability[_IRON_CHEST]
        p._tick_durability(floats=[], map_key=None)
        assert p.durability[_IRON_HELMET] == initial_helmet - 1
        assert p.durability[_IRON_CHEST] == initial_chest - 1


# ---------------------------------------------------------------------------
# cycle_weapon
# ---------------------------------------------------------------------------


class TestCycleWeapon:
    def test_cycle_with_single_weapon_is_noop(self) -> None:
        p = Player(320.0, 320.0, player_id=1, control_scheme=CONTROL_SCHEME_PLAYER1)
        assert len(p.unlocked_weapons) == 1
        original = p.weapon_id
        p.cycle_weapon()
        assert p.weapon_id == original

    def test_cycle_forward(self) -> None:
        p = Player(320.0, 320.0, player_id=1, control_scheme=CONTROL_SCHEME_PLAYER1)
        p.unlocked_weapons = ["sword", "arrow", "axe"]
        p.weapon_id = "sword"
        p.cycle_weapon(1)
        assert p.weapon_id == "arrow"

    def test_cycle_backward(self) -> None:
        p = Player(320.0, 320.0, player_id=1, control_scheme=CONTROL_SCHEME_PLAYER1)
        p.unlocked_weapons = ["sword", "arrow", "axe"]
        p.weapon_id = "sword"
        p.cycle_weapon(-1)
        assert p.weapon_id == "axe"

    def test_cycle_wraps_around(self) -> None:
        p = Player(320.0, 320.0, player_id=1, control_scheme=CONTROL_SCHEME_PLAYER1)
        p.unlocked_weapons = ["sword", "arrow"]
        p.weapon_id = "arrow"
        p.cycle_weapon(1)
        assert p.weapon_id == "sword"
