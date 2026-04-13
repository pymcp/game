"""Bake procedural entity art into PNG sprite sheets.

Run from the repository root::

    python tools/bake_sprites.py

Generates unified 7-row × 4-column, 96×96-cell sprite sheets (384×672 px)
for every enemy type, creature kind, pet kind, and worker.

Sheet row layout (all entity types share this format):
  row 0 – idle      (4 frames @ 4 fps)
  row 1 – up        (4 frames @ 8 fps)
  row 2 – right     (4 frames @ 8 fps)
  row 3 – down      (4 frames @ 8 fps)
  row 4 – left      (4 frames @ 8 fps) ← blank → engine auto-mirrors right
  row 5 – attacking (4 frames @ 8 fps) ← blank for non-combat → falls back to idle
  row 6 – damaged   (4 frames @ 4 fps)

These sheets are PLACEHOLDER art baked from the existing procedural draw code.
Replace any sheet PNG with hand-drawn or AI-generated art (keeping the same
384×672 dimensions and matching JSON manifest) and the game will use it
automatically at next startup.
"""

import json
import math
import os
import sys

# ---------------------------------------------------------------------------
# Headless pygame initialisation (must happen before any game imports)
# ---------------------------------------------------------------------------
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

pygame.init()
pygame.display.set_mode((1, 1))

# Now it is safe to import game modules.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data import ENEMY_TYPES  # noqa: E402
from src.entities.enemy import Enemy  # noqa: E402
from src.entities.overland_creature import OverlandCreature  # noqa: E402
from src.entities.pet import Pet  # noqa: E402
from src.entities.sea_creature import SeaCreature  # noqa: E402
from src.entities.worker import Worker  # noqa: E402

# ---------------------------------------------------------------------------
# Output directory
# ---------------------------------------------------------------------------
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS_DIR = os.path.join(_REPO_ROOT, "assets", "sprites")

# ---------------------------------------------------------------------------
# Unified cell dimensions — all entity sprites share this canvas size.
# ---------------------------------------------------------------------------
FW: int = 96   # frame width  (pixels)
FH: int = 96   # frame height (pixels)
CX: int = 48   # draw centre X within a cell
CY: int = 48   # draw centre Y within a cell

# Standard manifest template — identical for every entity type.
# Row 4 (left) is intentionally absent from the JSON when blank so the
# Animator's auto-flip logic kicks in.
_STANDARD_STATES: list[tuple[str, int, int, float]] = [
    # (name,  row, frames, fps)
    ("idle",      0, 4, 3.0),
    ("up",        1, 4, 6.0),
    ("right",     2, 4, 6.0),
    ("down",      3, 4, 6.0),
    # row 4 (left) omitted here → added only when explicit art is generated
    ("attacking", 5, 4, 6.0),
    ("damaged",   6, 4, 3.0),
]


def _standard_manifest(include_left: bool = False) -> dict:
    """Build the unified 7-row manifest dict.

    Args:
        include_left: When True, the manifest includes an explicit left row (row 4).
                      When False (default), the engine auto-mirrors right frames.
    """
    states: dict[str, dict] = {}
    for name, row, frames, fps in _STANDARD_STATES:
        states[name] = {"row": row, "frames": frames, "fps": fps}
    if include_left:
        states["left"] = {"row": 4, "frames": 4, "fps": 6.0}
    return {"frame_size": [FW, FH], "states": states}


def _ticks_seq(period_ms: float, n_frames: int) -> list[int]:
    """Return *n_frames* evenly-spaced ticks values across one full period."""
    return [int(i / n_frames * period_ms) for i in range(n_frames)]


# ---------------------------------------------------------------------------
# Surface helpers
# ---------------------------------------------------------------------------


def _blank() -> pygame.Surface:
    """Return a transparent 96×96 RGBA surface."""
    surf = pygame.Surface((FW, FH), pygame.SRCALPHA)
    surf.fill((0, 0, 0, 0))
    return surf


def _blank_row() -> list[pygame.Surface]:
    """Return 4 blank (fully transparent) frames."""
    return [_blank() for _ in range(4)]


