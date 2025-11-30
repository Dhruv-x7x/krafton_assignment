"""
Main WebSocket Server for the Coin Collector multiplayer game.
Implements server-authoritative game logic with simulated network latency.
"""

import asyncio
import json
import time
from collections import deque
from dataclasses import dataclass
from typing import Dict, Optional, Set
import websockets
from websockets.server import WebSocketServerProtocol

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from shared.constants import (
    SERVER_HOST, SERVER_PORT, NETWORK_DELAY_MS, STATE_BROADCAST_RATE,
    PLAYER_COLOR_NAMES, GameStates, MessageTypes
)
from game_state import GameState


@dataclass
class DelayedMessage:
    """A message that will be processed after a delay."""
    process_time: float
    message: dict
    player_id: int


class DelayedMessageQueue:
    """
    Queue for simulating network latency.
    Messages are held for NETWORK_DELAY_MS before being processed.
    """
    
    def __init__(self, delay_ms: int = NETWORK_DELAY_MS):
        self.delay = delay_ms / 1000.0
        self.queue: deque = deque()
    
    def add_message(self, message: dict, player_id: int) -> None:
        """Add a message to the delay queue."""
        process_time = time.time() + self.delay
        self.queue.append(DelayedMessage(process_time, message, player_id))
    
    def get_ready_messages(self) -> list:
        """Get all messages that are ready to be processed."""
        ready = []
        current_time = time.time()
        while self.queue and self.queue[0].process_time <= current_time:
            ready.append(self.queue.popleft())
        return ready


@dataclass
class DelayedBroadcast:
    """A broadcast message that will be sent after a delay."""
    send_time: float
    message: str
    exclude_player_id: Optional[int] = None


class DelayedBroadcastQueue:
    """
    Queue for simulating network latency on outgoing broadcasts.
    Messages are held for NETWORK_DELAY_MS before being sent to clients.
    """
    
    def __init__(self, delay_ms: int = NETWORK_DELAY_MS):
        self.delay = delay_ms / 1000.0
        self.queue: deque = deque()
    
    def add_broadcast(self, message: dict, exclude: Optional[int] = None) -> None:
        """Add a broadcast message to the delay queue."""
        send_time = time.time() + self.delay
        message_str = json.dumps(message)
        self.queue.append(DelayedBroadcast(send_time, message_str, exclude))
    
    def get_ready_broadcasts(self) -> list:
        """Get all broadcasts that are ready to be sent."""
        ready = []
        current_time = time.time()
        while self.queue and self.queue[0].send_time <= current_time:
            ready.append(self.queue.popleft())
        return ready


