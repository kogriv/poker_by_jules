from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from poker_game.core.player import Player # Using Player directly, not just player_id for active players
from poker_game.core.cards import Card # For community cards, etc.

# To handle serialization/deserialization of custom objects like Player and Card
# we'll need helper methods or rely on a structure that's easily JSON serializable.

def player_to_dict(player: Player) -> Dict[str, Any]:
    return {
        "player_id": player.player_id,
        "stack": player.stack,
        "hole_cards": [card_to_dict(c) for c in player.hole_cards], # Only for current player in some contexts
        "current_bet": player.current_bet,
        "is_folded": player.is_folded,
        "is_all_in": player.is_all_in,
        "class_type": player.__class__.__name__ # To recreate the correct Player type
    }

def card_to_dict(card: Card) -> Dict[str, str]:
    return {"rank": card.rank, "suit": card.suit}

def dict_to_card(data: Dict[str, str]) -> Card:
    return Card(rank=data["rank"], suit=data["suit"])

# We'll need a way to map class_type back to actual classes for deserialization
# This would typically involve importing the specific player classes.
# For now, this will be handled in the from_dict method or by a factory.

@dataclass
class GameState:
    players: List[Player] = field(default_factory=list)
    dealer_button_position: int = 0
    current_player_turn_index: int = 0 # Index in the 'active_players_in_round' list or similar
    # active_players_in_round: List[Player] = field(default_factory=list) # Players still in the current hand

    community_cards: List[Card] = field(default_factory=list)
    pot_size: int = 0
    current_round_pot: int = 0 # Money bet in the current betting round (flop, turn, river)

    current_bet_to_match: int = 0 # Highest bet amount in the current betting round that needs to be matched
    last_raiser: Optional[str] = None # player_id of the last player who raised
    last_raise_amount: int = 0 # The amount of the last raise (additional money on top of previous bet)

    game_phase: str = "pre-flop"  # e.g., "pre-flop", "flop", "turn", "river", "showdown", "round_over"

    small_blind: int = 10 # Default, should be configurable
    big_blind: int = 20   # Default, should be configurable
    min_bet : int = 20 # Usually equal to big blind for first bet, or last raise size for re-raise

    round_number: int = 0
    is_game_over: bool = False

    # Optional: Could store history of actions for replay or detailed logging
    # action_history: List[Action] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        # Custom serialization for players and cards
        # return asdict(self) # asdict won't handle custom objects well by default
        return {
            "players": [player_to_dict(p) for p in self.players],
            "dealer_button_position": self.dealer_button_position,
            "current_player_turn_index": self.current_player_turn_index,
            "community_cards": [card_to_dict(c) for c in self.community_cards],
            "pot_size": self.pot_size,
            "current_round_pot": self.current_round_pot,
            "current_bet_to_match": self.current_bet_to_match,
            "last_raiser": self.last_raiser,
            "last_raise_amount": self.last_raise_amount,
            "game_phase": self.game_phase,
            "small_blind": self.small_blind,
            "big_blind": self.big_blind,
            "min_bet": self.min_bet,
            "round_number": self.round_number,
            "is_game_over": self.is_game_over,
            # "action_history": [asdict(action) for action in self.action_history]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GameState':
        # Custom deserialization
        # Need to import player types here or have a factory
        from poker_game.core.player import HumanPlayer # Example
        from poker_game.core.bot_player import RandomBot, TightBot, AggressiveBot # Examples

        player_class_map = {
            "Player": Player, # Should not happen if concrete types are stored
            "HumanPlayer": HumanPlayer,
            "RandomBot": RandomBot,
            "TightBot": TightBot,
            "AggressiveBot": AggressiveBot
        }

        players_data = data.get("players", [])
        loaded_players = []
        for p_data in players_data:
            player_cls_name = p_data.get("class_type", "Player") # Default to Player if not specified
            player_cls = player_class_map.get(player_cls_name, Player) # Fallback to base Player

            # Basic instantiation, specific player types might need more args or load methods
            player = player_cls(player_id=p_data["player_id"], stack=p_data["stack"])
            player.hole_cards = [dict_to_card(c_data) for c_data in p_data.get("hole_cards", [])]
            player.current_bet = p_data.get("current_bet", 0)
            player.is_folded = p_data.get("is_folded", False)
            player.is_all_in = p_data.get("is_all_in", False)
            loaded_players.append(player)

        community_cards = [dict_to_card(c_data) for c_data in data.get("community_cards", [])]

        # action_history_data = data.get("action_history", [])
        # loaded_action_history = []
        # if action_history_data: # Assuming Action is a dataclass too
        #     from poker_game.core.events import Action # local import
        #     loaded_action_history = [Action(**a_data) for a_data in action_history_data]


        return cls(
            players=loaded_players,
            dealer_button_position=data.get("dealer_button_position", 0),
            current_player_turn_index=data.get("current_player_turn_index", 0),
            community_cards=community_cards,
            pot_size=data.get("pot_size", 0),
            current_round_pot=data.get("current_round_pot", 0),
            current_bet_to_match=data.get("current_bet_to_match", 0),
            last_raiser=data.get("last_raiser"),
            last_raise_amount=data.get("last_raise_amount", 0),
            game_phase=data.get("game_phase", "pre-flop"),
            small_blind=data.get("small_blind", 10),
            big_blind=data.get("big_blind", 20),
            min_bet=data.get("min_bet", 20),
            round_number=data.get("round_number", 0),
            is_game_over=data.get("is_game_over", False),
            # action_history=loaded_action_history
        )

    def get_player_by_id(self, player_id: str) -> Optional[Player]:
        for player in self.players:
            if player.player_id == player_id:
                return player
        return None

    def get_active_players_in_round(self) -> List[Player]:
        """Returns players who are not folded and not all-in (unless they are the only ones left or betting is over)."""
        # More accurately, players who are not folded. All-in players are still "in" the round.
        return [p for p in self.players if not p.is_folded]

    def get_players_eligible_to_act(self) -> List[Player]:
        """Returns players who are not folded and not all-in."""
        return [p for p in self.players if not p.is_folded and not p.is_all_in]

    def __str__(self) -> str:
        player_strs = [f"{p.player_id}({p.stack})" for p in self.players]
        community_str = ", ".join(map(str, self.community_cards))
        return (
            f"GameState(Round: {self.round_number}, Phase: {self.game_phase}, "
            f"Pot: {self.pot_size}, Community: [{community_str}], "
            f"Players: {player_strs}, TurnIdx: {self.current_player_turn_index}, "
            f"BetToMatch: {self.current_bet_to_match})"
        )
