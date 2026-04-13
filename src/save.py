"""Game state serialization — save on exit, load on startup."""

import json
import os

from src.world.map import GameMap
from src.entities.player import Player, CONTROL_SCHEME_PLAYER1, CONTROL_SCHEME_PLAYER2
from src.entities.worker import Worker
from src.entities.pet import Pet
from src.entities.enemy import Enemy

SAVE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "save.json")
SAVE_VERSION = 1


# ---------------------------------------------------------------------------
# Map key encoding (JSON only allows string keys)
# ---------------------------------------------------------------------------

def _key_to_str(key):
    """Convert a map dict key to a JSON-safe string."""
    if key == "overland":
        return "overland"
    if isinstance(key, tuple):
        if len(key) == 3 and key[0] == "sector":
            return f"sector:{key[1]}:{key[2]}"
        if len(key) == 2:
            return f"cave:{key[0]}:{key[1]}"
    return str(key)


def _str_to_key(s):
    """Decode a serialized map key string back to the original dict key."""
    if s == "overland":
        return "overland"
    if s.startswith("sector:"):
        _, sx, sy = s.split(":")
        return ("sector", int(sx), int(sy))
    if s.startswith("cave:"):
        _, col, row = s.split(":")
        return (int(col), int(row))
    return s


def _player_map_key_to_str(key):
    """Serialize player.current_map (same encoding as map keys)."""
    return _key_to_str(key)


def _str_to_player_map_key(s):
    return _str_to_key(s)


# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------

# Optional attributes that cave maps carry (not present on overland maps)
_CAVE_EXTRA_ATTRS = (
    "entrance_col", "entrance_row",
    "exit_col", "exit_row",
    "spawn_col", "spawn_row",
    "cave_style",
)
# origin_map is a map key (string or tuple) — encoded/decoded via key helpers


def _serialize_map(game_map):
    """Serialize a GameMap to a JSON-serializable dict."""
    # town_clusters uses (row, col) tuple keys — encode as "row:col" strings
    tc = {f"{r}:{c}": v for (r, c), v in game_map.town_clusters.items()}
    enemies = [_serialize_enemy(e) for e in game_map.enemies]
    data = {
        "world": game_map.world,
        "tileset": game_map.tileset,
        "tile_hp": game_map.tile_hp,
        "town_clusters": tc,
        "enemies": enemies,
    }
    # Persist cave-specific attributes when present
    for attr in _CAVE_EXTRA_ATTRS:
        if hasattr(game_map, attr):
            data[attr] = getattr(game_map, attr)
    if hasattr(game_map, "origin_map"):
        data["origin_map"] = _key_to_str(game_map.origin_map)
    return data


def _serialize_player(player):
    return {
        "x": player.x,
        "y": player.y,
        "player_id": player.player_id,
        "color": list(player.color),
        "pick_level": player.pick_level,
        "weapon_level": player.weapon_level,
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
        "is_dead": player.is_dead,
    }


def _serialize_worker(worker):
    return {
        "x": worker.x,
        "y": worker.y,
        "player_id": worker.player_id,
        "speed": worker.speed,
        "body_color": list(worker.body_color),
        "skin_color": list(worker.skin_color),
        "hat_color": list(worker.hat_color),
        "size_mod": worker.size_mod,
    }


def _serialize_pet(pet):
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
    }


def _serialize_enemy(enemy):
    return {
        "x": enemy.x,
        "y": enemy.y,
        "type_key": enemy.type_key,
        "hp": enemy.hp,
    }


# ---------------------------------------------------------------------------
# Deserializers
# ---------------------------------------------------------------------------

def _deserialize_map(data):
    """Reconstruct a GameMap from saved dict."""
    game_map = GameMap(data["world"], tileset=data["tileset"])
    game_map.tile_hp = data["tile_hp"]
    game_map.town_clusters = {
        (int(k.split(":")[0]), int(k.split(":")[1])): v
        for k, v in data["town_clusters"].items()
    }
    game_map.enemies = [_deserialize_enemy(e) for e in data.get("enemies", [])]
    # Restore cave-specific attributes when present
    for attr in _CAVE_EXTRA_ATTRS:
        if attr in data:
            setattr(game_map, attr, data[attr])
    if "origin_map" in data:
        game_map.origin_map = _str_to_key(data["origin_map"])
    return game_map


