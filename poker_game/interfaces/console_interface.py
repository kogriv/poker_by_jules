from poker_game.interfaces.base_interface import GameInterface
from poker_game.core.player import Player, HumanPlayer
from poker_game.core.game_state import GameState
from poker_game.core.events import Action, GameEvent
from poker_game.core.cards import Card # For type hinting if needed
from typing import Optional # Added Optional

class ConsoleInterface(GameInterface):
    def __init__(self, game_mode: str = "normal"): # Default to normal if not specified
        self.game_mode = game_mode
        self._print_welcome_banner()

    def _print_welcome_banner(self):
        print("🎰 TEXAS HOLD'EM POKER 🎰")
        print("==================================================")
        print("Welcome to Texas Hold'em Poker!")
        print("==================================================")
        print() # Empty line for spacing

    def get_player_action(self, player: Player, game_state: GameState, allowed_actions: dict) -> Action:
        if not isinstance(player, HumanPlayer):
            # Bots decide on their own, this method might not be called for them by GameEngine directly if bots have their own logic path.
            # Or, if it is, it should just trigger their internal decision.
            # For now, let's assume GameEngine calls player.make_decision() which for HumanPlayer would delegate to this.
            # This method in the interface is specifically for when HUMAN input is needed.
            raise TypeError("get_player_action on ConsoleInterface is for HumanPlayer only.")

        # Game state summary is now shown by display_game_state before this method is called.
        # self.display_player_cards(player) # Human cards are shown in display_game_state if it's their turn

        print(f"\n{player.player_id}, it's your turn!")

        action_map = {} # For numbered choices if we re-implement
        possible_choices_display = [] # For user-friendly list

        amount_to_call = game_state.current_bet_to_match - player.current_bet

        if allowed_actions.get("fold"): possible_choices_display.append("fold")
        if allowed_actions.get("check") and amount_to_call <= 0: possible_choices_display.append("check")
        if allowed_actions.get("call") and amount_to_call > 0: possible_choices_display.append("call")
        if allowed_actions.get("bet"): possible_choices_display.append("bet <amount>")
        if allowed_actions.get("raise"): possible_choices_display.append("raise <total_amount>")

        print(f"Valid actions: {', '.join(possible_choices_display)}")
        print("------------------------------------------------------------")
        print("Action explanations:")
        if "fold" in possible_choices_display: print("- fold: Give up your hand")
        if "check" in possible_choices_display: print("- check: Pass without betting (only when no bet to call)")
        if "call" in possible_choices_display:
            call_cost = min(player.stack, amount_to_call)
            print(f"- call: Match the current bet (costs {call_cost})")
        if "bet <amount>" in possible_choices_display:
            min_bet_val = allowed_actions.get("bet", {}).get("min", game_state.big_blind)
            max_bet_val = allowed_actions.get("bet", {}).get("max", player.stack)
            print(f"- bet <amount>: Make a bet (e.g., 'bet 50'). Min: {min_bet_val}, Max: {max_bet_val} (your stack)")
        if "raise <total_amount>" in possible_choices_display:
            min_raise_val = allowed_actions.get("raise", {}).get("min_total_bet", game_state.current_bet_to_match + game_state.big_blind)
            max_raise_val = allowed_actions.get("raise", {}).get("max_total_bet", player.current_bet + player.stack)
            print(f"- raise <total_amount>: Raise the current bet (e.g., 'raise 100'). Min total: {min_raise_val}, Max total: {max_raise_val} (all-in)")
        print("------------------------------------------------------------")


        if self.game_mode == "smoke":
            print(f"SMOKE MODE: {player.player_id} auto-acting.")
            if allowed_actions.get("check") and (game_state.current_bet_to_match - player.current_bet) <=0:
                print(f"SMOKE MODE: {player.player_id} auto-checking.")
                return Action(type="check", player_id=player.player_id)
            elif allowed_actions.get("call") and (game_state.current_bet_to_match - player.current_bet) > 0:
                 actual_call_amount = allowed_actions.get("call")
                 if isinstance(actual_call_amount, int) and actual_call_amount > 0 and actual_call_amount <= player.stack :
                    print(f"SMOKE MODE: {player.player_id} auto-calling {actual_call_amount}.")
                    return Action(type="call", amount=actual_call_amount, player_id=player.player_id)
                 elif isinstance(actual_call_amount, int) and actual_call_amount > 0 and actual_call_amount > player.stack and player.stack > 0:
                    print(f"SMOKE MODE: {player.player_id} auto-calling ALL-IN for {player.stack}.")
                    return Action(type="call", amount=player.stack, player_id=player.player_id)
            if allowed_actions.get("fold"):
                print(f"SMOKE MODE: {player.player_id} auto-folding.")
                return Action(type="fold", player_id=player.player_id)
            if allowed_actions:
                first_action_type = list(allowed_actions.keys())[0]
                if first_action_type == "bet" and isinstance(allowed_actions["bet"], dict):
                    return Action(type="bet", amount=allowed_actions["bet"]["min"], player_id=player.player_id)
                elif first_action_type == "raise" and isinstance(allowed_actions["raise"], dict):
                     return Action(type="raise", amount=allowed_actions["raise"]["min_total_bet"], player_id=player.player_id)
                return Action(type="check", player_id=player.player_id)
            else:
                return Action(type="check", player_id=player.player_id)

        # NORMAL MODE: Interactive input loop
        else:
            while True:
                try:
                    choice = input(f"Enter your action for {player.player_id}: ").strip().lower()
                    parts = choice.split()
                    action_type_input = parts[0]

                    action_amount = 0
                    if len(parts) > 1:
                        try:
                            action_amount = int(parts[1])
                        except ValueError:
                            print("Invalid amount. Please enter a number for the amount.")
                            continue

                    # Validate action type
                    if action_type_input not in allowed_actions and not (action_type_input in ["bet", "raise"] and "<amount>" in "".join(possible_choices_display)):
                        print(f"Invalid action type: '{action_type_input}'. Valid actions: {', '.join(possible_choices_display)}")
                        continue

                    # Specific action validation
                    if action_type_input == "fold":
                        if allowed_actions.get("fold"):
                            return Action(type="fold", player_id=player.player_id)
                        else: print("Action 'fold' is not allowed right now.") # Should not happen if listed

                    elif action_type_input == "check":
                        if allowed_actions.get("check") and amount_to_call <=0:
                            return Action(type="check", player_id=player.player_id)
                        else: print("Action 'check' is not allowed (must call or bet is pending).")

                    elif action_type_input == "call":
                        if allowed_actions.get("call") and amount_to_call > 0:
                            call_cost = min(player.stack, amount_to_call) # This is what player.place_bet will take
                            # The amount in Action for call should be the amount_to_call for matching purposes,
                            # player.place_bet will handle if it's an all-in for less.
                            # The 'call' value in allowed_actions IS the correct amount player needs to put in.
                            return Action(type="call", amount=allowed_actions["call"], player_id=player.player_id)
                        else: print("Action 'call' is not allowed or nothing to call.")

                    elif action_type_input == "bet":
                        bet_details = allowed_actions.get("bet")
                        if bet_details and amount_to_call <= 0:
                            if len(parts) < 2: print("Please specify bet amount (e.g., 'bet 50')."); continue
                            min_bet_val = bet_details["min"]
                            max_bet_val = bet_details["max"]
                            if not (min_bet_val <= action_amount <= max_bet_val):
                                print(f"Invalid bet amount. Must be between {min_bet_val} and {max_bet_val}. Your stack: {player.stack}")
                                continue

                            confirm = input(f"Confirm bet {action_amount} chips? (y/n): ").strip().lower()
                            if confirm == 'y':
                                return Action(type="bet", amount=action_amount, player_id=player.player_id)
                            else: print("Bet cancelled."); continue
                        else: print("Action 'bet' is not allowed now (e.g. facing a bet).")

                    elif action_type_input == "raise":
                        raise_details = allowed_actions.get("raise")
                        if raise_details and amount_to_call > 0 :
                            if len(parts) < 2: print("Please specify total amount for raise (e.g., 'raise 100')."); continue
                            min_raise_total = raise_details["min_total_bet"]
                            max_raise_total = raise_details["max_total_bet"]

                            # action_amount is the TOTAL bet player wants to make for the round
                            if not (min_raise_total <= action_amount <= max_raise_total):
                                print(f"Invalid raise amount. Total bet must be between {min_raise_total} and {max_raise_total}. Your stack: {player.stack}")
                                continue

                            # This additional check from before seems correct to ensure it's a valid raise value.
                            if action_amount <= game_state.current_bet_to_match :
                                print(f"Must raise to more than current bet to match ({game_state.current_bet_to_match}).")
                                continue

                            confirm = input(f"Confirm raise to total {action_amount} chips? (y/n): ").strip().lower()
                            if confirm == 'y':
                                return Action(type="raise", amount=action_amount, player_id=player.player_id)
                            else: print("Raise cancelled."); continue
                        else: print("Action 'raise' is not allowed now (e.g. no prior bet to raise).")
                    elif action_type_input in ["quit", "exit"]:
                        confirm_quit = ""
                        try:
                            confirm_quit = input("Are you sure you want to quit the game? (y/n): ").strip().lower()
                        except EOFError:
                            print("\nEOFError during quit confirmation. Assuming 'n'.")
                            confirm_quit = "n" # Default to not quitting if input fails

                        if confirm_quit == 'y':
                            return Action(type="quit", player_id=player.player_id)
                        else:
                            print("Quit cancelled.")
                            continue # Re-prompt for action
                    else:
                        # This case should ideally be caught by the initial action_type_input check
                        print(f"Unrecognized action command: '{action_type_input}'. Valid actions: {', '.join(possible_choices_display)}")

                except EOFError:
                    print("\nEOFError: Input stream ended. This can happen in non-interactive environments.")
                    print("Defaulting to FOLD action for this turn.")
                    if allowed_actions.get("fold"):
                        return Action(type="fold", player_id=player.player_id)
                    else:
                        return Action(type="check", player_id=player.player_id)
                except Exception as e:
                    print(f"An error occurred processing input: {e}. Please try again.")

    def notify_event(self, event: GameEvent, game_state: GameState) -> None:
        # Simplified event notifications, as display_game_state will be the primary view.
        # Outputting key actions for a running log.
        # print(f"DEBUG [EVENT] {event.timestamp.strftime('%H:%M:%S')} - {event.type}: {event.data}") # Keep for debugging if needed

        if event.type == "player_action":
            player_id = event.data.get('player_id', 'UnknownPlayer')
            action_type = event.data.get('action_type', 'unknown_action')
            amount = event.data.get('amount', 0)

            # The check for is_current_human_turn was causing NameError because current_player_id is not in scope here.
            # For now, notify_event will print all actions. display_game_state is the primary view.
            # If suppression of human's own action log is desired, current_player_id would need to be passed to notify_event.

            if action_type == "small_blind":
                print(f"{player_id} posts Small Blind ({amount})")
            elif action_type == "big_blind":
                print(f"{player_id} posts Big Blind ({amount})")
            elif action_type == "fold":
                print(f"{player_id} FOLDS")
            elif action_type == "check":
                print(f"{player_id} CHECKS")
            elif action_type == "call":
                print(f"{player_id} CALLS {amount}")
            elif action_type == "bet":
                print(f"{player_id} BETS {amount}")
            elif action_type == "raise":
                # The 'amount' for a raise action in GameEvent data is the total bet amount.
                print(f"{player_id} RAISES to {amount}")
            # else:
                # print(f"{player_id} performs {action_type} {amount if amount else ''}") # Generic fallback

        elif event.type == "community_cards_dealt":
            # This will be visible in display_game_state. Can add a specific message if desired.
            # print(f"--- {event.data.get('phase', '').upper()} --- Cards: {event.data.get('cards')}")
            pass # display_game_state will show them

        # Other event types can be handled here for specific logging/messages if needed.
        # e.g., "round_start", "phase_start" are now handled by dedicated display methods.

    def display_game_state(self, game_state: GameState, current_player_id: Optional[str] = None, show_hole_cards_for_player: Optional[str] = None) -> None:
        print("\n============================================================")
        print(f"ROUND {game_state.round_number} - {game_state.game_phase.upper()}")
        print("============================================================")

        community_cards_str = " ".join(str(c) for c in game_state.community_cards) if game_state.community_cards else "None"
        print(f"Community: [ {community_cards_str} ]")

        total_pot_display = game_state.pot_size + game_state.current_round_pot
        print(f"💰 Pot: {total_pot_display} chips")

        # Current bet to match for the street (not player's individual current bet for the street)
        # game_state.current_bet_to_match is the highest total bet made by a player on this street.
        # A player needs to at least match this to stay in.
        # "Current bet" in the UI example likely means "bet to call".
        bet_to_call = 0
        if current_player_id:
            player_obj = game_state.get_player_by_id(current_player_id)
            if player_obj:
                bet_to_call = game_state.current_bet_to_match - player_obj.current_bet

        # If no current player, current_bet_to_match is the general high bet.
        # The example "🎯 Current bet: 20" implies the highest bet on the table this round.
        print(f"🎯 Current total bet to match: {game_state.current_bet_to_match}")
        print("\nPlayers:")

        dealer_player_id = game_state.players[game_state.dealer_button_position].player_id

        for p in game_state.players:
            if p.stack == 0 and not p.is_all_in and not p.is_folded and p.current_bet == 0 : # Truly out of game, skip display
                # This condition might need refinement if players can be 0 stack but still all-in from previous street
                # For now, if stack is 0 and they are not part of current action, they are "out".
                # A better way is to filter players for display based on if they played this game round or are still in.
                # For now, let's show all players from game_state.players and mark their status.
                pass


            prefix = ">>> " if p.player_id == current_player_id else "    "

            role_markers = []
            if p.player_id == dealer_player_id:
                role_markers.append("D")
            if p.player_id == game_state.small_blind_player_id:
                role_markers.append("SB")
            if p.player_id == game_state.big_blind_player_id:
                role_markers.append("BB")
            role_str = f" [{', '.join(role_markers)}]" if role_markers else ""

            status_parts = []
            if p.current_bet > 0:
                status_parts.append(f"bet: {p.current_bet}")
            if p.is_folded:
                status_parts.append("FOLDED")
            elif p.is_all_in: # Don't show "bet: X" if all-in, as stack is 0. current_bet is their total commitment.
                status_parts.append("ALL-IN")
                # Remove "bet: X" if already added and player is all-in, to avoid redundancy.
                if f"bet: {p.current_bet}" in status_parts and p.stack == 0 :
                    idx_to_remove = -1
                    for i, part in enumerate(status_parts):
                        if part.startswith("bet:"):
                            idx_to_remove = i
                            break
                    if idx_to_remove != -1 : status_parts.pop(idx_to_remove)


            status_str = f" ({', '.join(status_parts)})" if status_parts else ""

            player_line = f"{prefix}{p.player_id}: {p.stack} chips{role_str}{status_str}"
            print(player_line)

            if p.player_id == show_hole_cards_for_player and p.hole_cards: # Current human player's turn
                 print(f"    🎴 Your cards: {' '.join(str(c) for c in p.hole_cards)}")
            elif game_state.game_phase == "showdown" and not p.is_folded and p.hole_cards: # Showdown phase
                 print(f"    Cards: {' '.join(str(c) for c in p.hole_cards)}")
            # Optionally, for non-current players during non-showdown, show [X X] if you want to indicate they have cards
            # elif p.hole_cards and not p.is_folded :
            #    print(f"    Cards: [X X]")


        print("------------------------------------------------------------")

    def display_round_start(self, game_state: GameState, round_number: int) -> None:
        print(f"\n--- Starting Round {round_number} ---")
        print("==================================================")
        print(f"STARTING ROUND {round_number}")
        print("==================================================")
        # Dealer button display can be part of display_game_state for context
        # Blinds posting messages will come from notify_event for player actions.
        # No longer need to calculate/display SB/BB posters here as GameState will have them for display_game_state.

    def display_player_cards(self, player: Player) -> None:
        if isinstance(player, HumanPlayer): # Only show for human players via this direct call
            print(f"Your cards, {player.player_id}: {[str(c) for c in player.hole_cards] if player.hole_cards else 'None'}")

    def display_winner(self, winners_data: list, game_state: GameState, hand_results: dict) -> None:
        print("\n🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉")
        print("HAND RESULTS")
        print("🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉")

        if not winners_data:
            print("No winners determined (e.g., all folded before showdown).")
        else:
            for winner_info in winners_data:
                player_id = winner_info["player_id"]
                amount_won = winner_info["amount_won"]
                hand_name = winner_info.get("hand_name", "Unknown Hand")
                best_cards = winner_info.get("best_cards", [])

                player = game_state.get_player_by_id(player_id)
                player_display_name = player.player_id if player else player_id

                print(f"🏆 Winner: {player_display_name}")
                if hand_name and hand_name != " uncontested_pot": # Don't show "Unknown Hand" or "uncontested" as hand type here
                    print(f"🃏 Hand: {hand_name} ({' '.join(str(c) for c in best_cards)})")
                print(f"💰 Winnings: {amount_won} chips")
                if player and player.hole_cards and hand_name != " uncontested_pot": # Show winner's hole cards if they had a showdown
                    print(f"   {player_display_name}'s hole cards: {' '.join(str(c) for c in player.hole_cards)}")
                print("------------------------------------------------------------")

        # Display all hands at showdown, including losers
        if game_state.game_phase == "showdown" and len(winners_data) > 0 and winners_data[0].get("hand_name") != " uncontested_pot":
            print("\nShowdown Hands:")
            # Iterate through players who were part of the showdown (not folded)
            # hand_results dict is {player_id: {'hand_name': ..., 'best_cards': ..., ...}}
            for p_id, result in hand_results.items():
                player_obj = game_state.get_player_by_id(p_id)
                if player_obj and not player_obj.is_folded and player_obj.hole_cards: # Ensure player was in showdown
                    is_a_winner = any(w_data["player_id"] == p_id for w_data in winners_data)
                    win_indicator = " (Winner)" if is_a_winner else ""

                    # Only print if it's not the main winner already detailed above, or to add their hole cards if not shown
                    # This logic can be tricky to avoid duplicate display.
                    # Alternative: always list all showdown hands clearly.
                    print(f"  {player_obj.player_id}{win_indicator}:")
                    print(f"    Hole: {' '.join(str(c) for c in player_obj.hole_cards)}")
                    print(f"    Best Hand: {result['hand_name']} ({' '.join(str(c) for c in result['best_cards'])})")
            print("------------------------------------------------------------")

        if self.game_mode == "normal":
            try:
                input("Press Enter to continue...")
            except EOFError: # Handle non-interactive environment for normal mode testing
                print("Auto-continuing (EOFError in normal mode)...")
        else: # Smoke mode
            print("Continuing...") # Or just nothing for smoke mode


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
