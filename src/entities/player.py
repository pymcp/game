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
from src.data.armor import (
    ARMOR_PIECES,
    ACCESSORY_PIECES,
    AccessoryEffect,
    ARMOR_SLOT_ORDER,
    item_fits_slot,
)
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
        equip_key: int,
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
            equip_key: pygame key constant for opening the equipment menu
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
        self.equip_key = equip_key
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
    equip_key=pygame.K_q,
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
    equip_key=pygame.K_RSHIFT,
    move_description="Arrows",
)


class Player:
    """The player character."""

    COLLISION_HALF = 10

    def __init__(
        self,
        x: float,
        y: float,
        player_id: int = 1,
        control_scheme: "ControlScheme | None" = None,
    ) -> None:
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

        # Armor & accessories — None means the slot is empty
        self.equipment: dict[str, str | None] = {
            slot: None for slot in ARMOR_SLOT_ORDER
        }
        # Remaining durability for each currently-equipped armor piece
        self.durability: dict[str, int] = {}

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

        # Mount state — True while riding a Creature
        self.on_mount: bool = False

        # Map tracking - "overland" or (cave_col, cave_row) or ("island", n)
        self.current_map = "overland"

        # Portal tracking — the map key the player came from when entering portal realm
        self.portal_origin_map: str | tuple | None = None

        # Respawn anchor — set when the player exits a portal so death respawns them here
        self.last_portal_exit_map: str | tuple | None = None
        self.last_portal_exit_x: float | None = None
        self.last_portal_exit_y: float | None = None

    # -- properties --------------------------------------------------------

    @property
    def defense_pct(self) -> float:
        """Total damage reduction fraction (0.0–1.0) from the four armor body slots."""
        total = 0.0
        for slot in ("helmet", "chest", "legs", "boots"):
            item = self.equipment.get(slot)
            if item and item in ARMOR_PIECES:
                total += ARMOR_PIECES[item]["defense_pct"]
        return min(total, 0.90)  # cap at 90% to always allow at least 1 dmg

    def active_effects(self) -> dict[AccessoryEffect, float]:
        """Return total accessory effect values (ring1 + ring2 + amulet combined)."""
        totals: dict[AccessoryEffect, float] = {}
        for slot in ("ring1", "ring2", "amulet"):
            item = self.equipment.get(slot)
            if item and item in ACCESSORY_PIECES:
                piece = ACCESSORY_PIECES[item]
                effect = piece["effect"]
                totals[effect] = totals.get(effect, 0.0) + piece["effect_value"]
        return totals

    # -- equipment --------------------------------------------------------

    def equip_item(self, slot: str, item_name: str) -> bool:
        """Equip *item_name* into *slot*, consuming it from inventory.

        Returns True on success, False if the item is not in inventory or
        doesn't fit the slot.  Any previously-equipped item in that slot is
        returned to inventory first.
        """
        if self.inventory.get(item_name, 0) <= 0:
            return False
        if not item_fits_slot(item_name, slot):
            return False
        # Return the currently-equipped item before overwriting
        self.unequip_item(slot)
        # Remove from inventory
        self.inventory[item_name] -= 1
        if self.inventory[item_name] <= 0:
            del self.inventory[item_name]
        # Place in equipment slot
        self.equipment[slot] = item_name
        if item_name in ARMOR_PIECES:
            self.durability[item_name] = ARMOR_PIECES[item_name]["durability"]
        # Recompute max_hp when an HP-boost accessory is equipped
        self._recalc_max_hp()
        return True

    def unequip_item(self, slot: str) -> None:
        """Unequip the item in *slot* and return it to inventory (if not already broken)."""
        item_name = self.equipment.get(slot)
        if item_name is None:
            return
        self.equipment[slot] = None
        # Broken armor (durability tracked but already spent) is destroyed
        still_intact = (
            item_name not in ARMOR_PIECES or self.durability.get(item_name, 0) > 0
        )
        if still_intact:
            self.inventory[item_name] = self.inventory.get(item_name, 0) + 1
        self.durability.pop(item_name, None)
        self._recalc_max_hp()

    def _recalc_max_hp(self) -> None:
        """Recompute max_hp including any HP-boost amulet effect."""
        base_max = 100 + (self.level - 1) * 10
        hp_bonus = 0.0
        amulet = self.equipment.get("amulet")
        if amulet and amulet in ACCESSORY_PIECES:
            piece = ACCESSORY_PIECES[amulet]
            if piece["effect"] == AccessoryEffect.HP_BOOST:
                hp_bonus = piece["effect_value"]
        new_max = int(base_max + hp_bonus)
        # Preserve current HP ratio when max changes
        if self.max_hp > 0:
            ratio = self.hp / self.max_hp
            self.max_hp = new_max
            self.hp = min(self.max_hp, max(1, int(self.max_hp * ratio)))
        else:
            self.max_hp = new_max

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

    def update_movement(
        self, keys: pygame.key.ScancodeWrapper, dt: float, world: list[list[int]]
    ) -> None:
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
        self,
        keys: pygame.key.ScancodeWrapper,
        mouse_buttons: tuple[bool, bool, bool],
        dt: float,
        world: list[list[int]],
        tile_hp: list[list[int]],
        cam_x: float,
        cam_y: float,
        particles: list,
        floats: list,
        map_key: str | tuple | None = None,
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
                        particles.append(Particle(tile_cx, tile_cy, pcol, map_key))

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
                                    map_key,
                                )
                            )
                        for _ in range(12):
                            particles.append(
                                Particle(tile_cx, tile_cy, info["color"], map_key)
                            )
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

    def take_damage(
        self,
        amount: int,
        particles: list,
        floats: list,
        map_key: str | tuple | None = None,
    ) -> None:
        """Take damage (reduced by armor) and trigger hurt effects."""
        if self.hurt_timer > 0:
            return
        effective = max(1, int(amount * (1.0 - self.defense_pct)))
        self.hp = max(0, self.hp - effective)
        self.hurt_timer = 30
        floats.append(
            FloatingText(
                self.x, self.y - 20, f"-{effective} HP", (255, 60, 60), map_key
            )
        )
        for _ in range(6):
            particles.append(Particle(self.x, self.y, (255, 60, 60)))
        self._tick_durability(floats, map_key)

    def _tick_durability(
        self, floats: list, map_key: str | tuple | None = None
    ) -> None:
        """Decrement durability on all equipped armor pieces; destroy pieces that reach 0."""
        for slot in ("helmet", "chest", "legs", "boots"):
            item = self.equipment.get(slot)
            if item is None or item not in self.durability:
                continue
            self.durability[item] -= 1
            if self.durability[item] <= 0:
                slot_label = slot.capitalize()
                floats.append(
                    FloatingText(
                        int(self.x),
                        int(self.y) - 30,
                        f"{slot_label} broke!",
                        (255, 160, 50),
                        map_key,
                    )
                )
                self.equipment[slot] = None
                del self.durability[item]

    def check_level_up(
        self, particles: list, floats: list, map_key: str | tuple | None = None
    ) -> None:
        """Check for level ups and apply bonuses."""
        while self.xp >= self.xp_next:
            self.xp -= self.xp_next
            self.level += 1
            self.xp_next = xp_for_level(self.level)
            self.max_hp += 10
            self.hp = self.max_hp
            floats.append(
                FloatingText(
                    self.x,
                    self.y - 30,
                    f"Level {self.level}!",
                    (255, 255, 100),
                    map_key,
                )
            )
            for _ in range(15):
                particles.append(Particle(self.x, self.y, (255, 255, 100)))

    # -- drawing -----------------------------------------------------------

    def _facing_dir(self) -> str:
        """Reduce the continuous facing vector to one of four cardinal directions."""
        if abs(self.facing_dy) >= abs(self.facing_dx):
            return "down" if self.facing_dy >= 0 else "up"
        return "left" if self.facing_dx < 0 else "right"

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
        elif self.on_mount:
            return  # the mounted creature renders the rider figure
        else:
            self._draw_normal(surf, psx, psy, body_color)

    def _draw_normal(
        self, surf: pygame.Surface, psx: int, psy: int, body_color: tuple[int, int, int]
    ) -> None:
        """Draw the player facing the correct cardinal direction with directional armor."""
        facing = self._facing_dir()
        skin: tuple[int, int, int] = (240, 200, 160)
        pick_color: tuple[int, int, int] = PICKAXES[self.pick_level]["color"]

        chest_item = self.equipment.get("chest")
        torso_color: tuple[int, int, int] = (
            ARMOR_PIECES[chest_item]["color"]
            if chest_item and chest_item in ARMOR_PIECES
            else body_color
        )
        legs_item = self.equipment.get("legs")
        leg_color: tuple[int, int, int] | None = (
            ARMOR_PIECES[legs_item]["color"]
            if legs_item and legs_item in ARMOR_PIECES
            else None
        )
        boots_item = self.equipment.get("boots")
        boot_color: tuple[int, int, int] | None = (
            ARMOR_PIECES[boots_item]["color"]
            if boots_item and boots_item in ARMOR_PIECES
            else None
        )
        helmet_item = self.equipment.get("helmet")
        helm_color: tuple[int, int, int] | None = (
            ARMOR_PIECES[helmet_item]["color"]
            if helmet_item and helmet_item in ARMOR_PIECES
            else None
        )
        lc: tuple[int, int, int] = leg_color if leg_color is not None else body_color

        if facing == "down":
            # --- FRONT (facing toward viewer) ---
            # Arms
            pygame.draw.rect(
                surf, body_color, (psx - 16, psy - 12, 6, 18), border_radius=2
            )
            pygame.draw.rect(
                surf, body_color, (psx + 10, psy - 12, 6, 18), border_radius=2
            )
            # Torso
            pygame.draw.rect(
                surf, torso_color, (psx - 10, psy - 14, 20, 24), border_radius=4
            )
            # Chest front accent line
            if chest_item and chest_item in ARMOR_PIECES:
                ac = (
                    max(0, torso_color[0] - 50),
                    max(0, torso_color[1] - 50),
                    max(0, torso_color[2] - 50),
                )
                pygame.draw.line(surf, ac, (psx, psy - 10), (psx, psy + 6), 2)
            # Legs (separate left/right)
            pygame.draw.rect(surf, lc, (psx - 9, psy + 10, 8, 14), border_radius=2)
            pygame.draw.rect(surf, lc, (psx + 1, psy + 10, 8, 14), border_radius=2)
            # Boots
            if boot_color:
                pygame.draw.rect(
                    surf, boot_color, (psx - 10, psy + 22, 10, 5), border_radius=1
                )
                pygame.draw.rect(
                    surf, boot_color, (psx, psy + 22, 10, 5), border_radius=1
                )
            # Head
            pygame.draw.circle(surf, skin, (psx, psy - 20), 8)
            # Eyes
            pygame.draw.circle(surf, (60, 35, 20), (psx - 3, psy - 21), 2)
            pygame.draw.circle(surf, (60, 35, 20), (psx + 3, psy - 21), 2)
            # Helmet — front with visor strip
            if helm_color:
                pygame.draw.rect(
                    surf, helm_color, (psx - 8, psy - 29, 16, 11), border_radius=3
                )
                visor = (
                    max(0, helm_color[0] - 70),
                    max(0, helm_color[1] - 70),
                    max(0, helm_color[2] - 70),
                )
                pygame.draw.rect(
                    surf, visor, (psx - 6, psy - 21, 12, 4), border_radius=1
                )
            # Pickaxe (right side)
            pygame.draw.line(
                surf, pick_color, (psx + 16, psy - 8), (psx + 24, psy - 16), 3
            )
            pygame.draw.line(
                surf, pick_color, (psx + 21, psy - 19), (psx + 27, psy - 13), 3
            )

        elif facing == "up":
            # --- BACK (facing away from viewer) ---
            arm_dark = (
                max(0, body_color[0] - 20),
                max(0, body_color[1] - 20),
                max(0, body_color[2] - 20),
            )
            pygame.draw.rect(
                surf, arm_dark, (psx - 16, psy - 12, 6, 16), border_radius=2
            )
            pygame.draw.rect(
                surf, arm_dark, (psx + 10, psy - 12, 6, 16), border_radius=2
            )
            # Torso
            pygame.draw.rect(
                surf, torso_color, (psx - 10, psy - 14, 20, 24), border_radius=4
            )
            # Legs
            pygame.draw.rect(surf, lc, (psx - 9, psy + 10, 8, 14), border_radius=2)
            pygame.draw.rect(surf, lc, (psx + 1, psy + 10, 8, 14), border_radius=2)
            # Boots
            if boot_color:
                pygame.draw.rect(
                    surf, boot_color, (psx - 10, psy + 22, 10, 5), border_radius=1
                )
                pygame.draw.rect(
                    surf, boot_color, (psx, psy + 22, 10, 5), border_radius=1
                )
            # Head (back — hair tuft, no eyes)
            pygame.draw.circle(surf, skin, (psx, psy - 20), 8)
            pygame.draw.rect(
                surf, (90, 55, 25), (psx - 5, psy - 28, 10, 6), border_radius=2
            )
            # Helmet — back cap, no visor
            if helm_color:
                pygame.draw.rect(
                    surf, helm_color, (psx - 8, psy - 29, 16, 11), border_radius=3
                )
            # Pickaxe (trailing left side)
            pygame.draw.line(
                surf, pick_color, (psx - 16, psy - 8), (psx - 24, psy - 16), 3
            )
            pygame.draw.line(
                surf, pick_color, (psx - 21, psy - 19), (psx - 27, psy - 13), 3
            )

        elif facing == "right":
            # --- RIGHT PROFILE ---
            # Back arm (darker, behind torso)
            back_arm = (
                max(0, body_color[0] - 30),
                max(0, body_color[1] - 30),
                max(0, body_color[2] - 30),
            )
            pygame.draw.rect(
                surf, back_arm, (psx - 14, psy - 10, 5, 14), border_radius=2
            )
            # Torso (narrower side profile)
            pygame.draw.rect(
                surf, torso_color, (psx - 6, psy - 14, 14, 24), border_radius=3
            )
            # Back leg (darker) then front leg on top
            dark_lc = (max(0, lc[0] - 35), max(0, lc[1] - 35), max(0, lc[2] - 35))
            pygame.draw.rect(surf, dark_lc, (psx - 5, psy + 10, 7, 12), border_radius=2)
            pygame.draw.rect(surf, lc, (psx - 1, psy + 10, 7, 12), border_radius=2)
            # Boot (forward foot)
            if boot_color:
                pygame.draw.rect(
                    surf, boot_color, (psx - 2, psy + 20, 12, 5), border_radius=1
                )
            # Front arm (on top)
            pygame.draw.rect(
                surf, body_color, (psx + 8, psy - 12, 6, 18), border_radius=2
            )
            # Head (shifted right)
            pygame.draw.circle(surf, skin, (psx + 2, psy - 20), 8)
            pygame.draw.circle(surf, (60, 35, 20), (psx + 5, psy - 21), 2)
            # Helmet — side profile with forward nub
            if helm_color:
                pygame.draw.rect(
                    surf, helm_color, (psx - 5, psy - 29, 15, 11), border_radius=3
                )
                nub = (
                    max(0, helm_color[0] - 60),
                    max(0, helm_color[1] - 60),
                    max(0, helm_color[2] - 60),
                )
                pygame.draw.rect(surf, nub, (psx + 9, psy - 23, 3, 5), border_radius=1)
            # Pickaxe (forward)
            pygame.draw.line(
                surf, pick_color, (psx + 14, psy - 10), (psx + 22, psy - 18), 3
            )
            pygame.draw.line(
                surf, pick_color, (psx + 19, psy - 21), (psx + 25, psy - 15), 3
            )

        else:  # left
            # --- LEFT PROFILE ---
            # Back arm (darker, behind torso)
            back_arm = (
                max(0, body_color[0] - 30),
                max(0, body_color[1] - 30),
                max(0, body_color[2] - 30),
            )
            pygame.draw.rect(
                surf, back_arm, (psx + 9, psy - 10, 5, 14), border_radius=2
            )
            # Torso (narrower side profile)
            pygame.draw.rect(
                surf, torso_color, (psx - 8, psy - 14, 14, 24), border_radius=3
            )
            # Back leg (darker) then front leg on top
            dark_lc = (max(0, lc[0] - 35), max(0, lc[1] - 35), max(0, lc[2] - 35))
            pygame.draw.rect(surf, dark_lc, (psx - 2, psy + 10, 7, 12), border_radius=2)
            pygame.draw.rect(surf, lc, (psx - 6, psy + 10, 7, 12), border_radius=2)
            # Boot (forward foot)
            if boot_color:
                pygame.draw.rect(
                    surf, boot_color, (psx - 10, psy + 20, 12, 5), border_radius=1
                )
            # Front arm (on top)
            pygame.draw.rect(
                surf, body_color, (psx - 14, psy - 12, 6, 18), border_radius=2
            )
            # Head (shifted left)
            pygame.draw.circle(surf, skin, (psx - 2, psy - 20), 8)
            pygame.draw.circle(surf, (60, 35, 20), (psx - 5, psy - 21), 2)
            # Helmet — side profile with forward nub
            if helm_color:
                pygame.draw.rect(
                    surf, helm_color, (psx - 10, psy - 29, 15, 11), border_radius=3
                )
                nub = (
                    max(0, helm_color[0] - 60),
                    max(0, helm_color[1] - 60),
                    max(0, helm_color[2] - 60),
                )
                pygame.draw.rect(surf, nub, (psx - 12, psy - 23, 3, 5), border_radius=1)
            # Pickaxe (forward)
            pygame.draw.line(
                surf, pick_color, (psx - 14, psy - 10), (psx - 22, psy - 18), 3
            )
            pygame.draw.line(
                surf, pick_color, (psx - 19, psy - 21), (psx - 25, psy - 15), 3
            )

    def _draw_on_boat(
        self, surf: pygame.Surface, psx: int, psy: int, body_color: tuple[int, int, int]
    ) -> None:
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
