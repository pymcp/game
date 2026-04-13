"""Game state serialization — save on exit, load on startup."""

import json
import os
from typing import TYPE_CHECKING

from src.world.map import GameMap
from src.world.scene import MapScene
from src.config import BiomeType
from src.entities.player import (
    Player,
    ControlScheme,
    CONTROL_SCHEME_PLAYER1,
    CONTROL_SCHEME_PLAYER2,
)
from src.entities.worker import Worker
from src.entities.pet import Pet
from src.entities.enemy import Enemy
from src.entities.creature import Creature
from src.entities.sea_creature import SeaCreature
from src.entities.overland_creature import OverlandCreature

if TYPE_CHECKING:
    from src.game import Game

SAVE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "save.json")
SAVE_VERSION = 10


# ---------------------------------------------------------------------------
# Map key encoding (JSON only allows string keys)
# ---------------------------------------------------------------------------


def _key_to_str(key: str | tuple) -> str:
    """Convert a map dict key to a JSON-safe string."""
    if key == "overland":
        return "overland"
    if isinstance(key, tuple):
        if len(key) == 3 and key[0] == "sector":
            return f"sector:{key[1]}:{key[2]}"
        if len(key) == 3 and key[0] == "underwater":
            return f"underwater:{key[1]}:{key[2]}"
        if len(key) == 2:
            return f"cave:{key[0]}:{key[1]}"
        if len(key) == 3 and key[0] == "house":
            return f"house:{key[1]}:{key[2]}"
        if len(key) == 4 and key[0] == "house_sub":
            return f"house_sub:{key[1]}:{key[2]}:{key[3]}"
    return str(key)


def _str_to_key(s: str) -> str | tuple:
    """Decode a serialized map key string back to the original dict key."""
    if s == "overland":
        return "overland"
    if s.startswith("sector:"):
        _, sx, sy = s.split(":")
        return ("sector", int(sx), int(sy))
    if s.startswith("underwater:"):
        _, col, row = s.split(":")
        return ("underwater", int(col), int(row))
    if s.startswith("cave:"):
        _, col, row = s.split(":")
        return (int(col), int(row))
    if s.startswith("house:"):
        _, col, row = s.split(":")
        return ("house", int(col), int(row))
    if s.startswith("house_sub:"):
        parts = s.split(":")
        return ("house_sub", int(parts[1]), int(parts[2]), int(parts[3]))
    return s


def _player_map_key_to_str(key: str | tuple) -> str:
    """Serialize player.current_map (same encoding as map keys)."""
    return _key_to_str(key)


def _str_to_player_map_key(s: str) -> str | tuple:
    return _str_to_key(s)


# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------

# Optional attributes that cave/underwater maps carry (not present on all maps)
_MAP_EXTRA_ATTRS = (
    "entrance_col",
    "entrance_row",
    "exit_col",
    "exit_row",
    "spawn_col",
    "spawn_row",
    "chest_col",
    "chest_row",
    "cave_style",
    "dive_col",
    "dive_row",
    "portal_col",
    "portal_row",
    "ritual_stone_positions",
    "portal_guardian_spawned",
    "origin_sx",
    "origin_sy",
    "slot_size",
    "slot_padding",
    "slot_cols",
    "slot_rows",
    "housing_tier",
    "worktable_col",
    "worktable_row",
)
# origin_map is a map key (string or tuple) — encoded/decoded via key helpers


