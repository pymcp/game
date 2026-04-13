"""Enemy class with data-driven vector rendering."""

import math
import pygame
from src.config import TILE, SCREEN_W, SCREEN_H
from src.effects import Particle


def _clamp_color(base: tuple[int, int, int], offset: tuple[int, int, int]) -> tuple[int, int, int]:
    """Clamp color values to 0-255."""
    return tuple(max(0, min(255, base[i] + offset[i])) for i in range(3))


class Enemy:
    """A data-driven enemy instance. Create with an enemy-type key."""

    def __init__(self, x: float, y: float, type_key: str) -> None:
        from src.data import ENEMY_TYPES

        self.x = float(x)
        self.y = float(y)
        self.type_key = type_key
        info = ENEMY_TYPES[type_key]
        self.hp = info["hp"]
        self.max_hp = info["hp"]
        self.attack = info["attack"]
        self.speed = info["speed"]
        self.xp = info["xp"]
        self.color = info["color"]
        self.attack_cd = info["attack_cd"]
        self.draw_commands = info["draw_commands"]
        self.name = info["name"]
        self.chase_range = info["chase_range"]

        self.state = "idle"
        self.cooldown = 0.0
        self.hurt_flash = 0
        self.knockback_vx = 0.0
        self.knockback_vy = 0.0

    def _on_screen(self, cam_x: float, cam_y: float, margin: int = 0) -> bool:
        """Check if enemy is on screen."""
        return (
            cam_x - margin <= self.x <= cam_x + SCREEN_W + margin
            and cam_y - margin <= self.y <= cam_y + SCREEN_H + margin
        )

    def _blocked(self, wx: float, wy: float, world: list[list[int]]) -> bool:
        """Check if position is blocked."""
        from src.config import WATER, MOUNTAIN, HOUSE, CAVE_WALL

        col = int(wx) // TILE
        row = int(wy) // TILE
        world_rows = len(world)
        world_cols = len(world[0]) if world_rows > 0 else 0
        if col < 0 or col >= world_cols or row < 0 or row >= world_rows:
            return True
        return world[row][col] in (WATER, MOUNTAIN, HOUSE, CAVE_WALL)

    def update(self, dt: float, px: float, py: float, cam_x: float, cam_y: float, world: list[list[int]], particles: list) -> None:
        """Update enemy state and position."""
        if self.hp <= 0:
            return

        # Knockback
        if abs(self.knockback_vx) > 0.1 or abs(self.knockback_vy) > 0.1:
            nx = self.x + self.knockback_vx * dt
            ny = self.y + self.knockback_vy * dt
            if not self._blocked(nx, ny, world):
                self.x = nx
                self.y = ny
            self.knockback_vx *= 0.8
            self.knockback_vy *= 0.8

        if self.hurt_flash > 0:
            self.hurt_flash -= 1
        if self.cooldown > 0:
            self.cooldown -= dt

        dist = math.hypot(px - self.x, py - self.y)

        if self.state == "idle":
            trigger = self.chase_range if self.chase_range > 0 else None
            if trigger:
                if dist < trigger:
                    self.state = "chase"
            elif self._on_screen(cam_x, cam_y, margin=TILE * 2):
                self.state = "chase"

        elif self.state == "chase":
            if dist > 1:
                dx = (px - self.x) / dist
                dy = (py - self.y) / dist
                nx = self.x + dx * self.speed * dt
                ny = self.y + dy * self.speed * dt
                if not self._blocked(nx, self.y, world):
                    self.x = nx
                if not self._blocked(self.x, ny, world):
                    self.y = ny
            if dist < TILE * 0.9:
                self.state = "attack"
            if dist > SCREEN_W and not self._on_screen(cam_x, cam_y, margin=TILE * 4):
                self.state = "idle"

        elif self.state == "attack":
            if dist > TILE * 1.5:
                self.state = "chase"

        world_rows = len(world)
        world_cols = len(world[0]) if world_rows > 0 else 1
        self.x = max(TILE, min((world_cols - 1) * TILE, self.x))
        self.y = max(TILE, min((world_rows - 1) * TILE, self.y))

    def try_attack(self, px: float, py: float) -> int:
        """Try to attack player. Returns damage if successful, 0 otherwise."""
        if self.hp <= 0 or self.state != "attack":
            return 0
        dist = math.hypot(px - self.x, py - self.y)
        if dist < TILE * 1.2 and self.cooldown <= 0:
            self.cooldown = self.attack_cd
            return self.attack
        return 0

    def take_damage(self, amount: int, source_x: float, source_y: float, particles: list) -> None:
        """Take damage and create damage-dealing particles."""
        self.hp -= amount
        self.hurt_flash = 8
        dx = self.x - source_x
        dy = self.y - source_y
        dist = max(1, math.hypot(dx, dy))
        self.knockback_vx = (dx / dist) * 6
        self.knockback_vy = (dy / dist) * 6
        for _ in range(6):
            particles.append(Particle(self.x, self.y, self.color))

    def draw(self, surf: pygame.Surface, cam_x: float, cam_y: float) -> None:
        """Draw enemy using vector draw commands."""
        if self.hp <= 0:
            return
        sx = int(self.x - cam_x)
        sy = int(self.y - cam_y)
        # Use surface dimensions instead of hardcoded SCREEN_W/SCREEN_H for split-screen support
        surf_w, surf_h = surf.get_size()
        if sx < -40 or sx > surf_w + 40 or sy < -40 or sy > surf_h + 40:
            return

        base = (255, 255, 255) if self.hurt_flash > 0 else self.color

        for cmd in self.draw_commands:
            shape = cmd[0]
            color_offset = cmd[1]
            c = _clamp_color(base, color_offset)
            args = cmd[2:]

            if shape == "circle":
                cx_off, cy_off, radius = args
                pygame.draw.circle(surf, c, (sx + cx_off, sy + cy_off), radius)
            elif shape == "rect":
                xo, yo, w, h = args
                pygame.draw.rect(surf, c, (sx + xo, sy + yo, w, h))
            elif shape == "ellipse":
                xo, yo, w, h = args
                pygame.draw.ellipse(surf, c, (sx + xo, sy + yo, w, h))
            elif shape == "line":
                x1, y1, x2, y2, width = args
                pygame.draw.line(surf, c, (sx + x1, sy + y1), (sx + x2, sy + y2), width)
            elif shape == "polygon":
                points_off = args[0]
                pts = [(sx + px_off, sy + py_off) for px_off, py_off in points_off]
                pygame.draw.polygon(surf, c, pts)

        if self.hp < self.max_hp:
            bar_w = 20
            bx = sx - bar_w // 2
            by = sy - 16
            ratio = max(0, self.hp / self.max_hp)
            pygame.draw.rect(surf, (60, 60, 60), (bx, by, bar_w, 3))
            pygame.draw.rect(surf, (220, 40, 40), (bx, by, int(bar_w * ratio), 3))
