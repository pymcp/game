"""Enemy type definitions.

Each enemy type is a dict with:
   name        – display name
   color       – primary RGB color
   hp          – max hit-points
   attack      – damage dealt per hit to the player
   speed       – movement speed (world-units per normalised frame)
   attack_cd   – cooldown between attacks in normalised frames
   chase_range – pixel distance at which enemy starts chasing (0 = viewport)
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
        "chase_range": 0,
        "draw_commands": [
            ("ellipse", (0, 0, 0),       -10, -4, 20, 14),
            ("ellipse", (40, 40, 40),     -6, -2, 8, 6),
            ("circle",  (-80, -80, -80),  -4, -6, 2),
            ("circle",  (-80, -80, -80),   4, -6, 2),
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
            ("rect", (0, 0, 0), -10, -10, 20, 20),
            ("circle", (-180, -25, -25), -4, -4, 2),
            ("circle", (-180, -25, -25),  4, -4, 2),
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
            ("polygon", (0, 0, 0), [(-12, -10), (0, -14), (12, -10), (10, 10), (-10, 10)]),
        ],
    },
}
