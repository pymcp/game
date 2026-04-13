import pygame
import random
import math
import sys

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SCREEN_W, SCREEN_H = 960, 640
TILE = 32
FPS = 60

# World size in tiles
WORLD_COLS = 80
WORLD_ROWS = 60

# Colors
BG = (30, 30, 46)
UI_BG = (20, 20, 30, 200)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

# Tile types ---------------------------------------------------------------
GRASS = 0
DIRT = 1
STONE = 2
IRON_ORE = 3
GOLD_ORE = 4
DIAMOND_ORE = 5
TREE = 6
WATER = 7
HOUSE = 8
MOUNTAIN = 9

TILE_INFO = {
    GRASS: {
        "name": "Grass",
        "color": (76, 153, 0),
        "mineable": False,
        "hp": 0,
        "drop": None,
        "drop_color": None,
    },
    DIRT: {
        "name": "Dirt",
        "color": (139, 90, 43),
        "mineable": True,
        "hp": 15,
        "drop": "Dirt",
        "drop_color": (139, 90, 43),
    },
    STONE: {
        "name": "Stone",
        "color": (136, 140, 141),
        "mineable": True,
        "hp": 30,
        "drop": "Stone",
        "drop_color": (136, 140, 141),
    },
    IRON_ORE: {
        "name": "Iron Ore",
        "color": (180, 130, 100),
        "mineable": True,
        "hp": 45,
        "drop": "Iron",
        "drop_color": (180, 130, 100),
    },
    GOLD_ORE: {
        "name": "Gold Ore",
        "color": (230, 200, 50),
        "mineable": True,
        "hp": 60,
        "drop": "Gold",
        "drop_color": (230, 200, 50),
    },
    DIAMOND_ORE: {
        "name": "Diamond",
        "color": (100, 220, 255),
        "mineable": True,
        "hp": 80,
        "drop": "Diamond",
        "drop_color": (100, 220, 255),
    },
    TREE: {
        "name": "Tree",
        "color": (34, 100, 34),
        "mineable": True,
        "hp": 20,
        "drop": "Wood",
        "drop_color": (139, 105, 60),
    },
    WATER: {
        "name": "Water",
        "color": (28, 100, 180),
        "mineable": False,
        "hp": 0,
        "drop": None,
        "drop_color": None,
    },
    HOUSE: {
        "name": "House",
        "color": (160, 82, 45),
        "mineable": False,
        "hp": 0,
        "drop": None,
        "drop_color": None,
    },
    MOUNTAIN: {
        "name": "Mountain",
        "color": (90, 80, 75),
        "mineable": True,
        "hp": 50,
        "drop": "Stone",
        "drop_color": (136, 140, 141),
    },
}

# Pickaxe tiers
PICKAXES = [
    {"name": "Wooden Pick", "power": 5, "color": (160, 120, 60)},
    {"name": "Stone Pick", "power": 10, "color": (150, 150, 150)},
    {"name": "Iron Pick", "power": 18, "color": (200, 180, 160)},
    {"name": "Gold Pick", "power": 28, "color": (240, 210, 60)},
    {"name": "Diamond Pick", "power": 45, "color": (120, 230, 255)},
]

UPGRADE_COSTS = [
    {"Stone": 10},
    {"Iron": 8},
    {"Gold": 6},
    {"Diamond": 4},
]

# ---------------------------------------------------------------------------
# Weapon Definitions  (add new weapons here!)
# ---------------------------------------------------------------------------
# Each weapon is a dict with:
#   name      – display name
#   damage    – HP removed from enemy on hit
#   distance  – max travel distance in pixels before despawning
#   speed     – projectile speed (world-units per normalised frame)
#   cooldown  – minimum frames between shots
#   size      – collision radius in pixels
#   color     – RGB color of the projectile
#   pierce    – if True the projectile passes through enemies (hits all in path)
#   knockback – knockback strength applied to hit enemies
#   draw      – how to render: ("circle",) or ("rect", w, h) or ("line", length, width)

WEAPONS = [
    {
        "name": "Rock Throw",
        "damage": 8,
        "distance": TILE * 5,
        "speed": 5.0,
        "cooldown": 25,
        "size": 4,
        "color": (160, 150, 140),
        "pierce": False,
        "knockback": 4,
        "draw": ("circle",),
    },
    {
        "name": "Iron Dagger",
        "damage": 15,
        "distance": TILE * 3,
        "speed": 7.0,
        "cooldown": 18,
        "size": 3,
        "color": (200, 190, 180),
        "pierce": False,
        "knockback": 5,
        "draw": ("line", 10, 2),
    },
    {
        "name": "Fire Bolt",
        "damage": 25,
        "distance": TILE * 7,
        "speed": 6.0,
        "cooldown": 35,
        "size": 5,
        "color": (255, 120, 30),
        "pierce": True,
        "knockback": 6,
        "draw": ("circle",),
    },
]

WEAPON_UNLOCK_COSTS = [
    {"Iron": 5},
    {"Gold": 5},
]

# ---------------------------------------------------------------------------
# World Generation
# ---------------------------------------------------------------------------


def generate_world():
    """Return a 2‑D list of tile‑type IDs using simple noise‑like placement."""
    world = [[GRASS for _ in range(WORLD_COLS)] for _ in range(WORLD_ROWS)]

    # Scatter clusters
    def scatter(tile_id, count, cluster_min, cluster_max):
        for _ in range(count):
            cx = random.randint(0, WORLD_COLS - 1)
            cy = random.randint(0, WORLD_ROWS - 1)
            size = random.randint(cluster_min, cluster_max)
            for __ in range(size):
                nx = cx + random.randint(-2, 2)
                ny = cy + random.randint(-2, 2)
                if 0 <= nx < WORLD_COLS and 0 <= ny < WORLD_ROWS:
                    world[ny][nx] = tile_id

    scatter(DIRT, 60, 4, 12)
    scatter(STONE, 45, 3, 10)
    scatter(WATER, 20, 4, 14)
    scatter(TREE, 70, 2, 6)
    scatter(IRON_ORE, 25, 2, 5)
    scatter(GOLD_ORE, 15, 1, 4)
    scatter(DIAMOND_ORE, 8, 1, 3)

    # Mountain ranges — larger clusters placed after ores so they can overlap
    scatter(MOUNTAIN, 30, 6, 18)

    return world


# ---------------------------------------------------------------------------
# Particles (mining feedback)
# ---------------------------------------------------------------------------


class Particle:
    __slots__ = ("x", "y", "vx", "vy", "life", "color", "size")

    def __init__(self, x, y, color):
        angle = random.uniform(0, 2 * math.pi)
        speed = random.uniform(1, 3)
        self.x = x
        self.y = y
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        self.life = random.randint(15, 30)
        self.color = color
        self.size = random.randint(2, 4)

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vy += 0.1  # gravity
        self.life -= 1

    def draw(self, surf, cam_x, cam_y):
        sx = int(self.x - cam_x)
        sy = int(self.y - cam_y)
        if 0 <= sx < SCREEN_W and 0 <= sy < SCREEN_H:
            pygame.draw.rect(surf, self.color, (sx, sy, self.size, self.size))


# ---------------------------------------------------------------------------
# Floating text (e.g. "+1 Iron")
# ---------------------------------------------------------------------------


