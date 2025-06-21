import random
from typing import List, Tuple, Dict
from collections import Counter

# Card Ranks and Suits
SUITS = ['♥', '♦', '♣', '♠'] # Hearts, Diamonds, Clubs, Spades
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K', 'A']
RANK_VALUES = {rank: i for i, rank in enumerate(RANKS, 2)} # T=10, J=11, Q=12, K=13, A=14

class Card:
    def __init__(self, rank: str, suit: str):
        if rank not in RANKS:
            raise ValueError(f"Invalid rank: {rank}")
        if suit not in SUITS:
            raise ValueError(f"Invalid suit: {suit}")
        self.rank = rank
        self.suit = suit

    def __repr__(self) -> str:
        return f"{self.rank}{self.suit}"

    def __eq__(self, other) -> bool:
        if not isinstance(other, Card):
            return NotImplemented
        return self.rank == other.rank and self.suit == other.suit

    def __lt__(self, other) -> bool: # For sorting cards
        if not isinstance(other, Card):
            return NotImplemented
        return self.rank_value() < other.rank_value()

    def rank_value(self) -> int:
        return RANK_VALUES[self.rank]

class Deck:
    def __init__(self):
        self.cards: List[Card] = self._create_deck()
        self.shuffle()

    def _create_deck(self) -> List[Card]:
        return [Card(rank, suit) for suit in SUITS for rank in RANKS]

    def shuffle(self) -> None:
        random.shuffle(self.cards)

    def deal(self, num_cards: int = 1) -> List[Card]:
        if num_cards > len(self.cards):
            raise ValueError("Not enough cards in deck to deal.")
        dealt_cards = [self.cards.pop() for _ in range(num_cards)]
        return dealt_cards

    def __len__(self) -> int:
        return len(self.cards)

