"""Unit tests for SectorManager (src/world/sector_manager.py)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pygame
import pytest

from src.config import TILE, BiomeType
from src.world.sector_manager import SectorManager
from src.entities.player import Player
from tests.conftest import MockGame

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_sm(game: MockGame) -> SectorManager:
    """Create a SectorManager wired to *game*."""
    return game.sectors


# ---------------------------------------------------------------------------
# Coordinate helpers
# ---------------------------------------------------------------------------


class TestGetPlayerSector:
    def test_overland_returns_origin(self, player1: Player) -> None:
        player1.current_map = "overland"
        assert SectorManager.get_player_sector(player1) == (0, 0)

    def test_sector_tuple_returns_coords(self, player1: Player) -> None:
        player1.current_map = ("sector", 3, -2)
        assert SectorManager.get_player_sector(player1) == (3, -2)

    def test_sector_0_0_tuple_returns_origin(self, player1: Player) -> None:
        player1.current_map = ("sector", 0, 0)
        assert SectorManager.get_player_sector(player1) == (0, 0)

    def test_cave_returns_none(self, player1: Player) -> None:
        player1.current_map = ("cave", 5, 10, 0)
        assert SectorManager.get_player_sector(player1) is None

    def test_housing_returns_none(self, player1: Player) -> None:
        player1.current_map = ("house", 3, 4)
        assert SectorManager.get_player_sector(player1) is None


class TestGetSectorCoords:
    def test_overland(self) -> None:
        assert SectorManager.get_sector_coords("overland") == (0, 0)

    def test_sector_tuple(self) -> None:
        assert SectorManager.get_sector_coords(("sector", 1, 2)) == (1, 2)

    def test_cave_returns_none(self) -> None:
        assert SectorManager.get_sector_coords(("cave", 5, 10, 0)) is None

    def test_arbitrary_string_returns_none(self) -> None:
        assert SectorManager.get_sector_coords("portal_realm") is None


# ---------------------------------------------------------------------------
# Biome / armor checks
# ---------------------------------------------------------------------------


class TestBiomeChecks:
    def test_standard_always_passes(self, player1: Player) -> None:
        assert SectorManager.check_biome_entry_armor(player1, BiomeType.STANDARD)

    def test_tundra_no_armor_fails(self, player1: Player) -> None:
        assert not SectorManager.check_biome_entry_armor(player1, BiomeType.TUNDRA)

    def test_tundra_one_piece_passes(self, player1: Player) -> None:
        player1.equipment["helmet"] = "Leather Helmet"
        assert SectorManager.check_biome_entry_armor(player1, BiomeType.TUNDRA)

    def test_volcano_partial_armor_fails(self, player1: Player) -> None:
        player1.equipment["helmet"] = "Leather Helmet"
        assert not SectorManager.check_biome_entry_armor(player1, BiomeType.VOLCANO)

    def test_volcano_full_armor_passes(self, player1: Player) -> None:
        for s in ["helmet", "chest", "legs", "boots"]:
            player1.equipment[s] = f"Leather {s.title()}"
        assert SectorManager.check_biome_entry_armor(player1, BiomeType.VOLCANO)


class TestHasAncientArmor:
    def test_no_armor_returns_false(self, player1: Player) -> None:
        assert not SectorManager.has_ancient_armor(player1)

    def test_non_ancient_returns_false(self, player1: Player) -> None:
        player1.equipment["helmet"] = "Leather Helmet"
        assert not SectorManager.has_ancient_armor(player1)

    def test_ancient_armor_returns_true(self, player1: Player) -> None:
        player1.equipment["helmet"] = "Ancient Helmet"
        assert SectorManager.has_ancient_armor(player1)


# ---------------------------------------------------------------------------
# Wipe tick
# ---------------------------------------------------------------------------


class TestTickWipe:
    def test_advances_progress(self, mock_game: MockGame) -> None:
        sm = _make_sm(mock_game)
        sm.sector_wipe[1] = {"progress": 0.0, "direction": "right"}
        sm.tick_wipe(1.0)
        assert sm.sector_wipe[1]["progress"] > 0.0

    def test_removes_when_complete(self, mock_game: MockGame) -> None:
        sm = _make_sm(mock_game)
        sm.sector_wipe[1] = {"progress": 0.99, "direction": "left"}
        sm.tick_wipe(100.0)  # large dt → completes
        assert 1 not in sm.sector_wipe

    def test_empty_wipe_is_noop(self, mock_game: MockGame) -> None:
        sm = _make_sm(mock_game)
        sm.tick_wipe(1.0)  # should not raise
        assert sm.sector_wipe == {}


# ---------------------------------------------------------------------------
# Biome damage tick
# ---------------------------------------------------------------------------


class TestTickBiomeDamage:
    def test_noop_when_no_warnings(self, mock_game: MockGame) -> None:
        sm = _make_sm(mock_game)
        sm.tick_biome_damage(1.0)  # should not raise

    def test_damage_applied_when_expired(
        self, mock_game: MockGame, player1: Player
    ) -> None:
        sm = _make_sm(mock_game)
        initial_hp = player1.hp
        sm._biome_warn_timers[1] = {"biome": BiomeType.TUNDRA, "frames": 1.0}
        sm.tick_biome_damage(1.0)
        # Player has no armor → should take damage
        assert player1.hp < initial_hp
        # Timer should be cleared
        assert sm._biome_warn_timers[1] is None

    def test_no_damage_if_armored(self, mock_game: MockGame, player1: Player) -> None:
        sm = _make_sm(mock_game)
        player1.equipment["helmet"] = "Leather Helmet"
        initial_hp = player1.hp
        sm._biome_warn_timers[1] = {"biome": BiomeType.TUNDRA, "frames": 1.0}
        sm.tick_biome_damage(1.0)
        # Player has armor → no damage
        assert player1.hp == initial_hp


# ---------------------------------------------------------------------------
# Draw sector wipe
# ---------------------------------------------------------------------------


class TestDrawSectorWipe:
    def test_draw_at_midpoint(self, mock_game: MockGame) -> None:
        sm = _make_sm(mock_game)
        sm.draw_sector_wipe_viewport(0, 0, 320, 360, 0.5)

    def test_draw_at_zero(self, mock_game: MockGame) -> None:
        sm = _make_sm(mock_game)
        sm.draw_sector_wipe_viewport(0, 0, 320, 360, 0.0)

    def test_draw_at_one(self, mock_game: MockGame) -> None:
        sm = _make_sm(mock_game)
        sm.draw_sector_wipe_viewport(0, 0, 320, 360, 1.0)


# ---------------------------------------------------------------------------
# Thumbnail generation
# ---------------------------------------------------------------------------


class TestThumbnail:
    def test_returns_none_for_unknown_sector(self, mock_game: MockGame) -> None:
        sm = _make_sm(mock_game)
        assert sm.generate_sector_thumbnail(99, 99) is None

    def test_caches_result(self, mock_game: MockGame) -> None:
        sm = _make_sm(mock_game)
        # Sector (0,0) maps to "overland" key but the thumbnail expects ("sector", 0, 0)
        # which is aliased to the overland scene
        thumb1 = sm.generate_sector_thumbnail(0, 0)
        thumb2 = sm.generate_sector_thumbnail(0, 0)
        assert thumb1 is thumb2
