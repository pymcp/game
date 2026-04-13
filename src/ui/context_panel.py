"""Floating context panel — shared by inventory tooltip and sign display.

Renders a semi-transparent panel with a title and content lines, dynamically
positioned to stay within the viewport.  Prefers placement below the anchor
point, but flips above if there isn't enough room.
"""

from __future__ import annotations

from typing import Sequence

import pygame


class ContextLine:
    """A single line of text inside a :class:`ContextPanel`."""

    __slots__ = ("text", "color", "font_key")

    def __init__(
        self,
        text: str,
        color: tuple[int, int, int] = (180, 175, 210),
        font_key: str = "xs",
    ) -> None:
        self.text = text
        self.color = color
        self.font_key = font_key  # "sm" -> font_ui_sm, "xs" -> font_ui_xs


class ContextPanel:
    """A floating info panel that stays inside the viewport.

    Parameters
    ----------
    bg_color:
        Panel background RGBA.
    border_color:
        Panel border RGB (``None`` to skip the border).
    border_width:
        Width of the border in pixels.
    padding:
        Inner padding in pixels.
    border_radius:
        Corner radius for the border.
    max_width:
        Maximum panel width in pixels.  ``None`` means fill
        ``viewport_w - 2 * margin``.
    margin:
        Minimum distance from the viewport edges.
    """

    def __init__(
        self,
        bg_color: tuple[int, int, int, int] = (14, 12, 24, 210),
        border_color: tuple[int, int, int] | None = None,
        border_width: int = 2,
        padding: int = 14,
        border_radius: int = 4,
        max_width: int | None = None,
        margin: int = 12,
    ) -> None:
        self.bg_color = bg_color
        self.border_color = border_color
        self.border_width = border_width
        self.padding = padding
        self.border_radius = border_radius
        self.max_width = max_width
        self.margin = margin

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compute_layout(
        self,
        fonts: dict[str, pygame.font.Font],
        title: str | None,
        lines: Sequence[ContextLine],
        *,
        viewport_x: int,
        viewport_y: int,
        viewport_w: int,
        viewport_h: int,
        anchor_x: int | None = None,
        anchor_y: int | None = None,
        title_color: tuple[int, int, int] = (220, 210, 255),
    ) -> tuple[int, int, int, int] | None:
        """Compute panel rect ``(px, py, panel_w, panel_h)`` or *None*."""
        if not title and not lines:
            return None

        pad = self.padding
        margin = self.margin

        title_h = 0
        if title:
            font_sm = fonts.get("sm") or fonts["xs"]
            title_h = font_sm.get_height() + 6

        content_h = 0
        max_text_w = 0
        for ln in lines:
            font = fonts.get(ln.font_key, fonts["xs"])
            content_h += font.get_height() + 4
            max_text_w = max(max_text_w, font.size(ln.text)[0])

        if title:
            font_sm = fonts.get("sm") or fonts["xs"]
            max_text_w = max(max_text_w, font_sm.size(title)[0])

        panel_h = pad + title_h + content_h + pad
        cap = self.max_width or (viewport_w - 2 * margin)
        panel_w = min(max_text_w + pad * 2, cap, viewport_w - 2 * margin)

        if anchor_x is not None and anchor_y is not None:
            px = anchor_x - panel_w // 2
            px = max(
                viewport_x + margin,
                min(px, viewport_x + viewport_w - panel_w - margin),
            )
            gap = 8
            py = anchor_y + gap
            if py + panel_h > viewport_y + viewport_h - margin:
                py = anchor_y - panel_h - gap
            py = max(
                viewport_y + margin,
                min(py, viewport_y + viewport_h - panel_h - margin),
            )
        else:
            px = viewport_x + (viewport_w - panel_w) // 2
            py = viewport_y + viewport_h - panel_h - margin

        return (px, py, panel_w, panel_h)

    def draw(
        self,
        screen: pygame.Surface,
        fonts: dict[str, pygame.font.Font],
        title: str | None,
        lines: Sequence[ContextLine],
        *,
        viewport_x: int,
        viewport_y: int,
        viewport_w: int,
        viewport_h: int,
        anchor_x: int | None = None,
        anchor_y: int | None = None,
        title_color: tuple[int, int, int] = (220, 210, 255),
    ) -> None:
        """Render the panel on *screen*.

        If *anchor_x* / *anchor_y* are given the panel is placed below that
        point (or above if it wouldn't fit).  Otherwise it defaults to
        bottom-center of the viewport.
        """
        layout = self.compute_layout(
            fonts,
            title,
            lines,
            viewport_x=viewport_x,
            viewport_y=viewport_y,
            viewport_w=viewport_w,
            viewport_h=viewport_h,
            anchor_x=anchor_x,
            anchor_y=anchor_y,
            title_color=title_color,
        )
        if layout is None:
            return

        px, py, panel_w, panel_h = layout
        pad = self.padding

        # --- Draw background ---
        panel_surf = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel_surf.fill(self.bg_color)
        if self.border_color is not None:
            pygame.draw.rect(
                panel_surf,
                self.border_color,
                (0, 0, panel_w, panel_h),
                self.border_width,
                border_radius=self.border_radius,
            )
        screen.blit(panel_surf, (px, py))

        # --- Draw title ---
        cur_y = py + pad
        if title:
            font_sm = fonts.get("sm") or fonts["xs"]
            title_surf = font_sm.render(title, True, title_color)
            screen.blit(title_surf, (px + pad, cur_y))
            cur_y += title_surf.get_height() + 6

        # --- Draw lines ---
        for ln in lines:
            font = fonts.get(ln.font_key, fonts["xs"])
            surf = font.render(ln.text, True, ln.color)
            screen.blit(surf, (px + pad, cur_y))
            cur_y += surf.get_height() + 4
