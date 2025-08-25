# 🎮 Party Game Platform

A real-time multiplayer party game platform featuring **Clicker Challenge** and **Trivia** games built with FastAPI, WebSockets, and vanilla JavaScript.

## 🎯 Games Available

### 👆 Clicker Challenge
- **10-second button-mash race**
- Everyone taps as fast as they can
- Real-time score tracking
- Results displayed as score cards with rankings

### 🧠 Trivia Challenge  
- Question-based game with buzzer system
- First player to buzz gets to answer
- Points awarded for correct answers (bonus for speed)
- 5 questions per game with live leaderboard

## 🚀 Quick Start

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Run the server:**
   ```bash
   python app/main.py
   ```

4. **Open your browser:**
   ```
   http://localhost:8000
   ```

## 🎮 How to Play

### Creating a Game
1. Choose your game type (Clicker or Trivia)
2. Enter your name and click "Create Lobby"
3. Share the room code with friends
4. Wait for players to join and mark themselves ready
5. Start the game!

### Joining a Game
1. Get the room code from the host
2. Enter the room code and your name
3. Click "Join Lobby"
4. Mark yourself as ready
5. Wait for the host to start!

## 🏗️ Architecture

### Backend (FastAPI + WebSockets)
- **`app/main.py`**: Main FastAPI application
- **`app/routers/`**: REST API endpoints and WebSocket handlers
- **`app/schemas/`**: Pydantic models for request/response validation
- **`app/game_logic/`**: Game engines for Clicker and Trivia
- **`app/utils/`**: Storage interface and utilities

### Frontend (Vanilla JS)
- **`static/index.html`**: Single-page application
- **`static/css/style.css`**: Modern responsive styling
- **`static/js/app.js`**: Real-time game client

### Real-time Features
- **WebSocket connections** for instant updates
- **Buzzer system** with first-in lockout logic
- **Live score tracking** during games
- **Chat system** in lobbies
- **Connection management** with auto-reconnect

## 🔧 API Endpoints

### REST API
- `POST /api/lobbies` - Create new lobby
- `POST /api/lobbies/join` - Join existing lobby  
- `GET /api/lobbies/{room_code}` - Get lobby details
- `DELETE /api/lobbies/{room_code}/players/{player_id}` - Leave lobby
- `GET /health` - Health check

### WebSocket Events

#### Client → Server
- `player_ready/player_unready` - Toggle ready status
- `chat` - Send chat message
- `game_action` - Host game controls (start/end)
- `player_action` - In-game actions (click/buzz/answer)
- `ping` - Heartbeat

#### Server → Client  
- `lobby_updated` - Player status changes
- `player_joined/player_left` - Player connections
- `game_started` - Game initialization
- `tick` - Timer updates
- `click_registered` - Clicker score updates
- `new_question` - Trivia question display
- `buzz_lockout/buzzer_cleared` - Buzzer state
- `answer_result` - Trivia answer feedback
- `game_finished` - Final results

## 🎯 Game Logic

### Clicker Challenge
- 10-second countdown timer
- Each click increments player score
- Real-time score broadcasting
- Winner determined by highest click count

### Trivia Challenge  
- 5 pre-loaded questions with multiple choice
- **Buzzer system**: First to buzz gets to answer
- **Lockout mechanism**: Other players blocked until next question
- **Scoring**: Correct answers earn points (bonus for speed)
- **Timer**: 30 seconds per question

## 🔒 Security Features

- Input validation with Pydantic
- Room code generation and validation
- Player name uniqueness per lobby
- WebSocket connection verification
- No secrets in code (uses environment variables)
- Sanitized logging (no PII)

## 🎨 UI/UX Features

- **Responsive design** - Works on desktop and mobile
- **Real-time updates** - Live scores and player status
- **Visual feedback** - Button animations and status indicators
- **Score cards** - Beautiful results display with rankings
- **Connection status** - Shows player online/offline state
- **Chat system** - Lobby communication

## 🚀 Deployment

### Local Development
```bash
python app/main.py
```

### Production
```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### Environment Variables
```bash
PORT=8000              # Server port
HOST=0.0.0.0          # Server host
DEBUG=false           # Debug mode
SECRET_KEY=your-key   # Security key
CLICKER_DURATION=10   # Clicker game duration
MAX_LOBBY_SIZE=8      # Max players per lobby
LOBBY_TIMEOUT=3600    # Lobby cleanup time
```

## 🔮 Future Enhancements

- **Redis scaling**: Horizontal scaling with Redis pub/sub
- **More games**: Additional party game modes
- **Custom questions**: User-provided trivia questions
- **Spectator mode**: Watch games without playing
- **Game replays**: Save and replay game sessions
- **Achievements**: Player progress tracking

## 🧪 Testing

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=app
```

## 📁 Project Structure

```
fairytalegame/
├── .cursor/rules/          # AI coding rules
├── app/
│   ├── routers/           # API endpoints
│   ├── schemas/           # Pydantic models  
│   ├── game_logic/        # Game engines
│   ├── utils/             # Storage & utilities
│   └── main.py           # FastAPI app
├── static/
│   ├── css/              # Styles
│   ├── js/               # Client code
│   └── index.html        # SPA
├── requirements.txt       # Dependencies
├── .env.example          # Config template
└── README.md            # This file
```

Built with ❤️ using FastAPI, WebSockets, and modern web standards.