class HandEvaluator:
    # Hand rankings, higher value is better hand
    HAND_RANKINGS = {
        "HIGH_CARD": 1,
        "ONE_PAIR": 2,
        "TWO_PAIR": 3,
        "THREE_OF_A_KIND": 4,
        "STRAIGHT": 5,
        "FLUSH": 6,
        "FULL_HOUSE": 7,
        "FOUR_OF_A_KIND": 8,
        "STRAIGHT_FLUSH": 9,
        "ROYAL_FLUSH": 10, # Technically a type of Straight Flush
    }

    def evaluate_hand(self, hole_cards: List[Card], community_cards: List[Card]) -> Tuple[str, List[Card], int, List[int]]:
        """
        Evaluates the best 5-card hand from the given hole cards and community cards.
        Returns:
            - Hand name (e.g., "FULL_HOUSE")
            - Best 5 cards forming the hand
            - Hand rank (integer from HAND_RANKINGS)
            - Tie-breaking kicker values (list of card rank values, ordered by significance)
        """
        all_cards = sorted(hole_cards + community_cards, key=lambda c: c.rank_value(), reverse=True)

        if len(all_cards) < 5: # Cannot form a 5-card hand yet (e.g. pre-flop, flop)
            # Return a value based on hole cards only for strength evaluation if needed,
            # but for actual hand ranking, we need 5 cards.
            # For now, let's assume this is called when at least 5 cards are available to form a hand.
            # Or, handle this by returning a very low rank.
             # For hand strength, this might be okay, but for final evaluation, it's an issue.
            if not all_cards:
                 return "NO_CARDS", [], 0, [] # Should not happen with hole cards

            # Simple high card for less than 5 cards for now
            best_five = all_cards[:5]
            kickers = [c.rank_value() for c in best_five]
            return "HIGH_CARD", best_five, self.HAND_RANKINGS["HIGH_CARD"], kickers


        best_hand_rank = 0
        best_hand_name = "HIGH_CARD" # Default
        best_five_cards = all_cards[:5] # Default to top 5 cards by rank
        best_kickers = [c.rank_value() for c in best_five_cards]

        # Iterate through all 5-card combinations (C(n,5))
        # For Texas Hold'em, n is 7 (2 hole + 5 community) or 6 (2 hole + 4 community on turn) or 5 (flop)
        from itertools import combinations

        num_cards_to_choose = 5
        if len(all_cards) < num_cards_to_choose: # Should not happen if we deal cards correctly
            # This case is more for partial hand evaluation during betting rounds.
            # The primary use of evaluate_hand is at showdown.
            # If this is called mid-round for strength, it needs different logic.
            # For now, assume it's for showdown or a situation where 5 cards are expected.
            # Let's just use all available cards if less than 5, though this isn't standard poker hand.
             best_five_cards = sorted(all_cards, key=lambda c: c.rank_value(), reverse=True)
             kickers = [c.rank_value() for c in best_five_cards]
             # This isn't a standard 5-card hand, so rank it as lowest.
             return "INCOMPLETE_HAND", best_five_cards, 0, kickers


        for combo in combinations(all_cards, num_cards_to_choose):
            current_cards = sorted(list(combo), key=lambda c: c.rank_value(), reverse=True)
            rank_name, rank_val, kickers = self._calculate_hand_details(current_cards)

            if rank_val > best_hand_rank:
                best_hand_rank = rank_val
                best_hand_name = rank_name
                best_five_cards = current_cards
                best_kickers = kickers
            elif rank_val == best_hand_rank:
                # Tie-breaking: compare kickers
                for i in range(len(kickers)):
                    if kickers[i] > best_kickers[i]:
                        best_hand_name = rank_name # Name might be same, but cards forming it are better
                        best_five_cards = current_cards
                        best_kickers = kickers
                        break
                    if kickers[i] < best_kickers[i]:
                        break

        return best_hand_name, best_five_cards, best_hand_rank, best_kickers

    def _calculate_hand_details(self, five_cards: List[Card]) -> Tuple[str, int, List[int]]:
        """
        Calculates the rank and kickers for a specific 5-card hand.
        Assumes five_cards is sorted by rank descending.
        """
        ranks = [card.rank_value() for card in five_cards]
        suits = [card.suit for card in five_cards]
        rank_counts = Counter(ranks)
        sorted_rank_counts = sorted(rank_counts.items(), key=lambda item: (item[1], item[0]), reverse=True)

        is_flush = len(set(suits)) == 1

        # Check for straight (Ace can be low or high)
        is_straight = False
        # Normal straight: 5, 4, 3, 2, A (ranks: 5,4,3,2,14 -> map A to 1 for this check)
        unique_ranks_for_straight = sorted(list(set(ranks)), reverse=True)
        if len(unique_ranks_for_straight) >= 5: # Need at least 5 unique ranks for a straight from 5 cards
            # Check for A-5 straight (wheel)
            if set(unique_ranks_for_straight[:5]) == {14, 5, 4, 3, 2}: # A, 5, 4, 3, 2
                is_straight = True
                # For kicker purposes, the straight is represented by its highest card (5 in A-5)
                straight_high_card_rank = 5
                # Kicker list for A-5 straight is [5,4,3,2,1] (Ace as 1)
                straight_kickers = [5,4,3,2,1]


            else: # Check for other straights
                for i in range(len(unique_ranks_for_straight) - 4):
                    # Check if 5 consecutive ranks exist
                    # e.g., ranks are [10,9,8,7,6] -> 10-6 = 4
                    if unique_ranks_for_straight[i] - unique_ranks_for_straight[i+4] == 4:
                        is_straight = True
                        straight_high_card_rank = unique_ranks_for_straight[i]
                        straight_kickers = unique_ranks_for_straight[i:i+5]
                        break

        # Royal Flush / Straight Flush
        if is_straight and is_flush:
            if straight_high_card_rank == RANK_VALUES['A'] and unique_ranks_for_straight[0] == RANK_VALUES['A']: # Ace-high straight flush
                 # Ensure it's T,J,Q,K,A specifically for Royal Flush name
                if set(ranks) == {RANK_VALUES['A'], RANK_VALUES['K'], RANK_VALUES['Q'], RANK_VALUES['J'], RANK_VALUES['T']}:
                    return "ROYAL_FLUSH", self.HAND_RANKINGS["ROYAL_FLUSH"], straight_kickers # Kicker is just the straight itself
                # else it's a normal Ace-high straight flush if Ace is high but not T-A. (e.g. A,K,Q,J,9 is not a straight)
                # This should be caught by the straight_kickers from the straight logic.
                # If it's A,K,Q,J,T, straight_kickers will be [14,13,12,11,10]
                # This specific check for ROYAL_FLUSH name is fine.
                return "STRAIGHT_FLUSH", self.HAND_RANKINGS["STRAIGHT_FLUSH"], straight_kickers


            return "STRAIGHT_FLUSH", self.HAND_RANKINGS["STRAIGHT_FLUSH"], straight_kickers

        # Four of a Kind
        # sorted_rank_counts = [(rank, count), ...] sorted by count then rank
        if sorted_rank_counts[0][1] == 4:
            four_kind_rank = sorted_rank_counts[0][0]
            # Kicker is the rank of the four of a kind, then the remaining card
            kicker_card_rank = [r for r in ranks if r != four_kind_rank][0]
            return "FOUR_OF_A_KIND", self.HAND_RANKINGS["FOUR_OF_A_KIND"], [four_kind_rank, kicker_card_rank]

        # Full House (3 of a kind and a pair)
        if sorted_rank_counts[0][1] == 3 and sorted_rank_counts[1][1] == 2:
            three_kind_rank = sorted_rank_counts[0][0]
            pair_rank = sorted_rank_counts[1][0]
            return "FULL_HOUSE", self.HAND_RANKINGS["FULL_HOUSE"], [three_kind_rank, pair_rank]

        # Flush (but not straight flush)
        if is_flush:
            # Kickers are all 5 card ranks, sorted
            return "FLUSH", self.HAND_RANKINGS["FLUSH"], sorted(ranks, reverse=True)

        # Straight (but not straight flush)
        if is_straight:
            return "STRAIGHT", self.HAND_RANKINGS["STRAIGHT"], straight_kickers # Kickers are the ranks in the straight

        # Three of a Kind
        if sorted_rank_counts[0][1] == 3:
            three_kind_rank = sorted_rank_counts[0][0]
            # Kickers are the rank of the three of a kind, then the two highest other cards
            other_kickers = sorted([r for r in ranks if r != three_kind_rank], reverse=True)
            return "THREE_OF_A_KIND", self.HAND_RANKINGS["THREE_OF_A_KIND"], [three_kind_rank] + other_kickers[:2]

        # Two Pair
        if sorted_rank_counts[0][1] == 2 and sorted_rank_counts[1][1] == 2:
            high_pair_rank = sorted_rank_counts[0][0] # Highest pair because sorted_rank_counts sorts by rank if counts are equal
            low_pair_rank = sorted_rank_counts[1][0]
            # Kicker is the rank of the high pair, then low pair, then the remaining card
            kicker_card_rank = [r for r in ranks if r != high_pair_rank and r != low_pair_rank][0]
            return "TWO_PAIR", self.HAND_RANKINGS["TWO_PAIR"], [high_pair_rank, low_pair_rank, kicker_card_rank]

        # One Pair
        if sorted_rank_counts[0][1] == 2:
            pair_rank = sorted_rank_counts[0][0]
            # Kickers are the rank of the pair, then the three highest other cards
            other_kickers = sorted([r for r in ranks if r != pair_rank], reverse=True)
            return "ONE_PAIR", self.HAND_RANKINGS["ONE_PAIR"], [pair_rank] + other_kickers[:3]

        # High Card
        # Kickers are all 5 card ranks, sorted
        return "HIGH_CARD", self.HAND_RANKINGS["HIGH_CARD"], sorted(ranks, reverse=True)

    def compare_hands(self, hand1_details: Tuple[str, List[Card], int, List[int]],
                        hand2_details: Tuple[str, List[Card], int, List[int]]) -> int:
        """
        Compares two evaluated hands.
        Returns:
            1 if hand1 is better,
           -1 if hand2 is better,
            0 if it's a tie (split pot).
        """
        _, _, rank1, kickers1 = hand1_details
        _, _, rank2, kickers2 = hand2_details

        if rank1 > rank2:
            return 1
        if rank1 < rank2:
            return -1

        # Ranks are equal, compare kickers
        for k1, k2 in zip(kickers1, kickers2):
            if k1 > k2:
                return 1
            if k1 < k2:
                return -1

        return 0 # Tie

