# Game settings

# Blinds
SMALL_BLIND: int = 10
BIG_BLIND: int = 20

# Starting stack for players
STARTING_STACK: int = 1000

# Minimum bet size (usually equal to Big Blind)
# This can also be dynamic based on game state (e.g. last raise amount)
# For initial config, let's set a default. GameEngine might override or use dynamically.
MIN_BET: int = BIG_BLIND # Default minimum bet/raise increment.

# Number of players
# These are more like parameters for game setup rather than fixed settings here.
# For MVP: 1 human + 2-3 bots.
NUM_BOTS: int = 2 # Example, can be configured at game start
# Bot types to use, can be a list like ["RandomBot", "TightBot"]
BOT_TYPES: list[str] = ["RandomBot", "TightBot"]


# Max rounds (0 for unlimited until one player remains)
MAX_ROUNDS: int = 0 # 0 means play until one winner or quit

# Game ID for saving/loading (if applicable, otherwise can be dynamic)
DEFAULT_GAME_ID: str = "poker_game_01"

# Add any other game-wide configurations here
# For example, tournament structure, payout structures for future.

# Logging Level (for a potential logger)
# LOG_LEVEL = "INFO" # e.g., DEBUG, INFO, WARNING, ERROR

# Interface specific settings (if any) could also go here,
# though better in their respective interface modules if complex.
# CONSOLE_COLORS_ENABLED = True
