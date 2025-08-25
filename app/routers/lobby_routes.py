"""
REST API endpoints for lobby management
"""
from datetime import datetime
from typing import List
from fastapi import APIRouter, HTTPException, status
from app.schemas.game_schemas import LobbyCreate, LobbyResponse, JoinLobby, Player
from app.utils.storage import storage, generate_room_code, generate_player_id

router = APIRouter()

@router.post("/lobbies", response_model=LobbyResponse, status_code=status.HTTP_201_CREATED)
async def create_lobby(lobby_data: LobbyCreate):
    """Create a new game lobby"""
    
    # Use custom room code if provided, otherwise generate one
    if lobby_data.custom_room_code:
        room_code = lobby_data.custom_room_code.upper()
        # Check if custom code is already taken
        if await storage.get_lobby(room_code):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Room code '{room_code}' is already taken"
            )
    else:
        room_code = generate_room_code()
        # Ensure unique room code
        while await storage.get_lobby(room_code):
            room_code = generate_room_code()
    
    # Generate host player
    host_player_id = generate_player_id(lobby_data.host_name)
    host_player = Player(
        player_id=host_player_id,
        name=lobby_data.host_name,
        is_host=True,
        is_ready=True,
        connected=True,
        joined_at=datetime.now()
    )
    
    # Create lobby
    lobby = {
        "room_code": room_code,
        "host_player_id": host_player_id,
        "game_type": lobby_data.game_type,
        "status": "waiting",
        "players": [host_player.model_dump()],
        "created_at": datetime.now(),
        "game_state": None,
        "game_results": None
    }
    
    await storage.save_lobby(room_code, lobby)
    
    return LobbyResponse(**lobby)

@router.post("/lobbies/join", response_model=LobbyResponse)
async def join_lobby(join_data: JoinLobby):
    """Join an existing lobby"""
    lobby = await storage.get_lobby(join_data.room_code)
    
    if not lobby:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lobby not found"
        )
    
    if lobby["status"] != "waiting":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Lobby is not accepting new players"
        )
    
    # Check if player name already exists
    existing_names = [p["name"] for p in lobby["players"]]
    if join_data.player_name in existing_names:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Player name already taken"
        )
    
    # Check lobby capacity
    if len(lobby["players"]) >= 8:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Lobby is full"
        )
    
    # Create new player
    player_id = generate_player_id(join_data.player_name)
    new_player = Player(
        player_id=player_id,
        name=join_data.player_name,
        is_host=False,
        is_ready=False,
        connected=True,
        joined_at=datetime.now()
    )
    
    await storage.upsert_player(join_data.room_code, new_player)
    
    # Get updated lobby
    updated_lobby = await storage.get_lobby(join_data.room_code)
    
    # Broadcast player joined
    await storage.publish(join_data.room_code, "player_joined", {
        "player": new_player.model_dump(),
        "message": f"{new_player.name} joined the lobby"
    })
    
    return LobbyResponse(**updated_lobby)

@router.get("/lobbies/{room_code}", response_model=LobbyResponse)
async def get_lobby(room_code: str):
    """Get lobby details"""
    lobby = await storage.get_lobby(room_code)
    
    if not lobby:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lobby not found"
        )
    
    return LobbyResponse(**lobby)

@router.delete("/lobbies/{room_code}/players/{player_id}")
async def leave_lobby(room_code: str, player_id: str):
    """Remove player from lobby"""
    lobby = await storage.get_lobby(room_code)
    
    if not lobby:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lobby not found"
        )
    
    # Find player
    player = next((p for p in lobby["players"] if p["player_id"] == player_id), None)
    if not player:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Player not found in lobby"
        )
    
    await storage.remove_player(room_code, player_id)
    
    # Broadcast player left
    await storage.publish(room_code, "player_left", {
        "player_id": player_id,
        "player_name": player["name"],
        "message": f"{player['name']} left the lobby"
    })
    
    return {"message": "Player removed from lobby"}

@router.get("/lobbies", response_model=List[str])
async def list_lobbies():
    """List all active lobby codes (for debugging)"""
    return await storage.list_lobbies()
