"""Unified sprite-draw helper for all entity types.

``sprite_draw`` is a standalone function that handles the common logic of:
  - mapping an entity's ``facing_direction`` and state to an ``AnimationState``
  - advancing the animator
  - blitting the current frame centred on the entity's screen position

Any entity that has the following attributes can use it:
  Required:
    x, y             : float  — world position
    _animator        : Animator | None
    facing_direction : str    — one of "up", "down", "left", "right"
  Optional:
    hurt_flash       : int    — when > 0 the DAMAGED state is used
    hurt_timer       : float  — alternate hurt indicator (Player uses this)
    _is_moving       : bool   — when False / absent, IDLE is used instead of
                                a directional state
    _is_attacking    : bool   — when True, ATTACKING state is preferred

Returns True if a sprite frame was blitted, False if the caller should fall
through to its procedural draw code.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from src.rendering.animator import AnimationState

if TYPE_CHECKING:
    from src.rendering.animator import Animator

# Mapping from facing_direction string → AnimationState for walking frames
_DIR_TO_STATE: dict[str, AnimationState] = {
    "up": AnimationState.UP,
    "down": AnimationState.DOWN,
    "left": AnimationState.LEFT,
    "right": AnimationState.RIGHT,
}


def sprite_draw(
    entity: object,
    surf: pygame.Surface,
    cam_x: float,
    cam_y: float,
    dt: float,
) -> bool:
    """Draw *entity* using its sprite animator if available.

    The animator must have already been loaded (``_ensure_animator`` called).
    This function only operates on ``entity._animator``; it never loads sprites.

    Args:
        entity:  Any entity object satisfying the documented attribute contract.
        surf:    Surface to draw onto (the viewport subsurface).
        cam_x:   Camera scroll offset X (world-space).
        cam_y:   Camera scroll offset Y (world-space).
        dt:      Frame delta (≈1.0 at 60 fps) used to advance animation.

    Returns:
        True  — sprite frame was blitted; caller should not draw procedurally.
        False — no animator / no frame; caller should use procedural fallback.
    """
    animator: Animator | None = getattr(entity, "_animator", None)
    if animator is None:
        return False

    # --- Determine animation state ---
    hurt = getattr(entity, "hurt_flash", 0) or (
        getattr(entity, "hurt_timer", 0.0) > 0
    )
    attacking = getattr(entity, "_is_attacking", False)
    is_moving = getattr(entity, "_is_moving", True)  # default True for entities that
    #                                                    don't track this explicitly

    if hurt:
        state = AnimationState.DAMAGED
    elif attacking:
        state = AnimationState.ATTACKING
    elif not is_moving:
        state = AnimationState.IDLE
    else:
        facing: str = getattr(entity, "facing_direction", "right")
        state = _DIR_TO_STATE.get(facing, AnimationState.RIGHT)

    animator.set_state(state)
    animator.update(dt)
    frame = animator.current_frame()
    if frame is None:
        return False

    sx = int(entity.x - cam_x)  # type: ignore[attr-defined]
    sy = int(entity.y - cam_y)  # type: ignore[attr-defined]
    fw, fh = frame.get_size()
    surf.blit(frame, (sx - fw // 2, sy - fh // 2))
    return True
