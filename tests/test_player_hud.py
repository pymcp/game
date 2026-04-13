"""Unit tests for PlayerHUD (src/ui/player_hud.py)."""

from __future__ import annotations

import pygame
import pytest

from src.ui.player_hud import PlayerHUD, _get_settlement_tier
from tests.conftest import MockGame


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_hud(game: MockGame) -> PlayerHUD:
    return PlayerHUD(game)


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestInit:
    def test_creates_without_error(self, mock_game: MockGame) -> None:
        hud = _make_hud(mock_game)
        assert hud.game is mock_game


# ---------------------------------------------------------------------------
# draw (integration — no crash)
# ---------------------------------------------------------------------------


class TestDraw:
    def test_draw_no_crash(self, mock_game: MockGame, player1) -> None:
        hud = _make_hud(mock_game)
        hud.draw(player1, 0, 0, 320, 360)

    def test_draw_player2(self, mock_game: MockGame, player2) -> None:
        hud = _make_hud(mock_game)
        hud.draw(player2, 320, 0, 320, 360)

    def test_draw_with_sign_active(self, mock_game: MockGame, player1) -> None:
        mock_game._sign_display[1] = {"text": "Hello\nWorld", "timer": 3.0}
        hud = _make_hud(mock_game)
        hud.draw(player1, 0, 0, 320, 360)

    def test_draw_with_sky_anim_ascend(self, mock_game: MockGame, player1) -> None:
        mock_game._sky_anim[1] = {"phase": "ascend", "progress": 0.5}
        hud = _make_hud(mock_game)
        hud.draw(player1, 0, 0, 320, 360)

    def test_draw_with_sky_anim_descend(self, mock_game: MockGame, player1) -> None:
        mock_game._sky_anim[1] = {"phase": "descend", "progress": 0.5}
        hud = _make_hud(mock_game)
        hud.draw(player1, 0, 0, 320, 360)

    def test_draw_with_sky_anim_phase_sky_skipped(
        self, mock_game: MockGame, player1
    ) -> None:
        mock_game._sky_anim[1] = {"phase": "sky", "progress": 0.5}
        hud = _make_hud(mock_game)
        # Phase "sky" should not draw overlay — no crash
        hud.draw(player1, 0, 0, 320, 360)


# ---------------------------------------------------------------------------
# Sector minimap
# ---------------------------------------------------------------------------


class TestSectorMinimap:
    def test_minimap_draws_on_overland(self, mock_game: MockGame, player1) -> None:
        hud = _make_hud(mock_game)
        # Player is on "overland" so minimap should render (no crash)
        hud._draw_sector_minimap(player1, 0, 0, 320, 360)

    def test_minimap_hidden_underground(self, mock_game: MockGame, player1) -> None:
        player1.current_map = ("cave", 5, 10, 0)
        hud = _make_hud(mock_game)
        # Should return early (no crash, no render)
        hud._draw_sector_minimap(player1, 0, 0, 320, 360)

    def test_minimap_with_visited_sectors(
        self, mock_game: MockGame, player1
    ) -> None:
        mock_game.visited_sectors.update({(1, 0), (-1, 0), (0, 1)})
        mock_game.land_sectors.add((1, 0))
        hud = _make_hud(mock_game)
        hud._draw_sector_minimap(player1, 0, 0, 320, 360)

    def test_minimap_with_sky_revealed(
        self, mock_game: MockGame, player1
    ) -> None:
        mock_game.sky_revealed_sectors.add((2, 2))
        hud = _make_hud(mock_game)
        hud._draw_sector_minimap(player1, 0, 0, 320, 360)


# ---------------------------------------------------------------------------
# Interaction hints
# ---------------------------------------------------------------------------


class TestInteractionHints:
    def test_hints_no_crash(self, mock_game: MockGame, player1) -> None:
        hud = _make_hud(mock_game)
        hud._draw_interaction_hints(player1, 0, 0, 320, 360)

    def test_hints_no_map_returns_early(
        self, mock_game: MockGame, player1
    ) -> None:
        player1.current_map = "nonexistent"
        hud = _make_hud(mock_game)
        # Should return early without error
        hud._draw_interaction_hints(player1, 0, 0, 320, 360)


# ---------------------------------------------------------------------------
# Sign display
# ---------------------------------------------------------------------------


class TestSignDisplay:
    def test_no_sign_no_crash(self, mock_game: MockGame, player1) -> None:
        hud = _make_hud(mock_game)
        hud._draw_sign_display(player1, 0, 0, 320, 360)

    def test_active_sign_renders(self, mock_game: MockGame, player1) -> None:
        mock_game._sign_display[1] = {"text": "Welcome!\nTo the village", "timer": 5.0}
        hud = _make_hud(mock_game)
        hud._draw_sign_display(player1, 0, 0, 320, 360)


# ---------------------------------------------------------------------------
# Sky anim overlay
# ---------------------------------------------------------------------------


class TestSkyAnimOverlay:
    def test_no_anim_no_crash(self, mock_game: MockGame, player1) -> None:
        hud = _make_hud(mock_game)
        hud._draw_sky_anim_overlay(player1, 0, 0, 320, 360)

    def test_ascend_overlay(self, mock_game: MockGame, player1) -> None:
        mock_game._sky_anim[1] = {"phase": "ascend", "progress": 0.8}
        hud = _make_hud(mock_game)
        hud._draw_sky_anim_overlay(player1, 0, 0, 320, 360)

    def test_descend_overlay(self, mock_game: MockGame, player1) -> None:
        mock_game._sky_anim[1] = {"phase": "descend", "progress": 0.3}
        hud = _make_hud(mock_game)
        hud._draw_sky_anim_overlay(player1, 0, 0, 320, 360)

    def test_zero_progress_no_crash(self, mock_game: MockGame, player1) -> None:
        mock_game._sky_anim[1] = {"phase": "ascend", "progress": 0.0}
        hud = _make_hud(mock_game)
        hud._draw_sky_anim_overlay(player1, 0, 0, 320, 360)


# ---------------------------------------------------------------------------
# _get_settlement_tier helper
# ---------------------------------------------------------------------------


class TestGetSettlementTier:
    def test_single_house(self) -> None:
        idx, name = _get_settlement_tier(1)
        assert isinstance(idx, int)
        assert isinstance(name, str)

    def test_large_cluster(self) -> None:
        idx, name = _get_settlement_tier(100)
        assert idx >= 0
        assert len(name) > 0
