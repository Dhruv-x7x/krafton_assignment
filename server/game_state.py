"""
Game State Management for the Coin Collector server.
Handles all game logic including player positions, coins, scores, and collisions.
This is the authoritative source of truth for the game.
"""

import math
import random
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from shared.constants import (
    GAME_WIDTH, GAME_HEIGHT, PLAYER_RADIUS, PLAYER_SPEED,
    COIN_RADIUS, COIN_SPAWN_INTERVAL, MAX_COINS,
    PLAYER_COLOR_NAMES, GameStates, GAME_DURATION, WINNING_SCORE
)


@dataclass
class Player:
    """Represents a player in the game."""
    id: int
    x: float
    y: float
    score: int = 0
    color: str = "blue"
    # Current input state (direction the player wants to move)
    dx: int = 0  # -1 (left), 0 (none), 1 (right)
    dy: int = 0  # -1 (up), 0 (none), 1 (down)
    
    def to_dict(self) -> dict:
        """Convert player to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "x": round(self.x, 2),
            "y": round(self.y, 2),
            "score": self.score,
            "color": self.color
        }


@dataclass
class Coin:
    """Represents a coin in the game."""
    id: int
    x: float
    y: float
    
    def to_dict(self) -> dict:
        """Convert coin to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "x": round(self.x, 2),
            "y": round(self.y, 2)
        }


