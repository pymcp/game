"""Player character class."""

import math
import random
import pygame
from src.config import (
    TILE,
    WORLD_COLS,
    WORLD_ROWS,
    SCREEN_W,
    SCREEN_H,
    GRASS,
    DIRT,
    MOUNTAIN,
)
from src.data import PICKAXES, WEAPONS, UPGRADE_COSTS, WEAPON_UNLOCK_COSTS, TILE_INFO
from src.world import try_spend, xp_for_level, hits_blocking, out_of_bounds
from src.effects import Particle, FloatingText


class ControlScheme:
    """Represents a player's control scheme."""

    def __init__(
        self,
        move_keys: dict[str, int],
        mining_key: int,
        fire_key: int,
        upgrade_pick_key: int,
        upgrade_weapon_key: int,
        build_house_key: int,
        toggle_auto_mine_key: int,
        toggle_auto_fire_key: int,
        interact_key: int,
        build_pier_key: int,
        move_description: str = "",
    ) -> None:
        """Initialize control scheme.

        Args:
            move_keys: Dict with 'left', 'right', 'up', 'down' pygame key constants
            mining_key: pygame key constant for mining
            fire_key: pygame key constant for firing weapon
            upgrade_pick_key: pygame key constant for pickaxe upgrade
            upgrade_weapon_key: pygame key constant for weapon upgrade
            build_house_key: pygame key constant for building a house
            toggle_auto_mine_key: pygame key constant for toggling auto mine
            toggle_auto_fire_key: pygame key constant for toggling auto fire
            move_description: String description of movement controls (e.g., "WASD", "Arrow Keys")
        """
        self.move_keys = move_keys
        self.mining_key = mining_key
        self.fire_key = fire_key
        self.upgrade_pick_key = upgrade_pick_key
        self.upgrade_weapon_key = upgrade_weapon_key
        self.build_house_key = build_house_key
        self.toggle_auto_mine_key = toggle_auto_mine_key
        self.toggle_auto_fire_key = toggle_auto_fire_key
        self.interact_key = interact_key
        self.build_pier_key = build_pier_key
        self.move_description = move_description

    def get_controls_list(self) -> list[str]:
        """Return list of control descriptions for UI display."""
        return [
            f"{self.move_description}: Move",
            f"{pygame.key.name(self.mining_key).upper()}: Mine",
            f"{pygame.key.name(self.fire_key).upper()}: Fire",
            f"{pygame.key.name(self.upgrade_pick_key).upper()}: Upgrade Pickaxe",
            f"{pygame.key.name(self.upgrade_weapon_key).upper()}: Upgrade Weapon",
            f"{pygame.key.name(self.build_house_key).upper()}: Build House",
            f"{pygame.key.name(self.interact_key).upper()}: Interact / Sail",
            f"{pygame.key.name(self.build_pier_key).upper()}: Build Pier",
        ]


# Pre-configured control schemes
CONTROL_SCHEME_PLAYER1 = ControlScheme(
    move_keys={
        "left": pygame.K_a,
        "right": pygame.K_d,
        "up": pygame.K_w,
        "down": pygame.K_s,
    },
    mining_key=pygame.K_SPACE,
    fire_key=pygame.K_f,
    upgrade_pick_key=pygame.K_u,
    upgrade_weapon_key=pygame.K_n,
    build_house_key=pygame.K_b,
    toggle_auto_mine_key=pygame.K_m,
    toggle_auto_fire_key=pygame.K_g,
    interact_key=pygame.K_e,
    build_pier_key=pygame.K_h,
    move_description="WASD",
)

CONTROL_SCHEME_PLAYER2 = ControlScheme(
    move_keys={
        "left": pygame.K_LEFT,
        "right": pygame.K_RIGHT,
        "up": pygame.K_UP,
        "down": pygame.K_DOWN,
    },
    mining_key=pygame.K_KP_0,
    fire_key=pygame.K_KP_ENTER,
    upgrade_pick_key=pygame.K_i,
    upgrade_weapon_key=pygame.K_o,
    build_house_key=pygame.K_v,
    toggle_auto_mine_key=pygame.K_KP_MULTIPLY,
    toggle_auto_fire_key=pygame.K_KP_DIVIDE,
    interact_key=pygame.K_KP_5,
    build_pier_key=pygame.K_KP_PLUS,
    move_description="Arrows",
)


