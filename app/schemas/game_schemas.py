"""
Game-specific Pydantic schemas for request/response validation
"""
from typing import Dict, List, Optional, Union, Literal
from pydantic import BaseModel, Field
from datetime import datetime

# Base Models
class PlayerBase(BaseModel):
    player_id: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=30)

class Player(PlayerBase):
    is_ready: bool = False
    is_host: bool = False
    connected: bool = True
    joined_at: datetime

# Lobby Models
class LobbyCreate(BaseModel):
    host_name: str = Field(..., min_length=1, max_length=30)
    game_type: Literal["clicker", "trivia"] = "clicker"
    custom_room_code: Optional[str] = Field(None, min_length=4, max_length=6)

class LobbyResponse(BaseModel):
    room_code: str
    host_player_id: str
    game_type: str
    status: Literal["waiting", "starting", "active", "finished"]
    players: List[Player]
    created_at: datetime

class JoinLobby(BaseModel):
    room_code: str = Field(..., min_length=4, max_length=6)
    player_name: str = Field(..., min_length=1, max_length=30)

# Game State Models
class ClickerGameState(BaseModel):
    game_type: Literal["clicker"] = "clicker"
    duration: int = 10  # seconds
    scores: Dict[str, int] = {}  # player_id -> click_count
    time_remaining: Optional[int] = None
    is_active: bool = False

class TriviaQuestion(BaseModel):
    question_id: str
    question: str
    options: List[str]
    correct_answer: int  # index of correct option
    time_limit: int = 30  # seconds

class TriviaGameState(BaseModel):
    game_type: Literal["trivia"] = "trivia"
    current_question: Optional[TriviaQuestion] = None
    question_number: int = 0
    total_questions: int = 5
    scores: Dict[str, int] = {}  # player_id -> total_score
    answers: Dict[str, int] = {}  # player_id -> answer_index
    time_remaining: Optional[int] = None
    is_active: bool = False
    round_locked: bool = False
    already_answered: set[str] = set()

GameState = Union[ClickerGameState, TriviaGameState]

# WebSocket Message Models
class WSMessage(BaseModel):
    type: str
    data: Dict

class PlayerAction(BaseModel):
    action: Literal["ready", "unready", "click", "answer", "buzz"]
    data: Optional[Dict] = {}

class GameAction(BaseModel):
    action: Literal["start_game", "next_question", "end_game"]
    data: Optional[Dict] = {}

# Score Display
class ScoreCard(BaseModel):
    player_id: str
    name: str
    score: int
    rank: int

class GameResults(BaseModel):
    game_type: str
    scores: List[ScoreCard]
    duration: Optional[int] = None  # game duration in seconds
    completed_at: datetime
