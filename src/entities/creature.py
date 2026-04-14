"""Concrete Creature class — passive NPC animals that wander their home map."""

from __future__ import annotations

import enum
import math
import random

import pygame

from src.config import TILE
from src.data import BLOCKING_TILES
from src.rendering.animator import Animator, AnimationState


class WanderState(enum.Enum):
    """States for the creature wander finite-state machine."""

    IDLE = "idle"
    WALKING = "walking"


class Creature:
    """Passive NPC animal that wanders its home map and can be mounted.

    All behaviour (wander FSM, riding, drawing) is handled here.
    Per-type properties (speed, size, colour, mountability) are drawn from
    ``src.data.creatures.CREATURE_TYPES``.
    """

    def __init__(
        self,
        x: float,
        y: float,
        kind: str,
        home_map: str | tuple,
    ) -> None:
        from src.data.creatures import CREATURE_TYPES

        type_data = CREATURE_TYPES[kind]

        self.x = float(x)
        self.y = float(y)
        self.kind = kind
        self.home_map: str | tuple = home_map

        # Per-type properties — speed gets ±15% variance at spawn time
        self.speed: float = type_data["speed"] * random.uniform(0.85, 1.15)
        self.size: float = type_data["size"]
        self.body_color: tuple[int, int, int] = type_data["color_fn"]()
        self.mount_speed_mult: float = type_data["mount_speed_mult"]
        self.mountable: bool = type_data["mountable"]

        self.facing_direction: str = random.choice(["left", "right"])

        # Wander FSM
        self.dest_x: float = self.x
        self.dest_y: float = self.y
        self._wander_state: WanderState = WanderState.IDLE
        self._idle_timer: float = random.uniform(3.0, 8.0)

        # Mount state — rider_id is always None on load (transient)
        self.rider_id: int | None = None

        # Sprite animator — lazily initialised from SpriteRegistry on first use
        self._animator: Animator | None = None
        self._animator_checked: bool = False

        # Set each update tick so draw() can animate correctly
        self._is_moving: bool = False

    # ------------------------------------------------------------------
    # Backward-compat facing helpers
    # ------------------------------------------------------------------

    @property
    def facing_right(self) -> bool:
        return self.facing_direction in ("right", "up")

    @facing_right.setter
    def facing_right(self, value: bool) -> None:
        self.facing_direction = "right" if value else "left"

    def _update_facing(self, dx: float, dy: float) -> None:
        if dx == 0 and dy == 0:
            return
        if abs(dy) >= abs(dx):
            self.facing_direction = "down" if dy >= 0 else "up"
        else:
            self.facing_direction = "right" if dx > 0 else "left"

    # ------------------------------------------------------------------
    # Sprite animator helper
    # ------------------------------------------------------------------

    def _ensure_animator(self, sprite_id: str) -> None:
        if self._animator_checked:
            return
        self._animator_checked = True
        from src.rendering.registry import SpriteRegistry

        self._animator = SpriteRegistry.get_instance().make_animator(sprite_id)

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update(self, dt: float, world: list[list[int]]) -> None:
        """Advance wander FSM and move toward destination."""
        rows = len(world)
        cols = len(world[0])

        if self._wander_state is WanderState.IDLE:
            self._idle_timer -= dt
            if self._idle_timer <= 0:
                self._pick_wander_dest(cols, rows)
                self._wander_state = WanderState.WALKING
            self._is_moving = False
            return

        # WALKING state — move toward destination
        dx = self.dest_x - self.x
        dy = self.dest_y - self.y
        dist = math.hypot(dx, dy)

        if dist < 4:
            self._wander_state = WanderState.IDLE
            self._idle_timer = random.uniform(3.0, 8.0)
            self._is_moving = False
            return

        self._is_moving = True
        step = self.speed * dt
        nx = self.x + (dx / dist) * step
        ny = self.y + (dy / dist) * step

        nc = int(nx) // TILE
        nr = int(ny) // TILE

        if dx != 0 or dy != 0:
            self._update_facing(dx, dy)

        if 0 <= nc < cols and 0 <= nr < rows and world[nr][nc] not in BLOCKING_TILES:
            self.x = nx
            self.y = ny
        else:
            # Blocked — rest before trying again
            self._wander_state = WanderState.IDLE
            self._idle_timer = random.uniform(3.0, 8.0)

    def update_riding(
        self,
        dx: float,
        dy: float,
        dt: float,
        world: list[list[int]],
        player_speed: float = 3.2,
    ) -> None:
        """Move this creature under player control at mount_speed_mult × player speed."""
        if dx == 0 and dy == 0:
            self._is_moving = False
            return

        rows = len(world)
        cols = len(world[0])

        if dx != 0 and dy != 0:
            dx *= 0.707
            dy *= 0.707

        if dx != 0 or dy != 0:
            self._update_facing(dx, dy)

        step = player_speed * self.mount_speed_mult * dt
        nx = self.x + dx * step
        ny = self.y + dy * step
        nc = int(nx) // TILE
        nr = int(ny) // TILE

        if 0 <= nc < cols and 0 <= nr < rows and world[nr][nc] not in BLOCKING_TILES:
            self.x = nx
            self.y = ny
            self._is_moving = True

    # ------------------------------------------------------------------
    # Draw — dispatches to per-kind methods; sprite blit preferred
    # ------------------------------------------------------------------

    def draw(
        self,
        screen: pygame.Surface,
        offset_x: float,
        offset_y: float,
        ticks: int,
        rider_color: tuple[int, int, int] | None = None,
    ) -> None:
        """Draw the creature — sprite blit when available, procedural fallback."""
        sx = int(self.x - offset_x)
        sy = int(self.y - offset_y)
        surf_w, surf_h = screen.get_size()

        cull = TILE * 5
        if sx < -cull or sx > surf_w + cull or sy < -cull or sy > surf_h + cull:
            return

        # --- Sprite path ---
        self._ensure_animator(self.kind)
        from src.rendering.sprite_draw import sprite_draw

        if sprite_draw(self, screen, offset_x, offset_y, dt=1.0):
            self._draw_rider_overlay_sprite(screen, sx, sy, rider_color)
            return

        # --- Procedural fallback ---
        r = int(TILE * self.size)
        c = self.body_color

        if self.kind == "horse":
            self._draw_horse(screen, sx, sy, r, c, ticks, rider_color)
        elif self.kind == "grasshopper":
            self._draw_grasshopper(screen, sx, sy, r, c, ticks, rider_color)
        elif self.kind == "dolphin":
            bright = tuple(min(255, ch + 60) for ch in c)
            self._draw_dolphin(screen, sx, sy, r, c, bright, ticks, rider_color)
        elif self.kind == "fish":
            bright = tuple(min(255, ch + 60) for ch in c)
            self._draw_fish(screen, sx, sy, r, c, bright)
        elif self.kind == "jellyfish":
            self._draw_jellyfish(screen, sx, sy, r, c, ticks)

    def _draw_rider_overlay_sprite(
        self,
        screen: pygame.Surface,
        sx: int,
        sy: int,
        rider_color: tuple[int, int, int] | None,
    ) -> None:
        """Generic rider overlay drawn on top of a sprite-path creature."""
        if rider_color is None:
            return
        r = int(TILE * self.size)
        body_h = r
        seat_x = sx
        seat_y = sy - body_h // 2 - 2
        pygame.draw.rect(screen, rider_color, (seat_x - 5, seat_y - 10, 10, 10))
        pygame.draw.circle(screen, (240, 200, 160), (seat_x, seat_y - 14), 5)
        for side in (-1, 1):
            pygame.draw.rect(screen, rider_color, (seat_x + side * 5, seat_y - 4, 4, 8))

    # ------------------------------------------------------------------
    # Per-kind procedural draw methods
    # ------------------------------------------------------------------

    def _draw_horse(
        self,
        screen: pygame.Surface,
        sx: int,
        sy: int,
        r: int,
        c: tuple[int, int, int],
        ticks: int,
        rider_color: tuple[int, int, int] | None,
    ) -> None:
        bob = int(math.sin(ticks * 0.006) * 1)
        sy += bob
        flip = 1 if self.facing_right else -1

        dark: tuple = tuple(max(0, ch - 40) for ch in c)
        mane_color: tuple[int, int, int] = tuple(max(0, ch - 60) for ch in c)  # type: ignore[assignment]

        body_w = r * 2
        body_h = r
        pygame.draw.ellipse(
            screen, c, (sx - body_w // 2, sy - body_h // 2, body_w, body_h)
        )

        leg_w = max(3, r // 6)
        leg_h = r // 2 + 4
        leg_y_top = sy + body_h // 2 - 4
        leg_swing = int(math.sin(ticks * 0.015) * 4)
        for i, lx_off in enumerate([-r // 3, -r // 8, r // 8, r // 3]):
            swing = leg_swing if i % 2 == 0 else -leg_swing
            lx = sx + flip * lx_off
            pygame.draw.rect(
                screen, dark, (lx - leg_w // 2, leg_y_top + swing, leg_w, leg_h)
            )

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
        eye_x = neck_tip_x + flip * head_r // 2
        eye_y = neck_tip_y - head_r // 3
        pygame.draw.circle(screen, (20, 20, 20), (eye_x, eye_y), max(2, head_r // 3))

        for i in range(4):
            t = i / 3.0
            mx = int(neck_base_x * (1 - t) + neck_tip_x * t)
            my = int(neck_base_y * (1 - t) + neck_tip_y * t)
            pygame.draw.line(screen, mane_color, (mx, my), (mx - flip * 4, my - 5), 2)

        tail_base_x = sx - flip * (r - 2)
        tail_base_y = sy - body_h // 4
        tail_tip_x = tail_base_x - flip * (r // 3)
        tail_tip_y = tail_base_y + r // 3
        pygame.draw.line(
            screen, mane_color, (tail_base_x, tail_base_y), (tail_tip_x, tail_tip_y), 3
        )

        if rider_color is not None:
            seat_x = sx
            seat_y = sy - body_h // 2 - 2
            pygame.draw.rect(screen, rider_color, (seat_x - 5, seat_y - 10, 10, 10))
            pygame.draw.circle(screen, (240, 200, 160), (seat_x, seat_y - 14), 5)
            for side in (-1, 1):
                pygame.draw.rect(
                    screen, rider_color, (seat_x + side * 5, seat_y - 4, 4, 8)
                )

    def _draw_grasshopper(
        self,
        screen: pygame.Surface,
        sx: int,
        sy: int,
        r: int,
        c: tuple[int, int, int],
        ticks: int,
        rider_color: tuple[int, int, int] | None,
    ) -> None:
        """Side-on grasshopper: oval body, long articulated hind legs, antennae."""
        bob = int(math.sin(ticks * 0.008) * 1)
        sy += bob
        flip = 1 if self.facing_right else -1

        dark: tuple = tuple(max(0, ch - 50) for ch in c)
        light: tuple = tuple(min(255, ch + 40) for ch in c)

        # Body — elongated horizontal oval
        body_w = int(r * 1.6)
        body_h = int(r * 0.7)
        pygame.draw.ellipse(
            screen, c, (sx - body_w // 2, sy - body_h // 2, body_w, body_h)
        )

        # Head — small circle at front
        head_r = max(4, r // 4)
        head_x = sx + flip * (body_w // 2)
        head_y = sy - body_h // 4
        pygame.draw.circle(screen, c, (head_x, head_y), head_r)
        # Compound eye
        eye_x = head_x + flip * (head_r // 2)
        eye_y = head_y - head_r // 3
        pygame.draw.circle(screen, (20, 20, 20), (eye_x, eye_y), max(2, head_r // 3))

        # Antennae — two thin lines from head
        ant_len = body_h + 4
        for off in (-1, 1):
            ax0 = head_x + flip * (head_r - 1)
            ay0 = head_y - head_r // 2
            ax1 = ax0 + flip * ant_len
            ay1 = ay0 - ant_len // 2 + off * 3
            pygame.draw.line(screen, dark, (ax0, ay0), (ax1, ay1), 1)

        # Short front legs (2 pairs near head)
        leg_w = max(2, r // 8)
        leg_top = sy + body_h // 2 - 2
        for lx_off in [body_w // 3, body_w // 6]:
            lx = sx + flip * lx_off
            pygame.draw.rect(
                screen, dark, (lx - leg_w // 2, leg_top, leg_w, body_h // 2)
            )

        # Long articulated hind legs
        hind_swing = int(math.sin(ticks * 0.012) * 5)
        thigh_len = int(r * 0.9)
        shin_len = int(r * 1.1)
        # Upper segment goes up-back, lower goes down-forward
        for side_off in [-body_w // 4, 0]:
            kx0 = sx - flip * (body_w // 4 - side_off)
            ky0 = sy + body_h // 3
            # Knee above body
            kx1 = kx0 - flip * (thigh_len // 2)
            ky1 = ky0 - thigh_len + hind_swing
            # Foot
            kx2 = kx1 + flip * shin_len
            ky2 = ky1 + shin_len - hind_swing // 2
            pygame.draw.line(screen, dark, (kx0, ky0), (kx1, ky1), max(2, leg_w))
            pygame.draw.line(screen, dark, (kx1, ky1), (kx2, ky2), max(2, leg_w))

        # Wing hint — flat translucent-looking polygon on back
        wing_color: tuple = tuple(min(255, ch + 80) for ch in c)
        wing_pts = [
            (sx - flip * (body_w // 6), sy - body_h // 2),
            (sx - flip * (body_w // 2), sy - body_h // 2 - body_h // 3),
            (sx + flip * (body_w // 6), sy - body_h // 4),
        ]
        pygame.draw.polygon(screen, wing_color, wing_pts)

        if rider_color is not None:
            seat_x = sx
            seat_y = sy - body_h // 2 - 2
            pygame.draw.rect(screen, rider_color, (seat_x - 4, seat_y - 9, 8, 9))
            pygame.draw.circle(screen, (240, 200, 160), (seat_x, seat_y - 12), 4)
            for side in (-1, 1):
                pygame.draw.rect(
                    screen, rider_color, (seat_x + side * 4, seat_y - 3, 3, 7)
                )

    def _draw_dolphin(
        self,
        screen: pygame.Surface,
        sx: int,
        sy: int,
        r: int,
        c: tuple,
        bright: tuple,
        ticks: int,
        rider_color: tuple[int, int, int] | None,
    ) -> None:
        bob = int(math.sin(ticks * 0.005) * 2)
        sy += bob
        flip = 1 if self.facing_right else -1
        pygame.draw.ellipse(screen, c, (sx - r, sy - r // 2, r * 2, r))
        pygame.draw.polygon(
            screen,
            bright,
            [
                (sx, sy - r // 2),
                (sx + flip * r // 2, sy - r),
                (sx + flip * r // 3, sy - r // 2),
            ],
        )
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
        eye_x = sx + flip * r // 2
        pygame.draw.circle(screen, (20, 20, 30), (eye_x, sy - 2), max(2, r // 5))
        if rider_color is not None:
            seat_x = sx + flip * (r // 4)
            seat_y = sy - r // 2 - 2
            pygame.draw.rect(screen, rider_color, (seat_x - 4, seat_y - 9, 8, 9))
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
        pygame.draw.ellipse(screen, c, (sx - r, sy - r // 2, r * 2, r))
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
        pygame.draw.circle(screen, c, (sx, sy), r)
        dark: tuple = tuple(max(0, ch - 40) for ch in c)
        pygame.draw.ellipse(screen, dark, (sx - r, sy - 2, r * 2, r))
        tentacle_color: tuple = tuple(max(0, ch - 60) for ch in c)
        for i in range(4):
            angle = (i / 4) * math.pi
            tx = sx + int(math.cos(math.pi + angle) * r * 0.7)
            wave = int(math.sin(ticks * 0.005 + i * 1.3) * 3)
            pygame.draw.line(
                screen, tentacle_color, (tx, sy), (tx + wave, sy + r * 2), 1
            )

    # ------------------------------------------------------------------
    # Wander helper
    # ------------------------------------------------------------------

    def _pick_wander_dest(self, cols: int, rows: int) -> None:
        """Choose a new random destination within a short range."""
        angle = random.uniform(0, 2 * math.pi)
        dist = random.uniform(TILE * 1.5, TILE * 4)
        self.dest_x = max(TILE, min((cols - 1) * TILE, self.x + math.cos(angle) * dist))
        self.dest_y = max(TILE, min((rows - 1) * TILE, self.y + math.sin(angle) * dist))
