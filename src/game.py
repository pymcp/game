"""Main game class and orchestration."""

import pygame
import math
import random
from src.config import (
    SCREEN_W,
    SCREEN_H,
    TILE,
    FPS,
    BG,
    WORLD_COLS,
    WORLD_ROWS,
    GRASS,
    DIRT,
    MOUNTAIN,
    TREE,
    WATER,
    HOUSE,
    IRON_ORE,
    GOLD_ORE,
    DIAMOND_ORE,
    CAVE_MOUNTAIN,
    CAVE_HILL,
    CAVE_EXIT,
    PIER,
    BOAT,
    TREASURE_CHEST,
    SETTLEMENT_TIER_SIZES,
    SETTLEMENT_TIER_NAMES,
    HOUSE_BUILD_COST,
    PIER_BUILD_COST,
    BOAT_BUILD_COST,
    SECTOR_WIPE_DURATION,
)
from src.data import TILE_INFO, WEAPONS, PICKAXES, UPGRADE_COSTS, WEAPON_UNLOCK_COSTS
from src.world import (
    generate_world,
    generate_ocean_sector,
    spawn_enemies,
    try_spend,
    has_adjacent_house,
    compute_town_clusters,
)
from src.world.map import GameMap
from src.world.environments import CaveEnvironment
from src.entities import Player, Projectile, Worker, Pet
from src.entities.player import CONTROL_SCHEME_PLAYER1, CONTROL_SCHEME_PLAYER2
from src.effects import Particle, FloatingText


