"""Housing environment — generates interiors for houses and settlements."""

import random

from src.config import (
    MAP_BORDER,
    GRASS,
    TREE,
    SETTLEMENT_TIER_SIZES,
    SETTLEMENT_TIER_NAMES,
    WOOD_FLOOR,
    WOOD_WALL,
    WORKTABLE,
    HOUSE_EXIT,
    DIRT_PATH,
    STONE_PATH,
    COBBLESTONE,
    ROAD,
    SETTLEMENT_HOUSE,
)
from src.world.environments.base import BaseEnvironment
from src.world.map import GameMap

# ---------------------------------------------------------------------------
# Dimensions
# ---------------------------------------------------------------------------

# Tier-0 (single cottage): small room inside a yard
_COTTAGE_ROWS = 16
_COTTAGE_COLS = 16
# How many tiles of exterior yard to show around the building on each side
_COTTAGE_ROOM_OFFSET = 3

# Tier 1+ (settlement): map grows taller for larger settlements.
# Index matches tier (tier-0 unused here).
_SETTLEMENT_ROWS_BY_TIER = [16, 30, 36, 42, 54, 62]
_SETTLEMENT_COLS = 40

# How many sub-houses to place per settlement tier (index = tier, 0-based)
# Tier 0 is cottage — no sub-houses; tier 1+ use SETTLEMENT_TIER_SIZES[tier]
_SUB_HOUSE_COUNT = [0, 2, 4, 9, 16, 25]

# Path tile used for walkable ground inside each settlement tier.
# Index matches SETTLEMENT_TIER_NAMES: Cottage, Hamlet, Village, Town, Large Town, City
_TIER_PATH_TILE = [
    None,  # 0 Cottage   — no settlement paths
    DIRT_PATH,  # 1 Hamlet    — dirt paths
    STONE_PATH,  # 2 Village   — stone paths
    COBBLESTONE,  # 3 Town      — cobblestone paths
    COBBLESTONE,  # 4 Large Town — cobblestone paths
    ROAD,  # 5 City      — paved roads
]

# Probability that any exterior tile becomes a TREE (natural forest edge feel)
_EXTERIOR_TREE_DENSITY = 0.28

# Width (in tiles) of the main path for each tier
_TIER_PATH_WIDTH = [0, 1, 1, 2, 2, 3]

# Sub-house interior floor area (walls add 1 tile each side, exterior = interior + 2)
_SH_MIN_IW = 2  # minimum interior width
_SH_MIN_IH = 3  # minimum interior height
_SH_MAX_IW = 9  # maximum interior width
_SH_MAX_IH = 9  # maximum interior height
# Maximum exterior dimensions (used for column boundary checks)
_SH_MAX_EXT_W = _SH_MAX_IW + 2  # 11
_SH_MAX_EXT_H = _SH_MAX_IH + 2  # 11

# Distance from the path edge to the center column of a sub-house
_SIDE_OFFSET_1 = 6  # first column per side (all tiers)
_SIDE_OFFSET_2 = 14  # second column per side (Large Town / City only)