class GameServer:
    """
    Main game server handling WebSocket connections and game logic.
    """
    
    def __init__(self):
        self.game_state = GameState()
        self.clients: Dict[int, WebSocketServerProtocol] = {}
        self.available_player_ids = [1, 2]  # Pool of available player IDs
        self.input_queue = DelayedMessageQueue()
        self.broadcast_queue = DelayedBroadcastQueue()  # New: delayed broadcast queue
        self.running = False
        self.last_update_time = time.time()
        self.last_broadcast_time = time.time()
        self.broadcast_interval = 1.0 / STATE_BROADCAST_RATE
        
    async def register_client(self, websocket: WebSocketServerProtocol) -> Optional[int]:
        """
        Register a new client connection.
        Returns the assigned player ID, or None if game is full.
        """
        if len(self.clients) >= 2 or not self.available_player_ids:
            await websocket.send(json.dumps({
                "type": "error",
                "message": "Game is full. Only 2 players allowed."
            }))
            return None
        
        # Get an available player ID from the pool
        player_id = self.available_player_ids.pop(0)
        
        self.clients[player_id] = websocket
        player = self.game_state.add_player(player_id)
        
        # Send player assignment
        await websocket.send(json.dumps({
            "type": MessageTypes.ASSIGN,
            "player_id": player_id,
            "color": player.color,
            "x": player.x,
            "y": player.y
        }))
        
        print(f"Player {player_id} connected. Total players: {len(self.clients)}")
        
        # Check if we can start the game
        if self.game_state.can_start_game():
            await self.start_game()
        else:
            # Notify client they're waiting
            await websocket.send(json.dumps({
                "type": "waiting",
                "message": "Waiting for another player to join..."
            }))
        
        return player_id
    
    async def unregister_client(self, player_id: int) -> None:
        """Handle client disconnection."""
        if player_id in self.clients:
            del self.clients[player_id]
            self.game_state.remove_player(player_id)
            # Return the player ID to the available pool
            if player_id not in self.available_player_ids:
                self.available_player_ids.append(player_id)
                self.available_player_ids.sort()  # Keep IDs in order
            print(f"Player {player_id} disconnected. Total players: {len(self.clients)}")
            
            # Notify other players (queue for delayed send)
            self.broadcast_queue.add_broadcast({
                "type": MessageTypes.PLAYER_DISCONNECTED,
                "player_id": player_id
            })
    
    async def start_game(self) -> None:
        """Start the game and notify all clients."""
        self.game_state.start_game()
        print("Game starting!")
        
        # Queue game start broadcast with delay
        self.broadcast_queue.add_broadcast({
            "type": MessageTypes.GAME_START,
            "timestamp": time.time()
        })
    
    def queue_broadcast(self, message: dict, exclude: Optional[int] = None) -> None:
        """Queue a message for delayed broadcast to all clients."""
        self.broadcast_queue.add_broadcast(message, exclude)
    
    async def send_delayed_broadcasts(self) -> None:
        """Send all broadcasts that have passed their delay time."""
        ready_broadcasts = self.broadcast_queue.get_ready_broadcasts()
        for broadcast in ready_broadcasts:
            await self._send_to_clients(broadcast.message, broadcast.exclude_player_id)
    
    async def _send_to_clients(self, message_str: str, exclude: Optional[int] = None) -> None:
        """Actually send a message to all connected clients."""
        if not self.clients:
            return
        
        tasks = []
        for player_id, websocket in list(self.clients.items()):
            if exclude and player_id == exclude:
                continue
            try:
                tasks.append(websocket.send(message_str))
            except websockets.exceptions.ConnectionClosed:
                pass
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def broadcast(self, message: dict, exclude: Optional[int] = None) -> None:
        """
        Queue a message for delayed broadcast to all connected clients.
        The actual sending happens in send_delayed_broadcasts().
        """
        self.broadcast_queue.add_broadcast(message, exclude)
    
    async def broadcast_state(self) -> None:
        """Queue the current game state for delayed broadcast to all clients."""
        state = self.game_state.get_state_snapshot()
        self.broadcast_queue.add_broadcast(state)
    
    def process_input(self, player_id: int, message: dict) -> None:
        """Queue an input message for delayed processing."""
        self.input_queue.add_message(message, player_id)
    
    def process_delayed_inputs(self) -> None:
        """Process all inputs that have passed their delay time."""
        ready_messages = self.input_queue.get_ready_messages()
        for delayed_msg in ready_messages:
            if delayed_msg.message.get("type") == MessageTypes.INPUT:
                dx = delayed_msg.message.get("dx", 0)
                dy = delayed_msg.message.get("dy", 0)
                self.game_state.update_player_input(delayed_msg.player_id, dx, dy)
    
    async def handle_client(self, websocket: WebSocketServerProtocol) -> None:
        """Handle a single client connection."""
        player_id = await self.register_client(websocket)
        if player_id is None:
            return
        
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    # Queue the input for delayed processing
                    self.process_input(player_id, data)
                except json.JSONDecodeError:
                    print(f"Invalid JSON from player {player_id}")
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            await self.unregister_client(player_id)
    
    async def game_loop(self) -> None:
        """Main game loop - updates game state and broadcasts to clients."""
        self.running = True
        target_tick_rate = 60  # 60 ticks per second
        tick_interval = 1.0 / target_tick_rate
        
        while self.running:
            loop_start = time.time()
            
            # Calculate delta time
            current_time = time.time()
            delta_time = current_time - self.last_update_time
            self.last_update_time = current_time
            
            # Process delayed inputs
            self.process_delayed_inputs()
            
            # Send any delayed broadcasts that are ready
            await self.send_delayed_broadcasts()
            
            # Only process game logic if we have clients and game is playing
            if self.clients and self.game_state.state == GameStates.PLAYING:
                events = self.game_state.update(delta_time)
                
                # Queue any events for broadcast (coin collected, etc.)
                for event in events:
                    self.queue_broadcast(event)
                
                # Check if game ended
                if self.game_state.state == GameStates.ENDED:
                    self.queue_broadcast({
                        "type": MessageTypes.GAME_OVER,
                        "winner": self.game_state.winner,
                        "final_scores": {
                            p.id: p.score for p in self.game_state.players.values()
                        }
                    })
            
            # Broadcast state at the configured rate (only if game is playing)
            if (self.clients and 
                self.game_state.state == GameStates.PLAYING and
                current_time - self.last_broadcast_time >= self.broadcast_interval):
                await self.broadcast_state()
                self.last_broadcast_time = current_time
            
            # Sleep to maintain tick rate
            elapsed = time.time() - loop_start
            sleep_time = max(0, tick_interval - elapsed)
            await asyncio.sleep(sleep_time)
    
    async def start(self) -> None:
        """Start the game server."""
        print(f"Starting Coin Collector server on ws://{SERVER_HOST}:{SERVER_PORT}")
        print(f"Simulated network latency: {NETWORK_DELAY_MS}ms")
        print("Waiting for players to connect...")
        
        async with websockets.serve(
            self.handle_client,
            SERVER_HOST,
            SERVER_PORT,
            ping_interval=20,
            ping_timeout=20
        ):
            await self.game_loop()


async def main():
    """Main entry point."""
    server = GameServer()
    await server.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServer shutting down...")
