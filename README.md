# Coin Collector - Multiplayer Game

A real-time multiplayer coin collector game built with Python, Pygame, and WebSockets. Players compete to collect coins in a shared game arena with server-authoritative game logic.

![Game Screenshot](screenshot.png)

## Features

- **Real-time Multiplayer**: 2 players compete simultaneously
- **Server-Authoritative**: All game logic runs on the server to prevent cheating
- **Network Latency Simulation**: 200ms artificial latency to demonstrate networking concepts
- **Entity Interpolation**: Smooth rendering of remote players despite network delays
- **Client-Side Prediction**: Responsive local player controls with server reconciliation

## Requirements

- **Python**: 3.10 or higher
- **Operating System**: Windows, macOS, or Linux
- **Network**: Local network or localhost for testing

### Dependencies

**Server:**
- `websockets>=12.0`

**Client:**
- `pygame>=2.5.0`
- `websockets>=12.0`

## Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd coin-collector-multiplayer
   ```

2. **Install server dependencies:**
   ```bash
   cd server
   pip install -r requirements.txt
   ```

3. **Install client dependencies:**
   ```bash
   cd ../client
   pip install -r requirements.txt
   ```

   Or install all at once:
   ```bash
   pip install websockets pygame
   ```

## How to Run

### Step 1: Start the Server

Open a terminal and run:
```bash
cd server
python server.py
```

You should see:
```
Starting Coin Collector server on ws://localhost:8765
Simulated network latency: 200ms
Waiting for players to connect...
```

### Step 2: Start Client 1

Open a **new terminal** and run:
```bash
cd client
python client.py
```

### Step 3: Start Client 2

Open **another new terminal** and run:
```bash
cd client
python client.py
```

The game will automatically start once both players are connected!

## Controls

| Key | Action |
|-----|--------|
| `W` or `↑` | Move Up |
| `A` or `←` | Move Left |
| `S` or `↓` | Move Down |
| `D` or `→` | Move Right |
| `ESC` | Quit Game |

## Gameplay

1. **Objective**: Collect more coins than your opponent!
2. **Coins**: Yellow circles that spawn randomly every 3 seconds
3. **Scoring**: Each coin collected awards 1 point
4. **Winning**: First player to reach 10 points wins, or the player with the most points when time runs out (60 seconds)

## Architecture

### Client-Server Model

This game uses a **server-authoritative** architecture:

```
┌─────────────────────────────────────────────────────────────┐
│                         SERVER                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                    Game State                            │ │
│  │  - All player positions (authoritative)                  │ │
│  │  - All coin positions and spawning                       │ │
│  │  - Score tracking                                        │ │
│  │  - Collision detection                                   │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
         ▲                                    ▲
         │ Input (dx, dy)                     │ Input (dx, dy)
         │                                    │
         ▼ State Updates                      ▼ State Updates