class HousingEnvironment(BaseEnvironment):
    """Generates a housing interior map seeded by its overland entrance position.

    Two layout modes:
      - Tier 0 (Cottage): small wood-walled room with a single WORKTABLE.
      - Tier 1+ (Hamlet → City): top-down settlement with paths, a main
        building containing the WORKTABLE, and N enterable SETTLEMENT_HOUSE
        tiles arranged along streets.
    """

    TILESET = "housing"

    def __init__(
        self,
        entry_col: int,
        entry_row: int,
        tier: int,
        exterior_tile: int = GRASS,
        sub_w: int | None = None,
        sub_h: int | None = None,
    ) -> None:
        self.entry_col = entry_col
        self.entry_row = entry_row
        self.tier = max(0, min(tier, len(SETTLEMENT_TIER_SIZES) - 1))
        self.exterior_tile = exterior_tile
        # When set, generate() produces a variable-sized sub-house interior
        self.sub_w = sub_w
        self.sub_h = sub_h

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self) -> GameMap:
        """Generate and return a fully configured housing GameMap."""
        rng = random.Random(self.entry_col * 10_000 + self.entry_row)

        if self.sub_w is not None and self.sub_h is not None:
            return self._generate_sub_house_interior(rng, self.sub_w, self.sub_h)
        if self.tier == 0:
            return self._generate_cottage(rng)
        return self._generate_settlement(rng)

    def spawn_enemies(self, game_map: GameMap) -> list:
        """No enemies inside housing environments."""
        return []

    # ------------------------------------------------------------------
    # Cottage layout (tier 0)
    # ------------------------------------------------------------------

    def _generate_cottage(self, rng: random.Random) -> GameMap:
        rows, cols = _COTTAGE_ROWS, _COTTAGE_COLS
        offset = _COTTAGE_ROOM_OFFSET
        wall_thickness = 2

        # Fill entire map with exterior terrain (grass/dirt/trees from overworld)
        world = [[self.exterior_tile] * cols for _ in range(rows)]

        # Room walls: a rectangle starting `offset` tiles from each edge
        room_top = offset
        room_bottom = rows - offset - 1
        room_left = offset
        room_right = cols - offset - 1
        for r in range(room_top, room_bottom + 1):
            for c in range(room_left, room_right + 1):
                world[r][c] = WOOD_WALL

        # Carve wood-floor interior (leaving wall_thickness walls on each side)
        for r in range(room_top + wall_thickness, room_bottom - wall_thickness + 1):
            for c in range(room_left + wall_thickness, room_right - wall_thickness + 1):
                world[r][c] = WOOD_FLOOR

        # Worktable in the center of the interior
        wt_row = (room_top + room_bottom) // 2
        wt_col = (room_left + room_right) // 2
        world[wt_row][wt_col] = WORKTABLE

        # Door cut into the south wall of the building.
        # Both wall layers at the door column are opened so the player can walk out.
        exit_col = (room_left + room_right) // 2
        exit_row = room_bottom  # outer south wall row — visible door tile
        world[exit_row][exit_col] = HOUSE_EXIT
        world[exit_row - 1][exit_col] = WOOD_FLOOR  # clear inner wall at doorway

        # Spawn at the last interior row (just inside the doorway)
        spawn_row = room_bottom - wall_thickness
        spawn_col = exit_col

        game_map = GameMap(world, tileset=self.TILESET)
        self._set_housing_attrs(
            game_map,
            rows=rows,
            cols=cols,
            exit_row=exit_row,
            exit_col=exit_col,
            spawn_row=spawn_row,
            spawn_col=spawn_col,
            worktable_row=wt_row,
            worktable_col=wt_col,
            sub_house_positions=[],
        )
        return game_map

    # ------------------------------------------------------------------
    # Settlement layout (tier 1+)
    # ------------------------------------------------------------------

    def _generate_settlement(self, rng: random.Random) -> GameMap:
        rows = _SETTLEMENT_ROWS_BY_TIER[self.tier]
        cols = _SETTLEMENT_COLS
        path_tile = _TIER_PATH_TILE[self.tier]
        path_width = _TIER_PATH_WIDTH[self.tier]
        border = MAP_BORDER

        path_col = cols // 2
        # Bounds of the main vertical path (1–3 tiles wide, centred on path_col)
        path_left = path_col - path_width // 2
        path_right = path_col + (path_width - 1) // 2

        # 1. Fill entire map with GRASS + scattered TREE (forested clearing feel)
        world = [[GRASS] * cols for _ in range(rows)]
        for r in range(rows):
            for c in range(cols):
                if rng.random() < _EXTERIOR_TREE_DENSITY:
                    world[r][c] = TREE

        # 2. Exit and spawn
        exit_row = rows - border  # sits in the southern border row
        exit_col = path_col
        spawn_row = exit_row - 1
        spawn_col = exit_col

        # 3. Determine sub-house column positions on each side of the main path.
        #    Large Town and City get two columns per side; others get one.
        use_two_cols = self.tier >= 4
        if use_two_cols:
            left_centers = [path_left - _SIDE_OFFSET_1, path_left - _SIDE_OFFSET_2]
            right_centers = [path_right + _SIDE_OFFSET_1, path_right + _SIDE_OFFSET_2]
        else:
            left_centers = [path_left - _SIDE_OFFSET_1]
            right_centers = [path_right + _SIDE_OFFSET_1]

        # Remove columns that would place the widest possible room outside the border.
        # We use the max half-width here; individual placement checks per actual width.
        max_half_w = _SH_MAX_EXT_W // 2
        left_centers = [c for c in left_centers if c - max_half_w >= border]
        right_centers = [c for c in right_centers if c + max_half_w < cols - border]
        all_centers = left_centers + right_centers
        houses_per_row = len(all_centers)

        n_sub = _SUB_HOUSE_COUNT[self.tier]
        n_rows_max = max(1, (n_sub + houses_per_row - 1) // houses_per_row)  # ceil div

        # Pre-generate a random (interior_w, interior_h) for every house slot.
        house_specs: list[tuple[int, int]] = [
            (
                rng.randint(_SH_MIN_IW, _SH_MAX_IW),
                rng.randint(_SH_MIN_IH, _SH_MAX_IH),
            )
            for _ in range(n_sub)
        ]

        # Compute the SETTLEMENT_HOUSE door row for every row-slot working upward
        # from the entrance.  Each row's height = max exterior height in that row + gap.
        _gap = 2
        first_sh_row = exit_row - 5
        sh_rows: list[int] = []
        cur_sh = first_sh_row
        for row_idx in range(n_rows_max):
            start = row_idx * houses_per_row
            row_specs = house_specs[start : start + houses_per_row]
            if not row_specs:
                break
            max_ext_h = max(ih + 2 for _, ih in row_specs)
            room_top_check = cur_sh - (max_ext_h - 1)
            if room_top_check < border + 1:
                break
            sh_rows.append(cur_sh)
            cur_sh -= max_ext_h + _gap

        # 4. Draw the narrow main vertical path from just past the top border
        #    all the way down to the exit row.
        for r in range(border + 1, exit_row):
            for c in range(path_left, path_right + 1):
                world[r][c] = path_tile

        # 5. Place sub-houses in rows from the entrance upward.
        #    The FIRST house placed (closest to entrance, left side) is the craft house
        #    and gets a WORKTABLE placed at the centre of its interior.
        sub_house_positions: list[tuple[int, int, int, int]] = []
        placed = 0
        wt_row = border + 2  # fallback — should always be overwritten below
        wt_col = path_col

        for row_idx, sh_row in enumerate(sh_rows):
            row_start = row_idx * houses_per_row

            for col_slot, c_center in enumerate(all_centers):
                spec_idx = row_start + col_slot
                if spec_idx >= n_sub:
                    break

                iw, ih = house_specs[spec_idx]
                ext_w = iw + 2
                ext_h = ih + 2
                room_left = c_center - ext_w // 2
                room_right = room_left + ext_w - 1
                room_top = sh_row - (ext_h - 1)

                if room_left < border or room_right >= cols - border:
                    continue
                if room_top < border + 1:
                    continue

                # Carve the sub-house room with its actual random dimensions
                self._carve_room(
                    world,
                    room_top,
                    room_left,
                    ext_h,
                    ext_w,
                    WOOD_WALL,
                    WOOD_FLOOR,
                )
                # SETTLEMENT_HOUSE in south wall; open the inner-wall row for entry
                world[sh_row][c_center] = SETTLEMENT_HOUSE
                world[sh_row - 1][c_center] = WOOD_FLOOR

                # First sub-house placed gets the WORKTABLE (interior centre tile)
                if placed == 0:
                    wt_row = room_top + ext_h // 2
                    wt_col = c_center
                    world[wt_row][wt_col] = WORKTABLE

                # Horizontal connector one row BELOW the south wall so the wall
                # remains fully intact.  Runs from the main path out to directly
                # south of the door, meeting it from below.
                if (
                    c_center < path_col
                ):  # left side — path runs east from door to main path
                    for cc in range(c_center, path_left):
                        world[sh_row + 1][cc] = path_tile
                else:  # right side — path runs west from main path to door
                    for cc in range(path_right + 1, c_center + 1):
                        world[sh_row + 1][cc] = path_tile

                # Store col, row, and interior dimensions for interior generation
                sub_house_positions.append((c_center, sh_row, iw, ih))
                placed += 1

            if placed >= n_sub:
                break

        # 7. Restore HOUSE_EXIT (path drawing may have overwritten it)
        world[exit_row][exit_col] = HOUSE_EXIT

        game_map = GameMap(world, tileset=self.TILESET)
        self._set_housing_attrs(
            game_map,
            rows=rows,
            cols=cols,
            exit_row=exit_row,
            exit_col=exit_col,
            spawn_row=spawn_row,
            spawn_col=spawn_col,
            worktable_row=wt_row,
            worktable_col=wt_col,
            sub_house_positions=sub_house_positions,
        )
        return game_map

    # ------------------------------------------------------------------
    # Sub-house interior (variable-sized room entered from a settlement)
    # ------------------------------------------------------------------

    def _generate_sub_house_interior(
        self, rng: random.Random, interior_w: int, interior_h: int
    ) -> GameMap:
        """Generate a small interior room for a settlement sub-house.

        The map is just large enough for the room plus a small border so
        the camera has somewhere to sit.  The exterior pad is filled with
        GRASS (unreachable through walls) for a clean look.
        """
        pad = 3
        ext_w = interior_w + 2
        ext_h = interior_h + 2
        cols = ext_w + 2 * pad
        rows = ext_h + 2 * pad

        world = [[GRASS] * cols for _ in range(rows)]

        room_top = pad
        room_left = pad
        room_bottom = pad + ext_h - 1
        room_right = pad + ext_w - 1

        # Walls then floor
        for r in range(room_top, room_bottom + 1):
            for c in range(room_left, room_right + 1):
                world[r][c] = WOOD_WALL
        for r in range(room_top + 1, room_bottom):
            for c in range(room_left + 1, room_right):
                world[r][c] = WOOD_FLOOR

        # Worktable in the centre (skip if room is too small for it to be surrounded)
        wt_row = (room_top + room_bottom) // 2
        wt_col = (room_left + room_right) // 2
        if interior_w >= 3 and interior_h >= 3:
            world[wt_row][wt_col] = WORKTABLE

        # Door in the south wall
        exit_col = (room_left + room_right) // 2
        exit_row = room_bottom
        world[exit_row][exit_col] = HOUSE_EXIT
        world[exit_row - 1][exit_col] = WOOD_FLOOR  # open inner wall

        spawn_row = exit_row - 1
        spawn_col = exit_col

        game_map = GameMap(world, tileset=self.TILESET)
        self._set_housing_attrs(
            game_map,
            rows=rows,
            cols=cols,
            exit_row=exit_row,
            exit_col=exit_col,
            spawn_row=spawn_row,
            spawn_col=spawn_col,
            worktable_row=wt_row,
            worktable_col=wt_col,
            sub_house_positions=[],
        )
        return game_map

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _carve_room(
        world: list[list[int]],
        top_row: int,
        left_col: int,
        h: int,
        w: int,
        wall_tile: int,
        floor_tile: int,
    ) -> None:
        """Fill a rectangle with wall_tile, then carve the interior with floor_tile."""
        for r in range(top_row, top_row + h):
            for c in range(left_col, left_col + w):
                world[r][c] = wall_tile
        for r in range(top_row + 1, top_row + h - 1):
            for c in range(left_col + 1, left_col + w - 1):
                world[r][c] = floor_tile

    @staticmethod
    def _set_housing_attrs(
        game_map: GameMap,
        rows: int,
        cols: int,
        exit_row: int,
        exit_col: int,
        spawn_row: int,
        spawn_col: int,
        worktable_row: int,
        worktable_col: int,
        sub_house_positions: list[tuple],
    ) -> None:
        """Attach all housing-specific attributes to the GameMap."""
        game_map.exit_row = exit_row
        game_map.exit_col = exit_col
        game_map.spawn_row = spawn_row
        game_map.spawn_col = spawn_col
        game_map.worktable_row = worktable_row
        game_map.worktable_col = worktable_col
        game_map.sub_house_positions = sub_house_positions
        # housing_tier is set externally after generate() so we default to 0 here;
        # callers (game.py) will set it via game_map.housing_tier = tier.
