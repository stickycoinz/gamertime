"""
Trivia Game Logic with questions and buzzer system
"""
import asyncio
import time
from typing import Dict, List, Optional
from datetime import datetime
from app.schemas.game_schemas import TriviaGameState, TriviaQuestion, Player, ScoreCard, GameResults
from app.utils.storage import storage

# Sample trivia questions
SAMPLE_QUESTIONS = [
    {
        "question_id": "q1",
        "question": "What is the capital of France?",
        "options": ["London", "Berlin", "Paris", "Madrid"],
        "correct_answer": 2
    },
    {
        "question_id": "q2", 
        "question": "Which planet is known as the Red Planet?",
        "options": ["Venus", "Mars", "Jupiter", "Saturn"],
        "correct_answer": 1
    },
    {
        "question_id": "q3",
        "question": "Who painted the Mona Lisa?",
        "options": ["Van Gogh", "Picasso", "Da Vinci", "Monet"],
        "correct_answer": 2
    },
    {
        "question_id": "q4",
        "question": "What is the largest ocean on Earth?",
        "options": ["Atlantic", "Indian", "Arctic", "Pacific"],
        "correct_answer": 3
    },
    {
        "question_id": "q5",
        "question": "In which year did World War II end?",
        "options": ["1944", "1945", "1946", "1947"],
        "correct_answer": 1
    }
]

