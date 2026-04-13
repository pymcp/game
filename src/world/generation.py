"""World generation and enemy spawning."""
import random
import math
from src.config import WORLD_COLS, WORLD_ROWS, TILE, GRASS, DIRT, STONE, WATER, TREE, IRON_ORE, GOLD_ORE, DIAMOND_ORE, MOUNTAIN
from src.data import ENEMY_TYPES


def generate_world():
    """Return a 2-D list of tile-type IDs using simple noise-like placement."""
    world = [[GRASS for _ in range(WORLD_COLS)] for _ in range(WORLD_ROWS)]

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
    scatter(MOUNTAIN, 30, 6, 18)

    return world


def spawn_enemies(world):
    """Scatter enemies on walkable tiles throughout the world."""
    from src.entities import Enemy
    
    enemies = []
    spawn_count = {}
    for _ in range(25):
        for attempt in range(20):
            col = random.randint(2, WORLD_COLS - 3)
            row = random.randint(2, WORLD_ROWS - 3)
            if world[row][col] == GRASS:
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
