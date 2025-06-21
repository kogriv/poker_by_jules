from typing import Dict, Optional
from poker_game.storage.repository import GameRepository
from poker_game.core.game_state import GameState # Using specific GameState

class MemoryRepository(GameRepository):
    def __init__(self):
        self._games: Dict[str, Dict] = {} # Store serialized game state (dicts)
        # self._player_stats: Dict[str, Dict] = {} # For future use

    def save_game(self, game_id: str, game_state: GameState) -> None:
        print(f"MemoryRepository: Saving game {game_id}...")
        # GameState should have a to_dict() method for serialization
        self._games[game_id] = game_state.to_dict()
        print(f"Game {game_id} saved. Current stored games: {list(self._games.keys())}")


    def load_game(self, game_id: str) -> Optional[GameState]:
        print(f"MemoryRepository: Attempting to load game {game_id}...")
        game_data = self._games.get(game_id)
        if game_data:
            print(f"Found game data for {game_id}. Deserializing...")
            # GameState should have a from_dict() class method for deserialization
            return GameState.from_dict(game_data)
        print(f"No game data found for {game_id}.")
        return None

    def delete_game(self, game_id: str) -> None:
        if game_id in self._games:
            del self._games[game_id]
            print(f"MemoryRepository: Deleted game {game_id}.")
        else:
            print(f"MemoryRepository: Game {game_id} not found for deletion.")

    # def update_player_stats(self, player_id: str, stats_data: dict) -> None:
    #     if player_id not in self._player_stats:
    #         self._player_stats[player_id] = {}
    #     self._player_stats[player_id].update(stats_data)
    #     print(f"MemoryRepository: Updated stats for player {player_id}.")

    # def load_player_stats(self, player_id: str) -> Optional[dict]:
    #     return self._player_stats.get(player_id)

    def list_saved_games(self) -> list[str]:
        """Helper to see what's in memory, useful for debugging or simple load UIs."""
        return list(self._games.keys())
