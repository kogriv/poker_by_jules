from poker_game.interfaces.base_interface import GameInterface
from poker_game.core.player import Player, HumanPlayer
from poker_game.core.game_state import GameState
from poker_game.core.events import Action, GameEvent
from poker_game.core.cards import Card # For type hinting Card objects
from typing import TYPE_CHECKING, Dict, Any, Optional, List
import queue # Thread-safe queue for actions from web to game engine
import logging # For logging

if TYPE_CHECKING:
    from flask_socketio import SocketIO
    # from poker_game.core.game_engine import GameEngine # Avoid direct import if possible

logger = logging.getLogger(__name__)

class WebInterface(GameInterface):
    def __init__(self, socketio_instance: 'SocketIO', action_queue: queue.Queue, human_player_id_for_view: str):
        self.socketio = socketio_instance
        self.action_queue = action_queue
        self.human_player_id = human_player_id_for_view
        # self.game_engine: Optional['GameEngine'] = None
        logger.info("WebInterface initialized.")

    # def set_game_engine(self, game_engine: 'GameEngine'):
    #     self.game_engine = game_engine

    def _card_to_str_dict(self, card: Card) -> Dict[str, str]:
        """Converts a Card object to a dict {'rank': 'X', 'suit': 'Y'} for JSON."""
        return {"rank": card.rank, "suit": card.suit}

    def _game_state_to_json(self, game_state: GameState, perspective_player_id: Optional[str] = None) -> Dict[str, Any]:
        """Converts GameState to a JSON-serializable dict for web clients."""
        if not game_state:
            logger.warning("Attempted to serialize a None game_state.")
            return {}

        players_data = []
        for p in game_state.players:
            player_dict = {
                "player_id": p.player_id,
                "stack": p.stack,
                "current_bet": p.current_bet, # Bet amount for the current street
                "is_folded": p.is_folded,
                "is_all_in": p.is_all_in,
                "is_human": isinstance(p, HumanPlayer), # Could be used by JS to identify the human
                "is_dealer": game_state.players[game_state.dealer_button_position].player_id == p.player_id,
                "is_sb": game_state.small_blind_player_id == p.player_id,
                "is_bb": game_state.big_blind_player_id == p.player_id,
                "hole_cards": None,
            }
            # Determine card visibility
            if p.player_id == perspective_player_id and p.hole_cards:
                player_dict["hole_cards"] = [self._card_to_str_dict(card) for card in p.hole_cards]
            elif game_state.game_phase == "showdown" and not p.is_folded and p.hole_cards:
                player_dict["hole_cards"] = [self._card_to_str_dict(card) for card in p.hole_cards]
            elif p.hole_cards and not p.is_folded:
                 player_dict["hole_cards"] = ["HIDDEN", "HIDDEN"] # Placeholder for hidden cards

            players_data.append(player_dict)

        current_player_obj = game_state.players[game_state.current_player_turn_index] if game_state.players and 0 <= game_state.current_player_turn_index < len(game_state.players) else None
        current_player_turn_id_val = current_player_obj.player_id if current_player_obj else None


        return {
            "players": players_data,
            "community_cards": [self._card_to_str_dict(card) for card in game_state.community_cards] if game_state.community_cards else [],
            "pot_size": game_state.pot_size + game_state.current_round_pot,
            "current_bet_to_match": game_state.current_bet_to_match,
            "game_phase": game_state.game_phase,
            "round_number": game_state.round_number,
            "current_player_turn_id": current_player_turn_id_val,
            "dealer_button_player_id": game_state.players[game_state.dealer_button_position].player_id if game_state.players else None,
            "small_blind_player_id": game_state.small_blind_player_id,
            "big_blind_player_id": game_state.big_blind_player_id,
            "is_game_over": game_state.is_game_over,
            # "game_over_reason": getattr(game_state, 'game_over_reason', None) # If you add this to GameState
        }

    def get_player_action(self, player: Player, game_state: GameState, allowed_actions: dict) -> Action:
        logger.info(f"WebInterface: Requesting action for {player.player_id}")

        if not isinstance(player, HumanPlayer):
            # This should ideally not be called for bots by the GameEngine if engine directly calls bot.make_decision()
            logger.warning(f"WebInterface.get_player_action called for Bot {player.player_id}. Bots should decide internally. Auto-folding.")
            return Action(type="fold", player_id=player.player_id)

        # For HumanPlayer (which is self.human_player_id in this context for MVP)
        if player.player_id != self.human_player_id:
            logger.error(f"WebInterface.get_player_action called for unexpected human player {player.player_id}. Expected {self.human_player_id}. Auto-folding.")
            return Action(type="fold", player_id=player.player_id)

        payload = {
            "player_id_to_act": player.player_id, # Whose turn it is
            "allowed_actions": allowed_actions,
            "game_state_for_player": self._game_state_to_json(game_state, player.player_id) # State from this player's perspective
        }

        # Emit to a specific client or all and let client filter.
        # For MVP with one human, emitting to all and letting JS check player_id might be simpler than managing SIDs for rooms.
        # However, 'request_player_action' should ideally target only the specific player.
        # This requires mapping player_id to a client's session ID (sid) on connect.
        # For now, let's assume JS will filter based on player_id_to_act matching its own ID.
        logger.info(f"WebInterface: Emitting 'request_player_action' for {player.player_id} with payload: {payload}")
        self.socketio.emit('request_player_action', payload)

        try:
            # Block and wait for the action from the web client
            # The web route (/submit_action) will put the Action object onto this queue
            action = self.action_queue.get(timeout=120) # 2 minute timeout
            logger.info(f"WebInterface: Received action from queue for {player.player_id}: {action}")
            if action.player_id != player.player_id:
                logger.error(f"Action received for wrong player! Expected {player.player_id}, got {action.player_id}. Auto-folding.")
                return Action(type="fold", player_id=player.player_id)
            return action
        except queue.Empty:
            logger.warning(f"WebInterface: Timeout waiting for action from {player.player_id}. Auto-folding.")
            return Action(type="fold", player_id=player.player_id)
        except Exception as e:
            logger.error(f"WebInterface: Error getting action from queue for {player.player_id}: {e}. Auto-folding.")
            return Action(type="fold", player_id=player.player_id)


    def notify_event(self, event: GameEvent, game_state: GameState) -> None:
        # logger.debug(f"WebInterface: Notifying event {event.type} to clients.")
        game_update_payload = {
            "event": {"type": event.type, "data": event.data},
            "game_state": self._game_state_to_json(game_state, self.human_player_id)
        }
        self.socketio.emit('game_update', game_update_payload)
        # logger.debug("WebInterface: 'game_update' emitted.")


    def display_game_state(self, game_state: GameState, current_player_id: Optional[str] = None, show_hole_cards_for_player: Optional[str] = None) -> None:
        # This is called by GameEngine. For Web, the main update is via notify_event.
        # This can serve as an additional explicit state push if needed.
        # logger.debug(f"WebInterface: display_game_state called (current: {current_player_id}). Triggering game_update.")
        game_update_payload = {
            "game_state": self._game_state_to_json(game_state, self.human_player_id) # Perspective of the human user
        }
        self.socketio.emit('game_update', game_update_payload)

    def display_round_start(self, game_state: GameState, round_number: int) -> None:
        # logger.info(f"WebInterface: Displaying round start for round {round_number}")
        # This info is part of game_state. A specific banner event can be nice.
        self.socketio.emit('round_start_banner', {'round_number': round_number,
                                                 'message': f"--- STARTING ROUND {round_number} ---"})


    def display_player_cards(self, player: Player) -> None:
        # This is mainly for the human player.
        # The game_state update (with perspective) should generally handle this.
        # However, an explicit emit to a specific player might be useful if their cards change mid-update.
        if isinstance(player, HumanPlayer) and player.player_id == self.human_player_id and player.hole_cards:
            # logger.debug(f"WebInterface: Emitting 'player_cards_update' for {player.player_id}")
            # This emit should ideally target only this specific player's client session.
            # For now, emitting to all; JS should filter.
            self.socketio.emit('game_update', {
                "game_state": self._game_state_to_json(player.game_state_view, self.human_player_id) # Assuming player has a view of gamestate
            }) # Send a full game update, JS will re-render player area

    def display_winner(self, winners_data: list, game_state: GameState, hand_results: dict) -> None:
        # logger.info(f"WebInterface: Displaying winner. Winners: {len(winners_data)}")

        # Prepare hand_results with stringified cards for JSON
        json_hand_results = {}
        if hand_results:
            for pid, res_data in hand_results.items():
                json_hand_results[pid] = {
                    "hand_name": res_data["hand_name"],
                    "best_cards": [self._card_to_str_dict(c) for c in res_data["best_cards"]] if res_data.get("best_cards") else []
                }

        # Prepare winners_data with stringified cards
        json_winners_data = []
        for wd in winners_data:
            json_wd = wd.copy()
            if "best_cards" in json_wd and json_wd["best_cards"]:
                json_wd["best_cards"] = [self._card_to_str_dict(c) for c in json_wd["best_cards"]]
            json_winners_data.append(json_wd)

        results_payload = {
            "winners_data": json_winners_data,
            "hand_results": json_hand_results,
            "game_state_after_win": self._game_state_to_json(game_state, self.human_player_id) # State after pot distribution
        }
        self.socketio.emit('round_results', results_payload)


    def get_player_names(self, num_players: int) -> List[str]:
        logger.info("WebInterface: get_player_names called - returning default for web MVP.")
        if num_players == 1: # Assuming this is for the human player
            return [self.human_player_id]
        # This method is less relevant for web where player identity is handled differently.
        return [f"WebBot{i}" for i in range(num_players-1)] # Placeholder if needed

    def show_message(self, message: str) -> None:
        logger.info(f"WebInterface: show_message: {message}")
        self.socketio.emit('show_message', {'message': message})

```
