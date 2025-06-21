import unittest
from poker_game.core.cards import Card, Deck, HandEvaluator, SUITS, RANKS, RANK_VALUES

class TestCard(unittest.TestCase):
    def test_card_creation(self):
        card = Card('A', '♠')
        self.assertEqual(card.rank, 'A')
        self.assertEqual(card.suit, '♠')
        self.assertEqual(str(card), "A♠")

    def test_invalid_card_rank(self):
        with self.assertRaises(ValueError):
            Card('X', '♠')

    def test_invalid_card_suit(self):
        with self.assertRaises(ValueError):
            Card('A', 'Hearts') # Invalid suit symbol

    def test_card_equality(self):
        card1 = Card('K', '♦')
        card2 = Card('K', '♦')
        card3 = Card('Q', '♦')
        self.assertEqual(card1, card2)
        self.assertNotEqual(card1, card3)
        self.assertNotEqual(card1, "K♦") # Test against different type

    def test_card_sorting_and_rank_value(self):
        card_2c = Card('2', '♣')
        card_th = Card('T', '♥')
        card_as = Card('A', '♠')

        self.assertEqual(card_2c.rank_value(), RANK_VALUES['2'])
        self.assertEqual(card_th.rank_value(), RANK_VALUES['T'])
        self.assertEqual(card_as.rank_value(), RANK_VALUES['A'])

        self.assertTrue(card_2c < card_th)
        self.assertTrue(card_th < card_as)

        cards = [card_as, card_2c, card_th]
        expected_sorted = [card_2c, card_th, card_as]
        self.assertEqual(sorted(cards), expected_sorted)


class TestDeck(unittest.TestCase):
    def test_deck_creation(self):
        deck = Deck()
        self.assertEqual(len(deck.cards), 52)
        # Check for unique cards
        self.assertEqual(len(set(str(c) for c in deck.cards)), 52)

    def test_deck_shuffle(self):
        deck1 = Deck()
        # deck2 = Deck() # deck2 is shuffled by default on init - Not needed for this test logic

        # Convert to string representation for comparison
        # Get current order of deck1 (it's shuffled on init)
        deck1_cards_before_shuffle_again = [str(c) for c in deck1.cards]

        deck1.shuffle() # Shuffle it again
        deck1_cards_after_shuffle_again = [str(c) for c in deck1.cards]

        # Compare deck1's state before and after the explicit shuffle call.
        # It's statistically very improbable they are the same.
        self.assertNotEqual(deck1_cards_after_shuffle_again, deck1_cards_before_shuffle_again, "Shuffle should change card order")

        # Check that all original cards are still present after shuffle
        self.assertEqual(len(deck1.cards), 52)
        # Ensure all unique card representations are still there
        self.assertEqual(len(set(deck1_cards_after_shuffle_again)), 52)


    def test_deck_deal(self):
        deck = Deck()
        initial_len = len(deck.cards)

        # Deal one card
        card = deck.deal()[0]
        self.assertIsInstance(card, Card)
        self.assertEqual(len(deck.cards), initial_len - 1)

        # Deal multiple cards
        num_to_deal = 5
        hand = deck.deal(num_to_deal)
        self.assertEqual(len(hand), num_to_deal)
        self.assertEqual(len(deck.cards), initial_len - 1 - num_to_deal)
        for h_card in hand:
            self.assertIsInstance(h_card, Card)

    def test_deal_too_many_cards(self):
        deck = Deck()
        with self.assertRaises(ValueError):
            deck.deal(53)

        # Deal all cards then try one more
        deck.deal(52)
        self.assertEqual(len(deck.cards), 0)
        with self.assertRaises(ValueError):
            deck.deal(1)

    def test_len_deck(self):
        deck = Deck()
        self.assertEqual(len(deck), 52)
        deck.deal(10)
        self.assertEqual(len(deck), 42)

