"""Enemy type definitions.

Each enemy type is a dict with:
   name        – display name
   color       – primary RGB color
   hp          – max hit-points
   attack      – damage dealt per hit to the player
   speed       – movement speed (world-units per normalised frame)
   attack_cd   – cooldown between attacks in normalised frames
   chase_range – pixel distance at which enemy starts chasing (0 = viewport)
   environments – list of EnemyEnvironment values indicating where this enemy spawns
   draw_commands – list of vector draw instructions executed relative to
                   the enemy's screen position (sx, sy).  Each entry is a
                   tuple:  (shape, color_offset, *args)
       shape = "circle"  -> (cx_off, cy_off, radius)
       shape = "rect"    -> (x_off, y_off, w, h)
       shape = "ellipse" -> (x_off, y_off, w, h)
       shape = "line"    -> (x1_off, y1_off, x2_off, y2_off, width)
       shape = "polygon" -> ([(x_off, y_off), ...],)
   color_offset is added per-channel to the type's base color (clamped 0-255).
"""

from enum import Enum


class EnemyEnvironment(Enum):
    OVERLAND = "overland"
    CAVE_MOUNTAIN = "cave_mountain"
    CAVE_HILL = "cave_hill"
    PORTAL_GUARDIAN = "portal_guardian"
    TUNDRA = "tundra"
    VOLCANO = "volcano"
    ZOMBIE = "zombie"
    DESERT = "desert"


class PortalQuestType(Enum):
    RITUAL = "ritual"
    GATHER = "gather"
    COMBAT = "combat"


