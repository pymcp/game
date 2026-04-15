#!/usr/bin/env python3
"""Generate assets/tiles/standalone/mountain.png — 4-variant mountain peaks.

Canvas       : 256 × 80 px  (4 frames × 64 px wide, 80 px tall)
draw_offset  : [-16, -48]   — centers 64 px frame on 32 px tile; peak rises
               48 px above the tile top; bottom 32 px sits at tile level.
               Adjacent rows share 48 px of vertical overlap → natural range.
"""

import math
from PIL import Image, ImageDraw

# ── Colour palette ──────────────────────────────────────────────────────────
BG       = (204,  51, 187)   # #CC33BB — stripped by engine
SNOW     = (248, 248, 255)   # snow cap
SNOW_SH  = (210, 215, 228)   # snow shadow
ROCK_1   = (202, 195, 185)   # lit face (upper-left)
ROCK_2   = (158, 151, 142)   # mid face
ROCK_3   = (108, 103,  96)   # shadow face (lower-right)
ROCK_4   = ( 66,  63,  58)   # dark edge / crevice

FW, FH   = 64, 80
OUT      = "assets/tiles/standalone/mountain.png"

img  = Image.new("RGB", (FW * 4, FH), BG)
draw = ImageDraw.Draw(img)


# ── Helpers ─────────────────────────────────────────────────────────────────

def _poly(pts: list[tuple[int, int]], colour: tuple) -> None:
    draw.polygon(pts, fill=colour)


def _el(cx: int, cy: int, rx: int, ry: int, colour: tuple) -> None:
    draw.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=colour)


def _circle(cx: int, cy: int, r: int, colour: tuple) -> None:
    _el(cx, cy, r, r, colour)


def rocky_bumps(peak_x: int, peak_y: int, base_y: int, half_w: int, ox: int) -> None:
    """Scatter small dark ellipses on the silhouette edge for a craggy look."""
    for angle_deg in range(10, 360, 40):
        a   = math.radians(angle_deg)
        # mountain silhouette is roughly triangular; project onto it
        t   = abs(math.cos(a))
        bx  = peak_x + int(half_w * math.sin(a) * (1.0 - t * 0.5))
        by  = peak_y + int((base_y - peak_y) * (0.5 + 0.5 * abs(math.sin(a))))
        br  = max(2, half_w // 6)
        _el(ox + bx, by, br, max(1, br - 1), ROCK_4)


def draw_single_peak(
    ox: int,
    peak_x: int, peak_y: int,
    half_w: int, base_y: int,
) -> None:
    """
    Draw one mountain peak in offset-x frame.

    peak_x, peak_y  — apex coords in frame space
    half_w          — half-width of mountain at base_y
    base_y          — y of the wide base (near frame bottom)
    """
    left   = peak_x - half_w
    right  = peak_x + half_w

    # ── Outer silhouette (dark edge) ─────────────────────────────────────────
    _poly([
        (ox + peak_x, peak_y),
        (ox + left,   base_y),
        (ox + right,  base_y),
    ], ROCK_4)

    # ── Right (shadow) face — runs roughly from peak to lower-right ──────────
    _poly([
        (ox + peak_x,           peak_y),
        (ox + peak_x + 2,       peak_y + 12),
        (ox + right - 4,        base_y),
        (ox + right,            base_y),
    ], ROCK_3)

    # ── Main lit face — left-centre portion ──────────────────────────────────
    _poly([
        (ox + peak_x,           peak_y),
        (ox + left + 4,         base_y),
        (ox + peak_x - 4,       base_y - 18),
        (ox + peak_x - 2,       peak_y + 20),
    ], ROCK_2)

    # ── Upper-left highlight face ─────────────────────────────────────────────
    _poly([
        (ox + peak_x,           peak_y),
        (ox + peak_x - 2,       peak_y + 20),
        (ox + left + int(half_w * 0.55), base_y - int((base_y - peak_y) * 0.35)),
    ], ROCK_1)

    # ── Snow cap ──────────────────────────────────────────────────────────────
    _el(ox + peak_x, peak_y + 5, 7, 6, SNOW)
    _el(ox + peak_x + 1, peak_y + 7, 4, 4, SNOW_SH)

    # ── Craggy edge bumps ─────────────────────────────────────────────────────
    rocky_bumps(peak_x, peak_y, base_y, half_w, ox)


# ── Four distinct variants ───────────────────────────────────────────────────

# Frame 0  (x 0–63): Sharp alpine peak, centred
draw_single_peak(  0, peak_x=32, peak_y=7,  half_w=26, base_y=73)

# Frame 1  (x 64–127): Broad rounded peak — use twin stacked ellipses approach
# Outer body
_poly([(64+32, 9), (64+4, 74), (64+60, 74)], ROCK_4)
_poly([(64+32, 9), (64+32+2, 9+12), (64+56, 74), (64+60, 74)], ROCK_3)
_poly([(64+32, 9), (64+8, 74), (64+22, 52), (64+28, 22)], ROCK_2)
_poly([(64+32, 9), (64+28, 22), (64+16, 48)], ROCK_1)
# Broader flatter snow cap
_el(64+32, 16, 10, 7, SNOW)
_el(64+34, 19, 6, 4, SNOW_SH)
rocky_bumps(32, 9, 74, 28, 64)

# Frame 2  (x 128–191): Off-centre peak leans left — rugged look
draw_single_peak(128, peak_x=26, peak_y=10, half_w=28, base_y=72)
# Add a secondary ridge hump to the right
_poly([(128+44, 26), (128+36, 72), (128+56, 72)], ROCK_4)
_poly([(128+44, 26), (128+44, 36), (128+54, 72), (128+56, 72)], ROCK_3)
_el(128+44, 29, 5, 5, SNOW)

# Frame 3  (x 192–255): Twin peaks — two close summits
draw_single_peak(192, peak_x=20, peak_y=11, half_w=19, base_y=73)
# Erase the gap between twins with background, so they look separate
_poly([
    (192+26, 14), (192+38, 14),
    (192+38, 70), (192+26, 70),
], BG)
draw_single_peak(192, peak_x=44, peak_y=8,  half_w=18, base_y=73)
# Fill base so no gap at bottom
_poly([(192+4, 73), (192+60, 73), (192+60, 80), (192+4, 80)], ROCK_4)

# ── Save ──────────────────────────────────────────────────────────────────────
img.save(OUT)
print(f"Saved {img.size[0]}×{img.size[1]} → {OUT}")