class TestHandEvaluator(unittest.TestCase):
    def setUp(self):
        self.evaluator = HandEvaluator()
        # Define various hands for testing _calculate_hand_details (5-card evaluation)
        # Cards are sorted by rank desc for direct input to _calculate_hand_details
        self.royal_flush_cards = sorted([Card('A', '♠'), Card('K', '♠'), Card('Q', '♠'), Card('J', '♠'), Card('T', '♠')], key=lambda c: c.rank_value(), reverse=True)
        self.straight_flush_king_cards = sorted([Card('K', '♥'), Card('Q', '♥'), Card('J', '♥'), Card('T', '♥'), Card('9', '♥')], key=lambda c: c.rank_value(), reverse=True)
        self.straight_flush_5_high_cards = sorted([Card('A', '♦'), Card('2', '♦'), Card('3', '♦'), Card('4', '♦'), Card('5', '♦')], key=lambda c: c.rank_value(), reverse=True) # Wheel flush

        self.four_aces_cards = sorted([Card('A', '♠'), Card('A', '♥'), Card('A', '♦'), Card('A', '♣'), Card('K', '♠')], key=lambda c: c.rank_value(), reverse=True)
        self.four_sevens_cards = sorted([Card('7', '♠'), Card('7', '♥'), Card('7', '♦'), Card('7', '♣'), Card('Q', '♠')], key=lambda c: c.rank_value(), reverse=True)

        self.full_house_A_K_cards = sorted([Card('A', '♠'), Card('A', '♥'), Card('A', '♦'), Card('K', '♣'), Card('K', '♠')], key=lambda c: c.rank_value(), reverse=True)
        self.full_house_K_A_cards = sorted([Card('K', '♠'), Card('K', '♥'), Card('K', '♦'), Card('A', '♣'), Card('A', '♠')], key=lambda c: c.rank_value(), reverse=True)

        self.flush_ace_high_cards = sorted([Card('A', '♠'), Card('K', '♠'), Card('Q', '♠'), Card('J', '♠'), Card('8', '♠')], key=lambda c: c.rank_value(), reverse=True)
        self.flush_king_high_cards = sorted([Card('K', '♥'), Card('Q', '♥'), Card('J', '♥'), Card('9', '♥'), Card('7', '♥')], key=lambda c: c.rank_value(), reverse=True)

        self.straight_ace_high_cards = sorted([Card('A', '♠'), Card('K', '♥'), Card('Q', '♦'), Card('J', '♣'), Card('T', '♠')], key=lambda c: c.rank_value(), reverse=True)
        self.straight_king_high_cards = sorted([Card('K', '♠'), Card('Q', '♥'), Card('J', '♦'), Card('T', '♣'), Card('9', '♠')], key=lambda c: c.rank_value(), reverse=True)
        self.straight_5_high_cards = sorted([Card('A', '♠'), Card('2', '♥'), Card('3', '♦'), Card('4', '♣'), Card('5', '♠')], key=lambda c: c.rank_value(), reverse=True) # Wheel

        self.three_aces_cards = sorted([Card('A', '♠'), Card('A', '♥'), Card('A', '♦'), Card('K', '♣'), Card('Q', '♠')], key=lambda c: c.rank_value(), reverse=True)

        self.two_pair_A_K_Q_cards = sorted([Card('A', '♠'), Card('A', '♥'), Card('K', '♦'), Card('K', '♣'), Card('Q', '♠')], key=lambda c: c.rank_value(), reverse=True)
        self.two_pair_A_K_J_cards = sorted([Card('A', '♠'), Card('A', '♥'), Card('K', '♦'), Card('K', '♣'), Card('J', '♠')], key=lambda c: c.rank_value(), reverse=True)

        self.one_pair_A_K_Q_J_cards = sorted([Card('A', '♠'), Card('A', '♥'), Card('K', '♦'), Card('Q', '♣'), Card('J', '♠')], key=lambda c: c.rank_value(), reverse=True)
        self.one_pair_K_A_Q_J_cards = sorted([Card('K', '♠'), Card('K', '♥'), Card('A', '♦'), Card('Q', '♣'), Card('J', '♠')], key=lambda c: c.rank_value(), reverse=True)

        self.high_card_A_K_Q_J_9_cards = sorted([Card('A', '♠'), Card('K', '♥'), Card('Q', '♦'), Card('J', '♣'), Card('9', '♠')], key=lambda c: c.rank_value(), reverse=True)
        self.high_card_A_K_Q_J_8_cards = sorted([Card('A', '♣'), Card('K', '♦'), Card('Q', '♥'), Card('J', '♠'), Card('8', '♦')], key=lambda c: c.rank_value(), reverse=True)

    def _test_hand_calc(self, cards: list[Card], expected_name: str, expected_rank_val: int, expected_kickers: list[int]):
        name, rank_val, kickers = self.evaluator._calculate_hand_details(cards)
        self.assertEqual(name, expected_name, f"Hand name mismatch for {cards}")
        self.assertEqual(rank_val, expected_rank_val, f"Hand rank value mismatch for {cards}")
        self.assertEqual(kickers, expected_kickers, f"Kickers mismatch for {cards}")
        # Return for use in comparison tests, make sure it's the full tuple expected by compare_hands
        return name, cards, rank_val, kickers # Adding cards to match tuple structure

    def test_calculate_royal_flush(self):
        self._test_hand_calc(self.royal_flush_cards, "ROYAL_FLUSH", HandEvaluator.HAND_RANKINGS["ROYAL_FLUSH"], [14, 13, 12, 11, 10])

    def test_calculate_straight_flush(self):
        self._test_hand_calc(self.straight_flush_king_cards, "STRAIGHT_FLUSH", HandEvaluator.HAND_RANKINGS["STRAIGHT_FLUSH"], [13, 12, 11, 10, 9])
        self._test_hand_calc(self.straight_flush_5_high_cards, "STRAIGHT_FLUSH", HandEvaluator.HAND_RANKINGS["STRAIGHT_FLUSH"], [5, 4, 3, 2, 1])

    def test_calculate_four_of_a_kind(self):
        self._test_hand_calc(self.four_aces_cards, "FOUR_OF_A_KIND", HandEvaluator.HAND_RANKINGS["FOUR_OF_A_KIND"], [14, 13])
        self._test_hand_calc(self.four_sevens_cards, "FOUR_OF_A_KIND", HandEvaluator.HAND_RANKINGS["FOUR_OF_A_KIND"], [7, 12])

    def test_calculate_full_house(self):
        self._test_hand_calc(self.full_house_A_K_cards, "FULL_HOUSE", HandEvaluator.HAND_RANKINGS["FULL_HOUSE"], [14, 13])
        self._test_hand_calc(self.full_house_K_A_cards, "FULL_HOUSE", HandEvaluator.HAND_RANKINGS["FULL_HOUSE"], [13, 14])

    def test_calculate_flush(self):
        self._test_hand_calc(self.flush_ace_high_cards, "FLUSH", HandEvaluator.HAND_RANKINGS["FLUSH"], [14, 13, 12, 11, 8])
        self._test_hand_calc(self.flush_king_high_cards, "FLUSH", HandEvaluator.HAND_RANKINGS["FLUSH"], [13, 12, 11, 9, 7])

    def test_calculate_straight(self):
        self._test_hand_calc(self.straight_ace_high_cards, "STRAIGHT", HandEvaluator.HAND_RANKINGS["STRAIGHT"], [14, 13, 12, 11, 10])
        self._test_hand_calc(self.straight_king_high_cards, "STRAIGHT", HandEvaluator.HAND_RANKINGS["STRAIGHT"], [13, 12, 11, 10, 9])
        self._test_hand_calc(self.straight_5_high_cards, "STRAIGHT", HandEvaluator.HAND_RANKINGS["STRAIGHT"], [5, 4, 3, 2, 1])

    def test_calculate_three_of_a_kind(self):
        self._test_hand_calc(self.three_aces_cards, "THREE_OF_A_KIND", HandEvaluator.HAND_RANKINGS["THREE_OF_A_KIND"], [14, 13, 12])

    def test_calculate_two_pair(self):
        self._test_hand_calc(self.two_pair_A_K_Q_cards, "TWO_PAIR", HandEvaluator.HAND_RANKINGS["TWO_PAIR"], [14, 13, 12])
        self._test_hand_calc(self.two_pair_A_K_J_cards, "TWO_PAIR", HandEvaluator.HAND_RANKINGS["TWO_PAIR"], [14, 13, 11])

    def test_calculate_one_pair(self):
        self._test_hand_calc(self.one_pair_A_K_Q_J_cards, "ONE_PAIR", HandEvaluator.HAND_RANKINGS["ONE_PAIR"], [14, 13, 12, 11])
        self._test_hand_calc(self.one_pair_K_A_Q_J_cards, "ONE_PAIR", HandEvaluator.HAND_RANKINGS["ONE_PAIR"], [13, 14, 12, 11])

    def test_calculate_high_card(self):
        self._test_hand_calc(self.high_card_A_K_Q_J_9_cards, "HIGH_CARD", HandEvaluator.HAND_RANKINGS["HIGH_CARD"], [14, 13, 12, 11, 9])
        self._test_hand_calc(self.high_card_A_K_Q_J_8_cards, "HIGH_CARD", HandEvaluator.HAND_RANKINGS["HIGH_CARD"], [14, 13, 12, 11, 8])

    def test_evaluate_hand_7_cards(self):
        hole_cards = [Card('A', '♠'), Card('K', '♠')]
        community_cards = [Card('Q', '♠'), Card('J', '♠'), Card('T', '♠'), Card('2', '♥'), Card('3', '♦')]
        name, best_5, rank_val, kickers = self.evaluator.evaluate_hand(hole_cards, community_cards)
        self.assertEqual(name, "ROYAL_FLUSH")
        self.assertEqual(rank_val, HandEvaluator.HAND_RANKINGS["ROYAL_FLUSH"])
        self.assertEqual(kickers, [14, 13, 12, 11, 10])
        self.assertEqual(len(best_5), 5)
        # Check if the cards in best_5 are equivalent to royal_flush_cards (ignoring original object identity)
        self.assertCountEqual([str(c) for c in best_5], [str(c) for c in self.royal_flush_cards])


        hole_cards_fh = [Card('A', '♠'), Card('A', '♥')]
        community_cards_fh = [Card('K', '♦'), Card('K', '♣'), Card('A', '♦'), Card('2','♠'), Card('3','♥')]
        name_fh, _, rank_fh, kickers_fh = self.evaluator.evaluate_hand(hole_cards_fh, community_cards_fh)
        self.assertEqual(name_fh, "FULL_HOUSE")
        self.assertEqual(rank_fh, HandEvaluator.HAND_RANKINGS["FULL_HOUSE"])
        self.assertEqual(kickers_fh, [14, 13])

    def test_evaluate_hand_less_than_5_cards_total(self):
        hole = [Card('A', '♠'), Card('K', '♥')]
        community = []
        name, best, rank, kickers = self.evaluator.evaluate_hand(hole, community)
        self.assertEqual(name, "HIGH_CARD")
        self.assertEqual(len(best), 2) # Contains the two hole cards
        self.assertEqual(sorted(kickers, reverse=True), sorted([14,13], reverse=True))

        hole_f = [Card('A', '♠'), Card('K', '♥')] # A, K
        community_f = [Card('Q', '♦'), Card('J', '♣'), Card('T', '♠')] # Q, J, T -> A,K,Q,J,T Straight
        name_f, best_f, rank_f, kickers_f = self.evaluator.evaluate_hand(hole_f, community_f)
        self.assertEqual(name_f, "STRAIGHT")
        self.assertEqual(kickers_f, [14,13,12,11,10])
        self.assertEqual(len(best_f), 5)


    def test_compare_hands(self):
        rf_details = self._test_hand_calc(self.royal_flush_cards, "ROYAL_FLUSH", HandEvaluator.HAND_RANKINGS["ROYAL_FLUSH"], [14,13,12,11,10])
        sfk_details = self._test_hand_calc(self.straight_flush_king_cards, "STRAIGHT_FLUSH", HandEvaluator.HAND_RANKINGS["STRAIGHT_FLUSH"], [13,12,11,10,9])
        self.assertEqual(self.evaluator.compare_hands(rf_details, sfk_details), 1)
        self.assertEqual(self.evaluator.compare_hands(sfk_details, rf_details), -1)

        fh_details = self._test_hand_calc(self.full_house_A_K_cards, "FULL_HOUSE", HandEvaluator.HAND_RANKINGS["FULL_HOUSE"], [14,13])
        fl_details = self._test_hand_calc(self.flush_ace_high_cards, "FLUSH", HandEvaluator.HAND_RANKINGS["FLUSH"], [14,13,12,11,8])
        self.assertEqual(self.evaluator.compare_hands(fh_details, fl_details), 1)

        hc1_details = self._test_hand_calc(self.high_card_A_K_Q_J_9_cards, "HIGH_CARD", HandEvaluator.HAND_RANKINGS["HIGH_CARD"], [14,13,12,11,9])
        hc2_cards_equiv = sorted([Card('A', '♣'), Card('K', '♦'), Card('Q', '♥'), Card('J', '♠'), Card('9', '♦')], key=lambda c: c.rank_value(), reverse=True)
        hc2_details = self._test_hand_calc(hc2_cards_equiv, "HIGH_CARD", HandEvaluator.HAND_RANKINGS["HIGH_CARD"], [14,13,12,11,9])
        self.assertEqual(self.evaluator.compare_hands(hc1_details, hc2_details), 0)

        hc_better_kicker_details = self._test_hand_calc(self.high_card_A_K_Q_J_9_cards, "HIGH_CARD", HandEvaluator.HAND_RANKINGS["HIGH_CARD"], [14,13,12,11,9])
        hc_worse_kicker_details = self._test_hand_calc(self.high_card_A_K_Q_J_8_cards, "HIGH_CARD", HandEvaluator.HAND_RANKINGS["HIGH_CARD"], [14,13,12,11,8])
        self.assertEqual(self.evaluator.compare_hands(hc_better_kicker_details, hc_worse_kicker_details), 1)

        tp_better_kicker = self._test_hand_calc(self.two_pair_A_K_Q_cards, "TWO_PAIR", HandEvaluator.HAND_RANKINGS["TWO_PAIR"], [14,13,12])
        tp_worse_kicker = self._test_hand_calc(self.two_pair_A_K_J_cards, "TWO_PAIR", HandEvaluator.HAND_RANKINGS["TWO_PAIR"], [14,13,11])
        self.assertEqual(self.evaluator.compare_hands(tp_better_kicker, tp_worse_kicker), 1)

if __name__ == '__main__':
    unittest.main()
