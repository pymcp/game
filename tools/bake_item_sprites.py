"""Bake programmatic item and tab icon sprites.

Run from the repo root:
    python tools/bake_item_sprites.py

Outputs to assets/sprites/items/ (PNG + JSON manifest pairs).
Requires no display — uses SDL_VIDEODRIVER=dummy.
"""

import json
import math
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

pygame.init()
pygame.display.set_mode((1, 1))

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
OUT_DIR = os.path.join(REPO_ROOT, "assets", "sprites", "items")
os.makedirs(OUT_DIR, exist_ok=True)

W, H = 64, 64
_MANIFEST = {
    "frame_size": [W, H],
    "states": {"idle": {"row": 0, "frames": 1, "fps": 1}},
}


def _save(name: str, surf: pygame.Surface) -> None:
    pygame.image.save(surf, os.path.join(OUT_DIR, f"{name}.png"))
    with open(os.path.join(OUT_DIR, f"{name}.json"), "w") as fh:
        json.dump(_MANIFEST, fh, indent=2)
    print(f"  {name}.png")


def _blank() -> pygame.Surface:
    s = pygame.Surface((W, H), pygame.SRCALPHA)
    s.fill((0, 0, 0, 0))
    return s


def _s(c: tuple, amt: int) -> tuple[int, int, int]:
    """Shade a colour (positive = lighter, negative = darker)."""
    return (
        max(0, min(255, c[0] + amt)),
        max(0, min(255, c[1] + amt)),
        max(0, min(255, c[2] + amt)),
    )


# ===========================================================================
# MATERIAL ICONS
# ===========================================================================


def _bake_gem(name: str, col: tuple) -> None:
    """Diamond/gem shape — rotated square with facets."""
    s = _blank()
    pts_out = [(32, 8), (56, 32), (32, 56), (8, 32)]
    pts_in = [(32, 12), (52, 32), (32, 52), (12, 32)]
    pygame.draw.polygon(s, _s(col, -50), pts_out)
    pygame.draw.polygon(s, col, pts_in)
    pygame.draw.polygon(s, _s(col, 70), [(32, 12), (52, 32), (36, 26)])
    pygame.draw.circle(s, _s(col, 90), (27, 22), 4)
    _save(name, s)


def _bake_ore(name: str, col: tuple) -> None:
    """Irregular ore / rock chunk."""
    s = _blank()
    pts = [(22, 54), (8, 40), (10, 20), (26, 8), (46, 10), (58, 26), (54, 48), (38, 56)]
    inner = [
        (23, 52),
        (10, 40),
        (12, 22),
        (26, 10),
        (44, 12),
        (56, 26),
        (52, 46),
        (38, 54),
    ]
    pygame.draw.polygon(s, _s(col, -50), pts)
    pygame.draw.polygon(s, col, inner)
    pygame.draw.polygon(s, _s(col, 60), [(22, 14), (38, 8), (50, 22), (36, 24)])
    _save(name, s)


def _bake_wood(name: str) -> None:
    s = _blank()
    c = (140, 90, 45)
    pygame.draw.rect(s, _s(c, -40), (8, 18, 48, 28), border_radius=4)
    pygame.draw.rect(s, c, (10, 20, 44, 24), border_radius=3)
    for gy in [25, 30, 35]:
        pygame.draw.line(s, _s(c, 40), (13, gy), (51, gy), 1)
    pygame.draw.circle(s, _s(c, -30), (14, 32), 7)
    pygame.draw.circle(s, c, (14, 32), 6)
    _save(name, s)


def _bake_dirt(name: str) -> None:
    s = _blank()
    c = (145, 100, 55)
    pygame.draw.ellipse(s, _s(c, -40), (8, 20, 48, 30))
    pygame.draw.ellipse(s, c, (10, 22, 44, 26))
    pygame.draw.ellipse(s, _s(c, 50), (16, 24, 18, 10))
    _save(name, s)


