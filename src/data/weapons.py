"""Weapon definitions and unlock costs."""

from src.config import TILE

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
