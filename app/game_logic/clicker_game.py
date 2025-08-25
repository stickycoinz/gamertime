"""
Clicker Challenge Game Logic - 10-second button-mash race
"""
import asyncio
from typing import Dict, List
from datetime import datetime, timedelta
from app.schemas.game_schemas import ClickerGameState, Player, ScoreCard, GameResults
from app.utils.storage import storage

class ClickerGame:
    """Manages clicker game state and logic"""
    
    def __init__(self, room_code: str, duration: int = 10):
        self.room_code = room_code
        self.duration = duration
        self.state = ClickerGameState(duration=duration)
        self.start_time: datetime = None
        self.timer_task: asyncio.Task = None
    
    async def start_game(self, players: List[Player]) -> None:
        """Initialize and start the clicker game"""
        # Initialize scores for all players
        self.state.scores = {player.player_id: 0 for player in players}
        self.state.is_active = True
        self.state.time_remaining = self.duration
        self.start_time = datetime.now()
        
        # Broadcast game start
        await storage.publish(self.room_code, "game_started", {
            "game_type": "clicker",
            "duration": self.duration,
            "message": f"Clicker Challenge started! Tap as fast as you can for {self.duration} seconds!"
        })
        
        # Start countdown timer
        self.timer_task = asyncio.create_task(self._run_timer())
    
    async def handle_click(self, player_id: str) -> bool:
        """Process a player click, return True if valid"""
        if not self.state.is_active:
            return False
        
        if player_id not in self.state.scores:
            return False
        
        # Increment click count
        self.state.scores[player_id] += 1
        
        # Broadcast click update
        await storage.publish(self.room_code, "click_registered", {
            "player_id": player_id,
            "count": self.state.scores[player_id],
            "scores": self.state.scores
        })
        
        return True
    
    async def _run_timer(self) -> None:
        """Run the game countdown timer"""
        try:
            for remaining in range(self.duration, 0, -1):
                self.state.time_remaining = remaining
                
                # Broadcast tick every second
                await storage.publish(self.room_code, "tick", {
                    "time_remaining": remaining,
                    "scores": self.state.scores
                })
                
                await asyncio.sleep(1)
            
            # Game finished
            await self._end_game()
            
        except asyncio.CancelledError:
            # Game was cancelled
            self.state.is_active = False
    
    async def _end_game(self) -> None:
        """End the game and calculate results"""
        self.state.is_active = False
        self.state.time_remaining = 0
        
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
            game_type="clicker",
            scores=score_cards,
            duration=self.duration,
            completed_at=datetime.now()
        )
        
        # Broadcast final results
        await storage.publish(self.room_code, "game_finished", {
            "results": results.model_dump(),
            "winner": score_cards[0].model_dump() if score_cards else None,
            "message": f"🎉 {score_cards[0].name} wins with {score_cards[0].score} clicks!" if score_cards else "Game finished!"
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
active_games: Dict[str, ClickerGame] = {}