def _bake_coral(name: str) -> None:
    s = _blank()
    c = (220, 90, 100)
    dc = _s(c, -50)
    pygame.draw.rect(s, dc, (29, 32, 6, 24))
    pygame.draw.rect(s, c, (30, 33, 4, 22))
    for bx, by, ex, ey in [
        (32, 36, 18, 22),
        (32, 36, 46, 22),
        (32, 28, 18, 12),
        (32, 28, 46, 12),
    ]:
        pygame.draw.line(s, dc, (bx, by), (ex, ey), 4)
        pygame.draw.line(s, c, (bx, by), (ex, ey), 2)
    for tx, ty in [(18, 22), (46, 22), (18, 12), (46, 12), (32, 10)]:
        pygame.draw.circle(s, c, (tx, ty), 5)
    _save(name, s)


def _bake_sail(name: str) -> None:
    s = _blank()
    pygame.draw.line(s, (110, 75, 35), (32, 8), (32, 58), 4)
    pts = [(32, 10), (56, 50), (32, 50)]
    pygame.draw.polygon(s, (240, 232, 212), pts)
    pygame.draw.polygon(s, (200, 188, 160), pts, 2)
    pygame.draw.line(s, (150, 130, 90), (32, 50), (56, 50), 2)
    _save(name, s)


def _bake_scuba(name: str) -> None:
    s = _blank()
    pygame.draw.ellipse(s, (40, 130, 130), (14, 12, 36, 40))
    pygame.draw.ellipse(s, (60, 180, 180), (16, 14, 32, 36))
    pygame.draw.ellipse(s, (160, 220, 240), (18, 18, 28, 18))
    pygame.draw.line(s, (40, 120, 120), (14, 32), (6, 44), 3)
    pygame.draw.line(s, (40, 120, 120), (50, 32), (58, 44), 3)
    pygame.draw.circle(s, (40, 110, 110), (32, 54), 5)
    pygame.draw.circle(s, (70, 160, 160), (32, 54), 3)
    _save(name, s)


def _bake_obsidian(name: str) -> None:
    s = _blank()
    c = (55, 18, 75)
    pts = [(32, 8), (52, 18), (58, 36), (48, 56), (18, 56), (8, 38), (14, 18)]
    inner = [(32, 12), (50, 22), (54, 36), (44, 53), (20, 53), (10, 38), (16, 22)]
    pygame.draw.polygon(s, (25, 8, 45), pts)
    pygame.draw.polygon(s, c, inner)
    pygame.draw.line(s, (130, 60, 170), (22, 20), (40, 14), 2)
    pygame.draw.line(s, (130, 60, 170), (18, 30), (28, 22), 1)
    _save(name, s)


def _bake_void_stone(name: str) -> None:
    s = _blank()
    c = (70, 15, 95)
    glow = (150, 70, 210)
    pts = [(32, 10), (52, 22), (56, 42), (44, 58), (20, 58), (10, 40), (14, 22)]
    inner = [(32, 14), (50, 24), (52, 42), (42, 55), (22, 55), (12, 40), (16, 24)]
    pygame.draw.polygon(s, (35, 8, 55), pts)
    pygame.draw.polygon(s, c, inner)
    pygame.draw.line(s, glow, (32, 22), (40, 38), 2)
    pygame.draw.line(s, glow, (32, 22), (22, 40), 2)
    pygame.draw.circle(s, glow, (32, 32), 7, 2)
    _save(name, s)


def _bake_frost_crystal(name: str) -> None:
    s = _blank()
    c, dc = (140, 210, 255), (70, 155, 215)
    for a in range(0, 360, 60):
        r = math.radians(a)
        ex, ey = int(32 + 24 * math.cos(r)), int(32 + 24 * math.sin(r))
        pygame.draw.line(s, dc, (32, 32), (ex, ey), 4)
        pygame.draw.line(s, c, (32, 32), (ex, ey), 2)
    pygame.draw.circle(s, c, (32, 32), 8)
    pygame.draw.circle(s, (200, 240, 255), (32, 32), 5)
    _save(name, s)


