"""Bake procedural world-object sprites (sign, broken_ladder, sky_ladder, cloud).

Run from the repo root:
    python tools/bake_world_sprites.py

Outputs to assets/sprites/world/  (PNG + JSON manifest pairs).
Requires no display — uses SDL_VIDEODRIVER=dummy.
"""

import json
import math
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

pygame.init()
pygame.display.set_mode((1, 1))

# ---------------------------------------------------------------------------
# Output directory
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
OUT_DIR = os.path.join(REPO_ROOT, "assets", "sprites", "world")
os.makedirs(OUT_DIR, exist_ok=True)


def _save(name: str, sheet: pygame.Surface, manifest: dict) -> None:
    """Save a sprite sheet PNG and its JSON manifest."""
    png_path = os.path.join(OUT_DIR, f"{name}.png")
    json_path = os.path.join(OUT_DIR, f"{name}.json")
    pygame.image.save(sheet, png_path)
    with open(json_path, "w") as fh:
        json.dump(manifest, fh, indent=2)
    print(f"  {name}.png  {sheet.get_size()}  {list(manifest['states'].keys())}")


# ===========================================================================
# SIGN  (64×64, 1-frame IDLE)
# ===========================================================================


def bake_sign() -> None:
    fw, fh = 32, 32
    surf = pygame.Surface((fw, fh), pygame.SRCALPHA)
    surf.fill((0, 0, 0, 0))

    post_c = (120, 80, 40)
    wood_c = (185, 135, 70)
    grain_c = (150, 105, 50)
    text_c = (60, 35, 15)

    # Post (vertical)
    pygame.draw.rect(surf, post_c, (29, 28, 6, 36))
    # Sign board
    pygame.draw.rect(surf, wood_c, (10, 10, 44, 26), border_radius=3)
    pygame.draw.rect(surf, post_c, (10, 10, 44, 26), 2, border_radius=3)
    # Wood grain lines
    for gy in [17, 23, 29]:
        pygame.draw.line(surf, grain_c, (13, gy), (50, gy), 1)
    # Simplified text strokes (decorative only)
    for lx in range(15, 49, 7):
        pygame.draw.rect(surf, text_c, (lx, 14, 4, 2))
        pygame.draw.rect(surf, text_c, (lx, 20, 4, 2))
        pygame.draw.rect(surf, text_c, (lx, 26, 4, 2))
    # Nail dots
    pygame.draw.circle(surf, (80, 60, 40), (14, 14), 2)
    pygame.draw.circle(surf, (80, 60, 40), (50, 14), 2)
    pygame.draw.circle(surf, (80, 60, 40), (14, 32), 2)
    pygame.draw.circle(surf, (80, 60, 40), (50, 32), 2)

    sheet = surf
    manifest = {
        "frame_size": [fw, fh],
        "states": {
            "idle": {"row": 0, "frames": 1, "fps": 1},
        },
    }
    _save("sign", sheet, manifest)


# ===========================================================================
# BROKEN_LADDER  (64×128, 1-frame IDLE)
# ===========================================================================