class FloatingText:
    __slots__ = ("x", "y", "text", "color", "life")

    def __init__(self, x, y, text, color):
        self.x = x
        self.y = y
        self.text = text
        self.color = color
        self.life = 45

    def update(self):
        self.y -= 0.8
        self.life -= 1

    def draw(self, surf, font, cam_x, cam_y):
        alpha = max(0, min(255, self.life * 6))
        txt = font.render(self.text, True, self.color)
        txt.set_alpha(alpha)
        surf.blit(
            txt,
            (
                int(self.x - cam_x) - txt.get_width() // 2,
                int(self.y - cam_y) - txt.get_height() // 2,
            ),
        )


# ---------------------------------------------------------------------------
# Projectile (thrown weapon attack)
# ---------------------------------------------------------------------------


class Projectile:
    """A projectile fired in a direction.  Configured by a WEAPONS entry."""

    def __init__(self, x, y, dir_x, dir_y, weapon):
        self.x = float(x)
        self.y = float(y)
        self.dir_x = dir_x
        self.dir_y = dir_y
        self.speed = weapon["speed"]
        self.damage = weapon["damage"]
        self.distance = weapon["distance"]
        self.size = weapon["size"]
        self.color = weapon["color"]
        self.pierce = weapon["pierce"]
        self.knockback = weapon["knockback"]
        self.draw_style = weapon["draw"]
        self.travelled = 0.0
        self.alive = True
        self.hit_enemies = set()  # track already-hit enemies for pierce
        self.xp_earned = 0  # accumulated XP from kills this projectile made

    def update(self, dt):
        step = self.speed * dt
        self.x += self.dir_x * step
        self.y += self.dir_y * step
        self.travelled += step
        if self.travelled >= self.distance:
            self.alive = False
        # Die if out of world
        if (
            self.x < 0
            or self.x > WORLD_COLS * TILE
            or self.y < 0
            or self.y > WORLD_ROWS * TILE
        ):
            self.alive = False

    def check_hits(self, enemies, particles, floats):
        """Check collision with enemies, deal damage, return list of killed."""
        for enemy in enemies:
            if enemy.hp <= 0 or id(enemy) in self.hit_enemies:
                continue
            dist = math.hypot(enemy.x - self.x, enemy.y - self.y)
            if dist < self.size + 10:
                enemy.take_damage(self.damage, self.x, self.y, particles)
                # Extra knockback from weapon
                dx = enemy.x - self.x
                dy = enemy.y - self.y
                d = max(1, math.hypot(dx, dy))
                enemy.knockback_vx += (dx / d) * self.knockback
                enemy.knockback_vy += (dy / d) * self.knockback
                self.hit_enemies.add(id(enemy))
                if enemy.hp <= 0:
                    floats.append(
                        FloatingText(
                            enemy.x,
                            enemy.y,
                            f"{enemy.name} defeated! (+{enemy.xp} XP)",
                            (255, 220, 50),
                        )
                    )
                    self.xp_earned += enemy.xp
                    for _ in range(10):
                        particles.append(Particle(enemy.x, enemy.y, enemy.color))
                if not self.pierce:
                    self.alive = False
                    break

    def draw(self, surf, cam_x, cam_y):
        sx = int(self.x - cam_x)
        sy = int(self.y - cam_y)
        if sx < -20 or sx > SCREEN_W + 20 or sy < -20 or sy > SCREEN_H + 20:
            return
        style = self.draw_style[0]
        if style == "circle":
            pygame.draw.circle(surf, self.color, (sx, sy), self.size)
        elif style == "rect":
            w, h = self.draw_style[1], self.draw_style[2]
            pygame.draw.rect(surf, self.color, (sx - w // 2, sy - h // 2, w, h))
        elif style == "line":
            length, width = self.draw_style[1], self.draw_style[2]
            ex = sx + int(self.dir_x * length)
            ey = sy + int(self.dir_y * length)
            pygame.draw.line(surf, self.color, (sx, sy), (ex, ey), width)


# ---------------------------------------------------------------------------
# AI Worker
# ---------------------------------------------------------------------------


class Worker:
    """An AI-controlled character that wanders and mines for the player."""

    def __init__(self, x, y):
        self.x = float(x)
        self.y = float(y)
        self.speed = random.uniform(1.4, 2.2)

        # Randomised appearance
        self.body_color = (
            random.randint(60, 220),
            random.randint(60, 220),
            random.randint(60, 220),
        )
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
        self.hat_color = (
            random.randint(40, 255),
            random.randint(40, 255),
            random.randint(40, 255),
        )
        self.size_mod = random.uniform(0.8, 1.2)  # slightly different sizes

        # AI state
        self.state = "wander"  # "wander" | "walk_to" | "mining"
        self.target_tile = None  # (col, row)
        self.mine_progress = 0.0
        self.wander_timer = random.uniform(30, 120)  # frames until next decision
        self.dest_x = self.x
        self.dest_y = self.y

    # -- AI helpers --------------------------------------------------------

    def _pick_wander_dest(self):
        """Choose a random nearby walkable spot."""
        angle = random.uniform(0, 2 * math.pi)
        dist = random.uniform(TILE * 2, TILE * 6)
        self.dest_x = self.x + math.cos(angle) * dist
        self.dest_y = self.y + math.sin(angle) * dist
        self.dest_x = max(TILE, min((WORLD_COLS - 1) * TILE, self.dest_x))
        self.dest_y = max(TILE, min((WORLD_ROWS - 1) * TILE, self.dest_y))
        self.state = "wander"

    def _find_mineable(self, world):
        """Search nearby tiles for something mineable."""
        col = int(self.x) // TILE
        row = int(self.y) // TILE
        candidates = []
        search_r = 6
        for dr in range(-search_r, search_r + 1):
            for dc in range(-search_r, search_r + 1):
                c, r = col + dc, row + dr
                if 0 <= c < WORLD_COLS and 0 <= r < WORLD_ROWS:
                    if TILE_INFO[world[r][c]]["mineable"]:
                        d = abs(dc) + abs(dr)
                        candidates.append((d, c, r))
        if candidates:
            candidates.sort()
            # Pick one of the closest few for variety
            pick = random.choice(candidates[: min(5, len(candidates))])
            return (pick[1], pick[2])
        return None

    # -- Update ------------------------------------------------------------

    def update(self, dt, world, tile_hp, inventory, particles, floats):
        if self.state == "wander":
            # Walk toward wander destination
            dx = self.dest_x - self.x
            dy = self.dest_y - self.y
            dist = math.hypot(dx, dy)
            if dist > 2:
                self.x += (dx / dist) * self.speed * dt
                self.y += (dy / dist) * self.speed * dt
                # Avoid water
                col = int(self.x) // TILE
                row = int(self.y) // TILE
                if 0 <= col < WORLD_COLS and 0 <= row < WORLD_ROWS:
                    if world[row][col] in (WATER, MOUNTAIN):
                        self.x -= (dx / dist) * self.speed * dt
                        self.y -= (dy / dist) * self.speed * dt
                        self._pick_wander_dest()
            self.wander_timer -= dt
            if self.wander_timer <= 0 or dist <= 2:
                # Try to find something to mine
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
            # Check tile still mineable
            if (
                not (0 <= tc < WORLD_COLS and 0 <= tr < WORLD_ROWS)
                or not TILE_INFO[world[tr][tc]]["mineable"]
            ):
                self._pick_wander_dest()
                return
            dx = self.dest_x - self.x
            dy = self.dest_y - self.y
            dist = math.hypot(dx, dy)
            if dist > TILE * 1.2:
                self.x += (dx / dist) * self.speed * dt
                self.y += (dy / dist) * self.speed * dt
                # Avoid water
                col = int(self.x) // TILE
                row = int(self.y) // TILE
                if 0 <= col < WORLD_COLS and 0 <= row < WORLD_ROWS:
                    if world[row][col] in (WATER, MOUNTAIN):
                        self.x -= (dx / dist) * self.speed * dt
                        self.y -= (dy / dist) * self.speed * dt
                        self._pick_wander_dest()
            else:
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
            power = 5  # workers mine at base speed
            self.mine_progress += power * dt * 0.15
            tile_hp[tr][tc] = max(
                0, TILE_INFO[world[tr][tc]]["hp"] - self.mine_progress
            )
            # Mining particles
            if random.random() < 0.25:
                particles.append(
                    Particle(tile_cx, tile_cy, TILE_INFO[world[tr][tc]]["color"])
                )
            if tile_hp[tr][tc] <= 0:
                info = TILE_INFO[world[tr][tc]]
                drop = info["drop"]
                if drop:
                    inventory[drop] = inventory.get(drop, 0) + 1
                    floats.append(
                        FloatingText(tile_cx, tile_cy, f"+1 {drop}", info["drop_color"])
                    )
                for _ in range(8):
                    particles.append(Particle(tile_cx, tile_cy, info["color"]))
                # Mountains become dirt paths when mined
                new_tile = DIRT if world[tr][tc] == MOUNTAIN else GRASS
                world[tr][tc] = new_tile
                tile_hp[tr][tc] = TILE_INFO[new_tile]["hp"]
                self._pick_wander_dest()

        # Clamp to world
        self.x = max(TILE, min((WORLD_COLS - 1) * TILE, self.x))
        self.y = max(TILE, min((WORLD_ROWS - 1) * TILE, self.y))

    # -- Draw --------------------------------------------------------------

    def draw(self, surf, cam_x, cam_y):
        sx = int(self.x - cam_x)
        sy = int(self.y - cam_y)
        if sx < -40 or sx > SCREEN_W + 40 or sy < -40 or sy > SCREEN_H + 40:
            return
        s = self.size_mod
        bw = int(16 * s)
        bh = int(22 * s)
        # Body
        pygame.draw.rect(
            surf,
            self.body_color,
            (sx - bw // 2, sy - int(10 * s), bw, bh),
            border_radius=3,
        )
        # Head
        head_r = int(7 * s)
        pygame.draw.circle(surf, self.skin_color, (sx, sy - int(14 * s)), head_r)
        # Hat
        hat_w = int(14 * s)
        hat_h = int(5 * s)
        pygame.draw.rect(
            surf, self.hat_color, (sx - hat_w // 2, sy - int(20 * s), hat_w, hat_h)
        )
        # Pick (small)
        pygame.draw.line(
            surf,
            (160, 120, 60),
            (sx + int(8 * s), sy - int(4 * s)),
            (sx + int(14 * s), sy - int(12 * s)),
            2,
        )


# ---------------------------------------------------------------------------
# Pet (Cat / Dog) — follows the player around
# ---------------------------------------------------------------------------

CAT_COLORS = [
    (255, 165, 0),
    (80, 80, 80),
    (220, 220, 220),
    (180, 120, 50),
    (50, 50, 50),
    (255, 200, 150),
    (100, 100, 100),
    (200, 160, 80),
]

DOG_COLORS = [
    (180, 130, 70),
    (100, 70, 40),
    (220, 200, 170),
    (60, 60, 60),
    (200, 180, 150),
    (140, 100, 60),
    (90, 60, 30),
    (170, 150, 130),
]


class Pet:
    """A cat or dog that follows the player."""

    def __init__(self, x, y, kind="cat"):
        self.x = float(x)
        self.y = float(y)
        self.kind = kind  # "cat" or "dog"
        self.speed = random.uniform(2.8, 3.6)

        if kind == "cat":
            self.body_color = random.choice(CAT_COLORS)
            self.eye_color = random.choice(
                [(50, 200, 50), (200, 180, 30), (80, 160, 220)]
            )
            self.size = random.uniform(0.7, 1.0)
        else:
            self.body_color = random.choice(DOG_COLORS)
            self.eye_color = random.choice([(60, 40, 20), (40, 30, 15), (80, 60, 30)])
            self.size = random.uniform(0.85, 1.2)

        self.spot_color = (
            min(255, self.body_color[0] + random.randint(-40, 40)),
            min(255, self.body_color[1] + random.randint(-40, 40)),
            min(255, self.body_color[2] + random.randint(-40, 40)),
        )
        self.tail_phase = random.uniform(0, math.pi * 2)
        # Offset so multiple pets don't stack exactly on the player
        self.follow_offset_x = random.uniform(-20, 20)
        self.follow_offset_y = random.uniform(10, 30)

    def update(self, dt, target_x, target_y, world):
        dest_x = target_x + self.follow_offset_x
        dest_y = target_y + self.follow_offset_y
        dx = dest_x - self.x
        dy = dest_y - self.y
        dist = math.hypot(dx, dy)
        if dist > 18:
            move_speed = self.speed * dt
            # Speed up if far away so they don't get lost
            if dist > TILE * 5:
                move_speed *= 2.5
            self.x += (dx / dist) * move_speed
            self.y += (dy / dist) * move_speed
            # Avoid water by reverting
            col = int(self.x) // TILE
            row = int(self.y) // TILE
            if 0 <= col < WORLD_COLS and 0 <= row < WORLD_ROWS:
                if world[row][col] in (WATER, MOUNTAIN):
                    self.x -= (dx / dist) * move_speed
                    self.y -= (dy / dist) * move_speed
        # Clamp
        self.x = max(TILE, min((WORLD_COLS - 1) * TILE, self.x))
        self.y = max(TILE, min((WORLD_ROWS - 1) * TILE, self.y))

    def draw(self, surf, cam_x, cam_y, ticks):
        sx = int(self.x - cam_x)
        sy = int(self.y - cam_y)
        if sx < -40 or sx > SCREEN_W + 40 or sy < -40 or sy > SCREEN_H + 40:
            return
        s = self.size

        if self.kind == "cat":
            # Body (oval-ish rect)
            bw, bh = int(14 * s), int(8 * s)
            pygame.draw.ellipse(
                surf, self.body_color, (sx - bw // 2, sy - bh // 2, bw, bh)
            )
            # Head
            hr = int(5 * s)
            hx = sx + int(7 * s)
            pygame.draw.circle(surf, self.body_color, (hx, sy - int(2 * s)), hr)
            # Ears (triangles)
            ear_s = int(3 * s)
            pygame.draw.polygon(
                surf,
                self.body_color,
                [
                    (hx - ear_s, sy - int(6 * s)),
                    (hx - ear_s - 2, sy - int(10 * s)),
                    (hx - ear_s + 3, sy - int(7 * s)),
                ],
            )
            pygame.draw.polygon(
                surf,
                self.body_color,
                [
                    (hx + ear_s, sy - int(6 * s)),
                    (hx + ear_s + 2, sy - int(10 * s)),
                    (hx + ear_s - 3, sy - int(7 * s)),
                ],
            )
            # Eyes
            pygame.draw.circle(
                surf, self.eye_color, (hx - 2, sy - int(3 * s)), max(1, int(1.5 * s))
            )
            pygame.draw.circle(
                surf, self.eye_color, (hx + 2, sy - int(3 * s)), max(1, int(1.5 * s))
            )
            # Tail (wavy line)
            tail_wave = math.sin(ticks * 0.008 + self.tail_phase) * 4
            pygame.draw.line(
                surf,
                self.body_color,
                (sx - int(7 * s), sy),
                (sx - int(14 * s), sy - int(4 * s) + int(tail_wave)),
                2,
            )
        else:
            # Dog body (slightly larger, rectangular)
            bw, bh = int(16 * s), int(10 * s)
            pygame.draw.ellipse(
                surf, self.body_color, (sx - bw // 2, sy - bh // 2, bw, bh)
            )
            # Spots
            pygame.draw.circle(
                surf, self.spot_color, (sx - int(3 * s), sy - int(1 * s)), int(2.5 * s)
            )
            # Head
            hr = int(6 * s)
            hx = sx + int(8 * s)
            pygame.draw.circle(surf, self.body_color, (hx, sy - int(2 * s)), hr)
            # Snout
            pygame.draw.ellipse(
                surf,
                self.spot_color,
                (hx + int(2 * s), sy - int(3 * s), int(5 * s), int(4 * s)),
            )
            # Ears (floppy)
            pygame.draw.ellipse(
                surf,
                self.body_color,
                (hx - int(5 * s), sy - int(6 * s), int(4 * s), int(7 * s)),
            )
            pygame.draw.ellipse(
                surf,
                self.body_color,
                (hx + int(2 * s), sy - int(6 * s), int(4 * s), int(7 * s)),
            )
            # Eyes
            pygame.draw.circle(
                surf, self.eye_color, (hx - 2, sy - int(4 * s)), max(1, int(1.5 * s))
            )
            pygame.draw.circle(
                surf, self.eye_color, (hx + 2, sy - int(4 * s)), max(1, int(1.5 * s))
            )
            # Tail (wagging)
            tail_wag = math.sin(ticks * 0.012 + self.tail_phase) * 6
            pygame.draw.line(
                surf,
                self.body_color,
                (sx - int(8 * s), sy - int(2 * s)),
                (sx - int(14 * s), sy - int(8 * s) + int(tail_wag)),
                3,
            )


def has_adjacent_house(world, col, row):
    """Return True if any orthogonal neighbor is a HOUSE tile."""
    for dc, dr in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        nc, nr = col + dc, row + dr
        if 0 <= nc < WORLD_COLS and 0 <= nr < WORLD_ROWS:
            if world[nr][nc] == HOUSE:
                return True
    return False


# ---------------------------------------------------------------------------
# Enemy Definitions  (add new enemy types here!)
# ---------------------------------------------------------------------------
# Each enemy type is a dict with:
#   name        – display name
#   color       – primary RGB color
#   hp          – max hit-points
#   attack      – damage dealt per hit to the player
#   speed       – movement speed (world-units per normalised frame)
#   attack_cd   – cooldown between attacks in normalised frames
#   chase_range – pixel distance at which enemy starts chasing (0 = viewport)
#   draw_commands – list of vector draw instructions executed relative to
#                   the enemy's screen position (sx, sy).  Each entry is a
#                   tuple:  (shape, color_offset, *args)
#       shape = "circle"  -> (cx_off, cy_off, radius)
#       shape = "rect"    -> (x_off, y_off, w, h)
#       shape = "ellipse" -> (x_off, y_off, w, h)
#       shape = "line"    -> (x1_off, y1_off, x2_off, y2_off, width)
#       shape = "polygon" -> ([(x_off, y_off), ...],)
#   color_offset is added per-channel to the type's base color (clamped 0-255).

ENEMY_TYPES = {
    "slime": {
        "maximum": 5,
        "xp": 10,
        "name": "Slime",
        "color": (50, 180, 50),
        "hp": 30,
        "attack": 5,
        "speed": 1.2,
        "attack_cd": 40,
        "chase_range": 0,  # 0 = use viewport check
        "draw_commands": [
            # body – squat ellipse
            ("ellipse", (0, 0, 0), -10, -4, 20, 14),
            # highlight blob
            ("ellipse", (40, 40, 40), -6, -2, 8, 6),
            # left eye
            ("circle", (-80, -80, -80), -4, -6, 2),
            # right eye
            ("circle", (-80, -80, -80), 4, -6, 2),
        ],
    },
    "blocker": {
        "maximum": 5,
        "xp": 10,
        "name": "Blocker",
        "color": (180, 25, 25),
        "hp": 30,
        "attack": 5,
        "speed": 0.8,
        "attack_cd": 2,
        "chase_range": 0,
        "draw_commands": [
            # Body
            ("rect", (0, 0, 0), -10, -10, 20, 20),
            # Eye
            ("circle", (-180, -25, -25), -4, -4, 2),  # left eye
            ("circle", (-180, -25, -25), 4, -4, 2),  # right eye
        ],
    },
    "boss": {
        "maximum": 1,
        "xp": 20,
        "name": "Boss",
        "color": (255, 200, 150),
        "hp": 50,
        "attack": 10,
        "speed": 1.6,
        "attack_cd": 1,
        "chase_range": 0,
        "draw_commands": [
            # Body
            (
                "polygon",
                (0, 0, 0),
                [(-12, -10), (0, -14), (12, -10), (10, 10), (-10, 10)],
            ),
        ],
    },
}


def _clamp_color(base, offset):
    return tuple(max(0, min(255, base[i] + offset[i])) for i in range(3))


class Enemy:
    """A data-driven enemy instance.  Create with an enemy-type key."""

    def __init__(self, x, y, type_key):
        self.x = float(x)
        self.y = float(y)
        self.type_key = type_key
        info = ENEMY_TYPES[type_key]
        self.hp = info["hp"]
        self.max_hp = info["hp"]
        self.attack = info["attack"]
        self.speed = info["speed"]
        self.xp = info["xp"]
        self.color = info["color"]
        self.attack_cd = info["attack_cd"]
        self.draw_commands = info["draw_commands"]
        self.name = info["name"]
        self.chase_range = info["chase_range"]

        # State: "idle" | "chase" | "attack"
        self.state = "idle"
        self.cooldown = 0.0  # frames until next attack
        self.hurt_flash = 0  # frames of white flash when hit
        self.knockback_vx = 0.0
        self.knockback_vy = 0.0

    # -- helpers -----------------------------------------------------------

    def _on_screen(self, cam_x, cam_y, margin=0):
        return (
            cam_x - margin <= self.x <= cam_x + SCREEN_W + margin
            and cam_y - margin <= self.y <= cam_y + SCREEN_H + margin
        )

    def _blocked(self, wx, wy, world):
        col = int(wx) // TILE
        row = int(wy) // TILE
        if col < 0 or col >= WORLD_COLS or row < 0 or row >= WORLD_ROWS:
            return True
        return world[row][col] in (WATER, MOUNTAIN, HOUSE)

    # -- update ------------------------------------------------------------

    def update(self, dt, px, py, cam_x, cam_y, world, particles):
        if self.hp <= 0:
            return

        # Apply knockback
        if abs(self.knockback_vx) > 0.1 or abs(self.knockback_vy) > 0.1:
            nx = self.x + self.knockback_vx * dt
            ny = self.y + self.knockback_vy * dt
            if not self._blocked(nx, ny, world):
                self.x = nx
                self.y = ny
            self.knockback_vx *= 0.8
            self.knockback_vy *= 0.8

        if self.hurt_flash > 0:
            self.hurt_flash -= 1

        if self.cooldown > 0:
            self.cooldown -= dt

        dist = math.hypot(px - self.x, py - self.y)

        if self.state == "idle":
            # Wake up when on screen (or within chase_range)
            trigger = self.chase_range if self.chase_range > 0 else None
            if trigger:
                if dist < trigger:
                    self.state = "chase"
            else:
                if self._on_screen(cam_x, cam_y, margin=TILE * 2):
                    self.state = "chase"

        elif self.state == "chase":
            # Move toward the player
            if dist > 1:
                dx = (px - self.x) / dist
                dy = (py - self.y) / dist
                nx = self.x + dx * self.speed * dt
                ny = self.y + dy * self.speed * dt
                if not self._blocked(nx, self.y, world):
                    self.x = nx
                if not self._blocked(self.x, ny, world):
                    self.y = ny

            # Close enough to attack?
            if dist < TILE * 0.9:
                self.state = "attack"

            # Go idle if player is far away and off-screen
            if dist > SCREEN_W and not self._on_screen(cam_x, cam_y, margin=TILE * 4):
                self.state = "idle"

        elif self.state == "attack":
            # Stay close and keep swinging
            if dist > TILE * 1.5:
                self.state = "chase"

        # Clamp to world
        self.x = max(TILE, min((WORLD_COLS - 1) * TILE, self.x))
        self.y = max(TILE, min((WORLD_ROWS - 1) * TILE, self.y))

    def try_attack(self, px, py):
        """Return damage dealt this frame (0 if on cooldown / out of range)."""
        if self.hp <= 0 or self.state != "attack":
            return 0
        dist = math.hypot(px - self.x, py - self.y)
        if dist < TILE * 1.2 and self.cooldown <= 0:
            self.cooldown = self.attack_cd
            return self.attack
        return 0

    def take_damage(self, amount, source_x, source_y, particles):
        """Apply damage and knockback away from source."""
        self.hp -= amount
        self.hurt_flash = 8
        dx = self.x - source_x
        dy = self.y - source_y
        dist = max(1, math.hypot(dx, dy))
        self.knockback_vx = (dx / dist) * 6
        self.knockback_vy = (dy / dist) * 6
        for _ in range(6):
            particles.append(Particle(self.x, self.y, self.color))

    # -- draw --------------------------------------------------------------

    def draw(self, surf, cam_x, cam_y):
        if self.hp <= 0:
            return
        sx = int(self.x - cam_x)
        sy = int(self.y - cam_y)
        if sx < -40 or sx > SCREEN_W + 40 or sy < -40 or sy > SCREEN_H + 40:
            return

        base = (255, 255, 255) if self.hurt_flash > 0 else self.color

        for cmd in self.draw_commands:
            shape = cmd[0]
            color_offset = cmd[1]
            c = _clamp_color(base, color_offset)
            args = cmd[2:]

            if shape == "circle":
                cx_off, cy_off, radius = args
                pygame.draw.circle(surf, c, (sx + cx_off, sy + cy_off), radius)
            elif shape == "rect":
                xo, yo, w, h = args
                pygame.draw.rect(surf, c, (sx + xo, sy + yo, w, h))
            elif shape == "ellipse":
                xo, yo, w, h = args
                pygame.draw.ellipse(surf, c, (sx + xo, sy + yo, w, h))
            elif shape == "line":
                x1, y1, x2, y2, width = args
                pygame.draw.line(surf, c, (sx + x1, sy + y1), (sx + x2, sy + y2), width)
            elif shape == "polygon":
                points_off = args[0]
                pts = [(sx + px_off, sy + py_off) for px_off, py_off in points_off]
                pygame.draw.polygon(surf, c, pts)

        # HP bar (only when damaged)
        if self.hp < self.max_hp:
            bar_w = 20
            bx = sx - bar_w // 2
            by = sy - 16
            ratio = max(0, self.hp / self.max_hp)
            pygame.draw.rect(surf, (60, 60, 60), (bx, by, bar_w, 3))
            pygame.draw.rect(surf, (220, 40, 40), (bx, by, int(bar_w * ratio), 3))


def spawn_enemies(world):
    """Scatter enemies on walkable tiles throughout the world."""
    enemies = []
    spawn_count = {}
    for _ in range(25):
        for attempt in range(20):
            col = random.randint(2, WORLD_COLS - 3)
            row = random.randint(2, WORLD_ROWS - 3)
            if world[row][col] == GRASS:
                # Don't spawn too close to world center (player start)
                cx = col * TILE + TILE // 2
                cy = row * TILE + TILE // 2
                mid_x = (WORLD_COLS // 2) * TILE
                mid_y = (WORLD_ROWS // 2) * TILE
                if math.hypot(cx - mid_x, cy - mid_y) > TILE * 8:
                    enemy_key = random.choice(list(ENEMY_TYPES.keys()))
                    count = spawn_count.get(enemy_key, 0)
                    if count >= ENEMY_TYPES[enemy_key]["maximum"]:
                        continue
                    spawn_count[enemy_key] = count + 1
                    enemies.append(Enemy(cx, cy, enemy_key))
                    break
    return enemies


# ---------------------------------------------------------------------------
# Main Game
# ---------------------------------------------------------------------------


def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("Mining Game")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("monospace", 16)
    big_font = pygame.font.SysFont("monospace", 22, bold=True)

    # World state
    world = generate_world()
    # HP per tile instance
    tile_hp = [
        [TILE_INFO[world[r][c]]["hp"] for c in range(WORLD_COLS)]
        for r in range(WORLD_ROWS)
    ]

    # Player state
    px = (WORLD_COLS // 2) * TILE + TILE // 2
    py = (WORLD_ROWS // 2) * TILE + TILE // 2
    speed = 3.2
    pick_level = 0  # index into PICKAXES

    inventory = {}  # name -> count

    # Player health
    player_hp = 100
    player_max_hp = 100
    player_xp = 0
    player_level = 1

    # XP needed per level: 20, 45, 80, 125, 180, ... (+5 more each tier)
    def xp_for_level(lvl):
        base, inc = 20, 5
        return base + inc * (lvl - 1) * lvl // 2

    player_xp_next = xp_for_level(player_level)
    player_hurt_timer = 0  # invincibility frames after being hit

    # Player facing direction (last non-zero movement)
    facing_dx = 1.0
    facing_dy = 0.0

    # Weapon state
    weapon_level = 0  # index into WEAPONS
    weapon_cooldown = 0.0
    projectiles = []

    # Camera
    cam_x = px - SCREEN_W // 2
    cam_y = py - SCREEN_H // 2

    # Effects
    particles = []
    floats = []

    # Mining state
    mining_target = None  # (col, row)
    mining_progress = 0.0

    # AI Workers
    workers = []

    # Pets (cats and dogs)
    pets = []

    # Enemies
    enemies = spawn_enemies(world)

    running = True
    while running:
        dt = clock.tick(FPS) / 16.667  # normalise to ~60 fps

        # --- Events -------------------------------------------------------
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_u:
                    # Upgrade pickaxe
                    if pick_level < len(PICKAXES) - 1:
                        cost = UPGRADE_COSTS[pick_level]
                        can_afford = all(
                            inventory.get(k, 0) >= v for k, v in cost.items()
                        )
                        if can_afford:
                            for k, v in cost.items():
                                inventory[k] -= v
                                if inventory[k] <= 0:
                                    del inventory[k]
                            pick_level += 1
                elif event.key == pygame.K_b:
                    # Build a house (costs 20 Dirt)
                    build_col = int(px) // TILE
                    build_row = int(py) // TILE
                    if 0 <= build_col < WORLD_COLS and 0 <= build_row < WORLD_ROWS:
                        if (
                            world[build_row][build_col] == GRASS
                            and inventory.get("Dirt", 0) >= 20
                        ):
                            inventory["Dirt"] -= 20
                            if inventory["Dirt"] <= 0:
                                del inventory["Dirt"]
                            world[build_row][build_col] = HOUSE
                            tile_hp[build_row][build_col] = 0
                            tile_cx = build_col * TILE + TILE // 2
                            tile_cy = build_row * TILE + TILE // 2
                            floats.append(
                                FloatingText(
                                    tile_cx, tile_cy, "House built!", (210, 160, 60)
                                )
                            )
                            for _ in range(10):
                                particles.append(
                                    Particle(tile_cx, tile_cy, (160, 82, 45))
                                )

                            # Random chance: spawn a dog (25%) instead of a worker
                            if random.random() < 0.25:
                                pets.append(Pet(tile_cx, tile_cy, kind="dog"))
                                floats.append(
                                    FloatingText(
                                        tile_cx,
                                        tile_cy - 20,
                                        "Dog spawned!",
                                        (180, 130, 70),
                                    )
                                )
                            else:
                                workers.append(Worker(tile_cx, tile_cy))
                                floats.append(
                                    FloatingText(
                                        tile_cx,
                                        tile_cy - 20,
                                        "Worker spawned!",
                                        (100, 220, 255),
                                    )
                                )

                            # Check for adjacent houses -> spawn a cat
                            if has_adjacent_house(world, build_col, build_row):
                                pets.append(Pet(tile_cx, tile_cy, kind="cat"))
                                floats.append(
                                    FloatingText(
                                        tile_cx,
                                        tile_cy - 36,
                                        "Cat appeared!",
                                        (255, 165, 0),
                                    )
                                )
                elif event.key == pygame.K_n:
                    # Upgrade weapon
                    if weapon_level < len(WEAPONS) - 1:
                        cost = WEAPON_UNLOCK_COSTS[weapon_level]
                        can_afford = all(
                            inventory.get(k, 0) >= v for k, v in cost.items()
                        )
                        if can_afford:
                            for k, v in cost.items():
                                inventory[k] -= v
                                if inventory[k] <= 0:
                                    del inventory[k]
                            weapon_level += 1

        # --- Movement -----------------------------------------------------
        keys = pygame.key.get_pressed()
        dx = dy = 0
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            dx -= 1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            dx += 1
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            dy -= 1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            dy += 1

        if dx and dy:
            dx *= 0.707
            dy *= 0.707

        # Track facing direction
        if dx != 0 or dy != 0:
            mag = math.hypot(dx, dy)
            facing_dx = dx / mag
            facing_dy = dy / mag

        new_px = px + dx * speed * dt
        new_py = py + dy * speed * dt

        # Collision with world bounds; water causes a 2-tile bounce
        def tile_at(wx, wy):
            col = int(wx) // TILE
            row = int(wy) // TILE
            if col < 0 or col >= WORLD_COLS or row < 0 or row >= WORLD_ROWS:
                return -1  # out of bounds sentinel
            return world[row][col]

        def in_bounds(wx, wy):
            col = int(wx) // TILE
            row = int(wy) // TILE
            return 0 <= col < WORLD_COLS and 0 <= row < WORLD_ROWS

        BLOCKING_TILES = (WATER, MOUNTAIN)

        def hits_blocking(cx, cy, h):
            """Return True if the player box at (cx, cy) overlaps a blocking tile."""
            for ox in (-h, h):
                for oy in (-h, h):
                    if tile_at(cx + ox, cy + oy) in BLOCKING_TILES:
                        return True
            return False

        def out_of_bounds(cx, cy, h):
            for ox in (-h, h):
                for oy in (-h, h):
                    if not in_bounds(cx + ox, cy + oy):
                        return True
            return False

        half = 10  # half-size of player collision box
        bounce_dist = TILE * 2  # 2-tile bounce

        # Try moving X
        if not out_of_bounds(new_px, py, half):
            if hits_blocking(new_px, py, half):
                # Bounce back opposite to movement direction
                bounce_dir = -1 if dx > 0 else 1 if dx < 0 else 0
                bounce_px = px + bounce_dir * bounce_dist
                if not out_of_bounds(bounce_px, py, half) and not hits_blocking(
                    bounce_px, py, half
                ):
                    px = bounce_px
                # else: stay in place
            else:
                px = new_px

        # Try moving Y
        if not out_of_bounds(px, new_py, half):
            if hits_blocking(px, new_py, half):
                bounce_dir = -1 if dy > 0 else 1 if dy < 0 else 0
                bounce_py = py + bounce_dir * bounce_dist
                if not out_of_bounds(px, bounce_py, half) and not hits_blocking(
                    px, bounce_py, half
                ):
                    py = bounce_py
            else:
                py = new_py

        # Clamp to world
        px = max(half, min(WORLD_COLS * TILE - half, px))
        py = max(half, min(WORLD_ROWS * TILE - half, py))

        # --- Mining (hold SPACE or left-click) ----------------------------
        mouse_buttons = pygame.mouse.get_pressed()
        mining_input = keys[pygame.K_SPACE] or mouse_buttons[0]

        # Determine targeted tile (mouse position -> world coords, or facing tile)
        target_col, target_row = None, None
        if mouse_buttons[0]:
            mx, my = pygame.mouse.get_pos()
            target_col = int((mx + cam_x) // TILE)
            target_row = int((my + cam_y) // TILE)
        elif keys[pygame.K_SPACE]:
            # Mine tile the player is standing on or nearest mineable neighbor
            center_col = int(px) // TILE
            center_row = int(py) // TILE
            # Check surrounding tiles (including center) for mineable
            best = None
            best_dist = 999
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
                # Check distance
                tile_cx = target_col * TILE + TILE // 2
                tile_cy = target_row * TILE + TILE // 2
                dist = math.hypot(px - tile_cx, py - tile_cy)
                if (
                    dist < TILE * 2.5
                    and TILE_INFO[world[target_row][target_col]]["mineable"]
                ):
                    if mining_target != (target_col, target_row):
                        mining_target = (target_col, target_row)
                        mining_progress = 0
                    pick = PICKAXES[pick_level]
                    mining_progress += pick["power"] * dt * 0.15
                    tile_hp[target_row][target_col] = max(
                        0,
                        TILE_INFO[world[target_row][target_col]]["hp"]
                        - mining_progress,
                    )

                    # Particles while mining
                    if random.random() < 0.4:
                        pcol = TILE_INFO[world[target_row][target_col]]["color"]
                        particles.append(Particle(tile_cx, tile_cy, pcol))

                    if tile_hp[target_row][target_col] <= 0:
                        info = TILE_INFO[world[target_row][target_col]]
                        drop = info["drop"]
                        if drop:
                            inventory[drop] = inventory.get(drop, 0) + 1
                            floats.append(
                                FloatingText(
                                    tile_cx, tile_cy, f"+1 {drop}", info["drop_color"]
                                )
                            )
                        # Burst of particles
                        for _ in range(12):
                            particles.append(Particle(tile_cx, tile_cy, info["color"]))
                        # Mountains become dirt paths when mined
                        new_tile = (
                            DIRT if world[target_row][target_col] == MOUNTAIN else GRASS
                        )
                        world[target_row][target_col] = new_tile
                        tile_hp[target_row][target_col] = TILE_INFO[new_tile]["hp"]
                        mining_target = None
                        mining_progress = 0
                else:
                    mining_target = None
                    mining_progress = 0
        else:
            mining_target = None
            mining_progress = 0

        # --- Update AI Workers --------------------------------------------
        for w in workers:
            w.update(dt, world, tile_hp, inventory, particles, floats)

        # --- Update Pets --------------------------------------------------
        for pet in pets:
            pet.update(dt, px, py, world)

        # --- Update Enemies -----------------------------------------------
        if player_hurt_timer > 0:
            player_hurt_timer -= dt
        for enemy in enemies:
            enemy.update(dt, px, py, cam_x, cam_y, world, particles)
            dmg = enemy.try_attack(px, py)
            if dmg > 0 and player_hurt_timer <= 0:
                player_hp = max(0, player_hp - dmg)
                player_hurt_timer = 30  # ~0.5s invincibility
                floats.append(FloatingText(px, py - 20, f"-{dmg} HP", (255, 60, 60)))
                for _ in range(6):
                    particles.append(Particle(px, py, (255, 60, 60)))

        # Player attacks enemies with thrown weapon (F key or right-click)
        if weapon_cooldown > 0:
            weapon_cooldown -= dt
        mouse_buttons_r = pygame.mouse.get_pressed()
        # fire_input = keys[pygame.K_f] or mouse_buttons_r[2]
        fire_input = True
        if fire_input and weapon_cooldown <= 0:
            wpn = WEAPONS[weapon_level]
            projectiles.append(Projectile(px, py, facing_dx, facing_dy, wpn))
            weapon_cooldown = wpn["cooldown"]

        # Update projectiles
        for proj in projectiles:
            proj.update(dt)
            if proj.alive:
                proj.check_hits(enemies, particles, floats)
            player_xp += proj.xp_earned
            proj.xp_earned = 0
        projectiles = [p for p in projectiles if p.alive]

        # Level up check
        while player_xp >= player_xp_next:
            player_xp -= player_xp_next
            player_level += 1
            player_xp_next = xp_for_level(player_level)
            player_max_hp += 10
            player_hp = player_max_hp
            floats.append(
                FloatingText(px, py - 30, f"Level {player_level}!", (255, 255, 100))
            )
            for _ in range(15):
                particles.append(Particle(px, py, (255, 255, 100)))

        # Remove dead enemies
        enemies = [e for e in enemies if e.hp > 0]

        # --- Camera -------------------------------------------------------
        cam_x += (px - SCREEN_W // 2 - cam_x) * 0.1
        cam_y += (py - SCREEN_H // 2 - cam_y) * 0.1

        # --- Update effects -----------------------------------------------
        for p in particles:
            p.update()
        particles = [p for p in particles if p.life > 0]

        for f in floats:
            f.update()
        floats = [f for f in floats if f.life > 0]

        # --- Draw ---------------------------------------------------------
        screen.fill(BG)

        # Visible tile range
        start_col = max(0, int(cam_x) // TILE)
        end_col = min(WORLD_COLS, int(cam_x + SCREEN_W) // TILE + 2)
        start_row = max(0, int(cam_y) // TILE)
        end_row = min(WORLD_ROWS, int(cam_y + SCREEN_H) // TILE + 2)

        for r in range(start_row, end_row):
            for c in range(start_col, end_col):
                tid = world[r][c]
                info = TILE_INFO[tid]
                sx = c * TILE - int(cam_x)
                sy = r * TILE - int(cam_y)
                pygame.draw.rect(screen, info["color"], (sx, sy, TILE, TILE))

                # Tree trunk / canopy detail
                if tid == TREE:
                    pygame.draw.rect(screen, (100, 70, 30), (sx + 12, sy + 16, 8, 16))
                    pygame.draw.circle(screen, (30, 130, 30), (sx + 16, sy + 12), 12)

                # Ore sparkle
                if tid in (IRON_ORE, GOLD_ORE, DIAMOND_ORE):
                    for ox, oy in [(8, 8), (20, 12), (14, 22), (24, 24)]:
                        bright = [min(255, ch + 80) for ch in info["color"]]
                        pygame.draw.rect(screen, bright, (sx + ox, sy + oy, 3, 3))

                # Water wave
                if tid == WATER:
                    wave_off = int(
                        math.sin(pygame.time.get_ticks() * 0.003 + c * 0.7) * 3
                    )
                    pygame.draw.line(
                        screen,
                        (60, 150, 230),
                        (sx + 4, sy + 14 + wave_off),
                        (sx + 28, sy + 14 + wave_off),
                        2,
                    )

                # Mountain
                if tid == MOUNTAIN:
                    # Dark craggy peak
                    pygame.draw.polygon(
                        screen,
                        (110, 100, 90),
                        [
                            (sx + 4, sy + TILE),
                            (sx + 16, sy + 2),
                            (sx + TILE - 4, sy + TILE),
                        ],
                    )
                    # Snow cap
                    pygame.draw.polygon(
                        screen,
                        (230, 230, 240),
                        [(sx + 12, sy + 8), (sx + 16, sy + 2), (sx + 20, sy + 8)],
                    )
                    # Cracks / texture lines
                    pygame.draw.line(
                        screen, (70, 65, 60), (sx + 10, sy + 18), (sx + 14, sy + 12), 1
                    )
                    pygame.draw.line(
                        screen, (70, 65, 60), (sx + 20, sy + 20), (sx + 22, sy + 14), 1
                    )

                # House
                if tid == HOUSE:
                    # Walls
                    pygame.draw.rect(screen, (180, 120, 60), (sx + 4, sy + 12, 24, 18))
                    # Roof
                    pygame.draw.polygon(
                        screen,
                        (160, 40, 40),
                        [(sx + 2, sy + 12), (sx + 16, sy + 2), (sx + 30, sy + 12)],
                    )
                    # Door
                    pygame.draw.rect(screen, (100, 60, 30), (sx + 12, sy + 19, 8, 11))
                    # Window
                    pygame.draw.rect(screen, (180, 220, 255), (sx + 7, sy + 15, 5, 5))
                    pygame.draw.rect(screen, (80, 60, 40), (sx + 7, sy + 15, 5, 5), 1)

        # Mining progress bar
        if mining_target:
            mc, mr = mining_target
            info = TILE_INFO[world[mr][mc]]
            max_hp = info["hp"]
            if max_hp > 0:
                current = tile_hp[mr][mc]
                ratio = 1 - current / max_hp
                bx = mc * TILE - int(cam_x)
                by = mr * TILE - int(cam_y) - 8
                pygame.draw.rect(screen, (60, 60, 60), (bx, by, TILE, 5))
                pygame.draw.rect(screen, (50, 220, 50), (bx, by, int(TILE * ratio), 5))

        # Particles
        for p in particles:
            p.draw(screen, cam_x, cam_y)

        # Floating text
        for f in floats:
            f.draw(screen, font, cam_x, cam_y)

        # Workers
        for w in workers:
            w.draw(screen, cam_x, cam_y)

        # Pets
        ticks = pygame.time.get_ticks()
        for pet in pets:
            pet.draw(screen, cam_x, cam_y, ticks)

        # Enemies
        for enemy in enemies:
            enemy.draw(screen, cam_x, cam_y)

        # Projectiles
        for proj in projectiles:
            proj.draw(screen, cam_x, cam_y)

        # Player
        psx = int(px - cam_x)
        psy = int(py - cam_y)
        # Body (flashes red when hurt)
        body_color = (
            (230, 80, 80)
            if player_hurt_timer > 0 and int(player_hurt_timer * 4) % 2
            else (70, 130, 230)
        )
        pygame.draw.rect(
            screen, body_color, (psx - 10, psy - 14, 20, 28), border_radius=4
        )
        # Head
        pygame.draw.circle(screen, (240, 200, 160), (psx, psy - 18), 8)
        # Pick icon
        pick_color = PICKAXES[pick_level]["color"]
        pygame.draw.line(
            screen, pick_color, (psx + 10, psy - 8), (psx + 18, psy - 16), 3
        )
        pygame.draw.line(
            screen, pick_color, (psx + 15, psy - 19), (psx + 21, psy - 13), 3
        )

        # --- HUD ----------------------------------------------------------
        # Inventory panel
        panel_w = 220
        panel_h = 20 + max(1, len(inventory)) * 20 + 200
        panel_surf = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel_surf.fill((20, 20, 30, 180))
        screen.blit(panel_surf, (10, 10))

        # Player HP bar
        hp_ratio = max(0, player_hp / player_max_hp)
        hp_bar_w = 200
        pygame.draw.rect(screen, (60, 60, 60), (16, 16, hp_bar_w, 10))
        bar_col = (
            (50, 200, 50)
            if hp_ratio > 0.5
            else (220, 180, 30) if hp_ratio > 0.25 else (220, 40, 40)
        )
        pygame.draw.rect(screen, bar_col, (16, 16, int(hp_bar_w * hp_ratio), 10))
        hp_text = font.render(f"HP: {player_hp:.0f}/{player_max_hp}", True, WHITE)
        screen.blit(hp_text, (16, 28))

        # XP bar
        xp_ratio = player_xp / player_xp_next if player_xp_next > 0 else 0
        xp_bar_w = 200
        pygame.draw.rect(screen, (60, 60, 60), (16, 44, xp_bar_w, 8))
        pygame.draw.rect(screen, (80, 180, 255), (16, 44, int(xp_bar_w * xp_ratio), 8))
        xp_text = font.render(
            f"Lv {player_level}  XP: {player_xp}/{player_xp_next}",
            True,
            (180, 220, 255),
        )
        screen.blit(xp_text, (16, 54))

        # Pickaxe info
        pick = PICKAXES[pick_level]
        pygame.draw.rect(screen, pick["color"], (16, 74, 12, 12))
        screen.blit(font.render(pick["name"], True, WHITE), (34, 72))

        # Inventory items
        y_off = 96
        if inventory:
            for item_name, count in sorted(inventory.items()):
                info_color = WHITE
                for tid, tinfo in TILE_INFO.items():
                    if tinfo["drop"] == item_name and tinfo["drop_color"]:
                        info_color = tinfo["drop_color"]
                        break
                pygame.draw.rect(screen, info_color, (18, y_off + 2, 8, 8))
                screen.blit(
                    font.render(f"{item_name}: {count}", True, WHITE), (34, y_off)
                )
                y_off += 20
        else:
            screen.blit(font.render("(empty)", True, (150, 150, 150)), (34, y_off))
            y_off += 20

        # Upgrade hint
        y_off += 6
        if pick_level < len(PICKAXES) - 1:
            cost = UPGRADE_COSTS[pick_level]
            cost_str = ", ".join(f"{v} {k}" for k, v in cost.items())
            can = all(inventory.get(k, 0) >= v for k, v in cost.items())
            color = (100, 255, 100) if can else (180, 180, 180)
            screen.blit(
                font.render(f"[U] Upgrade: {cost_str}", True, color), (18, y_off)
            )
        else:
            screen.blit(
                font.render("Pick is MAX level!", True, (255, 215, 0)), (18, y_off)
            )
        y_off += 20

        # Build house hint
        can_build = inventory.get("Dirt", 0) >= 20
        build_color = (100, 255, 100) if can_build else (180, 180, 180)
        screen.blit(
            font.render("[B] Build House: 20 Dirt", True, build_color), (18, y_off)
        )
        y_off += 20

        # Weapon info
        wpn = WEAPONS[weapon_level]
        pygame.draw.rect(screen, wpn["color"], (18, y_off + 2, 8, 8))
        screen.blit(font.render(f"[F/RClick] {wpn['name']}", True, WHITE), (34, y_off))
        y_off += 20
        if weapon_level < len(WEAPONS) - 1:
            wcost = WEAPON_UNLOCK_COSTS[weapon_level]
            wcost_str = ", ".join(f"{v} {k}" for k, v in wcost.items())
            wcan = all(inventory.get(k, 0) >= v for k, v in wcost.items())
            wcolor = (100, 255, 100) if wcan else (180, 180, 180)
            screen.blit(
                font.render(f"[N] Next Weapon: {wcost_str}", True, wcolor), (18, y_off)
            )
        else:
            screen.blit(
                font.render("Weapon is MAX level!", True, (255, 215, 0)), (18, y_off)
            )
        y_off += 20

        # Worker & pet count
        if workers:
            screen.blit(
                font.render(f"Workers: {len(workers)}", True, (100, 220, 255)),
                (18, y_off),
            )
            y_off += 20
        num_cats = sum(1 for p in pets if p.kind == "cat")
        num_dogs = sum(1 for p in pets if p.kind == "dog")
        if num_cats or num_dogs:
            pet_parts = []
            if num_cats:
                pet_parts.append(f"Cats: {num_cats}")
            if num_dogs:
                pet_parts.append(f"Dogs: {num_dogs}")
            screen.blit(
                font.render("  ".join(pet_parts), True, (255, 200, 100)), (18, y_off)
            )

        # Controls hint (bottom)
        hint = "WASD: Move | Click/Space: Mine | F/RClick: Attack | U/N: Upgrade | B: Build"
        hint_surf = font.render(hint, True, (180, 180, 180))
        screen.blit(
            hint_surf, (SCREEN_W // 2 - hint_surf.get_width() // 2, SCREEN_H - 26)
        )

        # Tile tooltip on hover
        mx, my = pygame.mouse.get_pos()
        hover_col = int((mx + cam_x) // TILE)
        hover_row = int((my + cam_y) // TILE)
        if 0 <= hover_col < WORLD_COLS and 0 <= hover_row < WORLD_ROWS:
            tid = world[hover_row][hover_col]
            info = TILE_INFO[tid]
            tip = info["name"]
            if info["mineable"]:
                tip += f"  (HP: {tile_hp[hover_row][hover_col]:.0f}/{info['hp']})"
            tip_surf = font.render(tip, True, WHITE)
            tip_bg = pygame.Surface(
                (tip_surf.get_width() + 10, tip_surf.get_height() + 6), pygame.SRCALPHA
            )
            tip_bg.fill((0, 0, 0, 160))
            screen.blit(tip_bg, (mx + 14, my + 2))
            screen.blit(tip_surf, (mx + 19, my + 5))

        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
