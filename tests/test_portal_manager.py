"""Tests for PortalManager (extracted from game.py)."""

from __future__ import annotations

import pytest
from types import SimpleNamespace

from src.config import (
    TILE,
    GRASS,
    PORTAL_RUINS,
    PORTAL_ACTIVE,
    ANCIENT_STONE,
    PORTAL_FLOOR,
    PORTAL_WALL,
    TREASURE_CHEST,
    PORTAL_WARP_DURATION,
)
from src.data import PortalQuestType
from src.world.portal_manager import PortalManager
from src.world.map import GameMap

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_game(mock_game):
    """Extend the conftest mock_game with portal-specific state."""
    return mock_game


def _make_grass_map(rows: int = 30, cols: int = 30) -> GameMap:
    """Create a simple GameMap filled with GRASS."""
    world = [[GRASS] * cols for _ in range(rows)]
    gm = GameMap(world, tileset="overland")
    return gm


# ---------------------------------------------------------------------------
# Quest assignment
# ---------------------------------------------------------------------------


class TestAssignPortalQuest:
    def test_assigns_quest_to_portal_quests(self, mock_game: object) -> None:
        pm = mock_game.portals
        quest = pm.assign_portal_quest("overland")
        assert "overland" in pm.portal_quests
        assert quest is pm.portal_quests["overland"]

    def test_quest_has_required_keys(self, mock_game: object) -> None:
        pm = mock_game.portals
        quest = pm.assign_portal_quest("overland")
        assert "type" in quest
        assert "restored" in quest
        assert quest["restored"] is False
        assert isinstance(quest["type"], PortalQuestType)

    def test_deterministic_same_seed(self, mock_game: object) -> None:
        """Same world_seed + map_key → same quest type."""
        pm = mock_game.portals
        q1 = pm.assign_portal_quest(("sector", 3, 4))
        qt1 = q1["type"]
        # Reset and reassign
        pm.portal_quests.clear()
        q2 = pm.assign_portal_quest(("sector", 3, 4))
        assert q2["type"] == qt1

    def test_different_keys_can_differ(self, mock_game: object) -> None:
        """Different map keys MAY produce different quest types (probabilistic)."""
        pm = mock_game.portals
        types = set()
        for i in range(20):
            key = ("sector", i, 0)
            q = pm.assign_portal_quest(key)
            types.add(q["type"])
        assert len(types) >= 2  # at least two different quest types across 20 keys

    def test_ritual_quest_has_stones(self, mock_game: object) -> None:
        pm = mock_game.portals
        # Force a ritual quest by trying many keys
        for i in range(100):
            key = ("sector", i, 99)
            q = pm.assign_portal_quest(key)
            if q["type"] == PortalQuestType.RITUAL:
                assert q["stones_total"] == 4
                assert q["stones_activated"] == 0
                return
        pytest.skip("No ritual quest produced in 100 tries")

    def test_gather_quest_has_required(self, mock_game: object) -> None:
        pm = mock_game.portals
        for i in range(100):
            key = ("sector", i, 98)
            q = pm.assign_portal_quest(key)
            if q["type"] == PortalQuestType.GATHER:
                assert "required" in q
                assert "Gold" in q["required"]
                assert "Diamond" in q["required"]
                return
        pytest.skip("No gather quest produced in 100 tries")

    def test_combat_quest_has_guardian_flags(self, mock_game: object) -> None:
        pm = mock_game.portals
        for i in range(100):
            key = ("sector", i, 97)
            q = pm.assign_portal_quest(key)
            if q["type"] == PortalQuestType.COMBAT:
                assert q["guardian_defeated"] is False
                assert q["guardian_spawned"] is False
                return
        pytest.skip("No combat quest produced in 100 tries")

    def test_backward_compat_alias(self, mock_game: object) -> None:
        """portal_quests on game is the SAME dict as portals.portal_quests."""
        pm = mock_game.portals
        pm.assign_portal_quest("overland")
        assert mock_game.portal_quests is pm.portal_quests
        assert "overland" in mock_game.portal_quests


# ---------------------------------------------------------------------------
# Map placement
# ---------------------------------------------------------------------------


