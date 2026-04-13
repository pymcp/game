"""Projectile weapons fired by the player."""

import math
import pygame


class Projectile:
    """A projectile fired in a direction. Configured by a WEAPONS entry."""

    def __init__(self, x, y, dir_x, dir_y, weapon):
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

    def update(self, dt):
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

    def check_hits(self, enemies, particles, floats):
        """Check collisions with enemies."""
        from src.effects import FloatingText

        for enemy in enemies:
            if enemy.hp <= 0 or id(enemy) in self.hit_enemies:
                continue
            dist = math.hypot(enemy.x - self.x, enemy.y - self.y)
            if dist < self.size + 10:
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

    def draw(self, surf, cam_x, cam_y):
        """Draw projectile to screen."""
        from src.config import SCREEN_W, SCREEN_H

        sx = int(self.x - cam_x)
        sy = int(self.y - cam_y)
        if sx < -20 or sx > SCREEN_W + 20 or sy < -20 or sy > SCREEN_H + 20:
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
