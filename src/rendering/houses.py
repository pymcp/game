"""Procedural house tile renderer.

Draws settlement tiles at 32×32 base resolution into a pygame Surface.
The caller is responsible for scaling to TILE×TILE if needed.

Each tier corresponds to a settlement type:
  0 = Cottage, 1 = Hamlet, 2 = Village, 3 = Town, 4 = Large Town, 5 = City
"""

from __future__ import annotations

import math

import pygame


def draw_house_tile(
    screen: pygame.Surface,
    tx: int,
    ty: int,
    tier: int,
    n: bool,
    s: bool,
    e: bool,
    w: bool,
    ticks: int,
    tile_size: int,
) -> None:
    """Draw a house tile styled to its settlement tier.

    Renders into a 32×32 buffer then scales to *tile_size* × *tile_size* before
    blitting to *screen*.

    Args:
        screen:    Target surface to blit onto.
        tx, ty:    Top-left screen position.
        tier:      0=Cottage … 5=City.
        n, s, e, w: True if that direction has an adjacent house tile.
        ticks:     ``pygame.time.get_ticks()`` for animations.
        tile_size: Pixel size of one tile (TILE constant from config).
    """
    scale = tile_size // 32
    buf = pygame.Surface((32, 32), pygame.SRCALPHA)
    buf.fill((0, 0, 0, 0))
    draw_house_tile_32(buf, 0, 0, tier, n, s, e, w, ticks)
    if scale > 1:
        buf = pygame.transform.scale(buf, (tile_size, tile_size))
    screen.blit(buf, (tx, ty))


