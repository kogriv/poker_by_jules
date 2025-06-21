import unittest
from poker_game.core.game_state import GameState, player_to_dict, card_to_dict, dict_to_card
from poker_game.core.player import HumanPlayer, Player
from poker_game.core.bot_player import RandomBot
from poker_game.core.cards import Card
from poker_game.core.events import Action

class TestGameState(unittest.TestCase):
    def setUp(self):
        self.player1 = HumanPlayer(player_id="Alice", stack=1000)
        self.player2 = RandomBot(player_id="BobBot", stack=800)
        self.player1.hole_cards = [Card('A', '♠'), Card('K', '♥')]
        self.player2.hole_cards = [Card('7', '♦'), Card('2', '♣')]
        self.player1.current_bet = 100
        self.player2.current_bet = 50
        self.player2.is_folded = True

        self.community = [Card('Q', '♠'), Card('J', '♠'), Card('T', '♦')]

        self.game_state = GameState(
            players=[self.player1, self.player2],
            dealer_button_position=0,
            current_player_turn_index=1,
            community_cards=self.community,
            pot_size=300,
            current_round_pot=150,
            current_bet_to_match=100,
            last_raiser="Alice",
            last_raise_amount=50,
            game_phase="flop",
            small_blind=10,
            big_blind=20,
            min_bet=20,
            round_number=3,
            is_game_over=False
        )

    def test_card_serialization(self):
        card = Card('A', '♠')
        card_d = card_to_dict(card)
        self.assertEqual(card_d, {"rank": 'A', "suit": '♠'})
        new_card = dict_to_card(card_d)
        self.assertEqual(new_card.rank, 'A')
        self.assertEqual(new_card.suit, '♠')
        self.assertEqual(card, new_card)

    def test_player_serialization(self):
        player = HumanPlayer(player_id="TestP", stack=500)
        player.hole_cards = [Card('T', '♣'), Card('9', '♣')]
        player.current_bet = 25
        player.is_folded = False
        player.is_all_in = True

        player_d = player_to_dict(player)

        expected_dict = {
            "player_id": "TestP",
            "stack": 500,
            "hole_cards": [{"rank": 'T', "suit": '♣'}, {"rank": '9', "suit": '♣'}],
            "current_bet": 25,
            "is_folded": False,
            "is_all_in": True,
            "class_type": "HumanPlayer"
        }
        self.assertEqual(player_d, expected_dict)

    def test_game_state_to_dict(self):
        state_dict = self.game_state.to_dict()

        self.assertEqual(len(state_dict["players"]), 2)
        self.assertEqual(state_dict["players"][0]["player_id"], "Alice")
        self.assertEqual(state_dict["players"][0]["stack"], 1000) # Stack is not reduced by current_bet in player obj directly
        self.assertEqual(state_dict["players"][0]["current_bet"], 100)
        self.assertEqual(state_dict["players"][0]["class_type"], "HumanPlayer")
        self.assertEqual(len(state_dict["players"][0]["hole_cards"]), 2)
        self.assertEqual(state_dict["players"][0]["hole_cards"][0], {"rank": 'A', "suit": '♠'})

        self.assertEqual(state_dict["players"][1]["player_id"], "BobBot")
        self.assertEqual(state_dict["players"][1]["is_folded"], True)
        self.assertEqual(state_dict["players"][1]["class_type"], "RandomBot")


        self.assertEqual(state_dict["dealer_button_position"], 0)
        self.assertEqual(state_dict["current_player_turn_index"], 1)
        self.assertEqual(len(state_dict["community_cards"]), 3)
        self.assertEqual(state_dict["community_cards"][0], {"rank": 'Q', "suit": '♠'})
        self.assertEqual(state_dict["pot_size"], 300)
        self.assertEqual(state_dict["current_round_pot"], 150)
        self.assertEqual(state_dict["current_bet_to_match"], 100)
        self.assertEqual(state_dict["last_raiser"], "Alice")
        self.assertEqual(state_dict["last_raise_amount"], 50)
        self.assertEqual(state_dict["game_phase"], "flop")
        self.assertEqual(state_dict["small_blind"], 10)
        self.assertEqual(state_dict["big_blind"], 20)
        self.assertEqual(state_dict["min_bet"], 20)
        self.assertEqual(state_dict["round_number"], 3)
        self.assertFalse(state_dict["is_game_over"])

    def test_game_state_from_dict(self):
        state_dict = self.game_state.to_dict()
        rehydrated_state = GameState.from_dict(state_dict)

        self.assertIsInstance(rehydrated_state, GameState)
        self.assertEqual(len(rehydrated_state.players), 2)

        # Player 1 (Alice - HumanPlayer)
        p1_rehydrated = rehydrated_state.players[0]
        self.assertIsInstance(p1_rehydrated, HumanPlayer)
        self.assertEqual(p1_rehydrated.player_id, self.player1.player_id)
        self.assertEqual(p1_rehydrated.stack, self.player1.stack)
        self.assertEqual(p1_rehydrated.current_bet, self.player1.current_bet)
        self.assertEqual(len(p1_rehydrated.hole_cards), len(self.player1.hole_cards))
        self.assertEqual(p1_rehydrated.hole_cards[0], self.player1.hole_cards[0])
        self.assertEqual(p1_rehydrated.is_folded, self.player1.is_folded)

        # Player 2 (BobBot - RandomBot)
        p2_rehydrated = rehydrated_state.players[1]
        self.assertIsInstance(p2_rehydrated, RandomBot)
        self.assertEqual(p2_rehydrated.player_id, self.player2.player_id)
        self.assertEqual(p2_rehydrated.is_folded, self.player2.is_folded)

        self.assertEqual(rehydrated_state.dealer_button_position, self.game_state.dealer_button_position)
        self.assertEqual(rehydrated_state.current_player_turn_index, self.game_state.current_player_turn_index)

        self.assertEqual(len(rehydrated_state.community_cards), len(self.game_state.community_cards))
        if self.game_state.community_cards: # Ensure cards match if they exist
            self.assertEqual(rehydrated_state.community_cards[0], self.game_state.community_cards[0])

        self.assertEqual(rehydrated_state.pot_size, self.game_state.pot_size)
        self.assertEqual(rehydrated_state.current_round_pot, self.game_state.current_round_pot)
        self.assertEqual(rehydrated_state.current_bet_to_match, self.game_state.current_bet_to_match)
        self.assertEqual(rehydrated_state.last_raiser, self.game_state.last_raiser)
        self.assertEqual(rehydrated_state.last_raise_amount, self.game_state.last_raise_amount)
        self.assertEqual(rehydrated_state.game_phase, self.game_state.game_phase)
        self.assertEqual(rehydrated_state.small_blind, self.game_state.small_blind)
        self.assertEqual(rehydrated_state.big_blind, self.game_state.big_blind)
        self.assertEqual(rehydrated_state.min_bet, self.game_state.min_bet)
        self.assertEqual(rehydrated_state.round_number, self.game_state.round_number)
        self.assertEqual(rehydrated_state.is_game_over, self.game_state.is_game_over)

    def test_get_player_by_id(self):
        found_player = self.game_state.get_player_by_id("Alice")
        self.assertIsNotNone(found_player)
        self.assertEqual(found_player.player_id, "Alice")
        self.assertIsInstance(found_player, HumanPlayer)

        not_found_player = self.game_state.get_player_by_id("Charlie")
        self.assertIsNone(not_found_player)

    def test_get_active_players_in_round(self):
        # player1 (Alice) is not folded, player2 (BobBot) is folded.
        active_players = self.game_state.get_active_players_in_round()
        self.assertEqual(len(active_players), 1)
        self.assertEqual(active_players[0].player_id, "Alice")

        # Unfold BobBot for another test
        self.player2.is_folded = False
        active_players_both = self.game_state.get_active_players_in_round()
        self.assertEqual(len(active_players_both), 2)
        self.player2.is_folded = True # Reset for other tests

    def test_get_players_eligible_to_act(self):
        # player1 (Alice) is not folded, not all-in.
        # player2 (BobBot) is folded.
        eligible_players = self.game_state.get_players_eligible_to_act()
        self.assertEqual(len(eligible_players), 1)
        self.assertEqual(eligible_players[0].player_id, "Alice")

        # Make Alice all-in
        self.player1.is_all_in = True
        eligible_players_none = self.game_state.get_players_eligible_to_act()
        self.assertEqual(len(eligible_players_none), 0)
        self.player1.is_all_in = False # Reset

        # Unfold BobBot
        self.player2.is_folded = False
        eligible_players_both = self.game_state.get_players_eligible_to_act()
        self.assertEqual(len(eligible_players_both), 2)
        self.player2.is_folded = True # Reset

    def test_empty_game_state_serialization(self):
        empty_state = GameState()
        empty_dict = empty_state.to_dict()

        self.assertEqual(empty_dict["players"], [])
        self.assertEqual(empty_dict["community_cards"], [])
        # Check some defaults
        self.assertEqual(empty_dict["small_blind"], 10) # Default from dataclass field
        self.assertEqual(empty_dict["game_phase"], "pre-flop")

        rehydrated_empty = GameState.from_dict(empty_dict)
        self.assertEqual(len(rehydrated_empty.players), 0)
        self.assertEqual(len(rehydrated_empty.community_cards), 0)
        self.assertEqual(rehydrated_empty.small_blind, 10)

if __name__ == '__main__':
    unittest.main()
