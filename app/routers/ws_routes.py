"""
WebSocket routes for real-time game communication
"""
import json
import asyncio
from typing import Dict, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.schemas.game_schemas import PlayerAction, GameAction, Player
from app.utils.storage import storage
from app.game_logic.clicker_game import ClickerGame, active_games
from app.game_logic.trivia_game import TriviaGame, active_trivia_games

router = APIRouter()

# Track WebSocket connections
connections: Dict[str, Set[WebSocket]] = {}

@router.websocket("/ws/{room_code}/{player_id}")
async def websocket_endpoint(websocket: WebSocket, room_code: str, player_id: str):
    """Handle WebSocket connections for real-time communication"""
    await websocket.accept()
    
    # Verify lobby exists
    lobby = await storage.get_lobby(room_code)
    if not lobby:
        await websocket.close(code=4004, reason="Lobby not found")
        return
    
    # Verify player exists in lobby
    player = next((p for p in lobby["players"] if p["player_id"] == player_id), None)
    if not player:
        await websocket.close(code=4003, reason="Player not in lobby")
        return
    
    # Add connection to room
    if room_code not in connections:
        connections[room_code] = set()
    connections[room_code].add(websocket)
    
    # Update player connection status
    updated_player = Player(**player)
    updated_player.connected = True
    await storage.upsert_player(room_code, updated_player)
    
    # Notify lobby of connection
    await broadcast_to_room(room_code, "player_connected", {
        "player_id": player_id,
        "player_name": player["name"]
    })
    
    try:
        while True:
            # Receive message
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Handle message based on type
            await handle_websocket_message(room_code, player_id, message, websocket)
            
    except WebSocketDisconnect:
        # Remove connection
        connections[room_code].discard(websocket)
        
        # Update player connection status
        updated_player.connected = False
        await storage.upsert_player(room_code, updated_player)
        
        # Notify lobby of disconnection
        await broadcast_to_room(room_code, "player_disconnected", {
            "player_id": player_id,
            "player_name": player["name"]
        })
    
    except Exception as e:
        print(f"WebSocket error: {e}")
        await websocket.close(code=4000, reason="Internal error")

async def handle_websocket_message(room_code: str, player_id: str, message: Dict, websocket: WebSocket):
    """Process incoming WebSocket messages"""
    message_type = message.get("type")
    data = message.get("data", {})
    
    # Get current lobby state
    lobby = await storage.get_lobby(room_code)
    if not lobby:
        return
    
    player = next((p for p in lobby["players"] if p["player_id"] == player_id), None)
    if not player:
        return
    
    try:
        if message_type == "ping":
            # Respond to heartbeat
            await websocket.send_json({"type": "pong", "data": {}})
        
        elif message_type == "player_ready":
            await handle_player_ready(room_code, player_id, True)
        
        elif message_type == "player_unready":
            await handle_player_ready(room_code, player_id, False)
        
        elif message_type == "chat":
            await handle_chat_message(room_code, player_id, data.get("message", ""))
        
        elif message_type == "game_action":
            await handle_game_action(room_code, player_id, data)
        
        elif message_type == "player_action":
            await handle_player_action(room_code, player_id, data)
        
        else:
            print(f"Unknown message type: {message_type}")
    
    except Exception as e:
        print(f"Error handling message: {e}")
        await websocket.send_json({
            "type": "error",
            "data": {"message": "Failed to process message"}
        })

async def handle_player_ready(room_code: str, player_id: str, is_ready: bool):
    """Handle player ready/unready status"""
    lobby = await storage.get_lobby(room_code)
    if not lobby or lobby["status"] != "waiting":
        return
    
    # Update player ready status
    for p in lobby["players"]:
        if p["player_id"] == player_id:
            p["is_ready"] = is_ready
            break
    
    await storage.save_lobby(room_code, lobby)
    
    # Broadcast lobby update
    await broadcast_to_room(room_code, "lobby_updated", {
        "players": lobby["players"],
        "all_ready": all(p["is_ready"] for p in lobby["players"])
    })

