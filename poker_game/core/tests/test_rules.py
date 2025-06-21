import unittest
from poker_game.core.rules import TexasHoldemRules
from poker_game.core.cards import Card, HandEvaluator, Deck
from poker_game.core.player import Player, HumanPlayer
from poker_game.core.game_state import GameState
from poker_game.config import settings # For SB/BB values

class TestTexasHoldemRules(unittest.TestCase):
    def setUp(self):
        self.hand_evaluator = HandEvaluator()
        self.rules = TexasHoldemRules(self.hand_evaluator)

        # Sample players for different scenarios
        self.p1 = HumanPlayer(player_id="P1", stack=1000)
        self.p2 = HumanPlayer(player_id="P2", stack=1000)
        self.p3 = HumanPlayer(player_id="P3", stack=1000)
        self.p4 = HumanPlayer(player_id="P4", stack=1000)

        # Reset player states before each test method that uses them
        self.players_list = [self.p1, self.p2, self.p3, self.p4]
        for p in self.players_list:
            p.reset_for_new_round()
            p.stack = 1000 # Ensure consistent starting stack for tests using these players

        self.game_state = GameState(
            players=self.players_list,
            small_blind=settings.SMALL_BLIND,
            big_blind=settings.BIG_BLIND,
            min_bet=settings.BIG_BLIND
        )


    def test_deal_counts(self):
        self.assertEqual(self.rules.get_initial_deal_count(), 2)
        self.assertEqual(self.rules.get_flop_deal_count(), 3)
        self.assertEqual(self.rules.get_turn_deal_count(), 1)
        self.assertEqual(self.rules.get_river_deal_count(), 1)

    def test_determine_winners_one_winner_high_card(self):
        # P1: A K, P2: Q J. Community: 2 3 4 5 7 (no pairs, flushes, straights)
        self.p1.hole_cards = [Card('A', '♠'), Card('K', '♥')]
        self.p2.hole_cards = [Card('Q', '♦'), Card('J', '♣')]
        self.p3.is_folded = True # P3 folds
        self.p4.is_folded = True # P4 folds

        self.game_state.community_cards = [Card('2', '♣'), Card('3', '♦'), Card('4', '♥'), Card('5', '♠'), Card('7', '♣')]
        self.game_state.pot_size = 100 # Main pot
        self.game_state.current_round_pot = 50 # Bets from current round

        # Update game_state.players to only include those relevant or reset their state
        self.game_state.players = [self.p1, self.p2, self.p3, self.p4]


        winners_data = self.rules.determine_winners(self.game_state)

        self.assertEqual(len(winners_data), 1)
        winner = winners_data[0]
        self.assertEqual(winner["player_id"], "P1")
        self.assertEqual(winner["amount_won"], 150) # 100 + 50
        self.assertEqual(winner["hand_name"], "STRAIGHT") # P1 has A-2-3-4-5 (Wheel)
        # Expected best 5 cards for P1: A♠, 5♠, 4♥, 3♦, 2♣ (Ace from hole, rest from community)
        # The specific suit for community cards 2,3,4,5 were 2♣, 3♦, 4♥, 5♠
        self.assertCountEqual([str(c) for c in winner["best_cards"]], ['A♠', '5♠', '4♥', '3♦', '2♣'])


    def test_determine_winners_uncontested_pot(self):
        self.p1.is_folded = False
        self.p2.is_folded = True
        self.p3.is_folded = True
        self.p4.is_folded = True
        self.game_state.players = [self.p1, self.p2, self.p3, self.p4]
        self.game_state.pot_size = 100
        self.game_state.current_round_pot = 20

        winners_data = self.rules.determine_winners(self.game_state)
        self.assertEqual(len(winners_data), 1)
        winner = winners_data[0]
        self.assertEqual(winner["player_id"], "P1")
        self.assertEqual(winner["amount_won"], 120)
        self.assertEqual(winner["hand_name"], " uncontested_pot") # Specific string used
        self.assertEqual(winner["best_cards"], [])

    def test_determine_winners_tie_split_pot(self):
        # P1: A K, P2: A K (different suits for hole cards, same board)
        # Community: A Q J 2 3 (Both play A A K Q J)
        self.p1.hole_cards = [Card('A', '♠'), Card('K', '♥')]
        self.p2.hole_cards = [Card('A', '♣'), Card('K', '♦')]
        self.p3.is_folded = True
        self.p4.is_folded = True
        self.game_state.players = [self.p1, self.p2, self.p3, self.p4]

        self.game_state.community_cards = [Card('A', '♦'), Card('Q', '♠'), Card('J', '♥'), Card('2', '♣'), Card('3', '♦')]
        self.game_state.pot_size = 200
        self.game_state.current_round_pot = 0

        winners_data = self.rules.determine_winners(self.game_state)
        self.assertEqual(len(winners_data), 2)

        total_pot = 200
        amount_per_winner = total_pot // 2

        p1_won = any(w["player_id"] == "P1" and w["amount_won"] == amount_per_winner for w in winners_data)
        p2_won = any(w["player_id"] == "P2" and w["amount_won"] == amount_per_winner for w in winners_data)
        self.assertTrue(p1_won)
        self.assertTrue(p2_won)

        for winner in winners_data:
            self.assertEqual(winner["hand_name"], "ONE_PAIR") # Pair of Aces
            # Expected best 5: A, A, K, Q, J
            self.assertCountEqual([c.rank for c in winner["best_cards"]], ['A', 'A', 'K', 'Q', 'J'])

    def test_determine_winners_tie_split_pot_odd_chips(self):
        # P1 & P2 tie, pot is 201. One should get 101, other 100.
        self.p1.hole_cards = [Card('A', '♠'), Card('K', '♥')]
        self.p2.hole_cards = [Card('A', '♣'), Card('K', '♦')]
        self.p3.is_folded = True; self.p4.is_folded = True
        self.game_state.players = [self.p1, self.p2, self.p3, self.p4]
        self.game_state.community_cards = [Card('A', '♦'), Card('Q', '♠'), Card('J', '♥'), Card('2', '♣'), Card('3', '♦')]
        self.game_state.pot_size = 201 # Odd pot

        winners_data = self.rules.determine_winners(self.game_state)
        self.assertEqual(len(winners_data), 2)

        amounts_won = sorted([w["amount_won"] for w in winners_data])
        self.assertEqual(amounts_won, [100, 101]) # One gets 100, other 101

    def test_get_betting_order_pre_flop_3_players(self):
        # 3 players: P1, P2, P3. Dealer P1 (pos 0).
        # SB is P2 (pos 1), BB is P3 (pos 2). Action starts UTG (P1 - dealer in 3-handed).
        # Standard: SB, BB, UTG (dealer). Action UTG.
        # My rule: (dealer_pos + 3) % num_players if num_players > 2
        # (0 + 3) % 3 = 0. So P1 (dealer) acts first. This is correct for 3-handed.
        # Order: P1 (UTG/Dealer), P2 (SB), P3 (BB)
        players = [self.p1, self.p2, self.p3]
        self.game_state.players = players
        dealer_pos = 0 # P1 is dealer

        order = self.rules.get_betting_order(players, dealer_pos, "pre-flop")
        ordered_ids = [p.player_id for p in order]
        self.assertEqual(ordered_ids, ["P1", "P2", "P3"])

    def test_get_betting_order_pre_flop_4_players(self):
        # 4 players: P1, P2, P3, P4. Dealer P1 (pos 0).
        # SB P2, BB P3. UTG is P4. Action starts P4.
        # My rule: (dealer_pos + 3) % num_players = (0 + 3) % 4 = 3. So P4 acts first. Correct.
        # Order: P4 (UTG), P1 (Dealer), P2 (SB), P3 (BB)
        players = [self.p1, self.p2, self.p3, self.p4]
        self.game_state.players = players
        dealer_pos = 0 # P1 is dealer

        order = self.rules.get_betting_order(players, dealer_pos, "pre-flop")
        ordered_ids = [p.player_id for p in order]
        self.assertEqual(ordered_ids, ["P4", "P1", "P2", "P3"])

    def test_get_betting_order_post_flop_4_players(self):
        # 4 players: P1, P2, P3, P4. Dealer P1 (pos 0).
        # Action starts left of dealer: P2 (SB).
        # Order: P2, P3, P4, P1
        players = [self.p1, self.p2, self.p3, self.p4]
        self.game_state.players = players
        dealer_pos = 0 # P1 is dealer

        order = self.rules.get_betting_order(players, dealer_pos, "flop") # or turn, river
        ordered_ids = [p.player_id for p in order]
        self.assertEqual(ordered_ids, ["P2", "P3", "P4", "P1"])

    def test_get_betting_order_heads_up_pre_flop(self):
        # 2 players: P1, P2. Dealer P1 (pos 0).
        # P1 is SB, P2 is BB. Pre-flop, SB (Dealer) acts first.
        # My rule: if num_players == 2, start_index = dealer_pos. So P1. Correct.
        # Order: P1 (SB/Dealer), P2 (BB)
        players = [self.p1, self.p2]
        self.game_state.players = players
        dealer_pos = 0 # P1 is dealer

        order = self.rules.get_betting_order(players, dealer_pos, "pre-flop")
        ordered_ids = [p.player_id for p in order]
        self.assertEqual(ordered_ids, ["P1", "P2"])

    def test_get_betting_order_heads_up_post_flop(self):
        # 2 players: P1, P2. Dealer P1 (pos 0).
        # Post-flop, player NOT on button acts first (BB). So P2.
        # My rule: start_index = (dealer_pos + 1) % num_players = (0+1)%2 = 1. So P2. Correct.
        # Order: P2 (BB), P1 (SB/Dealer)
        players = [self.p1, self.p2]
        self.game_state.players = players
        dealer_pos = 0 # P1 is dealer

        order = self.rules.get_betting_order(players, dealer_pos, "flop")
        ordered_ids = [p.player_id for p in order]
        self.assertEqual(ordered_ids, ["P2", "P1"])

    def test_get_betting_order_with_folded_players(self):
        # P1 (Dealer), P2 (SB), P3 (BB - folded), P4 (UTG)
        # Pre-flop order should be: P4, P1, P2. (P3 is skipped)
        self.p3.is_folded = True
        players = [self.p1, self.p2, self.p3, self.p4] # P1=D, P2=SB, P3=BB(folded), P4=UTG
        self.game_state.players = players
        dealer_pos = 0 # P1

        order = self.rules.get_betting_order(players, dealer_pos, "pre-flop")
        ordered_ids = [p.player_id for p in order]
        self.assertEqual(ordered_ids, ["P4", "P1", "P2"])

    def test_get_betting_order_with_all_in_players(self):
        # P1 (Dealer), P2 (SB - all_in), P3 (BB), P4 (UTG)
        # All-in players don't act.
        # Pre-flop order: P4, P1, P3. (P2 is skipped for action)
        self.p2.is_all_in = True
        players = [self.p1, self.p2, self.p3, self.p4]
        self.game_state.players = players
        dealer_pos = 0

        order = self.rules.get_betting_order(players, dealer_pos, "pre-flop")
        ordered_ids = [p.player_id for p in order]
        self.assertEqual(ordered_ids, ["P4", "P1", "P3"])


    def test_get_allowed_actions_initial_bet_post_flop(self):
        # P1 to act, post-flop, no prior bets this street.
        # P1 stack 1000. BB is 20.
        self.game_state.current_bet_to_match = 0
        self.game_state.last_raiser = None
        self.game_state.last_raise_amount = 0
        self.game_state.big_blind = 20
        self.game_state.min_bet = 20 # Should be BB
        self.p1.current_bet = 0 # No bet yet this street

        actions = self.rules.get_allowed_actions(self.p1, self.game_state)

        self.assertTrue(actions["fold"])
        self.assertTrue(actions["check"])
        self.assertIn("bet", actions)
        self.assertEqual(actions["bet"]["min"], 20) # Min bet is BB
        self.assertEqual(actions["bet"]["max"], self.p1.stack) # Max bet is stack
        self.assertNotIn("call", actions)
        self.assertNotIn("raise", actions)

    def test_get_allowed_actions_facing_a_bet(self):
        # P1 to act, P2 bet 100. P1 stack 1000. BB 20.
        self.game_state.current_bet_to_match = 100
        self.game_state.last_raiser = "P2" # P2 made the bet
        self.game_state.last_raise_amount = 100 # P2's bet was 100 (first bet this street)
        self.game_state.big_blind = 20
        self.p1.current_bet = 0 # P1 has 0 in pot for this street

        actions = self.rules.get_allowed_actions(self.p1, self.game_state)

        self.assertTrue(actions["fold"])
        self.assertNotIn("check", actions)
        self.assertIn("call", actions)
        self.assertEqual(actions["call"], 100) # Amount to call

        self.assertIn("raise", actions)
        # Min raise: current_bet_to_match (100) + last_raise_amount (100) = 200 total bet
        self.assertEqual(actions["raise"]["min_total_bet"], 200)
        self.assertEqual(actions["raise"]["max_total_bet"], self.p1.stack) # Max is all-in (1000 total)
        self.assertNotIn("bet", actions)

    def test_get_allowed_actions_facing_bet_can_only_call_all_in(self):
        # P1 to act, P2 bet 100. P1 stack 50.
        self.p1.stack = 50
        self.game_state.current_bet_to_match = 100
        self.game_state.last_raiser = "P2"
        self.game_state.last_raise_amount = 100
        self.p1.current_bet = 0

        actions = self.rules.get_allowed_actions(self.p1, self.game_state)
        self.assertTrue(actions["fold"])
        self.assertIn("call", actions)
        self.assertEqual(actions["call"], 50) # Call all-in for 50
        self.assertNotIn("raise", actions) # Cannot raise, only call all-in

    def test_get_allowed_actions_facing_raise_can_all_in_raise_not_full(self):
        # P2 bet 100. P3 raised to 200 (raise of 100). P1 to act. P1 stack 250.
        # P1 already called 100. So P1.current_bet = 100. P1.stack = 150 remaining.
        # Current bet to match is 200. P1 needs to put in 100 more to call.
        # Last raise amount was 100. Min re-raise total would be 200 (current) + 100 (last raise) = 300.
        # P1 has 100 (in pot) + 150 (stack) = 250 total. Can't make full raise to 300.
        # Can raise all-in to 250 total.
        self.p1.stack = 150
        self.p1.current_bet = 100 # Called the initial 100 bet
        self.game_state.current_bet_to_match = 200 # P3 raised to 200
        self.game_state.last_raiser = "P3"
        self.game_state.last_raise_amount = 100 # P3's raise size was 100 on top of 100
        self.game_state.big_blind = 20

        actions = self.rules.get_allowed_actions(self.p1, self.game_state)
        self.assertTrue(actions["fold"])
        self.assertEqual(actions["call"], 100) # Call the remaining 100 (total 200)

        self.assertIn("raise", actions)
        # Min total bet for a "full" raise would be 300. P1 only has 250 total.
        # So min_total_bet for raise becomes their all-in amount if it's a valid raise.
        # P1's all-in is 150 more, making their total bet 250. This is a raise.
        self.assertEqual(actions["raise"]["min_total_bet"], 150 + 100) # All-in raise to 250 total
        self.assertEqual(actions["raise"]["max_total_bet"], 150 + 100) # All-in raise to 250 total

    def test_get_allowed_actions_player_all_in(self):
        self.p1.is_all_in = True
        self.p1.stack = 0
        actions = self.rules.get_allowed_actions(self.p1, self.game_state)
        self.assertEqual(actions, {"check": True}) # All-in player can only "check" / pass turn.

if __name__ == '__main__':
    unittest.main()
