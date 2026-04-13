"""Bake procedural entity art into PNG sprite sheets.

Run from the repository root::

    python tools/bake_sprites.py

This script renders every enemy type, creature kind, pet kind, and worker
using the game's existing procedural draw code, and saves the results as
PNG+JSON sprite-sheet pairs under ``assets/sprites/``.

After this script runs, the SpriteRegistry will automatically load the sheets
at game startup and entity classes will blit frames instead of re-running the
procedural draw code every frame.

Existing PNG files are overwritten so you can safely re-run the script after
adding new enemy types.  Hand-crafted replacements should be placed in the
same paths — they will take precedence as long as the matching ``.json``
manifest is kept consistent with the sheet layout.
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
# Canvas specs  (width, height, center_x, center_y)
# Each entity type is drawn centred at (cx, cy) on a (width × height) RGBA
# surface.  Generous padding means art can be freely replaced at any size
# up to the canvas dimensions.
# ---------------------------------------------------------------------------
ENEMY_CANVAS: tuple[int, int, int, int] = (64, 64, 32, 32)

CREATURE_CANVAS: dict[str, tuple[int, int, int, int]] = {
    "dolphin":   (160, 96,  80, 48),
    "fish":      (48,  48,  24, 24),
    "jellyfish": (64,  80,  32, 36),
    "horse":     (96,  96,  48, 48),
}

PET_CANVAS: dict[str, tuple[int, int, int, int]] = {
    "dog": (64, 64, 32, 32),
    "cat": (64, 64, 32, 32),
}

WORKER_CANVAS: tuple[int, int, int, int] = (64, 64, 32, 32)

# ---------------------------------------------------------------------------
# Animation frame sequences
# Each value is a list of ``ticks`` integers passed to the draw() method.
# Multiple ticks values → multiple columns on the spritesheet row.
# ---------------------------------------------------------------------------

def _ticks_seq(period_ms: float, n_frames: int) -> list[int]:
    """Return *n_frames* evenly-spaced ticks values across one full period."""
    return [int(i / n_frames * period_ms) for i in range(n_frames)]


# Creature animation specs: {kind: {state_name: [ticks, ...], ...}}
CREATURE_ANIM: dict[str, dict[str, list[int]]] = {
    "dolphin":   {"swim": _ticks_seq(1257, 8)},       # bob: T = 2π/0.005 ≈ 1257 ms
    "fish":      {"swim": [0]},                         # static
    "jellyfish": {"swim": _ticks_seq(1257, 8)},        # tentacle + bob
    "horse":     {                                      # leg swing: T = 2π/0.015 ≈ 419 ms
        "walk": _ticks_seq(419, 8),
        "idle": [0],
    },
}

PET_ANIM: dict[str, dict[str, list[int]]] = {
    "cat": {"idle": _ticks_seq(785, 8)},    # tail wave: T = 2π/0.008 ≈ 785 ms
    "dog": {"idle": _ticks_seq(524, 8)},    # tail wag:  T = 2π/0.012 ≈ 524 ms
}

# Workers have no ticks-based animation in the current draw code.
WORKER_ANIM: dict[str, list[int]] = {"idle": [0], "walk": [0]}


# ---------------------------------------------------------------------------
# Surface helpers
# ---------------------------------------------------------------------------

def _blank(w: int, h: int) -> pygame.Surface:
    """Return a transparent RGBA surface of (w × h)."""
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    surf.fill((0, 0, 0, 0))
    return surf


def _pack_sheet(
    rows: list[list[pygame.Surface]],
    fw: int,
    fh: int,
) -> pygame.Surface:
    """Pack *rows* of frames into a single sprite-sheet surface.

    ``rows[i][j]`` is placed at column j of row i.  All frames share the
    same (fw × fh) cell size.
    """
    max_cols = max(len(row) for row in rows)
    sheet = pygame.Surface((fw * max_cols, fh * len(rows)), pygame.SRCALPHA)
    sheet.fill((0, 0, 0, 0))
    for ri, row in enumerate(rows):
        for ci, frame in enumerate(row):
            sheet.blit(frame, (ci * fw, ri * fh))
    return sheet


def _save(
    sheet: pygame.Surface,
    manifest: dict,
    out_path: str,
) -> None:
    """Write the sheet PNG and companion JSON manifest."""
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    pygame.image.save(sheet, out_path)
    with open(out_path.replace(".png", ".json"), "w") as fh:
        json.dump(manifest, fh, indent=2)
    w, h = sheet.get_size()
    print(f"  {os.path.relpath(out_path, _REPO_ROOT)}  ({w}×{h})")


# ---------------------------------------------------------------------------
# Baking helpers (per entity class)
# ---------------------------------------------------------------------------

def _bake_enemy(type_key: str, out_dir: str) -> None:
    """Bake a single enemy type into enemies/<type_key>.png."""
    w, h, cx, cy = ENEMY_CANVAS
    e = Enemy(0.0, 0.0, type_key)
    # For drawing: enemy.draw(surf, cam_x, cam_y) computes sx = e.x - cam_x
    # We want sx = cx, so cam_x = e.x - cx (and same for y).
    cam_x = e.x - cx
    cam_y = e.y - cy

    rows: list[list[pygame.Surface]] = []
    states: dict[str, dict] = {}

    def _frame(hurt: bool) -> pygame.Surface:
        surf = _blank(w, h)
        e.hurt_flash = 8 if hurt else 0
        e.draw(surf, cam_x, cam_y)
        return surf

    for row_idx, (state_name, hurt) in enumerate(
        [("idle", False), ("walk", False), ("hurt", True)]
    ):
        rows.append([_frame(hurt)])
        states[state_name] = {"row": row_idx, "frames": 1, "fps": 1}

    sheet = _pack_sheet(rows, w, h)
    manifest = {"frame_size": [w, h], "states": states}
    _save(sheet, manifest, os.path.join(out_dir, "enemies", f"{type_key}.png"))


def _bake_sea_creature(kind: str, out_dir: str) -> None:
    """Bake a sea creature kind into creatures/<kind>.png."""
    w, h, cx, cy = CREATURE_CANVAS[kind]
    sc = SeaCreature(0.0, 0.0, kind=kind)
    offset_x = sc.x - cx
    offset_y = sc.y - cy

    rows: list[list[pygame.Surface]] = []
    states: dict[str, dict] = {}

    for row_idx, (state_name, ticks_list) in enumerate(CREATURE_ANIM[kind].items()):
        row_frames: list[pygame.Surface] = []
        for ticks in ticks_list:
            surf = _blank(w, h)
            sc.draw(surf, offset_x, offset_y, ticks, rider_color=None)
            row_frames.append(surf)
        rows.append(row_frames)
        states[state_name] = {
            "row": row_idx,
            "frames": len(ticks_list),
            "fps": 8 if len(ticks_list) > 1 else 1,
        }

    sheet = _pack_sheet(rows, w, h)
    manifest = {"frame_size": [w, h], "states": states}
    _save(sheet, manifest, os.path.join(out_dir, "creatures", f"{kind}.png"))


def _bake_overland_creature(kind: str, out_dir: str) -> None:
    """Bake an overland creature kind into creatures/<kind>.png."""
    w, h, cx, cy = CREATURE_CANVAS[kind]
    oc = OverlandCreature(0.0, 0.0, kind=kind)
    offset_x = oc.x - cx
    offset_y = oc.y - cy

    rows: list[list[pygame.Surface]] = []
    states: dict[str, dict] = {}

    for row_idx, (state_name, ticks_list) in enumerate(CREATURE_ANIM[kind].items()):
        row_frames: list[pygame.Surface] = []
        for ticks in ticks_list:
            surf = _blank(w, h)
            oc.draw(surf, offset_x, offset_y, ticks, rider_color=None)
            row_frames.append(surf)
        rows.append(row_frames)
        states[state_name] = {
            "row": row_idx,
            "frames": len(ticks_list),
            "fps": 8 if len(ticks_list) > 1 else 1,
        }

    sheet = _pack_sheet(rows, w, h)
    manifest = {"frame_size": [w, h], "states": states}
    _save(sheet, manifest, os.path.join(out_dir, "creatures", f"{kind}.png"))


def _bake_pet(kind: str, out_dir: str) -> None:
    """Bake a pet kind into pets/<kind>.png."""
    w, h, cx, cy = PET_CANVAS[kind]
    pet = Pet(0.0, 0.0, kind=kind)
    cam_x = pet.x - cx
    cam_y = pet.y - cy

    rows: list[list[pygame.Surface]] = []
    states: dict[str, dict] = {}

    for row_idx, (state_name, ticks_list) in enumerate(PET_ANIM[kind].items()):
        row_frames: list[pygame.Surface] = []
        for ticks in ticks_list:
            surf = _blank(w, h)
            pet.draw(surf, cam_x, cam_y, ticks)
            row_frames.append(surf)
        rows.append(row_frames)
        states[state_name] = {
            "row": row_idx,
            "frames": len(ticks_list),
            "fps": 8 if len(ticks_list) > 1 else 1,
        }

    sheet = _pack_sheet(rows, w, h)
    manifest = {"frame_size": [w, h], "states": states}
    _save(sheet, manifest, os.path.join(out_dir, "pets", f"{kind}.png"))


def _bake_worker(out_dir: str) -> None:
    """Bake the worker into workers/worker.png."""
    import random

    w, h, cx, cy = WORKER_CANVAS
    # Use deterministic colours so the baked sprite is stable across runs.
    worker = Worker(0.0, 0.0, player_id=1, home_map="overland")
    # Override randomised colours with a fixed neutral palette.
    worker.body_color = (80, 120, 200)
    worker.skin_color = (220, 180, 140)
    worker.hat_color = (60, 40, 20)
    cam_x = worker.x - cx
    cam_y = worker.y - cy

    rows: list[list[pygame.Surface]] = []
    states: dict[str, dict] = {}

    for row_idx, (state_name, ticks_list) in enumerate(WORKER_ANIM.items()):
        row_frames: list[pygame.Surface] = []
        for _ticks in ticks_list:
            surf = _blank(w, h)
            worker.draw(surf, cam_x, cam_y)
            row_frames.append(surf)
        rows.append(row_frames)
        states[state_name] = {"row": row_idx, "frames": 1, "fps": 1}

    sheet = _pack_sheet(rows, w, h)
    manifest = {"frame_size": [w, h], "states": states}
    _save(sheet, manifest, os.path.join(out_dir, "workers", "worker.png"))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print(f"Baking sprites into {os.path.relpath(ASSETS_DIR, _REPO_ROOT)}/\n")

    print("Enemies:")
    for type_key in ENEMY_TYPES:
        _bake_enemy(type_key, ASSETS_DIR)

    print("\nSea creatures:")
    for kind in ("dolphin", "fish", "jellyfish"):
        _bake_sea_creature(kind, ASSETS_DIR)

    print("\nOverland creatures:")
    _bake_overland_creature("horse", ASSETS_DIR)

    print("\nPets:")
    for kind in ("dog", "cat"):
        _bake_pet(kind, ASSETS_DIR)

    print("\nWorkers:")
    _bake_worker(ASSETS_DIR)

    print("\nDone.")
    pygame.quit()


if __name__ == "__main__":
    main()
