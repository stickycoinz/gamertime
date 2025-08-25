/**
 * Party Game Platform - Client-side JavaScript
 * Vanilla JS implementation for real-time multiplayer games
 */

class GameClient {
    constructor() {
        this.currentScreen = 'home-screen';
        this.selectedGame = null;
        this.lobbyData = null;
        this.playerData = null;
        this.websocket = null;
        this.gameState = null;
        
        this.init();
    }
    
    init() {
        this.setupEventListeners();
        this.showScreen('home-screen');
    }
    
    setupEventListeners() {
        // Home screen
        document.querySelectorAll('.game-card').forEach(card => {
            card.addEventListener('click', (e) => this.selectGame(e.target.closest('.game-card')));
        });
        
        document.getElementById('host-name').addEventListener('input', () => this.validateHostForm());
        document.getElementById('custom-room-code').addEventListener('input', () => this.validateHostForm());
        document.getElementById('create-lobby-btn').addEventListener('click', () => this.createLobby());
        
        document.getElementById('room-code').addEventListener('input', () => this.validateJoinForm());
        document.getElementById('player-name').addEventListener('input', () => this.validateJoinForm());
        document.getElementById('join-lobby-btn').addEventListener('click', () => this.joinLobby());
        
        // Lobby screen
        document.getElementById('ready-btn').addEventListener('click', () => this.toggleReady());
        document.getElementById('start-game-btn').addEventListener('click', () => this.startGame());
        document.getElementById('leave-lobby-btn').addEventListener('click', () => this.leaveLobby());
        
        document.getElementById('chat-input').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.sendChat();
        });
        document.getElementById('send-chat-btn').addEventListener('click', () => this.sendChat());
        
        // Game screen
        document.getElementById('click-btn').addEventListener('click', () => this.handleClick());
        document.getElementById('buzz-btn').addEventListener('click', () => this.handleBuzz());
        
        // Results screen
        document.getElementById('play-again-btn').addEventListener('click', () => this.playAgain());
        document.getElementById('back-to-lobby-btn').addEventListener('click', () => this.backToLobby());
        document.getElementById('leave-game-btn').addEventListener('click', () => this.leaveGame());
    }
    
    // Game Selection
    selectGame(card) {
        console.log('Selecting game:', card.dataset.game);
        document.querySelectorAll('.game-card').forEach(c => c.classList.remove('selected'));
        card.classList.add('selected');
        this.selectedGame = card.dataset.game;
        console.log('Selected game set to:', this.selectedGame);
        this.validateHostForm();
    }
    
    validateHostForm() {
        const name = document.getElementById('host-name').value.trim();
        const btn = document.getElementById('create-lobby-btn');
        const isValid = !!(name && this.selectedGame);
        console.log('Validating host form:', { name, selectedGame: this.selectedGame, isValid });
        btn.disabled = !isValid;
    }
    
    validateJoinForm() {
        const roomCode = document.getElementById('room-code').value.trim();
        const playerName = document.getElementById('player-name').value.trim();
        const btn = document.getElementById('join-lobby-btn');
        btn.disabled = !roomCode || !playerName;
    }
    
    // Lobby Management
    async createLobby() {
        const hostName = document.getElementById('host-name').value.trim();
        const customRoomCode = document.getElementById('custom-room-code').value.trim().toUpperCase();
        
        if (!this.selectedGame) {
            this.showMessage('Please select a game type first!', 'error');
            return;
        }
        
        try {
            const requestData = {
                host_name: hostName,
                game_type: this.selectedGame
            };
            
            if (customRoomCode) {
                requestData.custom_room_code = customRoomCode;
            }
            
            console.log('Creating lobby:', requestData);
            
            const response = await fetch('/api/lobbies', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(requestData)
            });
            
            console.log('Response status:', response.status);
            
            if (!response.ok) {
                const error = await response.json();
                console.error('API Error:', error);
                throw new Error(error.detail || `Server error: ${response.status}`);
            }
            
            const lobby = await response.json();
            console.log('Lobby created:', lobby);
            
            this.lobbyData = lobby;
            this.playerData = lobby.players.find(p => p.is_host);
            
            this.showMessage(`🎉 Lobby created! Room code: ${lobby.room_code}`, 'success');
            
            // Force scroll to top and show lobby screen
            window.scrollTo(0, 0);
            this.showScreen('lobby-screen');
            this.updateLobbyUI();
            this.connectWebSocket();
            
        } catch (error) {
            console.error('Create lobby error:', error);
            this.showMessage(`❌ ${error.message}`, 'error');
        }
    }
    
    async joinLobby() {
        const roomCode = document.getElementById('room-code').value.trim().toUpperCase();
        const playerName = document.getElementById('player-name').value.trim();
        
        try {
            console.log('Joining lobby:', { room_code: roomCode, player_name: playerName });
            
            const response = await fetch('/api/lobbies/join', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    room_code: roomCode,
                    player_name: playerName
                })
            });
            
            console.log('Join response status:', response.status);
            
            if (!response.ok) {
                const error = await response.json();
                console.error('Join API Error:', error);
                throw new Error(error.detail || `Failed to join lobby: ${response.status}`);
            }
            
            const lobby = await response.json();
            console.log('Joined lobby:', lobby);
            
            this.lobbyData = lobby;
            this.playerData = lobby.players.find(p => p.name === playerName);
            this.selectedGame = lobby.game_type;
            
            this.showMessage(`🎉 Joined ${lobby.room_code}!`, 'success');
            
            // Force scroll to top and show lobby screen  
            window.scrollTo(0, 0);
            this.showScreen('lobby-screen');
            this.updateLobbyUI();
            this.connectWebSocket();
            
        } catch (error) {
            console.error('Join lobby error:', error);
            this.showMessage(`❌ ${error.message}`, 'error');
        }
    }
    
    async leaveLobby() {
        if (this.websocket) {
            this.websocket.close();
        }
        
        try {
            await fetch(`/api/lobbies/${this.lobbyData.room_code}/players/${this.playerData.player_id}`, {
                method: 'DELETE'
            });
        } catch (error) {
            console.error('Error leaving lobby:', error);
        }
        
        this.resetState();
        this.showScreen('home-screen');
    }
    
    // WebSocket Connection
    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/${this.lobbyData.room_code}/${this.playerData.player_id}`;
        
        console.log('Connecting WebSocket:', wsUrl);
        this.websocket = new WebSocket(wsUrl);
        
        this.websocket.onopen = () => {
            console.log('WebSocket connected successfully');
            this.startHeartbeat();
            // Request fresh lobby data on connect
            this.refreshLobbyData();
        };
        
        this.websocket.onmessage = (event) => {
            const message = JSON.parse(event.data);
            this.handleWebSocketMessage(message);
        };
        
        this.websocket.onclose = (event) => {
            console.log('WebSocket disconnected', event.code, event.reason);
            if (event.code !== 1000) {
                this.showMessage('Connection lost. Trying to reconnect...', 'warning');
                setTimeout(() => this.connectWebSocket(), 3000);
            }
        };
        
        this.websocket.onerror = (error) => {
            console.error('WebSocket error:', error);
            this.showMessage('Connection error', 'error');
        };
    }
    
    startHeartbeat() {
        setInterval(() => {
            if (this.websocket?.readyState === WebSocket.OPEN) {
                this.websocket.send(JSON.stringify({type: 'ping', data: {}}));
            }
        }, 30000);
    }
    
    sendWebSocketMessage(type, data = {}) {
        if (this.websocket?.readyState === WebSocket.OPEN) {
            this.websocket.send(JSON.stringify({type, data}));
        }
    }
    
    // WebSocket Message Handling
    async handleWebSocketMessage(message) {
        const {type, data} = message;
        
        switch (type) {
                    case 'pong':
            // Heartbeat response
            break;
            
        case 'player_connected':
            console.log(`${data.player_name} connected`);
            await this.refreshLobbyData();
            break;
            
        case 'lobby_updated':
            this.updateLobbyFromWS(data);
            break;
            
        case 'player_joined':
            this.showMessage(`${data.player.name} joined the lobby`, 'success');
            // Refresh lobby data to show new player
            await this.refreshLobbyData();
            break;
            
        case 'player_left':
            this.showMessage(`${data.player_name} left the lobby`, 'warning');
            // Refresh lobby data to remove player
            await this.refreshLobbyData();
            break;
                
            case 'chat_message':
                this.addChatMessage(data);
                break;
                
            case 'game_started':
                this.handleGameStart(data);
                break;
                
            case 'tick':
                this.updateTimer(data);
                break;
                
            case 'click_registered':
                this.updateClickerScores(data);
                break;
                
            case 'new_question':
                this.handleNewQuestion(data);
                break;
                
                    case 'player_buzzed':
            this.handlePlayerBuzzed(data);
            break;
            
        case 'buzzer_cleared':
            this.handleBuzzerCleared(data);
            break;
                
            case 'answer_result':
                this.handleAnswerResult(data);
                break;
                
            case 'time_up':
                this.handleTimeUp(data);
                break;
                
            case 'game_finished':
                this.handleGameFinished(data);
                break;
                
            case 'error':
                this.showMessage(data.message, 'error');
                break;
                
            default:
                console.log('Unknown message type:', type, data);
        }
    }
    
    // Lobby UI Updates
    updateLobbyUI() {
        document.getElementById('room-code-display').textContent = this.lobbyData.room_code;
        document.getElementById('game-type-display').textContent = `🎮 ${this.getGameDisplayName()}`;
        
        this.updatePlayersList();
        this.updateLobbyActions();
    }
    
    updateLobbyFromWS(data) {
        if (data.players) {
            this.lobbyData.players = data.players;
            this.updatePlayersList();
        }
        
        if (data.all_ready && this.playerData.is_host) {
            document.getElementById('start-game-btn').disabled = false;
        }
    }
    
    async refreshLobbyData() {
        try {
            const response = await fetch(`/api/lobbies/${this.lobbyData.room_code}`);
            if (response.ok) {
                const lobby = await response.json();
                this.lobbyData = lobby;
                this.updatePlayersList();
                this.updateLobbyActions();
            }
        } catch (error) {
            console.error('Failed to refresh lobby data:', error);
        }
    }
    
    updatePlayersList() {
        const list = document.getElementById('players-list');
        list.innerHTML = '';
        
        this.lobbyData.players.forEach(player => {
            const playerCard = document.createElement('div');
            playerCard.className = `player-card ${player.is_host ? 'host' : ''} ${player.is_ready ? 'ready' : ''} ${player.connected ? 'connected' : 'disconnected'}`;
            
            playerCard.innerHTML = `
                <div class="player-info">
                    <span class="player-name">${player.name}</span>
                </div>
                <div class="player-status">
                    ${player.is_host ? '<span class="status-badge host">Host</span>' : ''}
                    <span class="status-badge ${player.is_ready ? 'ready' : 'not-ready'}">
                        ${player.is_ready ? 'Ready' : 'Not Ready'}
                    </span>
                </div>
            `;
            
            list.appendChild(playerCard);
        });
    }
    
    updateLobbyActions() {
        const readyBtn = document.getElementById('ready-btn');
        const startBtn = document.getElementById('start-game-btn');
        
        readyBtn.textContent = this.playerData.is_ready ? 'Not Ready' : 'Ready';
        readyBtn.className = `ready-btn ${this.playerData.is_ready ? 'ready' : ''}`;
        
        if (this.playerData.is_host) {
            startBtn.style.display = 'block';
            const allReady = this.lobbyData.players.every(p => p.is_ready);
            startBtn.disabled = !allReady;
        }
    }
    
    // Lobby Actions
    toggleReady() {
        const isReady = !this.playerData.is_ready;
        console.log(`Player ${this.playerData.player_id} toggling ready: ${isReady}`);
        
        this.playerData.is_ready = isReady;
        
        this.sendWebSocketMessage(isReady ? 'player_ready' : 'player_unready');
        this.updateLobbyActions();
    }
    
    startGame() {
        this.sendWebSocketMessage('game_action', {action: 'start_game'});
    }
    
    sendChat() {
        const input = document.getElementById('chat-input');
        const message = input.value.trim();
        
        if (message) {
            this.sendWebSocketMessage('chat', {message});
            input.value = '';
        }
    }
    
    addChatMessage(data) {
        const messages = document.getElementById('chat-messages');
        const messageDiv = document.createElement('div');
        messageDiv.className = 'chat-message';
        messageDiv.innerHTML = `
            <span class="sender">${data.player_name}:</span>
            <span class="content">${data.message}</span>
        `;
        
        messages.appendChild(messageDiv);
        messages.scrollTop = messages.scrollHeight;
    }
    
    // Game Logic
    handleGameStart(data) {
        this.gameState = {type: data.game_type, active: true};
        this.showScreen('game-screen');
        
        document.getElementById('game-title').textContent = this.getGameDisplayName();
        document.getElementById('game-status').textContent = data.message;
        
        if (data.game_type === 'clicker') {
            this.setupClickerGame(data);
        } else if (data.game_type === 'trivia') {
            this.setupTriviaGame(data);
        }
    }
    
    setupClickerGame(data) {
        document.getElementById('clicker-game').style.display = 'block';
        document.getElementById('trivia-game').style.display = 'none';
        
        const clickBtn = document.getElementById('click-btn');
        clickBtn.disabled = false;
        clickBtn.querySelector('.click-count').textContent = '0';
        
        this.updateClickerScores({scores: {}});
    }
    
    setupTriviaGame(data) {
        document.getElementById('trivia-game').style.display = 'block';
        document.getElementById('clicker-game').style.display = 'none';
        
        document.getElementById('buzz-btn').disabled = false;
        document.getElementById('question-text').textContent = 'Waiting for first question...';
        
        this.updateTriviaScores({});
    }
    
    updateTimer(data) {
        const timer = document.getElementById('timer-display');
        if (data.time_remaining !== undefined) {
            timer.textContent = data.time_remaining;
        }
        
        if (this.gameState?.type === 'clicker' && data.scores) {
            this.updateClickerScores(data);
        }
    }
    
    // Clicker Game
    handleClick() {
        if (this.gameState?.active) {
            this.sendWebSocketMessage('player_action', {action: 'click'});
        }
    }
    
    updateClickerScores(data) {
        const scoresDiv = document.getElementById('clicker-scores');
        scoresDiv.innerHTML = '';
        
        // Update player's own count
        if (data.player_id === this.playerData.player_id) {
            document.getElementById('click-btn').querySelector('.click-count').textContent = data.count || 0;
        }
        
        // Sort scores
        const sortedScores = Object.entries(data.scores || {})
            .sort(([,a], [,b]) => b - a);
        
        sortedScores.forEach(([playerId, score], index) => {
            const player = this.lobbyData.players.find(p => p.player_id === playerId);
            const scoreItem = document.createElement('div');
            scoreItem.className = `score-item ${index === 0 ? 'leader' : ''}`;
            scoreItem.innerHTML = `
                <span>${player?.name || playerId}</span>
                <span>${score}</span>
            `;
            scoresDiv.appendChild(scoreItem);
        });
    }
    
    // Trivia Game
    handleNewQuestion(data) {
        document.getElementById('question-text').textContent = data.question;
        document.getElementById('game-status').textContent = `Question ${data.question_number}/${data.total_questions}`;
        
        // Show options (read-only)
        const optionsDiv = document.getElementById('question-options');
        optionsDiv.innerHTML = '';
        data.options.forEach((option, index) => {
            const optionDiv = document.createElement('div');
            optionDiv.className = 'option-card';
            optionDiv.textContent = `${index + 1}. ${option}`;
            optionsDiv.appendChild(optionDiv);
        });
        
        // Enable buzz button
        document.getElementById('buzz-btn').disabled = false;
        document.getElementById('answer-options').style.display = 'none';
    }
    
    handleBuzz() {
        if (this.gameState?.active) {
            this.sendWebSocketMessage('player_action', {action: 'buzz'});
        }
    }
    
    handlePlayerBuzzed(data) {
        // Show buzz order - DON'T disable button for others
        const message = `${data.player_name} buzzed in #${data.position}! (${data.total_buzzed} total)`;
        this.showMessage(message, data.player_id === this.playerData.player_id ? 'success' : 'info');
        
        // Update trivia scores display with buzz order
        this.updateBuzzOrder(data);
        
        // Only disable for the player who buzzed
        if (data.player_id === this.playerData.player_id) {
            document.getElementById('buzz-btn').disabled = true;
            document.getElementById('buzz-btn').textContent = `Buzzed #${data.position}`;
        }
    }
    
    updateBuzzOrder(data) {
        // Show live buzz order in the scores area
        const scoresDiv = document.getElementById('trivia-scores');
        const buzzOrderDiv = scoresDiv.querySelector('.buzz-order') || document.createElement('div');
        buzzOrderDiv.className = 'buzz-order';
        
        if (!scoresDiv.querySelector('.buzz-order')) {
            buzzOrderDiv.innerHTML = '<h4>Buzz Order:</h4>';
            scoresDiv.prepend(buzzOrderDiv);
        }
        
        const buzzList = buzzOrderDiv.querySelector('.buzz-list') || document.createElement('div');
        buzzList.className = 'buzz-list';
        buzzList.innerHTML = `${data.position}. ${data.player_name}`;
        
        if (!buzzOrderDiv.querySelector('.buzz-list')) {
            buzzOrderDiv.appendChild(buzzList);
        }
    }
    
    handleBuzzerCleared(data) {
        // Re-enable buzz button for new question
        const buzzBtn = document.getElementById('buzz-btn');
        buzzBtn.disabled = false;
        buzzBtn.textContent = '🔔 BUZZ!';
        document.getElementById('answer-options').style.display = 'none';
        
        // Clear buzz order display
        const scoresDiv = document.getElementById('trivia-scores');
        const buzzOrderDiv = scoresDiv.querySelector('.buzz-order');
        if (buzzOrderDiv) {
            buzzOrderDiv.remove();
        }
    }
    
    showAnswerOptions() {
        const optionsDiv = document.getElementById('answer-options');
        const questionOptions = document.querySelectorAll('#question-options .option-card');
        
        optionsDiv.innerHTML = '';
        questionOptions.forEach((option, index) => {
            const btn = document.createElement('button');
            btn.className = 'answer-option';
            btn.textContent = option.textContent;
            btn.onclick = () => this.submitAnswer(index);
            optionsDiv.appendChild(btn);
        });
        
        optionsDiv.style.display = 'grid';
    }
    
    submitAnswer(answerIndex) {
        this.sendWebSocketMessage('player_action', {
            action: 'answer',
            answer_index: answerIndex
        });
        
        // Disable answer options
        document.querySelectorAll('.answer-option').forEach(btn => btn.disabled = true);
    }
    
    handleAnswerResult(data) {
        const message = data.is_correct 
            ? `${data.player_name} is correct! +${data.points_awarded} points`
            : `${data.player_name} is wrong. Correct answer: ${data.correct_answer_text}`;
        
        this.showMessage(message, data.is_correct ? 'success' : 'error');
        this.updateTriviaScores(data.scores);
    }
    
    handleTimeUp(data) {
        this.showMessage(`Time's up! Correct answer: ${data.correct_answer_text}`, 'warning');
    }
    
    updateTriviaScores(scores) {
        const scoresDiv = document.getElementById('trivia-scores');
        scoresDiv.innerHTML = '';
        
        const sortedScores = Object.entries(scores || {})
            .sort(([,a], [,b]) => b - a);
        
        sortedScores.forEach(([playerId, score], index) => {
            const player = this.lobbyData.players.find(p => p.player_id === playerId);
            const scoreItem = document.createElement('div');
            scoreItem.className = `score-item ${index === 0 ? 'leader' : ''}`;
            scoreItem.innerHTML = `
                <span>${player?.name || playerId}</span>
                <span>${score}</span>
            `;
            scoresDiv.appendChild(scoreItem);
        });
    }
    
    // Game Results
    handleGameFinished(data) {
        this.gameState.active = false;
        this.showScreen('results-screen');
        
        if (data.winner) {
            document.getElementById('winner-text').textContent = data.winner.name;
        }
        
        this.displayFinalScores(data.results.scores);
        
        if (this.playerData.is_host) {
            document.getElementById('play-again-btn').style.display = 'block';
        }
    }
    
    displayFinalScores(scores) {
        const scoresDiv = document.getElementById('final-scores');
        scoresDiv.innerHTML = '';
        
        scores.forEach(scoreCard => {
            const card = document.createElement('div');
            card.className = `score-card rank-${scoreCard.rank}`;
            card.innerHTML = `
                <div>
                    <span class="rank">#${scoreCard.rank}</span>
                    <span class="name">${scoreCard.name}</span>
                </div>
                <span class="score">${scoreCard.score}</span>
            `;
            scoresDiv.appendChild(card);
        });
    }
    
    // Results Actions
    playAgain() {
        this.sendWebSocketMessage('game_action', {action: 'start_game'});
    }
    
    backToLobby() {
        this.showScreen('lobby-screen');
        this.updateLobbyUI();
    }
    
    leaveGame() {
        this.leaveLobby();
    }
    
    // Utility Methods
    showScreen(screenId) {
        console.log(`Switching to screen: ${screenId}`);
        
        // Hide all screens
        document.querySelectorAll('.screen').forEach(screen => {
            screen.classList.remove('active');
            screen.style.display = 'none';
        });
        
        // Show target screen
        const targetScreen = document.getElementById(screenId);
        targetScreen.style.display = 'block';
        targetScreen.classList.add('active');
        
        this.currentScreen = screenId;
        console.log(`Screen switched to: ${screenId}`);
    }
    
    showMessage(message, type = 'info') {
        const container = document.getElementById('status-messages');
        const messageDiv = document.createElement('div');
        messageDiv.className = `status-message ${type}`;
        messageDiv.textContent = message;
        
        container.appendChild(messageDiv);
        
        setTimeout(() => {
            messageDiv.remove();
        }, 5000);
    }
    
    getGameDisplayName() {
        return this.selectedGame === 'clicker' ? 'Clicker Challenge' : 'Trivia Challenge';
    }
    
    resetState() {
        this.selectedGame = null;
        this.lobbyData = null;
        this.playerData = null;
        this.gameState = null;
        
        if (this.websocket) {
            this.websocket.close();
            this.websocket = null;
        }
        
        // Reset forms
        document.getElementById('host-name').value = '';
        document.getElementById('custom-room-code').value = '';
        document.getElementById('room-code').value = '';
        document.getElementById('player-name').value = '';
        document.getElementById('chat-input').value = '';
        
        // Reset game selections
        document.querySelectorAll('.game-card').forEach(card => {
            card.classList.remove('selected');
        });
    }
}

// Initialize the game client when the page loads
document.addEventListener('DOMContentLoaded', () => {
    new GameClient();
});
