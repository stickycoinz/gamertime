"""
Storage interface and in-memory implementation for lobby/player state
"""
import asyncio
from typing import Dict, List, Optional, Set
from datetime import datetime, timedelta
import random
import string
from app.schemas.game_schemas import Player, LobbyResponse, GameState

class Storage:
    """Abstract storage interface for horizontal scaling"""
    
    async def get_lobby(self, room_code: str) -> Optional[Dict]:
        raise NotImplementedError
    
    async def save_lobby(self, room_code: str, lobby_data: Dict) -> None:
        raise NotImplementedError
    
    async def list_lobbies(self) -> List[str]:
        raise NotImplementedError
    
    async def upsert_player(self, room_code: str, player: Player) -> None:
        raise NotImplementedError
    
    async def remove_player(self, room_code: str, player_id: str) -> None:
        raise NotImplementedError
    
    async def publish(self, room_code: str, event: str, data: Dict) -> None:
        raise NotImplementedError

class InMemoryStorage(Storage):
    """In-memory implementation with asyncio.Lock for concurrency"""
    
    def __init__(self):
        self.lobbies: Dict[str, Dict] = {}
        self.connections: Dict[str, Set] = {}  # room_code -> set of websocket connections
        self.locks: Dict[str, asyncio.Lock] = {}
        self.cleanup_tasks: Dict[str, asyncio.Task] = {}
    
    def _get_lock(self, room_code: str) -> asyncio.Lock:
        """Get or create lock for room"""
        if room_code not in self.locks:
            self.locks[room_code] = asyncio.Lock()
        return self.locks[room_code]
    
    async def get_lobby(self, room_code: str) -> Optional[Dict]:
        return self.lobbies.get(room_code)
    
    async def save_lobby(self, room_code: str, lobby_data: Dict) -> None:
        async with self._get_lock(room_code):
            self.lobbies[room_code] = lobby_data
            
            # Schedule cleanup if lobby is finished
            if lobby_data.get("status") == "finished":
                self._schedule_cleanup(room_code)
    
    async def list_lobbies(self) -> List[str]:
        return list(self.lobbies.keys())
    
    async def upsert_player(self, room_code: str, player: Player) -> None:
        async with self._get_lock(room_code):
            if room_code in self.lobbies:
                # Find and update existing player or add new one
                players = self.lobbies[room_code]["players"]
                for i, p in enumerate(players):
                    if p["player_id"] == player.player_id:
                        players[i] = player.model_dump()
                        return
                # Add new player
                players.append(player.model_dump())
    
    async def remove_player(self, room_code: str, player_id: str) -> None:
        async with self._get_lock(room_code):
            if room_code in self.lobbies:
                players = self.lobbies[room_code]["players"]
                self.lobbies[room_code]["players"] = [
                    p for p in players if p["player_id"] != player_id
                ]
                
                # Clean up empty lobbies
                if not self.lobbies[room_code]["players"]:
                    self._schedule_cleanup(room_code)
    
    async def publish(self, room_code: str, event: str, data: Dict) -> None:
        """Broadcast event to all connections in room"""
        if room_code in self.connections:
            # Clean data to ensure JSON serializable
            clean_data = self._clean_for_json(data)
            message = {"type": event, "data": clean_data}
            
            # Send to all connections with better error handling
            disconnected = []
            for ws in self.connections[room_code]:
                try:
                    await ws.send_json(message)
                except Exception as e:
                    print(f"WebSocket send error: {e}")
                    disconnected.append(ws)
            
            # Remove disconnected websockets
            for ws in disconnected:
                self.connections[room_code].discard(ws)
                
            # Clean up empty connection sets
            if not self.connections[room_code]:
                del self.connections[room_code]
    
    def _clean_for_json(self, data):
        """Clean data to ensure JSON serializable"""
        import datetime
        if isinstance(data, dict):
            return {k: self._clean_for_json(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._clean_for_json(item) for item in data]
        elif isinstance(data, datetime.datetime):
            return data.isoformat()
        elif isinstance(data, set):
            return list(data)
        else:
            return data
    
    def add_connection(self, room_code: str, websocket) -> None:
        """Add WebSocket connection to room"""
        if room_code not in self.connections:
            self.connections[room_code] = set()
        self.connections[room_code].add(websocket)
    
    def remove_connection(self, room_code: str, websocket) -> None:
        """Remove WebSocket connection from room"""
        if room_code in self.connections:
            self.connections[room_code].discard(websocket)
    
    def _schedule_cleanup(self, room_code: str, delay: int = 300) -> None:
        """Schedule lobby cleanup after delay"""
        if room_code in self.cleanup_tasks:
            self.cleanup_tasks[room_code].cancel()
        
        async def cleanup():
            await asyncio.sleep(delay)
            async with self._get_lock(room_code):
                self.lobbies.pop(room_code, None)
                self.connections.pop(room_code, None)
                self.locks.pop(room_code, None)
                self.cleanup_tasks.pop(room_code, None)
        
        self.cleanup_tasks[room_code] = asyncio.create_task(cleanup())

def generate_room_code() -> str:
    """Generate a unique 4-character room code"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))

def generate_player_id(name: str) -> str:
    """Generate stable player ID from name + short hash"""
    import hashlib
    hash_short = hashlib.md5(f"{name}{datetime.now().isoformat()}".encode()).hexdigest()[:6]
    return f"{name.lower().replace(' ', '_')}_{hash_short}"

# Global storage instance
storage = InMemoryStorage()
