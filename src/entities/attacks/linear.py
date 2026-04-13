"""Straight-line projectile attack (rock, arrow, fire bolt, etc.)."""

from __future__ import annotations

from src.entities.attack import Attack


class LinearAttack(Attack):
    """Flies in a straight line at constant speed; dies on distance or wall."""

    def _move(self, dt: float, player_x: float, player_y: float) -> None:
        speed: float = self.cfg["speed"]
        distance: float = self.cfg["distance"]

        step = speed * dt
        self.x += self.dir_x * step
        self.y += self.dir_y * step

        if not hasattr(self, "_travelled"):
            self._travelled: float = 0.0
        self._travelled += step

        if self._travelled >= distance:
            self.alive = False