def draw_house_tile_32(
    sc: pygame.Surface,
    tx: int,
    ty: int,
    tier: int,
    n: bool,
    s: bool,
    e: bool,
    w: bool,
    ticks: int,
) -> None:
    """Draw a house tile at 32×32 base scale into *sc*."""

    if tier == 0:
        # -- Isolated Cottage --
        pygame.draw.rect(sc, (180, 120, 60), (tx + 4, ty + 12, 24, 18))
        pygame.draw.polygon(
            sc,
            (160, 40, 40),
            [(tx + 2, ty + 12), (tx + 16, ty + 2), (tx + 30, ty + 12)],
        )
        pygame.draw.rect(sc, (100, 60, 30), (tx + 12, ty + 19, 8, 11))
        pygame.draw.rect(sc, (180, 220, 255), (tx + 7, ty + 15, 5, 5))
        pygame.draw.rect(sc, (80, 60, 40), (tx + 7, ty + 15, 5, 5), 1)

    elif tier == 1:
        # -- Hamlet: warm cottage with chimney, wood grain, amber window --
        wall_c = (185, 130, 70)
        roof_c = (178, 55, 55)
        pygame.draw.rect(sc, wall_c, (tx + 3, ty + 11, 26, 19))
        # Wood-grain horizontal lines
        for ly in range(ty + 15, ty + 30, 4):
            pygame.draw.line(sc, (150, 100, 45), (tx + 3, ly), (tx + 29, ly), 1)
        # Roof
        if n:
            pygame.draw.rect(sc, roof_c, (tx + 3, ty + 7, 26, 5))
        else:
            pygame.draw.polygon(
                sc,
                roof_c,
                [(tx + 1, ty + 11), (tx + 16, ty + 1), (tx + 31, ty + 11)],
            )
        # Chimney
        pygame.draw.rect(sc, (120, 100, 85), (tx + 21, ty + 3, 4, 9))
        pygame.draw.rect(sc, (90, 80, 70), (tx + 20, ty + 2, 6, 3))
        # Door with arch top
        pygame.draw.rect(sc, (110, 65, 30), (tx + 12, ty + 21, 8, 9))
        pygame.draw.ellipse(sc, (110, 65, 30), (tx + 11, ty + 17, 10, 8))
        # Amber lit window
        pygame.draw.rect(sc, (255, 215, 120), (tx + 5, ty + 14, 5, 5))
        pygame.draw.rect(sc, (80, 60, 40), (tx + 5, ty + 14, 5, 5), 1)
        # Second window (right side)
        pygame.draw.rect(sc, (255, 215, 120), (tx + 22, ty + 14, 5, 5))
        pygame.draw.rect(sc, (80, 60, 40), (tx + 22, ty + 14, 5, 5), 1)
        # Path connectors on linked sides
        path_c = (175, 158, 128)
        if s:
            pygame.draw.rect(sc, path_c, (tx + 13, ty + 30, 6, 2))
        if e:
            pygame.draw.rect(sc, path_c, (tx + 30, ty + 22, 2, 5))
        if w:
            pygame.draw.rect(sc, path_c, (tx, ty + 22, 2, 5))

    elif tier == 2:
        # -- Village: row-house with brick walls, parapet, double windows --
        wall_c = (195, 105, 55)   # orange brick
        brick_c = (155, 78, 38)   # mortar / darker brick
        roof_c = (160, 82, 60)    # terracotta parapet
        # Wall extends to adjacent sides seamlessly
        lx = tx if w else tx + 3
        rx = tx + 32 if e else tx + 29
        ty2 = ty if n else ty + 6
        by2 = ty + 32 if s else ty + 30
        pygame.draw.rect(sc, wall_c, (lx, ty2, rx - lx, by2 - ty2))
        # Brick mortar lines
        for ly in range(ty2 + 5, by2, 5):
            pygame.draw.line(sc, brick_c, (lx, ly), (rx, ly), 1)
        # Parapet / roof on exposed north
        if not n:
            pygame.draw.rect(sc, roof_c, (lx, ty2 - 4, rx - lx, 5))
            for bx in range(lx, rx, 6):
                pygame.draw.rect(sc, (130, 65, 45), (bx, ty2 - 7, 4, 3))
        # Two windows side by side
        for win_x in (tx + 5, tx + 20):
            pygame.draw.rect(sc, (200, 225, 255), (win_x, ty + 10, 6, 8))
            pygame.draw.line(
                sc, (130, 100, 75), (win_x + 3, ty + 10), (win_x + 3, ty + 18), 1
            )
        # Arched doorway on south-exposed face
        if not s:
            pygame.draw.rect(sc, (105, 58, 28), (tx + 13, ty + 22, 6, 8))
            pygame.draw.ellipse(sc, (105, 58, 28), (tx + 11, ty + 18, 10, 8))

    elif tier == 3:
        # -- Town: stone walls, slate parapet with crenellations, 4-window grid --
        wall_c = (130, 125, 118)  # stone gray
        stone_c = (108, 104, 98)  # stone shadow
        roof_c = (88, 90, 102)    # slate
        lx = tx if w else tx + 2
        rx = tx + 32 if e else tx + 30
        ty2 = ty if n else ty + 3
        by2 = ty + 32 if s else ty + 30
        pygame.draw.rect(sc, wall_c, (lx, ty2, rx - lx, by2 - ty2))
        # Stone block texture (horizontal courses)
        for iy in range(ty2 + 6, by2, 7):
            pygame.draw.line(sc, stone_c, (lx, iy), (rx, iy), 1)
        # Vertical joints (offset each row)
        row_i = 0
        for iy in range(ty2 + 6, by2, 7):
            offset = 5 if row_i % 2 == 0 else 1
            for ix in range(lx + offset, rx, 10):
                pygame.draw.line(sc, stone_c, (ix, iy - 6), (ix, iy), 1)
            row_i += 1
        # Slate roof + crenellations on exposed north
        if not n:
            pygame.draw.rect(sc, roof_c, (lx, ty2 - 5, rx - lx, 6))
            for bx in range(lx, rx, 5):
                pygame.draw.rect(sc, (68, 70, 82), (bx, ty2 - 8, 3, 3))
        # 2×2 window grid
        win_c = (145, 175, 215)
        for wy, win_x in [
            (ty + 8, tx + 5),
            (ty + 8, tx + 19),
            (ty + 18, tx + 5),
            (ty + 18, tx + 19),
        ]:
            pygame.draw.rect(sc, win_c, (win_x, wy, 5, 6))
            pygame.draw.line(
                sc, (85, 110, 150), (win_x + 2, wy), (win_x + 2, wy + 6), 1
            )
            pygame.draw.line(
                sc, (85, 110, 150), (win_x, wy + 3), (win_x + 5, wy + 3), 1
            )
        # Recessed door
        if not s:
            pygame.draw.rect(sc, (55, 42, 28), (tx + 12, ty + 23, 8, 7))

    elif tier == 4:
        # -- Large Town: deep red brick, multi-row windows, iron roof, awning --
        wall_c = (158, 78, 65)  # deep red brick
        brick_c = (122, 55, 44)  # dark mortar
        roof_c = (55, 58, 68)   # iron grey
        lx = tx if w else tx + 1
        rx = tx + 32 if e else tx + 31
        ty2 = ty if n else ty + 2
        by2 = ty + 32 if s else ty + 31
        pygame.draw.rect(sc, wall_c, (lx, ty2, rx - lx, by2 - ty2))
        # Dense brick courses
        for iy in range(ty2 + 4, by2, 5):
            pygame.draw.line(sc, brick_c, (lx, iy), (rx, iy), 1)
        # Brick bonds (alternating vertical joints)
        row_i = 0
        for iy in range(ty2 + 4, by2, 5):
            offset = 4 if row_i % 2 == 0 else 0
            for ix in range(lx + offset, rx, 8):
                pygame.draw.line(sc, brick_c, (ix, iy - 4), (ix, iy), 1)
            row_i += 1
        # Iron roof parapet
        if not n:
            pygame.draw.rect(sc, roof_c, (lx, ty2 - 4, rx - lx, 5))
            for bx in range(lx, rx, 4):
                pygame.draw.rect(sc, (35, 38, 48), (bx, ty2 - 6, 2, 2))
        # 3 rows × 2 columns of windows
        win_c = (185, 205, 245)
        for wy in (ty + 4, ty + 13, ty + 22):
            for win_x in (tx + 5, tx + 21):
                pygame.draw.rect(sc, win_c, (win_x, wy, 5, 7))
                pygame.draw.line(
                    sc, (130, 150, 200), (win_x + 2, wy), (win_x + 2, wy + 7), 1
                )
                pygame.draw.line(
                    sc, (130, 150, 200), (win_x, wy + 3), (win_x + 5, wy + 3), 1
                )
        # Merchant awning on exposed south
        if not s:
            pygame.draw.rect(sc, (195, 85, 55), (tx + 3, ty + 24, 26, 3))
            for ax in range(tx + 3, tx + 29, 4):
                pygame.draw.line(
                    sc, (220, 100, 70), (ax, ty + 24), (ax + 2, ty + 27), 1
                )

    else:
        # -- City (tier 5): dark slate, gothic arch windows, spire --
        pulse = int(math.sin(ticks * 0.002) * 10)
        wall_c = (72, 78, 95)          # slate blue-grey
        stone_c = (56, 62, 78)         # deep shadow
        roof_c = (38, 42, 58)          # dark steel
        gold_c = (200, 170, 80 + pulse)  # animated gold trim
        lx = tx
        rx = tx + 32
        ty2 = ty
        by2 = ty + 32
        pygame.draw.rect(sc, wall_c, (lx, ty2, rx - lx, by2 - ty2))
        # Stone block grid
        for iy in range(ty2 + 5, by2, 6):
            for ix in range(lx, rx, 9):
                pygame.draw.rect(sc, stone_c, (ix, iy, 8, 5), 1)
        # Spire on exposed north
        if not n:
            mid = tx + 16
            pygame.draw.polygon(
                sc,
                roof_c,
                [
                    (mid - 3, ty2),
                    (mid + 3, ty2),
                    (mid + 1, ty2 - 9),
                    (mid - 1, ty2 - 9),
                ],
            )
            pygame.draw.polygon(
                sc,
                gold_c,
                [(mid - 1, ty2 - 9), (mid + 1, ty2 - 9), (mid, ty2 - 14)],
            )
            pygame.draw.rect(sc, roof_c, (lx, ty2 - 4, rx - lx, 5))
            # Gold crenellation trim
            for bx in range(lx, rx, 5):
                pygame.draw.rect(sc, gold_c, (bx, ty2 - 5, 3, 2))
        # Gothic arch windows (3 rows × 2 cols)
        win_c = (110, 145, 205)
        for wy in (ty + 3, ty + 13, ty + 21):
            for win_x in (tx + 4, tx + 21):
                # Arch body
                pygame.draw.rect(sc, win_c, (win_x, wy + 3, 6, 6))
                pygame.draw.ellipse(sc, win_c, (win_x, wy, 6, 6))
                # Gold arch trim
                pygame.draw.ellipse(sc, gold_c, (win_x, wy, 6, 6), 1)
        # Iron-bound door on exposed south
        if not s:
            pygame.draw.rect(sc, (40, 32, 22), (tx + 12, ty + 24, 8, 8))
            pygame.draw.ellipse(sc, (40, 32, 22), (tx + 11, ty + 20, 10, 8))
            pygame.draw.ellipse(sc, gold_c, (tx + 11, ty + 20, 10, 8), 1)