def _serialize_map(game_map: "GameMap | MapScene") -> dict:
    """Serialize a GameMap (or MapScene proxy) to a JSON-serializable dict."""
    # If we got a MapScene, extract the underlying raw GameMap for tile data,
    # and collect entities from the scene-level lists.
    if isinstance(game_map, MapScene):
        raw: GameMap = object.__getattribute__(game_map, "map")
        scene_enemies = game_map.enemies
        scene_workers = game_map.workers
        scene_pets = game_map.pets
        scene_creatures = game_map.creatures
    else:
        raw = game_map
        scene_enemies = getattr(game_map, "enemies", [])
        scene_workers = []
        scene_pets = []
        scene_creatures = []
    # town_clusters uses (row, col) tuple keys — encode as "row:col" strings
    tc = {f"{r}:{c}": v for (r, c), v in raw.town_clusters.items()}
    enemies = [_serialize_enemy(e) for e in scene_enemies]
    data = {
        "world": raw.world,
        "tileset": raw.tileset,
        "biome": raw.biome.value,
        "tile_hp": raw.tile_hp,
        "town_clusters": tc,
        "enemies": enemies,
        "workers": [_serialize_worker(w) for w in scene_workers],
        "pets": [_serialize_pet(p) for p in scene_pets],
        "creatures": [_serialize_creature(c) for c in scene_creatures],
    }
    # Persist map-specific attributes when present
    for attr in _MAP_EXTRA_ATTRS:
        if hasattr(raw, attr):
            data[attr] = getattr(raw, attr)
    if hasattr(raw, "origin_map"):
        data["origin_map"] = _key_to_str(raw.origin_map)
    if hasattr(raw, "sub_house_positions"):
        data["sub_house_positions"] = [list(entry) for entry in raw.sub_house_positions]
    if hasattr(raw, "portal_exits"):
        data["portal_exits"] = {
            f"{c}:{r}": (_key_to_str(v) if v is not None else None)
            for (c, r), v in raw.portal_exits.items()
        }
    # Sky-ladder quest data (overland map only)
    if getattr(raw, "sign_texts", {}):
        data["sign_texts"] = {
            f"{c}:{r}": text for (c, r), text in raw.sign_texts.items()
        }
    if getattr(raw, "ladder_repaired", False):
        data["ladder_repaired"] = raw.ladder_repaired
    if getattr(raw, "ladder_col", -1) >= 0:
        data["ladder_col"] = raw.ladder_col
        data["ladder_row"] = raw.ladder_row
    return data


def _serialize_player(player: Player) -> dict:
    return {
        "x": player.x,
        "y": player.y,
        "player_id": player.player_id,
        "color": list(player.color),
        "pick_level": player.pick_level,
        "weapon_id": player.weapon_id,
        "unlocked_weapons": player.unlocked_weapons,
        "inventory": player.inventory,
        "hp": player.hp,
        "max_hp": player.max_hp,
        "xp": player.xp,
        "level": player.level,
        "xp_next": player.xp_next,
        "facing_dx": player.facing_dx,
        "facing_dy": player.facing_dy,
        "auto_mine": player.auto_mine,
        "auto_fire": player.auto_fire,
        "on_boat": player.on_boat,
        "boat_col": player.boat_col,
        "boat_row": player.boat_row,
        "current_map": _player_map_key_to_str(player.current_map),
        "portal_origin_map": (
            _key_to_str(player.portal_origin_map)
            if player.portal_origin_map is not None
            else None
        ),
        "last_portal_exit_map": (
            _key_to_str(player.last_portal_exit_map)
            if player.last_portal_exit_map is not None
            else None
        ),
        "last_portal_exit_x": player.last_portal_exit_x,
        "last_portal_exit_y": player.last_portal_exit_y,
        "is_dead": player.is_dead,
        "equipment": player.equipment,
        "durability": player.durability,
        "on_mount": False,  # mount state is transient — always cleared on save
    }


def _serialize_worker(worker: Worker) -> dict:
    return {
        "x": worker.x,
        "y": worker.y,
        "player_id": worker.player_id,
        "speed": worker.speed,
        "body_color": list(worker.body_color),
        "skin_color": list(worker.skin_color),
        "hat_color": list(worker.hat_color),
        "size_mod": worker.size_mod,
        "home_map": _key_to_str(worker.home_map),
    }


def _serialize_pet(pet: Pet) -> dict:
    return {
        "x": pet.x,
        "y": pet.y,
        "kind": pet.kind,
        "speed": pet.speed,
        "body_color": list(pet.body_color),
        "eye_color": list(pet.eye_color),
        "size": pet.size,
        "spot_color": list(pet.spot_color),
        "follow_offset_x": pet.follow_offset_x,
        "follow_offset_y": pet.follow_offset_y,
        "home_map": _key_to_str(pet.home_map),
    }


def _serialize_enemy(enemy: Enemy) -> dict:
    return {
        "x": enemy.x,
        "y": enemy.y,
        "type_key": enemy.type_key,
        "hp": enemy.hp,
    }


