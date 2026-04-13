"""Particle effects for animations and visual feedback."""

import random
import math
import pygame


class Particle:
    """A physics-based particle with gravity and decay."""

    __slots__ = ("x", "y", "vx", "vy", "life", "color", "size")

    def __init__(self, x: float, y: float, color: tuple[int, int, int]) -> None:
        angle = random.uniform(0, 2 * math.pi)
        speed = random.uniform(1, 3)
        self.x = x
        self.y = y
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        self.life = random.randint(15, 30)
        self.color = color
        self.size = random.randint(2, 4)

    def update(self) -> None:
        """Update position with gravity."""
        self.x += self.vx
        self.y += self.vy
        self.vy += 0.1
        self.life -= 1

    def draw(self, surf: pygame.Surface, cam_x: float, cam_y: float) -> None:
        """Draw to screen if on-camera."""
        from src.config import SCREEN_W, SCREEN_H

        sx = int(self.x - cam_x)
        sy = int(self.y - cam_y)
        if 0 <= sx < SCREEN_W and 0 <= sy < SCREEN_H:
            pygame.draw.rect(surf, self.color, (sx, sy, self.size, self.size))
