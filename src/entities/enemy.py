"""Enemy class with data-driven vector rendering."""

import math
import pygame
from src.config import TILE, SCREEN_W, SCREEN_H
from src.effects import Particle
from src.rendering.animator import Animator, AnimationState
from src.world.collision import hits_blocking

# Player.COLLISION_HALF — kept as a module constant to avoid circular import.
_PLAYER_COLLISION_HALF: int = 20


def _clamp_color(
    base: tuple[int, int, int], offset: tuple[int, int, int]
) -> tuple[int, int, int]:
    """Clamp color values to 0-255."""
    return tuple(max(0, min(255, base[i] + offset[i])) for i in range(3))


class Enemy:
    """A data-driven enemy instance. Create with an enemy-type key."""

    # Class-level cache: (type_key, is_hurt_flash) → pre-rendered pygame.Surface.
    # Avoids creating a new Surface + redrawing every procedural fallback call.
    _proc_surface_cache: dict[tuple, "pygame.Surface"] = {}

    def __init__(self, x: float, y: float, type_key: str) -> None:
        from src.data import ENEMY_TYPES

        self.x = float(x)
        self.y = float(y)
        self.type_key = type_key
        info = ENEMY_TYPES[type_key]
        self.hp = info.hp
        self.max_hp = info.hp
        self.attack = info.attack
        self.speed = info.speed
        self.xp = info.xp
        self.color = info.color
        self.attack_cd = info.attack_cd
        self.draw_commands = info.draw_commands
        self.name = info.name
        self.chase_range = info.chase_range
        self.hitbox_radius: int = info.hitbox_radius

        self.state = "idle"
        self.cooldown = 0.0
        self.hurt_flash = 0
        self.knockback_vx = 0.0
        self.knockback_vy = 0.0
        self.facing_direction: str = "right"
        self._is_moving: bool = False
        self._is_attacking: bool = False

        # Sprite animator — lazily initialised from SpriteRegistry on first use.
        self._animator: Animator | None = None
        self._animator_checked: bool = False

    def _on_screen(self, cam_x: float, cam_y: float, margin: int = 0) -> bool:
        """Check if enemy is on screen."""
        return (
            cam_x - margin <= self.x <= cam_x + SCREEN_W + margin
            and cam_y - margin <= self.y <= cam_y + SCREEN_H + margin
        )

    def update(
        self,
        dt: float,
        px: float,
        py: float,
        cam_x: float,
        cam_y: float,
        world: list[list[int]],
        particles: list,
    ) -> None:
        """Update enemy state and position."""
        if self.hp <= 0:
            return

        # Knockback
        if abs(self.knockback_vx) > 0.1 or abs(self.knockback_vy) > 0.1:
            nx = self.x + self.knockback_vx * dt
            ny = self.y + self.knockback_vy * dt
            if not hits_blocking(world, nx, ny, self.hitbox_radius):
                self.x = nx
                self.y = ny
            self.knockback_vx *= 0.8
            self.knockback_vy *= 0.8

        if self.hurt_flash > 0:
            self.hurt_flash -= 1
        if self.cooldown > 0:
            self.cooldown -= dt

        dist = math.hypot(px - self.x, py - self.y)

        if self.state == "idle":
            trigger = self.chase_range if self.chase_range > 0 else None
            if trigger:
                if dist < trigger:
                    self.state = "chase"
            elif self._on_screen(cam_x, cam_y, margin=TILE * 2):
                self.state = "chase"

        elif self.state == "chase":
            moved = False
            if dist > 1:
                dx = (px - self.x) / dist
                dy = (py - self.y) / dist
                nx = self.x + dx * self.speed * dt
                ny = self.y + dy * self.speed * dt
                old_x, old_y = self.x, self.y
                if not hits_blocking(world, nx, self.y, self.hitbox_radius):
                    self.x = nx
                if not hits_blocking(world, self.x, ny, self.hitbox_radius):
                    self.y = ny
                moved = self.x != old_x or self.y != old_y
                # Update facing from dominant movement axis
                if abs(dy) >= abs(dx):
                    self.facing_direction = "down" if dy >= 0 else "up"
                else:
                    self.facing_direction = "right" if dx > 0 else "left"
            self._is_moving = moved
            if dist < self.hitbox_radius + _PLAYER_COLLISION_HALF:
                self.state = "attack"
            if dist > SCREEN_W and not self._on_screen(cam_x, cam_y, margin=TILE * 4):
                self.state = "idle"

        elif self.state == "attack":
            if dist > self.hitbox_radius + _PLAYER_COLLISION_HALF + 20:
                self.state = "chase"

        world_rows = len(world)
        world_cols = len(world[0]) if world_rows > 0 else 1
        self.x = max(TILE, min((world_cols - 1) * TILE, self.x))
        self.y = max(TILE, min((world_rows - 1) * TILE, self.y))

        # Expose state flags for sprite_draw() — animation is advanced there.
        # _is_moving is already set in the chase branch (True only if actually moved).
        if self.state != "chase":
            self._is_moving = False
        self._is_attacking = self.state == "attack"

    def try_attack(self, px: float, py: float) -> int:
        """Try to attack player. Returns damage if successful, 0 otherwise."""
        if self.hp <= 0 or self.state != "attack":
            return 0
        dist = math.hypot(px - self.x, py - self.y)
        if dist < self.hitbox_radius + _PLAYER_COLLISION_HALF and self.cooldown <= 0:
            self.cooldown = self.attack_cd
            return self.attack
        return 0

    def take_damage(
        self, amount: int, source_x: float, source_y: float, particles: list
    ) -> None:
        """Take damage and create damage-dealing particles."""
        self.hp -= amount
        self.hurt_flash = 8
        dx = self.x - source_x
        dy = self.y - source_y
        dist = max(1, math.hypot(dx, dy))
        self.knockback_vx = (dx / dist) * 6
        self.knockback_vy = (dy / dist) * 6
        for _ in range(6):
            particles.append(Particle(self.x, self.y, self.color))

    def _ensure_animator(self) -> None:
        """Lazy-load animator from SpriteRegistry the first time it is needed."""
        if self._animator_checked:
            return
        self._animator_checked = True
        from src.rendering.registry import SpriteRegistry

        self._animator = SpriteRegistry.get_instance().make_animator(self.type_key)

    def draw(self, surf: pygame.Surface, cam_x: float, cam_y: float) -> None:
        """Draw enemy — sprite blit when available, procedural fallback otherwise."""
        if self.hp <= 0:
            return
        sx = int(self.x - cam_x)
        sy = int(self.y - cam_y)
        surf_w, surf_h = surf.get_size()
        _margin = TILE * 2
        if (
            sx < -_margin
            or sx > surf_w + _margin
            or sy < -_margin
            or sy > surf_h + _margin
        ):
            return

        _TS: int = TILE // 32  # procedural scale factor (2 when TILE=64)

        # --- Sprite path ---
        self._ensure_animator()
        from src.rendering.sprite_draw import sprite_draw

        if sprite_draw(self, surf, cam_x, cam_y, dt=1.0):
            if self.hp < self.max_hp:
                bar_w = 24 * _TS
                bx = sx - bar_w // 2
                by = sy - 51 * _TS
                ratio = max(0.0, self.hp / self.max_hp)
                pygame.draw.rect(surf, (60, 60, 60), (bx, by, bar_w, 3 * _TS))
                pygame.draw.rect(
                    surf, (220, 40, 40), (bx, by, int(bar_w * ratio), 3 * _TS)
                )
            return

        # --- Procedural fallback: cached surface per (type_key, is_hurt_flash) ---
        is_hurt = self.hurt_flash > 0
        cache_key = (self.type_key, is_hurt)
        if cache_key not in Enemy._proc_surface_cache:
            base = (255, 255, 255) if is_hurt else self.color
            buf_sz = 64
            buf = pygame.Surface((buf_sz, buf_sz), pygame.SRCALPHA)
            buf.fill((0, 0, 0, 0))
            bx_c, by_c = buf_sz // 2, buf_sz // 2

            for cmd in self.draw_commands:
                shape = cmd[0]
                color_offset = cmd[1]
                c = _clamp_color(base, color_offset)
                args = cmd[2:]

                if shape == "circle":
                    cx_off, cy_off, radius = args
                    pygame.draw.circle(buf, c, (bx_c + cx_off, by_c + cy_off), radius)
                elif shape == "rect":
                    xo, yo, w, h = args
                    pygame.draw.rect(buf, c, (bx_c + xo, by_c + yo, w, h))
                elif shape == "ellipse":
                    xo, yo, w, h = args
                    pygame.draw.ellipse(buf, c, (bx_c + xo, by_c + yo, w, h))
                elif shape == "line":
                    x1, y1, x2, y2, width = args
                    pygame.draw.line(
                        buf, c, (bx_c + x1, by_c + y1), (bx_c + x2, by_c + y2), width
                    )
                elif shape == "polygon":
                    points_off = args[0]
                    pts = [(bx_c + px_off, by_c + py_off) for px_off, py_off in points_off]
                    pygame.draw.polygon(buf, c, pts)

            if _TS > 1:
                buf = pygame.transform.scale(buf, (buf_sz * _TS, buf_sz * _TS))
            Enemy._proc_surface_cache[cache_key] = buf

        buf = Enemy._proc_surface_cache[cache_key]
        surf.blit(buf, (sx - buf.get_width() // 2, sy - buf.get_height() // 2))

        if self.hp < self.max_hp:
            bar_w = 20 * _TS
            bx = sx - bar_w // 2
            by = sy - 16 * _TS
            ratio = max(0, self.hp / self.max_hp)
            pygame.draw.rect(surf, (60, 60, 60), (bx, by, bar_w, 3 * _TS))
            pygame.draw.rect(surf, (220, 40, 40), (bx, by, int(bar_w * ratio), 3 * _TS))