def _serialize_creature(c: Creature) -> dict:
    """Serialize any Creature subclass.  rider_id is always omitted (transient)."""
    creature_class = "sea" if isinstance(c, SeaCreature) else "overland"
    return {
        "creature_class": creature_class,
        "x": c.x,
        "y": c.y,
        "kind": c.kind,
        "speed": c.speed,
        "size": c.size,
        "body_color": list(c.body_color),
        "facing_direction": getattr(c, "facing_direction", "right"),
        "facing_right": c.facing_right,
        "home_map": _key_to_str(c.home_map),
    }


# ---------------------------------------------------------------------------
# Deserializers
# ---------------------------------------------------------------------------


def _deserialize_map(data: dict) -> MapScene:
    """Reconstruct a MapScene (wrapping a GameMap) from a saved dict."""
    game_map = GameMap(data["world"], tileset=data["tileset"])
    game_map.biome = BiomeType(data.get("biome", BiomeType.STANDARD.value))
    game_map.tile_hp = data["tile_hp"]
    game_map.town_clusters = {
        (int(k.split(":")[0]), int(k.split(":")[1])): v
        for k, v in data["town_clusters"].items()
    }
    # Temporarily set enemies on the raw map so MapScene.__init__ can transfer them.
    game_map.enemies = [_deserialize_enemy(e) for e in data.get("enemies", [])]
    # Restore map-specific attributes when present
    for attr in _MAP_EXTRA_ATTRS:
        if attr in data:
            setattr(game_map, attr, data[attr])
    if "origin_map" in data:
        game_map.origin_map = _str_to_key(data["origin_map"])
    if "sub_house_positions" in data:
        positions = []
        for entry in data["sub_house_positions"]:
            if len(entry) >= 4:
                positions.append(
                    (int(entry[0]), int(entry[1]), int(entry[2]), int(entry[3]))
                )
            else:
                positions.append((int(entry[0]), int(entry[1]), 3, 3))
        game_map.sub_house_positions = positions
    if "portal_exits" in data:
        game_map.portal_exits = {}
        for k, v in data["portal_exits"].items():
            col, row = k.split(":")
            game_map.portal_exits[(int(col), int(row))] = (
                _str_to_key(v) if v is not None else None
            )
    # Sky-ladder quest data
    if "sign_texts" in data:
        game_map.sign_texts = {
            (int(k.split(":")[0]), int(k.split(":")[1])): v
            for k, v in data["sign_texts"].items()
        }
    game_map.ladder_repaired = data.get("ladder_repaired", False)
    game_map.ladder_col = data.get("ladder_col", -1)
    game_map.ladder_row = data.get("ladder_row", -1)
    # Wrap in a MapScene (enemies are transferred during __init__)
    scene = MapScene(game_map)
    # Restore per-scene entities
    scene.workers = [_deserialize_worker(w) for w in data.get("workers", [])]
    scene.pets = [_deserialize_pet(p) for p in data.get("pets", [])]
    if "creatures" in data:
        scene.creatures = [_deserialize_creature(c) for c in data["creatures"]]
    return scene


