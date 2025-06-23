document.addEventListener('DOMContentLoaded', () => {
    const socket = io(); // Connect to Socket.IO server
    const myPlayerId = document.getElementById('my-player-id').textContent;

    // DOM Elements
    const roundNumberEl = document.getElementById('round-number');
    const gamePhaseEl = document.getElementById('game-phase');
    const communityCardsEl = document.getElementById('community-cards-display');
    const potSizeEl = document.getElementById('pot-size');
    const currentBetToMatchEl = document.getElementById('current-bet-to-match');
    const playersAreaEl = document.getElementById('players-area');
    const turnIndicatorEl = document.getElementById('turn-indicator');
    const actionFormEl = document.getElementById('action-form');
    const actionPlayerIdInputEl = document.getElementById('action-player-id'); // Already set by template
    const actionTypeSelectEl = document.getElementById('action-type');
    const amountInputGroupEl = document.getElementById('amount-input-group');
    const actionAmountInputEl = document.getElementById('action-amount');
    const allowedActionsSummaryTextEl = document.getElementById('allowed-actions-summary-text');
    const actionExplanationsTextEl = document.getElementById('action-explanations-text');
    const logListEl = document.getElementById('log-list');

    socket.on('connect', () => {
        console.log('Connected to server. My Player ID:', myPlayerId);
        socket.emit('request_initial_state'); // Ask for current game state
    });

    socket.on('disconnect', () => {
        logMessage('Disconnected from server.');
        turnIndicatorEl.textContent = "Disconnected. Please refresh.";
        actionFormEl.style.display = 'none';
    });

    socket.on('game_update', (data) => {
        console.log('Game Update:', data);
        if (data.game_state) {
            updateGameDisplay(data.game_state);
        }
        if (data.event) {
            logGameEvent(data.event, data.game_state); // Pass game_state for context if needed
        }
    });

    socket.on('request_player_action', (data) => {
        console.log('Request Player Action:', data);
        // Ensure game_state_for_player is used if provided, otherwise use last known game_state
        const currentGameState = data.game_state_for_player || (game_engine_instance ? game_engine_instance.game_state : null);
        if (currentGameState) { // Update display before prompting
            updateGameDisplay(currentGameState);
        }
        if (data.player_id_to_act === myPlayerId) {
            promptPlayerAction(data.player_id_to_act, data.allowed_actions, currentGameState);
        } else {
            actionFormEl.style.display = 'none'; // Not my turn
            turnIndicatorEl.textContent = `Waiting for ${data.player_id_to_act}...`;
        }
    });

    socket.on('round_start_banner', (data) => {
        logMessage(data.message || `--- STARTING ROUND ${data.round_number} ---`, 'event-banner');
    });

    socket.on('round_results', (data) => {
        displayRoundResults(data);
        if (data.game_state_after_win) { // Update to final state of the round
            updateGameDisplay(data.game_state_after_win);
        }
        turnIndicatorEl.textContent = "Round Over. Waiting for next round or game end...";
        actionFormEl.style.display = 'none';
    });

    socket.on('show_message', (data) => {
        logMessage(data.message, 'server-message');
    });

    actionFormEl.addEventListener('submit', function(event) {
        event.preventDefault();
        const actionType = actionTypeSelectEl.value;
        let amount = 0;
        if (actionType === 'bet' || actionType === 'raise') {
            amount = parseInt(actionAmountInputEl.value, 10) || 0;
        }

        const actionPayload = {
            player_id: myPlayerId,
            action_type: actionType,
            amount: amount,
        };

        console.log('Submitting action via POST:', actionPayload);
        fetch('/submit_action', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(actionPayload),
        })
        .then(response => response.json())
        .then(data => {
            console.log('Submit action POST response:', data);
            if (data.status === 'success') {
                actionFormEl.style.display = 'none'; // Hide form, wait for game_update
                turnIndicatorEl.textContent = "Action submitted. Waiting...";
            } else {
                logMessage(`Error: ${data.message}`, 'error');
            }
        })
        .catch((error) => {
            console.error('Error submitting action via POST:', error);
            logMessage('Network error submitting action.', 'error');
        });
    });

    actionTypeSelectEl.addEventListener('change', () => {
        const selectedAction = actionTypeSelectEl.value;
        amountInputGroupEl.style.display = (selectedAction === 'bet' || selectedAction === 'raise') ? 'block' : 'none';
        actionAmountInputEl.placeholder = selectedAction === 'bet' ? 'Bet amount' : 'Total amount for raise';
    });

    function updateGameDisplay(gameState) {
        if (!gameState || Object.keys(gameState).length === 0) {
            console.warn("updateGameDisplay called with empty or null gameState");
            return;
        }

        roundNumberEl.textContent = gameState.round_number || 'N/A';
        gamePhaseEl.textContent = gameState.game_phase || 'N/A';
        communityCardsEl.textContent = gameState.community_cards && gameState.community_cards.length > 0 ?
                                       gameState.community_cards.map(c => `${c.rank}${c.suit}`).join(' ') : '[ ]';
        potSizeEl.textContent = gameState.pot_size || '0';
        currentBetToMatchEl.textContent = gameState.current_bet_to_match || '0';

        // Display human player's cards if available (moved from player loop for prominence)
        const humanPlayerState = gameState.players.find(p => p.player_id === myPlayerId);
        const humanCardsArea = document.getElementById('human-player-cards-area'); // Assuming you add this div
        if (humanCardsArea) { // Clear it first
            humanCardsArea.innerHTML = '';
        }
        if (humanPlayerState && humanPlayerState.hole_cards && humanPlayerState.hole_cards.length > 0 && humanPlayerState.hole_cards[0] !== "HIDDEN") {
            const cardsText = humanPlayerState.hole_cards.map(c => `${c.rank}${c.suit}`).join(' ');
            if (humanCardsArea) humanCardsArea.innerHTML = `<h3>🂡 Your cards: ${cardsText}</h3>`;
            else logMessage(`Your cards: ${cardsText}`); // Fallback if dedicated area not found
        } else if (humanPlayerState && humanPlayerState.is_folded) {
            if (humanCardsArea) humanCardsArea.innerHTML = `<h3>🂡 Your cards: [ FOLDED ]</h3>`;
        } else if (humanPlayerState && humanPlayerState.hole_cards && humanPlayerState.hole_cards[0] === "HIDDEN") {
             if (humanCardsArea) humanCardsArea.innerHTML = `<h3>🂡 Your cards: [ X X ]</h3>`;
        }


        playersAreaEl.innerHTML = ''; // Clear previous player info
        gameState.players.forEach(player => {
            const playerDiv = document.createElement('div');
            playerDiv.className = 'player-info';
            playerDiv.id = `player-${player.player_id}`;
            if (player.player_id === gameState.current_player_turn_id) {
                playerDiv.classList.add('current-turn');
            }

            let roles = [];
            if(player.is_dealer) roles.push("D");
            if(player.is_sb) roles.push("SB");
            if(player.is_bb) roles.push("BB");
            const roleStr = roles.length > 0 ? ` <span class="player-role-indicator">[${roles.join(',')}]</span>` : "";

            let statusText = "";
            if(player.is_folded) statusText = "(FOLDED)";
            else if(player.is_all_in) statusText = "(ALL-IN)";

            let betInfo = "";
            if(player.current_bet > 0 && !player.is_all_in) betInfo = `Bet: ${player.current_bet}`;
            else if (player.is_all_in && player.current_bet > 0) betInfo = `Committed: ${player.current_bet}`;


            let cardsDisplay = "[ ]";
            if (player.hole_cards) {
                if (player.hole_cards[0] === "HIDDEN") {
                    cardsDisplay = "[ X X ]";
                } else {
                    cardsDisplay = `[ ${player.hole_cards.map(c => `${c.rank}${c.suit}`).join(' ')} ]`;
                }
            }

            const playerPrefix = player.player_id === gameState.current_player_turn_id ? ">>> " : "";

            playerDiv.innerHTML = `
                <h3 class="player-name">${playerPrefix}${player.player_id}${roleStr}</h3>
                <div class="player-cards">${cardsDisplay}</div>
                <p>Stack: <span class="player-stack">${player.stack}</span></p>
                ${betInfo ? `<p class="player-bet-this-street">${betInfo}</p>` : ''}
                ${statusText ? `<p class="player-status-text">${statusText}</p>` : ''}
            `;
            playersAreaEl.appendChild(playerDiv);
        });

        if (gameState.current_player_turn_id === myPlayerId && !gameState.is_game_over) {
            turnIndicatorEl.textContent = "Your Turn!";
            // Action form enabling is handled by 'request_player_action'
        } else if (gameState.current_player_turn_id) {
            turnIndicatorEl.textContent = `Waiting for ${gameState.current_player_turn_id}...`;
            actionFormEl.style.display = 'none';
        } else if (gameState.is_game_over) {
            turnIndicatorEl.textContent = "Game Over.";
            actionFormEl.style.display = 'none';
        }
    }

    function promptPlayerAction(playerId, allowedActions, currentGameState) {
        actionFormEl.style.display = 'block';
        actionPlayerIdInputEl.value = playerId; // Should be myPlayerId

        actionTypeSelectEl.innerHTML = ''; // Clear old options
        allowedActionsSummaryTextEl.textContent = '';
        actionExplanationsTextEl.innerHTML = '';

        let possibleChoices = [];
        const playerState = currentGameState.players.find(p => p.player_id === playerId);
        const amountToCall = currentGameState.current_bet_to_match - (playerState?.current_bet || 0);

        if (allowedActions.fold) {
            actionTypeSelectEl.add(new Option("Fold", "fold"));
            possibleChoices.push("fold");
            actionExplanationsTextEl.innerHTML += "<p>- fold: Give up your hand</p>";
        }
        if (allowedActions.check) {
            actionTypeSelectEl.add(new Option("Check", "check"));
            possibleChoices.push("check");
            actionExplanationsTextEl.innerHTML += "<p>- check: Pass without betting</p>";
        }
        if (allowedActions.call) {
            const callAmount = allowedActions.call;
            actionTypeSelectEl.add(new Option(`Call (${callAmount})`, "call"));
            possibleChoices.push("call");
            actionExplanationsTextEl.innerHTML += `<p>- call: Match current bet (costs ${callAmount})</p>`;
        }
        if (allowedActions.bet && allowedActions.bet.min !== undefined) { // Check if bet details exist
            actionTypeSelectEl.add(new Option("Bet", "bet"));
            possibleChoices.push("bet");
            actionExplanationsTextEl.innerHTML += `<p>- bet &lt;amount&gt;: Min ${allowedActions.bet.min}, Max ${allowedActions.bet.max}</p>`;
        }
        if (allowedActions.raise && allowedActions.raise.min_total_bet !== undefined) { // Check if raise details exist
            actionTypeSelectEl.add(new Option("Raise", "raise"));
            possibleChoices.push("raise");
            actionExplanationsTextEl.innerHTML += `<p>- raise &lt;total_amount&gt;: Min total ${allowedActions.raise.min_total_bet}, Max total ${allowedActions.raise.max_total_bet}</p>`;
        }
        allowedActionsSummaryTextEl.textContent = possibleChoices.join(', ');
        actionTypeSelectEl.dispatchEvent(new Event('change')); // Trigger change to update amount input visibility
    }

    function logGameEvent(event, gameState) { // gameState might be useful for context
        const item = document.createElement('li');
        let message = ``; // No [EVENT] prefix for cleaner log
        if (event.type === 'player_action') {
            const pId = event.data.player_id;
            const actionType = event.data.action_type;
            const amount = event.data.amount;
            message = `${pId} ${actionType.toUpperCase()}`;
            if (actionType === 'call' || actionType === 'bet') {
                message += ` ${amount}`;
            } else if (actionType === 'raise') {
                message += ` to ${amount}`;
            } else if (action_type === 'small_blind' || action_type === 'big_blind'){
                 message = `${pId} posts ${actionType.replace('_',' ')} (${amount})`;
            }
        } else if (event.type === 'community_cards_dealt') {
            message = `--- ${event.data.phase.toUpperCase()} --- Community: ${event.data.cards.join(' ')}`;
        } else if (event.type === 'phase_start') {
            message = `--- PHASE: ${event.data.phase.toUpperCase()} ---`;
        } else if (event.type === 'game_start'){
            message = `Game started with ${event.data.num_players} players.`;
        } else {
            // Generic log for other events, or ignore them
            // message = `${event.type}: ${JSON.stringify(event.data)}`;
            return; // Don't log everything by default
        }
        item.textContent = message;
        logListEl.appendChild(item);
        logListEl.scrollTop = logListEl.scrollHeight; // Scroll to bottom
        if (logListEl.children.length > 30) { logListEl.removeChild(logListEl.firstChild); }
    }

    function logMessage(message, type = 'info') { // type can be 'info', 'error', 'event-banner'
        const item = document.createElement('li');
        item.className = `log-${type}`;
        item.textContent = message;
        logListEl.appendChild(item);
        logListEl.scrollTop = logListEl.scrollHeight;
        if (logListEl.children.length > 30) { logListEl.removeChild(logListEl.firstChild); }
    }

    function displayRoundResults(data) {
        logMessage("🎉 HAND RESULTS 🎉", "event-banner");
        if (!data.winners_data || data.winners_data.length === 0) {
            logMessage("No winners determined.");
        } else {
            data.winners_data.forEach(winner => {
                let winMsg = `🏆 Winner: ${winner.player_id}, Winnings: ${winner.amount_won} chips`;
                if (winner.hand_name && winner.hand_name !== " uncontested_pot") {
                    winMsg += `, Hand: ${winner.hand_name} (${winner.best_cards.map(c=>c.rank+c.suit).join(' ')})`;
                }
                logMessage(winMsg);
            });
        }
        // Showdown hands are now part of the main game_state update for simplicity on client
        // if (data.hand_results && Object.keys(data.hand_results).length > 0) {
        //     logMessage("--- Showdown Hands ---", "event-banner");
        //     for (const [playerId, result] of Object.entries(data.hand_results)) {
        //         // Player's hole cards will be visible in the main player display if it's showdown
        //         logMessage(`${playerId}: ${result.hand_name} (${result.best_cards.map(c=>c.rank+c.suit).join(' ')})`);
        //     }
        // }
        logMessage("Press Enter or wait for next round...", "info"); // Placeholder for actual continue mechanism
    }
});

```
