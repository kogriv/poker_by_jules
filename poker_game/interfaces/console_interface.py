from poker_game.interfaces.base_interface import GameInterface
from poker_game.core.player import Player, HumanPlayer
from poker_game.core.game_state import GameState
from poker_game.core.events import Action, GameEvent
from poker_game.core.cards import Card # For type hinting if needed

class ConsoleInterface(GameInterface):
    def __init__(self, game_mode: str = "normal"): # Default to normal if not specified
        self.game_mode = game_mode

    def get_player_action(self, player: Player, game_state: GameState, allowed_actions: dict) -> Action:
        if not isinstance(player, HumanPlayer):
            # Bots decide on their own, this method might not be called for them by GameEngine directly if bots have their own logic path.
            # Or, if it is, it should just trigger their internal decision.
            # For now, let's assume GameEngine calls player.make_decision() which for HumanPlayer would delegate to this.
            # This method in the interface is specifically for when HUMAN input is needed.
            raise TypeError("get_player_action on ConsoleInterface is for HumanPlayer only.")

        print(f"\n--- {player.player_id}'s Turn ---")
        self.display_player_cards(player) # Show human their cards

        print(f"Community Cards: {[str(c) for c in game_state.community_cards] if game_state.community_cards else 'None'}")
        print(f"Pot: {game_state.pot_size + game_state.current_round_pot}")
        print(f"Current Bet to Match: {game_state.current_bet_to_match} (Your bet: {player.current_bet})")
        print(f"Your Stack: {player.stack}")

        prompt = "Allowed actions: "
        action_map = {}
        idx = 1

        # Build a user-friendly list of actions
        possible_choices = []
        if allowed_actions.get("fold"):
            possible_choices.append(f"{idx}. Fold")
            action_map[str(idx)] = Action(type="fold", player_id=player.player_id)
            idx += 1

        amount_to_call = game_state.current_bet_to_match - player.current_bet
        if allowed_actions.get("check") and amount_to_call <=0 :
            possible_choices.append(f"{idx}. Check")
            action_map[str(idx)] = Action(type="check", player_id=player.player_id)
            idx += 1

        if allowed_actions.get("call") and amount_to_call > 0:
            call_cost = min(player.stack, amount_to_call)
            possible_choices.append(f"{idx}. Call ({call_cost})")
            action_map[str(idx)] = Action(type="call", amount=call_cost, player_id=player.player_id)
            idx += 1

        min_bet = allowed_actions.get("bet", {}).get("min", game_state.big_blind)
        max_bet = allowed_actions.get("bet", {}).get("max", player.stack)
        if allowed_actions.get("bet") and amount_to_call <= 0: # Can bet if it's a check situation
            possible_choices.append(f"{idx}. Bet <amount> (min: {min_bet}, max: {max_bet})")
            action_map[str(idx)] = "bet_input" # Special marker for input
            idx += 1

        min_raise = allowed_actions.get("raise", {}).get("min_total_bet", 0) # Min total bet for a raise
        max_raise = allowed_actions.get("raise", {}).get("max_total_bet", player.stack) # Max total bet for a raise
        if allowed_actions.get("raise") and amount_to_call > 0 : # Can raise if there's a bet to call
             # Raise amount is the total amount the player will have bet in the round
            possible_choices.append(f"{idx}. Raise to <total_amount> (min_total: {min_raise}, max_total: {max_raise})")
            action_map[str(idx)] = "raise_input" # Special marker for input
            idx += 1

        if not possible_choices:
            # This might happen if player is all-in and action automatically resolves.
            # GameEngine should ideally not ask for action then.
            print("No actions available (e.g., you are all-in). Auto-checking/passing.")
            return Action(type="check", player_id=player.player_id) # Or a specific "pass" action

        print(prompt + ", ".join(possible_choices))

        if self.game_mode == "smoke":
            # SMOKE TEST: Automatically return a default action
            print(f"SMOKE MODE: {player.player_id} auto-acting.")
            if allowed_actions.get("check") and (game_state.current_bet_to_match - player.current_bet) <=0:
                print(f"SMOKE MODE: {player.player_id} auto-checking.")
                return Action(type="check", player_id=player.player_id)
            # Prefer call if possible and a bet is faced
            elif allowed_actions.get("call") and (game_state.current_bet_to_match - player.current_bet) > 0:
                 actual_call_amount = allowed_actions.get("call")
                 if isinstance(actual_call_amount, int) and actual_call_amount > 0 and actual_call_amount <= player.stack : # Ensure player can cover
                    print(f"SMOKE MODE: {player.player_id} auto-calling {actual_call_amount}.")
                    return Action(type="call", amount=actual_call_amount, player_id=player.player_id)
                 # If call amount is > stack, but call is allowed, it implies an all-in call
                 elif isinstance(actual_call_amount, int) and actual_call_amount > 0 and actual_call_amount > player.stack and player.stack > 0:
                    print(f"SMOKE MODE: {player.player_id} auto-calling ALL-IN for {player.stack}.")
                    return Action(type="call", amount=player.stack, player_id=player.player_id)


            # Fallback to fold if check/sensible call not simple options
            if allowed_actions.get("fold"):
                print(f"SMOKE MODE: {player.player_id} auto-folding.")
                return Action(type="fold", player_id=player.player_id)

            # If somehow fold is not an option, but others are (e.g. only bet/raise from all-in players), take first available.
            # This state should be rare.
            print(f"SMOKE MODE: {player.player_id} no simple action, taking first from {allowed_actions}")
            if allowed_actions: # Should always be true if this path is reached
                first_action_type = list(allowed_actions.keys())[0]
                if first_action_type == "bet" and isinstance(allowed_actions["bet"], dict):
                    return Action(type="bet", amount=allowed_actions["bet"]["min"], player_id=player.player_id)
                elif first_action_type == "raise" and isinstance(allowed_actions["raise"], dict):
                     return Action(type="raise", amount=allowed_actions["raise"]["min_total_bet"], player_id=player.player_id)
                # Fallback to a check action if nothing else (should be covered by fold)
                return Action(type="check", player_id=player.player_id) # Should be caught by player all-in if no actions
            else: # No allowed actions, implies player is all-in or situation is resolved.
                return Action(type="check", player_id=player.player_id) # Effectively a pass

        # NORMAL MODE: Interactive input loop
        else:
            while True:
                try:
                    choice = input(f"{player.player_id}, choose action (number or type e.g. 'bet 50'): ").strip().lower()
                    parts = choice.split()
                    action_type_input = parts[0]

                    selected_action = None

                    # Try matching by number first
                    if action_type_input in action_map: # action_map defined earlier in the function
                        action_val = action_map[action_type_input]
                        if isinstance(action_val, Action):
                            selected_action = action_val
                        elif action_val == "bet_input":
                            action_type_input = "bet" # Fall through to amount processing
                        elif action_val == "raise_input":
                            action_type_input = "raise" # Fall through to amount processing

                    if selected_action: # Action like fold, check, call (by number)
                        return selected_action

                    action_amount = 0
                    if len(parts) > 1:
                        try:
                            action_amount = int(parts[1])
                        except ValueError:
                            print("Invalid amount. Please enter a number.")
                            continue

                    if action_type_input == "fold":
                        if allowed_actions.get("fold"):
                            return Action(type="fold", player_id=player.player_id)
                        else: print("Fold not allowed.")
                    elif action_type_input == "check":
                        if allowed_actions.get("check") and amount_to_call <=0: # amount_to_call defined earlier
                            return Action(type="check", player_id=player.player_id)
                        else: print("Check not allowed (must call or raise).")
                    elif action_type_input == "call":
                        if allowed_actions.get("call") and amount_to_call > 0:
                            call_cost = min(player.stack, amount_to_call)
                            return Action(type="call", amount=call_cost, player_id=player.player_id)
                        else: print("Call not allowed or nothing to call.")

                    elif action_type_input == "bet":
                        # min_bet, max_bet are defined earlier in the function
                        if allowed_actions.get("bet") and amount_to_call <= 0:
                            if len(parts) < 2:
                                print("Please specify bet amount (e.g., 'bet 50').")
                                continue
                            if not (min_bet <= action_amount <= max_bet):
                                print(f"Invalid bet amount. Must be between {min_bet} and {max_bet}. Your stack: {player.stack}")
                                continue
                            if action_amount > player.stack:
                                 print(f"Cannot bet more than your stack ({player.stack}). Going all-in.")
                                 action_amount = player.stack
                            return Action(type="bet", amount=action_amount, player_id=player.player_id)
                        else:
                            print("Bet not allowed (must call or raise, or check).")

                    elif action_type_input == "raise":
                        # min_raise, max_raise are defined earlier in the function
                        if allowed_actions.get("raise") and amount_to_call > 0:
                            if len(parts) < 2:
                                print("Please specify total raise amount (e.g., 'raise 100').")
                                continue
                            if not (min_raise <= action_amount <= max_raise): # min_raise and max_raise are total bet amounts
                                print(f"Invalid raise (total) amount. Must be between {min_raise} and {max_raise}. Your stack: {player.stack}")
                                continue
                            if action_amount > player.stack: # This check might be redundant if max_raise is player.stack
                                print(f"Cannot raise to more than your stack ({player.stack}). Raising all-in.")
                                action_amount = player.stack # This should be player.current_bet + player.stack if action_amount is total
                                                             # No, action_amount IS the total bet here. So it should be capped at player's total betting capacity.
                                                             # Max_raise is already player.stack (total).
                            if action_amount <= game_state.current_bet_to_match :
                                print(f"Must raise to more than current bet to match ({game_state.current_bet_to_match}).")
                                continue

                            return Action(type="raise", amount=action_amount, player_id=player.player_id)
                        else:
                            print("Raise not allowed or no bet to raise.")
                    else:
                        print(f"Invalid action type: '{action_type_input}'. Choices: {', '.join(c.split()[0] for c in possible_choices if '<' not in c) + ['bet <amt>', 'raise <amt>']}")

                except EOFError:
                    print("\nEOFError: Input stream ended. This can happen in non-interactive environments.")
                    print("Defaulting to FOLD action for this turn.")
                    if allowed_actions.get("fold"):
                        return Action(type="fold", player_id=player.player_id)
                    else: # Should not happen if fold is always possible unless all-in with no action
                        return Action(type="check", player_id=player.player_id) # Fallback
                except Exception as e:
                    print(f"An error occurred processing input: {e}. Please try again.")

    def notify_event(self, event: GameEvent, game_state: GameState) -> None:
        # Simple console logging of events
        print(f"[EVENT] {event.timestamp.strftime('%H:%M:%S')} - {event.type}: {event.data}")

        # Could add more specific handling for certain event types to make output prettier
        if event.type == "player_action":
            player = game_state.get_player_by_id(event.data.get('player_id'))
            player_name = player.player_id if player else event.data.get('player_id', 'UnknownPlayer')
            action_type = event.data.get('action_type', 'unknown_action')
            amount = event.data.get('amount', 0)
            if action_type in ["bet", "call", "raise"] and amount > 0:
                print(f"  > {player_name} {action_type}s {amount}")
            elif action_type in ["fold", "check"]:
                 print(f"  > {player_name} {action_type}s")
            else:
                print(f"  > {player_name} performs {action_type}")


        elif event.type == "cards_dealt":
            if "player_id" in event.data and "cards" in event.data:
                # This is sensitive, console interface might not want to show all dealt cards
                # unless it's for the specific human player it's interacting with.
                # GameEngine should send specific "show_player_hole_cards" event to interface for that.
                # For now, let's assume this event is public info (e.g. "Player X received cards")
                # Or if it's community cards:
                if event.data.get("type") == "community":
                    print(f"  > Community cards dealt: {event.data['cards']}")
            # This might be better handled by display_game_state calls after such events.

        elif event.type == "round_end" or event.type == "showdown":
            self.display_game_state(game_state) # Show final state before winner usually

    def display_game_state(self, game_state: GameState, current_player_id: str = None, show_hole_cards_for_player: str = None) -> None:
        print("\n--- Current Game State ---")
        print(f"Round: {game_state.round_number}, Phase: {game_state.game_phase.upper()}")
        print(f"Community Cards: {[str(c) for c in game_state.community_cards] if game_state.community_cards else 'None'}")
        print(f"Total Pot: {game_state.pot_size + game_state.current_round_pot}") # Pot + current round bets

        print("Players:")
        for p in game_state.players:
            status = []
            if p.is_folded: status.append("FOLDED")
            if p.is_all_in: status.append("ALL-IN")
            status_str = f" ({', '.join(status)})" if status else ""

            turn_indicator = " (*) " if p.player_id == current_player_id else "     "

            hole_cards_str = ""
            if show_hole_cards_for_player == p.player_id and p.hole_cards:
                hole_cards_str = f" Cards: {[str(c) for c in p.hole_cards]}"
            elif p.hole_cards and game_state.game_phase == "showdown": # Show all cards at showdown
                hole_cards_str = f" Cards: {[str(c) for c in p.hole_cards]}"
            elif p.hole_cards : # For non-showdown, non-active player
                 hole_cards_str = " Cards: [X, X]" # Indicate they have cards but not shown

            print(f"  {turn_indicator}{p.player_id}: Stack={p.stack}, Bet={p.current_bet}{status_str}{hole_cards_str}")
        print("-------------------------")

    def display_round_start(self, game_state: GameState, round_number: int) -> None:
        print(f"\n--- Starting Round {round_number} ---")
        print(f"Dealer button is at player: {game_state.players[game_state.dealer_button_position].player_id}")
        # Blinds info can be part of this
        sb_player = game_state.players[(game_state.dealer_button_position + 1) % len(game_state.players)]
        bb_player = game_state.players[(game_state.dealer_button_position + 2) % len(game_state.players)]
        print(f"Small Blind ({game_state.small_blind}) posted by {sb_player.player_id if sb_player else 'N/A'}")
        print(f"Big Blind ({game_state.big_blind}) posted by {bb_player.player_id if bb_player else 'N/A'}")


    def display_player_cards(self, player: Player) -> None:
        if isinstance(player, HumanPlayer): # Only show for human players via this direct call
            print(f"Your cards, {player.player_id}: {[str(c) for c in player.hole_cards] if player.hole_cards else 'None'}")

    def display_winner(self, winners_data: list, game_state: GameState, hand_results: dict) -> None:
        # winners_data is expected to be a list of tuples: (player_id, amount_won, hand_name, best_5_cards)
        print("\n--- Round Over ---")
        if not winners_data:
            print("No winners determined (e.g. all folded).")
            return

        for winner_info in winners_data:
            player_id = winner_info["player_id"]
            amount_won = winner_info["amount_won"]
            hand_name = winner_info.get("hand_name", "Unknown Hand") # From hand_results
            best_cards = winner_info.get("best_cards", []) # From hand_results

            player = game_state.get_player_by_id(player_id)
            player_display_name = player.player_id if player else player_id

            print(f"Player {player_display_name} wins {amount_won} chips.")
            if hand_name and hand_name != "Unknown Hand":
                print(f"  With hand: {hand_name} ({[str(c) for c in best_cards]})")
            if player:
                 # Show hole cards of winner if not already visible
                 print(f"  {player_display_name}'s hole cards: {[str(c) for c in player.hole_cards]}")

        # Display hands of other players involved in showdown from hand_results
        if game_state.game_phase == "showdown":
            print("Showdown Hands:")
            for player_id, result in hand_results.items():
                player = game_state.get_player_by_id(player_id)
                if player and not player.is_folded : # Only show for players who went to showdown
                    is_winner = any(wd["player_id"] == player_id for wd in winners_data)
                    win_indicator = " (Winner)" if is_winner else ""
                    print(f"  {player.player_id}{win_indicator}: {result['hand_name']} ({[str(c) for c in result['best_cards']]}) - Hole: {[str(c) for c in player.hole_cards]}")


    def get_player_names(self, num_players: int) -> list[str]:
        names = []
        for i in range(num_players):
            while True:
                name = input(f"Enter name for Human Player {i+1}: ").strip()
                if name:
                    names.append(name)
                    break
                else:
                    print("Name cannot be empty.")
        return names

    def show_message(self, message: str) -> None:
        print(message)
