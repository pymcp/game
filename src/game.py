"""Main game class and orchestration."""

import pygame
import math
import random
from src.config import (
    SCREEN_W,
    SCREEN_H,
    VIEWPORT_W,
    VIEWPORT_H,
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
)
from src.data import TILE_INFO, WEAPONS
from src.world import generate_world, spawn_enemies, try_spend, has_adjacent_house
from src.world.map import GameMap
from src.world.generation import generate_cave_map
from src.entities import Player, Projectile, Worker, Pet
from src.entities.player import CONTROL_SCHEME_PLAYER1, CONTROL_SCHEME_PLAYER2
from src.effects import Particle, FloatingText
from src.ui import draw_hud, draw_tooltip


class Game:
    """Main game class managing all game state and the main loop (2 players)."""

    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H), pygame.RESIZABLE)
        pygame.display.set_caption("Mining Game - 2 Players (F11 for fullscreen)")
        self.clock = pygame.time.Clock()
        self.is_fullscreen = False
        self.font = pygame.font.SysFont("monospace", 16)
        self.big_font = pygame.font.SysFont("monospace", 22, bold=True)

        # Dynamic viewport dimensions
        self.viewport_w = VIEWPORT_W
        self.viewport_h = VIEWPORT_H

        # Map system - store all maps by key
        # "overland" is the main map, caves are keyed by (col, row)
        world_data = generate_world()
        self.maps = {
            "overland": GameMap(world_data, tileset="overland")
        }
        self.current_map_key = "overland"  # Track which map is being viewed (for rendering)

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

        # Store cave coordinates where players are for easy access
        self.cave_coords_to_map = {}  # Maps (col, row) to cave GameMap

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
        # Player 1 controls
        elif key == self.player1.controls.upgrade_pick_key:
            self.player1.try_upgrade_pick()
        elif key == self.player1.controls.upgrade_weapon_key:
            self.player1.try_upgrade_weapon()
        elif key == self.player1.controls.build_house_key:
            self._try_build_house(self.player1)
        elif key == self.player1.controls.toggle_auto_mine_key:
            self.player1.toggle_auto_mine()
        elif key == self.player1.controls.toggle_auto_fire_key:
            self.player1.toggle_auto_fire()
        # Player 2 controls
        elif key == self.player2.controls.upgrade_pick_key:
            self.player2.try_upgrade_pick()
        elif key == self.player2.controls.upgrade_weapon_key:
            self.player2.try_upgrade_weapon()
        elif key == self.player2.controls.build_house_key:
            self._try_build_house(self.player2)
        elif key == self.player2.controls.toggle_auto_mine_key:
            self.player2.toggle_auto_mine()
        elif key == self.player2.controls.toggle_auto_fire_key:
            self.player2.toggle_auto_fire()

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
            or player.inventory.get("Dirt", 0) < 20
        ):
            return
        if not try_spend(player.inventory, {"Dirt": 20}):
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

        import random

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

    # -- helper methods for cave system --------------------------------

    def get_player_current_map(self, player):
        """Get the GameMap object that the player is currently on."""
        map_key = player.current_map
        if map_key == "overland":
            return self.maps["overland"]
        elif isinstance(map_key, tuple):  # Cave coordinates (cave_col, cave_row)
            return self.maps.get(map_key)
        return None

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
                # Generate new cave map
                self.maps[cave_key] = generate_cave_map(tile_col, tile_row)

            cave_map = self.maps[cave_key]
            # Teleport player to cave spawn point (away from exit)
            player.x = cave_map.spawn_col * TILE + TILE // 2
            player.y = cave_map.spawn_row * TILE + TILE // 2
            player.current_map = cave_key

            # Update camera to follow player into cave
            if player.player_id == 1:
                self.cam1_x = player.x - self.viewport_w // 2
                self.cam1_y = player.y - self.viewport_h // 2
            else:
                self.cam2_x = player.x - self.viewport_w // 2
                self.cam2_y = player.y - self.viewport_h // 2

            # Floating text notification
            self.floats.append(
                FloatingText(
                    player.x, player.y - 30, "Entered cave!", (100, 150, 255)
                )
            )

    def check_cave_exits(self, player, current_map):
        """Check if player stepped on a cave exit and transition back to overland."""
        if player.current_map == "overland":
            return  # Already on overland

        if current_map == self.maps["overland"]:
            return  # Not on a cave map

        # Check if player is standing on a CAVE_EXIT tile
        if not hasattr(current_map, 'entrance_col'):
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
            for dr, dc in [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)]:
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

            # Update camera to follow player out of cave
            if player.player_id == 1:
                self.cam1_x = player.x - self.viewport_w // 2
                self.cam1_y = player.y - self.viewport_h // 2
            else:
                self.cam2_x = player.x - self.viewport_w // 2
                self.cam2_y = player.y - self.viewport_h // 2

            self.floats.append(
                FloatingText(
                    player.x, player.y - 30, "Exited cave!", (100, 255, 150)
                )
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

        # Check for cave transitions
        self.check_cave_transitions(self.player1, map1)
        self.check_cave_transitions(self.player2, map2)

        # Update maps after potential transitions
        map1 = self.get_player_current_map(self.player1)
        map2 = self.get_player_current_map(self.player2)

        # Check for cave exits
        self.check_cave_exits(self.player1, map1)
        self.check_cave_exits(self.player2, map2)

        # Update maps again after potential exits
        map1 = self.get_player_current_map(self.player1)
        map2 = self.get_player_current_map(self.player2)

        # Player 1 movement & mining
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

        # Player 2 movement & mining
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
        for enemy in self.enemies:
            # Enemies only attack players on overland map
            player1_on_overland = self.player1.current_map == "overland"
            player2_on_overland = self.player2.current_map == "overland"

            if not (player1_on_overland or player2_on_overland):
                continue  # No players to attack on overland

            # Enemies attack whichever player is closer (if on overland)
            if player1_on_overland and player2_on_overland:
                dist1 = math.hypot(self.player1.x - enemy.x, self.player1.y - enemy.y)
                dist2 = math.hypot(self.player2.x - enemy.x, self.player2.y - enemy.y)
                target_x, target_y = (
                    (self.player1.x, self.player1.y)
                    if dist1 < dist2
                    else (self.player2.x, self.player2.y)
                )
                target_player = self.player1 if dist1 < dist2 else self.player2
            elif player1_on_overland:
                target_x, target_y = self.player1.x, self.player1.y
                target_player = self.player1
            else:
                target_x, target_y = self.player2.x, self.player2.y
                target_player = self.player2

            # Use average camera for enemy update (they share the world)
            avg_cam_x = (self.cam1_x + self.cam2_x) / 2
            avg_cam_y = (self.cam1_y + self.cam2_y) / 2
            enemy.update(
                dt, target_x, target_y, avg_cam_x, avg_cam_y, overland_map.world, self.particles
            )

            dmg = enemy.try_attack(target_x, target_y)
            if dmg > 0:
                target_player.take_damage(dmg, self.particles, self.floats)

    def _update_combat(self, keys, mouse_buttons, dt):
        """Handle weapon firing for both players."""
        # Player 1 firing
        if self.player1.weapon_cooldown > 0:
            self.player1.weapon_cooldown -= dt
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
                )
            )
            self.player1.weapon_cooldown = wpn["cooldown"]

        # Player 2 firing
        if self.player2.weapon_cooldown > 0:
            self.player2.weapon_cooldown -= dt
        fire_input_p2 = keys[self.player2.controls.fire_key] or self.player2.auto_fire
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
                )
            )
            self.player2.weapon_cooldown = wpn["cooldown"]

    def _update_projectiles(self, dt):
        """Update all projectiles and check for hits."""
        for proj in self.projectiles:
            proj.update(dt)
            if proj.alive:
                proj.check_hits(self.enemies, self.particles, self.floats)
            # Award XP only to the player that fired this projectile
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
        border_accent = (180, 160, 140)  # Stone accent

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
                                    and current_map.get_tile(check_r, check_c + 1) == MOUNTAIN
                                    and current_map.get_tile(check_r + 1, check_c) == MOUNTAIN
                                    and current_map.get_tile(check_r + 1, check_c + 1) == MOUNTAIN
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
                    pygame.draw.rect(
                        self.screen, (180, 120, 60), (sx + 4, sy + 12, 24, 18)
                    )
                    pygame.draw.polygon(
                        self.screen,
                        (160, 40, 40),
                        [(sx + 2, sy + 12), (sx + 16, sy + 2), (sx + 30, sy + 12)],
                    )
                    pygame.draw.rect(
                        self.screen, (100, 60, 30), (sx + 12, sy + 19, 8, 11)
                    )
                    pygame.draw.rect(
                        self.screen, (180, 220, 255), (sx + 7, sy + 15, 5, 5)
                    )
                    pygame.draw.rect(
                        self.screen, (80, 60, 40), (sx + 7, sy + 15, 5, 5), 1
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
                        [(sx + 8, sy + 12), (sx + 24, sy + 12), (sx + 20, sy + 20), (sx + 10, sy + 20)],
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
                        pygame.draw.line(self.screen, rung_color, (sx + 8, sy + ry), (sx + 24, sy + ry), 2)
                    # Vertical rails
                    pygame.draw.line(self.screen, rung_color, (sx + 8, sy + 4), (sx + 8, sy + 28), 2)
                    pygame.draw.line(self.screen, rung_color, (sx + 24, sy + 4), (sx + 24, sy + 28), 2)

        # Draw effects and objects for this viewport
        for par in self.particles:
            par.draw(self.screen, cam_x - screen_x, cam_y - screen_y)
        for f in self.floats:
            f.draw(self.screen, self.font, cam_x - screen_x, cam_y - screen_y)

        # Workers, pets, and enemies only exist on overland map
        if player.current_map == "overland":
            for w in self.workers:
                w.draw(self.screen, cam_x - screen_x, cam_y - screen_y)

            ticks = pygame.time.get_ticks()
            for pet in self.pets:
                pet.draw(self.screen, cam_x - screen_x, cam_y - screen_y, ticks)
            for enemy in self.enemies:
                enemy.draw(self.screen, cam_x - screen_x, cam_y - screen_y)

        for proj in self.projectiles:
            proj.draw(self.screen, cam_x - screen_x, cam_y - screen_y)

        # Draw both players in this viewport (visible to both players)
        self.player1.draw(self.screen, cam_x - screen_x, cam_y - screen_y)
        self.player2.draw(self.screen, cam_x - screen_x, cam_y - screen_y)

        self._draw_player_ui(player, screen_x, screen_y, view_w, view_h)
        self.screen.set_clip(None)

    def _draw_player_ui(self, player, screen_x, screen_y, view_w, view_h):
        """Draw UI for a single player's viewport."""
        font_small = pygame.font.Font(None, 22)
        font_tiny = pygame.font.Font(None, 16)

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
