"""Projectile weapons fired by the player."""

import math
import pygame

from src.effects.particle import Particle


class Projectile:
    """A projectile fired in a direction. Configured by a WEAPONS entry."""

    def __init__(
        self,
        x: float,
        y: float,
        dir_x: float,
        dir_y: float,
        weapon: dict,
        player_id: int = 1,
        map_key: str | tuple = "overland",
    ) -> None:
        self.x = float(x)
        self.y = float(y)
        self.dir_x = dir_x
        self.dir_y = dir_y
        self.speed = weapon["speed"]
        self.damage = weapon["damage"]
        self.distance = weapon["distance"]
        self.size = weapon["size"]
        self.color = weapon["color"]
        self.pierce = weapon["pierce"]
        self.knockback = weapon["knockback"]
        self.draw_style = weapon["draw"]
        self.travelled = 0.0
        self.alive = True
        self.hit_enemies = set()
        self.xp_earned = 0
        self.player_id = player_id
        self.map_key = map_key

    def update(self, dt: float) -> None:
        """Move projectile and check distance."""
        from src.config import WORLD_COLS, WORLD_ROWS, TILE

        step = self.speed * dt
        self.x += self.dir_x * step
        self.y += self.dir_y * step
        self.travelled += step
        if self.travelled >= self.distance:
            self.alive = False
        if (
            self.x < 0
            or self.x > WORLD_COLS * TILE
            or self.y < 0
            or self.y > WORLD_ROWS * TILE
        ):
            self.alive = False

    def check_hits(self, enemies: list, particles: list, floats: list) -> None:
        """Check collisions with enemies."""
        from src.effects import FloatingText

        for enemy in enemies:
            if enemy.hp <= 0 or id(enemy) in self.hit_enemies:
                continue
            dist = math.hypot(enemy.x - self.x, enemy.y - self.y)
            if dist < self.size + enemy.hitbox_radius:
                enemy.take_damage(self.damage, self.x, self.y, particles)
                dx = enemy.x - self.x
                dy = enemy.y - self.y
                d = max(1, math.hypot(dx, dy))
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
        """Draw projectile to screen."""
        sx = int(self.x - cam_x)
        sy = int(self.y - cam_y)
        surf_w, surf_h = surf.get_size()
        if sx < -20 or sx > surf_w + 20 or sy < -20 or sy > surf_h + 20:
            return
        style = self.draw_style[0]
        if style == "circle":
            pygame.draw.circle(surf, self.color, (sx, sy), self.size)
        elif style == "rect":
            w, h = self.draw_style[1], self.draw_style[2]
            pygame.draw.rect(surf, self.color, (sx - w // 2, sy - h // 2, w, h))
        elif style == "line":
            length, width = self.draw_style[1], self.draw_style[2]
            ex = sx + int(self.dir_x * length)
            ey = sy + int(self.dir_y * length)
            pygame.draw.line(surf, self.color, (sx, sy), (ex, ey), width)
