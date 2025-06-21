from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from poker_game.core.player import Player
    from poker_game.core.game_state import GameState
    from poker_game.core.events import Action, GameEvent

class GameInterface(ABC):
    @abstractmethod
    def get_player_action(self, player: 'Player', game_state: 'GameState', allowed_actions: dict) -> 'Action':
        """
        Gets an action from the specified player.
        allowed_actions: A dict describing valid actions and their constraints (e.g. min/max bet).
                         Example: {'fold': True, 'call': 20, 'raise': {'min': 40, 'max': 1000}}
        """
        pass

    @abstractmethod
    def notify_event(self, event: 'GameEvent', game_state: 'GameState') -> None:
        """
        Notifies the interface about a game event.
        The interface can then decide how to display this information.
        game_state is provided for context if needed by the interface to render the event.
        """
        pass

    @abstractmethod
    def display_game_state(self, game_state: 'GameState', current_player_id: str = None, show_hole_cards_for_player: str = None) -> None:
        """Displays the current state of the game."""
        pass

    @abstractmethod
    def display_round_start(self, game_state: 'GameState', round_number: int) -> None:
        """Displays information at the start of a new round."""
        pass

    @abstractmethod
    def display_player_cards(self, player: 'Player') -> None:
        """Specifically displays a player's hole cards (usually only to that player)."""
        pass

    @abstractmethod
    def display_winner(self, winners: list, game_state: 'GameState', hand_results: dict) -> None:
        """Displays the winner(s) of the round and how they won."""
        pass

    @abstractmethod
    def get_player_names(self, num_players: int) -> list[str]:
        """Gets names for human players."""
        pass

    @abstractmethod
    def show_message(self, message: str) -> None:
        """Displays a generic message to the user."""
        pass