class Player:
    """The player character."""

    COLLISION_HALF = 10

    def __init__(self, x: float, y: float, player_id: int = 1, control_scheme: "ControlScheme | None" = None) -> None:
        """Initialize player.

        Args:
            x, y: Starting position
            player_id: 1 or 2 (for reference)
            control_scheme: ControlScheme instance for this player's controls
        """
        self.x = float(x)
        self.y = float(y)
        self.player_id = player_id
        self.speed = 3.2

        # Control scheme
        if control_scheme is None:
            control_scheme = (
                CONTROL_SCHEME_PLAYER1 if player_id == 1 else CONTROL_SCHEME_PLAYER2
            )
        self.controls = control_scheme

        # Random color for this player
        self.color = (
            random.randint(100, 255),
            random.randint(100, 255),
            random.randint(100, 255),
        )

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
        self.is_dead = False

        # Facing direction (last non-zero movement)
        self.facing_dx = 1.0
        self.facing_dy = 0.0

        # Mining
        self.mining_target = None
        self.mining_progress = 0.0

        # Auto fire and auto mine
        self.auto_mine = False
        self.auto_fire = False

        # Sailing / boat state
        self.on_boat = False
        self.boat_col = None  # last water tile column the boat occupied
        self.boat_row = None  # last water tile row the boat occupied

        # Map tracking - "overland" or (cave_col, cave_row) or ("island", n)
        self.current_map = "overland"

    # -- upgrades ----------------------------------------------------------

    def try_upgrade_pick(self) -> bool:
        """Attempt to upgrade pickaxe if cost is affordable."""
        if self.pick_level < len(PICKAXES) - 1:
            if try_spend(self.inventory, UPGRADE_COSTS[self.pick_level]):
                self.pick_level += 1
                return True
        return False

    def try_upgrade_weapon(self) -> bool:
        """Attempt to unlock next weapon if cost is affordable."""
        if self.weapon_level < len(WEAPONS) - 1:
            if try_spend(self.inventory, WEAPON_UNLOCK_COSTS[self.weapon_level]):
                self.weapon_level += 1
                return True
        return False

    def toggle_auto_mine(self) -> None:
        """Toggle auto mine mode."""
        self.auto_mine = not self.auto_mine

    def toggle_auto_fire(self) -> None:
        """Toggle auto fire mode."""
        self.auto_fire = not self.auto_fire

    # -- movement / collision ----------------------------------------------

    def update_movement(self, keys: pygame.key.ScancodeWrapper, dt: float, world: list[list[int]]) -> None:
        """Handle input and collision using the player's control scheme."""
        from src.config import GRASS, DIRT, MOUNTAIN, WATER

        dx = dy = 0
        move_keys = self.controls.move_keys

        # Check movement keys based on control scheme
        if keys[move_keys["left"]]:
            dx -= 1
        if keys[move_keys["right"]]:
            dx += 1
        if keys[move_keys["up"]]:
            dy -= 1
        if keys[move_keys["down"]]:
            dy += 1

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

        # On a boat, water tiles are passable
        boat_pass = (WATER,) if self.on_boat else ()

        # X axis - stop if blocked, no bouncing
        if not out_of_bounds(new_px, self.y, h, world):
            if not hits_blocking(world, new_px, self.y, h, boat_pass):
                self.x = new_px

        # Y axis - stop if blocked, no bouncing
        if not out_of_bounds(self.x, new_py, h, world):
            if not hits_blocking(world, self.x, new_py, h, boat_pass):
                self.y = new_py

        world_cols = len(world[0]) if len(world) > 0 else WORLD_COLS
        world_rows = len(world)
        self.x = max(h, min(world_cols * TILE - h, self.x))
        self.y = max(h, min(world_rows * TILE - h, self.y))

    # -- mining ------------------------------------------------------------

    def update_mining(
        self, keys: pygame.key.ScancodeWrapper, mouse_buttons: tuple[bool, bool, bool], dt: float, world: list[list[int]], tile_hp: list[list[int]], cam_x: float, cam_y: float, particles: list, floats: list
    ) -> None:
        """Handle mining input and tile breaking."""

        # Determine mining input based on control scheme
        mining_input = (
            keys[self.controls.mining_key] or mouse_buttons[0] or self.auto_mine
        )

        target_col, target_row = None, None
        world_cols = len(world[0]) if world else WORLD_COLS
        world_rows = len(world)
        if mouse_buttons[0]:
            mx, my = pygame.mouse.get_pos()
            target_col = int((mx + cam_x) // TILE)
            target_row = int((my + cam_y) // TILE)
        elif keys[self.controls.mining_key] or self.auto_mine:
            center_col = int(self.x) // TILE
            center_row = int(self.y) // TILE
            best, best_dist = None, 999
            for dr in range(-1, 2):
                for dc in range(-1, 2):
                    c, r = center_col + dc, center_row + dr
                    if 0 <= c < world_cols and 0 <= r < world_rows:
                        if TILE_INFO[world[r][c]]["mineable"]:
                            d = abs(dc) + abs(dr)
                            if d < best_dist:
                                best_dist = d
                                best = (c, r)
            if best:
                target_col, target_row = best

        if mining_input and target_col is not None and target_row is not None:
            if 0 <= target_col < world_cols and 0 <= target_row < world_rows:
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

    def take_damage(self, amount: int, particles: list, floats: list) -> None:
        """Take damage and trigger hurt effects."""
        if self.hurt_timer > 0:
            return
        self.hp = max(0, self.hp - amount)
        self.hurt_timer = 30
        floats.append(FloatingText(self.x, self.y - 20, f"-{amount} HP", (255, 60, 60)))
        for _ in range(6):
            particles.append(Particle(self.x, self.y, (255, 60, 60)))

    def check_level_up(self, particles: list, floats: list) -> None:
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

    def draw(self, surf: pygame.Surface, cam_x: float, cam_y: float) -> None:
        """Draw player sprite."""
        psx = int(self.x - cam_x)
        psy = int(self.y - cam_y)
        body_color = (
            (230, 80, 80)
            if self.hurt_timer > 0 and int(self.hurt_timer * 4) % 2
            else self.color
        )

        if self.on_boat:
            self._draw_on_boat(surf, psx, psy, body_color)
        else:
            self._draw_normal(surf, psx, psy, body_color)

    def _draw_normal(self, surf: pygame.Surface, psx: int, psy: int, body_color: tuple[int, int, int]) -> None:
        """Draw the standard standing player."""
        pygame.draw.rect(
            surf, body_color, (psx - 10, psy - 14, 20, 28), border_radius=4
        )
        pygame.draw.circle(surf, (240, 200, 160), (psx, psy - 18), 8)
        pick_color = PICKAXES[self.pick_level]["color"]
        pygame.draw.line(surf, pick_color, (psx + 10, psy - 8), (psx + 18, psy - 16), 3)
        pygame.draw.line(
            surf, pick_color, (psx + 15, psy - 19), (psx + 21, psy - 13), 3
        )

    def _draw_on_boat(self, surf: pygame.Surface, psx: int, psy: int, body_color: tuple[int, int, int]) -> None:
        """Draw the player seated in a boat (boat prominent in foreground)."""
        import math

        ticks = pygame.time.get_ticks()
        bob = int(math.sin(ticks * 0.004) * 2)  # gentle ±2px vertical bob

        # --- Player (seated, shifted up inside hull) ---
        # Torso (shorter — sitting)
        pygame.draw.rect(
            surf, body_color, (psx - 8, psy - 22 + bob, 16, 18), border_radius=3
        )
        # Head
        pygame.draw.circle(surf, (240, 200, 160), (psx, psy - 28 + bob), 8)

        # --- Boat hull (drawn over player legs — foreground) ---
        hull_color = (120, 80, 35)
        hull_dark = (80, 52, 20)
        # Main hull body
        pygame.draw.polygon(
            surf,
            hull_color,
            [
                (psx - 26, psy - 6 + bob),
                (psx + 26, psy - 6 + bob),
                (psx + 20, psy + 14 + bob),
                (psx - 20, psy + 14 + bob),
            ],
        )
        # Hull rim highlight
        pygame.draw.polygon(
            surf,
            (160, 115, 55),
            [
                (psx - 26, psy - 6 + bob),
                (psx + 26, psy - 6 + bob),
                (psx + 24, psy - 1 + bob),
                (psx - 24, psy - 1 + bob),
            ],
        )
        # Keel line
        pygame.draw.line(
            surf, hull_dark, (psx - 3, psy + 14 + bob), (psx + 3, psy + 14 + bob), 3
        )
        # Gunwale (top edge of hull sides)
        pygame.draw.line(
            surf, hull_dark, (psx - 26, psy - 6 + bob), (psx + 26, psy - 6 + bob), 2
        )

        # --- Mast & sail ---
        mast_x = psx + 4
        mast_top = psy - 46 + bob
        mast_base = psy - 6 + bob
        pygame.draw.line(surf, (88, 62, 28), (mast_x, mast_top), (mast_x, mast_base), 2)
        # Billowing sail
        sail_bulge = 14 + int(math.sin(ticks * 0.002) * 3)
        pygame.draw.polygon(
            surf,
            (240, 232, 210),
            [
                (mast_x + 1, mast_top + 2),
                (mast_x + 1, mast_base - 4),
                (mast_x + sail_bulge + 14, mast_top + (mast_base - mast_top) // 2),
            ],
        )
        # Sail outline
        pygame.draw.polygon(
            surf,
            (180, 170, 150),
            [
                (mast_x + 1, mast_top + 2),
                (mast_x + 1, mast_base - 4),
                (mast_x + sail_bulge + 14, mast_top + (mast_base - mast_top) // 2),
            ],
            1,
        )

        # --- Wake lines below hull ---
        wake_y = psy + 14 + bob
        for i in range(1, 4):
            frac = i * 0.3
            w_color = (60 + i * 15, 110 + i * 18, 175 + i * 12)
            pygame.draw.line(
                surf,
                w_color,
                (psx - int(frac * 22), wake_y + i * 4),
                (psx + int(frac * 22), wake_y + i * 4),
                1,
            )
