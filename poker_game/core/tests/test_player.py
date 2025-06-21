import unittest
from poker_game.core.player import Player, HumanPlayer
from poker_game.core.cards import Card
# GameState and Action might be needed if we test make_decision, but for now, focus on basic player mechanics.

class TestPlayer(unittest.TestCase):
    def setUp(self):
        self.player = HumanPlayer(player_id="test_human", stack=1000) # Using HumanPlayer as a concrete Player

    def test_player_creation(self):
        self.assertEqual(self.player.player_id, "test_human")
        self.assertEqual(self.player.stack, 1000)
        self.assertEqual(self.player.hole_cards, [])
        self.assertEqual(self.player.current_bet, 0)
        self.assertFalse(self.player.is_folded)
        self.assertFalse(self.player.is_all_in)

    def test_place_bet_normal(self):
        bet_amount = 100
        returned_bet = self.player.place_bet(bet_amount)

        self.assertEqual(returned_bet, bet_amount)
        self.assertEqual(self.player.stack, 1000 - bet_amount)
        self.assertEqual(self.player.current_bet, bet_amount)
        self.assertFalse(self.player.is_all_in)

    def test_place_bet_multiple_times_in_round(self):
        # Bets are cumulative for player.current_bet in a round
        self.player.place_bet(50) # Initial bet or call
        self.assertEqual(self.player.stack, 950)
        self.assertEqual(self.player.current_bet, 50)

        self.player.place_bet(100) # Subsequent bet (e.g. a raise, amount is additional)
        self.assertEqual(self.player.stack, 850)
        self.assertEqual(self.player.current_bet, 150) # 50 + 100
        self.assertFalse(self.player.is_all_in)

    def test_place_bet_all_in_exact(self):
        bet_amount = 1000
        returned_bet = self.player.place_bet(bet_amount)

        self.assertEqual(returned_bet, bet_amount)
        self.assertEqual(self.player.stack, 0)
        self.assertEqual(self.player.current_bet, bet_amount)
        self.assertTrue(self.player.is_all_in)

    def test_place_bet_all_in_overbet(self):
        bet_amount = 1200 # More than stack
        returned_bet = self.player.place_bet(bet_amount)

        self.assertEqual(returned_bet, 1000) # Actual bet is capped at stack
        self.assertEqual(self.player.stack, 0)
        self.assertEqual(self.player.current_bet, 1000)
        self.assertTrue(self.player.is_all_in)

    def test_place_bet_zero_amount(self):
        # Placing a zero bet shouldn't change stack or all_in status
        # (though game logic might prevent "bet 0", this tests Player method)
        returned_bet = self.player.place_bet(0)
        self.assertEqual(returned_bet, 0)
        self.assertEqual(self.player.stack, 1000)
        self.assertEqual(self.player.current_bet, 0) # current_bet accumulates
        self.assertFalse(self.player.is_all_in)


    def test_fold(self):
        self.player.hole_cards = [Card('A', '♠'), Card('K', '♥')]
        self.player.fold()

        self.assertTrue(self.player.is_folded)
        self.assertEqual(self.player.hole_cards, []) # Cards should be cleared on fold

    def test_reset_for_new_round(self):
        self.player.hole_cards = [Card('A', '♠'), Card('K', '♥')]
        self.player.place_bet(100)
        self.player.is_folded = True
        self.player.is_all_in = True # Should be reset if stack > 0, but for test consistency

        self.player.reset_for_new_round()

        self.assertEqual(self.player.hole_cards, [])
        self.assertEqual(self.player.current_bet, 0)
        self.assertFalse(self.player.is_folded)
        self.assertFalse(self.player.is_all_in) # is_all_in should be reset

    def test_reset_for_new_round_still_all_in_if_stack_zero(self):
        # This tests a subtle point: if reset is called but stack is still 0,
        # is_all_in might remain true or be re-evaluated.
        # Current Player.reset_for_new_round unconditionally sets is_all_in = False.
        # GameEngine should handle players with 0 stack (remove them or mark them out).
        # For the Player unit, it just resets its state.
        self.player.stack = 0
        self.player.is_all_in = True
        self.player.reset_for_new_round()
        self.assertFalse(self.player.is_all_in) # As per current implementation

    def test_human_player_make_decision_placeholder(self):
        # HumanPlayer.make_decision is expected to be called by an interface, not directly.
        # The base implementation raises NotImplementedError.
        with self.assertRaises(NotImplementedError):
            self.player.make_decision(None) # game_state is not used by this placeholder

if __name__ == '__main__':
    unittest.main()
