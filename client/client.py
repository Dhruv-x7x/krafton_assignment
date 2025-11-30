"""
Main Client for the Coin Collector multiplayer game.
Handles input, game loop, and coordinates network and rendering.
"""

import pygame
import sys
import time
from typing import Dict, List, Optional, Tuple

import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from shared.constants import (
    GAME_WIDTH, GAME_HEIGHT, PLAYER_RADIUS, PLAYER_SPEED,
    SERVER_HOST, SERVER_PORT, GameStates
)
from network import NetworkClient, GameNetworkState
from renderer import GameRenderer
from interpolation import InterpolatedEntity, LocalPlayerPredictor, EntityManager


class CoinCollectorClient:
    """
    Main game client that coordinates all components.
    """
    
    def __init__(self):
        # Initialize components
        self.renderer = GameRenderer()
        self.network = NetworkClient(SERVER_HOST, SERVER_PORT)
        self.network_state = GameNetworkState()
        
        # Local player state
        self.local_predictor = LocalPlayerPredictor(PLAYER_SPEED)
        
        # Remote entities (other players)
        self.entity_manager = EntityManager()
        
        # Coins (not interpolated, just direct from server)
        self.coins: List[dict] = []
        
        # Input state
        self.current_dx = 0
        self.current_dy = 0
        self.last_dx = 0
        self.last_dy = 0
        
        # Game state
        self.running = True
        self.game_time = 0
        
        # Set up network callbacks
        self.network.on_disconnect = self._on_disconnect
        self.network.on_connect = self._on_connect
        
        self.disconnected = False
    
    def _on_connect(self) -> None:
        """Called when connected to server."""
        print("Connected to server!")
    
    def _on_disconnect(self) -> None:
        """Called when disconnected from server."""
        print("Disconnected from server!")
        self.disconnected = True
    
    def handle_events(self) -> None:
        """Handle Pygame events."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
    
    def get_input(self) -> Tuple[int, int]:
        """
        Get current input state from keyboard.
        Returns (dx, dy) where each is -1, 0, or 1.
        """
        keys = pygame.key.get_pressed()
        
        dx = 0
        dy = 0
        
        # Horizontal movement (left/right)
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            dx -= 1
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            dx += 1
        
        # Vertical movement (up/down)
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            dy -= 1
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            dy += 1
        
        return dx, dy
    
    def process_server_messages(self) -> None:
        """Process all available messages from the server."""
        messages = self.network.get_messages()
        
        for message in messages:
            self.network_state.process_message(message)
            
            # Handle state updates
            if message.get("type") == "state":
                self._handle_state_update(message)
            elif message.get("type") == "assign":
                # Set initial position for local player
                x = message.get("x", GAME_WIDTH // 2)
                y = message.get("y", GAME_HEIGHT // 2)
                self.local_predictor.set_position(x, y)
    
    def _handle_state_update(self, state: dict) -> None:
        """Handle a game state update from the server."""
        timestamp = state.get("timestamp", time.time())
        players = state.get("players", [])
        self.coins = state.get("coins", [])
        self.game_time = state.get("game_time", 0)
        
        for player_data in players:
            player_id = player_data.get("id")
            x = player_data.get("x", 0)
            y = player_data.get("y", 0)
            score = player_data.get("score", 0)
            color = player_data.get("color", "gray")
            
            if player_id == self.network_state.player_id:
                # This is the local player - apply server correction
                self.local_predictor.apply_server_correction(x, y)
                # Update score from server (authoritative)
                self._local_player_score = score
            else:
                # Remote player - add to interpolation buffer
                self.entity_manager.update_entity(
                    player_id, timestamp, x, y, score, color
                )
    
    def update(self, delta_time: float) -> None:
        """Update game state."""
        # Get input
        self.current_dx, self.current_dy = self.get_input()
        
        # Send input to server if it changed or periodically
        if (self.current_dx != self.last_dx or self.current_dy != self.last_dy):
            self.network.send_input(self.current_dx, self.current_dy, force=True)
        else:
            self.network.send_input(self.current_dx, self.current_dy)
        
        self.last_dx = self.current_dx
        self.last_dy = self.current_dy
        
        # Update local player prediction
        self.local_predictor.set_input(self.current_dx, self.current_dy)
        self.local_predictor.update(
            delta_time, GAME_WIDTH, GAME_HEIGHT, PLAYER_RADIUS
        )
        
        # Process server messages
        self.process_server_messages()
    
    def render(self) -> None:
        """Render the current frame."""
        if self.disconnected:
            self.renderer.render_disconnected_screen()
            return
        
        if self.network_state.game_over:
            self.renderer.render_game_over_screen(
                self.network_state.winner,
                self.network_state.final_scores,
                self.network_state.player_id or 0
            )
            return
        
        if not self.network.is_connected():
            self.renderer.render_connecting_screen()
            return
        
        if self.network_state.waiting_for_players:
            self.renderer.render_waiting_screen()
            return
        
        # Get interpolated positions for remote players
        current_time = time.time()
        remote_positions = self.entity_manager.get_interpolated_positions(current_time)
        
        # Get local player position
        local_pos = (self.local_predictor.x, self.local_predictor.y)
        
        # Render the game
        self.renderer.render_game(
            local_player_pos=local_pos,
            local_player_id=self.network_state.player_id or 0,
            local_player_color=self.network_state.player_color,
            local_player_score=getattr(self, '_local_player_score', 0),
            remote_players=remote_positions,
            coins=self.coins,
            game_time=self.game_time
        )
    
    def run(self) -> None:
        """Main game loop."""
        print("Starting Coin Collector Client...")
        print(f"Connecting to server at {SERVER_HOST}:{SERVER_PORT}")
        
        # Start network client in background thread
        self.network.start()
        
        # Initialize local player score
        self._local_player_score = 0
        
        try:
            while self.running:
                # Handle events
                self.handle_events()
                
                # Calculate delta time
                delta_time = self.renderer.tick(60)
                
                # Update game state
                if self.network_state.game_started and not self.network_state.game_over:
                    self.update(delta_time)
                else:
                    # Still process messages even when not playing
                    self.process_server_messages()
                
                # Render
                self.render()
        
        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            self.network.stop()
            self.renderer.quit()


def main():
    """Main entry point."""
    client = CoinCollectorClient()
    client.run()


if __name__ == "__main__":
    main()