def _deserialize_player(data: dict, control_scheme: ControlScheme) -> Player:
    player = Player(
        data["x"], data["y"], player_id=data["player_id"], control_scheme=control_scheme
    )
    player.color = tuple(data["color"])
    player.pick_level = data["pick_level"]
    # New weapon system: weapon_id + unlocked_weapons
    if "weapon_id" in data:
        player.weapon_id = data["weapon_id"]
        player.unlocked_weapons = data.get("unlocked_weapons", [data["weapon_id"]])
    elif "weapon_level" in data:
        # Legacy migration: old integer weapon_level → weapon_id
        from src.data.attack_patterns import LEGACY_WEAPON_MAP, DEFAULT_WEAPONS

        old_level = data["weapon_level"]
        player.weapon_id = LEGACY_WEAPON_MAP.get(old_level, DEFAULT_WEAPONS[0])
        player.unlocked_weapons = [
            LEGACY_WEAPON_MAP[i] for i in range(old_level + 1) if i in LEGACY_WEAPON_MAP
        ]
    player.inventory = data["inventory"]
    player.hp = data["hp"]
    player.max_hp = data["max_hp"]
    player.xp = data["xp"]
    player.level = data["level"]
    player.xp_next = data["xp_next"]
    player.facing_dx = data["facing_dx"]
    player.facing_dy = data["facing_dy"]
    player.auto_mine = data["auto_mine"]
    player.auto_fire = data["auto_fire"]
    player.on_boat = data["on_boat"]
    player.boat_col = data["boat_col"]
    player.boat_row = data["boat_row"]
    player.current_map = _str_to_player_map_key(data["current_map"])
    player.is_dead = data.get("is_dead", False)
    raw_origin = data.get("portal_origin_map")
    player.portal_origin_map = (
        _str_to_key(raw_origin) if raw_origin is not None else None
    )
    raw_last_exit = data.get("last_portal_exit_map")
    player.last_portal_exit_map = (
        _str_to_key(raw_last_exit) if raw_last_exit is not None else None
    )
    player.last_portal_exit_x = data.get("last_portal_exit_x")
    player.last_portal_exit_y = data.get("last_portal_exit_y")
    # Equipment and durability (backward-compatible: empty if absent)
    from src.data.armor import ARMOR_SLOT_ORDER

    default_equip = {slot: None for slot in ARMOR_SLOT_ORDER}
    saved_equip = data.get("equipment", {})
    player.equipment = {**default_equip, **saved_equip}
    player.durability = data.get("durability", {})
    player.on_mount = data.get("on_mount", False)
    return player


def _deserialize_worker(data: dict) -> Worker:
    w = Worker(
        data["x"],
        data["y"],
        player_id=data["player_id"],
        home_map=_str_to_key(data.get("home_map", "overland")),
    )
    w.speed = data["speed"]
    w.body_color = tuple(data["body_color"])
    w.skin_color = tuple(data["skin_color"])
    w.hat_color = tuple(data["hat_color"])
    w.size_mod = data["size_mod"]
    return w


def _deserialize_pet(data: dict) -> Pet:
    p = Pet(
        data["x"],
        data["y"],
        kind=data["kind"],
        home_map=_str_to_key(data.get("home_map", "overland")),
    )
    p.speed = data["speed"]
    p.body_color = tuple(data["body_color"])
    p.eye_color = tuple(data["eye_color"])
    p.size = data["size"]
    p.spot_color = tuple(data["spot_color"])
    p.follow_offset_x = data["follow_offset_x"]
    p.follow_offset_y = data["follow_offset_y"]
    return p


def _deserialize_enemy(data: dict) -> Enemy:
    e = Enemy(data["x"], data["y"], data["type_key"])
    e.hp = data["hp"]
    return e


def _deserialize_sea_creature(data: dict) -> SeaCreature:
    """Kept for backward-compat loading of old saves with a 'sea_creatures' key."""
    sc = SeaCreature(
        data["x"],
        data["y"],
        kind=data["kind"],
        home_map=_str_to_key(data.get("home_map", "overland")),
    )
    sc.speed = data["speed"]
    sc.size = data["size"]
    sc.body_color = tuple(data["body_color"])
    sc.facing_right = data.get("facing_right", True)
    sc.rider_id = None
    return sc


