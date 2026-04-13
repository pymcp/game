"""Base class for all game environments."""


class BaseEnvironment:
    """Abstract base for environments (overland, cave, etc.).

    Each subclass defines how its map is generated and which enemies
    are appropriate for that environment.
    """

    def generate(self):
        """Generate and return a fully configured GameMap for this environment.

        Subclasses must implement this.  The returned GameMap may have
        extra attributes set (e.g. entrance_col for caves).
        """
        raise NotImplementedError

    def spawn_enemies(self, game_map):
        """Return a list of Enemy instances suitable for this environment.

        Args:
            game_map: The GameMap returned by generate(), in case spawn logic
                      needs to inspect tile layout.
        """
        raise NotImplementedError
