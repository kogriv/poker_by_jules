import argparse # Added for command-line arguments
from poker_game.core.game_engine import GameEngine
from poker_game.core.player import HumanPlayer
from poker_game.core.bot_player import RandomBot, TightBot, AggressiveBot # Import available bot types
from poker_game.core.events import EventSystem
from poker_game.interfaces.console_interface import ConsoleInterface
from poker_game.storage.memory_storage import MemoryRepository
from poker_game.config import settings

def main():
    parser = argparse.ArgumentParser(description="Run the Poker Game.")
    parser.add_argument(
        "--mode",
        type=str,
        choices=["normal", "smoke"],
        default="normal",
        help="Game mode: 'normal' for interactive play, 'smoke' for automated human actions (default: normal)."
    )
    args = parser.parse_args()
    game_mode = args.mode

    print(f"Welcome to Console Poker! (Mode: {game_mode})")

    # Setup components
    event_system = EventSystem()
    repository = MemoryRepository()
    # Pass game_mode to interface
    interface = ConsoleInterface(game_mode=game_mode)

    # Player setup
    players = []

    if game_mode == "smoke":
        human_player_name = "HumanPlayer"
        print("Smoke mode: Using default name 'HumanPlayer' for human.")
    else: # normal mode
        print("Normal mode: Please enter details for the human player.")
        try:
            human_player_name = interface.get_player_names(num_players=1)[0]
        except EOFError:
            print("\nEOFError encountered getting player name. This is expected in non-interactive sandbox for 'normal' mode.")
            print("Exiting early for this 'normal' mode sandbox test run.")
            return # Exit if we can't get name in normal mode in sandbox

    human_player = HumanPlayer(player_id=human_player_name, stack=settings.STARTING_STACK)
    players.append(human_player)

    # Add Bot players based on settings
    bot_constructors = {
        "RandomBot": RandomBot,
        "TightBot": TightBot,
        "AggressiveBot": AggressiveBot
    }

    num_bots_to_add = settings.NUM_BOTS
    if len(settings.BOT_TYPES) > 0:
        for i in range(num_bots_to_add):
            bot_type_name = settings.BOT_TYPES[i % len(settings.BOT_TYPES)] # Cycle through BOT_TYPES
            bot_constructor = bot_constructors.get(bot_type_name)
            if bot_constructor:
                bot_id = f"{bot_type_name}-{i+1}"
                players.append(bot_constructor(player_id=bot_id, stack=settings.STARTING_STACK))
            else:
                print(f"Warning: Unknown bot type '{bot_type_name}' in settings. Skipping.")
    else: # Default to RandomBot if BOT_TYPES is empty
        for i in range(num_bots_to_add):
            bot_id = f"RandomBot-{i+1}"
            players.append(RandomBot(player_id=bot_id, stack=settings.STARTING_STACK))

    if len(players) < 2:
        print("Not enough players to start the game (minimum 2 required).")
        return

    print("\nPlayers for this game:")
    for p in players:
        print(f"- {p.player_id} ({p.__class__.__name__})")
    print("---")

    # Initialize Game Engine
    game_id = settings.DEFAULT_GAME_ID

    # Allow loading a game or starting new one
    loaded_game_successfully = False
    if game_mode == "normal": # Only ask to load in normal mode
        choice = ""
        try:
            choice = input(f"Load existing game '{game_id}'? (y/n, default n): ").strip().lower()
        except EOFError:
            print("\nEOFError encountered for load game prompt. Defaulting to new game.")
            choice = "n"

        if choice == 'y':
            if repository.load_game(game_id) is not None: # GameEngine will handle actual loading
                print(f"Attempting to load game '{game_id}'.")
                # GameEngine will try to load it. If it fails, it starts fresh.
                # No need to print "No saved game found..." here, engine handles it.
                loaded_game_successfully = True # Assume engine will load if found by repo check
            else:
                print(f"No saved game data found for '{game_id}' by repository. Starting a new game.")
        else:
            print("Starting a new game.")
    else: # Smoke mode
        print("Smoke mode: Starting a new game by default (no load prompt).")
        # Optionally, could try to delete existing game if smoke mode should always be fresh
        # repository.delete_game(game_id)


    engine = GameEngine(
        players=players,
        interface=interface,
        repository=repository,
        event_system=event_system,
        game_id=game_id
    )

    try:
        engine.start_game()
    except KeyboardInterrupt:
        print("\nGame interrupted by user. Saving state...")
        engine.repository.save_game(engine.game_id, engine.game_state)
        print("Game saved. Exiting.")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
        print("Attempting to save game state before exiting...")
        engine.repository.save_game(engine.game_id, engine.game_state)
        print("Game state saved (if possible). Please report the error.")
        # Optionally, re-raise the exception for debugging
        # raise e
    finally:
        print("\nThank you for playing!")

if __name__ == "__main__":
    main()
