"""Spiral attack — orbits around the player in an expanding/contracting spiral."""

from __future__ import annotations

import math
from typing import Any

import pygame

from src.entities.attack import Attack


class SpiralAttack(Attack):
    """Orbits around the player, damaging enemies it touches."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._radius_min: float = self.cfg["radius_min"]
        self._radius_max: float = self.cfg["radius_max"]
        self._angular_speed: float = self.cfg["angular_speed"]
        self._duration: int = int(self.cfg.get("duration", 90))
        self._elapsed: int = 0
        # Start angle from facing direction
        self._angle: float = math.atan2(-self.dir_y, self.dir_x)
        # Don't collide with walls — orbital attacks ignore terrain
        self.wall_collide = False
        # Always pierces (orbiting blade hits everything)
        self.pierce = True

    def _move(self, dt: float, player_x: float, player_y: float) -> None:
        self._elapsed += 1
        if self._elapsed >= self._duration:
            self.alive = False
            return

        progress = self._elapsed / self._duration
        # Radius oscillates: expand in first half, contract in second
        if progress < 0.5:
            t = progress * 2
            radius = self._radius_min + (self._radius_max - self._radius_min) * t
        else:
            t = (progress - 0.5) * 2
            radius = self._radius_max - (self._radius_max - self._radius_min) * t

        self._angle += self._angular_speed * dt * 0.1
        self.x = player_x + math.cos(self._angle) * radius
        self.y = player_y - math.sin(self._angle) * radius
        # Update direction for drawing (tangent to circle)
        self.dir_x = -math.sin(self._angle)
        self.dir_y = -math.cos(self._angle)

    def _draw(self, surf: pygame.Surface, sx: int, sy: int) -> None:
        size = self.cfg.get("size", 4)
        # Trailing effect
        alpha = max(60, int(200 * (1.0 - self._elapsed / self._duration)))
        trail_surf = pygame.Surface((size * 4, size * 4), pygame.SRCALPHA)
        trail_color = (*self.color, alpha)
        pygame.draw.circle(trail_surf, trail_color, (size * 2, size * 2), size * 2)
        surf.blit(trail_surf, (sx - size * 2, sy - size * 2))
        # Core
        pygame.draw.circle(surf, self.color, (sx, sy), size)
        # Bright center
        bright = tuple(min(255, c + 80) for c in self.color)
        pygame.draw.circle(surf, bright, (sx, sy), max(1, size // 2))