def _bake_bones(name: str) -> None:
    s = _blank()
    c, dc = (220, 215, 195), (160, 155, 128)
    for p1, p2 in [((14, 14), (50, 50)), ((50, 14), (14, 50))]:
        pygame.draw.line(s, dc, p1, p2, 7)
        pygame.draw.line(s, c, p1, p2, 5)
    for cx, cy in [(14, 14), (50, 50), (50, 14), (14, 50)]:
        pygame.draw.circle(s, dc, (cx, cy), 9)
        pygame.draw.circle(s, c, (cx, cy), 7)
    _save(name, s)


def _bake_desert_crystal(name: str) -> None:
    s = _blank()
    c = (200, 175, 78)
    pts = [(32, 8), (52, 22), (52, 44), (32, 56), (12, 44), (12, 22)]
    inner = [(32, 12), (50, 24), (50, 42), (32, 52), (14, 42), (14, 24)]
    pygame.draw.polygon(s, _s(c, -50), pts)
    pygame.draw.polygon(s, c, inner)
    pygame.draw.polygon(s, _s(c, 70), [(32, 12), (50, 24), (32, 28)])
    _save(name, s)


# ===========================================================================
# ARMOR ICONS
# ===========================================================================


def _bake_helmet(name: str, col: tuple) -> None:
    s = _blank()
    dc, lc = _s(col, -50), _s(col, 55)
    pygame.draw.ellipse(s, dc, (10, 8, 44, 34))
    pygame.draw.ellipse(s, col, (12, 10, 40, 30))
    pygame.draw.rect(s, _s(col, -80), (14, 28, 36, 10), border_radius=2)
    for bx, bw in [(8, 10), (46, 10)]:
        pygame.draw.rect(s, dc, (bx, 30, bw, 18), border_radius=2)
        pygame.draw.rect(s, col, (bx + 1, 31, bw - 2, 16), border_radius=2)
    pygame.draw.rect(s, dc, (8, 44, 48, 8), border_radius=2)
    pygame.draw.rect(s, col, (9, 45, 46, 6), border_radius=2)
    pygame.draw.ellipse(s, lc, (16, 12, 18, 10))
    _save(name, s)


def _bake_chest(name: str, col: tuple) -> None:
    s = _blank()
    dc, lc = _s(col, -50), _s(col, 55)
    pygame.draw.rect(s, dc, (12, 14, 40, 40), border_radius=3)
    pygame.draw.rect(s, col, (14, 16, 36, 36), border_radius=3)
    for bx, bw in [(4, 14), (46, 14)]:
        pygame.draw.rect(s, dc, (bx, 12, bw, 12), border_radius=3)
        pygame.draw.rect(s, col, (bx + 1, 13, bw - 2, 10), border_radius=3)
    pygame.draw.line(s, dc, (32, 18), (32, 50), 2)
    pygame.draw.circle(s, dc, (32, 34), 5)
    pygame.draw.circle(s, lc, (32, 34), 3)
    pygame.draw.ellipse(s, lc, (18, 18, 16, 8))
    _save(name, s)


def _bake_legs(name: str, col: tuple) -> None:
    s = _blank()
    dc, lc = _s(col, -50), _s(col, 55)
    pygame.draw.rect(s, dc, (10, 8, 44, 10), border_radius=2)
    pygame.draw.rect(s, col, (12, 9, 40, 8), border_radius=2)
    for lx in [10, 36]:
        pygame.draw.rect(s, dc, (lx, 20, 18, 36), border_radius=3)
        pygame.draw.rect(s, col, (lx + 1, 21, 16, 34), border_radius=3)
        pygame.draw.ellipse(s, lc, (lx + 3, 23, 10, 6))
    _save(name, s)


def _bake_boots(name: str, col: tuple) -> None:
    s = _blank()
    dc, lc = _s(col, -50), _s(col, 55)
    for bx in [6, 38]:
        pygame.draw.rect(s, dc, (bx, 10, 20, 38), border_radius=4)
        pygame.draw.rect(s, col, (bx + 1, 11, 18, 36), border_radius=4)
        pygame.draw.rect(s, dc, (bx - 2, 44, 24, 8), border_radius=3)
        pygame.draw.ellipse(s, lc, (bx + 2, 14, 10, 8))
    _save(name, s)


