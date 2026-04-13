"""HUD rendering functions."""

import pygame
from src.config import SCREEN_W, SCREEN_H, TILE, WORLD_COLS, WORLD_ROWS, WHITE
from src.data import PICKAXES, WEAPONS, WEAPON_UNLOCK_COSTS, UPGRADE_COSTS, TILE_INFO


def draw_hud(screen, font, player, workers, pets):
    """Draw the HUD panel with inventory, stats, and controls."""
    p = player
    inv = p.inventory

    # Panel background
    panel_w = 220
    panel_h = 20 + max(1, len(inv)) * 20 + 200
    panel_surf = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
    panel_surf.fill((20, 20, 30, 180))
    screen.blit(panel_surf, (10, 10))

    # HP bar
    hp_ratio = max(0, p.hp / p.max_hp)
    hp_bar_w = 200
    pygame.draw.rect(screen, (60, 60, 60), (16, 16, hp_bar_w, 10))
    bar_col = (
        (50, 200, 50)
        if hp_ratio > 0.5
        else (220, 180, 30) if hp_ratio > 0.25 else (220, 40, 40)
    )
    pygame.draw.rect(screen, bar_col, (16, 16, int(hp_bar_w * hp_ratio), 10))
    screen.blit(font.render(f"HP: {p.hp:.0f}/{p.max_hp}", True, WHITE), (16, 28))

    # XP bar
    xp_ratio = p.xp / p.xp_next if p.xp_next > 0 else 0
    xp_bar_w = 200
    pygame.draw.rect(screen, (60, 60, 60), (16, 44, xp_bar_w, 8))
    pygame.draw.rect(screen, (80, 180, 255), (16, 44, int(xp_bar_w * xp_ratio), 8))
    screen.blit(
        font.render(f"Lv {p.level}  XP: {p.xp}/{p.xp_next}", True, (180, 220, 255)),
        (16, 54),
    )

    # Pickaxe
    pick = PICKAXES[p.pick_level]
    pygame.draw.rect(screen, pick["color"], (16, 74, 12, 12))
    screen.blit(font.render(pick["name"], True, WHITE), (34, 72))

    # Inventory
    y_off = 96
    if inv:
        for item_name, count in sorted(inv.items()):
            info_color = WHITE
            for tinfo in TILE_INFO.values():
                if tinfo["drop"] == item_name and tinfo["drop_color"]:
                    info_color = tinfo["drop_color"]
                    break
            pygame.draw.rect(screen, info_color, (18, y_off + 2, 8, 8))
            screen.blit(font.render(f"{item_name}: {count}", True, WHITE), (34, y_off))
            y_off += 20
    else:
        screen.blit(font.render("(empty)", True, (150, 150, 150)), (34, y_off))
        y_off += 20

    # Pickaxe upgrade hint
    y_off += 6
    if p.pick_level < len(PICKAXES) - 1:
        cost = UPGRADE_COSTS[p.pick_level]
        cost_str = ", ".join(f"{v} {k}" for k, v in cost.items())
        can = all(inv.get(k, 0) >= v for k, v in cost.items())
        color = (100, 255, 100) if can else (180, 180, 180)
        screen.blit(font.render(f"[U] Upgrade: {cost_str}", True, color), (18, y_off))
    else:
        screen.blit(font.render("Pick is MAX level!", True, (255, 215, 0)), (18, y_off))
    y_off += 20

    # Build house hint
    can_build = inv.get("Dirt", 0) >= 20
    screen.blit(
        font.render(
            "[B] Build House: 20 Dirt",
            True,
            (100, 255, 100) if can_build else (180, 180, 180),
        ),
        (18, y_off),
    )
    y_off += 20

    # Weapon info
    wpn = WEAPONS[p.weapon_level]
    pygame.draw.rect(screen, wpn["color"], (18, y_off + 2, 8, 8))
    screen.blit(font.render(f"[F/RClick] {wpn['name']}", True, WHITE), (34, y_off))
    y_off += 20
    if p.weapon_level < len(WEAPONS) - 1:
        wcost = WEAPON_UNLOCK_COSTS[p.weapon_level]
        wcost_str = ", ".join(f"{v} {k}" for k, v in wcost.items())
        wcan = all(inv.get(k, 0) >= v for k, v in wcost.items())
        screen.blit(
            font.render(
                f"[N] Next Weapon: {wcost_str}",
                True,
                (100, 255, 100) if wcan else (180, 180, 180),
            ),
            (18, y_off),
        )
    else:
        screen.blit(
            font.render("Weapon is MAX level!", True, (255, 215, 0)), (18, y_off)
        )
    y_off += 20

    # Worker & pet count
    if workers:
        screen.blit(
            font.render(f"Workers: {len(workers)}", True, (100, 220, 255)), (18, y_off)
        )
        y_off += 20
    num_cats = sum(1 for pet in pets if pet.kind == "cat")
    num_dogs = sum(1 for pet in pets if pet.kind == "dog")
    if num_cats or num_dogs:
        parts = []
        if num_cats:
            parts.append(f"Cats: {num_cats}")
        if num_dogs:
            parts.append(f"Dogs: {num_dogs}")
        screen.blit(font.render("  ".join(parts), True, (255, 200, 100)), (18, y_off))

    # Controls hint
    hint = "WASD: Move | Click/Space: Mine | F/RClick: Attack | U/N: Upgrade | B: Build"
    hint_surf = font.render(hint, True, (180, 180, 180))
    screen.blit(hint_surf, (SCREEN_W // 2 - hint_surf.get_width() // 2, SCREEN_H - 26))


def draw_tooltip(screen, font, cam_x, cam_y, world, tile_hp):
    """Draw tile hover tooltip."""
    from src.data import TILE_INFO

    mx, my = pygame.mouse.get_pos()
    hover_col = int((mx + cam_x) // TILE)
    hover_row = int((my + cam_y) // TILE)
    if 0 <= hover_col < WORLD_COLS and 0 <= hover_row < WORLD_ROWS:
        tid = world[hover_row][hover_col]
        info = TILE_INFO[tid]
        tip = info["name"]
        if info["mineable"]:
            tip += f"  (HP: {tile_hp[hover_row][hover_col]:.0f}/{info['hp']})"
        tip_surf = font.render(tip, True, WHITE)
        tip_bg = pygame.Surface(
            (tip_surf.get_width() + 10, tip_surf.get_height() + 6), pygame.SRCALPHA
        )
        tip_bg.fill((0, 0, 0, 160))
        screen.blit(tip_bg, (mx + 14, my + 2))
        screen.blit(tip_surf, (mx + 19, my + 5))
