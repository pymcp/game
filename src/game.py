"""Main game class and orchestration."""
import pygame
import math
from src.config import (
    SCREEN_W, SCREEN_H, TILE, FPS, BG, WORLD_COLS, WORLD_ROWS,
    GRASS, DIRT, MOUNTAIN, TREE, WATER, HOUSE, IRON_ORE, GOLD_ORE, DIAMOND_ORE
)
from src.data import TILE_INFO, WEAPONS
from src.world import generate_world, spawn_enemies, try_spend, has_adjacent_house
from src.entities import Player, Projectile, Worker, Pet
from src.effects import Particle, FloatingText
from src.ui import draw_hud, draw_tooltip


class Game:
    """Main game class managing all game state and the main loop."""

    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        pygame.display.set_caption("Mining Game")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("monospace", 16)
        self.big_font = pygame.font.SysFont("monospace", 22, bold=True)

        # World
        self.world = generate_world()
        self.tile_hp = [
            [TILE_INFO[self.world[r][c]]["hp"] for c in range(WORLD_COLS)]
            for r in range(WORLD_ROWS)
        ]

        # Player
        start_x = (WORLD_COLS // 2) * TILE + TILE // 2
        start_y = (WORLD_ROWS // 2) * TILE + TILE // 2
        self.player = Player(start_x, start_y)

        # Camera
        self.cam_x = self.player.x - SCREEN_W // 2
        self.cam_y = self.player.y - SCREEN_H // 2

        # Entities
        self.workers = []
        self.pets = []
        self.enemies = spawn_enemies(self.world)
        self.projectiles = []

        # Effects
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

    def _handle_keydown(self, key):
        """Handle key press."""
        p = self.player
        if key == pygame.K_ESCAPE:
            self.running = False
        elif key == pygame.K_u:
            p.try_upgrade_pick()
        elif key == pygame.K_n:
            p.try_upgrade_weapon()
        elif key == pygame.K_b:
            self._try_build_house()

    def _try_build_house(self):
        """Attempt to build a house at player position."""
        p = self.player
        build_col = int(p.x) // TILE
        build_row = int(p.y) // TILE
        if not (0 <= build_col < WORLD_COLS and 0 <= build_row < WORLD_ROWS):
            return
        if self.world[build_row][build_col] != GRASS or p.inventory.get("Dirt", 0) < 20:
            return
        if not try_spend(p.inventory, {"Dirt": 20}):
            return

        self.world[build_row][build_col] = HOUSE
        self.tile_hp[build_row][build_col] = 0
        tile_cx = build_col * TILE + TILE // 2
        tile_cy = build_row * TILE + TILE // 2
        self.floats.append(FloatingText(tile_cx, tile_cy, "House built!", (210, 160, 60)))
        for _ in range(10):
            self.particles.append(Particle(tile_cx, tile_cy, (160, 82, 45)))

        import random
        if random.random() < 0.25:
            self.pets.append(Pet(tile_cx, tile_cy, kind="dog"))
            self.floats.append(FloatingText(tile_cx, tile_cy - 20, "Dog spawned!", (180, 130, 70)))
        else:
            self.workers.append(Worker(tile_cx, tile_cy))
            self.floats.append(FloatingText(tile_cx, tile_cy - 20, "Worker spawned!", (100, 220, 255)))

        if has_adjacent_house(self.world, build_col, build_row):
            self.pets.append(Pet(tile_cx, tile_cy, kind="cat"))
            self.floats.append(FloatingText(tile_cx, tile_cy - 36, "Cat appeared!", (255, 165, 0)))

    # -- update ------------------------------------------------------------

    def update(self, dt):
        """Update game state."""
        keys = pygame.key.get_pressed()
        mouse_buttons = pygame.mouse.get_pressed()
        p = self.player

        # Player movement & mining
        p.update_movement(keys, dt, self.world)
        p.update_mining(keys, mouse_buttons, dt, self.world, self.tile_hp,
                        self.cam_x, self.cam_y, self.particles, self.floats)

        # Hurt timer
        if p.hurt_timer > 0:
            p.hurt_timer -= dt

        # Workers
        for w in self.workers:
            w.update(dt, self.world, self.tile_hp, p.inventory, self.particles, self.floats)

        # Pets
        for pet in self.pets:
            pet.update(dt, p.x, p.y, self.world)

        # Enemies
        self._update_enemies(dt)

        # Weapon firing
        self._update_combat(keys, mouse_buttons, dt)

        # Projectiles & XP
        self._update_projectiles(dt)
        p.check_level_up(self.particles, self.floats)

        # Cull dead enemies
        self.enemies = [e for e in self.enemies if e.hp > 0]

        # Camera
        self.cam_x += (p.x - SCREEN_W // 2 - self.cam_x) * 0.1
        self.cam_y += (p.y - SCREEN_H // 2 - self.cam_y) * 0.1

        # Effects
        for par in self.particles:
            par.update()
        self.particles = [par for par in self.particles if par.life > 0]
        for f in self.floats:
            f.update()
        self.floats = [f for f in self.floats if f.life > 0]

    def _update_enemies(self, dt):
        """Update all enemies and check for attacks."""
        p = self.player
        for enemy in self.enemies:
            enemy.update(dt, p.x, p.y, self.cam_x, self.cam_y, self.world, self.particles)
            dmg = enemy.try_attack(p.x, p.y)
            if dmg > 0:
                p.take_damage(dmg, self.particles, self.floats)

    def _update_combat(self, keys, mouse_buttons, dt):
        """Handle weapon firing."""
        p = self.player
        if p.weapon_cooldown > 0:
            p.weapon_cooldown -= dt
        fire_input = keys[pygame.K_f] or mouse_buttons[2]
        if fire_input and p.weapon_cooldown <= 0:
            wpn = WEAPONS[p.weapon_level]
            self.projectiles.append(Projectile(p.x, p.y, p.facing_dx, p.facing_dy, wpn))
            p.weapon_cooldown = wpn["cooldown"]

    def _update_projectiles(self, dt):
        """Update all projectiles and check for hits."""
        for proj in self.projectiles:
            proj.update(dt)
            if proj.alive:
                proj.check_hits(self.enemies, self.particles, self.floats)
            self.player.xp += proj.xp_earned
            proj.xp_earned = 0
        self.projectiles = [proj for proj in self.projectiles if proj.alive]

    # -- drawing -----------------------------------------------------------

    def draw(self):
        """Render everything to screen."""
        self.screen.fill(BG)
        self._draw_world()
        self._draw_mining_bar()

        for par in self.particles:
            par.draw(self.screen, self.cam_x, self.cam_y)
        for f in self.floats:
            f.draw(self.screen, self.font, self.cam_x, self.cam_y)
        for w in self.workers:
            w.draw(self.screen, self.cam_x, self.cam_y)

        ticks = pygame.time.get_ticks()
        for pet in self.pets:
            pet.draw(self.screen, self.cam_x, self.cam_y, ticks)
        for enemy in self.enemies:
            enemy.draw(self.screen, self.cam_x, self.cam_y)
        for proj in self.projectiles:
            proj.draw(self.screen, self.cam_x, self.cam_y)

        self.player.draw(self.screen, self.cam_x, self.cam_y)
        draw_hud(self.screen, self.font, self.player, self.workers, self.pets)
        draw_tooltip(self.screen, self.font, self.cam_x, self.cam_y, self.world, self.tile_hp)
        pygame.display.flip()

    def _draw_world(self):
        """Draw visible tiles with details."""
        cam_x, cam_y = self.cam_x, self.cam_y
        start_col = max(0, int(cam_x) // TILE)
        end_col = min(WORLD_COLS, int(cam_x + SCREEN_W) // TILE + 2)
        start_row = max(0, int(cam_y) // TILE)
        end_row = min(WORLD_ROWS, int(cam_y + SCREEN_H) // TILE + 2)

        for r in range(start_row, end_row):
            for c in range(start_col, end_col):
                tid = self.world[r][c]
                info = TILE_INFO[tid]
                sx = c * TILE - int(cam_x)
                sy = r * TILE - int(cam_y)
                pygame.draw.rect(self.screen, info["color"], (sx, sy, TILE, TILE))

                if tid == TREE:
                    pygame.draw.rect(self.screen, (100, 70, 30), (sx + 12, sy + 16, 8, 16))
                    pygame.draw.circle(self.screen, (30, 130, 30), (sx + 16, sy + 12), 12)
                elif tid in (IRON_ORE, GOLD_ORE, DIAMOND_ORE):
                    for ox, oy in [(8, 8), (20, 12), (14, 22), (24, 24)]:
                        bright = [min(255, ch + 80) for ch in info["color"]]
                        pygame.draw.rect(self.screen, bright, (sx + ox, sy + oy, 3, 3))
                elif tid == WATER:
                    wave_off = int(math.sin(pygame.time.get_ticks() * 0.003 + c * 0.7) * 3)
                    pygame.draw.line(self.screen, (60, 150, 230),
                                     (sx + 4, sy + 14 + wave_off),
                                     (sx + 28, sy + 14 + wave_off), 2)
                elif tid == MOUNTAIN:
                    pygame.draw.polygon(self.screen, (110, 100, 90), [
                        (sx + 4, sy + TILE), (sx + 16, sy + 2), (sx + TILE - 4, sy + TILE)])
                    pygame.draw.polygon(self.screen, (230, 230, 240), [
                        (sx + 12, sy + 8), (sx + 16, sy + 2), (sx + 20, sy + 8)])
                    pygame.draw.line(self.screen, (70, 65, 60), (sx + 10, sy + 18), (sx + 14, sy + 12), 1)
                    pygame.draw.line(self.screen, (70, 65, 60), (sx + 20, sy + 20), (sx + 22, sy + 14), 1)
                elif tid == HOUSE:
                    pygame.draw.rect(self.screen, (180, 120, 60), (sx + 4, sy + 12, 24, 18))
                    pygame.draw.polygon(self.screen, (160, 40, 40), [
                        (sx + 2, sy + 12), (sx + 16, sy + 2), (sx + 30, sy + 12)])
                    pygame.draw.rect(self.screen, (100, 60, 30), (sx + 12, sy + 19, 8, 11))
                    pygame.draw.rect(self.screen, (180, 220, 255), (sx + 7, sy + 15, 5, 5))
                    pygame.draw.rect(self.screen, (80, 60, 40), (sx + 7, sy + 15, 5, 5), 1)

    def _draw_mining_bar(self):
        """Draw mining progress bar for active mining tile."""
        mt = self.player.mining_target
        if not mt:
            return
        mc, mr = mt
        info = TILE_INFO[self.world[mr][mc]]
        max_hp = info["hp"]
        if max_hp > 0:
            current = self.tile_hp[mr][mc]
            ratio = 1 - current / max_hp
            bx = mc * TILE - int(self.cam_x)
            by = mr * TILE - int(self.cam_y) - 8
            pygame.draw.rect(self.screen, (60, 60, 60), (bx, by, TILE, 5))
            pygame.draw.rect(self.screen, (50, 220, 50), (bx, by, int(TILE * ratio), 5))