async def handle_chat_message(room_code: str, player_id: str, message: str):
    """Handle chat messages"""
    lobby = await storage.get_lobby(room_code)
    if not lobby:
        return
    
    player = next((p for p in lobby["players"] if p["player_id"] == player_id), None)
    if not player:
        return
    
    # Broadcast chat message
    await broadcast_to_room(room_code, "chat_message", {
        "player_id": player_id,
        "player_name": player["name"],
        "message": message[:200],  # Limit message length
        "timestamp": str(asyncio.get_event_loop().time())
    })

async def handle_game_action(room_code: str, player_id: str, data: Dict):
    """Handle game control actions (host only)"""
    lobby = await storage.get_lobby(room_code)
    if not lobby:
        return
    
    # Verify player is host
    player = next((p for p in lobby["players"] if p["player_id"] == player_id), None)
    if not player or not player["is_host"]:
        return
    
    action = data.get("action")
    
    if action == "start_game":
        await start_game(room_code, lobby)
    
    elif action == "end_game":
        await end_game(room_code)
    
    elif action == "next_question" and lobby["game_type"] == "trivia":
        # Handle trivia-specific actions
        if room_code in active_trivia_games:
            game = active_trivia_games[room_code]
            await game._next_question()

async def handle_player_action(room_code: str, player_id: str, data: Dict):
    """Handle in-game player actions"""
    action = data.get("action")
    
    if action == "click":
        # Handle clicker game clicks
        if room_code in active_games:
            game = active_games[room_code]
            await game.handle_click(player_id)
    
    elif action == "buzz":
        # Handle trivia game buzzer
        if room_code in active_trivia_games:
            game = active_trivia_games[room_code]
            await game.handle_buzz(player_id)
    
    elif action == "answer":
        # Handle trivia game answers
        if room_code in active_trivia_games:
            game = active_trivia_games[room_code]
            answer_index = data.get("answer_index")
            if answer_index is not None:
                await game.handle_answer(player_id, answer_index)

async def start_game(room_code: str, lobby: Dict):
    """Start a new game based on lobby type"""
    # Check all players are ready
    if not all(p["is_ready"] for p in lobby["players"]):
        await broadcast_to_room(room_code, "error", {
            "message": "All players must be ready to start"
        })
        return
    
    # Update lobby status
    lobby["status"] = "active"
    await storage.save_lobby(room_code, lobby)
    
    # Create game instance
    players = [Player(**p) for p in lobby["players"]]
    
    if lobby["game_type"] == "clicker":
        game = ClickerGame(room_code)
        active_games[room_code] = game
        await game.start_game(players)
    
    elif lobby["game_type"] == "trivia":
        game = TriviaGame(room_code)
        active_trivia_games[room_code] = game
        await game.start_game(players)

async def end_game(room_code: str):
    """Force end the current game"""
    # Stop clicker game
    if room_code in active_games:
        game = active_games[room_code]
        await game.stop_game()
        del active_games[room_code]
    
    # Stop trivia game
    if room_code in active_trivia_games:
        game = active_trivia_games[room_code]
        await game.stop_game()
        del active_trivia_games[room_code]
    
    # Update lobby status
    lobby = await storage.get_lobby(room_code)
    if lobby:
        lobby["status"] = "waiting"
        await storage.save_lobby(room_code, lobby)

async def broadcast_to_room(room_code: str, event_type: str, data: Dict):
    """Broadcast message to all connections in a room"""
    if room_code not in connections:
        return
    
    message = {"type": event_type, "data": data}
    
    # Send to all connections in room
    disconnected = set()
    for ws in connections[room_code]:
        try:
            await ws.send_json(message)
        except Exception:
            # Mark for removal
            disconnected.add(ws)
    
    # Remove disconnected WebSockets
    connections[room_code] -= disconnected