def _pack_sheet(rows: list[list[pygame.Surface]]) -> pygame.Surface:
    """Pack *rows* of exactly 4 frames into a 384×(FH*7) sprite sheet.

    Rows that are None or missing are left transparent.
    """
    n_rows = 7
    n_cols = 4
    sheet = pygame.Surface((FW * n_cols, FH * n_rows), pygame.SRCALPHA)
    sheet.fill((0, 0, 0, 0))
    for ri, row in enumerate(rows):
        if row is None:
            continue
        for ci, frame in enumerate(row[:n_cols]):
            sheet.blit(frame, (ci * FW, ri * FH))
    return sheet


def _save(name: str, sub_dir: str, sheet: pygame.Surface, manifest: dict) -> None:
    """Write the sheet PNG and companion JSON manifest."""
    out_dir = os.path.join(ASSETS_DIR, sub_dir)
    os.makedirs(out_dir, exist_ok=True)
    png_path = os.path.join(out_dir, f"{name}.png")
    json_path = os.path.join(out_dir, f"{name}.json")
    pygame.image.save(sheet, png_path)
    with open(json_path, "w") as fh:
        json.dump(manifest, fh, indent=2)
    w, h = sheet.get_size()
    print(f"  {sub_dir}/{name}.png  ({w}×{h})")


# ---------------------------------------------------------------------------
# Baking helpers (per entity class)
# ---------------------------------------------------------------------------


def _bake_enemy(type_key: str) -> None:
    """Bake a single enemy type into enemies/<type_key>.png (384×672)."""
    e = Enemy(0.0, 0.0, type_key)
    cam_x = e.x - CX
    cam_y = e.y - CY

    # idle: 4 frames with gently offset ticks to capture any idle sway
    idle_row: list[pygame.Surface] = []
    for t in _ticks_seq(120, 4):
        surf = _blank()
        e.hurt_flash = 0
        e.draw(surf, cam_x, cam_y)
        idle_row.append(surf)

    # directional walk rows: enemies are symmetric, so we draw the same
    # procedural art for every direction — Gemini-generated art will differ.
    walk_row: list[pygame.Surface] = []
    for t in _ticks_seq(120, 4):
        surf = _blank()
        e.hurt_flash = 0
        e.draw(surf, cam_x, cam_y)
        walk_row.append(surf)

    # damaged row: full hurt_flash
    damaged_row: list[pygame.Surface] = []
    for _ in range(4):
        surf = _blank()
        e.hurt_flash = 8
        e.draw(surf, cam_x, cam_y)
        damaged_row.append(surf)
    e.hurt_flash = 0

    rows = [
        idle_row,       # 0 idle
        walk_row,       # 1 up
        walk_row,       # 2 right
        walk_row,       # 3 down
        None,           # 4 left — blank, auto-mirrored from right at runtime
        None,           # 5 attacking — blank, falls back to idle
        damaged_row,    # 6 damaged
    ]

    _save(type_key, "enemies", _pack_sheet(rows), _standard_manifest())


def _bake_sea_creature(kind: str) -> None:
    """Bake a sea creature into creatures/<kind>.png (384×672)."""
    sc = SeaCreature(0.0, 0.0, kind=kind)
    cam_x = sc.x - CX
    cam_y = sc.y - CY

    # Ticks sequences per kind for idle/swim animation cycles
    swim_period = {"dolphin": 1257, "fish": 1, "jellyfish": 1257}.get(kind, 400)
    swim_ticks = _ticks_seq(swim_period, 4)

    def _frame(ticks: int, facing: str = "right") -> pygame.Surface:
        surf = _blank()
        sc.facing_direction = facing
        sc.draw(surf, cam_x, cam_y, ticks, rider_color=None)
        return surf

    idle_row = [_frame(t) for t in swim_ticks]
    right_row = [_frame(t, "right") for t in swim_ticks]
    left_row = [_frame(t, "left") for t in swim_ticks]

    rows = [
        idle_row,   # 0 idle
        idle_row,   # 1 up   (best-effort; genuine up art from Gemini)
        right_row,  # 2 right
        idle_row,   # 3 down (best-effort)
        left_row,   # 4 left — explicit art so no auto-flip needed
        None,       # 5 attacking — blank
        idle_row,   # 6 damaged (flash tint supplied by Gemini art)
    ]

    _save(kind, "creatures", _pack_sheet(rows), _standard_manifest(include_left=True))


