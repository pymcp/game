"""Area-of-effect attack — stationary explosion or ground effect."""

from __future__ import annotations

import math
from typing import Any

import pygame

from src.entities.attack import Attack


class AoEAttack(Attack):
    """Deals damage in a radius.  Optionally delayed, lingers for several frames."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._radius: float = self.cfg["radius"]
        self._delay: int = int(self.cfg.get("delay_frames", 0))
        self._linger: int = int(self.cfg.get("linger_frames", 15))
        self._elapsed: int = 0
        # AoE doesn't move or collide with walls
        self.wall_collide = False
        # AoE always pierces (hits everything in radius)
        self.pierce = True

    def _move(self, dt: float, player_x: float, player_y: float) -> None:
        self._elapsed += 1
        if self._elapsed > self._delay + self._linger:
            self.alive = False

    @property
    def _is_active(self) -> bool:
        return self._elapsed >= self._delay

    def _get_hit_targets(self, enemies: list[Any]) -> list[Any]:
        if not self._is_active:
            return []
        targets: list[Any] = []
        for enemy in enemies:
            if enemy.hp <= 0 or id(enemy) in self.hit_enemies:
                continue
            dist = math.hypot(enemy.x - self.x, enemy.y - self.y)
            if dist <= self._radius:
                targets.append(enemy)
        return targets

    def _draw(self, surf: pygame.Surface, sx: int, sy: int) -> None:
        if not self._is_active:
            return
        progress = (self._elapsed - self._delay) / max(1, self._linger)
        alpha = max(20, int(160 * (1.0 - progress)))
        radius = int(self._radius * min(1.0, progress * 3))

        # Expanding ring
        aoe_surf = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        color = (*self.color, alpha)
        pygame.draw.circle(aoe_surf, color, (radius, radius), radius)
        # Brighter inner core
        inner_r = max(1, radius // 3)
        bright = tuple(min(255, c + 60) for c in self.color)
        core_color = (*bright, min(255, alpha + 40))
        pygame.draw.circle(aoe_surf, core_color, (radius, radius), inner_r)

        surf.blit(aoe_surf, (sx - radius, sy - radius))
