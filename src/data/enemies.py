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
}
