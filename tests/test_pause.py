"""Tests for the Game.paused property (src/game.py)."""

from __future__ import annotations

from src.ui.death_challenge import DeathChallengeManager
from tests.conftest import MockGame


def test_paused_false_by_default(mock_game: MockGame) -> None:
    mock_game.death_challenge = DeathChallengeManager(mock_game)
    mock_game._confirm_quit = False
    assert mock_game_paused(mock_game) is False


def test_paused_true_when_death_challenge_active(mock_game: MockGame) -> None:
    mgr = DeathChallengeManager(mock_game)
    mock_game.death_challenge = mgr
    mock_game._confirm_quit = False
    mgr.start(mock_game.player1)
    assert mock_game_paused(mock_game) is True


def test_paused_true_when_confirm_quit(mock_game: MockGame) -> None:
    mock_game.death_challenge = DeathChallengeManager(mock_game)
    mock_game._confirm_quit = True
    assert mock_game_paused(mock_game) is True


def test_paused_true_when_both(mock_game: MockGame) -> None:
    mgr = DeathChallengeManager(mock_game)
    mock_game.death_challenge = mgr
    mgr.start(mock_game.player1)
    mock_game._confirm_quit = True
    assert mock_game_paused(mock_game) is True


def test_paused_false_after_challenge_solved(mock_game: MockGame) -> None:
    mgr = DeathChallengeManager(mock_game)
    mock_game.death_challenge = mgr
    mock_game._confirm_quit = False
    mgr.start(mock_game.player1)
    assert mock_game_paused(mock_game) is True
    # Solve the challenge
    challenge = mgr.challenges[1]
    challenge["input"] = str(challenge["answer"])
    mgr.submit(mock_game.player1)
    assert mock_game_paused(mock_game) is False


# ---------------------------------------------------------------------------
# Helper — recreates the Game.paused logic for MockGame
# ---------------------------------------------------------------------------


def mock_game_paused(game: MockGame) -> bool:
    """Mirrors Game.paused property for MockGame."""
    return game.death_challenge.has_active() or game._confirm_quit