ENEMY_TYPES = {
    "slime": {
        "environments": [EnemyEnvironment.OVERLAND],
        "maximum": 1,
        "xp": 10,
        "name": "Slime",
        "color": (50, 180, 50),
        "hp": 30,
        "attack": 5,
        "speed": 1.2,
        "attack_cd": 40,
        "chase_range": 0,
        "draw_commands": [
            ("ellipse", (0, 0, 0), -10, -4, 20, 14),
            ("ellipse", (40, 40, 40), -6, -2, 8, 6),
            ("circle", (-80, -80, -80), -4, -6, 2),
            ("circle", (-80, -80, -80), 4, -6, 2),
        ],
    },
    "blocker": {
        "environments": [EnemyEnvironment.OVERLAND],
        "maximum": 1,
        "xp": 10,
        "name": "Blocker",
        "color": (180, 25, 25),
        "hp": 30,
        "attack": 5,
        "speed": 0.8,
        "attack_cd": 2,
        "chase_range": 0,
        "draw_commands": [
            ("rect", (0, 0, 0), -10, -10, 20, 20),
            ("circle", (-180, -25, -25), -4, -4, 2),
            ("circle", (-180, -25, -25), 4, -4, 2),
        ],
    },
    "boss": {
        "environments": [EnemyEnvironment.OVERLAND],
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
            (
                "polygon",
                (0, 0, 0),
                [(-12, -10), (0, -14), (12, -10), (10, 10), (-10, 10)],
            ),
        ],
    },
    # -- Mountain cave enemies --
    "bat": {
        "environments": [EnemyEnvironment.CAVE_MOUNTAIN],
        "maximum": 8,
        "xp": 8,
        "name": "Bat",
        "color": (90, 55, 120),
        "hp": 15,
        "attack": 4,
        "speed": 2.8,
        "attack_cd": 25,
        "chase_range": 0,
        "draw_commands": [
            ("ellipse", (0, 0, 0), -7, -5, 14, 10),
            ("ellipse", (-30, -20, -20), -20, -9, 14, 9),
            ("ellipse", (-30, -20, -20), 6, -9, 14, 9),
            ("circle", (-60, -40, -60), -3, -7, 2),
            ("circle", (-60, -40, -60), 3, -7, 2),
        ],
    },
    "cave_troll": {
        "environments": [EnemyEnvironment.CAVE_MOUNTAIN],
        "maximum": 3,
        "xp": 35,
        "name": "Cave Troll",
        "color": (90, 115, 75),
        "hp": 90,
        "attack": 20,
        "speed": 0.85,
        "attack_cd": 60,
        "chase_range": 0,
        "draw_commands": [
            ("ellipse", (0, 0, 0), -14, -6, 28, 20),
            ("circle", (15, 15, 5), 0, -18, 10),
            ("rect", (-25, -15, -10), -18, -6, 7, 12),
            ("rect", (-25, -15, -10), 11, -6, 7, 12),
            ("circle", (-70, -70, -50), -4, -18, 2),
            ("circle", (-70, -70, -50), 4, -18, 2),
        ],
    },
    # -- Hill cave enemies --
    "goblin": {
        "environments": [EnemyEnvironment.CAVE_HILL],
        "maximum": 6,
        "xp": 12,
        "name": "Goblin",
        "color": (75, 155, 55),
        "hp": 25,
        "attack": 7,
        "speed": 2.1,
        "attack_cd": 30,
        "chase_range": 0,
        "draw_commands": [
            ("rect", (0, 0, 0), -7, -7, 14, 14),
            ("circle", (20, 20, -10), 0, -16, 7),
            ("circle", (-70, -70, -70), -3, -16, 2),
            ("circle", (-70, -70, -70), 3, -16, 2),
            ("polygon", (-20, -40, -20), [(-4, -20), (0, -26), (4, -20)]),
        ],
    },
    "cave_spider": {
        "environments": [EnemyEnvironment.CAVE_HILL],
        "maximum": 5,
        "xp": 15,
        "name": "Cave Spider",
        "color": (55, 35, 75),
        "hp": 20,
        "attack": 10,
        "speed": 1.9,
        "attack_cd": 20,
        "chase_range": 0,
        "draw_commands": [
            ("ellipse", (0, 0, 0), -9, -7, 18, 14),
            ("line", (-30, -20, -20), -9, -3, -20, -10, 2),
            ("line", (-30, -20, -20), -9, 1, -21, 1, 2),
            ("line", (-30, -20, -20), -9, 5, -20, 10, 2),
            ("line", (-30, -20, -20), 9, -3, 20, -10, 2),
            ("line", (-30, -20, -20), 9, 1, 21, 1, 2),
            ("line", (-30, -20, -20), 9, 5, 20, 10, 2),
            ("circle", (-40, -20, -40), -3, -8, 2),
            ("circle", (-40, -20, -40), 3, -8, 2),
        ],
    },
    "stone_sentinel": {
        "environments": [EnemyEnvironment.PORTAL_GUARDIAN],
        "maximum": 1,
        "xp": 50,
        "name": "Stone Sentinel",
        "color": (100, 90, 110),
        "hp": 120,
        "attack": 18,
        "speed": 0.7,
        "attack_cd": 80,
        "chase_range": 200,
        "draw_commands": [
            # Body — wide stone torso
            ("rect", (0, 0, 0), -14, -8, 28, 22),
            # Head — square, slightly lighter
            ("rect", (20, 18, 25), -9, -22, 18, 16),
            # Left arm — thick stone slab
            ("rect", (-15, -12, -18), -24, -6, 10, 18),
            # Right arm
            ("rect", (-15, -12, -18), 14, -6, 10, 18),
            # Glowing eye slots
            ("rect", (-100, -90, 100), -7, -18, 5, 4),
            ("rect", (-100, -90, 100), 2, -18, 5, 4),
            # Crack lines on body
            ("line", (-30, -25, -30), -5, -6, -2, 8, 1),
            ("line", (-30, -25, -30), 3, -4, 6, 10, 1),
        ],
    },
    # --- Tundra biome enemies ---
    "ice_golem": {
        "environments": [EnemyEnvironment.TUNDRA],
        "maximum": 3,
        "xp": 25,
        "name": "Ice Golem",
        "color": (140, 190, 230),
        "hp": 100,
        "attack": 15,
        "speed": 0.8,
        "attack_cd": 70,
        "chase_range": 0,
        "draw_commands": [
            ("rect", (0, 0, 0), -12, -8, 24, 20),
            ("rect", (15, 20, 25), -8, -22, 16, 16),
            ("rect", (-10, -15, -20), -22, -4, 10, 16),
            ("rect", (-10, -15, -20), 12, -4, 10, 16),
            ("circle", (-140, -190, -230), -4, -16, 3),
            ("circle", (-140, -190, -230), 4, -16, 3),
        ],
    },
    "frost_wolf": {
        "environments": [EnemyEnvironment.TUNDRA],
        "maximum": 4,
        "xp": 15,
        "name": "Frost Wolf",
        "color": (200, 225, 255),
        "hp": 45,
        "attack": 10,
        "speed": 2.2,
        "attack_cd": 35,
        "chase_range": 0,
        "draw_commands": [
            ("ellipse", (0, 0, 0), -10, -4, 22, 12),
            ("ellipse", (-10, -10, -10), -6, -14, 10, 10),
            ("circle", (-200, -225, -255), -3, -12, 2),
            ("circle", (-200, -225, -255), 3, -12, 2),
            ("rect", (0, 0, 0), 8, -2, 6, 4),
        ],
    },
    # --- Volcano biome enemies ---
    "fire_imp": {
        "environments": [EnemyEnvironment.VOLCANO],
        "maximum": 4,
        "xp": 15,
        "name": "Fire Imp",
        "color": (230, 80, 20),
        "hp": 40,
        "attack": 12,
        "speed": 2.0,
        "attack_cd": 30,
        "chase_range": 0,
        "draw_commands": [
            ("ellipse", (0, 0, 0), -7, -4, 14, 12),
            ("circle", (0, 10, 0), -1, -14, 6),
            ("circle", (-230, -80, -20), -3, -12, 2),
            ("circle", (-230, -80, -20), 3, -12, 2),
            ("polygon", (25, 100, 0), [(-5, -16), (0, -24), (5, -16)]),
        ],
    },
    "lava_troll": {
        "environments": [EnemyEnvironment.VOLCANO],
        "maximum": 3,
        "xp": 30,
        "name": "Lava Troll",
        "color": (90, 35, 20),
        "hp": 120,
        "attack": 20,
        "speed": 0.7,
        "attack_cd": 75,
        "chase_range": 0,
        "draw_commands": [
            ("rect", (0, 0, 0), -14, -6, 28, 22),
            ("rect", (10, 5, 5), -10, -22, 20, 18),
            ("rect", (-5, -5, -5), -24, -4, 10, 18),
            ("rect", (-5, -5, -5), 14, -4, 10, 18),
            ("circle", (130, 120, 60), -4, -14, 3),
            ("circle", (130, 120, 60), 4, -14, 3),
        ],
    },
    # --- Zombie / Ruins biome enemies ---
    "zombie": {
        "environments": [EnemyEnvironment.ZOMBIE],
        "maximum": 5,
        "xp": 12,
        "name": "Zombie",
        "color": (80, 105, 65),
        "hp": 50,
        "attack": 8,
        "speed": 0.9,
        "attack_cd": 50,
        "chase_range": 0,
        "draw_commands": [
            ("rect", (0, 0, 0), -8, -4, 16, 20),
            ("ellipse", (5, 5, 5), -7, -18, 14, 14),
            ("circle", (-80, -105, -65), -3, -14, 2),
            ("circle", (-80, -105, -65), 3, -14, 2),
            ("rect", (10, 10, 10), -14, -2, 6, 12),
            ("rect", (10, 10, 10), 8, -2, 6, 12),
        ],
    },
    "skeleton": {
        "environments": [EnemyEnvironment.ZOMBIE],
        "maximum": 4,
        "xp": 12,
        "name": "Skeleton",
        "color": (190, 185, 175),
        "hp": 30,
        "attack": 12,
        "speed": 1.4,
        "attack_cd": 40,
        "chase_range": 0,
        "draw_commands": [
            ("rect", (0, 0, 0), -6, -4, 12, 18),
            ("ellipse", (5, 5, 10), -6, -18, 12, 14),
            ("circle", (-190, -185, -175), -2, -14, 2),
            ("circle", (-190, -185, -175), 2, -14, 2),
            ("rect", (-10, -10, -10), -12, -2, 4, 14),
            ("rect", (-10, -10, -10), 8, -2, 4, 14),
        ],
    },
    # --- Desert biome enemies ---
    "sand_scorpion": {
        "environments": [EnemyEnvironment.DESERT],
        "maximum": 4,
        "xp": 18,
        "name": "Sand Scorpion",
        "color": (180, 150, 70),
        "hp": 55,
        "attack": 10,
        "speed": 1.5,
        "attack_cd": 45,
        "chase_range": 0,
        "draw_commands": [
            ("ellipse", (0, 0, 0), -10, -3, 20, 12),
            ("ellipse", (5, 5, 5), -5, -14, 10, 11),
            ("rect", (-20, -20, -20), -18, -4, 8, 4),
            ("rect", (-20, -20, -20), 10, -4, 8, 4),
            ("rect", (-20, -20, -20), -16, -8, 6, 4),
            ("rect", (-20, -20, -20), 10, -8, 6, 4),
            ("rect", (40, 30, 0), 8, -22, 4, 10),
        ],
    },
    "desert_bandit": {
        "environments": [EnemyEnvironment.DESERT],
        "maximum": 4,
        "xp": 18,
        "name": "Desert Bandit",
        "color": (160, 120, 70),
        "hp": 45,
        "attack": 14,
        "speed": 1.9,
        "attack_cd": 35,
        "chase_range": 0,
        "draw_commands": [
            ("rect", (0, 0, 0), -8, -4, 16, 20),
            ("ellipse", (5, 5, 5), -7, -18, 14, 14),
            ("circle", (-160, -120, -70), -3, -14, 2),
            ("circle", (-160, -120, -70), 3, -14, 2),
            ("rect", (-40, -20, 10), -10, -22, 20, 6),
            ("rect", (30, 20, 0), 12, -2, 4, 14),
        ],
    },
}
