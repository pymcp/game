"""Sea creature NPC — non-hostile sea life that wanders underwater maps."""

import math
import random

import pygame

from src.config import TILE
from src.data import BLOCKING_TILES

# Speeds (world-units per second)
_SPEEDS: dict[str, float] = {
    "dolphin": 3.5,
    "fish": 4.0,
    "jellyfish": 1.5,
}

# Visual sizes (pixels, relative to TILE)
_SIZES: dict[str, float] = {
    "dolphin": 1.95,
    "fish": 0.35,
    "jellyfish": 0.40,
}


class SeaCreature:
    """A passive sea creature that wanders its underwater home map."""

    def __init__(
        self,
        x: float,
        y: float,
        kind: str = "fish",
        home_map: str | tuple = "overland",
    ) -> None:
        self.x = float(x)
        self.y = float(y)
        self.kind = kind
        self.home_map: str | tuple = home_map
        self.speed: float = _SPEEDS.get(kind, 2.5) * random.uniform(0.85, 1.15)
        self.size: float = _SIZES.get(kind, 0.40)

        # Wander FSM
        self.dest_x: float = self.x
        self.dest_y: float = self.y
        self.wander_timer: float = random.uniform(60, 180)

        # Visual
        if kind == "dolphin":
            base = (60, 130, 200)
        elif kind == "fish":
            base = random.choice(
                [(240, 150, 30), (80, 200, 80), (180, 60, 200), (60, 200, 200)]
            )
        else:  # jellyfish
            base = random.choice([(220, 80, 200), (180, 80, 255), (80, 200, 240)])

        self.body_color: tuple[int, int, int] = base
        self.facing_right: bool = random.choice([True, False])

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update(self, dt: float, world: list[list[int]]) -> None:
        """Advance wander FSM and move toward destination."""
        rows = len(world)
        cols = len(world[0])

        self.wander_timer -= dt
        if self.wander_timer <= 0:
            self._pick_wander_dest(cols, rows)

        dx = self.dest_x - self.x
        dy = self.dest_y - self.y
        dist = math.hypot(dx, dy)

        if dist < 4:
            self.wander_timer = 0.0
            return

        step = self.speed * dt
        nx = self.x + (dx / dist) * step
        ny = self.y + (dy / dist) * step

        nc = int(nx) // TILE
        nr = int(ny) // TILE

        if dx != 0:
            self.facing_right = dx > 0

        # Collision: skip REEF tiles
        if 0 <= nc < cols and 0 <= nr < rows and world[nr][nc] not in BLOCKING_TILES:
            self.x = nx
            self.y = ny
        else:
            self.wander_timer = 0.0  # pick a new destination next frame

    # ------------------------------------------------------------------
    # Draw
    # ------------------------------------------------------------------

    def draw(
        self,
        screen: pygame.Surface,
        offset_x: float,
        offset_y: float,
        ticks: int,
    ) -> None:
        """Draw the sea creature at its world position adjusted by camera offset."""
        sx = int(self.x - offset_x)
        sy = int(self.y - offset_y)
        r = int(TILE * self.size)
        c = self.body_color
        bright = tuple(min(255, ch + 60) for ch in c)

        if self.kind == "dolphin":
            self._draw_dolphin(screen, sx, sy, r, c, bright, ticks)
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
    ) -> None:
        bob = int(math.sin(ticks * 0.005) * 2)
        sy += bob
        flip = -1 if self.facing_right else 1
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

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _pick_wander_dest(self, cols: int, rows: int) -> None:
        """Choose a new random destination within the map bounds."""
        angle = random.uniform(0, 2 * math.pi)
        dist = random.uniform(TILE * 3, TILE * 8)
        self.dest_x = max(TILE, min((cols - 1) * TILE, self.x + math.cos(angle) * dist))
        self.dest_y = max(TILE, min((rows - 1) * TILE, self.y + math.sin(angle) * dist))
        self.wander_timer = random.uniform(60, 180)
