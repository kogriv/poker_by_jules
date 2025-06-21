from poker_game.core.player import Player
from poker_game.core.events import Action
from abc import abstractmethod
import random
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from poker_game.core.game_state import GameState
    from poker_game.core.cards import Card


class BotPlayer(Player):
    @abstractmethod
    def make_decision(self, game_state: 'GameState') -> Action:
        pass

    def evaluate_hand_strength(self, hole_cards: List['Card'], community_cards: List['Card']) -> float:
        # Placeholder logic: 0.0 - 1.0, общая логика оценки
        # This will be a complex function, potentially using HandEvaluator
        # For now, a random placeholder
        if not hole_cards: # No cards, no strength
            return 0.0
        # A very naive placeholder
        # In a real scenario, this would involve poker hand evaluation (pair, two pair, etc.)
        # and comparing its strength relative to possible hands.
        # For now, let's simulate some basic strength based on card ranks.
        # (Ace=14, King=13, ..., 2=2)
        score = 0
        all_cards = hole_cards + community_cards
        if not all_cards:
            return 0.0

        # Simplified: just sum ranks / (14 * 7) as a rough proxy
        # This is NOT a good hand strength evaluation.
        for card in hole_cards: # Prioritize hole cards
            score += card.rank_value() * 2 # Give more weight to hole cards
        for card in community_cards:
            score += card.rank_value()

        max_possible_score = (14 * 2 * 2) + (14 * 5) # 2 hole cards (weighted) + 5 community cards
        if max_possible_score == 0: return 0.0

        strength = score / max_possible_score
        return min(max(strength, 0.0), 1.0)


    def calculate_pot_odds(self, game_state: 'GameState') -> float:
        # математика пот-оддсов
        # Pot odds = (Amount to Call) / (Current Pot Size + Amount to Call)
        if game_state.current_bet_to_match == 0: # No bet to call
            return 1.0 # Effectively infinite odds, can check for free

        amount_to_call = game_state.current_bet_to_match - self.current_bet
        if amount_to_call <= 0: # Already matched or raised higher
             return 1.0 # Can check or no cost to stay in

        if self.stack < amount_to_call: # Not enough stack to call
            amount_to_call = self.stack # What it costs to go all-in

        pot_size_before_call = game_state.pot_size + game_state.current_round_pot # Total pot if we call

        if (pot_size_before_call + amount_to_call) == 0:
            return 0.0 # Avoid division by zero, though unlikely

        pot_odds_ratio = amount_to_call / (pot_size_before_call + amount_to_call)
        return pot_odds_ratio


