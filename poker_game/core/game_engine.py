from typing import List, Optional, Tuple, Dict, Any
from poker_game.core.player import Player, HumanPlayer
from poker_game.core.bot_player import BotPlayer # For type checking
from poker_game.core.cards import Deck # Corrected import
from poker_game.core.game_state import GameState
from poker_game.core.rules import TexasHoldemRules
from poker_game.core.cards import HandEvaluator, Card
from poker_game.core.events import EventSystem, GameEvent, Action
from poker_game.interfaces.base_interface import GameInterface
from poker_game.storage.repository import GameRepository
from poker_game.config import settings # For blinds, starting stack

class GameEngine:
    def __init__(self,
                 players: List[Player],
                 interface: GameInterface,
                 repository: GameRepository,
                 event_system: EventSystem,
                 game_id: str = "default_poker_game"):

        self.game_id = game_id
        self.deck = Deck()
        self.hand_evaluator = HandEvaluator()
        self.rules = TexasHoldemRules(self.hand_evaluator)
        self.interface = interface
        self.repository = repository
        self.event_system = event_system

        # Subscribe interface to events for display purposes
        self.event_system.subscribe(self.handle_game_event_for_interface)

        # Initialize GameState
        self.game_state = GameState(
            players=players,
            small_blind=settings.SMALL_BLIND,
            big_blind=settings.BIG_BLIND,
            min_bet=settings.BIG_BLIND, # Initial min bet
            dealer_button_position=0 # Initial position, will rotate
        )
        # Ensure all players have unique IDs
        if len(set(p.player_id for p in players)) != len(players):
            raise ValueError("Player IDs must be unique.")

        self._active_round_players: List[Player] = [] # Players currently in the hand, ordered by action.

    def handle_game_event_for_interface(self, event: GameEvent):
        """Passes game events to the interface for display/logging."""
        # We also pass game_state for context, as interface might need it to render the event
        self.interface.notify_event(event, self.game_state)


    def start_game(self) -> None:
        """Starts and manages the overall game flow until completion."""
        self.event_system.post(GameEvent(type="game_start", data={"num_players": len(self.game_state.players)}))
        # Welcome banner is now in ConsoleInterface.__init__
        # self.interface.show_message("Poker game started!") # Message now part of banner

        # Try to load existing game, if any
        loaded_state = self.repository.load_game(self.game_id)
        if loaded_state:
            self.game_state = loaded_state
            # Ensure players list in game_state is comprised of full Player objects
            # GameState.from_dict should handle this.
            self.interface.show_message(f"Loaded saved game: {self.game_id}")
        else:
            self.interface.show_message(f"No saved game found. Starting new game: {self.game_id}")
            # Initialize players if not loaded (e.g. set stacks from settings)
            for player in self.game_state.players:
                if player.stack <= 0: # Ensure players start with fresh stacks if new game
                    player.stack = settings.STARTING_STACK

        # If a game was loaded, self.game_state.round_number is already set.
        # If new game, GameState dataclass defaults round_number to 0.
        # The increment to 1 for the first round happens in the loop.
        if not loaded_state:
            self.game_state.round_number = 0


        while not self.is_game_over():
            self.game_state.round_number += 1
            self.event_system.post(GameEvent(type="round_start", data={"round_number": self.game_state.round_number}))
            self.play_round()

            if self.game_state.is_game_over : # Check if play_round set it (e.g. player quit)
                # If game over by quit, reason might be set in game_state
                # Or we can add a specific flag/reason if action was "quit"
                break

            # Save state after each round
            self.repository.save_game(self.game_id, self.game_state)

            if self.is_game_over(): # Check again for conditions like only one player left
                break

        # Game ended
        final_reason = "Only one player remaining or max rounds reached."
        if hasattr(self.game_state, 'game_over_reason') and self.game_state.game_over_reason:
            final_reason = self.game_state.game_over_reason

        self.event_system.post(GameEvent(type="game_end", data={"reason": final_reason}))
        # Display final stats or winner if applicable
        # If game ended by quit, the quit message is already shown by _process_player_action
        if not (hasattr(self.game_state, 'game_over_reason') and hasattr(self.game_state.game_over_reason, 'lower') and "quit" in self.game_state.game_over_reason.lower()):
             self.interface.show_message("Game Over!")


    def is_game_over(self) -> bool:
        """Checks if the game should end (e.g., only one player has chips)."""
        if self.game_state.is_game_over: # Explicitly set by quit or other conditions
            return True

        # Game ends if only one (or zero) players have chips left
        players_with_chips = [p for p in self.game_state.players if p.stack > 0]
        if len(players_with_chips) <= 1:
            self.game_state.is_game_over = True # Set the flag
            if len(players_with_chips) == 1:
                self.game_state.game_over_reason = f"Player {players_with_chips[0].player_id} is the sole winner."
            elif not players_with_chips:
                 self.game_state.game_over_reason = "No players with chips remaining."
            else: # Should not happen if <=1
                 self.game_state.game_over_reason = "Game ended due to player count."
            return True

        # Could add max rounds from settings later
        # if settings.MAX_ROUNDS > 0 and self.game_state.round_number >= settings.MAX_ROUNDS:
        #    self.game_state.is_game_over = True
        #    self.game_state.game_over_reason = "Maximum rounds reached."
        #    return True

        return False

    def _setup_new_round(self):
        """Resets cards, pots, player statuses for a new round."""
        self.deck = Deck()
        self.game_state.community_cards = []
        self.game_state.pot_size = 0
        self.game_state.current_round_pot = 0
        self.game_state.last_raiser = None
        self.game_state.last_raise_amount = 0
        self.game_state.current_bet_to_match = 0
        self.game_state.small_blind_player_id = None # Reset for the new round
        self.game_state.big_blind_player_id = None   # Reset for the new round


        # Filter out players with 0 stack for this round's active players
        # Note: self.game_state.players still holds all original players for overall game tracking.
        self._active_round_players = [p for p in self.game_state.players if p.stack > 0]

        if len(self._active_round_players) < 2 : # Not enough players to continue
            self.game_state.is_game_over = True
            return

        for player in self.game_state.players: # Reset all players (even those with 0 stack, for consistency)
            player.reset_for_new_round()

        # Rotate dealer button among *active* players only
        # self.game_state.dealer_button_position is an index in the original self.game_state.players list.
        # We need to find the next *active* player for the button.

        current_dealer_player_id = self.game_state.players[self.game_state.dealer_button_position].player_id

        # Get a list of player_ids of active players in their original seating order.
        active_player_ids_in_order = [p.player_id for p in self.game_state.players if p.player_id in [ap.player_id for ap in self._active_round_players]]

        if not active_player_ids_in_order: # Should be caught by len(_active_round_players) < 2
             self.game_state.is_game_over = True
             return

        try:
            current_dealer_idx_among_actives = active_player_ids_in_order.index(current_dealer_player_id)
            next_dealer_id_among_actives = active_player_ids_in_order[(current_dealer_idx_among_actives + 1) % len(active_player_ids_in_order)]
        except ValueError: # Current dealer is no longer active, find next active from original dealer position
            found_next = False
            original_dealer_idx = self.game_state.dealer_button_position
            for i in range(1, len(self.game_state.players) + 1):
                next_potential_dealer_orig_idx = (original_dealer_idx + i) % len(self.game_state.players)
                if self.game_state.players[next_potential_dealer_orig_idx].player_id in active_player_ids_in_order:
                    next_dealer_id_among_actives = self.game_state.players[next_potential_dealer_orig_idx].player_id
                    found_next = True
                    break
            if not found_next: # Should not happen if active_player_ids_in_order is not empty
                self.game_state.is_game_over = True; return

        # Find the original index of this next dealer
        for i, p in enumerate(self.game_state.players):
            if p.player_id == next_dealer_id_among_actives:
                self.game_state.dealer_button_position = i
                break

        self.game_state.game_phase = "pre-flop"
        self.interface.display_round_start(self.game_state, self.game_state.round_number)


    def _post_blinds(self):
        """Posts small and big blinds using _active_round_players."""
        # _active_round_players is already filtered for players with stack > 0
        # and ordered by their original seating relative to each other.
        num_active_players = len(self._active_round_players)

        if num_active_players < 2:
            self.game_state.small_blind_player_id = None
            self.game_state.big_blind_player_id = None
            return

        # Find the dealer's index within the _active_round_players list
        dealer_player_from_main_list = self.game_state.players[self.game_state.dealer_button_position]

        dealer_idx_in_active = -1
        for i, p_active in enumerate(self._active_round_players):
            if p_active.player_id == dealer_player_from_main_list.player_id:
                dealer_idx_in_active = i
                break

        if dealer_idx_in_active == -1:
            # This implies the player at game_state.dealer_button_position has 0 stack.
            # _setup_new_round should have moved the button to an active player.
            # If this happens, it's an error in dealer button assignment.
            # For robustness, if dealer isn't active, pick first active as reference. (This is a patch)
            print(f"Warning: Dealer {dealer_player_from_main_list.player_id} is not in _active_round_players. Button logic error likely.")
            dealer_idx_in_active = 0 # Fallback, but indicates an issue upstream.

        sb_player: Player
        bb_player: Player

        if num_active_players == 2: # Heads-up: Dealer is SB, other is BB.
            sb_player = self._active_round_players[dealer_idx_in_active]
            bb_player = self._active_round_players[(dealer_idx_in_active + 1) % num_active_players]
        else: # 3+ players: SB is left of dealer, BB is left of SB.
            sb_player_idx_in_active = (dealer_idx_in_active + 1) % num_active_players
            bb_player_idx_in_active = (dealer_idx_in_active + 2) % num_active_players
            sb_player = self._active_round_players[sb_player_idx_in_active]
            bb_player = self._active_round_players[bb_player_idx_in_active]

        # Post Small Blind
        # Use game_state.small_blind (from settings) for the amount.
        sb_amount_to_post = min(self.game_state.small_blind, sb_player.stack)
        sb_player.place_bet(sb_amount_to_post)
        self.game_state.current_round_pot += sb_amount_to_post
        self.game_state.small_blind_player_id = sb_player.player_id
        self.event_system.post(GameEvent(type="player_action", data={"player_id": sb_player.player_id, "action_type": "small_blind", "amount": sb_amount_to_post}))

        # Post Big Blind
        bb_amount_to_post = min(self.game_state.big_blind, bb_player.stack)
        bb_player.place_bet(bb_amount_to_post)
        self.game_state.current_round_pot += bb_amount_to_post
        self.game_state.big_blind_player_id = bb_player.player_id
        self.event_system.post(GameEvent(type="player_action", data={"player_id": bb_player.player_id, "action_type": "big_blind", "amount": bb_amount_to_post}))

        self.game_state.current_bet_to_match = self.game_state.big_blind
        self.game_state.last_raiser = bb_player.player_id
        self.game_state.last_raise_amount = self.game_state.big_blind
        self.game_state.min_bet = self.game_state.big_blind


    def _deal_hole_cards(self):
        # _active_round_players list is already filtered for players with stack > 0
        num_active_players = len(self._active_round_players)
        if num_active_players == 0: return # Should be caught by _setup_new_round if len < 2

        # Find the dealer's index within the _active_round_players list
        dealer_player_from_main_list = self.game_state.players[self.game_state.dealer_button_position]
        dealer_active_player_idx = -1
        for i, p_active in enumerate(self._active_round_players):
            if p_active.player_id == dealer_player_from_main_list.player_id:
                dealer_active_player_idx = i
                break

        if dealer_active_player_idx == -1:
            # Should not happen if dealer button is always on an active player.
            print(f"Warning: Dealer {dealer_player_from_main_list.player_id} not in _active_round_players for dealing. Using first active as reference.")
            dealer_active_player_idx = 0 # Fallback

        # Deal one card at a time, starting left of dealer (in _active_round_players)
        start_deal_idx_in_active = (dealer_active_player_idx + 1) % num_active_players

        # In heads-up, dealer (SB) gets first card, then BB. Then second to SB, second to BB.
        # The (dealer_idx + 1) logic for start might be off for HU standard deal.
        # Standard HU: SB acts first preflop, gets first card. Dealer is SB.
        # So if dealer_active_player_idx is the dealer, they should be start_deal_idx_in_active for HU.
        if num_active_players == 2:
            start_deal_idx_in_active = dealer_active_player_idx # Dealer (SB) gets first card in HU


        for i in range(self.rules.get_initial_deal_count()): # 2 cards
            for j in range(num_active_players):
                player_to_deal_idx_in_active = (start_deal_idx_in_active + j) % num_active_players
                player = self._active_round_players[player_to_deal_idx_in_active]
                # player object is directly from _active_round_players, so stack > 0
                try:
                    card = self.deck.deal()[0]
                    player.hole_cards.append(card)
                except ValueError:
                    self.interface.show_message("Error: Not enough cards in deck to deal hole cards!")
                    self.game_state.is_game_over = True
                    return

        for player in self._active_round_players:
            self.event_system.post(GameEvent(type="cards_dealt_to_player", data={"player_id": player.player_id, "cards_count": len(player.hole_cards)}))
            if isinstance(player, HumanPlayer):
                self.interface.display_player_cards(player)

    def _deal_community_cards(self, phase: str):
        num_cards_to_deal = 0
        if phase == "flop":
            num_cards_to_deal = self.rules.get_flop_deal_count()
        elif phase == "turn":
            num_cards_to_deal = self.rules.get_turn_deal_count()
        elif phase == "river":
            num_cards_to_deal = self.rules.get_river_deal_count()

        if num_cards_to_deal > 0:
            if len(self.deck.cards) > num_cards_to_deal :
                self.deck.deal() # Burn card

            try:
                new_cards = self.deck.deal(num_cards_to_deal)
                self.game_state.community_cards.extend(new_cards)
                self.event_system.post(GameEvent(type="community_cards_dealt", data={"phase": phase, "cards": [str(c) for c in new_cards]}))
            except ValueError:
                self.interface.show_message(f"Error: Not enough cards in deck for {phase}!")
                self.game_state.is_game_over = True


    def _run_betting_round(self) -> bool:
        """
        Manages a single betting round.
        Returns True if round completed and betting should continue to next phase,
        False if only one player remains (everyone else folded) or game ended by quit.
        """

        # acting_order should only contain players who can act (not folded, not all-in, stack > 0)
        # TexasHoldemRules.get_betting_order filters by not folded and not all-in.
        # We must ensure that players with 0 stack and not all-in (i.e. busted from previous round)
        # are not included. _active_round_players (used by _post_blinds, _deal_hole_cards)
        # is already filtered by stack > 0.
        # The `acting_order` from `rules.get_betting_order` uses `self.game_state.players`.
        # This should be fine if `Player.is_all_in` is correctly managed for 0-stack players.
        # A player with 0 stack who isn't `is_all_in` is effectively out and should not be in `acting_order`.
        # `Player.reset_for_new_round` sets `is_all_in = False`.
        # So, `rules.get_betting_order` should correctly exclude them.

        acting_order = self.rules.get_betting_order(
            self.game_state.players,
            self.game_state.dealer_button_position,
            self.game_state.game_phase
        )

        if not acting_order:
            return True

        if self.game_state.game_phase != "pre-flop":
            self.game_state.current_bet_to_match = 0
            self.game_state.last_raiser = None
            self.game_state.last_raise_amount = 0
            for p in self._active_round_players:
                p.current_bet = 0

        current_player_index = 0
        num_actions_this_round = 0
        aggressor = self.game_state.last_raiser

        # Store the number of players who can act at the start of the round.
        # This helps determine if action has gone around fully.
        num_players_able_to_act_this_street = len(acting_order)


        while True:
            # If game ended by a quit action processed in the loop
            if self.game_state.is_game_over:
                return False # Signal game end

            non_folded_active_players = [p for p in self._active_round_players if not p.is_folded]
            if len(non_folded_active_players) <= 1:
                return False

            # This condition means all players in the original acting_order have had a turn
            # relative to the last aggressor, or everyone checked around.
            # More robust check: if current_player_index has looped and all bets are settled.
            # The loop termination logic below handles this.

            player = acting_order[current_player_index % len(acting_order)] # Use modulo for safety, though index should reset

            # display_game_state before asking for action
            self.interface.display_game_state(self.game_state, current_player_id=player.player_id, show_hole_cards_for_player=player.player_id if isinstance(player, HumanPlayer) else None)

            allowed_actions = self.rules.get_allowed_actions(player, self.game_state)

            action: Action
            if not allowed_actions: # Should only happen if player is all-in and no valid action like check
                 action = Action(type="check", player_id=player.player_id)
            elif isinstance(player, HumanPlayer):
                action = self.interface.get_player_action(player, self.game_state, allowed_actions)
            elif isinstance(player, BotPlayer):
                action = player.make_decision(self.game_state)
            else: # Should not happen
                action = Action(type="fold", player_id=player.player_id)

            num_actions_this_round +=1
            action_valid_and_processed = self._process_player_action(player, action, allowed_actions)

            if not action_valid_and_processed and action.type != "quit": # If quit, game over is set, loop will exit
                self.interface.show_message(f"Action by {player.player_id} was invalid and not processed. Defaulting to FOLD.")
                # Ensure fold is actually processed if this path is taken
                # This indicates a deeper issue if _process_player_action returns False for non-quit.
                # For now, assume _process_player_action handles forced folds.
                # If it returned False, it means it couldn't even process a default fold.
                # This part of the logic is slightly risky.
                # A safer _process_player_action always returns True by forcing valid action.
                # The current _process_player_action forces a fold on invalid check/bet/raise if it can't map.
                # But if action.type was not in allowed and not one of those, it returns False.
                # Let's ensure that if an action is truly invalid, it's forced to fold here.
                if "fold" in allowed_actions : # Check if fold is even possible
                    player.fold()
                    self.event_system.post(GameEvent(type="player_action", data={"player_id": player.player_id, "action_type": "fold", "amount": 0}))
                else: # Very rare, player cannot fold (e.g. already all-in and was asked to act?)
                    pass # No action taken, this player might be stuck.

            if self.game_state.is_game_over: # Check if action (like quit) ended the game
                return False

            # Post-action display (optional, as next player's turn will also display)
            # self.interface.display_game_state(self.game_state)

            # Update aggressor if a bet or raise occurred
            if action.type == "bet" or action.type == "raise":
                aggressor = player.player_id
                # When a bet or raise occurs, action must go around the table again
                # for all players who haven't folded, up to the aggressor.
                # Reset num_actions_this_round or use a different way to track "closing the action".
                num_actions_this_round = 1 # Current player acted, others need to respond.
                num_players_able_to_act_this_street = 0
                temp_idx = (current_player_index + 1) % len(acting_order)
                # Count how many players are still to act before action comes back to current aggressor
                for _ in range(len(acting_order)):
                    p_check = acting_order[temp_idx]
                    if not p_check.is_folded and not p_check.is_all_in:
                        num_players_able_to_act_this_street +=1
                    if p_check.player_id == aggressor:
                        break # Stop counting once we reach the aggressor again
                    temp_idx = (temp_idx + 1) % len(acting_order)


            # Check betting round end conditions
            betting_concluded = False
            # Condition 1: All players have acted (or had the chance to act) since the last aggressive action.
            # And the bets are now matched by everyone still in.
            if num_actions_this_round >= num_players_able_to_act_this_street :
                all_bets_settled = True
                for p_check in acting_order: # Check all players in original acting order
                    if p_check.is_folded or p_check.is_all_in:
                        continue
                    if p_check.current_bet < self.game_state.current_bet_to_match:
                        all_bets_settled = False
                        break
                if all_bets_settled:
                    # If it was checked around (no aggressor, or aggressor was BB and no raise)
                    # or if action has made it back to the aggressor who doesn't need to act again.
                    # The player whose turn it would be "next" is the one who opened action or was the last aggressor.
                    next_player_to_act_idx = (current_player_index + 1) % len(acting_order)
                    next_player_obj = acting_order[next_player_to_act_idx]

                    # If there was an aggressor, action ends when it's back to them and they don't need to act more.
                    # Or if no aggressor (checked around) and everyone has acted.
                    if aggressor is None : # Checked around
                        betting_concluded = True
                    elif next_player_obj.player_id == aggressor : # Action is back to the last aggressor
                         betting_concluded = True
                    # Special pre-flop BB option: if BB was aggressor (posted BB), and action came back
                    # to BB with no raises, BB has option to raise. If BB checks option, round ends.
                    # This is handled by `player.player_id == aggressor` check in the original betting loop logic.
                    # The current `all_bets_settled` implies that if `next_player_obj` is the aggressor,
                    # they don't need to do anything more as their bet is the one matched.

            if betting_concluded:
                break

            current_player_index = (current_player_index + 1) % len(acting_order)
            # If current_player_index wraps around, it means a full pass of acting_order has occurred.
            # The num_actions_this_round and aggressor logic should handle termination.

        # After loop, collect bets into main pot
        self.game_state.pot_size += self.game_state.current_round_pot
        self.game_state.current_round_pot = 0

        non_folded_players = [p for p in self._active_round_players if not p.is_folded]
        return len(non_folded_players) > 1


    def _process_player_action(self, player: Player, action: Action, allowed: Dict[str,Any]) -> bool:
        """Processes a player's action, updates game state. Returns True if action was valid and processed."""

        # If player tries to act when it's not allowed (e.g. action.type not in allowed by rules)
        # This first check is crucial.
        if action.type not in allowed and action.type != "quit": # Allow "quit" even if not in allowed_actions from rules
            self.interface.show_message(f"Action {action.type} by {player.player_id} is not in allowed actions: {list(allowed.keys())}. Defaulting to FOLD.")
            if "fold" in allowed: # If fold is a valid option
                player.fold()
                # Post fold event directly here as we are overriding the action
                self.event_system.post(GameEvent(type="player_action", data={"player_id": player.player_id, "action_type": "fold", "amount": 0}))
            # If fold is not allowed (e.g. all-in player, no action possible), this is a game state error.
            # For now, this means the action is simply not processed further if it can't be folded.
            return True # Considered "processed" by defaulting to fold or doing nothing if fold impossible.

        amount_to_call_for_player = self.game_state.current_bet_to_match - player.current_bet

        if action.type == "quit":
            self.interface.show_message(f"Player {player.player_id} chose to quit the game.")
            self.game_state.is_game_over = True
            self.game_state.game_over_reason = f"Player {player.player_id} quit." # Store reason
            return True

        if action.type == "fold":
            player.fold()
        elif action.type == "check":
            if amount_to_call_for_player > 0:
                # This should ideally be caught by allowed_actions check above or by interface validation.
                self.interface.show_message(f"Invalid Check by {player.player_id}. Must call {amount_to_call_for_player}. Auto-folding.")
                player.fold()
                # Post fold event as it's a forced action
                self.event_system.post(GameEvent(type="player_action", data={"player_id": player.player_id, "action_type": "fold", "amount": 0}))
                return True
        elif action.type == "call":
            if amount_to_call_for_player <= 0: # Calling nothing or when already matched
                 pass # Effectively a check.
            else:
                # `allowed["call"]` should be the exact amount player needs to add to pot to call.
                # `action.amount` from interface should match this.
                call_amount_to_add = action.amount
                # Validate if action.amount matches the required call amount from allowed_actions
                if call_amount_to_add != allowed['call']:
                     # This could happen if interface sends a different call amount than rules determined.
                     # Or if bot calculates incorrectly.
                     print(f"Warning: Call amount mismatch for {player.player_id}. Action amount: {action.amount}, Expected to add: {allowed['call']}. Using expected.")
                     call_amount_to_add = allowed['call']

                # Ensure player doesn't call more than they have left after current_bet
                # Player.place_bet handles betting more than stack (all-in).
                # The amount passed to place_bet is the additional amount for this action.
                actual_bet_from_stack = player.place_bet(call_amount_to_add)
                self.game_state.current_round_pot += actual_bet_from_stack

        elif action.type == "bet":
            # `action.amount` is the size of the bet itself.
            # This is an opening bet, so player.current_bet should be 0 for this street.
            # (This is reset for players in _run_betting_round for post-flop)
            # `allowed["bet"]` contains min/max for this bet action.
            min_bet_val = allowed.get("bet",{}).get("min", self.game_state.big_blind)
            max_bet_val = allowed.get("bet",{}).get("max", player.stack)

            if not (min_bet_val <= action.amount <= max_bet_val):
                self.interface.show_message(f"Invalid bet amount {action.amount} by {player.player_id}. Range: ({min_bet_val}-{max_bet_val}). Auto-folding.")
                player.fold()
                self.event_system.post(GameEvent(type="player_action", data={"player_id": player.player_id, "action_type": "fold", "amount": 0}))
                return True

            actual_bet_from_stack = player.place_bet(action.amount)
            self.game_state.current_round_pot += actual_bet_from_stack
            self.game_state.current_bet_to_match = player.current_bet
            self.game_state.last_raiser = player.player_id
            self.game_state.last_raise_amount = action.amount
            self.game_state.min_bet = action.amount


        elif action.type == "raise":
            # `action.amount` is the TOTAL amount the player is making their bet to for this street.
            # `allowed["raise"]` contains min_total_bet and max_total_bet.
            min_total_bet = allowed.get("raise",{}).get("min_total_bet", 0)
            max_total_bet = allowed.get("raise",{}).get("max_total_bet", 0)

            if not (min_total_bet <= action.amount <= max_total_bet):
                self.interface.show_message(f"Invalid raise (total) amount {action.amount} by {player.player_id}. Range: ({min_total_bet}-{max_total_bet}). Auto-folding.")
                player.fold()
                self.event_system.post(GameEvent(type="player_action", data={"player_id": player.player_id, "action_type": "fold", "amount": 0}))
                return True

            amount_to_add_to_pot = action.amount - player.current_bet # Amount player adds from stack this action

            actual_bet_from_stack = player.place_bet(amount_to_add_to_pot)
            self.game_state.current_round_pot += actual_bet_from_stack

            size_of_this_raise_increment = player.current_bet - self.game_state.current_bet_to_match # The amount the bet *increased by*

            self.game_state.current_bet_to_match = player.current_bet
            self.game_state.last_raiser = player.player_id
            self.game_state.last_raise_amount = size_of_this_raise_increment
            self.game_state.min_bet = size_of_this_raise_increment


        if player.stack == 0 and not player.is_all_in:
             player.is_all_in = True

        return True


    def _determine_winners_and_distribute_pot(self):
        showdown_hand_results = {}
        if self.game_state.game_phase == "showdown":
            # Include only players who are not folded for hand evaluation results passed to interface
            for p in self._active_round_players: # _active_round_players are those who started round with chips
                if not p.is_folded and p.hole_cards: # Check if they are still in and have cards
                    community = self.game_state.community_cards if self.game_state.community_cards is not None else []
                    hand_name, best_cards, rank_val, kickers = self.hand_evaluator.evaluate_hand(p.hole_cards, community)
                    showdown_hand_results[p.player_id] = {
                        "hand_name": hand_name, "best_cards": best_cards,
                        "rank_val": rank_val, "kickers": kickers
                    }

        # determine_winners itself filters for non-folded players from game_state.players
        winners_data = self.rules.determine_winners(self.game_state)

        if not winners_data:
            # This case should ideally be handled if, e.g., only one non-folded player remains before showdown.
            # self.rules.determine_winners should return that one player.
            # If it's truly empty, means something went wrong or all players folded simultaneously (not possible).
            non_folded_players = [p for p in self.game_state.players if not p.is_folded and p.stack > 0]
            if len(non_folded_players) == 1:
                winner_player = non_folded_players[0]
                pot_to_win = self.game_state.pot_size + self.game_state.current_round_pot
                winner_player.stack += pot_to_win
                winners_data = [{"player_id": winner_player.player_id, "amount_won": pot_to_win, "hand_name": " uncontested_pot", "best_cards": []}]
                self.event_system.post(GameEvent(type="pot_distributed", data={"player_id": winner_player.player_id, "amount": pot_to_win, "hand": " uncontested_pot"}))
            else:
                self.interface.show_message("No winners determined. Pot remains or error.")
                # Pot should not just remain, it should be awarded. This state implies an issue.
                # For now, if this rare case is hit, pot is effectively lost or not awarded by this logic path.
                # This needs review if it ever occurs. A pot should always be awarded if players bet.
                self.game_state.pot_size = 0 # Clear pot anyway to prevent carry-over issues
                self.game_state.current_round_pot = 0
                self.interface.display_winner([], self.game_state, showdown_hand_results) # Display no winner
                return


        for winner_info in winners_data:
            winner_player = self.game_state.get_player_by_id(winner_info["player_id"])
            if winner_player: # Should always find the player
                winner_player.stack += winner_info["amount_won"]
                self.event_system.post(GameEvent(type="pot_distributed",
                                                 data={"player_id": winner_player.player_id,
                                                       "amount": winner_info["amount_won"],
                                                       "hand": winner_info.get("hand_name")}))

        self.interface.display_winner(winners_data, self.game_state, showdown_hand_results)

        self.game_state.pot_size = 0
        self.game_state.current_round_pot = 0

    def play_round(self):
        """Plays a single round of poker (pre-flop, flop, turn, river, showdown)."""
        self._setup_new_round()

        if self.game_state.is_game_over: return

        self._post_blinds()
        # After blinds, check if game ends (e.g. only one player could post/afford blinds)
        if self.is_game_over(): return
        # Also check if _active_round_players is < 2 after blinds (e.g. someone went all-in on blinds)
        if len([p for p in self._active_round_players if p.stack > 0 or p.is_all_in]) < 2 and not \
           (len(self._active_round_players) == 1 and self._active_round_players[0].is_all_in): # Check if only one player is effectively left to win uncontested
            # This logic is tricky: if one player is all-in on blinds and other folds, all-in wins.
            # For now, rely on _run_betting_round and determine_winners to handle these edge cases.
            pass


        self._deal_hole_cards()
        if self.game_state.is_game_over: return

        round_continues = True
        for phase in ["pre-flop", "flop", "turn", "river"]:
            if self.game_state.is_game_over: break # Check before starting phase if quit happened

            self.game_state.game_phase = phase
            self.event_system.post(GameEvent(type="phase_start", data={"phase": phase}))

            if phase != "pre-flop":
                for p in self._active_round_players:
                    if not p.is_all_in: # Don't reset current_bet for all-in players from previous street
                        p.current_bet = 0
                self.game_state.current_bet_to_match = 0
                self.game_state.last_raiser = None
                self.game_state.last_raise_amount = 0
                self.game_state.min_bet = self.game_state.big_blind


            # Deal community cards if it's flop, turn, or river
            # But only if more than one player is still active (not folded)
            players_still_in_hand = [p for p in self._active_round_players if not p.is_folded]
            if len(players_still_in_hand) <= 1 and phase != "pre-flop": # If only one left, no more cards/betting
                round_continues = False
                break

            if phase in ["flop", "turn", "river"]:
                self._deal_community_cards(phase)
                if self.is_game_over(): return

            # Check for game end by quit before betting round
            if self.game_state.is_game_over: return # Changed from False to ensure it stops play_round


            # If all but one player are all-in, or only one player not all-in, no more betting.
            # Deal all remaining cards if betting cannot continue.
            players_who_can_bet = [p for p in players_still_in_hand if not p.is_all_in and p.stack > 0]

            if len(players_still_in_hand) > 1 and len(players_who_can_bet) <= 1 :
                 # If 0 or 1 player can still bet, but multiple are in hand (some all-in)
                self.interface.show_message("No more betting possible this round. Dealing remaining cards.")
                # Fast-forward community cards
                current_phase_index = TexasHoldemRules.GAME_PHASES.index(phase)
                if current_phase_index < TexasHoldemRules.GAME_PHASES.index("flop"):
                    if len(self.game_state.community_cards) < 3: self._deal_community_cards("flop")
                    if self.is_game_over(): return
                if current_phase_index < TexasHoldemRules.GAME_PHASES.index("turn"):
                    if len(self.game_state.community_cards) < 4: self._deal_community_cards("turn")
                    if self.is_game_over(): return
                if current_phase_index < TexasHoldemRules.GAME_PHASES.index("river"):
                    if len(self.game_state.community_cards) < 5: self._deal_community_cards("river")
                    if self.is_game_over(): return

                round_continues = False # No more betting, proceed to showdown after this
                break # End phase loop, go to showdown logic

            if not players_still_in_hand: # Should be caught by len <=1 above
                round_continues = False; break


            round_continues = self._run_betting_round()
            # display_game_state is called within _run_betting_round before player action
            # and by this loop after _run_betting_round if needed (but example doesn't show it there)
            # The current flow: display_game_state -> player_action -> notify_event (logs action) -> next player display_game_state
            # This seems fine.

            if not round_continues or self.game_state.is_game_over:
                break

        # Showdown or award pot
        self.game_state.game_phase = "showdown"
        self.event_system.post(GameEvent(type="phase_start", data={"phase": "showdown"}))
        # Show final state before winner announcement, ensuring all cards are revealed if it's a showdown
        self.interface.display_game_state(self.game_state, show_hole_cards_for_player=None)
        self._determine_winners_and_distribute_pot()

        # This event might be redundant if game_over event is more comprehensive
        self.event_system.post(GameEvent(type="round_end", data={"round_number": self.game_state.round_number}))

        # Final display for the round (shows updated stacks)
        # Only if game is not over by quit, otherwise quit message is enough.
        if not (hasattr(self.game_state, 'game_over_reason') and self.game_state.game_over_reason and "quit" in self.game_state.game_over_reason.lower()):
            self.interface.display_game_state(self.game_state)

        # Check for game over condition (e.g. one player has all chips)
        # is_game_over() is called at the start of the main game loop in start_game()
        # If a player quit, self.game_state.is_game_over is already true.
        pass
```
