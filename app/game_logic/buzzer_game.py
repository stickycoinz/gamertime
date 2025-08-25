"""
Simple Buzzer Board Game Logic for Live Trivia
Perfect for reading questions aloud and tracking buzz order
"""
import asyncio
import time
from typing import Dict, List, Optional, Set
from app.schemas.game_schemas import BuzzerGameState, Player, ScoreCard, GameResults
from app.utils.storage import storage

# Active buzzer games
active_buzzer_games: Dict[str, "BuzzerGame"] = {}

class BuzzerGame:
    def __init__(self, room_code: str):
        self.room_code = room_code
        self.state = BuzzerGameState()
    
    async def start_game(self, players: List[Player]) -> None:
        """Start a new buzzer game session"""
        self.state.is_active = True
        self.state.round_number = 0
        
        # Initialize scores for all players
        for player in players:
            self.state.scores[player.player_id] = 0
        
        # Broadcast game start
        await storage.publish(self.room_code, "game_started", {
            "game_type": "buzzer",
            "message": "Buzzer Board Active! Get ready to buzz in!",
            "players": [{"player_id": p.player_id, "name": p.name} for p in players]
        })
        
        # Start first round automatically
        await self.new_round()
    
    async def new_round(self) -> None:
        """Start a new buzzer round"""
        if not self.state.is_active:
            return
        
        # Increment round counter
        self.state.round_number += 1
        
        # Reset round state
        self.state.already_buzzed.clear()
        self.state.buzz_times.clear()
        self.state.round_start_time = time.time()
        self.state.buzzer_status = "disabled"  # Buzzers start disabled
        self.state.buzzer_live_time = None
        self.state.countdown_start_time = None
        
        # Broadcast new round
        await storage.publish(self.room_code, "new_round", {
            "round_number": self.state.round_number,
            "message": f"Round {self.state.round_number} - Host will activate buzzers",
            "buzzer_status": "disabled",
            "scores": self.state.scores
        })
        
        # Clear buzzer table on frontend
        await storage.publish(self.room_code, "buzzer_cleared", {
            "message": f"Round {self.state.round_number} - Waiting for host to activate buzzers"
        })
    
    async def buzzer_live(self) -> None:
        """Start the 3-second countdown and activate buzzers (host only)"""
        if not self.state.is_active or self.state.buzzer_status != "disabled":
            return
        
        # Start countdown
        self.state.buzzer_status = "countdown"
        self.state.countdown_start_time = time.time()
        
        # Notify host of countdown start (players don't see this)
        await storage.publish(self.room_code, "buzzer_countdown_start", {
            "countdown_duration": 3,
            "message": "Buzzer countdown started..."
        })
        
        # Start countdown task
        asyncio.create_task(self._run_buzzer_countdown())
    
    async def _run_buzzer_countdown(self) -> None:
        """Run the 3-second countdown then activate buzzers"""
        try:
            # 3-second countdown with host updates
            for i in range(3, 0, -1):
                await storage.publish(self.room_code, "buzzer_countdown_tick", {
                    "countdown": i,
                    "message": f"Buzzers live in {i}..."
                })
                await asyncio.sleep(1)
            
            # Activate buzzers
            self.state.buzzer_status = "live"
            self.state.buzzer_live_time = time.time()
            
            # Notify everyone buzzers are live
            await storage.publish(self.room_code, "buzzers_live", {
                "message": "Buzzers are LIVE!",
                "buzzer_status": "live"
            })
            
        except asyncio.CancelledError:
            # Countdown was cancelled
            pass

    async def handle_buzz(self, player_id: str) -> bool:
        """Handle player buzz attempt with anti-cheat validation"""
        if not self.state.is_active:
            return False
        
        # ANTI-CHEAT: Only allow buzzes when buzzers are live
        if self.state.buzzer_status != "live":
            # Log potential cheating attempt
            print(f"Anti-cheat: Player {player_id} tried to buzz when buzzers not live (status: {self.state.buzzer_status})")
            await storage.publish(self.room_code, "buzz_blocked", {
                "player_id": player_id,
                "message": "Buzzers are not live yet!",
                "reason": "early_buzz"
            })
            return False
        
        # Check if player already buzzed this round
        if player_id in self.state.already_buzzed:
            return False
        
        # Add player to buzzed list
        self.state.already_buzzed.add(player_id)
        
        # Get player name
        lobby = await storage.get_lobby(self.room_code)
        player_name = next(
            (p["name"] for p in lobby["players"] if p["player_id"] == player_id),
            player_id
        )
        
        # Track buzz time and calculate difference
        buzz_time = time.time()
        time_since_live = buzz_time - (self.state.buzzer_live_time or buzz_time)  # Time since buzzers went live
        
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
            "time_since_live": time_since_live * 1000,  # Convert to ms (time since buzzers went live)
            "time_diff": time_diff,
            "position": len(self.state.buzz_times) + 1
        }
        self.state.buzz_times.append(buzz_info)
        
        # Broadcast buzz with timing info
        await storage.publish(self.room_code, "player_buzzed", {
            "player_id": player_id,
            "player_name": player_name,
            "position": buzz_info["position"],
            "total_buzzed": len(self.state.already_buzzed),
            "buzz_time": buzz_time,
            "time_since_live": time_since_live * 1000,  # Time since buzzers went live
            "time_diff": time_diff,
            "buzz_table": self.state.buzz_times,  # Send full table for UI
            "message": f"{player_name} buzzed in #{buzz_info['position']} ({int(time_since_live * 1000)}ms)!"
        })
        
        return True
    
    async def award_points(self, player_id: str, points: int) -> bool:
        """Manually award points to a player (host controlled)"""
        if not self.state.is_active:
            return False
        
        # Ensure player exists in scores
        if player_id not in self.state.scores:
            self.state.scores[player_id] = 0
        
        # Award points
        self.state.scores[player_id] += points
        
        # Get player name
        lobby = await storage.get_lobby(self.room_code)
        player_name = next(
            (p["name"] for p in lobby["players"] if p["player_id"] == player_id),
            player_id
        )
        
        # Broadcast point award
        await storage.publish(self.room_code, "points_awarded", {
            "player_id": player_id,
            "player_name": player_name,
            "points_awarded": points,
            "new_total": self.state.scores[player_id],
            "scores": self.state.scores,
            "message": f"{player_name} awarded {points} points!"
        })
        
        return True
    
    async def get_game_state(self) -> Dict:
        """Get current game state for broadcasting"""
        return {
            "game_type": "buzzer",
            "round_number": self.state.round_number,
            "is_active": self.state.is_active,
            "buzz_times": self.state.buzz_times,
            "scores": self.state.scores,
            "total_buzzed": len(self.state.already_buzzed)
        }
    
    async def end_game(self) -> None:
        """End the buzzer game and show final results"""
        self.state.is_active = False
        
        # Calculate final results
        sorted_scores = sorted(
            self.state.scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # Get player names
        lobby = await storage.get_lobby(self.room_code)
        final_results = []
        for player_id, score in sorted_scores:
            player = next(
                (p for p in lobby["players"] if p["player_id"] == player_id),
                None
            )
            if player:
                final_results.append({
                    "player_id": player_id,
                    "player_name": player["name"],
                    "score": score,
                    "rank": len(final_results) + 1
                })
        
        # Broadcast final results
        await storage.publish(self.room_code, "game_finished", {
            "game_type": "buzzer",
            "winner": final_results[0] if final_results else None,
            "final_scores": final_results,
            "total_rounds": self.state.round_number,
            "message": f"Buzzer Game Complete! {final_results[0]['player_name'] if final_results else 'No winner'} wins!"
        })
    
    async def stop_game(self) -> None:
        """Force stop the game"""
        self.state.is_active = False
        await storage.publish(self.room_code, "game_stopped", {
            "message": "Buzzer game stopped by host"
        })