def _deserialize_player(data, control_scheme):
    player = Player(data["x"], data["y"], player_id=data["player_id"],
                    control_scheme=control_scheme)
    player.color = tuple(data["color"])
    player.pick_level = data["pick_level"]
    player.weapon_level = data["weapon_level"]
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
    return player


def _deserialize_worker(data):
    w = Worker(data["x"], data["y"], player_id=data["player_id"])
    w.speed = data["speed"]
    w.body_color = tuple(data["body_color"])
    w.skin_color = tuple(data["skin_color"])
    w.hat_color = tuple(data["hat_color"])
    w.size_mod = data["size_mod"]
    return w


def _deserialize_pet(data):
    p = Pet(data["x"], data["y"], kind=data["kind"])
    p.speed = data["speed"]
    p.body_color = tuple(data["body_color"])
    p.eye_color = tuple(data["eye_color"])
    p.size = data["size"]
    p.spot_color = tuple(data["spot_color"])
    p.follow_offset_x = data["follow_offset_x"]
    p.follow_offset_y = data["follow_offset_y"]
    return p


def _deserialize_enemy(data):
    e = Enemy(data["x"], data["y"], data["type_key"])
    e.hp = data["hp"]
    return e


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def save_game(game):
    """Serialize full game state to save.json."""
    maps_data = {}
    for key, game_map in game.maps.items():
        # Skip the sector (0,0) alias — it's the same object as "overland"
        if isinstance(key, tuple) and len(key) == 3 and key[0] == "sector" and key[1] == 0 and key[2] == 0:
            continue
        maps_data[_key_to_str(key)] = _serialize_map(game_map)

    save_data = {
        "version": SAVE_VERSION,
        "world_seed": game.world_seed,
        "maps": maps_data,
        "enemies": [_serialize_enemy(e) for e in game.enemies],
        "players": [
            _serialize_player(game.player1),
            _serialize_player(game.player2),
        ],
        "workers": [_serialize_worker(w) for w in game.workers],
        "pets": [_serialize_pet(p) for p in game.pets],
        "visited_sectors": [list(s) for s in game.visited_sectors],
        "land_sectors": [list(s) for s in game.land_sectors],
    }

    with open(SAVE_PATH, "w") as f:
        json.dump(save_data, f)


def load_game():
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


def apply_save(game, data):
    """Overwrite game state with the saved data dict."""
    game.world_seed = data["world_seed"]

    # Rebuild maps
    game.maps = {}
    for key_str, map_data in data["maps"].items():
        key = _str_to_key(key_str)
        game.maps[key] = _deserialize_map(map_data)

    # Re-create the sector (0,0) alias
    game.maps[("sector", 0, 0)] = game.maps["overland"]

    # Overland enemies  
    game.enemies = [_deserialize_enemy(e) for e in data["enemies"]]

    # Players
    p1_data, p2_data = data["players"][0], data["players"][1]
    game.player1 = _deserialize_player(p1_data, CONTROL_SCHEME_PLAYER1)
    game.player2 = _deserialize_player(p2_data, CONTROL_SCHEME_PLAYER2)

    # Workers and pets
    game.workers = [_deserialize_worker(w) for w in data["workers"]]
    game.pets = [_deserialize_pet(p) for p in data["pets"]]

    # Visited sectors
    game.visited_sectors = {tuple(s) for s in data.get("visited_sectors", [[0, 0]])}
    game.land_sectors = {tuple(s) for s in data.get("land_sectors", [[0, 0]])}

    # Snap cameras to loaded player positions
    game.cam1_x = game.player1.x - game.viewport_w // 2
    game.cam1_y = game.player1.y - game.viewport_h // 2
    game.cam2_x = game.player2.x - game.viewport_w // 2
    game.cam2_y = game.player2.y - game.viewport_h // 2