class GameState:
    """
    Manages the complete game state.
    This is the authoritative source of truth - all game logic happens here.
    """
    
    def __init__(self):
        self.players: Dict[int, Player] = {}
        self.coins: Dict[int, Coin] = {}
        self.state: str = GameStates.WAITING
        self.next_coin_id: int = 1
        self.last_coin_spawn_time: float = 0
        self.game_start_time: Optional[float] = None
        self.winner: Optional[int] = None
        
    def add_player(self, player_id: int) -> Player:
        """
        Add a new player to the game.
        Returns the created player object.
        """
        # Spawn player at a random position within safe bounds
        spawn_x = random.uniform(PLAYER_RADIUS + 50, GAME_WIDTH - PLAYER_RADIUS - 50)
        spawn_y = random.uniform(PLAYER_RADIUS + 50, GAME_HEIGHT - PLAYER_RADIUS - 50)
        
        # Assign color based on player ID
        color = PLAYER_COLOR_NAMES.get(player_id, "gray")
        
        player = Player(
            id=player_id,
            x=spawn_x,
            y=spawn_y,
            color=color
        )
        self.players[player_id] = player
        return player
    
    def remove_player(self, player_id: int) -> None:
        """Remove a player from the game completely."""
        if player_id in self.players:
            del self.players[player_id]
    
    def get_connected_player_count(self) -> int:
        """Get the number of connected players."""
        return len(self.players)
    
    def can_start_game(self) -> bool:
        """Check if the game can start (exactly 2 connected players)."""
        return self.get_connected_player_count() >= 2 and self.state == GameStates.WAITING
    
    def start_game(self) -> None:
        """Start the game."""
        self.state = GameStates.PLAYING
        self.game_start_time = time.time()
        self.last_coin_spawn_time = time.time()
        # Spawn initial coins
        for _ in range(3):
            self.spawn_coin()
    
    def update_player_input(self, player_id: int, dx: int, dy: int) -> None:
        """
        Update a player's input state.
        This is the only thing clients can control.
        """
        if player_id in self.players:
            player = self.players[player_id]
            # Clamp values to valid range
            player.dx = max(-1, min(1, dx))
            player.dy = max(-1, min(1, dy))
    
    def update(self, delta_time: float) -> List[dict]:
        """
        Update the game state by one tick.
        Returns a list of events that occurred (e.g., coin collected).
        """
        if self.state != GameStates.PLAYING:
            return []
        
        events = []
        current_time = time.time()
        
        # Check for game over conditions
        if GAME_DURATION and self.game_start_time:
            elapsed = current_time - self.game_start_time
            if elapsed >= GAME_DURATION:
                self._end_game()
                return events
        
        # Update player positions based on their input
        for player in self.players.values():
            # Calculate movement
            if player.dx != 0 or player.dy != 0:
                # Normalize diagonal movement
                magnitude = math.sqrt(player.dx ** 2 + player.dy ** 2)
                normalized_dx = player.dx / magnitude
                normalized_dy = player.dy / magnitude
                
                # Apply movement
                new_x = player.x + normalized_dx * PLAYER_SPEED * delta_time
                new_y = player.y + normalized_dy * PLAYER_SPEED * delta_time
                
                # Clamp to game boundaries
                player.x = max(PLAYER_RADIUS, min(GAME_WIDTH - PLAYER_RADIUS, new_x))
                player.y = max(PLAYER_RADIUS, min(GAME_HEIGHT - PLAYER_RADIUS, new_y))
        
        # Check for coin collisions
        # Use a set to track collected coins to prevent double collection
        coins_to_remove = set()
        for coin_id, coin in self.coins.items():
            if coin_id in coins_to_remove:
                continue  # Skip already collected coins
            for player in self.players.values():
                if self._check_collision(player.x, player.y, PLAYER_RADIUS,
                                        coin.x, coin.y, COIN_RADIUS):
                    player.score += 1
                    coins_to_remove.add(coin_id)
                    events.append({
                        "type": "coin_collected",
                        "player_id": player.id,
                        "coin_id": coin_id,
                        "new_score": player.score
                    })
                    
                    # Check for win by score
                    if WINNING_SCORE and player.score >= WINNING_SCORE:
                        self._end_game(player.id)
                    break
        
        # Remove collected coins
        for coin_id in coins_to_remove:
            del self.coins[coin_id]
        
        # Spawn new coins if needed
        if (current_time - self.last_coin_spawn_time >= COIN_SPAWN_INTERVAL and
                len(self.coins) < MAX_COINS):
            self.spawn_coin()
            self.last_coin_spawn_time = current_time
        
        return events
    
    def _end_game(self, winner_id: Optional[int] = None) -> None:
        """End the game and determine winner."""
        self.state = GameStates.ENDED
        
        if winner_id:
            self.winner = winner_id
        else:
            # Determine winner by score
            max_score = -1
            for player in self.players.values():
                if player.score > max_score:
                    max_score = player.score
                    self.winner = player.id
    
    def spawn_coin(self) -> Optional[Coin]:
        """Spawn a new coin at a random position."""
        if len(self.coins) >= MAX_COINS:
            return None
        
        # Find a valid spawn position (not too close to players)
        max_attempts = 50
        for _ in range(max_attempts):
            x = random.uniform(COIN_RADIUS + 10, GAME_WIDTH - COIN_RADIUS - 10)
            y = random.uniform(COIN_RADIUS + 10, GAME_HEIGHT - COIN_RADIUS - 10)
            
            # Check distance from all players
            valid = True
            for player in self.players.values():
                dist = math.sqrt((x - player.x) ** 2 + (y - player.y) ** 2)
                if dist < PLAYER_RADIUS + COIN_RADIUS + 50:  # Give some buffer
                    valid = False
                    break
            
            if valid:
                coin = Coin(id=self.next_coin_id, x=x, y=y)
                self.coins[self.next_coin_id] = coin
                self.next_coin_id += 1
                return coin
        
        # If we couldn't find a valid position, spawn anyway
        x = random.uniform(COIN_RADIUS + 10, GAME_WIDTH - COIN_RADIUS - 10)
        y = random.uniform(COIN_RADIUS + 10, GAME_HEIGHT - COIN_RADIUS - 10)
        coin = Coin(id=self.next_coin_id, x=x, y=y)
        self.coins[self.next_coin_id] = coin
        self.next_coin_id += 1
        return coin
    
    def _check_collision(self, x1: float, y1: float, r1: float,
                         x2: float, y2: float, r2: float) -> bool:
        """Check if two circles are colliding."""
        distance = math.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)
        return distance < (r1 + r2)
    
    def get_state_snapshot(self) -> dict:
        """
        Get a complete snapshot of the current game state.
        This is what gets broadcast to clients.
        """
        return {
            "type": "state",
            "timestamp": time.time(),
            "game_state": self.state,
            "players": [p.to_dict() for p in self.players.values()],
            "coins": [c.to_dict() for c in self.coins.values()],
            "game_time": (time.time() - self.game_start_time) if self.game_start_time else 0,
            "winner": self.winner
        }
    
    def get_remaining_time(self) -> Optional[float]:
        """Get remaining game time in seconds."""
        if not GAME_DURATION or not self.game_start_time:
            return None
        elapsed = time.time() - self.game_start_time
        return max(0, GAME_DURATION - elapsed)