class TestPlacePortalOnMap:
    def test_places_portal_ruins(self, mock_game: object) -> None:
        pm = mock_game.portals
        gm = _make_grass_map()
        pm.assign_portal_quest("test_key")
        pm.place_portal_on_map(gm, "test_key")
        assert hasattr(gm, "portal_col")
        assert hasattr(gm, "portal_row")
        tile = gm.get_tile(gm.portal_row, gm.portal_col)
        assert tile in (PORTAL_RUINS, PORTAL_ACTIVE)

    def test_restored_quest_places_active(self, mock_game: object) -> None:
        pm = mock_game.portals
        pm.assign_portal_quest("test_key")
        pm.portal_quests["test_key"]["restored"] = True
        gm = _make_grass_map()
        pm.place_portal_on_map(gm, "test_key")
        tile = gm.get_tile(gm.portal_row, gm.portal_col)
        assert tile == PORTAL_ACTIVE

    def test_no_quest_no_placement(self, mock_game: object) -> None:
        pm = mock_game.portals
        gm = _make_grass_map()
        pm.place_portal_on_map(gm, "no_quest_key")
        assert not hasattr(gm, "portal_col")

    def test_ritual_places_stones(self, mock_game: object) -> None:
        pm = mock_game.portals
        for i in range(100):
            key = ("sector", i, 50)
            q = pm.assign_portal_quest(key)
            if q["type"] == PortalQuestType.RITUAL:
                gm = _make_grass_map(40, 40)
                pm.place_portal_on_map(gm, key)
                assert hasattr(gm, "ritual_stone_positions")
                assert len(gm.ritual_stone_positions) > 0
                return
        pytest.skip("No ritual quest produced")


# ---------------------------------------------------------------------------
# Check portal restored
# ---------------------------------------------------------------------------


class TestCheckPortalRestored:
    def test_no_quest_returns_false(self, mock_game: object) -> None:
        pm = mock_game.portals
        assert pm.check_portal_restored("nonexistent") is False

    def test_already_restored_returns_true(self, mock_game: object) -> None:
        pm = mock_game.portals
        pm.assign_portal_quest("k")
        pm.portal_quests["k"]["restored"] = True
        assert pm.check_portal_restored("k") is True

    def test_ritual_complete_restores(self, mock_game: object) -> None:
        pm = mock_game.portals
        for i in range(100):
            key = ("sector", i, 40)
            q = pm.assign_portal_quest(key)
            if q["type"] == PortalQuestType.RITUAL:
                q["stones_activated"] = q["stones_total"]
                assert pm.check_portal_restored(key) is True
                assert q["restored"] is True
                return
        pytest.skip("No ritual quest")

    def test_combat_defeated_restores(self, mock_game: object) -> None:
        pm = mock_game.portals
        for i in range(100):
            key = ("sector", i, 41)
            q = pm.assign_portal_quest(key)
            if q["type"] == PortalQuestType.COMBAT:
                q["guardian_defeated"] = True
                assert pm.check_portal_restored(key) is True
                assert q["restored"] is True
                return
        pytest.skip("No combat quest")

    def test_incomplete_ritual_not_restored(self, mock_game: object) -> None:
        pm = mock_game.portals
        for i in range(100):
            key = ("sector", i, 42)
            q = pm.assign_portal_quest(key)
            if q["type"] == PortalQuestType.RITUAL:
                q["stones_activated"] = 1
                assert pm.check_portal_restored(key) is False
                assert q["restored"] is False
                return
        pytest.skip("No ritual quest")


# ---------------------------------------------------------------------------
# On sentinel defeated
# ---------------------------------------------------------------------------


class TestOnSentinelDefeated:
    def test_non_combat_quest_noop(self, mock_game: object) -> None:
        pm = mock_game.portals
        for i in range(100):
            key = ("sector", i, 30)
            q = pm.assign_portal_quest(key)
            if q["type"] != PortalQuestType.COMBAT:
                pm.on_sentinel_defeated(key)
                assert q["restored"] is False
                return
        pytest.skip("All quests were combat type")

    def test_combat_quest_marks_defeated(self, mock_game: object) -> None:
        pm = mock_game.portals
        for i in range(100):
            key = ("sector", i, 31)
            q = pm.assign_portal_quest(key)
            if q["type"] == PortalQuestType.COMBAT:
                pm.on_sentinel_defeated(key)
                assert q["guardian_defeated"] is True
                assert q["restored"] is True
                return
        pytest.skip("No combat quest")


# ---------------------------------------------------------------------------
# Debug force portal
# ---------------------------------------------------------------------------


class TestDebugForcePortal:
    def test_force_completes_quest(self, mock_game: object) -> None:
        pm = mock_game.portals
        gm = _make_grass_map()
        pm.debug_force_portal_on_map("overland", gm)
        assert "overland" in pm.portal_quests
        assert pm.portal_quests["overland"]["restored"] is True


# ---------------------------------------------------------------------------
# Portal warp tick
# ---------------------------------------------------------------------------


