"""Player character class."""

import math
import pygame
from src.config import TILE, WORLD_COLS, WORLD_ROWS, SCREEN_W, SCREEN_H
from src.data import PICKAXES, WEAPONS, UPGRADE_COSTS, WEAPON_UNLOCK_COSTS, TILE_INFO
from src.world import try_spend, xp_for_level, hits_blocking, out_of_bounds
from src.effects import Particle, FloatingText


class Player:
    """The player character."""

    COLLISION_HALF = 10

    def __init__(self, x, y, player_id=1):
        """Initialize player.

        Args:
            x, y: Starting position
            player_id: 1 for WASD controls, 2 for arrow keys + numpad
        """
        self.x = float(x)
        self.y = float(y)
        self.player_id = player_id
        self.speed = 3.2

        # Equipment
        self.pick_level = 0
        self.weapon_level = 0
        self.weapon_cooldown = 0.0

        # Inventory
        self.inventory = {}

        # Health / XP
        self.hp = 100
        self.max_hp = 100
        self.xp = 0
        self.level = 1
        self.xp_next = xp_for_level(self.level)
        self.hurt_timer = 0.0

        # Facing direction (last non-zero movement)
        self.facing_dx = 1.0
        self.facing_dy = 0.0

        # Mining
        self.mining_target = None
        self.mining_progress = 0.0

    # -- upgrades ----------------------------------------------------------

    def try_upgrade_pick(self):
        """Attempt to upgrade pickaxe if cost is affordable."""
        if self.pick_level < len(PICKAXES) - 1:
            if try_spend(self.inventory, UPGRADE_COSTS[self.pick_level]):
                self.pick_level += 1
                return True
        return False

    def try_upgrade_weapon(self):
        """Attempt to unlock next weapon if cost is affordable."""
        if self.weapon_level < len(WEAPONS) - 1:
            if try_spend(self.inventory, WEAPON_UNLOCK_COSTS[self.weapon_level]):
                self.weapon_level += 1
                return True
        return False

    # -- movement / collision ----------------------------------------------

    def update_movement(self, keys, dt, world):
        """Handle input and collision.

        Player 1: WASD or Arrow keys
        Player 2: Arrow keys or Numpad
        """
        from src.config import GRASS, DIRT, MOUNTAIN

        dx = dy = 0
        if self.player_id == 1:
            # Player 1: WASD + arrow keys
            if keys[pygame.K_a] or keys[pygame.K_LEFT]:
                dx -= 1
            if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
                dx += 1
            if keys[pygame.K_w] or keys[pygame.K_UP]:
                dy -= 1
            if keys[pygame.K_s] or keys[pygame.K_DOWN]:
                dy += 1
        else:
            # Player 2: Arrow keys + Numpad (2,4,6,8 for 4-way, 1/3/7/9 for diagonals)
            if keys[pygame.K_LEFT] or keys[pygame.K_KP_4]:
                dx -= 1
            if keys[pygame.K_RIGHT] or keys[pygame.K_KP_6]:
                dx += 1
            if keys[pygame.K_UP] or keys[pygame.K_KP_8]:
                dy -= 1
            if keys[pygame.K_DOWN] or keys[pygame.K_KP_2]:
                dy += 1
            # Numpad diagonals
            if keys[pygame.K_KP_7]:
                dx, dy = -1, -1
            if keys[pygame.K_KP_9]:
                dx, dy = 1, -1
            if keys[pygame.K_KP_1]:
                dx, dy = -1, 1
            if keys[pygame.K_KP_3]:
                dx, dy = 1, 1

        if dx and dy:
            dx *= 0.707
            dy *= 0.707

        if dx != 0 or dy != 0:
            mag = math.hypot(dx, dy)
            self.facing_dx = dx / mag
            self.facing_dy = dy / mag

        h = self.COLLISION_HALF
        new_px = self.x + dx * self.speed * dt
        new_py = self.y + dy * self.speed * dt

        # X axis - stop if blocked, no bouncing
        if not out_of_bounds(new_px, self.y, h):
            if not hits_blocking(world, new_px, self.y, h):
                self.x = new_px

        # Y axis - stop if blocked, no bouncing
        if not out_of_bounds(self.x, new_py, h):
            if not hits_blocking(world, self.x, new_py, h):
                self.y = new_py

        self.x = max(h, min(WORLD_COLS * TILE - h, self.x))
        self.y = max(h, min(WORLD_ROWS * TILE - h, self.y))

    # -- mining ------------------------------------------------------------

    def update_mining(
        self, keys, mouse_buttons, dt, world, tile_hp, cam_x, cam_y, particles, floats
    ):
        """Handle mining input and tile breaking.

        Player 1: SPACE or mouse click
        Player 2: KP_0 (numpad 0) or KP_Period
        """
        from src.config import GRASS, DIRT, MOUNTAIN

        # Determine mining input
        if self.player_id == 1:
            mining_input = keys[pygame.K_SPACE] or mouse_buttons[0]
        else:
            mining_input = keys[pygame.K_KP_0] or keys[pygame.K_KP_PERIOD]

        target_col, target_row = None, None
        if self.player_id == 1 and mouse_buttons[0]:
            mx, my = pygame.mouse.get_pos()
            target_col = int((mx + cam_x) // TILE)
            target_row = int((my + cam_y) // TILE)
        elif (self.player_id == 1 and keys[pygame.K_SPACE]) or (
            self.player_id == 2 and mining_input
        ):
            center_col = int(self.x) // TILE
            center_row = int(self.y) // TILE
            best, best_dist = None, 999
            for dr in range(-1, 2):
                for dc in range(-1, 2):
                    c, r = center_col + dc, center_row + dr
                    if 0 <= c < WORLD_COLS and 0 <= r < WORLD_ROWS:
                        if TILE_INFO[world[r][c]]["mineable"]:
                            d = abs(dc) + abs(dr)
                            if d < best_dist:
                                best_dist = d
                                best = (c, r)
            if best:
                target_col, target_row = best

        if mining_input and target_col is not None and target_row is not None:
            if 0 <= target_col < WORLD_COLS and 0 <= target_row < WORLD_ROWS:
                tile_cx = target_col * TILE + TILE // 2
                tile_cy = target_row * TILE + TILE // 2
                dist = math.hypot(self.x - tile_cx, self.y - tile_cy)
                if (
                    dist < TILE * 2.5
                    and TILE_INFO[world[target_row][target_col]]["mineable"]
                ):
                    if self.mining_target != (target_col, target_row):
                        self.mining_target = (target_col, target_row)
                        self.mining_progress = 0
                    pick = PICKAXES[self.pick_level]
                    self.mining_progress += pick["power"] * dt * 0.15
                    tile_hp[target_row][target_col] = max(
                        0,
                        TILE_INFO[world[target_row][target_col]]["hp"]
                        - self.mining_progress,
                    )

                    import random

                    if random.random() < 0.4:
                        pcol = TILE_INFO[world[target_row][target_col]]["color"]
                        particles.append(Particle(tile_cx, tile_cy, pcol))

                    if tile_hp[target_row][target_col] <= 0:
                        info = TILE_INFO[world[target_row][target_col]]
                        if info["drop"]:
                            self.inventory[info["drop"]] = (
                                self.inventory.get(info["drop"], 0) + 1
                            )
                            floats.append(
                                FloatingText(
                                    tile_cx,
                                    tile_cy,
                                    f"+1 {info['drop']}",
                                    info["drop_color"],
                                )
                            )
                        for _ in range(12):
                            particles.append(Particle(tile_cx, tile_cy, info["color"]))
                        new_tile = (
                            DIRT if world[target_row][target_col] == MOUNTAIN else GRASS
                        )
                        world[target_row][target_col] = new_tile
                        tile_hp[target_row][target_col] = TILE_INFO[new_tile]["hp"]
                        self.mining_target = None
                        self.mining_progress = 0
                    return
        self.mining_target = None
        self.mining_progress = 0

    # -- combat ------------------------------------------------------------

    def take_damage(self, amount, particles, floats):
        """Take damage and trigger hurt effects."""
        if self.hurt_timer > 0:
            return
        self.hp = max(0, self.hp - amount)
        self.hurt_timer = 30
        floats.append(FloatingText(self.x, self.y - 20, f"-{amount} HP", (255, 60, 60)))
        for _ in range(6):
            particles.append(Particle(self.x, self.y, (255, 60, 60)))

    def check_level_up(self, particles, floats):
        """Check for level ups and apply bonuses."""
        while self.xp >= self.xp_next:
            self.xp -= self.xp_next
            self.level += 1
            self.xp_next = xp_for_level(self.level)
            self.max_hp += 10
            self.hp = self.max_hp
            floats.append(
                FloatingText(
                    self.x, self.y - 30, f"Level {self.level}!", (255, 255, 100)
                )
            )
            for _ in range(15):
                particles.append(Particle(self.x, self.y, (255, 255, 100)))

    # -- drawing -----------------------------------------------------------

    def draw(self, surf, cam_x, cam_y):
        """Draw player sprite."""
        psx = int(self.x - cam_x)
        psy = int(self.y - cam_y)
        body_color = (
            (230, 80, 80)
            if self.hurt_timer > 0 and int(self.hurt_timer * 4) % 2
            else (70, 130, 230)
        )
        pygame.draw.rect(
            surf, body_color, (psx - 10, psy - 14, 20, 28), border_radius=4
        )
        pygame.draw.circle(surf, (240, 200, 160), (psx, psy - 18), 8)
        pick_color = PICKAXES[self.pick_level]["color"]
        pygame.draw.line(surf, pick_color, (psx + 10, psy - 8), (psx + 18, psy - 16), 3)
        pygame.draw.line(
            surf, pick_color, (psx + 15, psy - 19), (psx + 21, psy - 13), 3
        )
