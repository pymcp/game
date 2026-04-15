#!/usr/bin/env python3
"""Generate assets/tiles/standalone/tree.png — 4-variant top-down pixel-art trees.

Canvas  : 192 × 96 px  (4 frames × 48 px wide, 96 px tall)
Palette : #CC33BB background (stripped by engine), 4-tone green canopy, brown trunk
"""

from PIL import Image, ImageDraw

# ── Colour palette ─────────────────────────────────────────────────────────────
BG        = (204,  51, 187)   # #CC33BB  — engine strips this colour
HIGHLIGHT = ( 93, 179,  61)   # #5DB33D  — lit crown
MID       = ( 58, 140,  34)   # #3A8C22  — main canopy
SHADOW_G  = ( 34,  96,  26)   # #22601A  — shaded side
DARK      = ( 26,  74,  16)   # #1A4A10  — outer edge
TRUNK_LT  = (122,  75,  30)   # #7A4B1E  — lit side of trunk
TRUNK_DK  = ( 90,  52,  18)   # #5A3412  — shadow side of trunk

FW, FH = 48, 96
OUT    = "assets/tiles/standalone/tree.png"

img   = Image.new("RGB", (FW * 4, FH), BG)
draw  = ImageDraw.Draw(img)


def _el(ox: int, cx: int, cy: int, rx: int, ry: int, colour: tuple) -> None:
    draw.ellipse([ox + cx - rx, cy - ry, ox + cx + rx, cy + ry], fill=colour)


def _rc(ox: int, x1: int, y1: int, x2: int, y2: int, colour: tuple) -> None:
    draw.rectangle([ox + x1, y1, ox + x2, y2], fill=colour)


def draw_tree(
    ox: int,
    cx: int, cy: int,
    rx: int, ry: int,
    lx: int = -1, ly: int = -2,
) -> None:
    """
    Render one tree frame at x-offset *ox*.

    cx, cy  — canopy ellipse centre in frame coords
    rx, ry  — outer canopy radii
    lx, ly  — per-layer shift toward the light source
               negative lx  = lean left (light from upper-left)
               positive lx  = lean right
    """
    # ── Trunk ──────────────────────────────────────────────────────────────────
    # Draw behind canopy so only the bottom peeks out.
    trunk_top = cy + ry - 6
    _rc(ox, cx - 3, trunk_top, cx + 3, FH - 1, TRUNK_LT)   # full trunk: light
    _rc(ox, cx,     trunk_top, cx + 3, FH - 1, TRUNK_DK)   # right half: shadow

    # ── Canopy — 4 nested ellipses shifting toward the highlight corner ─────────
    #   Each successive ellipse is ~80 % of the previous and stepped by (lx, ly)
    #   so the bright spot migrates toward the upper-left/right (per lx sign).
    _el(ox, cx,        cy,        rx,             ry,            DARK)
    _el(ox, cx + lx,   cy + ly,   int(rx * 0.82), int(ry * 0.82), SHADOW_G)
    _el(ox, cx + lx*2, cy + ly*2, int(rx * 0.63), int(ry * 0.63), MID)
    _el(ox, cx + lx*3, cy + ly*3, int(rx * 0.38), int(ry * 0.40), HIGHLIGHT)

    # ── Fine leaf-cluster bumps on the outer ring ───────────────────────────────
    # Small darker ellipses around the silhouette give an organic, leafy edge.
    import math
    bump_r = max(3, rx // 4)
    for angle_deg in range(20, 360, 55):
        a = math.radians(angle_deg)
        bx = cx + int(rx * math.cos(a))
        by = cy + int(ry * math.sin(a))
        _el(ox, bx, by, bump_r, max(2, bump_r - 1), DARK)
        # Brighten upper-left bumps slightly to enhance 3-D illusion
        if math.cos(a) < -0.3 and math.sin(a) < -0.3:
            _el(ox, bx, by, max(1, bump_r - 2), max(1, bump_r - 2), SHADOW_G)


# ── Four distinct variants ─────────────────────────────────────────────────────

# Frame 0  (x 0–47): tall & narrow, leans left
#           cy=47 + ry=35 → canopy bottom y=82, ~13 px trunk visible
draw_tree(  0, cx=20, cy=47, rx=12, ry=35, lx=-1, ly=-2)

# Frame 1  (x 48–95): short & wide, symmetrical
#           cy=59 + ry=24 → canopy bottom y=83, ~12 px trunk visible
draw_tree( 48, cx=24, cy=59, rx=21, ry=24, lx=-1, ly=-3)

# Frame 2  (x 96–143): medium, leans right  (highlight on upper-right)
#           cy=53 + ry=30 → canopy bottom y=83, ~12 px trunk visible
draw_tree( 96, cx=27, cy=53, rx=15, ry=30, lx=+1, ly=-2)

# Frame 3  (x 144–191): large & full round
#           cy=52 + ry=34 → canopy bottom y=86, ~9 px trunk visible
draw_tree(144, cx=24, cy=52, rx=22, ry=34, lx=-2, ly=-3)

# ── Save ───────────────────────────────────────────────────────────────────────
img.save(OUT)
print(f"Saved {img.size[0]}×{img.size[1]} → {OUT}")
