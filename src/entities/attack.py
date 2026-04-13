"""Base Attack class — shared lifecycle for all weapon attack patterns."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

import pygame

from src.data.attack_patterns import WeaponDef, get_pattern_config
from src.effects.particle import Particle
from src.world.collision import tile_at
from src.data.tiles import BLOCKING_TILES

if TYPE_CHECKING:
    from src.entities.enemy import Enemy
    from src.effects.floating_text import FloatingText


class Attack:
    """Base class for all weapon attack instances.

    Subclasses override :meth:`_move`, :meth:`_get_hit_targets`, and
    :meth:`_draw` to implement pattern-specific behaviour.
    """

    def __init__(
        self,
        x: float,
        y: float,
        dir_x: float,
        dir_y: float,
        weapon: WeaponDef,
        player_id: int = 1,
        map_key: str | tuple = "overland",
        damage_mult: float = 1.0,
    ) -> None:
        self.x: float = float(x)
        self.y: float = float(y)
        self.dir_x: float = dir_x
        self.dir_y: float = dir_y
        self.weapon: WeaponDef = weapon
        self.damage: int = int(weapon.damage * damage_mult)
        self.knockback: float = weapon.knockback
        self.color: tuple[int, int, int] = weapon.color
        self.draw_style: tuple[Any, ...] = weapon.draw
        self.wall_collide: bool = weapon.wall_collide
        self.pierce: bool = weapon.pierce
        self.alive: bool = True
        self.hit_enemies: set[int] = set()
        self.xp_earned: int = 0
        self.player_id: int = player_id
        self.map_key: str | tuple = map_key
        self.age: int = 0  # frames since spawn

        self.cfg: dict[str, Any] = get_pattern_config(weapon)

    # ------------------------------------------------------------------
    # Public lifecycle
    # ------------------------------------------------------------------

    def update(
        self,
        dt: float,
        player_x: float,
        player_y: float,
        world: list[list[int]],
    ) -> None:
        """Advance one frame: move, wall-check, age."""
        if not self.alive:
            return
        self._move(dt, player_x, player_y)
        self.age += 1
        # Wall collision
        if self.wall_collide and self.alive:
            t = tile_at(world, self.x, self.y)
            if t in BLOCKING_TILES:
                self._on_wall_hit()
        # World bounds
        if self.alive:
            self._bounds_check(world)

    def check_hits(
        self,
        enemies: list[Any],
        particles: list[Any],
        floats: list[Any],
    ) -> None:
        """Check collisions with enemies and apply damage/knockback."""
        from src.effects import FloatingText

        for enemy in self._get_hit_targets(enemies):
            if enemy.hp <= 0 or id(enemy) in self.hit_enemies:
                continue
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
            if not self.pierce:
                self.alive = False
                break

    def draw(self, surf: pygame.Surface, cam_x: float, cam_y: float) -> None:
        """Render the attack to the screen."""
        if not self.alive:
            return
        sx = int(self.x - cam_x)
        sy = int(self.y - cam_y)
        surf_w, surf_h = surf.get_size()
        if sx < -40 or sx > surf_w + 40 or sy < -40 or sy > surf_h + 40:
            return
        self._draw(surf, sx, sy)

    # ------------------------------------------------------------------
    # Subclass hooks
    # ------------------------------------------------------------------

    def _move(self, dt: float, player_x: float, player_y: float) -> None:
        """Override to implement pattern-specific movement."""
        raise NotImplementedError

    def _get_hit_targets(self, enemies: list[Any]) -> list[Any]:
        """Return enemies within this attack's hitbox this frame.

        Default: circle collision at (self.x, self.y) with self.cfg["size"].
        """
        size = self.cfg.get("size", 4)
        targets: list[Any] = []
        for enemy in enemies:
            if enemy.hp <= 0 or id(enemy) in self.hit_enemies:
                continue
            dist = math.hypot(enemy.x - self.x, enemy.y - self.y)
            if dist < size + 10:
                targets.append(enemy)
        return targets

    def _draw(self, surf: pygame.Surface, sx: int, sy: int) -> None:
        """Override to implement pattern-specific rendering."""
        style = self.draw_style[0]
        if style == "circle":
            size = self.cfg.get("size", 4)
            pygame.draw.circle(surf, self.color, (sx, sy), size)
        elif style == "rect":
            w, h = self.draw_style[1], self.draw_style[2]
            pygame.draw.rect(surf, self.color, (sx - w // 2, sy - h // 2, w, h))
        elif style == "line":
            length, width = self.draw_style[1], self.draw_style[2]
            ex = sx + int(self.dir_x * length)
            ey = sy + int(self.dir_y * length)
            pygame.draw.line(surf, self.color, (sx, sy), (ex, ey), width)

    def _on_wall_hit(self) -> None:
        """Called when the attack collides with a blocking tile."""
        self.alive = False

    def _bounds_check(self, world: list[list[int]]) -> None:
        """Kill the attack if it exits the world bounds."""
        from src.config import TILE
        rows = len(world)
        cols = len(world[0]) if rows else 0
        if self.x < 0 or self.x > cols * TILE or self.y < 0 or self.y > rows * TILE:
            self.alive = False
