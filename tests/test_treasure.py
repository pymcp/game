"""Unit tests for TreasureManager (src/ui/treasure.py)."""

from __future__ import annotations

import pygame
import pytest

from src.ui.treasure import TreasureManager
from tests.conftest import MockGame

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_treasure(game: MockGame) -> TreasureManager:
    """Create a TreasureManager wired to *game*."""
    tm = TreasureManager(game)
    # Mirror the backward-compat alias the real Game.__init__ would set.
    game.treasure_reveals = tm.reveals
    return tm


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------


class TestInit:
    def test_starts_with_no_reveals(self, mock_game: MockGame) -> None:
        tm = _make_treasure(mock_game)
        assert tm.reveals == []

    def test_backward_compat_alias(self, mock_game: MockGame) -> None:
        tm = _make_treasure(mock_game)
        assert mock_game.treasure_reveals is tm.reveals


# ---------------------------------------------------------------------------
# open_chest
# ---------------------------------------------------------------------------


class TestOpenChest:
    def test_always_grants_sail(self, mock_game: MockGame, player1) -> None:
        tm = _make_treasure(mock_game)
        tm.open_chest(player1, 100, 100)
        assert player1.inventory.get("Sail", 0) >= 1

    def test_loot_added_to_inventory(self, mock_game: MockGame, player1) -> None:
        tm = _make_treasure(mock_game)
        tm.open_chest(player1, 100, 100)
        # At least Sail + one bonus item
        assert len(player1.inventory) >= 2

    def test_reveal_popup_queued(self, mock_game: MockGame, player1) -> None:
        tm = _make_treasure(mock_game)
        tm.open_chest(player1, 100, 100)
        assert len(tm.reveals) == 1
        reveal = tm.reveals[0]
        assert reveal["player_id"] == 1
        assert reveal["timer"] == 180.0
        assert "Sail" in reveal["items"]

    def test_particles_spawned(self, mock_game: MockGame, player1) -> None:
        tm = _make_treasure(mock_game)
        tm.open_chest(player1, 100, 100)
        # 55 sparkle + 12 lid = 67 total
        assert len(mock_game._particles) == 67

    def test_multiple_chests_queue_multiple_reveals(
        self, mock_game: MockGame, player1, player2
    ) -> None:
        tm = _make_treasure(mock_game)
        tm.open_chest(player1, 100, 100)
        tm.open_chest(player2, 200, 200)
        assert len(tm.reveals) == 2
        pids = {r["player_id"] for r in tm.reveals}
        assert pids == {1, 2}


# ---------------------------------------------------------------------------
# tick
# ---------------------------------------------------------------------------


class TestTick:
    def test_timer_decrements(self, mock_game: MockGame, player1) -> None:
        tm = _make_treasure(mock_game)
        tm.open_chest(player1, 100, 100)
        tm.tick(1.0)
        assert tm.reveals[0]["timer"] == 179.0

    def test_expired_reveals_culled(self, mock_game: MockGame, player1) -> None:
        tm = _make_treasure(mock_game)
        tm.open_chest(player1, 100, 100)
        tm.tick(180.0)
        assert len(tm.reveals) == 0

    def test_partial_cull(self, mock_game: MockGame, player1, player2) -> None:
        tm = _make_treasure(mock_game)
        tm.open_chest(player1, 100, 100)
        tm.open_chest(player2, 200, 200)
        # Manually reduce P1's timer almost to 0
        tm.reveals[0]["timer"] = 1.0
        tm.tick(1.0)
        # P1's reveal expired, P2's remains
        assert len(tm.reveals) == 1
        assert tm.reveals[0]["player_id"] == 2

    def test_backward_compat_alias_stays_in_sync(
        self, mock_game: MockGame, player1
    ) -> None:
        tm = _make_treasure(mock_game)
        tm.open_chest(player1, 100, 100)
        assert len(mock_game.treasure_reveals) == 1
        tm.tick(180.0)
        # The slice-assignment keeps the same list object
        assert mock_game.treasure_reveals is tm.reveals
        assert len(mock_game.treasure_reveals) == 0

    def test_tick_with_no_reveals_is_noop(self, mock_game: MockGame) -> None:
        tm = _make_treasure(mock_game)
        tm.tick(1.0)  # should not raise
        assert tm.reveals == []


# ---------------------------------------------------------------------------
# draw
# ---------------------------------------------------------------------------


class TestDraw:
    def test_draw_no_reveal_does_nothing(self, mock_game: MockGame, player1) -> None:
        tm = _make_treasure(mock_game)
        # Should not raise
        tm.draw(player1, 0, 0, 320, 360)

    def test_draw_with_active_reveal_renders(
        self, mock_game: MockGame, player1
    ) -> None:
        tm = _make_treasure(mock_game)
        tm.open_chest(player1, 100, 100)
        # Should not raise – renders onto mock_game.screen
        tm.draw(player1, 0, 0, 320, 360)
