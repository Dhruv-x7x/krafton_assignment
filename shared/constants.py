"""
Shared constants for the Coin Collector multiplayer game.
These constants are used by both server and client.
"""

# Game area dimensions
GAME_WIDTH = 800
GAME_HEIGHT = 600

# Player configuration
PLAYER_RADIUS = 15  # Circle radius in pixels
PLAYER_SPEED = 200  # Pixels per second

# Coin configuration
COIN_RADIUS = 10  # Circle radius in pixels
COIN_SPAWN_INTERVAL = 3.0  # Seconds between coin spawns
MAX_COINS = 5  # Maximum coins on the map at once

# Network configuration
SERVER_HOST = "localhost"
SERVER_PORT = 8765
NETWORK_DELAY_MS = 200  # Simulated latency in milliseconds
STATE_BROADCAST_RATE = 20  # Server state broadcasts per second (50ms interval)
INPUT_SEND_RATE = 20  # Client input sends per second

# Interpolation configuration
INTERPOLATION_DELAY = 0.1  # Render 100ms behind latest data for smooth interpolation
POSITION_BUFFER_SIZE = 20  # Number of position snapshots to keep

# Player colors (RGB tuples)
PLAYER_COLORS = {
    1: (50, 100, 255),   # Blue for Player 1
    2: (255, 50, 50),    # Red for Player 2
}

PLAYER_COLOR_NAMES = {
    1: "blue",
    2: "red",
}

# Coin color
COIN_COLOR = (255, 215, 0)  # Gold/Yellow

# UI colors
BACKGROUND_COLOR = (30, 30, 40)  # Dark gray
TEXT_COLOR = (255, 255, 255)  # White
WAITING_TEXT_COLOR = (200, 200, 200)  # Light gray

# Game states
class GameStates:
    WAITING = "waiting"
    PLAYING = "playing"
    ENDED = "ended"

# Message types
class MessageTypes:
    # Client -> Server
    INPUT = "input"
    
    # Server -> Client
    STATE = "state"
    ASSIGN = "assign"
    GAME_START = "game_start"
    COIN_COLLECTED = "coin_collected"
    PLAYER_DISCONNECTED = "player_disconnected"
    GAME_OVER = "game_over"

# Game rules
GAME_DURATION = 60  # Game duration in seconds (None for unlimited)
WINNING_SCORE = 10  # Score to win (None for time-based only)
