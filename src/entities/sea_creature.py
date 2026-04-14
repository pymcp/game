"""Sea creature NPC — non-hostile sea life that wanders underwater maps."""

import math
import random

import pygame

from src.config import TILE
from src.entities.creature import Creature

# Speeds (world-units per second)
_SPEEDS: dict[str, float] = {
    "dolphin": 0.9,
    "fish": 1.0,
    "jellyfish": 0.4,
}

# Visual sizes (pixels, relative to TILE)
_SIZES: dict[str, float] = {
    "dolphin": 1.95,
    "fish": 0.35,
    "jellyfish": 0.40,
}


class SeaCreature(Creature):
    """A passive sea creature that wanders its underwater home map."""

    def __init__(
        self,
        x: float,
        y: float,
        kind: str = "fish",
        home_map: str | tuple = "overland",
    ) -> None:
        speed = _SPEEDS.get(kind, 2.5) * random.uniform(0.85, 1.15)
        size = _SIZES.get(kind, 0.40)

        if kind == "dolphin":
            body_color: tuple[int, int, int] = (60, 130, 200)
        elif kind == "fish":
            body_color = random.choice(
                [(240, 150, 30), (80, 200, 80), (180, 60, 200), (60, 200, 200)]
            )
        else:  # jellyfish
            body_color = random.choice([(220, 80, 200), (180, 80, 255), (80, 200, 240)])

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
        """Draw the sea creature — sprite blit when available, procedural fallback."""
        from src.rendering.animator import AnimationState

        sx = int(self.x - offset_x)
        sy = int(self.y - offset_y)
        surf_w, surf_h = screen.get_size()
        if (
            sx < -TILE * 5
            or sx > surf_w + TILE * 5
            or sy < -TILE * 3
            or sy > surf_h + TILE * 3
        ):
            return

        # --- Sprite path ---
        self._ensure_animator(self.kind)
        from src.rendering.sprite_draw import sprite_draw

        if sprite_draw(self, screen, offset_x, offset_y, dt=1.0):
            # Rider overlay drawn procedurally on top of the base sprite
            if rider_color is not None and self.kind == "dolphin":
                r = int(__import__("src.config", fromlist=["TILE"]).TILE * self.size)
                flip = 1 if self.facing_right else -1
                seat_x = sx + flip * (r // 4)
                seat_y = sy - r // 2 - 2
                pygame.draw.rect(screen, rider_color, (seat_x - 4, seat_y - 9, 8, 9))
                pygame.draw.circle(screen, (240, 200, 160), (seat_x, seat_y - 12), 5)
            return

        # --- Procedural fallback ---
        r = int(__import__("src.config", fromlist=["TILE"]).TILE * self.size)
        c = self.body_color
        bright = tuple(min(255, ch + 60) for ch in c)

        if self.kind == "dolphin":
            self._draw_dolphin(screen, sx, sy, r, c, bright, ticks, rider_color)
        elif self.kind == "fish":
            self._draw_fish(screen, sx, sy, r, c, bright)
        else:
            self._draw_jellyfish(screen, sx, sy, r, c, ticks)

    def _draw_dolphin(
        self,
        screen: pygame.Surface,
        sx: int,
        sy: int,
        r: int,
        c: tuple,
        bright: tuple,
        ticks: int,
        rider_color: tuple[int, int, int] | None = None,
    ) -> None:
        bob = int(math.sin(ticks * 0.005) * 2)
        sy += bob
        flip = 1 if self.facing_right else -1
        # Body ellipse
        pygame.draw.ellipse(screen, c, (sx - r, sy - r // 2, r * 2, r))
        # Dorsal fin
        pygame.draw.polygon(
            screen,
            bright,
            [
                (sx, sy - r // 2),
                (sx + flip * r // 2, sy - r),
                (sx + flip * r // 3, sy - r // 2),
            ],
        )
        # Tail fin
        tail_x = sx - flip * r
        pygame.draw.polygon(
            screen,
            c,
            [
                (tail_x, sy),
                (tail_x - flip * r // 2, sy - r // 2),
                (tail_x - flip * r // 2, sy + r // 2),
            ],
        )
        # Eye
        eye_x = sx + flip * r // 2
        pygame.draw.circle(screen, (20, 20, 30), (eye_x, sy - 2), max(2, r // 5))
        # Rider seated on the dorsal area
        if rider_color is not None:
            seat_x = sx + flip * (r // 4)
            seat_y = sy - r // 2 - 2
            # Torso
            pygame.draw.rect(screen, rider_color, (seat_x - 4, seat_y - 9, 8, 9))
            # Head
            pygame.draw.circle(screen, (240, 200, 160), (seat_x, seat_y - 12), 5)

    def _draw_fish(
        self,
        screen: pygame.Surface,
        sx: int,
        sy: int,
        r: int,
        c: tuple,
        bright: tuple,
    ) -> None:
        flip = 1 if self.facing_right else -1
        # Body
        pygame.draw.ellipse(screen, c, (sx - r, sy - r // 2, r * 2, r))
        # Tail
        tail_x = sx - flip * r
        pygame.draw.polygon(
            screen,
            bright,
            [
                (tail_x, sy),
                (tail_x - flip * r // 2, sy - r // 2),
                (tail_x - flip * r // 2, sy + r // 2),
            ],
        )
        # Eye
        eye_x = sx + flip * (r // 2)
        pygame.draw.circle(screen, (240, 240, 240), (eye_x, sy - 2), max(2, r // 4))
        pygame.draw.circle(screen, (10, 10, 10), (eye_x, sy - 2), max(1, r // 6))

    def _draw_jellyfish(
        self,
        screen: pygame.Surface,
        sx: int,
        sy: int,
        r: int,
        c: tuple,
        ticks: int,
    ) -> None:
        bob = int(math.sin(ticks * 0.004) * 3)
        sy += bob
        # Bell (top half circle)
        pygame.draw.circle(screen, c, (sx, sy), r)
        # Cover bottom half with slightly darker fill
        dark = tuple(max(0, ch - 40) for ch in c)
        pygame.draw.ellipse(screen, dark, (sx - r, sy - 2, r * 2, r))
        # Trailing tentacles
        tentacle_color = tuple(max(0, ch - 60) for ch in c)
        for i in range(4):
            angle = (i / 4) * math.pi  # spread across bottom
            tx = sx + int(math.cos(math.pi + angle) * r * 0.7)
            wave = int(math.sin(ticks * 0.005 + i * 1.3) * 3)
            pygame.draw.line(
                screen, tentacle_color, (tx, sy), (tx + wave, sy + r * 2), 1
            )
