"""AI worker character that mines for the player."""

import random
import math
import pygame
from src.config import TILE, WORLD_COLS, WORLD_ROWS
from src.data import TILE_INFO, BLOCKING_TILES
from src.effects import Particle, FloatingText


class Worker:
    """An AI-controlled character that wanders and mines for the player."""

    def __init__(
        self, x: float, y: float, player_id: int = 1, home_map: str | tuple = "overland"
    ) -> None:
        self.x = float(x)
        self.y = float(y)
        self.speed = random.uniform(1.4, 2.2)
        self.player_id = player_id
        self.home_map: str | tuple = home_map
        self.xp_earned = 0

        self.body_color = tuple(random.randint(60, 220) for _ in range(3))
        self.skin_color = random.choice(
            [
                (240, 200, 160),
                (210, 170, 130),
                (180, 140, 100),
                (140, 100, 70),
                (255, 220, 185),
                (200, 155, 120),
            ]
        )
        self.hat_color = tuple(random.randint(40, 255) for _ in range(3))
        self.size_mod = random.uniform(0.8, 1.2)

        self.state = "wander"
        self.target_tile = None
        self.mine_progress = 0.0
        self.wander_timer = random.uniform(30, 120)
        self.dest_x = self.x
        self.dest_y = self.y

    def _pick_wander_dest(self) -> None:
        """Pick a new random wander destination."""
        angle = random.uniform(0, 2 * math.pi)
        dist = random.uniform(TILE * 2, TILE * 6)
        self.dest_x = max(
            TILE, min((WORLD_COLS - 1) * TILE, self.x + math.cos(angle) * dist)
        )
        self.dest_y = max(
            TILE, min((WORLD_ROWS - 1) * TILE, self.y + math.sin(angle) * dist)
        )
        self.state = "wander"

    def _find_mineable(self, world: list[list[int]]) -> tuple[int, int] | None:
        """Find the closest mineable tile nearby."""
        col = int(self.x) // TILE
        row = int(self.y) // TILE
        candidates = []
        search_r = 6
        for dr in range(-search_r, search_r + 1):
            for dc in range(-search_r, search_r + 1):
                c, r = col + dc, row + dr
                if 0 <= c < WORLD_COLS and 0 <= r < WORLD_ROWS:
                    if TILE_INFO[world[r][c]]["mineable"]:
                        candidates.append((abs(dc) + abs(dr), c, r))
        if candidates:
            candidates.sort()
            pick = random.choice(candidates[: min(5, len(candidates))])
            return (pick[1], pick[2])
        return None

    def _move_toward(
        self, dest_x: float, dest_y: float, dt: float, world: list[list[int]]
    ) -> float:
        """Move toward destination, reverting if landing on a blocked tile.
        Returns distance remaining."""
        dx = dest_x - self.x
        dy = dest_y - self.y
        dist = math.hypot(dx, dy)
        if dist > 2:
            step_x = (dx / dist) * self.speed * dt
            step_y = (dy / dist) * self.speed * dt
            self.x += step_x
            self.y += step_y
            col = int(self.x) // TILE
            row = int(self.y) // TILE
            if 0 <= col < WORLD_COLS and 0 <= row < WORLD_ROWS:
                if world[row][col] in BLOCKING_TILES:
                    self.x -= step_x
                    self.y -= step_y
                    self._pick_wander_dest()
        return dist

    def update(
        self,
        dt: float,
        world: list[list[int]],
        tile_hp: list[list[int]],
        inventory: dict[str, int],
        particles: list,
        floats: list,
    ) -> None:
        """Update worker AI and state machine."""
        from src.config import GRASS, DIRT, MOUNTAIN

        if self.state == "wander":
            dist = self._move_toward(self.dest_x, self.dest_y, dt, world)
            self.wander_timer -= dt
            if self.wander_timer <= 0 or dist <= 2:
                target = self._find_mineable(world)
                if target:
                    self.target_tile = target
                    tc, tr = target
                    self.dest_x = tc * TILE + TILE // 2
                    self.dest_y = tr * TILE + TILE // 2
                    self.state = "walk_to"
                    self.mine_progress = 0.0
                else:
                    self._pick_wander_dest()
                self.wander_timer = random.uniform(60, 180)

        elif self.state == "walk_to":
            tc, tr = self.target_tile
            if (
                not (0 <= tc < WORLD_COLS and 0 <= tr < WORLD_ROWS)
                or not TILE_INFO[world[tr][tc]]["mineable"]
            ):
                self._pick_wander_dest()
                return
            dist = self._move_toward(self.dest_x, self.dest_y, dt, world)
            if dist <= TILE * 1.2:
                self.state = "mining"
                self.mine_progress = 0.0

        elif self.state == "mining":
            tc, tr = self.target_tile
            if (
                not (0 <= tc < WORLD_COLS and 0 <= tr < WORLD_ROWS)
                or not TILE_INFO[world[tr][tc]]["mineable"]
            ):
                self._pick_wander_dest()
                return
            tile_cx = tc * TILE + TILE // 2
            tile_cy = tr * TILE + TILE // 2
            self.mine_progress += 5 * dt * 0.15
            tile_hp[tr][tc] = max(
                0, TILE_INFO[world[tr][tc]]["hp"] - self.mine_progress
            )
            if random.random() < 0.25:
                particles.append(
                    Particle(tile_cx, tile_cy, TILE_INFO[world[tr][tc]]["color"])
                )
            if tile_hp[tr][tc] <= 0:
                info = TILE_INFO[world[tr][tc]]
                if info["drop"]:
                    inventory[info["drop"]] = inventory.get(info["drop"], 0) + 1
                    floats.append(
                        FloatingText(
                            tile_cx, tile_cy, f"+1 {info['drop']}", info["drop_color"]
                        )
                    )
                    # Award XP to the player for resources mined
                    self.xp_earned += 5
                for _ in range(8):
                    particles.append(Particle(tile_cx, tile_cy, info["color"]))
                new_tile = DIRT if world[tr][tc] == MOUNTAIN else GRASS
                world[tr][tc] = new_tile
                tile_hp[tr][tc] = TILE_INFO[new_tile]["hp"]
                self._pick_wander_dest()

        self.x = max(TILE, min((WORLD_COLS - 1) * TILE, self.x))
        self.y = max(TILE, min((WORLD_ROWS - 1) * TILE, self.y))

    def draw(self, surf: pygame.Surface, cam_x: float, cam_y: float) -> None:
        """Draw worker sprite."""
        sx = int(self.x - cam_x)
        sy = int(self.y - cam_y)
        surf_w, surf_h = surf.get_size()
        if sx < -40 or sx > surf_w + 40 or sy < -40 or sy > surf_h + 40:
            return
        s = self.size_mod
        bw, bh = int(16 * s), int(22 * s)
        pygame.draw.rect(
            surf,
            self.body_color,
            (sx - bw // 2, sy - int(10 * s), bw, bh),
            border_radius=3,
        )
        head_r = int(7 * s)
        pygame.draw.circle(surf, self.skin_color, (sx, sy - int(14 * s)), head_r)
        hat_w, hat_h = int(14 * s), int(5 * s)
        pygame.draw.rect(
            surf, self.hat_color, (sx - hat_w // 2, sy - int(20 * s), hat_w, hat_h)
        )
        pygame.draw.line(
            surf,
            (160, 120, 60),
            (sx + int(8 * s), sy - int(4 * s)),
            (sx + int(14 * s), sy - int(12 * s)),
            2,
        )
