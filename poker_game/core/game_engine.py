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
        self.interface.show_message("Poker game started!")

        # Try to load existing game, if any
        loaded_state = self.repository.load_game(self.game_id)
        if loaded_state:
            self.game_state = loaded_state
            self.interface.show_message(f"Loaded saved game: {self.game_id}")
        else:
            self.interface.show_message(f"No saved game found. Starting new game: {self.game_id}")
            # Initialize players if not loaded (e.g. set stacks from settings)
            for player in self.game_state.players:
                if player.stack <= 0: # Ensure players start with fresh stacks if new game
                    player.stack = settings.STARTING_STACK

        self.game_state.round_number = self.game_state.round_number if loaded_state else 0

        while not self.is_game_over():
            self.game_state.round_number += 1
            self.event_system.post(GameEvent(type="round_start", data={"round_number": self.game_state.round_number}))
            self.play_round()

            # Save state after each round
            self.repository.save_game(self.game_id, self.game_state)

            if self.is_game_over(): # Check again after round
                break

            # Ask to continue or quit (optional feature)
            # For now, auto-continue if not game over

        self.event_system.post(GameEvent(type="game_end", data={"reason": "Game over condition met."}))
        self.interface.show_message("Game Over!")
        # Display final stats or winner if applicable

    def is_game_over(self) -> bool:
        """Checks if the game should end (e.g., only one player has chips)."""
        if self.game_state.is_game_over: # Explicitly set
            return True

        players_with_chips = [p for p in self.game_state.players if p.stack > 0]
        if len(players_with_chips) <= 1:
            self.game_state.is_game_over = True
            return True

        # Could add max rounds from settings later
        # if settings.MAX_ROUNDS > 0 and self.game_state.round_number >= settings.MAX_ROUNDS:
        #    self.game_state.is_game_over = True
        #    return True

        return False

    def _setup_new_round(self):
        """Resets cards, pots, player statuses for a new round."""
        self.deck = Deck() # Fresh deck
        self.game_state.community_cards = []
        self.game_state.pot_size = 0 # Main pot from previous rounds collected
        self.game_state.current_round_pot = 0 # Bets in this specific betting phase
        self.game_state.last_raiser = None
        self.game_state.last_raise_amount = 0
        self.game_state.current_bet_to_match = 0 # Reset for the new round's betting

        for player in self.game_state.players:
            player.reset_for_new_round() # Resets hole_cards, current_bet, is_folded, is_all_in
            if player.stack == 0 and not any(p.player_id == player.player_id for p in self._active_round_players):
                # If player busted in a previous round and is not part of current setup.
                # This logic might be better handled by removing players with 0 stack from game_state.players list
                # or marking them as 'out_of_game'. For now, they just can't play.
                pass

        # Rotate dealer button (skip players with 0 stack for button position)
        active_player_indices = [i for i, p in enumerate(self.game_state.players) if p.stack > 0]
        if not active_player_indices: # Should be caught by is_game_over
            self.game_state.is_game_over = True
            return

        current_dealer_original_index = self.game_state.dealer_button_position
        try:
            # Find current dealer's position in the active player list
            current_dealer_active_idx = active_player_indices.index(current_dealer_original_index)
            next_dealer_active_idx = (current_dealer_active_idx + 1) % len(active_player_indices)
            self.game_state.dealer_button_position = active_player_indices[next_dealer_active_idx]
        except ValueError: # If current dealer is no longer active, find next active from original position
            pos = self.game_state.dealer_button_position
            while True:
                pos = (pos + 1) % len(self.game_state.players)
                if self.game_state.players[pos].stack > 0:
                    self.game_state.dealer_button_position = pos
                    break
                if pos == self.game_state.dealer_button_position: # Full circle, only one or no active players
                    break # Should be caught by game_over

        self.game_state.game_phase = "pre-flop"
        self._active_round_players = [p for p in self.game_state.players if p.stack > 0] # Players eligible for this round

        self.interface.display_round_start(self.game_state, self.game_state.round_number)


    def _post_blinds(self):
        """Posts small and big blinds."""
        num_active_players = len(self._active_round_players)
        if num_active_players < 2: # Not enough players for blinds
            return

        # Determine players relative to the button, considering only active players for posting blinds
        # This needs to map dealer_button_position (original index) to active player list.

        # Simple approach: use original player list indices for button, SB, BB calculations
        # but only collect from players who are active (stack > 0).

        players_in_game = self.game_state.players # All players, active or not for position calculation
        num_total_players = len(players_in_game)

        # Find SB position (player to the left of dealer)
        sb_pos = (self.game_state.dealer_button_position + 1) % num_total_players
        while players_in_game[sb_pos].stack == 0: # Skip busted players for SB
            sb_pos = (sb_pos + 1) % num_total_players
            if sb_pos == self.game_state.dealer_button_position: # Cycled through all, only dealer left or no one
                return # Should not happen if game_over is checked

        # Find BB position (player to the left of SB)
        bb_pos = (sb_pos + 1) % num_total_players
        while players_in_game[bb_pos].stack == 0: # Skip busted players for BB
            bb_pos = (bb_pos + 1) % num_total_players
            if bb_pos == sb_pos : # Cycled through all, only SB found or no one else
                 # Heads-up: dealer is SB, other is BB.
                if num_active_players == 2:
                    # Dealer posts SB, other posts BB.
                    # If sb_pos was dealer, then bb_pos needs to be the other active player.
                    # This logic gets complex with inactive players.
                    # Let's use _active_round_players which is simpler for HU.
                    if num_active_players == 2:
                        # Find dealer in _active_round_players
                        dealer_active_idx = -1
                        for i, p in enumerate(self._active_round_players):
                            if p.player_id == players_in_game[self.game_state.dealer_button_position].player_id:
                                dealer_active_idx = i
                                break
                        if dealer_active_idx != -1:
                            sb_player_active = self._active_round_players[dealer_active_idx]
                            bb_player_active = self._active_round_players[(dealer_active_idx + 1) % num_active_players]

                            sb_player_active = self._active_round_players[dealer_active_idx]
                            bb_player_active = self._active_round_players[(dealer_active_idx + 1) % num_active_players]

                            # DEBUG: Using settings directly for SB/BB amounts in HU
                            sb_val = settings.SMALL_BLIND # Direct from settings
                            bb_val = settings.BIG_BLIND   # Direct from settings

                            sb_amount = sb_player_active.place_bet(min(sb_val, sb_player_active.stack))
                            self.game_state.current_round_pot += sb_amount
                            self.game_state.small_blind_player_id = sb_player_active.player_id # Set SB player ID
                            self.event_system.post(GameEvent(type="player_action", data={"player_id": sb_player_active.player_id, "action_type": "small_blind", "amount": sb_amount}))

                            bb_amount = bb_player_active.place_bet(min(bb_val, bb_player_active.stack))
                            self.game_state.current_round_pot += bb_amount
                            self.game_state.big_blind_player_id = bb_player_active.player_id # Set BB player ID
                            self.event_system.post(GameEvent(type="player_action", data={"player_id": bb_player_active.player_id, "action_type": "big_blind", "amount": bb_amount}))

                            self.game_state.current_bet_to_match = self.game_state.big_blind
                            self.game_state.last_raiser = bb_player_active.player_id # BB is the first "bet"
                            self.game_state.last_raise_amount = self.game_state.big_blind # Effectively
                            return # HU blinds posted.

                # If not HU and BB loops back to SB, something is wrong or only one player can post.
                return


        sb_player = players_in_game[sb_pos]
        bb_player = players_in_game[bb_pos]

        # Post Small Blind
        sb_amount = sb_player.place_bet(min(self.game_state.small_blind, sb_player.stack)) # Using game_state.small_blind here
        self.game_state.current_round_pot += sb_amount
        self.game_state.small_blind_player_id = sb_player.player_id # Set SB player ID
        self.event_system.post(GameEvent(type="player_action", data={"player_id": sb_player.player_id, "action_type": "small_blind", "amount": sb_amount}))

        # Post Big Blind
        bb_amount = bb_player.place_bet(min(self.game_state.big_blind, bb_player.stack)) # Using game_state.big_blind here
        self.game_state.current_round_pot += bb_amount
        self.game_state.big_blind_player_id = bb_player.player_id # Set BB player ID
        self.event_system.post(GameEvent(type="player_action", data={"player_id": bb_player.player_id, "action_type": "big_blind", "amount": bb_amount}))

        self.game_state.current_bet_to_match = self.game_state.big_blind
        self.game_state.last_raiser = bb_player.player_id # BB is the initial "bet" to match or raise.
        self.game_state.last_raise_amount = self.game_state.big_blind # The "raise" amount is the BB itself.
        # Min_bet for the round is also BB.
        self.game_state.min_bet = self.game_state.big_blind


    def _deal_hole_cards(self):
        num_active_players = len(self._active_round_players)
        if num_active_players == 0: return

        # Deal one card at a time, starting left of dealer
        # Need to map dealer_button_position to _active_round_players list.
        # For simplicity, let's find the starting active player index.

        start_deal_idx = 0
        dealer_player_id = self.game_state.players[self.game_state.dealer_button_position].player_id

        # Find dealer in active players list
        dealer_active_player_idx = -1
        for i, p in enumerate(self._active_round_players):
            if p.player_id == dealer_player_id:
                dealer_active_player_idx = i
                break

        if dealer_active_player_idx != -1:
            start_deal_idx = (dealer_active_player_idx + 1) % num_active_players
        else: # Dealer is not active, start from first active player (arbitrary but consistent)
            start_deal_idx = 0


        for i in range(self.rules.get_initial_deal_count()): # 2 cards
            for j in range(num_active_players):
                player_to_deal_idx = (start_deal_idx + j) % num_active_players
                player = self._active_round_players[player_to_deal_idx]
                if player.stack > 0: # Should always be true for _active_round_players
                    try:
                        card = self.deck.deal()[0]
                        player.hole_cards.append(card)
                    except ValueError: # Not enough cards
                        self.interface.show_message("Error: Not enough cards in deck to deal hole cards!")
                        self.game_state.is_game_over = True # Critical error
                        return

        for player in self._active_round_players:
            # Event for card dealing (could be private to player via interface)
            # For console, we might show the human player their cards.
            self.event_system.post(GameEvent(type="cards_dealt_to_player", data={"player_id": player.player_id, "cards_count": len(player.hole_cards)}))
            if isinstance(player, HumanPlayer):
                self.interface.display_player_cards(player) # Show human their cards

    def _deal_community_cards(self, phase: str):
        num_cards_to_deal = 0
        if phase == "flop":
            num_cards_to_deal = self.rules.get_flop_deal_count()
        elif phase == "turn":
            num_cards_to_deal = self.rules.get_turn_deal_count()
        elif phase == "river":
            num_cards_to_deal = self.rules.get_river_deal_count()

        if num_cards_to_deal > 0:
            # Burn a card (optional, but standard)
            if len(self.deck.cards) > num_cards_to_deal : # Check if enough cards for burn + deal
                self.deck.deal() # Burn card

            try:
                new_cards = self.deck.deal(num_cards_to_deal)
                self.game_state.community_cards.extend(new_cards)
                self.event_system.post(GameEvent(type="community_cards_dealt", data={"phase": phase, "cards": [str(c) for c in new_cards]}))
            except ValueError:
                self.interface.show_message(f"Error: Not enough cards in deck for {phase}!")
                self.game_state.is_game_over = True # Critical error


    def _run_betting_round(self) -> bool:
        """
        Manages a single betting round (pre-flop, flop, turn, river).
        Returns True if round completed normally, False if only one player remains (everyone else folded).
        """
        # Determine order of play based on rules (TexasHoldemRules.get_betting_order)
        # For _active_round_players, we need players who are not folded AND not all-in.
        # All-in players don't act but are still in the hand.

        # Players who can still make decisions in this betting round
        # This list will shrink as players act or fold.
        # The order is crucial.

        # Get initial acting order for this round
        # Players eligible to act: not folded, not all-in.
        acting_order = self.rules.get_betting_order(
            self.game_state.players, # Pass all players for position calculation
            self.game_state.dealer_button_position,
            self.game_state.game_phase
        )

        if not acting_order: # No one can act (e.g. all but one are all-in or folded)
            return True # Betting round effectively ends

        # Initial bet to match for this round for players who haven't acted yet.
        # Pre-flop, BB is current_bet_to_match. Post-flop, it's 0 until a bet.
        if self.game_state.game_phase != "pre-flop":
            self.game_state.current_bet_to_match = 0
            self.game_state.last_raiser = None # No one has bet/raised yet this street
            self.game_state.last_raise_amount = 0
            for p in self._active_round_players: # Reset current_bet for post-flop rounds
                p.current_bet = 0 # Bets are per street

        # Track who has acted and if betting should end
        # Betting ends when:
        # 1. All players have had a turn and all bets are matched (no pending raise).
        # 2. Only one player remains (all others folded).

        current_player_index = 0 # Index in the 'acting_order' list
        num_actions_this_round = 0 # To ensure everyone gets at least one chance if no raise

        # The player who made the last aggressive action (bet or raise) that needs to be matched.
        # If None, action continues until all players have checked or acted on an initial bet.
        aggressor = self.game_state.last_raiser # Pre-flop, BB is initial aggressor. Post-flop, None.
        # If post-flop, first player to bet becomes aggressor.

        # Correct starting player for pre-flop: player after BB (UTG or SB in HU)
        # Correct starting player for post-flop: player after dealer button
        # `acting_order` from `rules.get_betting_order` should already be correct.

        while True:
            # Check if only one player is left who hasn't folded
            non_folded_players = [p for p in self._active_round_players if not p.is_folded]
            if len(non_folded_players) <= 1:
                return False # Round ends, proceed to showdown or award pot

            if current_player_index >= len(acting_order): # Should not happen if logic is correct
                # This means we've looped through all initially eligible players.
                # If aggressor is still set, it implies the loop should have continued or ended.
                # This state might indicate all remaining players are all-in or checked around.
                break


            player = acting_order[current_player_index]

            # If player has folded or is all-in already, skip them for *action choice*
            # (all-in players are still in for showdown if they got that far)
            if player.is_folded or player.is_all_in:
                # If this player was the aggressor and now they are skipped, means others matched them.
                if aggressor == player.player_id and player.is_all_in:
                    # If an all-in player was the last aggressor, action continues until
                    # all other players have acted once more to match/raise this all-in.
                    # This is complex. For now, if aggressor is all-in, others must call/fold.
                    # The loop condition needs to handle "action completed back to aggressor".
                    pass # Let loop continue, but this player doesn't act.

                current_player_index += 1
                if current_player_index >= len(acting_order): # Check if we completed a full pass
                    # If we've passed through all players and the current bet is matched by everyone still in
                    # or everyone has checked around.
                    # Condition: current_player_index means we are about to start a new loop or end.
                    # If last_raiser is None (checked around) or if current player is last_raiser
                    # and all bets are equal, then round ends.
                    all_bets_matched = True
                    active_bettors = [p for p in acting_order if not p.is_folded and not p.is_all_in and p.current_bet < self.game_state.current_bet_to_match]
                    if not active_bettors: # No one left who needs to call a higher bet
                        if self.game_state.last_raiser is None or \
                           (len(acting_order) > 0 and acting_order[0].player_id == self.game_state.last_raiser and num_actions_this_round >= len(acting_order)):
                             break # Checked around, or action is back to the initial aggressor who doesn't need to act again.
                    # This break condition is tricky. Simpler: if num_actions >= num_players_in_round AND all bets are equal.
                    if num_actions_this_round >= len(acting_order):
                        bets_equal = True
                        first_bet_val = -1
                        for p_check in acting_order:
                            if p_check.is_folded or p_check.is_all_in: continue
                            if first_bet_val == -1: first_bet_val = p_check.current_bet
                            elif p_check.current_bet != first_bet_val:
                                bets_equal = False; break
                        if bets_equal and self.game_state.current_bet_to_match == first_bet_val : break


                if current_player_index >= len(acting_order) and aggressor is None and num_actions_this_round >= len(acting_order):
                    # Everyone checked around
                     break
                if current_player_index >= len(acting_order) and aggressor is not None:
                    # Action has made a full circle back to where the aggressor would be (or passed them if they were early)
                    # Check if all active (non-folded, non-all-in) players have bet amounts equal to current_bet_to_match
                    all_called_or_folded = True
                    for p_check in acting_order:
                        if not p_check.is_folded and not p_check.is_all_in:
                            if p_check.current_bet < self.game_state.current_bet_to_match:
                                all_called_or_folded = False
                                break
                    if all_called_or_folded:
                        break # Betting round ends

                if current_player_index >= len(acting_order): # Reset for next loop if betting continues
                    current_player_index = 0
                    if aggressor is None and num_actions_this_round > 0: # If someone bet after checks
                        # This means the first bettor became the aggressor, and we need to loop again.
                        # Aggressor should have been set by a "bet" action.
                        pass # Loop will continue.
                    elif aggressor is None and num_actions_this_round == 0 : # Still checking
                        pass # Should not happen if acting_order is not empty.
                    # If aggressor is set, we are waiting for action to come back to them or all match.

                continue # Skip to next player if current is folded/all-in


            self.interface.display_game_state(self.game_state, current_player_id=player.player_id, show_hole_cards_for_player=player.player_id if isinstance(player, HumanPlayer) else None)

            allowed_actions = self.rules.get_allowed_actions(player, self.game_state)

            if not allowed_actions or (len(allowed_actions) == 1 and "fold" in allowed_actions and player.stack == 0) : # Should be caught by all-in
                 action = Action(type="check", player_id=player.player_id) # Effectively a pass
            elif isinstance(player, HumanPlayer):
                action = self.interface.get_player_action(player, self.game_state, allowed_actions)
            elif isinstance(player, BotPlayer):
                action = player.make_decision(self.game_state) # Bots need full game_state to make informed decisions
                                                              # Bot decision logic should internally use allowed_actions
                                                              # or GameEngine should validate bot action.
                # Validate Bot Action (basic)
                if action.type == "call" and "call" not in allowed_actions: action.type = "check" if "check" in allowed_actions else "fold"
                if action.type == "bet" and "bet" not in allowed_actions: action.type = "check" if "check" in allowed_actions else "fold"
                # More validation needed here. For now, assume bot plays validly based on its logic.
            else:
                # Should not happen with defined player types
                action = Action(type="fold", player_id=player.player_id)

            num_actions_this_round +=1
            action_valid = self._process_player_action(player, action, allowed_actions)

            if not action_valid:
                # This can happen if Human input is faulty beyond simple retries in interface,
                # or if Bot provides an invalid action despite allowed_actions.
                # For now, if action is invalid at this stage, force fold.
                self.interface.show_message(f"Invalid action from {player.player_id}. Defaulting to FOLD.")
                action = Action(type="fold", player_id=player.player_id)
                self._process_player_action(player,action, {"fold":True}) # Process the fold


            self.event_system.post(GameEvent(type="player_action",
                                             data={"player_id": player.player_id,
                                                   "action_type": action.type,
                                                   "amount": action.amount}))

            # Update who the aggressor is if a bet or raise occurred
            if action.type == "bet" or action.type == "raise":
                aggressor = player.player_id
                # Reset num_actions_this_round here? No, a raise re-opens betting, everyone needs a chance to act again *after* the raise.
                # The loop condition needs to ensure players who have already acted get another turn if there was a raise.
                # This is why `acting_order` is static for the round, and we loop through it.
                # The condition for ending the loop is when action returns to the aggressor and their bet is matched or all others folded.

                # If a raise occurs, all players who have already acted (before the current raiser in order)
                # must get a chance to act again. The `current_player_index` continues, and will wrap around.
                # The loop terminates when the current_player_index reaches the aggressor again, AND their bet hasn't been re-raised.

                # Let's refine the end condition of the betting loop:
                # Betting ends when:
                # 1. All players have acted at least once in this round.
                # 2. The highest bet has been called by all active players, or they have folded.
                #    This means action has returned to the last aggressor, and no one re-raised them.
                #    Or, if there was no aggressor (everyone checked).

                # Reset acting_order to ensure everyone gets a chance to respond to the new aggressor
                # No, this is not how it works. Action continues in order.
                # The `aggressor` variable helps determine when the round can end.

            # Check end condition for betting round:
            # Option A: Loop until current_player_index is the aggressor AND current_bet_to_match is their bet.
            # Option B: Simpler: if num_actions >= len(acting_order_initial_eligible_players) AND all current_bets are equal (for those not folded/all-in)
            #           OR if someone raised, then the "len" check restarts from the raiser.

            # Let's use a flag: has_betting_concluded
            betting_concluded = True
            # Who is next to act, effectively? If current_player_index + 1 wraps around, it's player at index 0.
            # The player "whose turn it would be" if action continued.

            player_who_closed_action = aggressor # Player who made the last bet/raise. If None, it was checked around.

            # If no one has made an aggressive action yet (e.g. everyone checking post-flop)
            if player_who_closed_action is None and num_actions_this_round >= len(acting_order):
                 # Everyone has had a chance to act, and all have checked (or folded)
                 pass # betting_concluded remains true by default
            elif player_who_closed_action is None and num_actions_this_round < len(acting_order):
                betting_concluded = False # Not everyone has acted yet

            elif player_who_closed_action is not None:
                # There was a bet or raise. Betting ends when action gets back to this player
                # and they don't face a new raise.
                # We need to see if all other active players have either matched the aggressor's bet or folded.
                betting_concluded = True # Assume true, prove false
                for p_idx in range(len(acting_order)):
                    p_check = acting_order[p_idx]
                    if p_check.is_folded or p_check.is_all_in:
                        continue

                    # If this player is the aggressor, their bet is the one to match.
                    # If this player is NOT the aggressor, their bet must match current_bet_to_match
                    if p_check.player_id != player_who_closed_action:
                        if p_check.current_bet < self.game_state.current_bet_to_match:
                             betting_concluded = False # Someone still needs to call/raise/fold
                             break
                    # If it IS the aggressor, we need to ensure action has passed them once.
                    # This is tricky. The aggressor concept with index tracking is better.
                    # The loop should naturally end when `current_player_index` would point to the aggressor again,
                    # and no one re-raised.

            # Revised End Condition:
            # The betting round ends if:
            # (a) All players have had the chance to act (num_actions_this_round >= len(acting_order)).
            # (b) And all players still in the hand (not folded, not all-in) have put in the same amount of money for the round,
            #     UNLESS a player is all-in for less.
            # (c) Or only one player remains not folded. (Handled at start of loop)

            if num_actions_this_round >= len(acting_order): # Everyone had a chance to act
                all_bets_settled = True
                # Check if all non-folded, non-all-in players have bets equal to current_bet_to_match
                for p_check in acting_order:
                    if p_check.is_folded or p_check.is_all_in:
                        continue
                    if p_check.current_bet < self.game_state.current_bet_to_match:
                        all_bets_settled = False
                        break

                if all_bets_settled:
                    # Special case: BB pre-flop option. If no raise before BB, BB can raise.
                    # This means `aggressor` was BB initially. If action returns to BB and no raise,
                    # BB can check (if their BB covers current_bet_to_match) or raise.
                    # If player is BB, and it's pre-flop, and current_bet_to_match is still BB value,
                    # and they haven't acted yet on "the option"
                    is_bb = False # Determine if player is the Big Blind
                    # This needs proper BB tracking. For now, assume this is handled by `aggressor` logic.
                    # If `player` is the `aggressor` (e.g. BB pre-flop, or first bettor post-flop),
                    # and `all_bets_settled` is true (meaning everyone called them or folded), then round ends.
                    if player.player_id == aggressor or aggressor is None : # Or if it was checked around (aggressor is None)
                         betting_concluded = True
                    else: # Action is not yet back to the aggressor
                         betting_concluded = False
                else: # Not all bets settled
                    betting_concluded = False
            else: # Not everyone has acted yet
                betting_concluded = False

            if betting_concluded:
                break # Exit betting loop

            current_player_index += 1
            if current_player_index >= len(acting_order):
                current_player_index = 0 # Wrap around

        # After loop, collect bets into main pot
        self.game_state.pot_size += self.game_state.current_round_pot
        self.game_state.current_round_pot = 0
        for p in self.game_state.players: # Reset player's current_bet for next street, unless it's pre-flop where BB is special
            # Player.current_bet should be reset at start of FLOP, TURN, RIVER betting rounds.
            # For pre-flop, it's fine, it accumulates.
            pass # current_bet is their total for this street, used for current_bet_to_match logic.

        # Check again if only one player remains after betting round
        non_folded_players = [p for p in self._active_round_players if not p.is_folded]
        return len(non_folded_players) > 1


    def _process_player_action(self, player: Player, action: Action, allowed: Dict[str,Any]) -> bool:
        """Processes a player's action, updates game state. Returns True if action was valid and processed."""

        # Basic validation against allowed actions (interface should also do this for humans)
        if action.type not in allowed:
            if action.type == "bet" and "check" in allowed : # Tried to bet when only check was option (e.g. already a bet)
                action.type = "check" # Default to check if bet is not allowed but check is
            elif action.type == "raise" and "call" in allowed: # Tried to raise when only call was option
                action.type = "call"
                action.amount = allowed["call"]
            else: # Truly invalid
                self.interface.show_message(f"Action {action.type} not allowed for {player.player_id}. Allowed: {list(allowed.keys())}")
                # Fallback to fold if possible, otherwise it's a bug or Human forced invalid state.
                if "fold" in allowed: player.fold(); return True
                return False # Critical error or needs re-prompt

        amount_to_call_for_player = self.game_state.current_bet_to_match - player.current_bet

        if action.type == "fold":
            player.fold()
        elif action.type == "check":
            # Valid only if current_bet_to_match is 0 or player already matched it.
            if amount_to_call_for_player > 0:
                self.interface.show_message(f"Invalid Check by {player.player_id}. Must call {amount_to_call_for_player}.")
                player.fold() # Penalize with a fold. Or re-prompt.
                return True # Processed as fold
        elif action.type == "call":
            if amount_to_call_for_player <= 0: # Nothing to call
                 # This should ideally be a check. If player chose "call" when check was option.
                 pass # Treat as check effectively.
            else:
                call_amount = min(player.stack, amount_to_call_for_player)
                # action.amount from interface should be this call_amount.
                # If interface sent full amount_to_call, but player stack is less, it's an all-in call.
                actual_call_amount_from_stack = player.place_bet(call_amount)
                self.game_state.current_round_pot += actual_call_amount_from_stack
                # Player's total bet for this round is now player.current_bet.

        elif action.type == "bet":
            # Valid if amount_to_call_for_player <= 0 (i.e. it was a check to player)
            # action.amount is the bet amount itself.
            min_bet = allowed.get("bet",{}).get("min", self.game_state.big_blind)
            max_bet = allowed.get("bet",{}).get("max", player.stack)
            if not (min_bet <= action.amount <= max_bet):
                self.interface.show_message(f"Invalid bet amount {action.amount} by {player.player_id}. Range: ({min_bet}-{max_bet}). Stack: {player.stack}")
                # Force a valid bet (e.g. min_bet or all-in) or fold. For now, fold.
                player.fold(); return True

            actual_bet_amount_from_stack = player.place_bet(action.amount)
            self.game_state.current_round_pot += actual_bet_amount_from_stack
            self.game_state.current_bet_to_match = player.current_bet # This is the new total bet to match
            self.game_state.last_raiser = player.player_id
            self.game_state.last_raise_amount = action.amount # The bet amount itself is the "raise" over 0.
            self.game_state.min_bet = action.amount # Next raise must be at least this much more. (This is rule for raise increment)


        elif action.type == "raise":
            # action.amount is the TOTAL amount the player is making their bet to.
            # The "raise amount" itself (on top of previous bet) is action.amount - self.game_state.current_bet_to_match
            # Player's current_bet before this action is what they had in before this raise.
            # Amount they need to add: action.amount - player.current_bet

            min_total_raise = allowed.get("raise",{}).get("min_total_bet", self.game_state.current_bet_to_match + self.game_state.big_blind) # Fallback min
            max_total_raise = allowed.get("raise",{}).get("max_total_bet", player.stack + player.current_bet) # Fallback max (all-in raise)
                                                                                                               # Max total bet is player.stack

            if not (min_total_raise <= action.amount <= player.stack + player.current_bet ): # Max check is tricky
                                                                                        # action.amount IS the total bet. So it should be <= player.stack (if starting from 0)
                                                                                        # or <= player.stack + player.current_bet (if already bet some)
                                                                                        # Correct: action.amount (total bet) must be <= player.current_bet (already in pot) + player.stack (remaining)
                self.interface.show_message(f"Invalid raise amount {action.amount} by {player.player_id}. Total bet range: ({min_total_raise} - {player.stack + player.current_bet}).")
                player.fold(); return True

            amount_to_add_to_pot = action.amount - player.current_bet
            if amount_to_add_to_pot > player.stack: # Should be caught by total amount check
                amount_to_add_to_pot = player.stack # All-in raise

            actual_raise_amount_from_stack = player.place_bet(amount_to_add_to_pot)
            self.game_state.current_round_pot += actual_raise_amount_from_stack

            # The "size of the raise" (for next player to re-raise by at least that much)
            # is the amount raised ON TOP of the previous current_bet_to_match.
            size_of_this_raise = player.current_bet - self.game_state.current_bet_to_match

            self.game_state.current_bet_to_match = player.current_bet # New bet to match
            self.game_state.last_raiser = player.player_id
            self.game_state.last_raise_amount = size_of_this_raise
            self.game_state.min_bet = size_of_this_raise # Next raise must be at least this much more on top. (This is raise increment)


        if player.stack == 0 and not player.is_all_in: # Should be set by place_bet
             player.is_all_in = True # Ensure it's set

        return True


    def _determine_winners_and_distribute_pot(self):
        # Uses self.rules.determine_winners
        # winner_info is list of dicts: {'player_id': str, 'amount_won': int, 'hand_name': str, 'best_cards': List[Card]}

        # We need to provide hand details for all players who went to showdown for the interface
        showdown_hand_results = {}
        if self.game_state.game_phase == "showdown":
            for p in self._active_round_players:
                if not p.is_folded and p.hole_cards:
                    # Ensure community_cards is not None
                    community = self.game_state.community_cards if self.game_state.community_cards is not None else []
                    hand_name, best_cards, rank_val, kickers = self.hand_evaluator.evaluate_hand(p.hole_cards, community)
                    showdown_hand_results[p.player_id] = {
                        "hand_name": hand_name, "best_cards": best_cards,
                        "rank_val": rank_val, "kickers": kickers
                    }

        winners_data = self.rules.determine_winners(self.game_state)

        if not winners_data:
            self.interface.show_message("No winners (e.g. error or all folded before showdown). Pot remains or is returned?")
            # This case should be rare if logic is correct. Pot should go to last non-folder.
            # determine_winners handles the "one non-folder" case.
            return

        for winner_info in winners_data:
            winner_player = self.game_state.get_player_by_id(winner_info["player_id"])
            if winner_player:
                winner_player.stack += winner_info["amount_won"]
                self.event_system.post(GameEvent(type="pot_distributed",
                                                 data={"player_id": winner_player.player_id,
                                                       "amount": winner_info["amount_won"],
                                                       "hand": winner_info.get("hand_name")}))

        self.interface.display_winner(winners_data, self.game_state, showdown_hand_results)

        # Reset pot after distribution
        self.game_state.pot_size = 0
        self.game_state.current_round_pot = 0 # Should be 0 already if collected previously

    def play_round(self):
        """Plays a single round of poker (pre-flop, flop, turn, river, showdown)."""
        self._setup_new_round()

        if self.game_state.is_game_over: return # Setup might realize game is over

        self._post_blinds()
        if self.is_game_over(): return # Posting blinds might end game for some

        self._deal_hole_cards()
        if self.is_game_over(): return

        # Betting phases
        round_continues = True
        for phase in ["pre-flop", "flop", "turn", "river"]:
            self.game_state.game_phase = phase
            self.event_system.post(GameEvent(type="phase_start", data={"phase": phase}))

            # Reset player current_bet for Flop, Turn, River (not Pre-flop as blinds are bets)
            if phase != "pre-flop":
                for p in self._active_round_players:
                    p.current_bet = 0
                self.game_state.current_bet_to_match = 0
                self.game_state.last_raiser = None
                self.game_state.last_raise_amount = 0
                self.game_state.min_bet = self.game_state.big_blind # Reset min opening bet size for the street


            # Deal community cards if it's flop, turn, or river
            if phase in ["flop", "turn", "river"]:
                # Check if enough players are still in to continue to this phase's betting.
                # (e.g. if pre-flop betting resulted in only one player, skip flop/turn/river dealing & betting)
                active_for_betting = [p for p in self._active_round_players if not p.is_folded]
                if len(active_for_betting) <=1 :
                    round_continues = False # No betting possible, proceed to showdown/award
                    break
                self._deal_community_cards(phase)
                if self.is_game_over(): return # Deck error

            # Run betting round
            # Ensure _active_round_players for betting round only includes those not folded and not all-in (unless they are the only one left)
            # The _run_betting_round method uses rules.get_betting_order which filters these.

            # Before betting, if only one player is not folded, round ends.
            non_folded_players = [p for p in self._active_round_players if not p.is_folded]
            if len(non_folded_players) <= 1:
                round_continues = False
                break # End phase loop, proceed to showdown/award

            # If all remaining players are all-in, no more betting. Deal all remaining cards.
            players_who_can_act = [p for p in non_folded_players if not p.is_all_in]
            if not players_who_can_act and len(non_folded_players) > 1: # All remaining are all-in
                # If phase is pre-flop, deal flop, turn, river
                # If phase is flop, deal turn, river
                # If phase is turn, deal river
                self.interface.show_message("All remaining players are all-in. Dealing remaining cards.")
                if phase == "pre-flop":
                    self._deal_community_cards("flop")
                    if self.is_game_over(): return
                    self._deal_community_cards("turn")
                    if self.is_game_over(): return
                    self._deal_community_cards("river")
                    if self.is_game_over(): return
                elif phase == "flop":
                    self._deal_community_cards("turn")
                    if self.is_game_over(): return
                    self._deal_community_cards("river")
                    if self.is_game_over(): return
                elif phase == "turn":
                    self._deal_community_cards("river")
                    if self.is_game_over(): return

                round_continues = False # No more betting, proceed to showdown
                break # End phase loop


            round_continues = self._run_betting_round()
            self.interface.display_game_state(self.game_state) # Show state after betting round

            if not round_continues: # Only one player left after betting
                break # End phase loop, proceed to showdown/award

        # Showdown or award pot
        self.game_state.game_phase = "showdown" # Even if uncontested, it's the end phase
        self.event_system.post(GameEvent(type="phase_start", data={"phase": "showdown"}))
        self.interface.display_game_state(self.game_state, show_hole_cards_for_player=None) # Show final state before winner announcement
        self._determine_winners_and_distribute_pot()

        self.event_system.post(GameEvent(type="round_end", data={"round_number": self.game_state.round_number}))
        self.interface.display_game_state(self.game_state) # Final state for the round

        # Check for game over condition (e.g. one player has all chips)
        if self.is_game_over():
            # Announce overall game winner if applicable
            active_players = [p for p in self.game_state.players if p.stack > 0]
            if len(active_players) == 1:
                self.interface.show_message(f"Player {active_players[0].player_id} is the overall winner of the game!")
            # Further game end logic...
            pass
