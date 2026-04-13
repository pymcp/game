"""Homing attack — steers toward the nearest enemy within a cone."""

from __future__ import annotations

import math
from typing import Any

from src.entities.attack import Attack


class HomingAttack(Attack):
    """Projectile that gradually steers toward the nearest enemy."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._speed: float = self.cfg["speed"]
        self._distance: float = self.cfg["distance"]
        self._turn_rate: float = math.radians(self.cfg.get("turn_rate", 5.0))
        self._acquire_cone: float = math.radians(self.cfg.get("acquire_cone", 60))
        self._travelled: float = 0.0
        self._current_angle: float = math.atan2(self.dir_y, self.dir_x)
        # Reference to enemies set each frame by the game loop via _enemies
        self._enemies: list[Any] = []

    def _move(self, dt: float, player_x: float, player_y: float) -> None:
        # Steer toward nearest enemy within acquisition cone
        target = self._find_target()
        if target is not None:
            desired = math.atan2(target.y - self.y, target.x - self.x)
            diff = (desired - self._current_angle + math.pi) % (2 * math.pi) - math.pi
            # Clamp turn rate
            turn = max(-self._turn_rate, min(self._turn_rate, diff))
            self._current_angle += turn

        self.dir_x = math.cos(self._current_angle)
        self.dir_y = math.sin(self._current_angle)

        step = self._speed * dt
        self.x += self.dir_x * step
        self.y += self.dir_y * step
        self._travelled += step

        if self._travelled >= self._distance:
            self.alive = False

    def _find_target(self) -> Any | None:
        """Find the nearest enemy within the acquisition cone."""
        best: Any | None = None
        best_dist = float("inf")
        for enemy in self._enemies:
            if enemy.hp <= 0 or id(enemy) in self.hit_enemies:
                continue
            dx = enemy.x - self.x
            dy = enemy.y - self.y
            dist = math.hypot(dx, dy)
            if dist > self._distance:
                continue
            # Check if within acquisition cone
            angle_to = math.atan2(dy, dx)
            diff = abs(
                (angle_to - self._current_angle + math.pi) % (2 * math.pi) - math.pi
            )
            if diff <= self._acquire_cone and dist < best_dist:
                best_dist = dist
                best = enemy
        return best

    def check_hits(
        self,
        enemies: list[Any],
        particles: list[Any],
        floats: list[Any],
    ) -> None:
        # Store enemy reference for homing logic
        self._enemies = enemies
        super().check_hits(enemies, particles, floats)