class TestTickWarp:
    def test_warp_progresses(self, mock_game: object) -> None:
        pm = mock_game.portals
        pm.portal_warp[1] = {"progress": 0.0, "switched": True}
        pm.tick_warp(PORTAL_WARP_DURATION / 2)
        assert abs(pm.portal_warp[1]["progress"] - 0.5) < 0.01

    def test_warp_completes_and_removes(self, mock_game: object) -> None:
        pm = mock_game.portals
        pm.portal_warp[1] = {"progress": 0.0, "switched": True}
        pm.tick_warp(PORTAL_WARP_DURATION * 1.1)
        assert 1 not in pm.portal_warp

    def test_multiple_warps_independent(self, mock_game: object) -> None:
        pm = mock_game.portals
        pm.portal_warp[1] = {"progress": 0.0, "switched": True}
        pm.portal_warp[2] = {"progress": 0.5, "switched": True}
        pm.tick_warp(PORTAL_WARP_DURATION * 0.6)
        assert 1 in pm.portal_warp  # only 0.6 progress
        assert 2 not in pm.portal_warp  # 0.5 + 0.6 >= 1.0

    def test_deferred_switch_at_midpoint(self, mock_game: object) -> None:
        """Pending transition executes when progress crosses 0.5."""
        pm = mock_game.portals
        player = mock_game.player1
        player.current_map = "overland"
        pm.portal_warp[1] = {
            "progress": 0.0,
            "switched": False,
            "pending": {
                "pid": 1,
                "current_map": "portal_realm",
                "x": 100.0,
                "y": 200.0,
                "portal_origin_map": "overland",
                "clear_portal_origin": False,
                "float_text": "Entered portal realm!",
                "float_color": (160, 60, 220),
            },
        }
        # Tick to just before midpoint
        pm.tick_warp(PORTAL_WARP_DURATION * 0.4)
        assert player.current_map == "overland"
        assert not pm.portal_warp[1]["switched"]
        # Tick past midpoint
        pm.tick_warp(PORTAL_WARP_DURATION * 0.2)
        assert player.current_map == "portal_realm"
        assert pm.portal_warp[1]["switched"]
        assert player.x == 100.0
        assert player.y == 200.0


# ---------------------------------------------------------------------------
# Try interact portal ruins
# ---------------------------------------------------------------------------


class TestTryInteractPortalRuins:
    def test_no_quest_shows_text(self, mock_game: object) -> None:
        pm = mock_game.portals
        player = mock_game.player1
        player.x = 100.0
        player.y = 100.0
        player.current_map = "some_key"
        pm.try_interact_portal_ruins(player, "some_key")
        assert len(mock_game._floats) == 1
        assert "Ancient portal" in mock_game._floats[0].text

    def test_restored_shows_active(self, mock_game: object) -> None:
        pm = mock_game.portals
        player = mock_game.player1
        player.x = 100.0
        player.y = 100.0
        player.current_map = "k"
        pm.assign_portal_quest("k")
        pm.portal_quests["k"]["restored"] = True
        pm.try_interact_portal_ruins(player, "k")
        assert any("active" in f.text.lower() for f in mock_game._floats)


# ---------------------------------------------------------------------------
# Try activate ritual stone
# ---------------------------------------------------------------------------


class TestTryActivateRitualStone:
    def _setup_ritual(self, mock_game: object) -> tuple:
        """Find or force a ritual quest and return (pm, quest, key, gm)."""
        pm = mock_game.portals
        for i in range(100):
            key = ("sector", i, 60)
            q = pm.assign_portal_quest(key)
            if q["type"] == PortalQuestType.RITUAL:
                gm = _make_grass_map(40, 40)
                pm.place_portal_on_map(gm, key)
                return pm, q, key, gm
        pytest.skip("No ritual quest produced")

    def test_correct_stone_advances(self, mock_game: object) -> None:
        pm, quest, key, gm = self._setup_ritual(mock_game)
        player = mock_game.player1
        player.current_map = key
        positions = gm.ritual_stone_positions
        assert len(positions) > 0
        col, row = positions[0]
        pm.try_activate_ritual_stone(player, gm, col, row)
        assert quest["stones_activated"] == 1

    def test_wrong_stone_doesnt_advance(self, mock_game: object) -> None:
        pm, quest, key, gm = self._setup_ritual(mock_game)
        player = mock_game.player1
        player.current_map = key
        positions = gm.ritual_stone_positions
        if len(positions) > 1:
            wrong_col, wrong_row = positions[1]
            pm.try_activate_ritual_stone(player, gm, wrong_col, wrong_row)
            assert quest["stones_activated"] == 0


# ---------------------------------------------------------------------------
# Backward compat alias
# ---------------------------------------------------------------------------


class TestBackwardCompat:
    def test_portal_warp_alias(self, mock_game: object) -> None:
        assert mock_game.portal_warp is mock_game.portals.portal_warp

    def test_portal_quests_alias(self, mock_game: object) -> None:
        assert mock_game.portal_quests is mock_game.portals.portal_quests

    def test_mutation_through_alias(self, mock_game: object) -> None:
        mock_game.portals.assign_portal_quest("test_bc")
        assert "test_bc" in mock_game.portal_quests
