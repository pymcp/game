"""Boomerang attack — flies outward then returns to the player."""

from __future__ import annotations

import math
from typing import Any

from src.entities.attack import Attack


class BoomerangAttack(Attack):
    """Flies outward, then reverses direction and returns to the player.

    Enemies can be hit on both the outbound and return pass.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._speed: float = self.cfg["speed"]
        self._max_distance: float = self.cfg["max_distance"]
        self._return_speed: float = self.cfg.get("return_speed", self._speed * 1.3)
        self._travelled: float = 0.0
        self._phase: str = "outbound"  # "outbound" | "returning"

    def _move(self, dt: float, player_x: float, player_y: float) -> None:
        if self._phase == "outbound":
            step = self._speed * dt
            self.x += self.dir_x * step
            self.y += self.dir_y * step
            self._travelled += step
            if self._travelled >= self._max_distance:
                self._phase = "returning"
                # Clear hit set so enemies can be hit again on return
                self.hit_enemies.clear()
        else:
            # Return toward current player position
            dx = player_x - self.x
            dy = player_y - self.y
            dist = math.hypot(dx, dy)
            if dist < 10:
                self.alive = False
                return
            nx = dx / dist
            ny = dy / dist
            step = self._return_speed * dt
            self.x += nx * step
            self.y += ny * step
            # Update direction for draw consistency
            self.dir_x = nx
            self.dir_y = ny
