"""Tests for InventoryRenderer (src/ui/inventory_renderer.py)."""

from __future__ import annotations

import pygame

from src.ui.inventory_renderer import InventoryRenderer
from src.ui.inventory import InventoryTab, InventoryState
from tests.conftest import MockGame


# ---------------------------------------------------------------------------
# Construction & initial state
# ---------------------------------------------------------------------------


def test_construction(mock_game: MockGame) -> None:
    renderer = InventoryRenderer(mock_game)
    assert not renderer.is_open(1)
    assert not renderer.is_open(2)
    assert renderer._icon_cache == {}


def test_toggle_opens_and_closes(mock_game: MockGame) -> None:
    renderer = InventoryRenderer(mock_game)
    renderer.toggle(1)
    assert renderer.is_open(1)
    assert not renderer.is_open(2)
    renderer.toggle(1)
    assert not renderer.is_open(1)


def test_toggle_resets_state(mock_game: MockGame) -> None:
    renderer = InventoryRenderer(mock_game)
    renderer.toggle(1)
    state = renderer._ui[1]
    state.grid_idx = 5
    state.tab = InventoryTab.RECIPES
    # Close and reopen — should reset
    renderer.toggle(1)
    renderer.toggle(1)
    assert renderer._ui[1].grid_idx == 0
    assert renderer._ui[1].tab == InventoryTab.ARMOR


def test_open_to_tab(mock_game: MockGame) -> None:
    renderer = InventoryRenderer(mock_game)
    renderer.open_to_tab(2, InventoryTab.RECIPES)
    assert renderer.is_open(2)
    assert renderer._ui[2].tab == InventoryTab.RECIPES


def test_close(mock_game: MockGame) -> None:
    renderer = InventoryRenderer(mock_game)
    renderer.toggle(1)
    assert renderer.is_open(1)
    renderer.close(1)
    assert not renderer.is_open(1)


# ---------------------------------------------------------------------------
# Input handling
# ---------------------------------------------------------------------------


def test_escape_closes_inventory(mock_game: MockGame) -> None:
    renderer = InventoryRenderer(mock_game)
    renderer.toggle(1)
    assert renderer.is_open(1)
    renderer.handle_input(pygame.K_ESCAPE, mock_game.player1)
    assert not renderer.is_open(1)


def test_equip_key_closes_inventory(mock_game: MockGame) -> None:
    renderer = InventoryRenderer(mock_game)
    renderer.toggle(1)
    assert renderer.is_open(1)
    equip_key = mock_game.player1.controls.equip_key
    renderer.handle_input(equip_key, mock_game.player1)
    assert not renderer.is_open(1)


def test_tab_switch_forward(mock_game: MockGame) -> None:
    renderer = InventoryRenderer(mock_game)
    renderer.toggle(1)
    assert renderer._ui[1].tab == InventoryTab.ARMOR
    # P1 next tab = X
    renderer.handle_input(pygame.K_x, mock_game.player1)
    assert renderer._ui[1].tab == InventoryTab.WEAPONS


def test_tab_switch_backward(mock_game: MockGame) -> None:
    renderer = InventoryRenderer(mock_game)
    renderer.toggle(1)
    assert renderer._ui[1].tab == InventoryTab.ARMOR
    # P1 prev tab = Z
    renderer.handle_input(pygame.K_z, mock_game.player1)
    assert renderer._ui[1].tab == InventoryTab.RECIPES  # wraps around


def test_doll_focus_navigation(mock_game: MockGame) -> None:
    renderer = InventoryRenderer(mock_game)
    renderer.toggle(1)
    state = renderer._ui[1]
    # Move left to enter doll
    renderer.handle_input(pygame.K_a, mock_game.player1)  # left
    assert state.doll_focus is True
    # Move right to exit doll
    renderer.handle_input(pygame.K_d, mock_game.player1)  # right
    assert state.doll_focus is False


# ---------------------------------------------------------------------------
# Drawing (smoke — just make sure it doesn't crash)
# ---------------------------------------------------------------------------


def test_draw_does_not_crash(mock_game: MockGame) -> None:
    renderer = InventoryRenderer(mock_game)
    renderer.toggle(1)
    # Should not raise
    renderer.draw(
        mock_game.player1,
        screen_x=0,
        screen_y=0,
        view_w=mock_game.viewport_w,
        view_h=mock_game.viewport_h,
    )


def test_draw_with_message(mock_game: MockGame) -> None:
    renderer = InventoryRenderer(mock_game)
    renderer.toggle(1)
    renderer._ui[1].message = "Test message"
    renderer._ui[1].message_timer = 2.0
    renderer.draw(
        mock_game.player1,
        screen_x=0,
        screen_y=0,
        view_w=mock_game.viewport_w,
        view_h=mock_game.viewport_h,
    )


# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------


def test_layout_constants() -> None:
    assert InventoryRenderer.DOLL_W == 280
    assert InventoryRenderer.CELL == 72
    assert InventoryRenderer.GAP == 5
    assert InventoryRenderer.COLS == 8
    assert InventoryRenderer.TAB_H == 68
    assert InventoryRenderer.TOOLTIP_H == 165
    assert InventoryRenderer.SLOT_SZ == 40


# ---------------------------------------------------------------------------
# Icon cache
# ---------------------------------------------------------------------------


def test_icon_cache_returns_none_for_missing(mock_game: MockGame) -> None:
    renderer = InventoryRenderer(mock_game)
    # No sprites loaded — should return None, not crash
    assert renderer.get_icon("nonexistent_sprite", 40) is None