def bake_broken_ladder() -> None:
    fw, fh = 32, 64
    surf = pygame.Surface((fw, fh), pygame.SRCALPHA)
    surf.fill((0, 0, 0, 0))

    rail_c = (100, 75, 45)
    rung_c = (130, 100, 60)
    broken_c = (80, 55, 30)
    nail_c = (70, 55, 40)

    # Left rail
    pygame.draw.rect(surf, rail_c, (14, 8, 8, 112), border_radius=2)
    # Right rail
    pygame.draw.rect(surf, rail_c, (42, 8, 8, 112), border_radius=2)

    # Rails have some splits/cracks
    for crack_y in [35, 78]:
        pygame.draw.line(surf, broken_c, (14, crack_y), (22, crack_y + 4), 2)
        pygame.draw.line(surf, broken_c, (42, crack_y + 8), (50, crack_y + 3), 2)

    # Rungs (4 total, but broken — some tilted, some missing a chunk)
    rung_positions = [20, 44, 68, 94]
    for i, ry in enumerate(rung_positions):
        if i == 1:
            # Broken rung — only left half remains, tilted
            pts = [(18, ry - 3), (36, ry + 2), (36, ry + 7), (18, ry + 2)]
            pygame.draw.polygon(surf, broken_c, pts)
        elif i == 2:
            # Tilted but intact
            pts = [(18, ry + 4), (46, ry - 2), (46, ry + 3), (18, ry + 9)]
            pygame.draw.polygon(surf, rung_c, pts)
        else:
            # Normal rung
            pygame.draw.rect(surf, rung_c, (18, ry - 3, 28, 6), border_radius=1)

    # Nail marks
    for ry in rung_positions:
        pygame.draw.circle(surf, nail_c, (18, ry), 2)
        pygame.draw.circle(surf, nail_c, (46, ry), 2)

    manifest = {
        "frame_size": [fw, fh],
        "states": {
            "idle": {"row": 0, "frames": 1, "fps": 1},
        },
    }
    _save("broken_ladder", surf, manifest)


# ===========================================================================
# SKY_LADDER  (32×64, row0=idle 1-frame; row1=extending 8-frames)
# ===========================================================================


def _draw_ladder_frame(
    surf: pygame.Surface, ox: int, oy: int, rungs_visible: int, glow: float = 0.0
) -> None:
    """Draw a clean repaired ladder at offset (ox, oy) with *rungs_visible* rungs."""
    rail_c = (180, 145, 80)
    rung_c = (220, 185, 105)
    shine_c = (240, 220, 160)
    glow_c = (255, int(220 + glow * 35), int(100 + glow * 80))

    if glow > 0:
        # Soft glow halo behind rails
        glow_surf = pygame.Surface((64, 128), pygame.SRCALPHA)
        alpha = int(glow * 80)
        pygame.draw.rect(glow_surf, (*glow_c, alpha), (10, oy, 12, 128 - oy))
        pygame.draw.rect(glow_surf, (*glow_c, alpha), (42, oy, 12, 128 - oy))
        surf.blit(glow_surf, (ox, 0))

    # Rails
    pygame.draw.rect(surf, rail_c, (ox + 14, oy + 8, 8, 112), border_radius=3)
    pygame.draw.rect(surf, rail_c, (ox + 42, oy + 8, 8, 112), border_radius=3)
    # Rail shine
    pygame.draw.line(surf, shine_c, (ox + 16, oy + 10), (ox + 16, oy + 118), 1)
    pygame.draw.line(surf, shine_c, (ox + 44, oy + 10), (ox + 44, oy + 118), 1)

    rung_ys = [20, 44, 68, 94]
    for idx, ry in enumerate(rung_ys[:rungs_visible]):
        pygame.draw.rect(surf, rung_c, (ox + 18, oy + ry - 3, 28, 7), border_radius=2)
        pygame.draw.line(
            surf, shine_c, (ox + 20, oy + ry - 2), (ox + 44, oy + ry - 2), 1
        )


def bake_sky_ladder() -> None:
    fw, fh = 32, 64
    n_extend = 8
    total_rows = 1 + n_extend
    sheet = pygame.Surface((fw, fh * total_rows), pygame.SRCALPHA)
    sheet.fill((0, 0, 0, 0))

    # Row 0: idle (fully repaired, no glow)
    _draw_ladder_frame(sheet, 0, 0, rungs_visible=4)

    # Rows 1-8: extending — rungs shoot upward from bottom with growing glow
    for frame_idx in range(n_extend):
        oy = fh * (1 + frame_idx)
        progress = (frame_idx + 1) / n_extend  # 0.125 → 1.0
        rungs_vis = max(1, int(progress * 4 + 0.5))
        glow = progress * 0.8
        _draw_ladder_frame(sheet, 0, oy, rungs_visible=rungs_vis, glow=glow)

        # Sparks / ascending light dots near the top
        n_sparks = int(progress * 6)
        rng = pygame.time.get_ticks() + frame_idx * 997
        for s in range(n_sparks):
            sx = 20 + (s * 37 + rng) % 24
            sy_local = 8 + (s * 53 + rng) % 60
            alpha = int(200 - s * 20)
            spark_c = (255, 240, 180, max(0, alpha))
            spark_surf = pygame.Surface((4, 4), pygame.SRCALPHA)
            pygame.draw.circle(spark_surf, spark_c, (2, 2), 2)
            sheet.blit(spark_surf, (sx, oy + sy_local))

    manifest = {
        "frame_size": [fw, fh],
        "states": {
            "idle": {"row": 0, "frames": 1, "fps": 1},
            "extending": {"row": 1, "frames": n_extend, "fps": 8},
        },
    }
    _save("sky_ladder", sheet, manifest)


