"""Tests for src.ui.context_panel — ContextPanel positioning and rendering."""

from __future__ import annotations

import pygame
import pytest

from src.ui.context_panel import ContextLine, ContextPanel

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _init_pygame() -> None:
    pygame.init()
    pygame.display.set_mode((1, 1))


def _make_fonts() -> dict[str, pygame.font.Font]:
    return {
        "sm": pygame.font.SysFont(None, 22),
        "xs": pygame.font.SysFont(None, 16),
    }


def _sample_lines(n: int = 2) -> list[ContextLine]:
    return [ContextLine(f"Line {i}", color=(200, 200, 200)) for i in range(n)]


# ---------------------------------------------------------------------------
# ContextLine
# ---------------------------------------------------------------------------


class TestContextLine:
    def test_defaults(self) -> None:
        ln = ContextLine("hello")
        assert ln.text == "hello"
        assert ln.color == (180, 175, 210)
        assert ln.font_key == "xs"

    def test_custom(self) -> None:
        ln = ContextLine("yo", color=(255, 0, 0), font_key="sm")
        assert ln.color == (255, 0, 0)
        assert ln.font_key == "sm"


# ---------------------------------------------------------------------------
# ContextPanel — compute_layout positioning
# ---------------------------------------------------------------------------


class TestComputeLayout:
    """Test the pure positioning logic via compute_layout()."""

    def test_returns_none_for_empty(self) -> None:
        panel = ContextPanel()
        fonts = _make_fonts()
        result = panel.compute_layout(
            fonts,
            None,
            [],
            viewport_x=0,
            viewport_y=0,
            viewport_w=800,
            viewport_h=600,
        )
        assert result is None

    def test_bottom_center_no_anchor(self) -> None:
        panel = ContextPanel(margin=12)
        fonts = _make_fonts()
        lines = _sample_lines(1)
        result = panel.compute_layout(
            fonts,
            "Title",
            lines,
            viewport_x=0,
            viewport_y=0,
            viewport_w=800,
            viewport_h=600,
        )
        assert result is not None
        px, py, pw, ph = result
        # Centered horizontally
        assert px == (800 - pw) // 2
        # At bottom minus margin
        assert py == 600 - ph - 12

    def test_below_anchor(self) -> None:
        panel = ContextPanel(margin=12)
        fonts = _make_fonts()
        lines = _sample_lines(1)
        result = panel.compute_layout(
            fonts,
            "Title",
            lines,
            viewport_x=0,
            viewport_y=0,
            viewport_w=800,
            viewport_h=600,
            anchor_x=400,
            anchor_y=200,
        )
        assert result is not None
        px, py, pw, ph = result
        # Should be below anchor (anchor_y + 8 gap)
        assert py == 200 + 8

    def test_flips_above_when_no_room_below(self) -> None:
        panel = ContextPanel(margin=12)
        fonts = _make_fonts()
        lines = _sample_lines(3)
        # Anchor near bottom edge
        result = panel.compute_layout(
            fonts,
            "Title",
            lines,
            viewport_x=0,
            viewport_y=0,
            viewport_w=800,
            viewport_h=600,
            anchor_x=400,
            anchor_y=570,
        )
        assert result is not None
        _px, py, _pw, ph = result
        # Should be above anchor (anchor_y - ph - 8)
        assert py < 570

    def test_clamps_horizontal_left(self) -> None:
        panel = ContextPanel(margin=12)
        fonts = _make_fonts()
        lines = _sample_lines(1)
        result = panel.compute_layout(
            fonts,
            None,
            lines,
            viewport_x=0,
            viewport_y=0,
            viewport_w=800,
            viewport_h=600,
            anchor_x=5,
            anchor_y=200,
        )
        assert result is not None
        px, _py, _pw, _ph = result
        assert px >= 12  # margin

    def test_clamps_horizontal_right(self) -> None:
        panel = ContextPanel(margin=12)
        fonts = _make_fonts()
        lines = _sample_lines(1)
        result = panel.compute_layout(
            fonts,
            None,
            lines,
            viewport_x=0,
            viewport_y=0,
            viewport_w=800,
            viewport_h=600,
            anchor_x=795,
            anchor_y=200,
        )
        assert result is not None
        px, _py, pw, _ph = result
        assert px + pw <= 800 - 12  # margin

    def test_clamps_vertical(self) -> None:
        panel = ContextPanel(margin=12)
        fonts = _make_fonts()
        lines = _sample_lines(1)
        result = panel.compute_layout(
            fonts,
            None,
            lines,
            viewport_x=0,
            viewport_y=0,
            viewport_w=800,
            viewport_h=600,
            anchor_x=400,
            anchor_y=5,
        )
        assert result is not None
        _px, py, _pw, _ph = result
        assert py >= 12  # Never above viewport + margin

    def test_viewport_offset(self) -> None:
        """Viewport not at (0,0) — e.g. player 2 in split screen."""
        panel = ContextPanel(margin=12)
        fonts = _make_fonts()
        lines = _sample_lines(1)
        result = panel.compute_layout(
            fonts,
            "Title",
            lines,
            viewport_x=640,
            viewport_y=0,
            viewport_w=640,
            viewport_h=720,
        )
        assert result is not None
        px, py, pw, ph = result
        assert px >= 640 + 12
        assert px + pw <= 640 + 640 - 12

    def test_max_width_caps_wide_content(self) -> None:
        panel = ContextPanel(max_width=300, margin=12)
        fonts = _make_fonts()
        wide_line = [ContextLine("A" * 200, color=(200, 200, 200))]
        result = panel.compute_layout(
            fonts,
            None,
            wide_line,
            viewport_x=0,
            viewport_y=0,
            viewport_w=800,
            viewport_h=600,
        )
        assert result is not None
        _px, _py, pw, _ph = result
        assert pw == 300

    def test_panel_shrinks_to_content(self) -> None:
        panel = ContextPanel(max_width=600, margin=12, padding=14)
        fonts = _make_fonts()
        lines = [ContextLine("Hi")]
        result = panel.compute_layout(
            fonts,
            None,
            lines,
            viewport_x=0,
            viewport_y=0,
            viewport_w=800,
            viewport_h=600,
        )
        assert result is not None
        _px, _py, pw, _ph = result
        assert pw < 600

    def test_title_only(self) -> None:
        panel = ContextPanel()
        fonts = _make_fonts()
        result = panel.compute_layout(
            fonts,
            "Only Title",
            [],
            viewport_x=0,
            viewport_y=0,
            viewport_w=800,
            viewport_h=600,
        )
        assert result is not None

    def test_lines_only(self) -> None:
        panel = ContextPanel()
        fonts = _make_fonts()
        result = panel.compute_layout(
            fonts,
            None,
            _sample_lines(2),
            viewport_x=0,
            viewport_y=0,
            viewport_w=800,
            viewport_h=600,
        )
        assert result is not None


