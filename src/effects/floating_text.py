"""Floating text for damage, items, and feedback."""

import pygame


class FloatingText:
    """Text that floats and fades out."""

    __slots__ = ("x", "y", "text", "color", "life")

    def __init__(self, x, y, text, color):
        self.x = x
        self.y = y
        self.text = text
        self.color = color
        self.life = 45

    def update(self):
        """Float upward and fade."""
        self.y -= 0.8
        self.life -= 1

    def draw(self, surf, font, cam_x, cam_y):
        """Draw to screen with alpha fade."""
        from src.config import SCREEN_W, SCREEN_H

        alpha = max(0, min(255, self.life * 6))
        txt = font.render(self.text, True, self.color)
        txt.set_alpha(alpha)
        surf.blit(
            txt,
            (
                int(self.x - cam_x) - txt.get_width() // 2,
                int(self.y - cam_y) - txt.get_height() // 2,
            ),
        )
