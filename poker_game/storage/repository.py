from abc import ABC, abstractmethod
from typing import Optional, Any # Using Any for game_state for now
from poker_game.core.game_state import GameState # Import specific GameState

class GameRepository(ABC):
    @abstractmethod
    def save_game(self, game_id: str, game_state: GameState) -> None:
        pass

    @abstractmethod
    def load_game(self, game_id: str) -> Optional[GameState]:
        pass

    @abstractmethod
    def delete_game(self, game_id: str) -> None:
        pass

    # May add methods for player stats later
    # @abstractmethod
    # def update_player_stats(self, player_id: str, stats_data: dict) -> None:
    #     pass

    # @abstractmethod
    # def load_player_stats(self, player_id: str) -> Optional[dict]:
    #     pass
