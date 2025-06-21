from poker_game.core.cards import Card, HandEvaluator
from poker_game.core.player import Player
from poker_game.core.game_state import GameState # For type hinting
from typing import List, Tuple, Dict, Optional, Any

class TexasHoldemRules:
    GAME_PHASES = ["pre-flop", "flop", "turn", "river", "showdown"]
    MIN_PLAYERS = 2
    MAX_PLAYERS = 10 # Typical for one table, problem states 2-6 for MVP

    def __init__(self, hand_evaluator: HandEvaluator):
        self.hand_evaluator = hand_evaluator

    def get_initial_deal_count(self) -> int:
        return 2 # 2 hole cards per player

    def get_flop_deal_count(self) -> int:
        return 3 # 3 cards for the flop

    def get_turn_deal_count(self) -> int:
        return 1 # 1 card for the turn

    def get_river_deal_count(self) -> int:
        return 1 # 1 card for the river

    def determine_winners(self, game_state: GameState) -> List[Dict[str, Any]]:
        """
        Determines the winner(s) of the hand from players who haven't folded.
        Handles main pot and side pots if necessary (though side pots are complex and for later).
        For MVP, assume one main pot.
        Returns a list of winner dicts: [{'player_id': str, 'amount_won': int, 'hand_name': str, 'best_cards': List[Card]}]
        """
        active_players = [p for p in game_state.players if not p.is_folded]

        if not active_players:
            return []
        if len(active_players) == 1: # Everyone else folded
            winner = active_players[0]
            # Pot includes main pot + current round's uncollected bets
            total_pot_to_win = game_state.pot_size + game_state.current_round_pot
            return [{"player_id": winner.player_id,
                     "amount_won": total_pot_to_win,
                     "hand_name": " uncontested_pot", # Or None
                     "best_cards": []}] # No showdown needed

        # Showdown: Evaluate hands for all remaining players
        player_hands_details = {} # player_id -> (hand_name, best_5_cards, rank_val, kickers)
        for player in active_players:
            if player.hole_cards: # Should always have hole cards if not folded
                # Ensure community_cards is not None, even if empty list
                community = game_state.community_cards if game_state.community_cards is not None else []
                hand_name, best_cards, rank_val, kickers = self.hand_evaluator.evaluate_hand(player.hole_cards, community)
                player_hands_details[player.player_id] = {
                    "player_obj": player,
                    "hand_name": hand_name,
                    "best_cards": best_cards,
                    "rank_val": rank_val,
                    "kickers": kickers,
                    "details_tuple": (hand_name, best_cards, rank_val, kickers) # For compare_hands
                }
            else: # Should not happen for active players at showdown
                # Give them the worst possible hand if it occurs
                 player_hands_details[player.player_id] = {
                    "player_obj": player, "hand_name": "NO_HAND", "best_cards": [], "rank_val": -1, "kickers": [],
                    "details_tuple": ("NO_HAND", [], -1, [])
                 }


        if not player_hands_details: return []

        # Sort players by hand strength (best hand first)
        # player_hands_details.items() gives list of (player_id, details_dict)
        sorted_players_by_hand = sorted(
            player_hands_details.values(),
            key=lambda x: (x["rank_val"], x["kickers"]), # Sort by rank, then by kickers directly
            reverse=True
        )

        # For MVP, assume one pot and winner takes all. Side pot logic is complex.
        # The best hand(s) win the pot.
        best_hand_details_tuple = sorted_players_by_hand[0]["details_tuple"]
        winners = []
        for p_details in sorted_players_by_hand:
            comparison = self.hand_evaluator.compare_hands(p_details["details_tuple"], best_hand_details_tuple)
            if comparison == 0: # This hand is tied with the best hand
                winners.append(p_details)
            else: # This hand is worse than the current best, no need to check further
                break

        total_pot_to_distribute = game_state.pot_size + game_state.current_round_pot
        amount_per_winner = total_pot_to_distribute // len(winners) if winners else 0
        # Remainder chips (if any) can go to the first winner in order (e.g., by seat position if needed for strictness)
        # For now, integer division is fine. Smallest chip unit handling can be added.

        winner_results = []
        for winner_detail in winners:
            winner_results.append({
                "player_id": winner_detail["player_obj"].player_id,
                "amount_won": amount_per_winner, # Simplified, no side pots
                "hand_name": winner_detail["hand_name"],
                "best_cards": winner_detail["best_cards"]
            })

        # Handle remainder if pot doesn't divide evenly
        remainder = total_pot_to_distribute % len(winners) if winners else 0
        if remainder > 0 and winner_results:
            # Distribute remainder chips, one per winner starting from the first one
            # This could be based on player order from the button for fairness in ties.
            # For now, just add to the first few winners in the list.
            for i in range(remainder):
                winner_results[i % len(winner_results)]["amount_won"] += 1

        return winner_results

    def get_betting_order(self, players: List[Player], dealer_pos: int, phase: str) -> List[Player]:
        """
        Determines the order of players for a betting round.
        Pre-flop: Starts with player after Big Blind.
        Post-flop (flop, turn, river): Starts with first active player to the left of the dealer.
        """
        num_players = len(players)
        if num_players == 0:
            return []

        active_players = [p for p in players if not p.is_folded and not p.is_all_in]
        if not active_players: # No one can act
            return []

        # Create a list of (original_index, player) for players who can still act
        eligible_to_act_with_indices = []
        for i, p in enumerate(players):
            if not p.is_folded and not p.is_all_in:
                eligible_to_act_with_indices.append((i, p))

        if not eligible_to_act_with_indices: return []


        if phase == "pre-flop":
            # In heads-up (2 players), dealer is SB, other is BB. Action starts with dealer (SB).
            # In 3+ players, SB, BB, then UTG (player after BB).
            if num_players == 2:
                # Dealer (SB) acts first pre-flop. BB acts last pre-flop.
                # Order: SB (dealer_pos), BB ((dealer_pos + 1) % num_players)
                # If players[dealer_pos] can act, they are first.
                # Then players[(dealer_pos + 1)%num_players] if they can act.
                # This needs to consider who is SB/BB based on dealer_pos.
                # Player at dealer_pos is SB. Player at (dealer_pos+1)%num_players is BB.
                # Action starts with SB.
                start_index = dealer_pos
            else: # 3+ players
                # Action starts with player left of Big Blind (UTG)
                # SB is (dealer_pos + 1) % num_players
                # BB is (dealer_pos + 2) % num_players
                start_index = (dealer_pos + 3) % num_players
        else: # Flop, Turn, River
            # Action starts with the first active player to the left of the dealer button.
            start_index = (dealer_pos + 1) % num_players

        ordered_players = []
        # Iterate through players starting from start_index, wrapping around,
        # only adding those who are in eligible_to_act_with_indices.

        # Find the first player in eligible_to_act_with_indices at or after start_index
        first_actor_index_in_eligible = -1

        # Search from start_index onwards (wrapping)
        for i in range(num_players):
            current_original_idx = (start_index + i) % num_players
            for k, (orig_idx, player) in enumerate(eligible_to_act_with_indices):
                if orig_idx == current_original_idx:
                    first_actor_index_in_eligible = k
                    break
            if first_actor_index_in_eligible != -1:
                break

        if first_actor_index_in_eligible == -1: # No one eligible, should be caught earlier
            return []

        # Now construct the ordered list from eligible_to_act_with_indices
        for i in range(len(eligible_to_act_with_indices)):
            idx_in_eligible = (first_actor_index_in_eligible + i) % len(eligible_to_act_with_indices)
            ordered_players.append(eligible_to_act_with_indices[idx_in_eligible][1])

        return ordered_players


    def get_allowed_actions(self, player: Player, game_state: GameState) -> Dict[str, Any]:
        """
        Determines the valid actions for a player given the current game state.
        Returns a dictionary like:
        {
            "fold": True,
            "check": True, # (if no bet to call)
            "call": amount_to_call, # (if there's a bet and player can cover)
            "bet": {"min": min_bet, "max": player.stack}, # (if no bet prior)
            "raise": {"min_raise_amount": X, "min_total_bet": Y, "max_total_bet": player.stack} # (if there's a bet)
        }
        The amounts for bet/raise need careful calculation based on game rules (e.g. min raise size).
        """
        allowed = {"fold": True} # Folding is always an option unless player is all-in with no prior action.
                                # But even then, it's more like a forced check.
                                # If player is all-in already, they have no actions.

        if player.is_all_in or player.stack == 0: # Player is all-in, no more actions
            return {"check": True} # Effectively a check / pass turn

        amount_to_call = game_state.current_bet_to_match - player.current_bet

        min_bet_or_raise = game_state.big_blind # Default minimum for an opening bet or a raise amount.
        if game_state.last_raise_amount > 0: # If there was a previous raise in this round
            min_bet_or_raise = max(min_bet_or_raise, game_state.last_raise_amount)


        if amount_to_call <= 0: # No bet to call, player can check or bet
            allowed["check"] = True
            # Bet action: min bet is big blind, max is player's stack
            # Ensure min_bet is at least big_blind
            actual_min_bet = max(game_state.big_blind, game_state.min_bet) # min_bet in GameState should track this
            if player.stack > 0:
                 allowed["bet"] = {"min": min(actual_min_bet, player.stack), "max": player.stack}
        else: # There is a bet to call
            # Call action:
            # If player has enough stack, call amount is amount_to_call.
            # If player has less stack, call amount is player.stack (all-in call).
            allowed["call"] = min(amount_to_call, player.stack)

            # Raise action:
            # Raise action:
            # Player must have more stack than amount_to_call to make a new raise.
            # If player.current_bet + player.stack <= game_state.current_bet_to_match, they cannot raise.
            # amount_to_call = game_state.current_bet_to_match - player.current_bet
            # So, player.stack > amount_to_call means they can at least call and have chips left.

            if player.stack > amount_to_call: # If player can do more than just call current amount
                min_raise_increment = max(game_state.big_blind, game_state.last_raise_amount if game_state.last_raise_amount > 0 else game_state.big_blind)

                # Minimum total amount for a "full" or "standard" raise
                standard_min_total_bet_for_raise = game_state.current_bet_to_match + min_raise_increment

                # Player's maximum possible total bet if they go all-in now (for this street)
                player_max_total_bet_this_street = player.current_bet + player.stack

                # Can the player make at least a "full" standard raise?
                if player_max_total_bet_this_street >= standard_min_total_bet_for_raise:
                    # Yes, they can make a full raise or more.
                    # The minimum they can raise to is standard_min_total_bet_for_raise.
                    # The maximum they can raise to is their all-in amount.
                    allowed["raise"] = {
                        "min_total_bet": standard_min_total_bet_for_raise,
                        "max_total_bet": player_max_total_bet_this_street
                    }
                elif player_max_total_bet_this_street > game_state.current_bet_to_match:
                    # Player cannot make a "full" raise, but their all-in amount is greater
                    # than current_bet_to_match. This is an all-in raise (potentially incomplete).
                    # In this case, their only raise option is to go all-in.
                    allowed["raise"] = {
                        "min_total_bet": player_max_total_bet_this_street, # Must go all-in to raise
                        "max_total_bet": player_max_total_bet_this_street
                    }
                # If player_max_total_bet_this_street <= game_state.current_bet_to_match,
                # they cannot raise at all (their all-in is just a call or less).
                # In this scenario, "raise" is not added to allowed actions.


        # If only action is fold or call (all-in for less than full call)
        if list(allowed.keys()) == ["fold", "call"] and player.stack <= amount_to_call and amount_to_call > 0:
            pass # This is a valid state: fold or call all-in.

        return allowed
