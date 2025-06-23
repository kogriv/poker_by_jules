from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import threading
import queue
import logging # Added logging

# Game components will be imported properly in the next step
from poker_game.core.game_engine import GameEngine
from poker_game.interfaces.web_interface import WebInterface
from poker_game.core.player import HumanPlayer, Player # Added Player
from poker_game.core.bot_player import RandomBot, TightBot, AggressiveBot # Added AggressiveBot
from poker_game.core.events import EventSystem
from poker_game.storage.memory_storage import MemoryRepository
from poker_game.config import settings
from poker_game.core.game_state import Action
from typing import Optional # Added Optional


# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder='poker_game/web/templates', static_folder='poker_game/web/static')
app.config['SECRET_KEY'] = 'your_very_secret_key_for_flask_sessions_and_socketio'
socketio = SocketIO(app, async_mode=None, logger=True, engineio_logger=True)

# --- Global Game Management ---
game_engine_instance: Optional[GameEngine] = None
web_interface_instance: Optional[WebInterface] = None
action_queue = queue.Queue()
game_thread: Optional[threading.Thread] = None
game_lock = threading.Lock()

HUMAN_PLAYER_ID = "Player1"

def get_bot_by_type(bot_type_name: str, bot_id: str, stack: int) -> Optional[Player]:
    if bot_type_name == "RandomBot":
        return RandomBot(player_id=bot_id, stack=stack)
    elif bot_type_name == "TightBot":
        return TightBot(player_id=bot_id, stack=stack)
    elif bot_type_name == "AggressiveBot":
        return AggressiveBot(player_id=bot_id, stack=stack)
    logger.warning(f"Unknown bot type: {bot_type_name}")
    return None

def initialize_and_start_game():
    global game_engine_instance, web_interface_instance, game_thread, action_queue

    with game_lock:
        if game_engine_instance is None or (game_thread and not game_thread.is_alive()):
            logger.info("Initializing new game for web interface...")

            event_system = EventSystem()
            repository = MemoryRepository()

            while not action_queue.empty():
                try:
                    action_queue.get_nowait()
                except queue.Empty:
                    break

            web_interface_instance = WebInterface(
                socketio_instance=socketio,
                action_queue=action_queue,
                human_player_id_for_view=HUMAN_PLAYER_ID
            )

            players: List[Player] = [HumanPlayer(player_id=HUMAN_PLAYER_ID, stack=settings.STARTING_STACK)]

            num_bots_to_add = settings.NUM_BOTS
            if settings.BOT_TYPES:
                 for i in range(num_bots_to_add):
                    bot_type_name = settings.BOT_TYPES[i % len(settings.BOT_TYPES)]
                    bot_id = f"{bot_type_name}-{i+1}"
                    bot_player = get_bot_by_type(bot_type_name, bot_id, settings.STARTING_STACK)
                    if bot_player:
                        players.append(bot_player)
            else: # Default to RandomBots if BOT_TYPES is empty
                for i in range(num_bots_to_add):
                    players.append(RandomBot(player_id=f"RandomBot-{i+1}", stack=settings.STARTING_STACK))


            current_game_id = "web_poker_session"

            game_engine_instance = GameEngine(
                players=players,
                interface=web_interface_instance,
                repository=repository,
                event_system=event_system,
                game_id=current_game_id
            )
            # web_interface_instance.set_game_engine(game_engine_instance) # If needed

            logger.info(f"Starting GameEngine in a new thread for game_id: {current_game_id}")
            game_thread = threading.Thread(target=game_engine_instance.start_game, daemon=True)
            game_thread.start()
        else:
            logger.info("Game is already running or thread active.")

@app.route('/')
def index():
    logger.info(f"Route / accessed by {request.remote_addr}")
    if game_engine_instance is None or (game_thread and not game_thread.is_alive()):
         initialize_and_start_game()
    return render_template('game.html', human_player_id=HUMAN_PLAYER_ID)

@app.route('/submit_action', methods=['POST'])
def submit_action_route():
    global action_queue, game_engine_instance, web_interface_instance # web_interface_instance added
    if not game_engine_instance or not game_engine_instance.game_state or game_engine_instance.game_state.is_game_over:
        logger.warning("Action submitted but game is not active.")
        return jsonify({"status": "error", "message": "Game not active or over."}), 400

    data = request.json
    logger.info(f"Received action data via POST: {data}")

    player_id = data.get('player_id')
    action_type = data.get('action_type')
    amount_str = data.get('amount', "0") # Amount might come as string

    if not player_id or not action_type:
        logger.error(f"Missing player_id or action_type in submitted action: {data}")
        return jsonify({"status": "error", "message": "Missing player_id or action_type"}), 400

    if player_id != HUMAN_PLAYER_ID:
        logger.warning(f"Action submitted for non-human player {player_id}. Ignoring.")
        return jsonify({"status": "error", "message": "Action only allowed for designated human player."}), 403

    try:
        action_amount = int(amount_str)
    except ValueError:
        logger.error(f"Invalid amount format for action: {amount_str}")
        return jsonify({"status": "error", "message": "Invalid amount format."}), 400

    game_action = Action(type=action_type, amount=action_amount, player_id=player_id)

    logger.info(f"Putting action onto queue for player {player_id}: {game_action}")
    action_queue.put(game_action)

    return jsonify({"status": "success", "message": "Action received by server."})

