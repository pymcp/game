"""Bake player base sprite and equipment overlay sheets.

Run from the repository root::

    python tools/bake_player_sprites.py

Outputs to assets/sprites/players/:
  player_base.png     — greyscale body in all 7 directions × 4 frames (384×672)
  helmet_overlay.png  — white template layer for helmet slot, same layout
  chest_overlay.png   — white template layer for chest slot
  legs_overlay.png    — white template layer for legs slot
  boots_overlay.png   — white template layer for boots slot

At runtime the game:
  1. Tints player_base.png by player.color (each player has a random body colour)
  2. Tints each overlay by ARMOR_PIECES[equipped_item]["color"]
  3. Composites overlays onto the base frame

All sheets follow the unified 384×672 format (7 rows × 4 cols, each cell 96×96).
"""

import json
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

pygame.init()
pygame.display.set_mode((1, 1))

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.entities.player import Player  # noqa: E402

# ---------------------------------------------------------------------------
# Output paths
# ---------------------------------------------------------------------------
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(_REPO_ROOT, "assets", "sprites", "players")
os.makedirs(OUT_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Unified cell size (matches bake_sprites.py)
# ---------------------------------------------------------------------------
FW: int = 96
FH: int = 96
CX: int = 48
CY: int = 48

_MANIFEST: dict = {
    "frame_size": [FW, FH],
    "states": {
        "idle": {"row": 0, "frames": 4, "fps": 4.0},
        "up": {"row": 1, "frames": 4, "fps": 8.0},
        "right": {"row": 2, "frames": 4, "fps": 8.0},
        "down": {"row": 3, "frames": 4, "fps": 8.0},
        "left": {"row": 4, "frames": 4, "fps": 8.0},
        "attacking": {"row": 5, "frames": 4, "fps": 8.0},
        "damaged": {"row": 6, "frames": 4, "fps": 4.0},
    },
}

# Equipment slots that receive their own overlay sheet
OVERLAY_SLOTS: list[str] = ["helmet", "chest", "legs", "boots"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _blank() -> pygame.Surface:
    """Return a transparent 96×96 RGBA surface."""
    surf = pygame.Surface((FW, FH), pygame.SRCALPHA)
    surf.fill((0, 0, 0, 0))
    return surf


def _pack_sheet(rows: list[list[pygame.Surface] | None]) -> pygame.Surface:
    """Pack 7 rows of 4 frames into a 384×672 sheet."""
    sheet = pygame.Surface((FW * 4, FH * 7), pygame.SRCALPHA)
    sheet.fill((0, 0, 0, 0))
    for ri, row in enumerate(rows):
        if row is None:
            continue
        for ci, frame in enumerate(row[:4]):
            sheet.blit(frame, (ci * FW, ri * FH))
    return sheet


def _save(name: str, sheet: pygame.Surface) -> None:
    png_path = os.path.join(OUT_DIR, f"{name}.png")
    json_path = os.path.join(OUT_DIR, f"{name}.json")
    pygame.image.save(sheet, png_path)
    with open(json_path, "w") as fh:
        json.dump(_MANIFEST, fh, indent=2)
    w, h = sheet.get_size()
    print(f"  players/{name}.png  ({w}×{h})")


def _grey(r: int, g: int, b: int, a: int = 255) -> tuple[int, int, int, int]:
    """Convert an RGBA colour to a greyscale RGBA value (luminance-preserving)."""
    lum = int(0.299 * r + 0.587 * g + 0.114 * b)
    return (lum, lum, lum, a)


def _to_greyscale(surf: pygame.Surface) -> pygame.Surface:
    """Return a greyscale copy of *surf* (preserving alpha channel)."""
    out = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    for x in range(surf.get_width()):
        for y in range(surf.get_height()):
            r, g, b, a = surf.get_at((x, y))
            if a > 0:
                out.set_at((x, y), _grey(r, g, b, a))
    return out


def _isolate_slot(full: pygame.Surface, player: Player, slot: str) -> pygame.Surface:
    """Return a surface showing only the pixels contributed by *slot*'s armor.

    We draw the player twice — once with armor and once without — and keep
    only pixels that differ.  The differing pixels are set to white (to act
    as a tint template).
    """
    # Frame without this slot
    player.equipment[slot] = None
    bare = _blank()
    player.draw(bare, player.x - CX, player.y - CY)

    # Frame with a placeholder armor that draws white (full brightness)
    # We use a dummy white color for the armor by temporarily injecting it.
    # Instead of injecting, we just compare the two frames and keep diffs.
    out = pygame.Surface((FW, FH), pygame.SRCALPHA)
    out.fill((0, 0, 0, 0))
    for x in range(FW):
        for y in range(FH):
            pb = bare.get_at((x, y))
            pf = full.get_at((x, y))
            # Pixel is part of this slot if it changed at all
            if pf[:3] != pb[:3] and pf[3] > 0:
                # Store as white so it can be tinted at runtime
                out.set_at((x, y), (255, 255, 255, pf[3]))
    return out


# ---------------------------------------------------------------------------
# Baking
# ---------------------------------------------------------------------------

FACING_DIRS: list[tuple[str, float, float]] = [
    ("idle", 1.0, 0.0),  # row 0 — idle faces right by default
    ("up", 0.0, -1.0),  # row 1
    ("right", 1.0, 0.0),  # row 2
    ("down", 0.0, 1.0),  # row 3
    ("left", -1.0, 0.0),  # row 4
    ("right", 1.0, 0.0),  # row 5 — attacking (same dir as right for now)
    ("right", 1.0, 0.0),  # row 6 — damaged
]

# Small walk oscillation applied to frames within a directional row
_WALK_DX: list[float] = [1.0, 1.0, 1.0, 1.0]


def _make_player() -> Player:
    """Return a neutral (greyscale-compatible) player instance."""
    p = Player(0.0, 0.0, player_id=1)
    # Fixed neutral grey body — will be tinted per-player at runtime
    p.color = (200, 200, 200)
    return p


def bake_base_and_overlays() -> None:
    """Generate player_base.png and per-slot overlay sheets."""
    p = _make_player()
    cam_x = p.x - CX
    cam_y = p.y - CY

    base_rows: list[list[pygame.Surface] | None] = []
    overlay_rows: dict[str, list[list[pygame.Surface] | None]] = {
        slot: [] for slot in OVERLAY_SLOTS
    }

    for row_idx, (dir_name, fdx, fdy) in enumerate(FACING_DIRS):
        # --- injury tint for damaged row ---
        is_damaged = dir_name == "damaged"
        if is_damaged:
            p.hurt_timer = 99.0  # force hurt-flash red
        else:
            p.hurt_timer = 0.0

        base_row: list[pygame.Surface] = []
        slot_overlay_row: dict[str, list[pygame.Surface]] = {
            s: [] for s in OVERLAY_SLOTS
        }

        for frame_idx in range(4):
            # Set facing direction
            p.facing_dx = fdx
            p.facing_dy = fdy if fdy != 0.0 else 0.0

            # --- Capture full frame (all equipment removed for base) ---
            for slot in OVERLAY_SLOTS:
                p.equipment[slot] = None

            full_surf = _blank()
            p.draw(full_surf, cam_x, cam_y)

            # Convert body to greyscale
            base_row.append(_to_greyscale(full_surf))

            # --- Per-slot overlays: not needed in placeholder bake ---
            # Overlays are all-transparent here; they are filled with real art
            # by Gemini or a hand-crafted artist following the overlay spec.
            for slot in OVERLAY_SLOTS:
                slot_overlay_row[slot].append(_blank())

        base_rows.append(base_row)
        for slot in OVERLAY_SLOTS:
            overlay_rows[slot].append(slot_overlay_row[slot])

    p.hurt_timer = 0.0

    print("Saving base sheet...")
    _save("player_base", _pack_sheet(base_rows))

    print("Saving overlay sheets...")
    for slot in OVERLAY_SLOTS:
        _save(f"{slot}_overlay", _pack_sheet(overlay_rows[slot]))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    print(f"Baking player sprites into players/\n")
    bake_base_and_overlays()
    print("\nDone.")
    pygame.quit()


if __name__ == "__main__":
    main()
