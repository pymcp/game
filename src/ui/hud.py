"""HUD rendering functions."""

import pygame
from src.config import SCREEN_W, SCREEN_H, TILE, WORLD_COLS, WORLD_ROWS, WHITE
from src.data import PICKAXES, WEAPONS


def draw_hud(
    screen: pygame.Surface, font: pygame.font.Font, player, workers: list, pets: list
) -> None:
    """Draw the HUD panel with core stats only. Inventory and equipment are in the menu."""
    p = player

    # Panel background
    panel_w = 220
    panel_h = 130
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
    pygame.draw.rect(screen, (60, 60, 60), (16, 44, hp_bar_w, 8))
    pygame.draw.rect(screen, (80, 180, 255), (16, 44, int(hp_bar_w * xp_ratio), 8))
    screen.blit(
        font.render(f"Lv {p.level}  XP: {p.xp}/{p.xp_next}", True, (180, 220, 255)),
        (16, 54),
    )

    y_off = 72

    # Current pickaxe
    pick = PICKAXES[p.pick_level]
    pygame.draw.rect(screen, pick["color"], (16, y_off + 1, 10, 10))
    pick_label = (
        pick["name"] if p.pick_level < len(PICKAXES) - 1 else f"{pick['name']} (MAX)"
    )
    screen.blit(font.render(pick_label, True, WHITE), (32, y_off))
    y_off += 18

    # Current weapon
    wpn = WEAPONS[p.weapon_level]
    pygame.draw.rect(screen, wpn["color"], (16, y_off + 1, 10, 10))
    wpn_label = (
        wpn["name"] if p.weapon_level < len(WEAPONS) - 1 else f"{wpn['name']} (MAX)"
    )
    screen.blit(font.render(wpn_label, True, WHITE), (32, y_off))
    y_off += 18

    # Workers / pets
    parts = []
    if workers:
        parts.append(f"Workers: {len(workers)}")
    num_cats = sum(1 for pet in pets if pet.kind == "cat")
    num_dogs = sum(1 for pet in pets if pet.kind == "dog")
    if num_cats:
        parts.append(f"Cats: {num_cats}")
    if num_dogs:
        parts.append(f"Dogs: {num_dogs}")
    if parts:
        screen.blit(font.render("  ".join(parts), True, (200, 220, 255)), (16, y_off))

    # Controls hint
    equip_key_name = pygame.key.name(p.controls.equip_key).upper()
    hint = f"WASD: Move | Space: Mine | F: Attack | U: Pick  N: Weapon | B: Build | {equip_key_name}: Inventory"
    hint_surf = font.render(hint, True, (180, 180, 180))
    screen.blit(hint_surf, (SCREEN_W // 2 - hint_surf.get_width() // 2, SCREEN_H - 26))


def draw_tooltip(
    screen: pygame.Surface,
    font: pygame.font.Font,
    cam_x: float,
    cam_y: float,
    world: list[list[int]],
    tile_hp: list[list[int]],
) -> None:
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