# ===========================================================================
# CLOUD  (256×64, 4-frame IDLE at 0.5fps — slow shape variation)
# ===========================================================================


def _draw_cloud(
    surf: pygame.Surface, ox: int, oy: int, variant: int, alpha: int = 200
) -> None:
    """Draw a fluffy cloud shape at (ox, oy) into surf."""
    base_c = (240, 245, 255, alpha)
    highlight_c = (255, 255, 255, alpha)
    shadow_c = (200, 210, 230, int(alpha * 0.7))

    # Different puff arrangements per variant
    puff_configs = [
        [(28, 36, 22), (48, 30, 28), (68, 34, 20), (86, 36, 18)],
        [(22, 38, 20), (42, 28, 26), (64, 32, 24), (84, 36, 18), (100, 38, 14)],
        [(30, 40, 18), (50, 32, 24), (72, 28, 26), (90, 34, 20)],
        [(20, 36, 20), (40, 30, 22), (60, 36, 20), (80, 28, 24), (96, 36, 16)],
    ]
    puffs = puff_configs[variant % 4]

    cloud_layer = pygame.Surface((128, 64), pygame.SRCALPHA)
    cloud_layer.fill((0, 0, 0, 0))

    # Shadow ellipse at base
    for cx, cy, r in puffs:
        shadow_surf = pygame.Surface((r * 2, int(r * 0.6) * 2), pygame.SRCALPHA)
        shadow_surf.fill((0, 0, 0, 0))
        pygame.draw.ellipse(shadow_surf, shadow_c, (0, 0, r * 2, int(r * 0.6) * 2))
        cloud_layer.blit(shadow_surf, (cx - r, cy + int(r * 0.4)))

    # Main puffs
    for cx, cy, r in puffs:
        puff_surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        puff_surf.fill((0, 0, 0, 0))
        pygame.draw.circle(puff_surf, base_c, (r, r), r)
        cloud_layer.blit(puff_surf, (cx - r, cy - r))

    # Highlight on top puffs
    for cx, cy, r in puffs:
        hl_r = max(3, r // 3)
        hl_surf = pygame.Surface((hl_r * 2, hl_r * 2), pygame.SRCALPHA)
        hl_surf.fill((0, 0, 0, 0))
        pygame.draw.circle(hl_surf, highlight_c, (hl_r, hl_r), hl_r)
        cloud_layer.blit(hl_surf, (cx - hl_r // 2, cy - r + 4))

    surf.blit(cloud_layer, (ox, oy))


def bake_cloud() -> None:
    fw, fh = 64, 32
    n_frames = 4
    sheet = pygame.Surface((fw * n_frames, fh), pygame.SRCALPHA)
    sheet.fill((0, 0, 0, 0))

    for i in range(n_frames):
        _draw_cloud(sheet, i * fw, 0, variant=i, alpha=200)

    manifest = {
        "frame_size": [fw, fh],
        "states": {
            "idle": {"row": 0, "frames": n_frames, "fps": 0.5},
        },
    }
    _save("cloud", sheet, manifest)


# ===========================================================================
# Main
# ===========================================================================

if __name__ == "__main__":
    print(f"Baking world sprites → {OUT_DIR}")
    bake_sign()
    bake_broken_ladder()
    bake_sky_ladder()
    bake_cloud()
    print("Done.")
    pygame.quit()
