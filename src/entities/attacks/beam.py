"""Beam attack — sustained line of damage while fire key is held."""

from __future__ import annotations

import math
from typing import Any

import pygame

from src.entities.attack import Attack
from src.world.collision import tile_at
from src.data.tiles import BLOCKING_TILES


class BeamAttack(Attack):
    """Continuous beam emanating from the player in the facing direction.

    Damage is applied every ``tick_rate`` frames.  The beam truncates at the
    first blocking tile when ``wall_collide`` is True.  The game loop is
    responsible for keeping the beam alive while the fire button is held and
    killing it on release.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._range: float = self.cfg["range"]
        self._width: int = int(self.cfg.get("width", 6))
        self._tick_rate: int = int(self.cfg.get("tick_rate", 10))
        self._tick_counter: int = 0
        self._effective_range: float = self._range
        # Beam always pierces along its line
        self.pierce = True
        # Wall collision is handled specially — truncate, don't die
        self.wall_collide = False
        self._should_check_walls: bool = self.weapon.wall_collide

    def _move(self, dt: float, player_x: float, player_y: float) -> None:
        # Beam is anchored to the player
        self.x = player_x
        self.y = player_y
        self._tick_counter += 1

    def update(
        self,
        dt: float,
        player_x: float,
        player_y: float,
        world: list[list[int]],
    ) -> None:
        """Override to handle wall truncation instead of death."""
        if not self.alive:
            return
        self._move(dt, player_x, player_y)
        self.age += 1
        # Compute effective range (truncate at first wall)
        if self._should_check_walls:
            self._effective_range = self._compute_wall_range(world)
        else:
            self._effective_range = self._range

    def _compute_wall_range(self, world: list[list[int]]) -> float:
        """Walk along the beam direction and find the first blocking tile."""
        from src.config import TILE
        step = TILE // 2  # check every half-tile
        for i in range(1, int(self._range / step) + 1):
            check_dist = step * i
            cx = self.x + self.dir_x * check_dist
            cy = self.y + self.dir_y * check_dist
            t = tile_at(world, cx, cy)
            if t in BLOCKING_TILES:
                return float(check_dist)
        return self._range

    def _get_hit_targets(self, enemies: list[Any]) -> list[Any]:
        # Only damage on tick_rate intervals
        if self._tick_counter % self._tick_rate != 0:
            return []

        # Clear hit set each tick so enemies take repeated damage
        self.hit_enemies.clear()

        targets: list[Any] = []
        for enemy in enemies:
            if enemy.hp <= 0:
                continue
            # Project enemy position onto beam line
            ex = enemy.x - self.x
            ey = enemy.y - self.y
            proj_len = ex * self.dir_x + ey * self.dir_y
            if proj_len < 0 or proj_len > self._effective_range:
                continue
            # Perpendicular distance from beam line
            perp = abs(ex * (-self.dir_y) + ey * self.dir_x)
            if perp <= self._width + 10:
                targets.append(enemy)
        return targets

    def _draw(self, surf: pygame.Surface, sx: int, sy: int) -> None:
        end_x = sx + int(self.dir_x * self._effective_range)
        end_y = sy + int(self.dir_y * self._effective_range)

        # Outer glow
        glow = tuple(min(255, c + 40) for c in self.color)
        pygame.draw.line(surf, glow, (sx, sy), (end_x, end_y), self._width + 4)
        # Core beam
        pygame.draw.line(surf, self.color, (sx, sy), (end_x, end_y), self._width)
        # Bright center
        bright = tuple(min(255, c + 80) for c in self.color)
        pygame.draw.line(surf, bright, (sx, sy), (end_x, end_y), max(1, self._width // 3))

        # Flicker at the tip
        flicker = int(math.sin(self.age * 0.5) * 3)
        pygame.draw.circle(
            surf, bright,
            (end_x + flicker, end_y + flicker),
            self._width,
        )