def _deserialize_creature(data: dict) -> Creature:
    """Deserialize a Creature from a unified dict (version 7+)."""
    kind = data["kind"]
    home_map = _str_to_key(data.get("home_map", "overland"))
    creature_class = data.get("creature_class", "sea")

    if creature_class == "overland":
        c: Creature = OverlandCreature(
            data["x"], data["y"], kind=kind, home_map=home_map
        )
    else:
        c = SeaCreature(data["x"], data["y"], kind=kind, home_map=home_map)

    c.speed = data["speed"]
    c.size = data["size"]
    c.body_color = tuple(data["body_color"])  # type: ignore[assignment]
    # Prefer facing_direction (new saves); fall back to facing_right (old saves)
    if "facing_direction" in data:
        c.facing_direction = data["facing_direction"]
    else:
        c.facing_right = data.get("facing_right", True)
    c.rider_id = None
    return c


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def save_game(game: "Game") -> None:
    """Serialize full game state to save.json."""
    maps_data = {}
    for key, game_map in game.maps.items():
        # Skip the sector (0,0) alias — it's the same object as "overland"
        if (
            isinstance(key, tuple)
            and len(key) == 3
            and key[0] == "sector"
            and key[1] == 0
            and key[2] == 0
        ):
            continue
        maps_data[_key_to_str(key)] = _serialize_map(game_map)

    # Serialize entity archive (evicted sector entities)
    entity_archive: dict = {}
    for arc_key, arc_data in game._entity_archive.items():
        entity_archive[_key_to_str(arc_key)] = arc_data

    save_data = {
        "version": SAVE_VERSION,
        "world_seed": game.world_seed,
        "maps": maps_data,
        "entity_archive": entity_archive,
        "players": [
            _serialize_player(game.player1),
            _serialize_player(game.player2),
        ],
        "visited_sectors": [list(s) for s in game.visited_sectors],
        "land_sectors": [list(s) for s in game.land_sectors],
        "sky_revealed_sectors": [list(s) for s in game.sky_revealed_sectors],
        "portal_quests": {
            _key_to_str(k): {**v, "type": v["type"].value}
            for k, v in game.portal_quests.items()
        },
    }

    with open(SAVE_PATH, "w") as f:
        json.dump(save_data, f)


def load_game() -> dict | None:
    """Load save.json and return the raw dict, or None if no save exists."""
    if not os.path.exists(SAVE_PATH):
        return None
    try:
        with open(SAVE_PATH, "r") as f:
            data = json.load(f)
        if data.get("version") != SAVE_VERSION:
            return None
        return data
    except (json.JSONDecodeError, KeyError, OSError):
        return None


def apply_save(game: "Game", data: dict) -> None:
    """Overwrite game state with the saved data dict."""
    game.world_seed = data["world_seed"]
    game.sectors.world_seed = data["world_seed"]

    # Rebuild maps as MapScene instances (entities are inline per-map in v8)
    game.maps = {}
    for key_str, map_data in data["maps"].items():
        key = _str_to_key(key_str)
        game.maps[key] = _deserialize_map(map_data)

    # Re-create the sector (0,0) alias
    game.maps[("sector", 0, 0)] = game.maps["overland"]

    # Restore entity archive (evicted sector entities) — update in-place
    game.sectors._entity_archive.clear()
    for arc_key_str, arc_data in data.get("entity_archive", {}).items():
        game.sectors._entity_archive[_str_to_key(arc_key_str)] = arc_data

    # Players
    p1_data, p2_data = data["players"][0], data["players"][1]
    game.player1 = _deserialize_player(p1_data, CONTROL_SCHEME_PLAYER1)
    game.player2 = _deserialize_player(p2_data, CONTROL_SCHEME_PLAYER2)

    # Visited sectors — update in-place so SectorManager aliases stay valid
    game.sectors.visited_sectors.clear()
    game.sectors.visited_sectors.update(
        {tuple(s) for s in data.get("visited_sectors", [[0, 0]])}
    )
    game.sectors.land_sectors.clear()
    game.sectors.land_sectors.update(
        {tuple(s) for s in data.get("land_sectors", [[0, 0]])}
    )
    game.sectors.sky_revealed_sectors.clear()
    game.sectors.sky_revealed_sectors.update(
        {tuple(s) for s in data.get("sky_revealed_sectors", [])}
    )

    # Portal quest state
    raw_quests = data.get("portal_quests", {})
    from src.data import PortalQuestType

    restored_quests = {
        _str_to_key(k): {**v, "type": PortalQuestType(v["type"])}
        for k, v in raw_quests.items()
    }
    # Update the PortalManager's dict in-place so the backward-compat alias stays valid
    game.portals.portal_quests.clear()
    game.portals.portal_quests.update(restored_quests)

    # Snap cameras to loaded player positions
    game.cam1_x = game.player1.x - game.viewport_w // 2
    game.cam1_y = game.player1.y - game.viewport_h // 2
    game.cam2_x = game.player2.x - game.viewport_w // 2
    game.cam2_y = game.player2.y - game.viewport_h // 2