def _bake_overland_creature(kind: str) -> None:
    """Bake a land creature into creatures/<kind>.png (384×672)."""
    oc = OverlandCreature(0.0, 0.0, kind=kind)
    cam_x = oc.x - CX
    cam_y = oc.y - CY

    walk_period = {"horse": 419}.get(kind, 400)
    walk_ticks = _ticks_seq(walk_period, 4)

    def _frame(ticks: int, facing: str = "right", moving: bool = True) -> pygame.Surface:
        surf = _blank()
        oc.facing_direction = facing
        oc._is_moving = moving
        oc.draw(surf, cam_x, cam_y, ticks, rider_color=None)
        return surf

    idle_row = [_frame(0, moving=False) for _ in range(4)]
    right_row = [_frame(t, "right") for t in walk_ticks]
    left_row  = [_frame(t, "left")  for t in walk_ticks]

    rows = [
        idle_row,   # 0 idle
        idle_row,   # 1 up   (best-effort)
        right_row,  # 2 right
        idle_row,   # 3 down (best-effort)
        left_row,   # 4 left — explicit
        None,       # 5 attacking — blank
        idle_row,   # 6 damaged (best-effort; Gemini will add flash)
    ]

    _save(kind, "creatures", _pack_sheet(rows), _standard_manifest(include_left=True))


def _bake_pet(kind: str) -> None:
    """Bake a pet into pets/<kind>.png (384×672)."""
    # Use deterministic colours so baked sprites are stable across runs.
    pet = Pet(0.0, 0.0, kind=kind)
    cam_x = pet.x - CX
    cam_y = pet.y - CY

    period = {"cat": 785, "dog": 524}.get(kind, 600)
    anim_ticks = _ticks_seq(period, 4)

    def _frame(ticks: int) -> pygame.Surface:
        surf = _blank()
        pet.draw(surf, cam_x, cam_y, ticks)
        return surf

    idle_row = [_frame(t) for t in anim_ticks]

    rows = [
        idle_row,  # 0 idle
        idle_row,  # 1 up
        idle_row,  # 2 right
        idle_row,  # 3 down
        None,      # 4 left — blank, auto-flip
        None,      # 5 attacking — blank
        idle_row,  # 6 damaged — blank, Gemini art will differ
    ]

    _save(kind, "pets", _pack_sheet(rows), _standard_manifest())


def _bake_worker() -> None:
    """Bake the worker into workers/worker.png (384×672)."""
    worker = Worker(0.0, 0.0, player_id=1, home_map="overland")
    # Use stable deterministic colours so the baked sprite is reproducible.
    worker.body_color = (80, 120, 200)
    worker.skin_color = (220, 180, 140)
    worker.hat_color = (60, 40, 20)
    cam_x = worker.x - CX
    cam_y = worker.y - CY

    def _frame() -> pygame.Surface:
        surf = _blank()
        worker.draw(surf, cam_x, cam_y)
        return surf

    idle_row = [_frame() for _ in range(4)]

    rows = [
        idle_row,  # 0 idle
        idle_row,  # 1 up
        idle_row,  # 2 right
        idle_row,  # 3 down
        None,      # 4 left — blank, auto-flip
        None,      # 5 attacking — blank
        idle_row,  # 6 damaged
    ]

    _save("worker", "workers", _pack_sheet(rows), _standard_manifest())


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    print(f"Baking unified 7×4 96×96 sprites into {os.path.relpath(ASSETS_DIR, _REPO_ROOT)}/\n")

    print("Enemies:")
    for type_key in ENEMY_TYPES:
        _bake_enemy(type_key)

    print("\nSea creatures:")
    for kind in ("dolphin", "fish", "jellyfish"):
        _bake_sea_creature(kind)

    print("\nOverland creatures:")
    _bake_overland_creature("horse")

    print("\nPets:")
    for kind in ("dog", "cat"):
        _bake_pet(kind)

    print("\nWorkers:")
    _bake_worker()

    print("\nDone.")
    pygame.quit()


if __name__ == "__main__":
    main()
