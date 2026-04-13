"""Melee arc/sweep attack — hitbox anchored to player position."""

from __future__ import annotations

import math
from typing import Any

import pygame

from src.entities.attack import Attack


class MeleeArcAttack(Attack):
    """Short-lived arc hitbox that follows the player and sweeps enemies."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._elapsed: int = 0
        self._duration: int = int(self.cfg.get("duration_frames", 12))
        self._arc_deg: float = self.cfg.get("arc_degrees", 90)
        self._radius: float = self.cfg.get("radius", 96)
        # Base angle from facing direction
        self._base_angle: float = math.atan2(-self.dir_y, self.dir_x)
        # Don't collide with walls — melee attacks ignore terrain
        self.wall_collide = False

    def _move(self, dt: float, player_x: float, player_y: float) -> None:
        # Stay anchored to the player
        self.x = player_x
        self.y = player_y
        self._elapsed += 1
        if self._elapsed >= self._duration:
            self.alive = False

    def _get_hit_targets(self, enemies: list[Any]) -> list[Any]:
        half_arc = math.radians(self._arc_deg / 2)
        # Sweep: the arc rotates over the duration for visual feel
        progress = self._elapsed / max(1, self._duration)
        sweep_angle = self._base_angle + math.radians(self._arc_deg) * (progress - 0.5)

        targets: list[Any] = []
        for enemy in enemies:
            if enemy.hp <= 0 or id(enemy) in self.hit_enemies:
                continue
            dx = enemy.x - self.x
            dy = enemy.y - self.y
            dist = math.hypot(dx, dy)
            if dist > self._radius:
                continue
            angle_to_enemy = math.atan2(-dy, dx)
            diff = (angle_to_enemy - sweep_angle + math.pi) % (2 * math.pi) - math.pi
            if abs(diff) <= half_arc:
                targets.append(enemy)
        return targets

    def _draw(self, surf: pygame.Surface, sx: int, sy: int) -> None:
        progress = self._elapsed / max(1, self._duration)
        alpha = max(30, int(180 * (1.0 - progress)))

        half_arc = self._arc_deg / 2
        sweep_angle = math.degrees(self._base_angle) + self._arc_deg * (progress - 0.5)
        start_deg = sweep_angle - half_arc
        end_deg = sweep_angle + half_arc

        # Draw a semi-transparent arc
        arc_surf = pygame.Surface(
            (int(self._radius * 2), int(self._radius * 2)), pygame.SRCALPHA
        )
        rx = int(self._radius)
        ry = int(self._radius)
        rect = pygame.Rect(0, 0, rx * 2, ry * 2)

        # Pygame arcs use radians, measured counter-clockwise from +x
        start_rad = math.radians(-end_deg)
        end_rad = math.radians(-start_deg)

        color = (*self.color, alpha)
        pygame.draw.arc(arc_surf, color, rect, start_rad, end_rad, max(2, int(self._radius * 0.3)))

        # Draw a filled pie slice for the hitbox visualization
        n_points = 12
        points = [(rx, ry)]
        for i in range(n_points + 1):
            a = math.radians(start_deg + (end_deg - start_deg) * i / n_points)
            points.append((rx + int(self._radius * math.cos(a)), ry - int(self._radius * math.sin(a))))
        fill_color = (*self.color, alpha // 3)
        if len(points) > 2:
            pygame.draw.polygon(arc_surf, fill_color, points)

        surf.blit(arc_surf, (sx - rx, sy - ry))
