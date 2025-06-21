from abc import ABC, abstractmethod
from poker_game.core.events import Action # Forward declaration for GameState
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from poker_game.core.game_state import GameState # To avoid circular import

class Player(ABC):
    def __init__(self, player_id: str, stack: int):
        self.player_id = player_id
        self.stack = stack
        self.hole_cards = [] # List of Card objects
        self.current_bet = 0 # Amount bet in the current betting round
        self.is_folded = False
        self.is_all_in = False

    @abstractmethod
    def make_decision(self, game_state: 'GameState') -> Action: # Added type hint for GameState
        pass

    def place_bet(self, amount: int) -> int:
        """Places a bet, reduces stack, and returns the amount bet."""
        bet_amount = min(amount, self.stack)
        self.stack -= bet_amount
        self.current_bet += bet_amount
        if self.stack == 0:
            self.is_all_in = True
        return bet_amount

    def fold(self):
        self.is_folded = True
        self.hole_cards = []

    def reset_for_new_round(self):
        self.hole_cards = []
        self.current_bet = 0
        self.is_folded = False
        self.is_all_in = False

    def __repr__(self):
        return f"{self.__class__.__name__}(id='{self.player_id}', stack={self.stack})"

class HumanPlayer(Player):
    def make_decision(self, game_state: 'GameState') -> Action:
        # This will be handled by the ConsoleInterface or other UI
        # For now, let's return a placeholder or raise NotImplementedError
        raise NotImplementedError("HumanPlayer decision should be handled by an interface.")