class RandomBot(BotPlayer):
    def make_decision(self, game_state: 'GameState') -> Action:
        possible_actions = ["fold", "check", "call", "bet", "raise"]

        amount_to_call = game_state.current_bet_to_match - self.current_bet

        if amount_to_call > 0 and "call" not in possible_actions: # Should not happen with current list
             possible_actions.append("call")
        if amount_to_call == 0 and "check" not in possible_actions: # Should not happen
            possible_actions.append("check")

        # Filter out invalid actions
        valid_actions = []
        if self.stack == 0: # All-in
            return Action(type="check", player_id=self.player_id) # Effectively a check

        if amount_to_call == 0 :
            valid_actions.append(Action(type="check", player_id=self.player_id))
            # Can always bet if stack > 0 and it's a check situation
            if self.stack > game_state.big_blind: # Min bet is big blind
                 valid_actions.append(Action(type="bet", amount=min(self.stack, game_state.big_blind), player_id=self.player_id))
        else: # There is a bet to match
            if self.stack > amount_to_call: # Can call or raise
                valid_actions.append(Action(type="call", amount=amount_to_call, player_id=self.player_id))
                # Can raise if stack > amount_to_call + min_raise
                # min_raise is typically last bet/raise amount, or big blind if first bet round.
                # For simplicity, let's assume min_raise = big_blind for now
                if self.stack > amount_to_call + game_state.big_blind:
                    valid_actions.append(Action(type="raise", amount=amount_to_call + game_state.big_blind, player_id=self.player_id))
                else: # Can only go all-in as a raise
                     valid_actions.append(Action(type="raise", amount=self.stack, player_id=self.player_id))

            elif self.stack == amount_to_call: # Can only call (all-in)
                 valid_actions.append(Action(type="call", amount=self.stack, player_id=self.player_id))
            # else: stack < amount_to_call, can only fold or go all-in (which is a call for less)

        # Always possible to fold (unless it's a check situation and no bets)
        if amount_to_call > 0 : # Only makes sense to fold if there's a bet
            valid_actions.append(Action(type="fold", player_id=self.player_id))

        if not valid_actions: # Should not happen, but as a fallback
            if amount_to_call == 0:
                return Action(type="check", player_id=self.player_id)
            elif self.stack <= amount_to_call : # Must go all-in or fold
                 return random.choice([Action(type="fold", player_id=self.player_id), Action(type="call", amount=self.stack, player_id=self.player_id)])
            else: # Fallback, should be covered
                return Action(type="fold", player_id=self.player_id)


        chosen_action_template = random.choice(valid_actions)
        final_action = Action(type=chosen_action_template.type, player_id=self.player_id)

        if chosen_action_template.type == "bet":
            # Bet between min_bet (big_blind) and stack
            bet_amount = random.randint(game_state.big_blind, self.stack)
            final_action.amount = bet_amount
        elif chosen_action_template.type == "raise":
            # Raise amount must be at least current_bet_to_match + min_raise (typically last bet/raise size or big_blind)
            # For random bot, let's simplify: raise by at least big_blind on top of the call amount
            min_raise_total = amount_to_call + game_state.big_blind
            if self.stack > min_raise_total :
                raise_amount = random.randint(min_raise_total, self.stack)
                final_action.amount = raise_amount - amount_to_call # The raise part
            else: # All-in raise
                final_action.amount = self.stack - amount_to_call
            final_action.amount = max(final_action.amount, game_state.min_bet) # ensure it's at least min_bet if it's the first bet. More complex logic needed here for actual raise sizing.
                                                                                # The action amount for raise is the ADDITIONAL amount on top of call.
                                                                                # Let's adjust: action.amount for raise should be the TOTAL bet amount.
            if self.stack > min_raise_total:
                total_bet_amount = random.randint(min_raise_total, self.stack)
                final_action.amount = total_bet_amount
            else: # All-in raise
                final_action.amount = self.stack


        elif chosen_action_template.type == "call":
            final_action.amount = min(self.stack, amount_to_call)

        return final_action


class TightBot(BotPlayer):
    def make_decision(self, game_state: 'GameState') -> Action:
        hand_strength = self.evaluate_hand_strength(self.hole_cards, game_state.community_cards)
        amount_to_call = game_state.current_bet_to_match - self.current_bet

        # Basic tight strategy
        if hand_strength < 0.4: # Weak hand
            if amount_to_call > 0: # If there's a bet to call
                return Action(type="fold", player_id=self.player_id)
            else: # Can check for free
                return Action(type="check", player_id=self.player_id)
        elif hand_strength < 0.7: # Medium hand
            if amount_to_call > 0:
                pot_odds = self.calculate_pot_odds(game_state)
                # Call if pot odds are favorable (simplified: hand strength > pot_odds_ratio)
                # This is a common simplification, though true pot odds involve equity vs odds.
                if hand_strength > pot_odds and self.stack >= amount_to_call:
                    return Action(type="call", amount=min(self.stack, amount_to_call), player_id=self.player_id)
                elif self.stack < amount_to_call: # All-in call if hand is decent and forced
                     return Action(type="call", amount=self.stack, player_id=self.player_id)
                else:
                    return Action(type="fold", player_id=self.player_id)
            else: # Can check or make a small bet
                if random.random() < 0.3: # Occasionally bet with medium hand
                     bet_amount = min(self.stack, game_state.big_blind * 2) # Small bet
                     if bet_amount > 0 :
                        return Action(type="bet", amount=bet_amount, player_id=self.player_id)
                return Action(type="check", player_id=self.player_id)
        else: # Strong hand (hand_strength >= 0.7)
            if amount_to_call > 0:
                # Raise if possible, otherwise call
                min_raise_total = amount_to_call + max(game_state.last_raise_amount, game_state.big_blind)
                if self.stack > min_raise_total:
                    # Raise proportionally to pot or a fixed amount
                    raise_val = min(self.stack, min_raise_total + game_state.big_blind * 2) # Example raise
                    return Action(type="raise", amount=raise_val, player_id=self.player_id)
                elif self.stack > amount_to_call : # Can call or all-in raise
                     return Action(type="call", amount=min(self.stack, amount_to_call), player_id=self.player_id) # Or raise all-in
                elif self.stack <= amount_to_call : # All-in call
                    return Action(type="call", amount=self.stack, player_id=self.player_id)

            else: # No bet to call, so bet/raise strongly
                bet_amount = min(self.stack, game_state.big_blind * 3) # Decent sized bet
                if bet_amount > 0:
                    return Action(type="bet", amount=bet_amount, player_id=self.player_id)
                else: # Cannot bet (e.g. stack is 0, though caught by all-in earlier)
                    return Action(type="check", player_id=self.player_id)

        # Fallback, should be covered by logic above
        if amount_to_call == 0:
            return Action(type="check", player_id=self.player_id)
        return Action(type="fold", player_id=self.player_id)