# ===========================================================================
# ACCESSORY ICONS
# ===========================================================================


def _bake_ring(name: str, col: tuple) -> None:
    s = _blank()
    dc, lc = _s(col, -50), _s(col, 60)
    pygame.draw.circle(s, dc, (32, 38), 21)
    pygame.draw.circle(s, col, (32, 38), 19, 9)
    gem_pts = [(32, 10), (44, 24), (32, 30), (20, 24)]
    pygame.draw.polygon(s, dc, gem_pts)
    pygame.draw.polygon(s, lc, [(32, 13), (42, 24), (32, 27), (22, 24)])
    pygame.draw.polygon(s, (255, 255, 255), [(32, 13), (42, 24), (35, 20)])
    _save(name, s)


def _bake_amulet(name: str, col: tuple) -> None:
    s = _blank()
    dc, lc = _s(col, -50), _s(col, 60)
    for cy in range(8, 26, 6):
        pygame.draw.circle(s, (160, 150, 120), (32, cy), 3, 1)
    pygame.draw.circle(s, dc, (32, 44), 18)
    pygame.draw.circle(s, col, (32, 44), 16)
    pygame.draw.circle(s, dc, (32, 44), 8, 2)
    pygame.draw.circle(s, lc, (27, 39), 4)
    pygame.draw.circle(s, lc, (32, 38), 3)
    _save(name, s)


# ===========================================================================
# WEAPON ICONS
# ===========================================================================


def _bake_rock_throw() -> None:
    s = _blank()
    c = (155, 148, 132)
    pts = [
        (32, 12),
        (50, 18),
        (57, 32),
        (52, 50),
        (36, 56),
        (20, 52),
        (10, 38),
        (14, 22),
    ]
    inner = [
        (32, 15),
        (48, 20),
        (54, 32),
        (50, 48),
        (35, 53),
        (21, 49),
        (12, 38),
        (16, 24),
    ]
    pygame.draw.polygon(s, _s(c, -45), pts)
    pygame.draw.polygon(s, c, inner)
    pygame.draw.polygon(s, _s(c, 60), [(24, 20), (38, 16), (46, 26), (34, 28)])
    _save("rock_throw", s)


def _bake_iron_dagger() -> None:
    s = _blank()
    blade, guard_c, handle_c = (200, 195, 190), (140, 130, 118), (110, 72, 40)
    pygame.draw.rect(s, _s(handle_c, -30), (28, 44, 8, 16), border_radius=2)
    pygame.draw.rect(s, handle_c, (29, 45, 6, 14), border_radius=2)
    pygame.draw.rect(s, _s(guard_c, -30), (16, 38, 32, 8), border_radius=2)
    pygame.draw.rect(s, guard_c, (17, 39, 30, 6), border_radius=2)
    pts = [(32, 8), (39, 38), (25, 38)]
    pygame.draw.polygon(s, _s(blade, -40), pts)
    pygame.draw.polygon(s, blade, [(32, 10), (38, 36), (26, 36)])
    pygame.draw.line(s, (240, 245, 250), (32, 10), (38, 35), 1)
    _save("iron_dagger", s)


def _bake_fire_bolt() -> None:
    s = _blank()
    c = (255, 120, 30)
    pts = [(32, 8), (50, 36), (46, 50), (32, 58), (18, 50), (14, 36)]
    inner = [(32, 12), (48, 36), (44, 48), (32, 55), (20, 48), (16, 36)]
    pygame.draw.polygon(s, _s(c, -60), pts)
    pygame.draw.polygon(s, c, inner)
    pygame.draw.ellipse(s, (255, 220, 80), (24, 32, 16, 16))
    pygame.draw.circle(s, (255, 255, 200), (32, 38), 4)
    _save("fire_bolt", s)


# ===========================================================================
# PICKAXE ICONS
# ===========================================================================