# Example Usage (for testing HandEvaluator)
if __name__ == '__main__':
    evaluator = HandEvaluator()

    # Test cases
    royal_flush = [Card('A', '♠'), Card('K', '♠'), Card('Q', '♠'), Card('J', '♠'), Card('T', '♠')]
    straight_flush_king = [Card('K', '♥'), Card('Q', '♥'), Card('J', '♥'), Card('T', '♥'), Card('9', '♥')]
    straight_flush_5_high = [Card('5', '♦'), Card('4', '♦'), Card('3', '♦'), Card('2', '♦'), Card('A', '♦')] # Wheel

    four_of_a_kind = [Card('A', '♠'), Card('A', '♥'), Card('A', '♦'), Card('A', '♣'), Card('K', '♠')]
    four_of_a_kind_kicker = [Card('7', '♠'), Card('7', '♥'), Card('7', '♦'), Card('7', '♣'), Card('Q', '♠')]

    full_house_A_K = [Card('A', '♠'), Card('A', '♥'), Card('A', '♦'), Card('K', '♣'), Card('K', '♠')]
    full_house_K_A = [Card('K', '♠'), Card('K', '♥'), Card('K', '♦'), Card('A', '♣'), Card('A', '♠')]

    flush_ace_high = [Card('A', '♠'), Card('K', '♠'), Card('Q', '♠'), Card('J', '♠'), Card('8', '♠')]
    flush_king_high = [Card('K', '♥'), Card('Q', '♥'), Card('J', '♥'), Card('9', '♥'), Card('7', '♥')]

    straight_ace_high = [Card('A', '♠'), Card('K', '♥'), Card('Q', '♦'), Card('J', '♣'), Card('T', '♠')]
    straight_king_high = [Card('K', '♠'), Card('Q', '♥'), Card('J', '♦'), Card('T', '♣'), Card('9', '♠')]
    straight_5_high = [Card('5', '♠'), Card('4', '♥'), Card('3', '♦'), Card('2', '♣'), Card('A', '♠')] # Wheel

    three_of_a_kind = [Card('A', '♠'), Card('A', '♥'), Card('A', '♦'), Card('K', '♣'), Card('Q', '♠')]

    two_pair_A_K_Q = [Card('A', '♠'), Card('A', '♥'), Card('K', '♦'), Card('K', '♣'), Card('Q', '♠')]
    two_pair_A_K_J = [Card('A', '♠'), Card('A', '♥'), Card('K', '♦'), Card('K', '♣'), Card('J', '♠')]
    two_pair_A_Q_K = [Card('A', '♠'), Card('A', '♥'), Card('Q', '♦'), Card('Q', '♣'), Card('K', '♠')]

    one_pair_A_K_Q_J = [Card('A', '♠'), Card('A', '♥'), Card('K', '♦'), Card('Q', '♣'), Card('J', '♠')]
    one_pair_A_K_Q_9 = [Card('A', '♠'), Card('A', '♥'), Card('K', '♦'), Card('Q', '♣'), Card('9', '♠')]

    high_card_A = [Card('A', '♠'), Card('K', '♥'), Card('Q', '♦'), Card('J', '♣'), Card('9', '♠')]
    high_card_K = [Card('K', '♠'), Card('Q', '♥'), Card('J', '♦'), Card('9', '♣'), Card('8', '♠')]

    hole = [Card('A', '♠'), Card('K', '♥')]
    community = [Card('Q', '♦'), Card('J', '♣'), Card('T', '♠'), Card('2', '♠'), Card('3', '♦')]
    # Expected: Straight Ace high

    tests = {
        "Royal Flush": (royal_flush, "ROYAL_FLUSH", [14,13,12,11,10]),
        "Straight Flush King High": (straight_flush_king, "STRAIGHT_FLUSH", [13,12,11,10,9]),
        "Straight Flush 5 High (Wheel)": (straight_flush_5_high, "STRAIGHT_FLUSH", [5,4,3,2,1]),
        "Four of a Kind Aces": (four_of_a_kind, "FOUR_OF_A_KIND", [14, 13]),
        "Four of a Kind Sevens": (four_of_a_kind_kicker, "FOUR_OF_A_KIND", [7, 12]),
        "Full House A over K": (full_house_A_K, "FULL_HOUSE", [14, 13]),
        "Full House K over A": (full_house_K_A, "FULL_HOUSE", [13, 14]), # Should be K, A
        "Flush Ace High": (flush_ace_high, "FLUSH", [14,13,12,11,8]),
        "Flush King High": (flush_king_high, "FLUSH", [13,12,11,9,7]),
        "Straight Ace High": (straight_ace_high, "STRAIGHT", [14,13,12,11,10]),
        "Straight King High": (straight_king_high, "STRAIGHT", [13,12,11,10,9]),
        "Straight 5 High (Wheel)": (straight_5_high, "STRAIGHT", [5,4,3,2,1]),
        "Three of a Kind Aces": (three_of_a_kind, "THREE_OF_A_KIND", [14,13,12]),
        "Two Pair A, K kicker Q": (two_pair_A_K_Q, "TWO_PAIR", [14,13,12]),
        "Two Pair A, K kicker J": (two_pair_A_K_J, "TWO_PAIR", [14,13,11]),
        "Two Pair A, Q kicker K": (two_pair_A_Q_K, "TWO_PAIR", [14,12,13]), # Sorted kickers: HighPair, LowPair, Other
        "One Pair Aces, K,Q,J": (one_pair_A_K_Q_J, "ONE_PAIR", [14,13,12,11]),
        "One Pair Aces, K,Q,9": (one_pair_A_K_Q_9, "ONE_PAIR", [14,13,12,9]),
        "High Card Ace": (high_card_A, "HIGH_CARD", [14,13,12,11,9]),
        "High Card King": (high_card_K, "HIGH_CARD", [13,12,11,9,8]),
        "Community Eval (Ace High Straight)": (hole + community, "STRAIGHT", [14,13,12,11,10])
    }

    print("Running HandEvaluator Tests:")
    passed_all = True
    for name, (cards_to_eval, expected_name, expected_kickers_ranks) in tests.items():
        if name == "Community Eval (Ace High Straight)":
            # This uses the main evaluate_hand method
            hand_name, best_cards, hand_rank, kickers = evaluator.evaluate_hand(cards_to_eval[:2], cards_to_eval[2:])
        else:
            # These test _calculate_hand_details directly with 5 cards
            hand_name, hand_rank, kickers = evaluator._calculate_hand_details(sorted(cards_to_eval, key=lambda c: c.rank_value(), reverse=True))

        print(f"Test: {name}")
        print(f"  Input cards: {cards_to_eval}")
        print(f"  Result: {hand_name}, Cards: {best_cards if name == 'Community Eval (Ace High Straight)' else cards_to_eval}, Kickers: {kickers}")
        print(f"  Expected: {expected_name}, Expected Kickers: {expected_kickers_ranks}")

        if hand_name == expected_name and kickers == expected_kickers_ranks:
            print(f"  Status: PASSED")
        else:
            print(f"  Status: FAILED")
            passed_all = False
        print("-" * 20)

    if passed_all:
        print("All HandEvaluator basic tests PASSED!")
    else:
        print("Some HandEvaluator tests FAILED.")

    print("\nComparison Tests:")
    # Hand 1: Full House (Aces over Kings)
    # Hand 2: Flush (King high)
    h1_details = evaluator._calculate_hand_details(full_house_A_K)
    h2_details = evaluator._calculate_hand_details(flush_king_high)
    print(f"Comparing {h1_details[0]} {h1_details[2]} vs {h2_details[0]} {h2_details[2]}: Expected 1, Got {evaluator.compare_hands(h1_details, h2_details)}")

    # Hand 1: Two Pair (A, K, Q kicker)
    # Hand 2: Two Pair (A, K, J kicker)
    h1_tp_details = evaluator._calculate_hand_details(two_pair_A_K_Q)
    h2_tp_details = evaluator._calculate_hand_details(two_pair_A_K_J)
    print(f"Comparing {h1_tp_details[0]} {h1_tp_details[2]} vs {h2_tp_details[0]} {h2_tp_details[2]}: Expected 1, Got {evaluator.compare_hands(h1_tp_details, h2_tp_details)}")

    # Hand 1: Straight (Ace High)
    # Hand 2: Straight (King High)
    h1_str_details = evaluator._calculate_hand_details(straight_ace_high)
    h2_str_details = evaluator._calculate_hand_details(straight_king_high)
    print(f"Comparing {h1_str_details[0]} {h1_str_details[2]} vs {h2_str_details[0]} {h2_str_details[2]}: Expected 1, Got {evaluator.compare_hands(h1_str_details, h2_str_details)}")

    # Tie test: Two identical high card hands
    hc1 = [Card('A', '♠'), Card('K', '♥'), Card('Q', '♦'), Card('J', '♣'), Card('9', '♠')]
    hc2 = [Card('A', '♣'), Card('K', '♦'), Card('Q', '♥'), Card('J', '♠'), Card('9', '♦')] # Same ranks, diff suits
    h1_hc_details = evaluator._calculate_hand_details(hc1)
    h2_hc_details = evaluator._calculate_hand_details(hc2)
    print(f"Comparing {h1_hc_details[0]} {h1_hc_details[2]} vs {h2_hc_details[0]} {h2_hc_details[2]} (tie): Expected 0, Got {evaluator.compare_hands(h1_hc_details, h2_hc_details)}")

    # Test evaluate_hand with 7 cards leading to a straight flush
    hole_sf = [Card('A', '♦'), Card('K', '♦')]
    comm_sf = [Card('Q', '♦'), Card('J', '♦'), Card('T', '♦'), Card('2','♠'), Card('3','♥')]
    name, bc, rank, kicks = evaluator.evaluate_hand(hole_sf, comm_sf)
    print(f"7-card Royal Flush Test: {name}, {bc}, {rank}, {kicks} -> Expected ROYAL_FLUSH, [14,13,12,11,10]")

    # Test evaluate_hand with 7 cards, best is full house
    hole_fh = [Card('A', '♠'), Card('A', '♥')] # Pair of Aces
    comm_fh = [Card('K', '♦'), Card('K', '♣'), Card('A', '♦'), Card('2','♠'), Card('3','♥')] # Trips Aces + Pair Kings
    # Expected: Full House, Aces over Kings
    name_fh, bc_fh, rank_fh, kicks_fh = evaluator.evaluate_hand(hole_fh, comm_fh)
    print(f"7-card Full House Test (Aces full of Kings): {name_fh}, {bc_fh}, {rank_fh}, {kicks_fh} -> Expected FULL_HOUSE, [14, 13]")
    # Check that best_five_cards are correct: 3 Aces, 2 Kings
    ace_count = sum(1 for card in bc_fh if card.rank == 'A')
    king_count = sum(1 for card in bc_fh if card.rank == 'K')
    print(f"  Aces in best hand: {ace_count}, Kings in best hand: {king_count}")
    if not (ace_count == 3 and king_count == 2 and name_fh == "FULL_HOUSE" and kicks_fh == [14,13]):
        print("  FAILED Full House composition check.")
        passed_all = False
    else:
        print("  PASSED Full House composition check.")

    if passed_all:
        print("\nAll extended tests also passed!")
    else:
        print("\nSome extended tests FAILED.")
