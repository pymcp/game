"""Pet companion class (cat/dog)."""

import random
import math
import pygame
from src.config import TILE, WORLD_COLS, WORLD_ROWS
from src.data import BLOCKING_TILES

# Pet color palettes
CAT_COLORS = [
    (255, 165, 0),
    (80, 80, 80),
    (220, 220, 220),
    (180, 120, 50),
    (50, 50, 50),
    (255, 200, 150),
    (100, 100, 100),
    (200, 160, 80),
]

DOG_COLORS = [
    (180, 130, 70),
    (100, 70, 40),
    (220, 200, 170),
    (60, 60, 60),
    (200, 180, 150),
    (140, 100, 60),
    (90, 60, 30),
    (170, 150, 130),
]


class Pet:
    """A cat or dog that follows the player."""

    def __init__(
        self, x: float, y: float, kind: str = "cat", home_map: str | tuple = "overland"
    ) -> None:
        self.x = float(x)
        self.y = float(y)
        self.kind = kind
        self.speed = random.uniform(2.8, 3.6)
        self.home_map: str | tuple = home_map

        if kind == "cat":
            self.body_color = random.choice(CAT_COLORS)
            self.eye_color = random.choice(
                [(50, 200, 50), (200, 180, 30), (80, 160, 220)]
            )
            self.size = random.uniform(0.7, 1.0)
        else:
            self.body_color = random.choice(DOG_COLORS)
            self.eye_color = random.choice([(60, 40, 20), (40, 30, 15), (80, 60, 30)])
            self.size = random.uniform(0.85, 1.2)

        self.spot_color = tuple(
            min(255, self.body_color[i] + random.randint(-40, 40)) for i in range(3)
        )
        self.tail_phase = random.uniform(0, math.pi * 2)
        self.follow_offset_x = random.uniform(-20, 20)
        self.follow_offset_y = random.uniform(10, 30)

    def update(
        self, dt: float, target_x: float, target_y: float, world: list[list[int]]
    ) -> None:
        """Update pet position to follow player."""
        dest_x = target_x + self.follow_offset_x
        dest_y = target_y + self.follow_offset_y
        dx = dest_x - self.x
        dy = dest_y - self.y
        dist = math.hypot(dx, dy)
        if dist > 18:
            move_speed = self.speed * dt
            if dist > TILE * 5:
                move_speed *= 2.5
            step_x = (dx / dist) * move_speed
            step_y = (dy / dist) * move_speed
            self.x += step_x
            self.y += step_y
            col = int(self.x) // TILE
            row = int(self.y) // TILE
            if 0 <= col < WORLD_COLS and 0 <= row < WORLD_ROWS:
                if world[row][col] in BLOCKING_TILES:
                    self.x -= step_x
                    self.y -= step_y
        self.x = max(TILE, min((WORLD_COLS - 1) * TILE, self.x))
        self.y = max(TILE, min((WORLD_ROWS - 1) * TILE, self.y))

    def draw(
        self, surf: pygame.Surface, cam_x: float, cam_y: float, ticks: int
    ) -> None:
        """Draw pet sprite."""
        sx = int(self.x - cam_x)
        sy = int(self.y - cam_y)
        surf_w, surf_h = surf.get_size()
        if sx < -40 or sx > surf_w + 40 or sy < -40 or sy > surf_h + 40:
            return
        s = self.size

        if self.kind == "cat":
            bw, bh = int(14 * s), int(8 * s)
            pygame.draw.ellipse(
                surf, self.body_color, (sx - bw // 2, sy - bh // 2, bw, bh)
            )
            hr = int(5 * s)
            hx = sx + int(7 * s)
            pygame.draw.circle(surf, self.body_color, (hx, sy - int(2 * s)), hr)
            ear_s = int(3 * s)
            pygame.draw.polygon(
                surf,
                self.body_color,
                [
                    (hx - ear_s, sy - int(6 * s)),
                    (hx - ear_s - 2, sy - int(10 * s)),
                    (hx - ear_s + 3, sy - int(7 * s)),
                ],
            )
            pygame.draw.polygon(
                surf,
                self.body_color,
                [
                    (hx + ear_s, sy - int(6 * s)),
                    (hx + ear_s + 2, sy - int(10 * s)),
                    (hx + ear_s - 3, sy - int(7 * s)),
                ],
            )
            pygame.draw.circle(
                surf, self.eye_color, (hx - 2, sy - int(3 * s)), max(1, int(1.5 * s))
            )
            pygame.draw.circle(
                surf, self.eye_color, (hx + 2, sy - int(3 * s)), max(1, int(1.5 * s))
            )
            tail_wave = math.sin(ticks * 0.008 + self.tail_phase) * 4
            pygame.draw.line(
                surf,
                self.body_color,
                (sx - int(7 * s), sy),
                (sx - int(14 * s), sy - int(4 * s) + int(tail_wave)),
                2,
            )
        else:
            bw, bh = int(16 * s), int(10 * s)
            pygame.draw.ellipse(
                surf, self.body_color, (sx - bw // 2, sy - bh // 2, bw, bh)
            )
            pygame.draw.circle(
                surf, self.spot_color, (sx - int(3 * s), sy - int(1 * s)), int(2.5 * s)
            )
            hr = int(6 * s)
            hx = sx + int(8 * s)
            pygame.draw.circle(surf, self.body_color, (hx, sy - int(2 * s)), hr)
            pygame.draw.ellipse(
                surf,
                self.spot_color,
                (hx + int(2 * s), sy - int(3 * s), int(5 * s), int(4 * s)),
            )
            pygame.draw.ellipse(
                surf,
                self.body_color,
                (hx - int(5 * s), sy - int(6 * s), int(4 * s), int(7 * s)),
            )
            pygame.draw.ellipse(
                surf,
                self.body_color,
                (hx + int(2 * s), sy - int(6 * s), int(4 * s), int(7 * s)),
            )
            pygame.draw.circle(
                surf, self.eye_color, (hx - 2, sy - int(4 * s)), max(1, int(1.5 * s))
            )
            pygame.draw.circle(
                surf, self.eye_color, (hx + 2, sy - int(4 * s)), max(1, int(1.5 * s))
            )
            tail_wag = math.sin(ticks * 0.012 + self.tail_phase) * 6
            pygame.draw.line(
                surf,
                self.body_color,
                (sx - int(8 * s), sy - int(2 * s)),
                (sx - int(14 * s), sy - int(8 * s) + int(tail_wag)),
                3,
            )
