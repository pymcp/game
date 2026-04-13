"""Pet companion class (cat/dog)."""

import random
import math
import pygame
from src.config import TILE, WORLD_COLS, WORLD_ROWS
from src.data import BLOCKING_TILES
from src.rendering.animator import Animator, AnimationState

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
        self.facing_direction: str = "right"
        self._is_moving: bool = False

        self._animator: Animator | None = None
        self._animator_checked: bool = False

    def _ensure_animator(self) -> None:
        """Lazy-load animator from SpriteRegistry on first use."""
        if self._animator_checked:
            return
        self._animator_checked = True
        from src.rendering.registry import SpriteRegistry

        self._animator = SpriteRegistry.get_instance().make_animator(self.kind)

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
            # Update facing direction from dominant movement axis
            if abs(dy) >= abs(dx):
                self.facing_direction = "down" if dy >= 0 else "up"
            else:
                self.facing_direction = "right" if dx > 0 else "left"
            self._is_moving = True
            col = int(self.x) // TILE
            row = int(self.y) // TILE
            if 0 <= col < WORLD_COLS and 0 <= row < WORLD_ROWS:
                if world[row][col] in BLOCKING_TILES:
                    self.x -= step_x
                    self.y -= step_y
                    self._is_moving = False
        else:
            self._is_moving = False
        self.x = max(TILE, min((WORLD_COLS - 1) * TILE, self.x))
        self.y = max(TILE, min((WORLD_ROWS - 1) * TILE, self.y))

    def draw(
        self, surf: pygame.Surface, cam_x: float, cam_y: float, ticks: int
    ) -> None:
        """Draw pet sprite."""
        sx = int(self.x - cam_x)
        sy = int(self.y - cam_y)
        surf_w, surf_h = surf.get_size()
        if (
            sx < -TILE * 2
            or sx > surf_w + TILE * 2
            or sy < -TILE * 2
            or sy > surf_h + TILE * 2
        ):
            return

        # --- Sprite path ---
        self._ensure_animator()
        from src.rendering.sprite_draw import sprite_draw

        if sprite_draw(self, surf, cam_x, cam_y, dt=1.0):
            return

        # --- Procedural fallback (draw at 32-unit scale, scale up) ---
        _TS: int = TILE // 32
        buf_sz = 64
        buf = pygame.Surface((buf_sz, buf_sz), pygame.SRCALPHA)
        buf.fill((0, 0, 0, 0))
        _sx, _sy = buf_sz // 2, buf_sz // 2
        s = self.size

        if self.kind == "cat":
            bw, bh = int(14 * s), int(8 * s)
            pygame.draw.ellipse(
                buf, self.body_color, (_sx - bw // 2, _sy - bh // 2, bw, bh)
            )
            hr = int(5 * s)
            hx = _sx + int(7 * s)
            pygame.draw.circle(buf, self.body_color, (hx, _sy - int(2 * s)), hr)
            ear_s = int(3 * s)
            pygame.draw.polygon(
                buf,
                self.body_color,
                [
                    (hx - ear_s, _sy - int(6 * s)),
                    (hx - ear_s - 2, _sy - int(10 * s)),
                    (hx - ear_s + 3, _sy - int(7 * s)),
                ],
            )
            pygame.draw.polygon(
                buf,
                self.body_color,
                [
                    (hx + ear_s, _sy - int(6 * s)),
                    (hx + ear_s + 2, _sy - int(10 * s)),
                    (hx + ear_s - 3, _sy - int(7 * s)),
                ],
            )
            pygame.draw.circle(
                buf, self.eye_color, (hx - 2, _sy - int(3 * s)), max(1, int(1.5 * s))
            )
            pygame.draw.circle(
                buf, self.eye_color, (hx + 2, _sy - int(3 * s)), max(1, int(1.5 * s))
            )
            tail_wave = math.sin(ticks * 0.008 + self.tail_phase) * 4
            pygame.draw.line(
                buf,
                self.body_color,
                (_sx - int(7 * s), _sy),
                (_sx - int(14 * s), _sy - int(4 * s) + int(tail_wave)),
                2,
            )
        else:
            bw, bh = int(16 * s), int(10 * s)
            pygame.draw.ellipse(
                buf, self.body_color, (_sx - bw // 2, _sy - bh // 2, bw, bh)
            )
            pygame.draw.circle(
                buf, self.spot_color, (_sx - int(3 * s), _sy - int(1 * s)), int(2.5 * s)
            )
            hr = int(6 * s)
            hx = _sx + int(8 * s)
            pygame.draw.circle(buf, self.body_color, (hx, _sy - int(2 * s)), hr)
            pygame.draw.ellipse(
                buf,
                self.spot_color,
                (hx + int(2 * s), _sy - int(3 * s), int(5 * s), int(4 * s)),
            )
            pygame.draw.ellipse(
                buf,
                self.body_color,
                (hx - int(5 * s), _sy - int(6 * s), int(4 * s), int(7 * s)),
            )
            pygame.draw.ellipse(
                buf,
                self.body_color,
                (hx + int(2 * s), _sy - int(6 * s), int(4 * s), int(7 * s)),
            )
            pygame.draw.circle(
                buf, self.eye_color, (hx - 2, _sy - int(4 * s)), max(1, int(1.5 * s))
            )
            pygame.draw.circle(
                buf, self.eye_color, (hx + 2, _sy - int(4 * s)), max(1, int(1.5 * s))
            )
            tail_wag = math.sin(ticks * 0.012 + self.tail_phase) * 6
            pygame.draw.line(
                buf,
                self.body_color,
                (_sx - int(8 * s), _sy - int(2 * s)),
                (_sx - int(14 * s), _sy - int(8 * s) + int(tail_wag)),
                3,
            )

        if _TS > 1:
            buf = pygame.transform.scale(buf, (buf_sz * _TS, buf_sz * _TS))
        surf.blit(buf, (sx - buf.get_width() // 2, sy - buf.get_height() // 2))
