"""Base class for all passive NPC creatures (sea, land, etc.)."""

from __future__ import annotations

import math
import random

import pygame

from src.config import TILE
from src.data import BLOCKING_TILES


class Creature:
    """Passive NPC animal that wanders its home map and can be mounted.

    Subclasses must implement ``draw()``.  All other behaviour (wander FSM,
    riding) is provided here.
    """

    def __init__(
        self,
        x: float,
        y: float,
        kind: str,
        home_map: str | tuple,
        speed: float,
        size: float,
        body_color: tuple[int, int, int],
    ) -> None:
        self.x = float(x)
        self.y = float(y)
        self.kind = kind
        self.home_map: str | tuple = home_map
        self.speed = speed
        self.size = size
        self.body_color: tuple[int, int, int] = body_color
        self.facing_right: bool = random.choice([True, False])

        # Wander FSM
        self.dest_x: float = self.x
        self.dest_y: float = self.y
        self.wander_timer: float = random.uniform(60, 180)

        # Mount state — rider_id is always None when loaded from save (transient)
        self.rider_id: int | None = None

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

        if 0 <= nc < cols and 0 <= nr < rows and world[nr][nc] not in BLOCKING_TILES:
            self.x = nx
            self.y = ny
        else:
            self.wander_timer = 0.0

    def update_riding(
        self, dx: float, dy: float, dt: float, world: list[list[int]]
    ) -> None:
        """Move this creature under player control at 1.5× its wander speed.

        Args:
            dx: Horizontal input direction (-1, 0 or 1).
            dy: Vertical input direction (-1, 0 or 1).
            dt: Frame delta time.
            world: The tile grid for collision checking.
        """
        if dx == 0 and dy == 0:
            return

        rows = len(world)
        cols = len(world[0])

        # Normalise diagonal movement
        if dx != 0 and dy != 0:
            dx *= 0.707
            dy *= 0.707

        if dx != 0:
            self.facing_right = dx > 0

        step = self.speed * 1.5 * dt
        nx = self.x + dx * step
        ny = self.y + dy * step
        nc = int(nx) // TILE
        nr = int(ny) // TILE

        if 0 <= nc < cols and 0 <= nr < rows and world[nr][nc] not in BLOCKING_TILES:
            self.x = nx
            self.y = ny

    # ------------------------------------------------------------------
    # Draw  (abstract — subclasses must override)
    # ------------------------------------------------------------------

    def draw(
        self,
        screen: pygame.Surface,
        offset_x: float,
        offset_y: float,
        ticks: int,
        rider_color: tuple[int, int, int] | None = None,
    ) -> None:
        raise NotImplementedError(
            f"{type(self).__name__} must implement draw()"
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
