"""Tests for DeathChallengeManager (src/ui/death_challenge.py)."""

from __future__ import annotations

import pygame

from src.ui.death_challenge import DeathChallengeManager
from tests.conftest import MockGame


def test_construction(mock_game: MockGame) -> None:
    mgr = DeathChallengeManager(mock_game)
    assert mgr.challenges == {}
    assert not mgr.is_active(1)
    assert not mgr.is_active(2)


def test_start_creates_challenge(mock_game: MockGame) -> None:
    mgr = DeathChallengeManager(mock_game)
    mgr.start(mock_game.player1)
    assert mgr.is_active(1)
    challenge = mgr.challenges[1]
    assert "question" in challenge
    assert "answer" in challenge
    assert isinstance(challenge["answer"], int)
    assert challenge["input"] == ""
    assert challenge["wrong"] is False
    assert mock_game.player1.is_dead is True


def test_submit_correct_answer(mock_game: MockGame) -> None:
    mgr = DeathChallengeManager(mock_game)
    mgr.start(mock_game.player1)
    challenge = mgr.challenges[1]
    # Fill in the correct answer
    challenge["input"] = str(challenge["answer"])
    mgr.submit(mock_game.player1)
    assert not mgr.is_active(1)
    assert mock_game.player1.is_dead is False
    assert mock_game.player1.hp == mock_game.player1.max_hp
    # Should have spawned a "Respawned!" float
    assert len(mock_game._floats) == 1


def test_submit_wrong_answer(mock_game: MockGame) -> None:
    mgr = DeathChallengeManager(mock_game)
    mgr.start(mock_game.player1)
    challenge = mgr.challenges[1]
    challenge["input"] = str(challenge["answer"] + 999)
    mgr.submit(mock_game.player1)
    assert mgr.is_active(1)
    assert challenge["wrong"] is True
    assert challenge["input"] == ""


def test_submit_non_numeric(mock_game: MockGame) -> None:
    mgr = DeathChallengeManager(mock_game)
    mgr.start(mock_game.player1)
    challenge = mgr.challenges[1]
    challenge["input"] = "abc"
    mgr.submit(mock_game.player1)
    assert challenge["wrong"] is True
    assert challenge["input"] == ""


def test_handle_keydown_digit(mock_game: MockGame) -> None:
    mgr = DeathChallengeManager(mock_game)
    mgr.start(mock_game.player1)
    consumed = mgr.handle_keydown(pygame.K_5, mock_game.player1)
    assert consumed is True
    assert mgr.challenges[1]["input"] == "5"


def test_handle_keydown_backspace(mock_game: MockGame) -> None:
    mgr = DeathChallengeManager(mock_game)
    mgr.start(mock_game.player1)
    mgr.challenges[1]["input"] = "12"
    consumed = mgr.handle_keydown(pygame.K_BACKSPACE, mock_game.player1)
    assert consumed is True
    assert mgr.challenges[1]["input"] == "1"


def test_handle_keydown_minus(mock_game: MockGame) -> None:
    mgr = DeathChallengeManager(mock_game)
    mgr.start(mock_game.player1)
    consumed = mgr.handle_keydown(pygame.K_MINUS, mock_game.player1)
    assert consumed is True
    assert mgr.challenges[1]["input"] == "-"


def test_handle_keydown_enter_triggers_submit(mock_game: MockGame) -> None:
    mgr = DeathChallengeManager(mock_game)
    mgr.start(mock_game.player1)
    challenge = mgr.challenges[1]
    challenge["input"] = str(challenge["answer"])
    consumed = mgr.handle_keydown(pygame.K_RETURN, mock_game.player1)
    assert consumed is True
    assert not mgr.is_active(1)


def test_handle_keydown_no_challenge(mock_game: MockGame) -> None:
    mgr = DeathChallengeManager(mock_game)
    consumed = mgr.handle_keydown(pygame.K_5, mock_game.player1)
    assert consumed is False


def test_draw_no_crash(mock_game: MockGame) -> None:
    mgr = DeathChallengeManager(mock_game)
    mgr.start(mock_game.player1)
    # Should not raise
    mgr.draw(mock_game.player1, 0, 0, 320, 360)


def test_draw_full_screen(mock_game: MockGame) -> None:
    """Death challenge renders correctly with full-screen dimensions."""
    mgr = DeathChallengeManager(mock_game)
    mgr.start(mock_game.player1)
    # Should not raise with full-screen coords
    mgr.draw(mock_game.player1, 0, 0, 640, 360)


def test_draw_no_challenge(mock_game: MockGame) -> None:
    mgr = DeathChallengeManager(mock_game)
    # Should return silently
    mgr.draw(mock_game.player1, 0, 0, 320, 360)


def test_respawn_to_overland(mock_game: MockGame) -> None:
    mgr = DeathChallengeManager(mock_game)
    mgr.start(mock_game.player1)
    challenge = mgr.challenges[1]
    challenge["input"] = str(challenge["answer"])
    mgr.submit(mock_game.player1)
    # Player should be on overland
    assert mock_game.player1.current_map == "overland"


def test_respawn_to_portal_exit(mock_game: MockGame) -> None:
    mgr = DeathChallengeManager(mock_game)
    mock_game.player1.last_portal_exit_map = "overland"
    mock_game.player1.last_portal_exit_x = 100.0
    mock_game.player1.last_portal_exit_y = 200.0
    mgr.start(mock_game.player1)
    challenge = mgr.challenges[1]
    challenge["input"] = str(challenge["answer"])
    mgr.submit(mock_game.player1)
    assert mock_game.player1.x == 100.0
    assert mock_game.player1.y == 200.0


def test_has_active_false_when_empty(mock_game: MockGame) -> None:
    mgr = DeathChallengeManager(mock_game)
    assert mgr.has_active() is False


def test_has_active_true_when_challenge(mock_game: MockGame) -> None:
    mgr = DeathChallengeManager(mock_game)
    mgr.start(mock_game.player1)
    assert mgr.has_active() is True


def test_has_active_true_for_either_player(mock_game: MockGame) -> None:
    mgr = DeathChallengeManager(mock_game)
    mgr.start(mock_game.player2)
    assert mgr.has_active() is True


def test_get_active_player_id_none(mock_game: MockGame) -> None:
    mgr = DeathChallengeManager(mock_game)
    assert mgr.get_active_player_id() is None


def test_get_active_player_id_returns_lowest(mock_game: MockGame) -> None:
    mgr = DeathChallengeManager(mock_game)
    mgr.start(mock_game.player2)
    assert mgr.get_active_player_id() == 2
    mgr.start(mock_game.player1)
    assert mgr.get_active_player_id() == 1


def test_has_active_false_after_solve(mock_game: MockGame) -> None:
    mgr = DeathChallengeManager(mock_game)
    mgr.start(mock_game.player1)
    challenge = mgr.challenges[1]
    challenge["input"] = str(challenge["answer"])
    mgr.submit(mock_game.player1)
    assert mgr.has_active() is False