def _bake_pickaxe(name: str, col: tuple) -> None:
    s = _blank()
    dc, lc = _s(col, -45), _s(col, 55)
    handle_c = (140, 90, 45)
    pygame.draw.line(s, _s(handle_c, -30), (50, 52), (14, 52), 8)
    pygame.draw.line(s, handle_c, (50, 51), (14, 51), 5)
    pts = [(8, 22), (28, 14), (56, 22), (56, 34), (30, 40), (8, 34)]
    inner = [(10, 23), (28, 16), (54, 23), (54, 32), (30, 38), (10, 32)]
    pygame.draw.polygon(s, dc, pts)
    pygame.draw.polygon(s, col, inner)
    pygame.draw.polygon(s, dc, [(8, 24), (8, 32), (2, 28)])
    pygame.draw.polygon(s, lc, [(9, 25), (9, 31), (4, 28)])
    pygame.draw.line(s, lc, (16, 18), (46, 18), 2)
    _save(name, s)


# ===========================================================================
# TAB ICONS
# ===========================================================================


def _bake_tab_armor() -> None:
    s = _blank()
    c = (180, 170, 200)
    dc = _s(c, -60)
    pygame.draw.ellipse(s, dc, (10, 8, 44, 34))
    pygame.draw.ellipse(s, c, (12, 10, 40, 30))
    pygame.draw.rect(s, _s(c, -90), (14, 28, 36, 10), border_radius=2)
    pygame.draw.rect(s, dc, (8, 40, 48, 10), border_radius=2)
    pygame.draw.rect(s, c, (9, 41, 46, 8), border_radius=2)
    _save("tab_armor", s)


def _bake_tab_weapons() -> None:
    s = _blank()
    blade, guard_c, handle_c = (190, 190, 202), (160, 145, 120), (120, 82, 42)
    pts = [(32, 6), (39, 46), (25, 46)]
    pygame.draw.polygon(s, _s(blade, -40), pts)
    pygame.draw.polygon(s, blade, [(32, 8), (38, 44), (26, 44)])
    pygame.draw.line(s, (240, 245, 255), (32, 8), (38, 42), 1)
    pygame.draw.rect(s, _s(guard_c, -30), (14, 44, 36, 8), border_radius=3)
    pygame.draw.rect(s, guard_c, (15, 45, 34, 6), border_radius=3)
    pygame.draw.rect(s, _s(handle_c, -30), (28, 52, 8, 10), border_radius=2)
    pygame.draw.rect(s, handle_c, (29, 53, 6, 8), border_radius=2)
    _save("tab_weapons", s)


def _bake_tab_pickaxes() -> None:
    s = _blank()
    c, dc = (186, 176, 166), (100, 92, 85)
    handle_c = (140, 90, 45)
    pygame.draw.line(s, _s(handle_c, -30), (52, 54), (12, 54), 8)
    pygame.draw.line(s, handle_c, (52, 53), (12, 53), 5)
    pts = [(8, 22), (28, 14), (56, 20), (56, 32), (30, 38), (8, 32)]
    inner = [(10, 23), (28, 16), (54, 22), (54, 30), (30, 36), (10, 30)]
    pygame.draw.polygon(s, dc, pts)
    pygame.draw.polygon(s, c, inner)
    pygame.draw.polygon(s, dc, [(8, 24), (8, 30), (2, 27)])
    _save("tab_pickaxes", s)


def _bake_tab_materials() -> None:
    s = _blank()
    gems = [(90, 210, 240), (230, 200, 60), (140, 90, 200)]
    centers = [(32, 16), (20, 40), (44, 40)]
    for col, (cx, cy) in zip(gems, centers):
        pts_out = [(cx, cy - 12), (cx + 12, cy), (cx, cy + 12), (cx - 12, cy)]
        pts_in = [(cx, cy - 9), (cx + 9, cy), (cx, cy + 9), (cx - 9, cy)]
        pygame.draw.polygon(s, _s(col, -50), pts_out)
        pygame.draw.polygon(s, col, pts_in)
        pygame.draw.polygon(
            s, _s(col, 70), [(cx, cy - 9), (cx + 9, cy), (cx + 2, cy - 4)]
        )
    _save("tab_materials", s)


