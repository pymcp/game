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
)
from src.data import TILE_INFO, WEAPONS
from src.world import generate_world, spawn_enemies, try_spend, has_adjacent_house
from src.entities import Player, Projectile, Worker, Pet
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

        # World
        self.world = generate_world()
        self.tile_hp = [
            [TILE_INFO[self.world[r][c]]["hp"] for c in range(WORLD_COLS)]
            for r in range(WORLD_ROWS)
        ]

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
                            if self.world[row][col] == GRASS:
                                return col * TILE + TILE // 2, row * TILE + TILE // 2
            # Fallback to center if no grass found
            return (WORLD_COLS // 2) * TILE + TILE // 2, (
                WORLD_ROWS // 2
            ) * TILE + TILE // 2

        start_x1, start_y1 = find_grass_spawn(-TILE)
        start_x2, start_y2 = find_grass_spawn(TILE)

        self.player1 = Player(start_x1, start_y1, player_id=1)
        self.player2 = Player(start_x2, start_y2, player_id=2)

        # Cameras (one for each player's viewport)
        self.cam1_x = self.player1.x - self.viewport_w // 2
        self.cam1_y = self.player1.y - self.viewport_h // 2
        self.cam2_x = self.player2.x - self.viewport_w // 2
        self.cam2_y = self.player2.y - self.viewport_h // 2

        # Entities (shared between players)
        self.workers = []
        self.pets = []
        self.enemies = spawn_enemies(self.world)
        self.projectiles = []

        # Effects (shared)
        self.particles = []
        self.floats = []

        self.running = True

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
        # Player 1 controls (WASD area)
        elif key == pygame.K_u:
            self.player1.try_upgrade_pick()
        elif key == pygame.K_n:
            self.player1.try_upgrade_weapon()
        elif key == pygame.K_b:
            self._try_build_house(self.player1)
        # Player 2 controls (Arrow keys area)
        elif key == pygame.K_i:
            self.player2.try_upgrade_pick()
        elif key == pygame.K_o:
            self.player2.try_upgrade_weapon()
        elif key == pygame.K_v:
            self._try_build_house(self.player2)

    def _try_build_house(self, player):
        """Attempt to build a house at player position."""
        build_col = int(player.x) // TILE
        build_row = int(player.y) // TILE
        if not (0 <= build_col < WORLD_COLS and 0 <= build_row < WORLD_ROWS):
            return
        if (
            self.world[build_row][build_col] != GRASS
            or player.inventory.get("Dirt", 0) < 20
        ):
            return
        if not try_spend(player.inventory, {"Dirt": 20}):
            return

        self.world[build_row][build_col] = HOUSE
        self.tile_hp[build_row][build_col] = 0
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
            self.workers.append(Worker(tile_cx, tile_cy))
            self.floats.append(
                FloatingText(tile_cx, tile_cy - 20, "Worker spawned!", (100, 220, 255))
            )

        if has_adjacent_house(self.world, build_col, build_row):
            self.pets.append(Pet(tile_cx, tile_cy, kind="cat"))
            self.floats.append(
                FloatingText(tile_cx, tile_cy - 36, "Cat appeared!", (255, 165, 0))
            )

    # -- update ------------------------------------------------------------

    def update(self, dt):
        """Update game state (both players, shared world)."""
        keys = pygame.key.get_pressed()
        mouse_buttons = pygame.mouse.get_pressed()

        # Player 1 movement & mining
        self.player1.update_movement(keys, dt, self.world)
        self.player1.update_mining(
            keys,
            mouse_buttons,
            dt,
            self.world,
            self.tile_hp,
            self.cam1_x,
            self.cam1_y,
            self.particles,
            self.floats,
        )
        if self.player1.hurt_timer > 0:
            self.player1.hurt_timer -= dt

        # Player 2 movement & mining
        self.player2.update_movement(keys, dt, self.world)
        self.player2.update_mining(
            keys,
            mouse_buttons,
            dt,
            self.world,
            self.tile_hp,
            self.cam2_x,
            self.cam2_y,
            self.particles,
            self.floats,
        )
        if self.player2.hurt_timer > 0:
            self.player2.hurt_timer -= dt

        # Workers (distribute resources randomly to either player)
        for w in self.workers:
            # Randomly choose which player gets the resources
            target_player = random.choice([self.player1, self.player2])
            w.update(
                dt,
                self.world,
                self.tile_hp,
                target_player.inventory,
                self.particles,
                self.floats,
            )

        # Pets
        for pet in self.pets:
            # Pets follow the closest player
            dist1 = math.hypot(pet.x - self.player1.x, pet.y - self.player1.y)
            dist2 = math.hypot(pet.x - self.player2.x, pet.y - self.player2.y)
            target = self.player1 if dist1 < dist2 else self.player2
            pet.update(dt, target.x, target.y, self.world)

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

        # Clamp cameras to world bounds
        world_pixel_w = WORLD_COLS * TILE
        world_pixel_h = WORLD_ROWS * TILE
        self.cam1_x = max(0, min(self.cam1_x, world_pixel_w - self.viewport_w))
        self.cam1_y = max(0, min(self.cam1_y, world_pixel_h - self.viewport_h))
        self.cam2_x = max(0, min(self.cam2_x, world_pixel_w - self.viewport_w))
        self.cam2_y = max(0, min(self.cam2_y, world_pixel_h - self.viewport_h))

        # Effects
        for par in self.particles:
            par.update()
        self.particles = [par for par in self.particles if par.life > 0]
        for f in self.floats:
            f.update()
        self.floats = [f for f in self.floats if f.life > 0]

    def _update_enemies(self, dt):
        """Update all enemies and check for attacks on both players."""
        for enemy in self.enemies:
            # Enemies attack whichever player is closer
            dist1 = math.hypot(self.player1.x - enemy.x, self.player1.y - enemy.y)
            dist2 = math.hypot(self.player2.x - enemy.x, self.player2.y - enemy.y)
            target_x, target_y = (
                (self.player1.x, self.player1.y)
                if dist1 < dist2
                else (self.player2.x, self.player2.y)
            )
            target_player = self.player1 if dist1 < dist2 else self.player2

            # Use average camera for enemy update (they share the world)
            avg_cam_x = (self.cam1_x + self.cam2_x) / 2
            avg_cam_y = (self.cam1_y + self.cam2_y) / 2
            enemy.update(
                dt, target_x, target_y, avg_cam_x, avg_cam_y, self.world, self.particles
            )

            dmg = enemy.try_attack(target_x, target_y)
            if dmg > 0:
                target_player.take_damage(dmg, self.particles, self.floats)

    def _update_combat(self, keys, mouse_buttons, dt):
        """Handle weapon firing for both players."""
        # Player 1: F or Right mouse button
        if self.player1.weapon_cooldown > 0:
            self.player1.weapon_cooldown -= dt
        fire_input_p1 = keys[pygame.K_f] or mouse_buttons[2]
        if fire_input_p1 and self.player1.weapon_cooldown <= 0:
            wpn = WEAPONS[self.player1.weapon_level]
            self.projectiles.append(
                Projectile(
                    self.player1.x,
                    self.player1.y,
                    self.player1.facing_dx,
                    self.player1.facing_dy,
                    wpn,
                )
            )
            self.player1.weapon_cooldown = wpn["cooldown"]

        # Player 2: KP_Enter (numpad enter)
        if self.player2.weapon_cooldown > 0:
            self.player2.weapon_cooldown -= dt
        fire_input_p2 = keys[pygame.K_KP_ENTER]
        if fire_input_p2 and self.player2.weapon_cooldown <= 0:
            wpn = WEAPONS[self.player2.weapon_level]
            self.projectiles.append(
                Projectile(
                    self.player2.x,
                    self.player2.y,
                    self.player2.facing_dx,
                    self.player2.facing_dy,
                    wpn,
                )
            )
            self.player2.weapon_cooldown = wpn["cooldown"]

    def _update_projectiles(self, dt):
        """Update all projectiles and check for hits."""
        for proj in self.projectiles:
            proj.update(dt)
            if proj.alive:
                proj.check_hits(self.enemies, self.particles, self.floats)
            # Award XP to the player that fired it (track which one based on position)
            # For now, split XP between both players
            xp_each = proj.xp_earned // 2
            self.player1.xp += xp_each
            self.player2.xp += xp_each
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
        # Draw border fill for out-of-bounds areas
        world_pixel_w = WORLD_COLS * TILE
        world_pixel_h = WORLD_ROWS * TILE

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
        end_col = min(WORLD_COLS, int(cam_x + view_w) // TILE + 2)
        start_row = max(0, int(cam_y) // TILE)
        end_row = min(WORLD_ROWS, int(cam_y + view_h) // TILE + 2)

        for r in range(start_row, end_row):
            for c in range(start_col, end_col):
                tid = self.world[r][c]
                info = TILE_INFO[tid]
                sx = c * TILE - int(cam_x) + screen_x
                sy = r * TILE - int(cam_y) + screen_y
                pygame.draw.rect(self.screen, info["color"], (sx, sy, TILE, TILE))

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
                        c + 1 < WORLD_COLS and r + 1 < WORLD_ROWS and
                        self.world[r][c] == MOUNTAIN and
                        self.world[r][c + 1] == MOUNTAIN and
                        self.world[r + 1][c] == MOUNTAIN and
                        self.world[r + 1][c + 1] == MOUNTAIN
                    )
                    
                    # Check if current tile is part of a larger 2x2 block
                    is_part_of_2x2 = False
                    if is_2x2_tl:
                        is_part_of_2x2 = True
                    else:
                        # Check if we're part of a 2x2 block from other positions
                        for dc, dr in [(-1, 0), (0, -1), (-1, -1)]:
                            check_c, check_r = c + dc, r + dr
                            if check_c >= 0 and check_r >= 0 and check_c + 1 < WORLD_COLS and check_r + 1 < WORLD_ROWS:
                                if (self.world[check_r][check_c] == MOUNTAIN and
                                    self.world[check_r][check_c + 1] == MOUNTAIN and
                                    self.world[check_r + 1][check_c] == MOUNTAIN and
                                    self.world[check_r + 1][check_c + 1] == MOUNTAIN):
                                    is_part_of_2x2 = True
                                    break
                    
                    if is_2x2_tl:
                        # Draw multiple ridge-like peaks for 2x2 mountain groups
                        base_y = sy + TILE * 2
                        block_left_x = sx
                        block_right_x = sx + TILE * 2
                        
                        # Define peaks (x_offset from block_left, height)
                        peaks = [
                            (12, sy - TILE // 3),      # Left-center peak
                            (24, sy - TILE // 5),      # Center-right peak  
                            (36, sy - TILE // 3.5),    # Right peak
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

        # Draw effects and objects for this viewport
        for par in self.particles:
            par.draw(self.screen, cam_x - screen_x, cam_y - screen_y)
        for f in self.floats:
            f.draw(self.screen, self.font, cam_x - screen_x, cam_y - screen_y)
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
        top_panel_h = 170
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

        # Bottom HUD Panel (Controls)
        ctrl_y_start = screen_y + view_h - 100
        bottom_panel_h = 92
        bottom_panel_w = 240
        bottom_panel_surf = pygame.Surface((bottom_panel_w, bottom_panel_h), pygame.SRCALPHA)
        bottom_panel_surf.fill((20, 20, 30, 200))  # Translucent dark blue-gray
        self.screen.blit(bottom_panel_surf, (screen_x + 8, ctrl_y_start))
        
        # Bottom panel border
        pygame.draw.rect(
            self.screen,
            (150, 150, 150),
            (screen_x + 8, ctrl_y_start, bottom_panel_w, bottom_panel_h),
            2,
        )

        # Control scheme
        if player == self.player1:
            controls = [
                "WASD: Move",
                "U: Upgrade Pickaxe",
                "N: Upgrade Weapon",
                "B: Build House",
            ]
        else:
            controls = [
                "Arrows: Move",
                "I: Upgrade Pickaxe",
                "O: Upgrade Weapon",
                "V: Build House",
            ]
        
        ctrl_y = ctrl_y_start + 8
        ctrl_header = font_small.render("Controls:", True, (200, 200, 200))
        self.screen.blit(ctrl_header, (screen_x + 18, ctrl_y))
        
        for idx, ctrl_text in enumerate(controls):
            ctrl_surf = font_tiny.render(ctrl_text, True, (180, 180, 180))
            self.screen.blit(ctrl_surf, (screen_x + 18, ctrl_y + 24 + idx * 15))
