"""Mining Game - Main entry point."""

import sys
from src.game import Game


def main():
    """Run the game."""
    game = Game()
    game.run()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)