def _bake_tab_accessories() -> None:
    s = _blank()
    c = (230, 200, 60)
    dc, lc = _s(c, -50), _s(c, 60)
    pygame.draw.circle(s, dc, (32, 40), 20)
    pygame.draw.circle(s, c, (32, 40), 18, 9)
    gem_pts = [(32, 12), (44, 26), (32, 32), (20, 26)]
    pygame.draw.polygon(s, (60, 190, 230), gem_pts)
    pygame.draw.polygon(s, (180, 240, 255), [(32, 14), (42, 26), (34, 24)])
    _save("tab_accessories", s)


def _bake_tab_recipes() -> None:
    s = _blank()
    parch, dark_p, ink = (220, 200, 155), (170, 145, 95), (60, 40, 20)
    pygame.draw.rect(s, dark_p, (14, 12, 36, 42), border_radius=3)
    pygame.draw.rect(s, parch, (16, 14, 32, 38), border_radius=3)
    pygame.draw.ellipse(s, dark_p, (12, 8, 40, 12))
    pygame.draw.ellipse(s, parch, (14, 9, 36, 10))
    pygame.draw.ellipse(s, dark_p, (12, 44, 40, 12))
    pygame.draw.ellipse(s, parch, (14, 46, 36, 10))
    for ly in [20, 26, 32, 38]:
        pygame.draw.line(s, ink, (20, ly), (44, ly), 2)
    _save("tab_recipes", s)


# ===========================================================================
# MAIN
# ===========================================================================

if __name__ == "__main__":
    print(f"Baking item sprites → {OUT_DIR}")

    # — Materials —
    _bake_gem("diamond", (90, 210, 240))
    _bake_gem("void_stone", (80, 20, 100))
    _bake_gem("desert_crystal", (200, 175, 80))
    _bake_ore("stone", (150, 150, 150))
    _bake_ore("iron", (186, 176, 166))
    _bake_ore("gold", (230, 200, 60))
    _bake_ore("ancient_stone", (140, 90, 200))
    _bake_wood("wood")
    _bake_dirt("dirt")
    _bake_coral("coral")
    _bake_sail("sail")
    _bake_scuba("scuba_gear")
    _bake_obsidian("obsidian")
    _bake_void_stone("void_stone")  # overwrites gem version for better look
    _bake_frost_crystal("frost_crystal")
    _bake_bones("bones")
    _bake_desert_crystal("desert_crystal")  # overwrites gem version

    # — Armor pieces (6 materials × 4 slots = 24) —
    _ARMOR_MATERIAL_COLORS: dict[str, tuple[int, int, int]] = {
        "stone": (150, 150, 150),
        "iron": (186, 176, 166),
        "gold": (230, 200, 60),
        "diamond": (90, 210, 240),
        "coral": (240, 120, 130),
        "ancient_stone": (140, 90, 200),
        "ancient": (180, 120, 255),
    }
    for mat_id, col in _ARMOR_MATERIAL_COLORS.items():
        _bake_helmet(f"{mat_id}_helmet", col)
        _bake_chest(f"{mat_id}_chest", col)
        _bake_legs(f"{mat_id}_legs", col)
        _bake_boots(f"{mat_id}_boots", col)

    # — Accessories —
    _bake_ring("iron_ring", (186, 176, 166))
    _bake_ring("gold_ring", (230, 200, 60))
    _bake_ring("diamond_ring", (90, 210, 240))
    _bake_amulet("coral_amulet", (240, 120, 130))
    _bake_amulet("ancient_amulet", (140, 90, 200))

    # — Weapons —
    _bake_rock_throw()
    _bake_iron_dagger()
    _bake_fire_bolt()

    # — Pickaxes —
    _bake_pickaxe("wooden_pick", (160, 120, 60))
    _bake_pickaxe("stone_pick", (150, 150, 150))
    _bake_pickaxe("iron_pick", (200, 180, 160))
    _bake_pickaxe("gold_pick", (240, 210, 60))
    _bake_pickaxe("diamond_pick", (120, 230, 255))

    # — Tab icons —
    _bake_tab_armor()
    _bake_tab_weapons()
    _bake_tab_pickaxes()
    _bake_tab_materials()
    _bake_tab_accessories()
    _bake_tab_recipes()

    print("Done!")
