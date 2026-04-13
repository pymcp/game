"""Chain attack — bounces between enemies on hit."""

from __future__ import annotations

import math
from typing import Any

import pygame

from src.entities.attack import Attack


class ChainAttack(Attack):
    """Flies toward enemies; on hit, redirects to the next nearest target."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._speed: float = self.cfg["speed"]
        self._max_bounces: int = int(self.cfg.get("max_bounces", 3))
        self._bounce_range: float = self.cfg.get("bounce_range", 256)
        self._damage_decay: float = self.cfg.get("damage_decay", 0.7)
        self._bounces: int = 0
        # Chain always pierces (stops only when no target or max bounces)
        self.pierce = True
        # Trail of positions for lightning-bolt effect
        self._trail: list[tuple[float, float]] = [(self.x, self.y)]

    def _move(self, dt: float, player_x: float, player_y: float) -> None:
        step = self._speed * dt
        self.x += self.dir_x * step
        self.y += self.dir_y * step

        # Bounds check handled by base class

    def check_hits(
        self,
        enemies: list[Any],
        particles: list[Any],
        floats: list[Any],
    ) -> None:
        """Override to implement chain-bounce logic on hit."""
        from src.effects import FloatingText
        from src.effects.particle import Particle

        size = self.cfg.get("size", 4)

        for enemy in enemies:
            if enemy.hp <= 0 or id(enemy) in self.hit_enemies:
                continue
            dist = math.hypot(enemy.x - self.x, enemy.y - self.y)
            if dist >= size + enemy.hitbox_radius:
                continue

            # Hit this enemy
            enemy.take_damage(self.damage, self.x, self.y, particles)
            dx = enemy.x - self.x
            dy = enemy.y - self.y
            d = max(1.0, math.hypot(dx, dy))
            enemy.knockback_vx += (dx / d) * self.knockback
            enemy.knockback_vy += (dy / d) * self.knockback
            self.hit_enemies.add(id(enemy))

            if enemy.hp <= 0:
                floats.append(
                    FloatingText(
                        enemy.x,
                        enemy.y,
                        f"{enemy.name} defeated! (+{enemy.xp} XP)",
                        (255, 220, 50),
                    )
                )
                self.xp_earned += enemy.xp
                for _ in range(10):
                    particles.append(Particle(enemy.x, enemy.y, enemy.color))

            self._trail.append((enemy.x, enemy.y))
            self._bounces += 1
            if self._bounces >= self._max_bounces:
                self.alive = False
                return

            # Decay damage for next bounce
            self.damage = max(1, int(self.damage * self._damage_decay))

            # Redirect toward nearest un-hit enemy in range
            next_target = self._find_next_target(enemies, enemy.x, enemy.y)
            if next_target is None:
                self.alive = False
                return

            # Snap to hit position and redirect
            self.x = enemy.x
            self.y = enemy.y
            tdx = next_target.x - self.x
            tdy = next_target.y - self.y
            td = max(1.0, math.hypot(tdx, tdy))
            self.dir_x = tdx / td
            self.dir_y = tdy / td
            return  # only one hit per frame

    def _find_next_target(
        self, enemies: list[Any], from_x: float, from_y: float
    ) -> Any | None:
        best = None
        best_dist = self._bounce_range
        for enemy in enemies:
            if enemy.hp <= 0 or id(enemy) in self.hit_enemies:
                continue
            dist = math.hypot(enemy.x - from_x, enemy.y - from_y)
            if dist < best_dist:
                best_dist = dist
                best = enemy
        return best

    def _draw(self, surf: pygame.Surface, sx: int, sy: int) -> None:
        # Draw lightning trail between bounce points
        cam_x = self.x - sx
        cam_y = self.y - sy
        points = [(int(px - cam_x), int(py - cam_y)) for px, py in self._trail]
        points.append((sx, sy))

        if len(points) >= 2:
            # Bright core line
            pygame.draw.lines(surf, self.color, False, points, 3)
            # Dimmer outer glow
            glow = tuple(min(255, c + 60) for c in self.color)
            pygame.draw.lines(surf, glow, False, points, 1)

        # Current projectile dot
        size = self.cfg.get("size", 4)
        pygame.draw.circle(surf, self.color, (sx, sy), size)
