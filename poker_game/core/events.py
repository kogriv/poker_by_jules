from dataclasses import dataclass
from datetime import datetime
from typing import Any # Changed from dict to Any for more flexibility in event data

@dataclass
class GameEvent:
    type: str  # "round_start", "player_action", "cards_dealt", etc.
    data: Any # Changed from dict to Any
    timestamp: datetime = None # Added default None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

@dataclass
class Action:
    type: str  # "fold", "check", "call", "bet", "raise"
    amount: int = 0
    player_id: str = ""

class EventSystem:
    def __init__(self):
        self._subscribers = []

    def subscribe(self, callback):
        self._subscribers.append(callback)

    def post(self, event: GameEvent):
        for subscriber in self._subscribers:
            subscriber(event)
