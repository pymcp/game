# Mining Game - Modular Architecture

This is a fully modularized version of the mining game, organized into logical packages and modules.

## Directory Structure

```
game/
├── main.py                 # Entry point: imports Game and runs it
├── src/
│   ├── __init__.py        # Package marker
│   ├── config.py          # Global constants (screen, tile types, colors)
│   ├── game.py            # Game class (main loop, orchestration)
│   │
│   ├── data/              # Game data (weapons, enemies, pickaxes, tiles)
│   │   ├── __init__.py
│   │   ├── tiles.py       # Tile definitions and properties
│   │   ├── pickaxes.py    # Pickaxe tiers and upgrade costs
│   │   ├── weapons.py     # Weapon definitions and costs
│   │   └── enemies.py     # Enemy type definitions (data-driven)
│   │
│   ├── world/             # World generation and collision
│   │   ├── __init__.py
│   │   ├── collision.py   # Collision helpers, tile queries, physics
│   │   └── generation.py  # World generation and enemy spawning
│   │
│   ├── entities/          # Game entities (player, enemies, AI, pets)
│   │   ├── __init__.py
│   │   ├── player.py      # Player class (movement, mining, combat)
│   │   ├── enemy.py       # Enemy class (data-driven, vector rendering)
│   │   ├── worker.py      # Worker AI (pathfinding, mining FSM)
│   │   ├── pet.py         # Pet class (cats/dogs that follow player)
│   │   └── projectile.py  # Projectile class (weapons, hit detection)
│   │
│   ├── effects/           # Visual effects
│   │   ├── __init__.py
│   │   ├── particle.py    # Particle class (gravity, decay)
│   │   └── floating_text.py  # FloatingText class (damage/item popups)
│   │
│   └── ui/                # User interface
│       ├── __init__.py
│       └── hud.py         # HUD rendering (inventory, stats, controls)
```

## Key Benefits

### **Maintainability**
- Each system is in its own module (player, enemies, world, etc.)
- Easy to find and modify specific functionality
- Clear dependencies between modules

### **Extensibility**
- Add new weapons: append to `WEAPONS` list in `src/data/weapons.py`
- Add new enemies: append to `ENEMY_TYPES` dict in `src/data/enemies.py`
- Add new tiles: add to `TILE_INFO` in `src/data/tiles.py`
- No need to modify core game loop

### **Performance**
- Collision helpers defined once, not recreated every frame
- Efficient imports with `__init__.py` aggregation
- Clean module boundaries reduce overhead

### **Testability**
- Each module can be imported and tested independently
- Easy to mock dependencies for unit testing
- Separation of concerns enables isolated testing

## Running the Game

```bash
cd /home/mpatterson/repos/game
source .venv/bin/activate
python main.py
```

## Module Dependencies

```
main.py
  └→ src.game
      ├→ src.config
      ├→ src.data (tiles, pickaxes, weapons, enemies)
      ├→ src.world (generation, collision)
      ├→ src.entities (player, enemy, worker, pet, projectile)
      ├→ src.effects (particle, floating_text)
      └→ src.ui (hud)
```

## Migration from Monolithic

The 1451-line `main.py` was split into:
- **src/config.py** (24 lines) - Constants
- **src/data/** (200+ lines) - Game data dictionaries
- **src/world/** (150+ lines) - World generation & collision
- **src/entities/** (600+ lines) - Player, enemies, workers, pets, projectiles
- **src/effects/** (60 lines) - Particles and floating text
- **src/ui/** (150+ lines) - HUD and tooltips
- **src/game.py** (200+ lines) - Game orchestration

## Quick Adds

### Add a new weapon:
```python
# In src/data/weapons.py, append to WEAPONS:
{
    "name": "Fireball",
    "damage": 35,
    "distance": TILE * 10,
    "speed": 4.0,
    "cooldown": 50,
    "size": 8,
    "color": (255, 100, 0),
    "pierce": True,
    "knockback": 8,
    "draw": ("circle",),
}
```

### Add a new enemy type:
```python
# In src/data/enemies.py, append to ENEMY_TYPES:
"goblin": {
    "maximum": 8,
    "xp": 15,
    "name": "Goblin",
    "color": (100, 150, 50),
    "hp": 25,
    "attack": 4,
    "speed": 2.0,
    "attack_cd": 30,
    "chase_range": 0,
    "draw_commands": [
        ("rect", (0, 0, 0), -8, -10, 16, 18),
        ("circle", (-100, -50, -50), -3, -5, 2),
    ],
}
```

Then update `WEAPON_UNLOCK_COSTS` or `ENEMY_TYPES["goblin"]["maximum"]` as needed.

## Old Files

- `main_old.py` - Original refactored monolithic version (1451 lines)
- `main.py.bak` - Original pre-refactor version (auto-generated backup)

These are preserved for reference but not needed.