class TriviaGame:
    """Manages trivia game state and buzzer logic"""
    
    def __init__(self, room_code: str):
        self.room_code = room_code
        self.state = TriviaGameState()
        self.questions = [TriviaQuestion(**q) for q in SAMPLE_QUESTIONS]
        self.timer_task: Optional[asyncio.Task] = None
    
    async def start_game(self, players: List[Player]) -> None:
        """Initialize and start the trivia game"""
        # Initialize scores for all players
        self.state.scores = {player.player_id: 0 for player in players}
        self.state.is_active = True
        self.state.question_number = 0
        
        # Broadcast game start
        await storage.publish(self.room_code, "game_started", {
            "game_type": "trivia",
            "total_questions": self.state.total_questions,
            "message": f"Trivia game started! {self.state.total_questions} questions ahead. First to buzz in wins!"
        })
        
        # Start first question
        await self._next_question()
    
    async def _next_question(self) -> None:
        """Present the next question"""
        if self.state.question_number >= len(self.questions):
            await self._end_game()
            return
        
        # Reset round state
        self.state.round_locked = False
        self.state.already_answered = set()
        self.state.answers = {}
        self.state.buzz_times = []  # Clear buzz times
        self.state.question_start_time = time.time()  # Track when question starts
        
        # Get current question
        self.state.current_question = self.questions[self.state.question_number]
        self.state.time_remaining = self.state.current_question.time_limit
        
        # Broadcast new question
        await storage.publish(self.room_code, "new_question", {
            "question_number": self.state.question_number + 1,
            "total_questions": len(self.questions),
            "question": self.state.current_question.question,
            "options": self.state.current_question.options,
            "time_limit": self.state.current_question.time_limit
        })
        
        # Clear buzzers for new question
        await storage.publish(self.room_code, "buzzer_cleared", {
            "message": "Buzzers ready for next question!"
        })
        
        # Start question timer
        self.timer_task = asyncio.create_task(self._run_question_timer())
    
    async def handle_buzz(self, player_id: str) -> bool:
        """Handle player buzz attempt - FIXED: No lockout, accept all buzzes"""
        if not self.state.is_active or not self.state.current_question:
            return False
        
        # Check if player already buzzed this round
        if player_id in self.state.already_answered:
            return False
        
        # Add player to buzzed list (NO LOCKOUT - accept all buzzes)
        self.state.already_answered.add(player_id)
        
        # Get player name
        lobby = await storage.get_lobby(self.room_code)
        player_name = next(
            (p["name"] for p in lobby["players"] if p["player_id"] == player_id),
            player_id
        )
        
        # Track buzz time and calculate difference
        buzz_time = time.time()
        time_since_question = buzz_time - (self.state.question_start_time or buzz_time)
        
        # Calculate difference from first buzz
        time_diff = None
        if len(self.state.buzz_times) > 0:
            first_buzz_time = self.state.buzz_times[0]["buzz_time"]
            time_diff = (buzz_time - first_buzz_time) * 1000  # Convert to milliseconds
        
        # Store buzz info
        buzz_info = {
            "player_id": player_id,
            "player_name": player_name,
            "buzz_time": buzz_time,
            "time_since_question": time_since_question * 1000,  # Convert to ms
            "time_diff": time_diff,
            "position": len(self.state.buzz_times) + 1
        }
        self.state.buzz_times.append(buzz_info)
        
        # Get buzz position
        position = len(self.state.already_answered)
        
        # Broadcast buzz with timing info (NO LOCKOUT)
        await storage.publish(self.room_code, "player_buzzed", {
            "player_id": player_id,
            "player_name": player_name,
            "position": position,
            "total_buzzed": len(self.state.already_answered),
            "buzz_time": buzz_time,
            "time_since_question": time_since_question * 1000,
            "time_diff": time_diff,
            "buzz_table": self.state.buzz_times,  # Send full table for UI
            "message": f"{player_name} buzzed in #{position}!"
        })
        
        return True
    
    async def handle_answer(self, player_id: str, answer_index: int) -> bool:
        """Handle player answer submission"""
        if not self.state.is_active or not self.state.current_question:
            return False
        
        # Only the player who buzzed can answer
        if not self.state.round_locked or player_id not in self.state.already_answered:
            return False
        
        # Record answer
        self.state.answers[player_id] = answer_index
        
        # Check if correct
        is_correct = answer_index == self.state.current_question.correct_answer
        
        if is_correct:
            # Award points (more points for faster answers)
            points = max(100 - (self.state.current_question.time_limit - self.state.time_remaining) * 5, 50)
            self.state.scores[player_id] += points
        
        # Get player name and correct answer text
        lobby = await storage.get_lobby(self.room_code)
        player_name = next(
            (p["name"] for p in lobby["players"] if p["player_id"] == player_id),
            player_id
        )
        correct_answer_text = self.state.current_question.options[self.state.current_question.correct_answer]
        
        # Broadcast answer result
        await storage.publish(self.room_code, "answer_result", {
            "player_id": player_id,
            "player_name": player_name,
            "answer_index": answer_index,
            "is_correct": is_correct,
            "correct_answer": self.state.current_question.correct_answer,
            "correct_answer_text": correct_answer_text,
            "points_awarded": points if is_correct else 0,
            "scores": self.state.scores
        })
        
        # Move to next question after delay
        await asyncio.sleep(3)
        self.state.question_number += 1
        await self._next_question()
        
        return True
    
    async def _run_question_timer(self) -> None:
        """Run the question countdown timer"""
        try:
            while self.state.time_remaining > 0:
                # Broadcast tick
                await storage.publish(self.room_code, "tick", {
                    "time_remaining": self.state.time_remaining,
                    "question_number": self.state.question_number + 1
                })
                
                await asyncio.sleep(1)
                self.state.time_remaining -= 1
            
            # Time up - move to next question
            if self.state.is_active:
                await storage.publish(self.room_code, "time_up", {
                    "correct_answer": self.state.current_question.correct_answer,
                    "correct_answer_text": self.state.current_question.options[self.state.current_question.correct_answer],
                    "message": "Time's up! Moving to next question..."
                })
                
                await asyncio.sleep(2)
                self.state.question_number += 1
                await self._next_question()
                
        except asyncio.CancelledError:
            # Timer was cancelled
            pass
    
    async def _end_game(self) -> None:
        """End the game and calculate results"""
        self.state.is_active = False
        
        # Calculate final scores and rankings
        sorted_scores = sorted(
            self.state.scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # Create score cards
        score_cards = []
        for rank, (player_id, score) in enumerate(sorted_scores, 1):
            # Get player name from lobby
            lobby = await storage.get_lobby(self.room_code)
            player_name = next(
                (p["name"] for p in lobby["players"] if p["player_id"] == player_id),
                player_id
            )
            
            score_cards.append(ScoreCard(
                player_id=player_id,
                name=player_name,
                score=score,
                rank=rank
            ))
        
        # Create game results
        results = GameResults(
            game_type="trivia",
            scores=score_cards,
            completed_at=datetime.now()
        )
        
        # Broadcast final results
        await storage.publish(self.room_code, "game_finished", {
            "results": results.model_dump(),
            "winner": score_cards[0].model_dump() if score_cards else None,
            "message": f"🧠 {score_cards[0].name} wins with {score_cards[0].score} points!" if score_cards else "Game finished!"
        })
        
        # Update lobby status
        lobby = await storage.get_lobby(self.room_code)
        if lobby:
            lobby["status"] = "finished"
            lobby["game_results"] = results.model_dump()
            await storage.save_lobby(self.room_code, lobby)
    
    async def stop_game(self) -> None:
        """Force stop the game"""
        if self.timer_task:
            self.timer_task.cancel()
        self.state.is_active = False
        
        await storage.publish(self.room_code, "game_stopped", {
            "message": "Game was stopped by host"
        })

# Global game instances
active_trivia_games: Dict[str, TriviaGame] = {}
