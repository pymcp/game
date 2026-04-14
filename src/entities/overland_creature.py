"""Overland creature NPC — passive land animals that wander surface maps."""

from __future__ import annotations

import math
import random

import pygame

from src.config import TILE
from src.entities.creature import Creature

# Base speeds (world-units per second)
_SPEEDS: dict[str, float] = {
    "horse": 0.3,
}

# Visual sizes (multiplier of TILE)
_SIZES: dict[str, float] = {
    "horse": 0.9,
}

# Brown coat colours for horses
_HORSE_COLORS: list[tuple[int, int, int]] = [
    (139, 90, 43),  # chestnut
    (101, 67, 33),  # dark bay
    (180, 130, 70),  # palomino
    (60, 40, 25),  # near-black
]


class OverlandCreature(Creature):
    """A passive land animal that wanders overland maps and can be mounted."""

    def __init__(
        self,
        x: float,
        y: float,
        kind: str = "horse",
        home_map: str | tuple = "overland",
    ) -> None:
        speed = _SPEEDS.get(kind, 3.0) * random.uniform(0.85, 1.15)
        size = _SIZES.get(kind, 1.0)

        if kind == "horse":
            body_color: tuple[int, int, int] = random.choice(_HORSE_COLORS)
        else:
            body_color = (150, 120, 80)

        super().__init__(x, y, kind, home_map, speed, size, body_color)

    # ------------------------------------------------------------------
    # Draw
    # ------------------------------------------------------------------

    def draw(
        self,
        screen: pygame.Surface,
        offset_x: float,
        offset_y: float,
        ticks: int,
        rider_color: tuple[int, int, int] | None = None,
    ) -> None:
        """Draw the land creature — sprite blit when available, procedural fallback."""
        from src.rendering.animator import AnimationState

        sx = int(self.x - offset_x)
        sy = int(self.y - offset_y)
        surf_w, surf_h = screen.get_size()
        if (
            sx < -TILE * 4
            or sx > surf_w + TILE * 4
            or sy < -TILE * 4
            or sy > surf_h + TILE * 4
        ):
            return

        # --- Sprite path ---
        self._ensure_animator(self.kind)
        from src.rendering.sprite_draw import sprite_draw

        if sprite_draw(self, screen, offset_x, offset_y, dt=1.0):
            # Rider overlay drawn procedurally on top
            if rider_color is not None:
                r = int(TILE * self.size)
                body_h = r
                seat_x = sx
                seat_y = sy - body_h // 2 - 2
                pygame.draw.rect(screen, rider_color, (seat_x - 5, seat_y - 10, 10, 10))
                pygame.draw.circle(screen, (240, 200, 160), (seat_x, seat_y - 14), 5)
                for side in (-1, 1):
                    pygame.draw.rect(
                        screen, rider_color, (seat_x + side * 5, seat_y - 4, 4, 8)
                    )
            return

        # --- Procedural fallback ---
        r = int(TILE * self.size)
        c = self.body_color

        if self.kind == "horse":
            self._draw_horse(screen, sx, sy, r, c, ticks, rider_color)

    def _draw_horse(
        self,
        screen: pygame.Surface,
        sx: int,
        sy: int,
        r: int,
        c: tuple[int, int, int],
        ticks: int,
        rider_color: tuple[int, int, int] | None = None,
    ) -> None:
        """Draw a side-on horse with animated legs and optional rider."""
        bob = int(math.sin(ticks * 0.006) * 1)
        sy += bob
        flip = 1 if self.facing_right else -1

        dark = tuple(max(0, ch - 40) for ch in c)
        mane_color: tuple[int, int, int] = tuple(max(0, ch - 60) for ch in c)  # type: ignore[assignment]

        # ---- Body (wide ellipse) ----
        body_w = r * 2
        body_h = r
        body_rect = pygame.Rect(sx - body_w // 2, sy - body_h // 2, body_w, body_h)
        pygame.draw.ellipse(screen, c, body_rect)

        # ---- Legs (4 thin rects, two on each side) ----
        leg_w = max(3, r // 6)
        leg_h = r // 2 + 4
        leg_y_top = sy + body_h // 2 - 4
        # Animate front vs back legs with a slight phase offset
        leg_swing = int(math.sin(ticks * 0.015) * 4)
        for i, lx_off in enumerate([-r // 3, -r // 8, r // 8, r // 3]):
            swing = leg_swing if i % 2 == 0 else -leg_swing
            lx = sx + flip * lx_off
            pygame.draw.rect(
                screen, dark, (lx - leg_w // 2, leg_y_top + swing, leg_w, leg_h)
            )

        # ---- Neck ----
        neck_base_x = sx + flip * (r // 2)
        neck_base_y = sy - body_h // 4
        neck_tip_x = neck_base_x + flip * (r // 3)
        neck_tip_y = neck_base_y - r // 2
        pygame.draw.line(
            screen,
            c,
            (neck_base_x, neck_base_y),
            (neck_tip_x, neck_tip_y),
            max(5, r // 5),
        )

        # ---- Head ----
        head_r = max(5, r // 4)
        pygame.draw.ellipse(
            screen,
            c,
            (
                neck_tip_x - head_r + flip * head_r // 2,
                neck_tip_y - head_r,
                head_r * 2,
                int(head_r * 1.4),
            ),
        )
        # Eye
        eye_x = neck_tip_x + flip * head_r // 2
        eye_y = neck_tip_y - head_r // 3
        pygame.draw.circle(screen, (20, 20, 20), (eye_x, eye_y), max(2, head_r // 3))

        # ---- Mane (a few short strokes along the top of the neck) ----
        for i in range(4):
            t = i / 3.0
            mx = int(neck_base_x * (1 - t) + neck_tip_x * t)
            my = int(neck_base_y * (1 - t) + neck_tip_y * t)
            pygame.draw.line(screen, mane_color, (mx, my), (mx - flip * 4, my - 5), 2)

        # ---- Tail ----
        tail_base_x = sx - flip * (r - 2)
        tail_base_y = sy - body_h // 4
        tail_tip_x = tail_base_x - flip * (r // 3)
        tail_tip_y = tail_base_y + r // 3
        pygame.draw.line(
            screen, mane_color, (tail_base_x, tail_base_y), (tail_tip_x, tail_tip_y), 3
        )

        # ---- Rider seated on back ----
        if rider_color is not None:
            seat_x = sx
            seat_y = sy - body_h // 2 - 2
            # Torso
            pygame.draw.rect(screen, rider_color, (seat_x - 5, seat_y - 10, 10, 10))
            # Head
            pygame.draw.circle(screen, (240, 200, 160), (seat_x, seat_y - 14), 5)
            # Legs dangling each side
            for side in (-1, 1):
                pygame.draw.rect(
                    screen, rider_color, (seat_x + side * 5, seat_y - 4, 4, 8)
                )