┌─────────────────┐                ┌─────────────────┐
│    CLIENT 1     │                │    CLIENT 2     │
│  ┌───────────┐  │                │  ┌───────────┐  │
│  │  Pygame   │  │                │  │  Pygame   │  │
│  │ Renderer  │  │                │  │ Renderer  │  │
│  └───────────┘  │                │  └───────────┘  │
└─────────────────┘                └─────────────────┘
```

### Why Server Authority?

**Security**: Clients can only send input intentions (`"I want to move left"`), not their actual positions. This prevents:
- Speed hacking (moving faster than allowed)
- Teleportation (jumping to coin positions)
- Score manipulation (claiming coins they didn't collect)

The server:
1. Receives input from clients
2. Calculates new positions based on game rules
3. Validates all movements (boundary checks)
4. Detects collisions (player vs coin)
5. Awards points when verified
6. Broadcasts authoritative state to all clients

## Network Simulation

### Artificial Latency (200ms)

This implementation includes **200ms simulated network latency** on all communications. This is intentional to:

1. Demonstrate real-world networking challenges
2. Show how interpolation and prediction improve player experience
3. Prove that the game works correctly even with network delays

In production, you would remove this artificial delay, but the interpolation and prediction systems would still help with natural network latency.

### Message Flow

```
Client Input → [200ms delay] → Server Processing → [200ms delay] → Client Render
```

Total round-trip: ~400ms (simulated)

## Smoothness: Entity Interpolation

### The Problem

Without interpolation, remote players would appear to "teleport" between positions as updates arrive at discrete intervals (every 50ms).

### The Solution

**Entity Interpolation** stores a buffer of recent position snapshots and smoothly interpolates between them:

```python
# Simplified interpolation logic
render_time = current_time - 100ms  # Render slightly behind latest data
position = lerp(previous_snapshot, next_snapshot, interpolation_factor)
```

This creates smooth visual movement even when:
- Updates are delayed by network latency
- Updates arrive at irregular intervals
- Some updates are dropped

### Client-Side Prediction

For the local player, we use **client-side prediction**:

1. Player presses a key
2. Client immediately moves the player locally (prediction)
3. Input is sent to server
4. Server calculates authoritative position
5. Client receives correction
6. Client smoothly reconciles any difference

This makes controls feel responsive despite network delays.

## File Structure

```
coin-collector-multiplayer/
├── server/
│   ├── server.py           # WebSocket server, game loop
│   ├── game_state.py       # Authoritative game state management
│   └── requirements.txt    # Server dependencies
├── client/
│   ├── client.py           # Main client, game loop
│   ├── renderer.py         # Pygame rendering
│   ├── network.py          # WebSocket client, message handling
│   ├── interpolation.py    # Entity interpolation logic
│   └── requirements.txt    # Client dependencies
├── shared/
│   └── constants.py        # Shared game constants
├── README.md               # This file
└── .gitignore
```

## Configuration

Game constants can be modified in `shared/constants.py`:

```python
# Game area
GAME_WIDTH = 800
GAME_HEIGHT = 600

# Player settings
PLAYER_RADIUS = 15
PLAYER_SPEED = 200  # pixels per second

# Coin settings
COIN_RADIUS = 10
COIN_SPAWN_INTERVAL = 3.0  # seconds
MAX_COINS = 5

# Network
NETWORK_DELAY_MS = 200  # simulated latency
STATE_BROADCAST_RATE = 20  # updates per second

# Game rules
GAME_DURATION = 60  # seconds (None for unlimited)
WINNING_SCORE = 10  # points to win
```

## Troubleshooting

### "Could not connect to server"
- Ensure the server is running before starting clients
- Check that port 8765 is not blocked by a firewall
- Verify `SERVER_HOST` in `constants.py` matches your setup

### "Game is full"
- Only 2 players can connect at a time
- Restart the server to reset

### Choppy remote player movement
- This is expected with 200ms latency simulation
- Interpolation should still provide reasonably smooth movement
- To reduce choppiness, decrease `NETWORK_DELAY_MS` in constants

### High CPU usage
- The game runs at 60 FPS
- This is normal for real-time games
- Close other applications if needed

## Assumptions Made

1. **Local Network Play**: Designed for localhost or LAN play
2. **2 Players Only**: The lobby waits for exactly 2 players
3. **Game Duration**: 60 seconds or first to 10 points
4. **Single Game Session**: Server runs one game at a time
5. **No Reconnection**: Disconnected players cannot rejoin
6. **No Persistent Storage**: Scores are not saved between sessions

## Technical Notes

### Thread Safety
- Network communication runs in a separate thread
- Message queues use locks for thread-safe access
- Pygame runs on the main thread (required by Pygame)

### Performance
- Server tick rate: 60 Hz
- State broadcast rate: 20 Hz (every 50ms)
- Client render rate: 60 FPS
- Input send rate: 20 Hz

## License

This project is for educational purposes.

## Acknowledgments

Built as a demonstration of real-time multiplayer game networking concepts including:
- Server-authoritative game design
- Client-side prediction
- Entity interpolation
- Network latency handling
