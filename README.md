# Mining Game - Modular Edition

A fully modularized mining/crafting/adventure game built with Python and Pygame.

## Quick Start

```bash
cd /home/mpatterson/repos/game
source .venv/bin/activate
python main.py
```

## File Structure (Organized)

```
game/
├── main.py                      ← Entry point (simple 14-line file)
├── ARCHITECTURE.md              ← Detailed technical documentation
├── MODULARIZATION_SUMMARY.md    ← Summary of changes
├── README.md                    ← This file
│
└── src/                         ← Game source code (organized by domain)
    ├── __init__.py
    ├── config.py                ← Global constants & configuration
    ├── game.py                  ← Game class (main loop, orchestration)
    │
    ├── data/                    ← Game content (data-driven)
    │   ├── tiles.py             ─ Tile definitions
    │   ├── pickaxes.py          ─ Mining tools & upgrades
    │   ├── weapons.py           ─ Combat weapons
    │   └── enemies.py           ─ Enemy types (reusable definitions)
    │
    ├── world/                   ← World management
    │   ├── collision.py         ─ Collision, pathfinding, physics
    │   └── generation.py        ─ Procedural world & enemy spawning
    │
    ├── entities/                ← Game characters & objects
    │   ├── player.py            ─ Player character
    │   ├── enemy.py             ─ Enemy entities
    │   ├── worker.py            ─ AI workers (mining FSM)
    │   ├── pet.py               ─ Pet companions (cats/dogs)
    │   └── projectile.py        ─ Weapons & projectiles
    │
    ├── effects/                 ← Visual feedback
    │   ├── particle.py          ─ Particle system
    │   └── floating_text.py     ─ Damage/item popups
    │
    └── ui/                      ← User Interface
        └── hud.py               ─ HUD rendering (inventory, stats)
```

## What Changed

### Before
- **1 file**: `main.py` (1451 lines)
- Hard to navigate
- Functions mixed with classes
- Constants scattered everywhere
- Difficult to extend

### After
- **22 organized files** in 6 logical packages
- Clear, focused modules
- Constants centralized
- Data-driven design
- Easy to add new content

## Game Features

✓ **Mining System** - 5 pickaxe tiers, 10 tile types  
✓ **Commerce** - Crafting, inventory management, upgrades  
✓ **Leveling** - XP system with exponential curve  
✓ **Combat** - 3 weapons, projectiles, pierce/knockback  
✓ **Enemies** - Data-driven types (slime, blocker, boss)  
✓ **AI** - Worker mining, pet following, enemy combat  
✓ **Terrain** - Procedural generation, biomes  
✓ **Graphics** - Vector drawing, particles, animations  

## Adding Content (Easy!)

### New Weapon
Edit `src/data/weapons.py` → append to `WEAPONS` list. Done!

### New Enemy Type
Edit `src/data/enemies.py` → append to `ENEMY_TYPES` dict. Done!

### New Tile Type
Edit `src/data/tiles.py` → append to `TILE_INFO` dict. Done!

See `ARCHITECTURE.md` for code examples.

## Documentation

- **MODULARIZATION_SUMMARY.md** - What changed and why
- **ARCHITECTURE.md** - Technical details, dependency graph, guides

## Original Files (Reference)

- `main_old.py` - Previous 1451-line monolithic version
- `main.py.bak` - Pre-refactor backup

These can be safely deleted or kept for reference.

## Key Improvements

| Before | After |
|--------|-------|
| 1 file, 1451 lines | 22 files, organized by purpose |
| Hard to find code | Each system in own module |
| Limited extensibility | Data-driven design |
| Difficult testing | Modular, testable structure |
| Monolithic game class | Separated concerns |

## Technical Stack

- **Python 3.12.3**
- **Pygame 2.6.1**
- **SDL 2.28.4**

## Development

All modules are fully importable and can be used independently:

```python
from src.entities import Player, Enemy
from src.world import generate_world, xp_for_level
from src.data import WEAPONS, ENEMY_TYPES
```

Perfect for unit testing, interactive exploration, or building tools!

---

**Status**: ✓ Fully Functional | ✓ Syntax Validated | ✓ Tested