class AggressiveBot(BotPlayer):
    def make_decision(self, game_state: 'GameState') -> Action:
        hand_strength = self.evaluate_hand_strength(self.hole_cards, game_state.community_cards)
        amount_to_call = game_state.current_bet_to_match - self.current_bet

        # Aggressive strategy: frequent bets/raises, occasional bluffs
        is_bluffing = random.random() < 0.2 # 20% chance to bluff

        if is_bluffing and self.stack > game_state.big_blind:
            if amount_to_call == 0: # No current bet, so make a bet
                bet_amount = min(self.stack, random.randint(game_state.big_blind, game_state.big_blind * 3))
                return Action(type="bet", amount=bet_amount, player_id=self.player_id)
            else: # There is a bet, consider a bluff raise
                min_raise_total = amount_to_call + max(game_state.last_raise_amount, game_state.big_blind)
                if self.stack > min_raise_total:
                    raise_val = min(self.stack, min_raise_total + random.randint(game_state.big_blind, game_state.big_blind*2))
                    return Action(type="raise", amount=raise_val, player_id=self.player_id)
                # else, can't bluff raise effectively, fall through to normal logic

        if hand_strength < 0.3: # Weak hand (unless bluffing)
            if amount_to_call > 0:
                return Action(type="fold", player_id=self.player_id)
            else:
                return Action(type="check", player_id=self.player_id)

        elif hand_strength < 0.6: # Medium hand
            if amount_to_call > 0:
                # More likely to call or raise than a tight bot
                if random.random() < 0.6 and self.stack >= amount_to_call: # 60% call
                    return Action(type="call", amount=min(self.stack, amount_to_call), player_id=self.player_id)
                # Try to raise if stack allows
                min_raise_total = amount_to_call + max(game_state.last_raise_amount, game_state.big_blind)
                if self.stack > min_raise_total and random.random() < 0.3 : # 30% raise with medium
                     raise_val = min(self.stack, min_raise_total + game_state.big_blind)
                     return Action(type="raise", amount=raise_val, player_id=self.player_id)
                elif self.stack >= amount_to_call: # Fallback to call if raise failed or not chosen
                    return Action(type="call", amount=min(self.stack, amount_to_call), player_id=self.player_id)
                else: # Not enough to call full amount, must fold or all-in call
                    if self.stack > 0 : # Can go all-in
                         return Action(type="call", amount=self.stack, player_id=self.player_id)
                    return Action(type="fold", player_id=self.player_id) # Should not happen if stack is 0 (all-in)
            else: # Can check or bet
                if random.random() < 0.7: # 70% chance to bet with medium hand
                    bet_amount = min(self.stack, random.randint(game_state.big_blind, game_state.big_blind * 3))
                    if bet_amount > 0:
                        return Action(type="bet", amount=bet_amount, player_id=self.player_id)
                return Action(type="check", player_id=self.player_id)

        else: # Strong hand (hand_strength >= 0.6)
            # Almost always bet or raise
            if amount_to_call > 0:
                min_raise_total = amount_to_call + max(game_state.last_raise_amount, game_state.big_blind)
                if self.stack > min_raise_total:
                    raise_val = min(self.stack, min_raise_total + random.randint(game_state.big_blind*2, game_state.big_blind*4)) # Larger raise
                    return Action(type="raise", amount=raise_val, player_id=self.player_id)
                elif self.stack > amount_to_call: # Can't make standard raise, but can call or all-in raise
                    return Action(type="raise", amount=self.stack, player_id=self.player_id) # All-in raise
                else: # All-in call
                    return Action(type="call", amount=self.stack, player_id=self.player_id)

            else: # No bet to call, so bet strongly
                bet_amount = min(self.stack, random.randint(game_state.big_blind * 2, game_state.big_blind * 5))
                if bet_amount > 0:
                    return Action(type="bet", amount=bet_amount, player_id=self.player_id)
                return Action(type="check", player_id=self.player_id)

        # Fallback
        if amount_to_call == 0:
            return Action(type="check", player_id=self.player_id)
        return Action(type="fold", player_id=self.player_id)
