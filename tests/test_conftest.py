"""Smoke tests for conftest fixtures — validates the test scaffolding works."""

from __future__ import annotations

from tests.conftest import MockGame
from src.world.scene import MapScene


def test_mock_game_has_scene(mock_game: MockGame) -> None:
    assert "overland" in mock_game.maps
    assert isinstance(mock_game.maps["overland"], MapScene)


def test_mock_game_players(mock_game: MockGame) -> None:
    assert mock_game.player1.player_id == 1
    assert mock_game.player2.player_id == 2
    assert mock_game.player1.current_map == "overland"


def test_mock_game_effect_routing(mock_game: MockGame) -> None:
    mock_game.floats.append("float1")
    mock_game.particles.append("particle1")
    assert mock_game._floats == ["float1"]
    assert mock_game._particles == ["particle1"]


def test_get_player_current_map(mock_game: MockGame) -> None:
    gmap = mock_game.get_player_current_map(mock_game.player1)
    assert gmap is not None
    assert gmap.tileset == "overland"


def test_is_in_housing_env(mock_game: MockGame) -> None:
    assert not mock_game._is_in_housing_env(mock_game.player1)
    mock_game.player1.current_map = ("house", 5, 5)
    assert mock_game._is_in_housing_env(mock_game.player1)
    # Reset
    mock_game.player1.current_map = "overland"