# --- SocketIO Event Handlers ---
@socketio.on('connect')
def handle_connect():
    global web_interface_instance # Ensure it's accessible
    logger.info(f'Client connected: {request.sid}')
    if game_engine_instance is None or (game_thread and not game_thread.is_alive()):
        logger.info("Game not running, initializing on connect.")
        initialize_and_start_game()

    # Ensure instance is available before trying to use it
    if web_interface_instance and game_engine_instance and game_engine_instance.game_state:
        logger.info(f"Game in progress, sending current state to new client {request.sid}")
        state_json = web_interface_instance._game_state_to_json(game_engine_instance.game_state, HUMAN_PLAYER_ID)
        emit('game_update', {'game_state': state_json}, room=request.sid)

        gs = game_engine_instance.game_state
        if gs.players and 0 <= gs.current_player_turn_index < len(gs.players):
            current_player_to_act = gs.players[gs.current_player_turn_index]
            if current_player_to_act.player_id == HUMAN_PLAYER_ID and \
               not current_player_to_act.is_folded and \
               not current_player_to_act.is_all_in:
                allowed = game_engine_instance.rules.get_allowed_actions(current_player_to_act, gs)
                payload = {
                    "player_id_to_act": current_player_to_act.player_id,
                    "allowed_actions": allowed,
                    "game_state_for_player": state_json
                }
                logger.info(f"Re-emitting 'request_player_action' to client {request.sid} for player {HUMAN_PLAYER_ID}")
                emit('request_player_action', payload, room=request.sid)
    else:
        logger.info("Game engine or web interface not ready on connect, client may need to request initial state.")


@socketio.on('disconnect')
def handle_disconnect():
    logger.info(f'Client disconnected: {request.sid}')

@socketio.on('request_initial_state')
def handle_request_initial_state():
    global web_interface_instance # Ensure it's accessible
    logger.info(f"Client {request.sid} requested initial state.")
    if web_interface_instance and game_engine_instance and game_engine_instance.game_state:
        state_json = web_interface_instance._game_state_to_json(game_engine_instance.game_state, HUMAN_PLAYER_ID)
        emit('game_update', {'game_state': state_json}, room=request.sid)

        gs = game_engine_instance.game_state
        if gs.players and 0 <= gs.current_player_turn_index < len(gs.players):
            current_player_to_act = gs.players[gs.current_player_turn_index]
            if current_player_to_act.player_id == HUMAN_PLAYER_ID and \
               not current_player_to_act.is_folded and \
               not current_player_to_act.is_all_in:
                allowed = game_engine_instance.rules.get_allowed_actions(current_player_to_act, gs)
                payload = { "player_id_to_act": current_player_to_act.player_id, "allowed_actions": allowed, "game_state_for_player": state_json }
                emit('request_player_action', payload, room=request.sid)
    else:
        logger.info("No active game to send initial state from for request_initial_state.")

if __name__ == '__main__':
    logger.info("Starting Flask-SocketIO server on http://localhost:5000")
    # Game initialization is triggered by the first client connecting or accessing the '/' route.
    try:
        # Use eventlet for async_mode if available, otherwise Flask dev server's default.
        # For production, 'eventlet' or 'gevent' with 'gevent-websocket' is recommended.
        socketio.run(app, host='0.0.0.0', port=5000, debug=True, use_reloader=False, allow_unsafe_werkzeug=True)
    except RuntimeError as e: # Catch common errors like "Eventlet is not installed"
        logger.error(f"RuntimeError starting SocketIO server (maybe eventlet/gevent missing or port in use?): {e}")
        logger.info("Attempting fallback to app.run() without full SocketIO capabilities.")
        app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
    except Exception as e:
        logger.error(f"An unexpected error occurred while starting the server: {e}")
```

**Key changes in this version of `web_server.py`:**
*   Properly imported game components.
*   Added `Optional` type hint.
*   Added more logging.
*   Refined `initialize_and_start_game` to clear the action queue and correctly select bot types.
*   Ensured `web_interface_instance` is globally accessible for `handle_connect` and `handle_request_initial_state`.
*   Added `allow_unsafe_werkzeug=True` to `socketio.run` for newer Werkzeug versions if `debug=True` and `use_reloader=False` causes issues (common in some setups).
*   The call to `initialize_and_start_game()` in `if __name__ == '__main__':` block is commented out because it's better to initialize on first client connection or first access to `/` route to ensure `socketio` object is fully ready. The `index()` route and `handle_connect` now handle this.

Now, retrying the launch.
