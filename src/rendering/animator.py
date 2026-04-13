"""Animation state machine for sprite-sheet based entity rendering.

Each Animator instance owns a reference to a loaded sprite sheet and a
manifest that describes which row / column range corresponds to each named
animation state.

Manifest JSON schema
--------------------
{
  "frame_size": [width, height],
  "states": {
    "<state_name>": {
      "row":    <int>,      // 0-based row index in the sheet
      "frames": <int>,      // number of columns (frames) in this state
      "fps":    <float>     // playback speed in real frames-per-second
    },
    ...
  }
}

The sheet is laid out as rows (states) × columns (frames).  All cells in a
sheet share the same (width × height) dimensions from ``frame_size``.

Unified entity sheet layout (384×672 px, 96×96 cells):
  row 0 – idle      (4 frames @ 4 fps)
  row 1 – up        (4 frames @ 8 fps)
  row 2 – right     (4 frames @ 8 fps)
  row 3 – down      (4 frames @ 8 fps)
  row 4 – left      (4 frames @ 8 fps)  ← may be blank; engine auto-mirrors right
  row 5 – attacking (4 frames @ 8 fps)  ← blank for non-combat entities → idle fallback
  row 6 – damaged   (4 frames @ 4 fps)
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

import pygame

if TYPE_CHECKING:
    pass


class AnimationState(Enum):
    """Named animation states an entity can be in."""

    # Legacy states — kept for world-object and backward-compat usage
    IDLE = "idle"
    WALK = "walk"
    SWIM = "swim"
    HURT = "hurt"
    MOUNTED = "mounted"
    EXTENDING = "extending"

    # Unified directional states (new entity sprite format)
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"
    ATTACKING = "attacking"
    DAMAGED = "damaged"


# When the LEFT state is not present in the manifest, the Animator
# automatically mirrors the RIGHT state frames horizontally.
_FLIP_PAIRS: dict[AnimationState, AnimationState] = {
    AnimationState.LEFT: AnimationState.RIGHT,
}


class Animator:
    """Frame-rate-independent sprite animator driven by game ``dt`` values.

    ``dt`` is the normalised frame delta used throughout the codebase:
        dt = clock.tick(FPS) / 16.667
    so dt ≈ 1.0 at 60 fps.  Internally this is converted to milliseconds
    (ms = dt × 16.667) so that the per-state ``fps`` value in the manifest
    translates directly to real-world playback speed.

    Falls back gracefully: if the current state has no entry in the manifest
    ``current_frame()`` returns ``None`` (caller should use procedural draw).

    Auto-flip: if LEFT state is requested but absent from the manifest, RIGHT
    frames are returned horizontally mirrored.  Flipped surfaces are cached so
    the transform only happens once per unique (state, frame_index) pair.
    """

    def __init__(self, sheet: pygame.Surface, manifest: dict) -> None:
        self._sheet = sheet
        self._manifest = manifest
        fw, fh = manifest["frame_size"]
        self._fw: int = fw
        self._fh: int = fh

        self._state: AnimationState = AnimationState.IDLE
        self._frame_idx: int = 0
        self._elapsed_ms: float = 0.0

        # Cache for horizontally-flipped frames: (state, frame_idx) → Surface
        self._flip_cache: dict[tuple[AnimationState, int], pygame.Surface] = {}

    # ------------------------------------------------------------------
    # State control
    # ------------------------------------------------------------------

    def set_state(self, state: AnimationState) -> None:
        """Switch to *state* and reset frame counter if state changed.

        If *state* is not in the manifest but has a flip-pair partner that is,
        the switch still succeeds (current_frame will auto-mirror the partner).
        """
        if state == self._state:
            return
        partner = _FLIP_PAIRS.get(state)
        has_state = state.value in self._manifest["states"]
        has_partner = partner is not None and partner.value in self._manifest["states"]
        if has_state or has_partner:
            self._state = state
            self._frame_idx = 0
            self._elapsed_ms = 0.0

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update(self, dt: float) -> None:
        """Advance animation by *dt* game-frames (≈1.0 at 60 fps)."""
        # Use the flip partner's data for timing when the state itself is absent
        data = self._state_data(self._state)
        if data is None:
            partner = _FLIP_PAIRS.get(self._state)
            if partner is not None:
                data = self._state_data(partner)
        if data is None or data["frames"] <= 1:
            return

        fps: float = data.get("fps", 8.0)
        frame_duration_ms: float = 1000.0 / fps
        self._elapsed_ms += dt * 16.667

        if self._elapsed_ms >= frame_duration_ms:
            self._elapsed_ms -= frame_duration_ms
            self._frame_idx = (self._frame_idx + 1) % data["frames"]

    # ------------------------------------------------------------------
    # Read current frame
    # ------------------------------------------------------------------

    def current_frame(self) -> pygame.Surface | None:
        """Return the current frame surface, or *None* if state is unknown.

        If the current state is absent from the manifest but has a flip-pair
        partner (e.g. LEFT → RIGHT), the partner's frame is returned mirrored
        horizontally.  Mirrored surfaces are cached per (state, frame_idx) to
        avoid repeated transform calls.
        """
        data = self._state_data(self._state)
        flip_needed = False

        if data is None:
            partner = _FLIP_PAIRS.get(self._state)
            if partner is not None:
                data = self._state_data(partner)
                flip_needed = data is not None
        if data is None:
            # Try fallback to IDLE
            data = self._state_data(AnimationState.IDLE)
        if data is None:
            # Last resort: use whichever state exists first in the manifest
            data = next(iter(self._manifest["states"].values()), None)
        if data is None:
            return None

        row: int = data["row"]
        col: int = self._frame_idx % max(1, data["frames"])
        rect = pygame.Rect(col * self._fw, row * self._fh, self._fw, self._fh)
        try:
            frame = self._sheet.subsurface(rect)
        except ValueError:
            return None

        if not flip_needed:
            return frame

        # Return cached flipped version, creating it on first access
        cache_key = (self._state, col)
        cached = self._flip_cache.get(cache_key)
        if cached is None:
            cached = pygame.transform.flip(frame, True, False)
            self._flip_cache[cache_key] = cached
        return cached

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _state_data(self, state: AnimationState) -> dict | None:
        return self._manifest["states"].get(state.value)