# ---------------------------------------------------------------------------
# ContextPanel — draw smoke tests
# ---------------------------------------------------------------------------


class TestDraw:
    """Smoke tests: draw() does not crash."""

    def test_draw_no_anchor(self) -> None:
        screen = pygame.Surface((800, 600), pygame.SRCALPHA)
        panel = ContextPanel()
        fonts = _make_fonts()
        panel.draw(
            screen,
            fonts,
            "Hello",
            _sample_lines(2),
            viewport_x=0,
            viewport_y=0,
            viewport_w=800,
            viewport_h=600,
        )

    def test_draw_with_anchor(self) -> None:
        screen = pygame.Surface((800, 600), pygame.SRCALPHA)
        panel = ContextPanel(border_color=(200, 200, 200))
        fonts = _make_fonts()
        panel.draw(
            screen,
            fonts,
            "Anchored",
            _sample_lines(1),
            viewport_x=0,
            viewport_y=0,
            viewport_w=800,
            viewport_h=600,
            anchor_x=300,
            anchor_y=200,
        )

    def test_draw_empty(self) -> None:
        screen = pygame.Surface((800, 600), pygame.SRCALPHA)
        panel = ContextPanel()
        fonts = _make_fonts()
        # Should be a no-op
        panel.draw(
            screen,
            fonts,
            None,
            [],
            viewport_x=0,
            viewport_y=0,
            viewport_w=800,
            viewport_h=600,
        )

    def test_draw_no_border(self) -> None:
        screen = pygame.Surface((800, 600), pygame.SRCALPHA)
        panel = ContextPanel(border_color=None)
        fonts = _make_fonts()
        panel.draw(
            screen,
            fonts,
            "No Border",
            _sample_lines(1),
            viewport_x=0,
            viewport_y=0,
            viewport_w=800,
            viewport_h=600,
        )

    def test_draw_sign_style(self) -> None:
        """Matches the sign display configuration."""
        screen = pygame.Surface((800, 600), pygame.SRCALPHA)
        panel = ContextPanel(
            bg_color=(15, 10, 5, 210),
            border_color=(180, 140, 70),
            border_width=2,
            padding=14,
            max_width=720,
        )
        fonts = _make_fonts()
        lines = [
            ContextLine("Welcome!", color=(230, 200, 130), font_key="sm"),
            ContextLine("This is a sign.", color=(210, 185, 145), font_key="sm"),
        ]
        panel.draw(
            screen,
            fonts,
            None,
            lines,
            viewport_x=0,
            viewport_y=0,
            viewport_w=800,
            viewport_h=600,
            anchor_x=400,
            anchor_y=300,
        )

    def test_draw_tooltip_style(self) -> None:
        """Matches the inventory tooltip configuration."""
        screen = pygame.Surface((800, 600), pygame.SRCALPHA)
        panel = ContextPanel(
            bg_color=(14, 12, 24, 210),
            border_color=None,
            padding=14,
            max_width=500,
        )
        fonts = _make_fonts()
        lines = [
            ContextLine("Slot: Helmet  |  Defense: 20%  |  Durability: 50"),
            ContextLine("Equipped in: helmet", color=(100, 220, 100)),
            ContextLine("E — Equip", color=(255, 220, 80)),
        ]
        panel.draw(
            screen,
            fonts,
            "Iron Helmet",
            lines,
            viewport_x=0,
            viewport_y=0,
            viewport_w=640,
            viewport_h=720,
            anchor_x=320,
            anchor_y=400,
        )