class Game:
    """Main game class managing all game state and the main loop (2 players)."""

    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H), pygame.RESIZABLE)
        pygame.display.set_caption("Mining Game - 2 Players (F11 for fullscreen)")
        self.clock = pygame.time.Clock()
        self.is_fullscreen = False
        self.font = pygame.font.SysFont("monospace", 16)

        # UI fonts — cached once to avoid re-creating every frame
        self.font_ui_sm = pygame.font.Font(None, 22)
        self.font_ui_xs = pygame.font.Font(None, 16)
        self.font_dc_big = pygame.font.SysFont("monospace", 38, bold=True)
        self.font_dc_med = pygame.font.SysFont("monospace", 26, bold=True)
        self.font_dc_sm = pygame.font.SysFont("monospace", 18)

        # Dynamic viewport dimensions (updated each frame from actual screen size)
        self.viewport_w = SCREEN_W // 2
        self.viewport_h = SCREEN_H

        # Map system - store all maps by key
        # "overland" is the main map, caves are keyed by (col, row)
        world_data = generate_world()
        self.maps = {"overland": GameMap(world_data, tileset="overland")}

        # Get shortcut reference to overland map
        overland_map = self.maps["overland"]

        # Two Players - find grass tiles near center
        def find_grass_spawn(offset_x):
            """Find a grass tile near center offset by offset_x."""
            start_col = (WORLD_COLS // 2) + (offset_x // TILE)
            start_row = WORLD_ROWS // 2

            # Search in expanding square around target position
            for search_dist in range(10):
                for dc in range(-search_dist, search_dist + 1):
                    for dr in range(-search_dist, search_dist + 1):
                        if abs(dc) != search_dist and abs(dr) != search_dist:
                            continue
                        col = start_col + dc
                        row = start_row + dr
                        if 0 <= col < WORLD_COLS and 0 <= row < WORLD_ROWS:
                            if overland_map.get_tile(row, col) == GRASS:
                                return col * TILE + TILE // 2, row * TILE + TILE // 2
            # Fallback to center if no grass found
            return (WORLD_COLS // 2) * TILE + TILE // 2, (
                WORLD_ROWS // 2
            ) * TILE + TILE // 2

        start_x1, start_y1 = find_grass_spawn(-TILE)
        start_x2, start_y2 = find_grass_spawn(TILE)

        self.player1 = Player(
            start_x1, start_y1, player_id=1, control_scheme=CONTROL_SCHEME_PLAYER1
        )
        self.player2 = Player(
            start_x2, start_y2, player_id=2, control_scheme=CONTROL_SCHEME_PLAYER2
        )

        # Cameras (one for each player's viewport)
        self.cam1_x = self.player1.x - self.viewport_w // 2
        self.cam1_y = self.player1.y - self.viewport_h // 2
        self.cam2_x = self.player2.x - self.viewport_w // 2
        self.cam2_y = self.player2.y - self.viewport_h // 2

        # Entities (shared between players - only on overland map)
        self.workers = []
        self.pets = []
        self.enemies = spawn_enemies(overland_map.world)
        self.projectiles = []

        # Effects (shared)
        self.particles = []
        self.floats = []

        self.running = True

        # Death challenge state: {player_id: {"question": str, "answer": int, "input": str, "wrong": bool}}
        self.death_challenges = {}

        # Deterministic seed for the ocean sector grid
        self.world_seed = random.randint(0, 0xFFFF_FFFF)
        # Alias sector (0,0) as the home overland map so sector logic can use one key type
        self.maps[("sector", 0, 0)] = self.maps["overland"]
        # Sector-wipe animation state: {player_id: {"progress": float, "direction": str}}
        self.sector_wipe = {}

    # -- death challenge ---------------------------------------------------

    def _start_death_challenge(self, player):
        """Pause a dead player and present a math problem they must solve to respawn."""
        player.is_dead = True
        player.hurt_timer = 0
        a = random.randint(1, 20)
        b = random.randint(1, 20)
        if random.choice([True, False]):
            answer = a + b
            question = f"{a} + {b} = ?"
        else:
            if a < b:
                a, b = b, a
            answer = a - b
            question = f"{a} - {b} = ?"
        self.death_challenges[player.player_id] = {
            "question": question,
            "answer": answer,
            "input": "",
            "wrong": False,
        }

    def _submit_death_challenge(self, player):
        """Check the typed answer; respawn player on correct answer."""
        challenge = self.death_challenges.get(player.player_id)
        if challenge is None:
            return
        try:
            typed = int(challenge["input"])
        except ValueError:
            challenge["wrong"] = True
            challenge["input"] = ""
            return
        if typed == challenge["answer"]:
            player.is_dead = False
            player.hp = player.max_hp
            del self.death_challenges[player.player_id]
            self._respawn_player(player)
            self.floats.append(
                FloatingText(player.x, player.y - 30, "Respawned!", (100, 255, 100))
            )
        else:
            challenge["wrong"] = True
            challenge["input"] = ""

    def _respawn_player(self, player):
        """Teleport a respawning player to a safe grass tile near the world centre."""
        player.current_map = "overland"
        overland = self.maps["overland"]
        for search_dist in range(1, 30):
            for dc in range(-search_dist, search_dist + 1):
                for dr in range(-search_dist, search_dist + 1):
                    if abs(dc) != search_dist and abs(dr) != search_dist:
                        continue
                    col = WORLD_COLS // 2 + dc
                    row = WORLD_ROWS // 2 + dr
                    if 0 <= col < WORLD_COLS and 0 <= row < WORLD_ROWS:
                        if overland.get_tile(row, col) == GRASS:
                            player.x = col * TILE + TILE // 2
                            player.y = row * TILE + TILE // 2
                            return
        player.x = WORLD_COLS // 2 * TILE + TILE // 2
        player.y = WORLD_ROWS // 2 * TILE + TILE // 2

    # -- main loop ---------------------------------------------------------

    def run(self):
        """Main game loop."""
        while self.running:
            dt = self.clock.tick(FPS) / 16.667
            self.handle_events()
            self.update(dt)
            self.draw()
        pygame.quit()

    # -- events ------------------------------------------------------------

    def handle_events(self):
        """Handle input events."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                self._handle_keydown(event.key)
            elif event.type == pygame.VIDEORESIZE:
                self.screen = pygame.display.set_mode(event.size, pygame.RESIZABLE)

    def _handle_keydown(self, key):
        """Handle key press (for both players based on key)."""
        # --- Death challenge input handling (takes priority over all other keys) ---
        active_player = None
        if self.player1.is_dead and self.player1.player_id in self.death_challenges:
            active_player = self.player1
        elif self.player2.is_dead and self.player2.player_id in self.death_challenges:
            active_player = self.player2

        if active_player is not None:
            challenge = self.death_challenges[active_player.player_id]
            digit_map = {
                pygame.K_0: "0",
                pygame.K_1: "1",
                pygame.K_2: "2",
                pygame.K_3: "3",
                pygame.K_4: "4",
                pygame.K_5: "5",
                pygame.K_6: "6",
                pygame.K_7: "7",
                pygame.K_8: "8",
                pygame.K_9: "9",
                pygame.K_KP0: "0",
                pygame.K_KP1: "1",
                pygame.K_KP2: "2",
                pygame.K_KP3: "3",
                pygame.K_KP4: "4",
                pygame.K_KP5: "5",
                pygame.K_KP6: "6",
                pygame.K_KP7: "7",
                pygame.K_KP8: "8",
                pygame.K_KP9: "9",
            }
            if key in digit_map:
                challenge["input"] += digit_map[key]
                challenge["wrong"] = False
                return
            elif key in (pygame.K_MINUS, pygame.K_KP_MINUS) and not challenge["input"]:
                challenge["input"] = "-"
                challenge["wrong"] = False
                return
            elif key == pygame.K_BACKSPACE:
                challenge["input"] = challenge["input"][:-1]
                challenge["wrong"] = False
                return
            elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._submit_death_challenge(active_player)
                return

        if key == pygame.K_ESCAPE:
            self.running = False
        elif key == pygame.K_F11:
            self.is_fullscreen = not self.is_fullscreen
            if self.is_fullscreen:
                self.screen = pygame.display.set_mode(
                    (SCREEN_W, SCREEN_H), pygame.FULLSCREEN
                )
            else:
                self.screen = pygame.display.set_mode(
                    (SCREEN_W, SCREEN_H), pygame.RESIZABLE
                )
        # Player 1 controls (blocked while dead)
        elif not self.player1.is_dead and key == self.player1.controls.upgrade_pick_key:
            self.player1.try_upgrade_pick()
        elif (
            not self.player1.is_dead and key == self.player1.controls.upgrade_weapon_key
        ):
            self.player1.try_upgrade_weapon()
        elif not self.player1.is_dead and key == self.player1.controls.build_house_key:
            self._try_build_house(self.player1)
        elif (
            not self.player1.is_dead
            and key == self.player1.controls.toggle_auto_mine_key
        ):
            self.player1.toggle_auto_mine()
        elif (
            not self.player1.is_dead
            and key == self.player1.controls.toggle_auto_fire_key
        ):
            self.player1.toggle_auto_fire()
        elif not self.player1.is_dead and key == self.player1.controls.interact_key:
            self._try_interact(self.player1)
        elif not self.player1.is_dead and key == self.player1.controls.build_pier_key:
            self._try_build_pier(self.player1)
        # Player 2 controls (blocked while dead)
        elif not self.player2.is_dead and key == self.player2.controls.upgrade_pick_key:
            self.player2.try_upgrade_pick()
        elif (
            not self.player2.is_dead and key == self.player2.controls.upgrade_weapon_key
        ):
            self.player2.try_upgrade_weapon()
        elif not self.player2.is_dead and key == self.player2.controls.build_house_key:
            self._try_build_house(self.player2)
        elif (
            not self.player2.is_dead
            and key == self.player2.controls.toggle_auto_mine_key
        ):
            self.player2.toggle_auto_mine()
        elif (
            not self.player2.is_dead
            and key == self.player2.controls.toggle_auto_fire_key
        ):
            self.player2.toggle_auto_fire()
        elif not self.player2.is_dead and key == self.player2.controls.interact_key:
            self._try_interact(self.player2)
        elif not self.player2.is_dead and key == self.player2.controls.build_pier_key:
            self._try_build_pier(self.player2)

    def _try_build_house(self, player):
        """Attempt to build a house at player position."""
        if player.current_map != "overland":
            return  # Can only build houses on overland map

        build_col = int(player.x) // TILE
        build_row = int(player.y) // TILE
        if not (0 <= build_col < WORLD_COLS and 0 <= build_row < WORLD_ROWS):
            return

        current_map = self.maps["overland"]
        if (
            current_map.get_tile(build_row, build_col) != GRASS
            or player.inventory.get("Dirt", 0) < HOUSE_BUILD_COST
        ):
            return
        if not try_spend(player.inventory, {"Dirt": HOUSE_BUILD_COST}):
            return

        current_map.set_tile(build_row, build_col, HOUSE)
        current_map.set_tile_hp(build_row, build_col, 0)
        tile_cx = build_col * TILE + TILE // 2
        tile_cy = build_row * TILE + TILE // 2
        self.floats.append(
            FloatingText(tile_cx, tile_cy, "House built!", (210, 160, 60))
        )
        for _ in range(10):
            self.particles.append(Particle(tile_cx, tile_cy, (160, 82, 45)))

        if random.random() < 0.25:
            self.pets.append(Pet(tile_cx, tile_cy, kind="dog"))
            self.floats.append(
                FloatingText(tile_cx, tile_cy - 20, "Dog spawned!", (180, 130, 70))
            )
        else:
            self.workers.append(Worker(tile_cx, tile_cy, player_id=player.player_id))
            self.floats.append(
                FloatingText(tile_cx, tile_cy - 20, "Worker spawned!", (100, 220, 255))
            )

        if has_adjacent_house(self.maps["overland"].world, build_col, build_row):
            self.pets.append(Pet(tile_cx, tile_cy, kind="cat"))
            self.floats.append(
                FloatingText(tile_cx, tile_cy - 36, "Cat appeared!", (255, 165, 0))
            )

        self._update_town_clusters(build_col, build_row, player)

    # -- helpers -----------------------------------------------------------

    def get_player_current_map(self, player):
        """Get the GameMap object that the player is currently on."""
        map_key = player.current_map
        if map_key == "overland":
            return self.maps["overland"]
        elif isinstance(map_key, tuple):
            return self.maps.get(map_key)
        return None

    def _find_grass_spawn(self, game_map, prefer_col, prefer_row):
        """Return (x, y) pixel centre of the nearest GRASS tile to prefer_col/row."""
        rows = game_map.rows
        cols = game_map.cols
        for sd in range(max(rows, cols)):
            for dc in range(-sd, sd + 1):
                for dr in range(-sd, sd + 1):
                    if abs(dc) != sd and abs(dr) != sd:
                        continue
                    c = prefer_col + dc
                    r = prefer_row + dr
                    if 0 <= c < cols and 0 <= r < rows:
                        if game_map.get_tile(r, c) == GRASS:
                            return c * TILE + TILE // 2, r * TILE + TILE // 2
        return prefer_col * TILE + TILE // 2, prefer_row * TILE + TILE // 2

    # -- sailing / pier / boat / interaction --------------------------------

    def _try_interact(self, player):
        """Context-sensitive interact key handler.

        Priority:
          1. If a sail-prompt is pending → confirm sailing.
          2. If player is on_boat → show sailing prompt.
          3. If adjacent to a TREASURE_CHEST → open it.
          4. If standing on a PIER tile with WATER adjacent → build boat (if materials).
        """
        pid = player.player_id
        current_map_obj = self.get_player_current_map(player)
        if current_map_obj is None:
            return

        p_col = int(player.x) // TILE
        p_row = int(player.y) // TILE

        # 1. On boat — show a sailing hint (actual edge-crossing handles transit)
        if player.on_boat:
            self.floats.append(
                FloatingText(
                    int(player.x),
                    int(player.y) - 36,
                    "Sail to the edge of the map!",
                    (100, 200, 255),
                )
            )
            return

        # 2. Adjacent treasure chest
        for dc, dr in [(0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)]:
            cc, rr = p_col + dc, p_row + dr
            if current_map_obj.get_tile(rr, cc) == TREASURE_CHEST:
                current_map_obj.set_tile(rr, cc, GRASS)
                current_map_obj.set_tile_hp(rr, cc, 0)
                player.inventory["Sail"] = player.inventory.get("Sail", 0) + 1
                tx = cc * TILE + TILE // 2
                ty = rr * TILE + TILE // 2
                self.floats.append(
                    FloatingText(tx, ty - 20, "Got a Sail!", (255, 220, 80))
                )
                for _ in range(15):
                    self.particles.append(Particle(tx, ty, (255, 200, 60)))
                return

        # 3. On a PIER tile → try to build a boat in the next water cell
        if current_map_obj.get_tile(p_row, p_col) == PIER:
            for dc, dr in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                cc, rr = p_col + dc, p_row + dr
                if current_map_obj.get_tile(rr, cc) == WATER:
                    cost = {"Wood": BOAT_BUILD_COST, "Sail": 1}
                    tx = p_col * TILE + TILE // 2
                    ty = p_row * TILE + TILE // 2
                    if not try_spend(player.inventory, cost):
                        self.floats.append(
                            FloatingText(
                                tx,
                                ty - 20,
                                f"Need {BOAT_BUILD_COST} Wood + 1 Sail!",
                                (255, 100, 100),
                            )
                        )
                        return
                    current_map_obj.set_tile(rr, cc, BOAT)
                    current_map_obj.set_tile_hp(rr, cc, 0)
                    btx = cc * TILE + TILE // 2
                    bty = rr * TILE + TILE // 2
                    self.floats.append(
                        FloatingText(btx, bty - 20, "Boat built!", (100, 200, 255))
                    )
                    for _ in range(12):
                        self.particles.append(Particle(btx, bty, (80, 160, 220)))
                    return

    def _try_build_pier(self, player):
        """Build a 2-tile pier extending from the player's shore tile into water."""
        if player.on_boat:
            return

        current_map_obj = self.get_player_current_map(player)
        if current_map_obj is None:
            return

        p_col = int(player.x) // TILE
        p_row = int(player.y) // TILE
        rows = current_map_obj.rows
        cols = current_map_obj.cols
        tx = p_col * TILE + TILE // 2
        ty = p_row * TILE + TILE // 2

        if current_map_obj.get_tile(p_row, p_col) not in (GRASS, DIRT):
            self.floats.append(
                FloatingText(tx, ty - 20, "Build on land!", (255, 100, 100))
            )
            return

        if not try_spend(player.inventory, {"Wood": PIER_BUILD_COST}):
            self.floats.append(
                FloatingText(
                    tx, ty - 20, f"Need {PIER_BUILD_COST} Wood!", (255, 100, 100)
                )
            )
            return

        # Prefer facing direction; fall back to all four cardinal directions
        fdx = player.facing_dx
        fdy = player.facing_dy
        if abs(fdx) >= abs(fdy):
            pref = (1 if fdx > 0 else -1, 0)
        else:
            pref = (0, 1 if fdy > 0 else -1)
        all_dirs = [pref] + [d for d in [(1, 0), (-1, 0), (0, 1), (0, -1)] if d != pref]

        for dc, dr in all_dirs:
            c1, r1 = p_col + dc, p_row + dr
            c2, r2 = p_col + dc * 2, p_row + dr * 2
            if (
                0 <= c1 < cols
                and 0 <= r1 < rows
                and 0 <= c2 < cols
                and 0 <= r2 < rows
                and current_map_obj.get_tile(r1, c1) == WATER
                and current_map_obj.get_tile(r2, c2) == WATER
            ):
                current_map_obj.set_tile(r1, c1, PIER)
                current_map_obj.set_tile_hp(r1, c1, 0)
                current_map_obj.set_tile(r2, c2, PIER)
                current_map_obj.set_tile_hp(r2, c2, 0)
                self.floats.append(
                    FloatingText(tx, ty - 20, "Pier built!", (200, 160, 60))
                )
                return

        # Refund
        player.inventory["Wood"] = player.inventory.get("Wood", 0) + PIER_BUILD_COST
        self.floats.append(
            FloatingText(tx, ty - 20, "No water to build on!", (255, 100, 100))
        )

    def _get_player_sector(self, player):
        """Return the (sx, sy) sector coordinates for a player's current map.

        Overland/"overland" maps map to sector (0, 0).
        Sector maps keyed as ("sector", sx, sy) return (sx, sy).
        Cave maps return None (no sector transitions underground).
        """
        key = player.current_map
        if key == "overland" or key == ("sector", 0, 0):
            return (0, 0)
        if isinstance(key, tuple) and len(key) == 3 and key[0] == "sector":
            return (key[1], key[2])
        return None  # cave or unknown

    def _get_or_generate_sector(self, sx, sy):
        """Return (or lazily generate) the GameMap for sector (sx, sy)."""
        if sx == 0 and sy == 0:
            return self.maps["overland"]
        key = ("sector", sx, sy)
        if key not in self.maps:
            world_data = generate_ocean_sector(sx, sy, self.world_seed)
            sector_map = GameMap(world_data, tileset="overland")
            sector_map.enemies = spawn_enemies(world_data)
            self.maps[key] = sector_map
        return self.maps[key]

    def _evict_distant_sectors(self):
        """Drop sector maps that are more than 2 sectors away from all players."""
        sectors_in_use = set()
        for player in (self.player1, self.player2):
            coords = self._get_player_sector(player)
            if coords is None:
                continue
            sx, sy = coords
            for dx in range(-2, 3):
                for dy in range(-2, 3):
                    sectors_in_use.add((sx + dx, sy + dy))

        to_evict = []
        for key in self.maps:
            if isinstance(key, tuple) and len(key) == 3 and key[0] == "sector":
                if key[1] != 0 or key[2] != 0:  # never evict home island
                    if (key[1], key[2]) not in sectors_in_use:
                        to_evict.append(key)
        for key in to_evict:
            del self.maps[key]

    def check_sector_transitions(self, player):
        """Detect when an on-boat player crosses the edge of their current sector
        and teleport them to the adjacent sector with a brief wipe animation."""
        if not player.on_boat:
            return
        sector_coords = self._get_player_sector(player)
        if sector_coords is None:
            return  # underground — no sector transitions

        sx, sy = sector_coords
        current_map = self._get_or_generate_sector(sx, sy)
        world_pixel_w = current_map.cols * TILE
        world_pixel_h = current_map.rows * TILE

        x, y = player.x, player.y
        pid = player.player_id
        direction = None
        new_sx, new_sy = sx, sy
        new_x, new_y = x, y

        margin = TILE // 2  # cross within half a tile of the edge

        if x < margin:
            direction = "left"
            new_sx = sx - 1
            new_x = float(world_pixel_w - TILE)
            new_y = y
        elif x > world_pixel_w - margin:
            direction = "right"
            new_sx = sx + 1
            new_x = float(TILE)
            new_y = y
        elif y < margin:
            direction = "up"
            new_sy = sy - 1
            new_x = x
            new_y = float(world_pixel_h - TILE)
        elif y > world_pixel_h - margin:
            direction = "down"
            new_sy = sy + 1
            new_x = x
            new_y = float(TILE)

        if direction is None:
            return

        # Generate next sector (may be cached)
        self._get_or_generate_sector(new_sx, new_sy)

        # Move the player to the new sector
        new_key = (
            ("sector", new_sx, new_sy) if (new_sx != 0 or new_sy != 0) else "overland"
        )
        player.current_map = new_key
        player.x = new_x
        player.y = new_y
        self._snap_camera_to_player(player)

        # Start the wipe animation
        self.sector_wipe[pid] = {
            "progress": 0.0,
            "direction": direction,
        }

        self._evict_distant_sectors()

    def _snap_camera_to_player(self, player):
        """Immediately snap a player's camera to centre on that player."""
        if player.player_id == 1:
            self.cam1_x = player.x - self.viewport_w // 2
            self.cam1_y = player.y - self.viewport_h // 2
        else:
            self.cam2_x = player.x - self.viewport_w // 2
            self.cam2_y = player.y - self.viewport_h // 2

    @staticmethod
    def _get_settlement_tier(cluster_size):
        """Return (tier_index, tier_name) for a given cluster size."""
        for i in range(len(SETTLEMENT_TIER_SIZES) - 1, -1, -1):
            if cluster_size >= SETTLEMENT_TIER_SIZES[i]:
                return (i, SETTLEMENT_TIER_NAMES[i])
        return (0, SETTLEMENT_TIER_NAMES[0])

    def _update_town_clusters(self, build_col, build_row, player):
        """Recompute town clusters after a house is placed and announce tier upgrades."""
        overland = self.maps["overland"]
        old_clusters = overland.town_clusters

        # Determine the largest cluster any adjacent tile belonged to before this build
        old_max_size = 0
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            old_max_size = max(
                old_max_size,
                old_clusters.get((build_row + dr, build_col + dc), 0),
            )
        old_tier_idx, _ = self._get_settlement_tier(old_max_size)

        # Recompute all clusters
        new_clusters = compute_town_clusters(overland.world)
        overland.town_clusters = new_clusters

        new_size = new_clusters.get((build_row, build_col), 1)
        new_tier_idx, new_tier_name = self._get_settlement_tier(new_size)

        if new_tier_idx > old_tier_idx and new_tier_idx > 0:
            tile_cx = build_col * TILE + TILE // 2
            tile_cy = build_row * TILE + TILE // 2

            # Tier-up announcement
            self.floats.append(
                FloatingText(tile_cx, tile_cy - 40, f"{new_tier_name}!", (255, 220, 80))
            )
            for _ in range(25):
                self.particles.append(Particle(tile_cx, tile_cy, (255, 200, 60)))

            # Gameplay bonuses scale with tier
            bonus_workers = new_tier_idx
            bonus_resources = {
                1: {"Dirt": 20},
                2: {"Dirt": 40, "Stone": 20},
                3: {"Dirt": 60, "Stone": 40, "Iron": 10},
                4: {"Stone": 60, "Iron": 30, "Gold": 10},
                5: {"Iron": 50, "Gold": 30, "Diamond": 5},
            }.get(new_tier_idx, {})

            for res, qty in bonus_resources.items():
                player.inventory[res] = player.inventory.get(res, 0) + qty

            for _ in range(bonus_workers):
                self.workers.append(
                    Worker(tile_cx, tile_cy, player_id=player.player_id)
                )

            if bonus_resources:
                res_text = ", ".join(f"+{v} {k}" for k, v in bonus_resources.items())
                self.floats.append(
                    FloatingText(tile_cx, tile_cy - 56, res_text, (120, 255, 120))
                )

    def _draw_house_tile(self, tx, ty, tier, n, s, e, w, ticks):
        """Draw a house tile styled to its settlement tier.

        Args:
            tx, ty: top-left screen position of the tile
            tier: 0=Cottage, 1=Hamlet, 2=Village, 3=Town, 4=Large Town, 5=City
            n, s, e, w: True if that direction has an adjacent house tile
            ticks: pygame.time.get_ticks() for animations
        """
        sc = self.screen

        if tier == 0:
            # -- Isolated Cottage --
            pygame.draw.rect(sc, (180, 120, 60), (tx + 4, ty + 12, 24, 18))
            pygame.draw.polygon(
                sc,
                (160, 40, 40),
                [(tx + 2, ty + 12), (tx + 16, ty + 2), (tx + 30, ty + 12)],
            )
            pygame.draw.rect(sc, (100, 60, 30), (tx + 12, ty + 19, 8, 11))
            pygame.draw.rect(sc, (180, 220, 255), (tx + 7, ty + 15, 5, 5))
            pygame.draw.rect(sc, (80, 60, 40), (tx + 7, ty + 15, 5, 5), 1)

        elif tier == 1:
            # -- Hamlet: warm cottage with chimney, wood grain, amber window --
            wall_c = (185, 130, 70)
            roof_c = (178, 55, 55)
            pygame.draw.rect(sc, wall_c, (tx + 3, ty + 11, 26, 19))
            # Wood-grain horizontal lines
            for ly in range(ty + 15, ty + 30, 4):
                pygame.draw.line(sc, (150, 100, 45), (tx + 3, ly), (tx + 29, ly), 1)
            # Roof
            if n:
                pygame.draw.rect(sc, roof_c, (tx + 3, ty + 7, 26, 5))
            else:
                pygame.draw.polygon(
                    sc,
                    roof_c,
                    [(tx + 1, ty + 11), (tx + 16, ty + 1), (tx + 31, ty + 11)],
                )
            # Chimney
            pygame.draw.rect(sc, (120, 100, 85), (tx + 21, ty + 3, 4, 9))
            pygame.draw.rect(sc, (90, 80, 70), (tx + 20, ty + 2, 6, 3))
            # Door with arch top
            pygame.draw.rect(sc, (110, 65, 30), (tx + 12, ty + 21, 8, 9))
            pygame.draw.ellipse(sc, (110, 65, 30), (tx + 11, ty + 17, 10, 8))
            # Amber lit window
            pygame.draw.rect(sc, (255, 215, 120), (tx + 5, ty + 14, 5, 5))
            pygame.draw.rect(sc, (80, 60, 40), (tx + 5, ty + 14, 5, 5), 1)
            # Second window (right side)
            pygame.draw.rect(sc, (255, 215, 120), (tx + 22, ty + 14, 5, 5))
            pygame.draw.rect(sc, (80, 60, 40), (tx + 22, ty + 14, 5, 5), 1)
            # Path connectors on linked sides
            path_c = (175, 158, 128)
            if s:
                pygame.draw.rect(sc, path_c, (tx + 13, ty + 30, 6, 2))
            if e:
                pygame.draw.rect(sc, path_c, (tx + 30, ty + 22, 2, 5))
            if w:
                pygame.draw.rect(sc, path_c, (tx, ty + 22, 2, 5))

        elif tier == 2:
            # -- Village: row-house with brick walls, parapet, double windows --
            wall_c = (195, 105, 55)  # orange brick
            brick_c = (155, 78, 38)  # mortar / darker brick
            roof_c = (160, 82, 60)  # terracotta parapet
            # Wall extends to adjacent sides seamlessly
            lx = tx if w else tx + 3
            rx = tx + 32 if e else tx + 29
            ty2 = ty if n else ty + 6
            by2 = ty + 32 if s else ty + 30
            pygame.draw.rect(sc, wall_c, (lx, ty2, rx - lx, by2 - ty2))
            # Brick mortar lines
            for ly in range(ty2 + 5, by2, 5):
                pygame.draw.line(sc, brick_c, (lx, ly), (rx, ly), 1)
            # Parapet / roof on exposed north
            if not n:
                pygame.draw.rect(sc, roof_c, (lx, ty2 - 4, rx - lx, 5))
                for bx in range(lx, rx, 6):
                    pygame.draw.rect(sc, (130, 65, 45), (bx, ty2 - 7, 4, 3))
            # Two windows side by side
            for wx in (tx + 5, tx + 20):
                pygame.draw.rect(sc, (200, 225, 255), (wx, ty + 10, 6, 8))
                pygame.draw.line(
                    sc, (130, 100, 75), (wx + 3, ty + 10), (wx + 3, ty + 18), 1
                )
            # Arched doorway on south-exposed face
            if not s:
                pygame.draw.rect(sc, (105, 58, 28), (tx + 13, ty + 22, 6, 8))
                pygame.draw.ellipse(sc, (105, 58, 28), (tx + 11, ty + 18, 10, 8))

        elif tier == 3:
            # -- Town: stone walls, slate parapet with crenellations, 4-window grid --
            wall_c = (130, 125, 118)  # stone gray
            stone_c = (108, 104, 98)  # stone shadow
            roof_c = (88, 90, 102)  # slate
            lx = tx if w else tx + 2
            rx = tx + 32 if e else tx + 30
            ty2 = ty if n else ty + 3
            by2 = ty + 32 if s else ty + 30
            pygame.draw.rect(sc, wall_c, (lx, ty2, rx - lx, by2 - ty2))
            # Stone block texture (horizontal courses)
            for iy in range(ty2 + 6, by2, 7):
                pygame.draw.line(sc, stone_c, (lx, iy), (rx, iy), 1)
            # Vertical joints (offset each row)
            row_i = 0
            for iy in range(ty2 + 6, by2, 7):
                offset = 5 if row_i % 2 == 0 else 1
                for ix in range(lx + offset, rx, 10):
                    pygame.draw.line(sc, stone_c, (ix, iy - 6), (ix, iy), 1)
                row_i += 1
            # Slate roof + crenellations on exposed north
            if not n:
                pygame.draw.rect(sc, roof_c, (lx, ty2 - 5, rx - lx, 6))
                for bx in range(lx, rx, 5):
                    pygame.draw.rect(sc, (68, 70, 82), (bx, ty2 - 8, 3, 3))
            # 2×2 window grid
            win_c = (145, 175, 215)
            for wy, wx in [
                (ty + 8, tx + 5),
                (ty + 8, tx + 19),
                (ty + 18, tx + 5),
                (ty + 18, tx + 19),
            ]:
                pygame.draw.rect(sc, win_c, (wx, wy, 5, 6))
                pygame.draw.line(sc, (85, 110, 150), (wx + 2, wy), (wx + 2, wy + 6), 1)
                pygame.draw.line(sc, (85, 110, 150), (wx, wy + 3), (wx + 5, wy + 3), 1)
            # Recessed door
            if not s:
                pygame.draw.rect(sc, (55, 42, 28), (tx + 12, ty + 23, 8, 7))

        elif tier == 4:
            # -- Large Town: deep red brick, multi-row windows, iron roof, awning --
            wall_c = (158, 78, 65)  # deep red brick
            brick_c = (122, 55, 44)  # dark mortar
            roof_c = (55, 58, 68)  # iron grey
            lx = tx if w else tx + 1
            rx = tx + 32 if e else tx + 31
            ty2 = ty if n else ty + 2
            by2 = ty + 32 if s else ty + 31
            pygame.draw.rect(sc, wall_c, (lx, ty2, rx - lx, by2 - ty2))
            # Dense brick courses
            for iy in range(ty2 + 4, by2, 5):
                pygame.draw.line(sc, brick_c, (lx, iy), (rx, iy), 1)
            # Brick bonds (alternating vertical joints)
            row_i = 0
            for iy in range(ty2 + 4, by2, 5):
                offset = 4 if row_i % 2 == 0 else 0
                for ix in range(lx + offset, rx, 8):
                    pygame.draw.line(sc, brick_c, (ix, iy - 4), (ix, iy), 1)
                row_i += 1
            # Iron roof parapet
            if not n:
                pygame.draw.rect(sc, roof_c, (lx, ty2 - 4, rx - lx, 5))
                for bx in range(lx, rx, 4):
                    pygame.draw.rect(sc, (35, 38, 48), (bx, ty2 - 6, 2, 2))
            # 3 rows × 2 columns of windows
            win_c = (185, 205, 245)
            for wy in (ty + 4, ty + 13, ty + 22):
                for wx in (tx + 5, tx + 21):
                    pygame.draw.rect(sc, win_c, (wx, wy, 5, 7))
                    pygame.draw.line(
                        sc, (130, 150, 200), (wx + 2, wy), (wx + 2, wy + 7), 1
                    )
                    pygame.draw.line(
                        sc, (130, 150, 200), (wx, wy + 3), (wx + 5, wy + 3), 1
                    )
            # Merchant awning on exposed south
            if not s:
                pygame.draw.rect(sc, (195, 85, 55), (tx + 3, ty + 24, 26, 3))
                for ax in range(tx + 3, tx + 29, 4):
                    pygame.draw.line(
                        sc, (220, 100, 70), (ax, ty + 24), (ax + 2, ty + 27), 1
                    )

        else:
            # -- City (tier 5): dark slate, gothic arch windows, spire --
            pulse = int(math.sin(ticks * 0.002) * 10)
            wall_c = (72, 78, 95)  # slate blue-grey
            stone_c = (56, 62, 78)  # deep shadow
            roof_c = (38, 42, 58)  # dark steel
            gold_c = (200, 170, 80 + pulse)  # animated gold trim
            lx = tx
            rx = tx + 32
            ty2 = ty
            by2 = ty + 32
            pygame.draw.rect(sc, wall_c, (lx, ty2, rx - lx, by2 - ty2))
            # Stone block grid
            for iy in range(ty2 + 5, by2, 6):
                for ix in range(lx, rx, 9):
                    pygame.draw.rect(sc, stone_c, (ix, iy, 8, 5), 1)
            # Spire on exposed north
            if not n:
                mid = tx + 16
                pygame.draw.polygon(
                    sc,
                    roof_c,
                    [
                        (mid - 3, ty2),
                        (mid + 3, ty2),
                        (mid + 1, ty2 - 9),
                        (mid - 1, ty2 - 9),
                    ],
                )
                pygame.draw.polygon(
                    sc,
                    gold_c,
                    [(mid - 1, ty2 - 9), (mid + 1, ty2 - 9), (mid, ty2 - 14)],
                )
                pygame.draw.rect(sc, roof_c, (lx, ty2 - 4, rx - lx, 5))
                # Gold crenellation trim
                for bx in range(lx, rx, 5):
                    pygame.draw.rect(sc, gold_c, (bx, ty2 - 5, 3, 2))
            # Gothic arch windows (3 rows × 2 cols)
            win_c = (110, 145, 205)
            for wy in (ty + 3, ty + 13, ty + 21):
                for wx in (tx + 4, tx + 21):
                    # Arch body
                    pygame.draw.rect(sc, win_c, (wx, wy + 3, 6, 6))
                    pygame.draw.ellipse(sc, win_c, (wx, wy, 6, 6))
                    # Gold arch trim
                    pygame.draw.ellipse(sc, gold_c, (wx, wy, 6, 6), 1)
            # Iron-bound door on exposed south
            if not s:
                pygame.draw.rect(sc, (40, 32, 22), (tx + 12, ty + 24, 8, 8))
                pygame.draw.ellipse(sc, (40, 32, 22), (tx + 11, ty + 20, 10, 8))
                pygame.draw.ellipse(sc, gold_c, (tx + 11, ty + 20, 10, 8), 1)

    def _nearest_living_player(self, map_key, enemy):
        """Return the nearest living player on map_key, or None if none present."""
        candidates = [
            p
            for p in (self.player1, self.player2)
            if p.current_map == map_key and not p.is_dead
        ]
        if not candidates:
            return None
        return min(candidates, key=lambda p: math.hypot(p.x - enemy.x, p.y - enemy.y))

    def check_cave_transitions(self, player, current_map):
        """Check if player stepped on a cave entrance and transition if so."""
        if player.current_map != "overland":
            return  # Only check for cave entry when on overland map

        if current_map != self.maps["overland"]:
            return

        tile_col = int(player.x) // TILE
        tile_row = int(player.y) // TILE

        if not (0 <= tile_col < WORLD_COLS and 0 <= tile_row < WORLD_ROWS):
            return

        tile_id = current_map.get_tile(tile_row, tile_col)

        # Check if standing on a cave entrance
        if tile_id in (CAVE_MOUNTAIN, CAVE_HILL):
            # Generate or load the cave map
            cave_key = (tile_col, tile_row)
            if cave_key not in self.maps:
                env = CaveEnvironment(tile_col, tile_row, cave_type=tile_id)
                self.maps[cave_key] = env.generate()

            cave_map = self.maps[cave_key]
            # Teleport player to cave spawn point (away from exit)
            player.x = cave_map.spawn_col * TILE + TILE // 2
            player.y = cave_map.spawn_row * TILE + TILE // 2
            player.current_map = cave_key

            self._snap_camera_to_player(player)
            self.floats.append(
                FloatingText(player.x, player.y - 30, "Entered cave!", (100, 150, 255))
            )

    def check_cave_exits(self, player, current_map):
        """Check if player stepped on a cave exit and transition back to overland."""
        if player.current_map == "overland":
            return  # Already on overland

        if current_map == self.maps["overland"]:
            return  # Not on a cave map

        # Check if player is standing on a CAVE_EXIT tile
        if not hasattr(current_map, "entrance_col"):
            return

        tile_col = int(player.x) // TILE
        tile_row = int(player.y) // TILE

        tile_id = current_map.get_tile(tile_row, tile_col)
        if tile_id == CAVE_EXIT:
            # Return to overland map near cave entrance (but NOT on the cave tile itself,
            # otherwise check_cave_transitions will send us right back in)
            entrance_col = current_map.entrance_col
            entrance_row = current_map.entrance_row
            overland = self.maps["overland"]

            # Find a walkable adjacent tile that isn't a cave entrance
            placed = False
            for dr, dc in [
                (1, 0),
                (-1, 0),
                (0, 1),
                (0, -1),
                (1, 1),
                (-1, -1),
                (1, -1),
                (-1, 1),
            ]:
                adj_c = entrance_col + dc
                adj_r = entrance_row + dr
                if 0 <= adj_c < overland.cols and 0 <= adj_r < overland.rows:
                    adj_tile = overland.get_tile(adj_r, adj_c)
                    if adj_tile not in (WATER, MOUNTAIN, CAVE_MOUNTAIN, CAVE_HILL):
                        player.x = adj_c * TILE + TILE // 2
                        player.y = adj_r * TILE + TILE // 2
                        placed = True
                        break
            if not placed:
                # Fallback: place on the cave tile anyway (rare edge case)
                player.x = entrance_col * TILE + TILE // 2
                player.y = entrance_row * TILE + TILE // 2

            player.current_map = "overland"

            self._snap_camera_to_player(player)
            self.floats.append(
                FloatingText(player.x, player.y - 30, "Exited cave!", (100, 255, 150))
            )

    # -- update ------------------------------------------------------------

    def update(self, dt):
        """Update game state (both players, shared world)."""
        # Update viewport sizes to match actual screen, just like draw() does
        screen_width, screen_height = self.screen.get_size()
        self.viewport_w = screen_width // 2
        self.viewport_h = screen_height

        keys = pygame.key.get_pressed()
        mouse_buttons = pygame.mouse.get_pressed()

        # Get player maps
        map1 = self.get_player_current_map(self.player1)
        map2 = self.get_player_current_map(self.player2)

        # Check for cave transitions (only for living players)
        if not self.player1.is_dead:
            self.check_cave_transitions(self.player1, map1)
        if not self.player2.is_dead:
            self.check_cave_transitions(self.player2, map2)

        # Update maps after potential transitions
        map1 = self.get_player_current_map(self.player1)
        map2 = self.get_player_current_map(self.player2)

        # Check for cave exits (only for living players)
        if not self.player1.is_dead:
            self.check_cave_exits(self.player1, map1)
        if not self.player2.is_dead:
            self.check_cave_exits(self.player2, map2)

        # Update maps again after potential exits
        map1 = self.get_player_current_map(self.player1)
        map2 = self.get_player_current_map(self.player2)

        # -- Sector-wipe animation tick ------------------------------------
        for pid in list(self.sector_wipe.keys()):
            self.sector_wipe[pid]["progress"] += dt / SECTOR_WIPE_DURATION
            if self.sector_wipe[pid]["progress"] >= 1.0:
                del self.sector_wipe[pid]
        # ----------------------------------------------------------------

        # -- Sector transitions for on-boat players -----------------------
        if not self.player1.is_dead:
            self.check_sector_transitions(self.player1)
        if not self.player2.is_dead:
            self.check_sector_transitions(self.player2)
        # ----------------------------------------------------------------

        # -- Boat disembark detection (before movement) -------------------
        for player in (self.player1, self.player2):
            if player.is_dead or not player.on_boat:
                continue
            cur_map = self.get_player_current_map(player)
            if cur_map is None:
                continue
            pc = int(player.x) // TILE
            pr = int(player.y) // TILE
            if cur_map.get_tile(pr, pc) == WATER:
                # Track the last water tile while sailing
                player.boat_col = pc
                player.boat_row = pr
            else:
                player.on_boat = False
                # Restore the boat tile at the last water position
                if player.boat_col is not None and player.boat_row is not None:
                    cur_map.set_tile(player.boat_row, player.boat_col, BOAT)
                    cur_map.set_tile_hp(player.boat_row, player.boat_col, 0)
                    player.boat_col = None
                    player.boat_row = None
                # Snap centre to the middle of the land tile so no part of the
                # hitbox overlaps water when collision resumes next movement step
                player.x = pc * TILE + TILE // 2
                player.y = pr * TILE + TILE // 2
        # ----------------------------------------------------------------

        # Player 1 movement & mining (skipped while dead)
        if not self.player1.is_dead:
            self.player1.update_movement(keys, dt, map1.world)
            self.player1.update_mining(
                keys,
                mouse_buttons,
                dt,
                map1.world,
                map1.tile_hp,
                self.cam1_x,
                self.cam1_y,
                self.particles,
                self.floats,
            )
            if self.player1.hurt_timer > 0:
                self.player1.hurt_timer -= dt

        # Player 2 movement & mining (skipped while dead)
        if not self.player2.is_dead:
            self.player2.update_movement(keys, dt, map2.world)
            self.player2.update_mining(
                keys,
                mouse_buttons,
                dt,
                map2.world,
                map2.tile_hp,
                self.cam2_x,
                self.cam2_y,
                self.particles,
                self.floats,
            )
            if self.player2.hurt_timer > 0:
                self.player2.hurt_timer -= dt

        # -- Boat boarding detection --------------------------------------
        for player in (self.player1, self.player2):
            if player.is_dead or player.on_boat:
                continue
            cur_map = self.get_player_current_map(player)
            if cur_map is None:
                continue
            pc = int(player.x) // TILE
            pr = int(player.y) // TILE
            if cur_map.get_tile(pr, pc) == BOAT:
                player.on_boat = True
                player.boat_col = pc
                player.boat_row = pr
                cur_map.set_tile(pr, pc, WATER)
                cur_map.set_tile_hp(pr, pc, 0)
                self.floats.append(
                    FloatingText(
                        int(player.x),
                        int(player.y) - 20,
                        "On the boat!",
                        (100, 200, 255),
                    )
                )
        # ----------------------------------------------------------------

        # Workers (each assigned to a specific player) - only on overland map
        overland_map = self.maps["overland"]
        for w in self.workers:
            # Get the player this worker is assigned to
            target_player = self.player1 if w.player_id == 1 else self.player2
            w.update(
                dt,
                overland_map.world,
                overland_map.tile_hp,
                target_player.inventory,
                self.particles,
                self.floats,
            )
            # Award XP to the player this worker is assigned to
            target_player.xp += w.xp_earned
            w.xp_earned = 0

        # Pets (only on overland map)
        for pet in self.pets:
            # Pets follow the closest player
            dist1 = math.hypot(pet.x - self.player1.x, pet.y - self.player1.y)
            dist2 = math.hypot(pet.x - self.player2.x, pet.y - self.player2.y)
            target = self.player1 if dist1 < dist2 else self.player2
            pet.update(dt, target.x, target.y, overland_map.world)

        # Enemies
        self._update_enemies(dt)
        self._update_cave_enemies(dt)

        # Weapon firing (for both players)
        self._update_combat(keys, mouse_buttons, dt)

        # Projectiles & XP (for both players)
        self._update_projectiles(dt)
        self.player1.check_level_up(self.particles, self.floats)
        self.player2.check_level_up(self.particles, self.floats)

        # Cull dead enemies
        self.enemies = [e for e in self.enemies if e.hp > 0]

        # Cameras
        self.cam1_x += (self.player1.x - self.viewport_w // 2 - self.cam1_x) * 0.1
        self.cam1_y += (self.player1.y - self.viewport_h // 2 - self.cam1_y) * 0.1
        self.cam2_x += (self.player2.x - self.viewport_w // 2 - self.cam2_x) * 0.1
        self.cam2_y += (self.player2.y - self.viewport_h // 2 - self.cam2_y) * 0.1

        # Clamp cameras to world bounds (each player might be on different size map)
        map1 = self.get_player_current_map(self.player1)
        map2 = self.get_player_current_map(self.player2)

        world1_pixel_w = map1.cols * TILE if map1 else WORLD_COLS * TILE
        world1_pixel_h = map1.rows * TILE if map1 else WORLD_ROWS * TILE
        world2_pixel_w = map2.cols * TILE if map2 else WORLD_COLS * TILE
        world2_pixel_h = map2.rows * TILE if map2 else WORLD_ROWS * TILE

        self.cam1_x = max(0, min(self.cam1_x, world1_pixel_w - self.viewport_w))
        self.cam1_y = max(0, min(self.cam1_y, world1_pixel_h - self.viewport_h))
        self.cam2_x = max(0, min(self.cam2_x, world2_pixel_w - self.viewport_w))
        self.cam2_y = max(0, min(self.cam2_y, world2_pixel_h - self.viewport_h))

        # Effects
        for par in self.particles:
            par.update()
        self.particles = [par for par in self.particles if par.life > 0]
        for f in self.floats:
            f.update()
        self.floats = [f for f in self.floats if f.life > 0]

    def _update_enemies(self, dt):
        """Update all enemies and check for attacks on both players."""
        overland_map = self.maps["overland"]
        avg_cam_x = (self.cam1_x + self.cam2_x) / 2
        avg_cam_y = (self.cam1_y + self.cam2_y) / 2
        for enemy in self.enemies:
            target_player = self._nearest_living_player("overland", enemy)
            if target_player is None:
                continue
            enemy.update(
                dt,
                target_player.x,
                target_player.y,
                avg_cam_x,
                avg_cam_y,
                overland_map.world,
                self.particles,
            )
            dmg = enemy.try_attack(target_player.x, target_player.y)
            if dmg > 0:
                target_player.take_damage(dmg, self.particles, self.floats)
                if target_player.hp <= 0 and not target_player.is_dead:
                    self._start_death_challenge(target_player)

    def _draw_sector_wipe_viewport(self, screen_x, screen_y, view_w, view_h, progress):
        """Draw a quick scroll-wipe flash when crossing a sector boundary.

        The first half of the animation blurs/fades out the old view with a
        horizontal or vertical white flash; the second half fades into the new
        view which is already rendered behind it.  We overlay a white rect
        whose alpha peaks at midpoint (progress == 0.5) and falls back to 0.
        """
        # Compute alpha: 0 → 255 at progress 0.5 → 0
        alpha = int(255 * (1.0 - abs(progress - 0.5) * 2.0))
        alpha = max(0, min(255, alpha))
        if alpha == 0:
            return
        flash = pygame.Surface((view_w, view_h), pygame.SRCALPHA)
        flash.fill((220, 240, 255, alpha))
        self.screen.blit(flash, (screen_x, screen_y))

    def _update_cave_enemies(self, dt):
        """Update enemies inside caves that currently contain at least one player."""
        active_caves = {
            p.current_map
            for p in (self.player1, self.player2)
            if not p.is_dead and isinstance(p.current_map, tuple)
        }
        for cave_key in active_caves:
            cave_map = self.maps.get(cave_key)
            if cave_map is None:
                continue

            # Camera for on-screen culling: average of players in this cave
            cave_cams = [
                (
                    (self.cam1_x, self.cam1_y)
                    if p is self.player1
                    else (self.cam2_x, self.cam2_y)
                )
                for p in (self.player1, self.player2)
                if p.current_map == cave_key and not p.is_dead
            ]
            cam_x = sum(c[0] for c in cave_cams) / len(cave_cams)
            cam_y = sum(c[1] for c in cave_cams) / len(cave_cams)

            for enemy in cave_map.enemies:
                target_player = self._nearest_living_player(cave_key, enemy)
                if target_player is None:
                    continue
                enemy.update(
                    dt,
                    target_player.x,
                    target_player.y,
                    cam_x,
                    cam_y,
                    cave_map.world,
                    self.particles,
                )
                dmg = enemy.try_attack(target_player.x, target_player.y)
                if dmg > 0:
                    target_player.take_damage(dmg, self.particles, self.floats)
                    if target_player.hp <= 0 and not target_player.is_dead:
                        self._start_death_challenge(target_player)

            cave_map.enemies = [e for e in cave_map.enemies if e.hp > 0]

    def _update_combat(self, keys, mouse_buttons, dt):
        """Handle weapon firing for both players."""
        # Player 1 firing (skipped while dead)
        if self.player1.weapon_cooldown > 0:
            self.player1.weapon_cooldown -= dt
        if not self.player1.is_dead:
            fire_input_p1 = (
                keys[self.player1.controls.fire_key]
                or mouse_buttons[2]
                or self.player1.auto_fire
            )
            if fire_input_p1 and self.player1.weapon_cooldown <= 0:
                wpn = WEAPONS[self.player1.weapon_level]
                self.projectiles.append(
                    Projectile(
                        self.player1.x,
                        self.player1.y,
                        self.player1.facing_dx,
                        self.player1.facing_dy,
                        wpn,
                        player_id=1,
                        map_key=self.player1.current_map,
                    )
                )
                self.player1.weapon_cooldown = wpn["cooldown"]

        # Player 2 firing (skipped while dead)
        if self.player2.weapon_cooldown > 0:
            self.player2.weapon_cooldown -= dt
        if not self.player2.is_dead:
            fire_input_p2 = (
                keys[self.player2.controls.fire_key] or self.player2.auto_fire
            )
            if fire_input_p2 and self.player2.weapon_cooldown <= 0:
                wpn = WEAPONS[self.player2.weapon_level]
                self.projectiles.append(
                    Projectile(
                        self.player2.x,
                        self.player2.y,
                        self.player2.facing_dx,
                        self.player2.facing_dy,
                        wpn,
                        player_id=2,
                        map_key=self.player2.current_map,
                    )
                )
                self.player2.weapon_cooldown = wpn["cooldown"]

    def _update_projectiles(self, dt):
        """Update all projectiles and check for hits against enemies on the same map."""
        for proj in self.projectiles:
            proj.update(dt)
            if proj.alive:
                if proj.map_key == "overland":
                    proj.check_hits(self.enemies, self.particles, self.floats)
                elif isinstance(proj.map_key, tuple):
                    cave_map = self.maps.get(proj.map_key)
                    if cave_map:
                        proj.check_hits(cave_map.enemies, self.particles, self.floats)
            if proj.player_id == 1:
                self.player1.xp += proj.xp_earned
            elif proj.player_id == 2:
                self.player2.xp += proj.xp_earned
            proj.xp_earned = 0
        self.projectiles = [proj for proj in self.projectiles if proj.alive]

    # -- drawing -----------------------------------------------------------

    def draw(self):
        """Render split-screen for both players."""
        # Get actual screen dimensions and update viewport sizes
        screen_width, screen_height = self.screen.get_size()
        self.viewport_w = screen_width // 2
        self.viewport_h = screen_height

        # Left side: Player 1
        self._draw_player_view(
            self.player1,
            self.cam1_x,
            self.cam1_y,
            0,
            0,
            self.viewport_w,
            self.viewport_h,
        )

        # Right side: Player 2
        self._draw_player_view(
            self.player2,
            self.cam2_x,
            self.cam2_y,
            self.viewport_w,
            0,
            self.viewport_w,
            self.viewport_h,
        )

        # Separator line
        pygame.draw.line(
            self.screen,
            (100, 100, 100),
            (self.viewport_w, 0),
            (self.viewport_w, screen_height),
            2,
        )

        pygame.display.flip()

    def _draw_player_view(
        self, player, cam_x, cam_y, screen_x, screen_y, view_w, view_h
    ):
        """Draw a single player's viewport."""
        self.screen.set_clip(pygame.Rect(screen_x, screen_y, view_w, view_h))

        # Get the map the player is currently on
        current_map = self.get_player_current_map(player)
        if current_map is None:
            current_map = self.maps["overland"]

        world_cols = current_map.cols
        world_rows = current_map.rows
        world_pixel_w = world_cols * TILE
        world_pixel_h = world_rows * TILE

        # Stone border colors
        border_outer = (60, 50, 40)  # Dark stone
        border_inner = (100, 85, 70)  # Light stone

        # Left border
        if cam_x < 0:
            border_width = min(view_w, int(-cam_x) + screen_x)
            pygame.draw.rect(
                self.screen, border_outer, (screen_x, screen_y, border_width, view_h)
            )
            # Add decorative bricks
            for by in range(screen_y, screen_y + view_h, 16):
                pygame.draw.rect(
                    self.screen, border_inner, (screen_x + 2, by, border_width - 4, 8)
                )

        # Right border
        if cam_x + view_w > world_pixel_w:
            border_start = max(0, int(world_pixel_w - cam_x) + screen_x)
            border_width = screen_x + view_w - border_start
            pygame.draw.rect(
                self.screen,
                border_outer,
                (border_start, screen_y, border_width, view_h),
            )
            # Add decorative bricks
            for by in range(screen_y, screen_y + view_h, 16):
                pygame.draw.rect(
                    self.screen,
                    border_inner,
                    (border_start + 2, by, border_width - 4, 8),
                )

        # Top border
        if cam_y < 0:
            border_height = min(view_h, int(-cam_y) + screen_y)
            pygame.draw.rect(
                self.screen, border_outer, (screen_x, screen_y, view_w, border_height)
            )
            # Add decorative bricks
            for bx in range(screen_x, screen_x + view_w, 16):
                pygame.draw.rect(
                    self.screen, border_inner, (bx, screen_y + 2, 8, border_height - 4)
                )

        # Bottom border
        if cam_y + view_h > world_pixel_h:
            border_start = max(0, int(world_pixel_h - cam_y) + screen_y)
            border_height = screen_y + view_h - border_start
            pygame.draw.rect(
                self.screen,
                border_outer,
                (screen_x, border_start, view_w, border_height),
            )
            # Add decorative bricks
            for bx in range(screen_x, screen_x + view_w, 16):
                pygame.draw.rect(
                    self.screen,
                    border_inner,
                    (bx, border_start + 2, 8, border_height - 4),
                )

        # Draw terrain for this viewport
        ticks = pygame.time.get_ticks()
        start_col = max(0, int(cam_x) // TILE)
        end_col = min(world_cols, int(cam_x + view_w) // TILE + 2)
        start_row = max(0, int(cam_y) // TILE)
        end_row = min(world_rows, int(cam_y + view_h) // TILE + 2)

        for r in range(start_row, end_row):
            for c in range(start_col, end_col):
                tid = current_map.get_tile(r, c)
                if tid is None:
                    continue
                info = TILE_INFO.get(tid, {})
                # Use tileset-aware color
                tile_color = current_map.get_tileset_color(tid)
                sx = c * TILE - int(cam_x) + screen_x
                sy = r * TILE - int(cam_y) + screen_y
                pygame.draw.rect(self.screen, tile_color, (sx, sy, TILE, TILE))

                if tid == TREE:
                    pygame.draw.rect(
                        self.screen, (100, 70, 30), (sx + 12, sy + 16, 8, 16)
                    )
                    pygame.draw.circle(
                        self.screen, (30, 130, 30), (sx + 16, sy + 12), 12
                    )
                elif tid in (IRON_ORE, GOLD_ORE, DIAMOND_ORE):
                    for ox, oy in [(8, 8), (20, 12), (14, 22), (24, 24)]:
                        bright = [min(255, ch + 80) for ch in info["color"]]
                        pygame.draw.rect(self.screen, bright, (sx + ox, sy + oy, 3, 3))
                elif tid == WATER:
                    wave_off = int(
                        math.sin(pygame.time.get_ticks() * 0.003 + c * 0.7) * 3
                    )
                    pygame.draw.line(
                        self.screen,
                        (60, 150, 230),
                        (sx + 4, sy + 14 + wave_off),
                        (sx + 28, sy + 14 + wave_off),
                        2,
                    )
                elif tid == MOUNTAIN:
                    # Check if this is part of a 2x2 mountain group starting from top-left
                    is_2x2_tl = (
                        c + 1 < world_cols
                        and r + 1 < world_rows
                        and current_map.get_tile(r, c) == MOUNTAIN
                        and current_map.get_tile(r, c + 1) == MOUNTAIN
                        and current_map.get_tile(r + 1, c) == MOUNTAIN
                        and current_map.get_tile(r + 1, c + 1) == MOUNTAIN
                    )

                    # Check if current tile is part of a larger 2x2 block
                    is_part_of_2x2 = False
                    if is_2x2_tl:
                        is_part_of_2x2 = True
                    else:
                        # Check if we're part of a 2x2 block from other positions
                        for dc, dr in [(-1, 0), (0, -1), (-1, -1)]:
                            check_c, check_r = c + dc, r + dr
                            if (
                                check_c >= 0
                                and check_r >= 0
                                and check_c + 1 < world_cols
                                and check_r + 1 < world_rows
                            ):
                                if (
                                    current_map.get_tile(check_r, check_c) == MOUNTAIN
                                    and current_map.get_tile(check_r, check_c + 1)
                                    == MOUNTAIN
                                    and current_map.get_tile(check_r + 1, check_c)
                                    == MOUNTAIN
                                    and current_map.get_tile(check_r + 1, check_c + 1)
                                    == MOUNTAIN
                                ):
                                    is_part_of_2x2 = True
                                    break

                    if is_2x2_tl:
                        # Draw multiple ridge-like peaks for 2x2 mountain groups
                        base_y = sy + TILE * 2
                        block_left_x = sx
                        block_right_x = sx + TILE * 2

                        # Define peaks (x_offset from block_left, height)
                        peaks = [
                            (12, sy - TILE // 3),  # Left-center peak
                            (24, sy - TILE // 5),  # Center-right peak
                            (36, sy - TILE // 3.5),  # Right peak
                        ]

                        # Draw background mountain
                        pygame.draw.polygon(
                            self.screen,
                            (80, 70, 60),
                            [
                                (block_left_x, base_y),
                                (block_left_x + 8, sy + TILE // 2),
                                (block_right_x - 8, sy + TILE // 2),
                                (block_right_x, base_y),
                            ],
                        )

                        # Draw each peak (wider and ridge-like)
                        for peak_x, peak_y in peaks:
                            x = block_left_x + peak_x
                            width = 18  # Width of each ridge peak

                            # Left slope (darker)
                            pygame.draw.polygon(
                                self.screen,
                                (60, 50, 40),
                                [
                                    (x - width, base_y),
                                    (x, peak_y),
                                    (x, base_y),
                                ],
                            )
                            # Right slope (lighter)
                            pygame.draw.polygon(
                                self.screen,
                                (100, 85, 65),
                                [
                                    (x, peak_y),
                                    (x + width, base_y),
                                    (x, base_y),
                                ],
                            )
                            # Wide snow cap on ridge
                            pygame.draw.polygon(
                                self.screen,
                                (245, 250, 255),
                                [
                                    (x - 8, peak_y + 6),
                                    (x, peak_y),
                                    (x + 8, peak_y + 6),
                                ],
                            )
                    elif not is_part_of_2x2:
                        # Draw regular small mountain triangles (only if not part of a 2x2 block)
                        pygame.draw.polygon(
                            self.screen,
                            (110, 100, 90),
                            [
                                (sx + 4, sy + TILE),
                                (sx + 16, sy + 2),
                                (sx + TILE - 4, sy + TILE),
                            ],
                        )
                        pygame.draw.polygon(
                            self.screen,
                            (230, 230, 240),
                            [(sx + 12, sy + 8), (sx + 16, sy + 2), (sx + 20, sy + 8)],
                        )
                        pygame.draw.line(
                            self.screen,
                            (70, 65, 60),
                            (sx + 10, sy + 18),
                            (sx + 14, sy + 12),
                            1,
                        )
                        pygame.draw.line(
                            self.screen,
                            (70, 65, 60),
                            (sx + 20, sy + 20),
                            (sx + 22, sy + 14),
                            1,
                        )
                elif tid == HOUSE:
                    cluster_size = current_map.town_clusters.get((r, c), 1)
                    tier, _ = self._get_settlement_tier(cluster_size)
                    hn = current_map.get_tile(r - 1, c) == HOUSE
                    hs = current_map.get_tile(r + 1, c) == HOUSE
                    he = current_map.get_tile(r, c + 1) == HOUSE
                    hw = current_map.get_tile(r, c - 1) == HOUSE
                    self._draw_house_tile(sx, sy, tier, hn, hs, he, hw, ticks)
                elif tid == PIER:
                    # Wood-plank dock over water
                    plank_c = (155, 115, 50)
                    edge_c = (100, 75, 30)
                    pygame.draw.rect(self.screen, plank_c, (sx + 2, sy + 2, 28, 28))
                    # Plank lines
                    for lx in range(sx + 6, sx + 29, 7):
                        pygame.draw.line(
                            self.screen, edge_c, (lx, sy + 2), (lx, sy + 30), 1
                        )
                    pygame.draw.rect(self.screen, edge_c, (sx + 2, sy + 2, 28, 28), 1)
                elif tid == BOAT:
                    # Small moored boat
                    pygame.draw.polygon(
                        self.screen,
                        (120, 80, 40),
                        [
                            (sx + 4, sy + 18),
                            (sx + 28, sy + 18),
                            (sx + 24, sy + 28),
                            (sx + 8, sy + 28),
                        ],
                    )
                    # Mast
                    pygame.draw.line(
                        self.screen,
                        (80, 55, 25),
                        (sx + 16, sy + 4),
                        (sx + 16, sy + 18),
                        2,
                    )
                    # Sail
                    pygame.draw.polygon(
                        self.screen,
                        (235, 225, 195),
                        [(sx + 17, sy + 5), (sx + 17, sy + 17), (sx + 27, sy + 11)],
                    )
                    # Cabin
                    pygame.draw.rect(
                        self.screen, (160, 110, 55), (sx + 10, sy + 12, 8, 7)
                    )
                    pygame.draw.rect(
                        self.screen, (180, 220, 255), (sx + 12, sy + 13, 3, 3)
                    )
                elif tid == TREASURE_CHEST:
                    # Golden chest with lock
                    chest_body = (185, 130, 40)
                    chest_band = (230, 180, 60)
                    chest_dark = (120, 85, 25)
                    # Body
                    pygame.draw.rect(self.screen, chest_body, (sx + 4, sy + 14, 24, 14))
                    # Lid
                    pygame.draw.rect(self.screen, chest_body, (sx + 4, sy + 8, 24, 8))
                    pygame.draw.polygon(
                        self.screen,
                        chest_band,
                        [
                            (sx + 4, sy + 16),
                            (sx + 28, sy + 16),
                            (sx + 28, sy + 19),
                            (sx + 4, sy + 19),
                        ],
                    )
                    # Lock
                    pygame.draw.rect(self.screen, chest_dark, (sx + 13, sy + 17, 6, 5))
                    pygame.draw.ellipse(
                        self.screen, chest_dark, (sx + 13, sy + 14, 6, 6)
                    )
                    # Shimmer sparkle
                    sp = int(math.sin(ticks * 0.006) * 2) + 2
                    pygame.draw.line(
                        self.screen,
                        (255, 240, 130),
                        (sx + 8, sy + 4 + sp),
                        (sx + 8 + 3, sy + 4 + sp - 3),
                        1,
                    )
                    pygame.draw.line(
                        self.screen,
                        (255, 240, 130),
                        (sx + 8, sy + 4 + sp),
                        (sx + 8 - 3, sy + 4 + sp + 3),
                        1,
                    )
                elif tid in (CAVE_MOUNTAIN, CAVE_HILL):
                    # Draw cave entrance
                    # Darker base color already set by tileset color
                    # Add cave entrance graphics
                    cave_color = tile_color
                    # Draw a shadowy entrance
                    pygame.draw.rect(self.screen, cave_color, (sx + 4, sy + 8, 24, 20))
                    # Add entrance shadow
                    shadow = tuple(max(0, c - 30) for c in cave_color)
                    pygame.draw.polygon(
                        self.screen,
                        shadow,
                        [
                            (sx + 8, sy + 12),
                            (sx + 24, sy + 12),
                            (sx + 20, sy + 20),
                            (sx + 10, sy + 20),
                        ],
                    )
                    # Add some rock detail
                    rock_color = tuple(max(0, min(255, c + 20)) for c in cave_color)
                    pygame.draw.circle(self.screen, rock_color, (sx + 12, sy + 15), 2)
                    pygame.draw.circle(self.screen, rock_color, (sx + 20, sy + 14), 2)
                    pygame.draw.circle(self.screen, rock_color, (sx + 16, sy + 20), 2)
                elif tid == CAVE_EXIT:
                    # Draw cave exit - a glowing portal/ladder
                    # Pulsing glow effect
                    pulse = int(math.sin(pygame.time.get_ticks() * 0.004) * 20 + 40)
                    glow_color = (pulse + 40, pulse + 80, pulse + 40)
                    pygame.draw.rect(self.screen, glow_color, (sx + 4, sy + 2, 24, 28))
                    # Ladder rungs
                    rung_color = (120, 90, 50)
                    for ry in range(6, 28, 6):
                        pygame.draw.line(
                            self.screen,
                            rung_color,
                            (sx + 8, sy + ry),
                            (sx + 24, sy + ry),
                            2,
                        )
                    # Vertical rails
                    pygame.draw.line(
                        self.screen, rung_color, (sx + 8, sy + 4), (sx + 8, sy + 28), 2
                    )
                    pygame.draw.line(
                        self.screen,
                        rung_color,
                        (sx + 24, sy + 4),
                        (sx + 24, sy + 28),
                        2,
                    )

        # Draw effects and objects for this viewport
        for par in self.particles:
            par.draw(self.screen, cam_x - screen_x, cam_y - screen_y)
        for f in self.floats:
            f.draw(self.screen, self.font, cam_x - screen_x, cam_y - screen_y)

        # Workers, pets, and overland enemies only on overland map
        if player.current_map == "overland":
            for w in self.workers:
                w.draw(self.screen, cam_x - screen_x, cam_y - screen_y)

            for pet in self.pets:
                pet.draw(self.screen, cam_x - screen_x, cam_y - screen_y, ticks)
            for enemy in self.enemies:
                enemy.draw(self.screen, cam_x - screen_x, cam_y - screen_y)
        else:
            # Draw enemies belonging to the cave the player is currently in
            cave_map = self.get_player_current_map(player)
            if cave_map is not None:
                for enemy in cave_map.enemies:
                    enemy.draw(self.screen, cam_x - screen_x, cam_y - screen_y)

        # Draw projectiles on this map only
        current_map_key = player.current_map
        for proj in self.projectiles:
            if proj.map_key == current_map_key:
                proj.draw(self.screen, cam_x - screen_x, cam_y - screen_y)

        # Draw players that share this map
        for p in (self.player1, self.player2):
            if p.current_map == current_map_key:
                p.draw(self.screen, cam_x - screen_x, cam_y - screen_y)

        self._draw_player_ui(player, screen_x, screen_y, view_w, view_h)
        if player.is_dead:
            self._draw_death_challenge(player, screen_x, screen_y, view_w, view_h)

        # Sector-wipe flash overlay (drawn last so it appears on top)
        wipe_state = self.sector_wipe.get(player.player_id)
        if wipe_state:
            self._draw_sector_wipe_viewport(
                screen_x, screen_y, view_w, view_h, wipe_state["progress"]
            )

        self.screen.set_clip(None)

    def _draw_player_ui(self, player, screen_x, screen_y, view_w, view_h):
        """Draw UI for a single player's viewport."""
        font_small = self.font_ui_sm
        font_tiny = self.font_ui_xs

        # Top HUD Panel (Stats & Inventory)
        top_panel_h = 240
        top_panel_w = 240
        top_panel_surf = pygame.Surface((top_panel_w, top_panel_h), pygame.SRCALPHA)
        top_panel_surf.fill((20, 20, 30, 200))  # Translucent dark blue-gray
        self.screen.blit(top_panel_surf, (screen_x + 8, screen_y + 8))

        # Top panel border
        pygame.draw.rect(
            self.screen,
            (150, 150, 150),
            (screen_x + 8, screen_y + 8, top_panel_w, top_panel_h),
            2,
        )

        # Health bar
        bar_w, bar_h = 220, 18
        hp_ratio = max(0, player.hp / player.max_hp)
        pygame.draw.rect(
            self.screen, (50, 50, 50), (screen_x + 18, screen_y + 18, bar_w, bar_h)
        )
        pygame.draw.rect(
            self.screen,
            (0, 255, 0),
            (screen_x + 18, screen_y + 18, bar_w * hp_ratio, bar_h),
        )
        hp_text = font_small.render(
            f"HP: {player.hp:.0f}/{player.max_hp}", True, (255, 255, 255)
        )
        self.screen.blit(hp_text, (screen_x + 25, screen_y + 20))

        # Level & XP
        level_text = font_small.render(f"Level {player.level}", True, (255, 255, 0))
        self.screen.blit(level_text, (screen_x + 18, screen_y + 45))
        xp_bar_w = 220
        xp_ratio = player.xp / player.xp_next if player.xp_next > 0 else 0
        pygame.draw.rect(
            self.screen, (50, 50, 0), (screen_x + 18, screen_y + 70, xp_bar_w, 10)
        )
        pygame.draw.rect(
            self.screen,
            (255, 255, 0),
            (screen_x + 18, screen_y + 70, xp_bar_w * xp_ratio, 10),
        )
        xp_text = font_tiny.render(
            f"XP: {player.xp}/{player.xp_next}", True, (255, 255, 0)
        )
        self.screen.blit(xp_text, (screen_x + 18, screen_y + 82))

        # Inventory (2-column layout)
        inv_y = screen_y + 105
        inv_text = font_small.render("Inventory:", True, (200, 200, 200))
        self.screen.blit(inv_text, (screen_x + 18, inv_y))

        items = list(player.inventory.items())
        items_per_column = 2

        for idx, (res, qty) in enumerate(items):
            col = idx // items_per_column
            row = idx % items_per_column
            x_offset = col * 110  # Column width
            y_offset = inv_y + 22 + row * 18
            res_text = font_tiny.render(f"{res}: {qty}", True, (180, 180, 180))
            self.screen.blit(res_text, (screen_x + 18 + x_offset, y_offset))

        # Weapon
        wpn = WEAPONS[player.weapon_level]
        wpn_text = font_tiny.render(f"Weapon: {wpn['name']}", True, (255, 150, 100))
        self.screen.blit(wpn_text, (screen_x + 18, inv_y + 82))

        # Upgrades panel
        upg_panel_y = screen_y + 8 + 240 + 6
        upg_panel_w = 240

        def _cost_str(cost_dict, inventory):
            """Format a cost dict as 'Item: need/have' entries."""
            parts = []
            for item, needed in cost_dict.items():
                have = inventory.get(item, 0)
                color_flag = have >= needed
                parts.append((f"{item}: {have}/{needed}", color_flag))
            return parts

        upg_lines = []  # list of (label, [(text, met), ...]) or (label, None) for MAX

        # Pickaxe upgrade
        pick_name = PICKAXES[player.pick_level]["name"]
        if player.pick_level < len(UPGRADE_COSTS):
            next_pick = PICKAXES[player.pick_level + 1]["name"]
            pick_cost = _cost_str(UPGRADE_COSTS[player.pick_level], player.inventory)
            upg_lines.append((f"Pick ({pick_name}→{next_pick}):", pick_cost))
        else:
            upg_lines.append((f"Pick ({pick_name}):", None))

        # Weapon unlock
        wpn_name = WEAPONS[player.weapon_level]["name"]
        if player.weapon_level < len(WEAPON_UNLOCK_COSTS):
            next_wpn = WEAPONS[player.weapon_level + 1]["name"]
            wpn_cost = _cost_str(
                WEAPON_UNLOCK_COSTS[player.weapon_level], player.inventory
            )
            upg_lines.append((f"Wpn ({wpn_name}→{next_wpn}):", wpn_cost))
        else:
            upg_lines.append((f"Wpn ({wpn_name}):", None))

        # House
        house_cost = _cost_str({"Dirt": HOUSE_BUILD_COST}, player.inventory)
        build_key = pygame.key.name(player.controls.build_house_key).upper()
        upg_lines.append((f"House ({build_key}):", house_cost))

        # Pier
        pier_key = pygame.key.name(player.controls.build_pier_key).upper()
        pier_cost = _cost_str({"Wood": PIER_BUILD_COST}, player.inventory)
        upg_lines.append((f"Pier ({pier_key}):", pier_cost))

        # Boat
        int_key = pygame.key.name(player.controls.interact_key).upper()
        boat_cost = _cost_str({"Wood": BOAT_BUILD_COST, "Sail": 1}, player.inventory)
        upg_lines.append((f"Boat ({int_key} at pier):", boat_cost))

        # Calculate panel height: header + 2 rows per entry (label + costs)
        upg_panel_h = 14 + len(upg_lines) * 30
        upg_surf = pygame.Surface((upg_panel_w, upg_panel_h), pygame.SRCALPHA)
        upg_surf.fill((20, 20, 30, 200))
        self.screen.blit(upg_surf, (screen_x + 8, upg_panel_y))
        pygame.draw.rect(
            self.screen,
            (150, 150, 150),
            (screen_x + 8, upg_panel_y, upg_panel_w, upg_panel_h),
            2,
        )

        upg_header = font_small.render("Upgrades:", True, (200, 200, 200))
        self.screen.blit(upg_header, (screen_x + 18, upg_panel_y + 4))

        entry_y = upg_panel_y + 20
        for label, cost_parts in upg_lines:
            label_surf = font_tiny.render(label, True, (200, 200, 200))
            self.screen.blit(label_surf, (screen_x + 18, entry_y))
            if cost_parts is None:
                max_surf = font_tiny.render("MAX", True, (100, 255, 100))
                self.screen.blit(max_surf, (screen_x + 18, entry_y + 13))
            else:
                cx = screen_x + 18
                for text, met in cost_parts:
                    col = (100, 255, 100) if met else (255, 100, 100)
                    ts = font_tiny.render(text, True, col)
                    self.screen.blit(ts, (cx, entry_y + 13))
                    cx += ts.get_width() + 6
            entry_y += 30

        # Auto toggle status
        auto_status_y = inv_y + 100
        auto_mine_key = pygame.key.name(player.controls.toggle_auto_mine_key).upper()
        auto_mine_status = (
            f"Auto Mine ({auto_mine_key}): {'ON' if player.auto_mine else 'OFF'}"
        )
        auto_mine_color = (100, 255, 100) if player.auto_mine else (150, 150, 150)
        auto_mine_text = font_tiny.render(auto_mine_status, True, auto_mine_color)
        self.screen.blit(auto_mine_text, (screen_x + 18, auto_status_y))

        auto_fire_key = pygame.key.name(player.controls.toggle_auto_fire_key).upper()
        auto_fire_status = (
            f"Auto Fire ({auto_fire_key}): {'ON' if player.auto_fire else 'OFF'}"
        )
        auto_fire_color = (100, 255, 100) if player.auto_fire else (150, 150, 150)
        auto_fire_text = font_tiny.render(auto_fire_status, True, auto_fire_color)
        self.screen.blit(auto_fire_text, (screen_x + 18, auto_status_y + 16))

        # Bottom HUD Panel (Controls)
        ctrl_y_start = screen_y + view_h - 100
        bottom_panel_h = 92
        bottom_panel_w = 240
        bottom_panel_surf = pygame.Surface(
            (bottom_panel_w, bottom_panel_h), pygame.SRCALPHA
        )
        bottom_panel_surf.fill((20, 20, 30, 200))  # Translucent dark blue-gray
        self.screen.blit(bottom_panel_surf, (screen_x + 8, ctrl_y_start))

        # Bottom panel border
        pygame.draw.rect(
            self.screen,
            (150, 150, 150),
            (screen_x + 8, ctrl_y_start, bottom_panel_w, bottom_panel_h),
            2,
        )

        # Control scheme (2-column layout)
        controls = player.controls.get_controls_list()

        ctrl_y = ctrl_y_start + 8
        ctrl_header = font_small.render("Controls:", True, (200, 200, 200))
        self.screen.blit(ctrl_header, (screen_x + 18, ctrl_y))

        controls_per_column = 3

        for idx, ctrl_text in enumerate(controls):
            col = idx // controls_per_column
            row = idx % controls_per_column
            x_offset = col * 110  # Column width
            y_offset = ctrl_y + 24 + row * 15
            ctrl_surf = font_tiny.render(ctrl_text, True, (180, 180, 180))
            self.screen.blit(ctrl_surf, (screen_x + 18 + x_offset, y_offset))

    def _draw_death_challenge(self, player, screen_x, screen_y, view_w, view_h):
        """Draw the death/respawn math challenge overlay for a player's viewport."""
        challenge = self.death_challenges.get(player.player_id)
        if challenge is None:
            return

        # Semi-transparent dark overlay over the whole viewport
        overlay = pygame.Surface((view_w, view_h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (screen_x, screen_y))

        font_big = self.font_dc_big
        font_med = self.font_dc_med
        font_small = self.font_dc_sm

        cx = screen_x + view_w // 2
        cy = screen_y + view_h // 2

        panel_w, panel_h = 360, 210
        panel_x = cx - panel_w // 2
        panel_y = cy - panel_h // 2

        panel_surf = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel_surf.fill((20, 10, 10, 235))
        self.screen.blit(panel_surf, (panel_x, panel_y))
        pygame.draw.rect(
            self.screen, (200, 50, 50), (panel_x, panel_y, panel_w, panel_h), 3
        )

        # "YOU DIED" header
        died_surf = font_big.render("YOU DIED", True, (255, 50, 50))
        self.screen.blit(died_surf, (cx - died_surf.get_width() // 2, panel_y + 14))

        # Instruction
        desc_surf = font_small.render(
            "Solve to respawn at full health:", True, (200, 200, 200)
        )
        self.screen.blit(desc_surf, (cx - desc_surf.get_width() // 2, panel_y + 62))

        # Math question
        q_surf = font_med.render(challenge["question"], True, (255, 255, 100))
        self.screen.blit(q_surf, (cx - q_surf.get_width() // 2, panel_y + 88))

        # Answer input field
        input_display = challenge["input"] if challenge["input"] else "_"
        input_color = (255, 80, 80) if challenge.get("wrong") else (100, 255, 100)
        input_surf = font_med.render(input_display, True, input_color)
        self.screen.blit(input_surf, (cx - input_surf.get_width() // 2, panel_y + 130))

        # Hint / wrong-answer message
        if challenge.get("wrong"):
            hint_surf = font_small.render(
                "Wrong answer — try again!", True, (255, 80, 80)
            )
        else:
            hint_surf = font_small.render(
                "Type your answer and press Enter", True, (140, 140, 140)
            )
        self.screen.blit(hint_surf, (cx - hint_surf.get_width() // 2, panel_y + 175))
