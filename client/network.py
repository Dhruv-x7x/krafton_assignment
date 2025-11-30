"""
Network handler for the Coin Collector game client.
Manages WebSocket connection to the server with simulated latency.
"""

import asyncio
import json
import time
import threading
from collections import deque
from dataclasses import dataclass
from typing import Callable, Optional, Dict, Any
from queue import Queue, Empty

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from shared.constants import (
    SERVER_HOST, SERVER_PORT, NETWORK_DELAY_MS, INPUT_SEND_RATE
)

# Websockets import - will be available after installing dependencies
try:
    import websockets
    from websockets.client import WebSocketClientProtocol
except ImportError:
    websockets = None
    WebSocketClientProtocol = None


@dataclass
class DelayedMessage:
    """A message that will be delivered after a delay."""
    delivery_time: float
    message: dict


class DelayedMessageQueue:
    """
    Queue for simulating network latency on incoming messages.
    Messages are held for NETWORK_DELAY_MS before being made available.
    """
    
    def __init__(self, delay_ms: int = NETWORK_DELAY_MS):
        self.delay = delay_ms / 1000.0
        self.queue: deque = deque()
        self.lock = threading.Lock()
    
    def add_message(self, message: dict) -> None:
        """Add a message to the delay queue."""
        delivery_time = time.time() + self.delay
        with self.lock:
            self.queue.append(DelayedMessage(delivery_time, message))
    
    def get_ready_messages(self) -> list:
        """Get all messages that are ready to be delivered."""
        ready = []
        current_time = time.time()
        with self.lock:
            while self.queue and self.queue[0].delivery_time <= current_time:
                ready.append(self.queue.popleft().message)
        return ready
    
    def clear(self) -> None:
        """Clear all pending messages."""
        with self.lock:
            self.queue.clear()


class NetworkClient:
    """
    WebSocket client for communicating with the game server.
    Runs in a separate thread to not block the game loop.
    """
    
    def __init__(self, host: str = SERVER_HOST, port: int = SERVER_PORT):
        self.host = host
        self.port = port
        self.uri = f"ws://{host}:{port}"
        
        # Connection state
        self.connected = False
        self.websocket: Optional[WebSocketClientProtocol] = None
        
        # Message queues
        self.incoming_queue = DelayedMessageQueue()
        self.outgoing_queue: Queue = Queue()
        
        # Threading
        self.thread: Optional[threading.Thread] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.running = False
        self._stop_event: Optional[asyncio.Event] = None
        
        # Input throttling
        self.last_input_send_time = 0
        self.input_send_interval = 1.0 / INPUT_SEND_RATE
        
        # Callbacks
        self.on_disconnect: Optional[Callable] = None
        self.on_connect: Optional[Callable] = None
    
    def start(self) -> None:
        """Start the network client in a separate thread."""
        if self.thread is not None and self.thread.is_alive():
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._run_thread, daemon=True)
        self.thread.start()
    
    def stop(self) -> None:
        """Stop the network client gracefully."""
        self.running = False
        
        # Signal the stop event if we have a loop
        if self.loop and self._stop_event:
            try:
                self.loop.call_soon_threadsafe(self._stop_event.set)
            except RuntimeError:
                pass  # Loop might already be closed
        
        # Close the websocket connection gracefully
        if self.websocket and self.loop:
            try:
                future = asyncio.run_coroutine_threadsafe(
                    self._close_websocket(), self.loop
                )
                future.result(timeout=1.0)
            except Exception:
                pass  # Ignore errors during shutdown
        
        if self.thread:
            self.thread.join(timeout=2.0)
    
    async def _close_websocket(self) -> None:
        """Close the websocket connection gracefully."""
        if self.websocket:
            try:
                await self.websocket.close()
            except Exception:
                pass
    
    def _run_thread(self) -> None:
        """Thread entry point - runs the asyncio event loop."""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self._stop_event = asyncio.Event()
        
        try:
            self.loop.run_until_complete(self._connect_and_run())
        except Exception as e:
            if self.running:  # Only print error if we didn't intentionally stop
                print(f"Network thread error: {e}")
        finally:
            # Cancel all pending tasks
            try:
                pending = asyncio.all_tasks(self.loop)
                for task in pending:
                    task.cancel()
                # Give tasks a chance to clean up
                if pending:
                    self.loop.run_until_complete(
                        asyncio.gather(*pending, return_exceptions=True)
                    )
            except Exception:
                pass
            
            try:
                self.loop.close()
            except Exception:
                pass
            self.connected = False
    
    async def _connect_and_run(self) -> None:
        """Connect to server and handle messages."""
        if websockets is None:
            print("Error: websockets library not installed!")
            return
        
        try:
            print(f"Connecting to {self.uri}...")
            async with websockets.connect(
                self.uri,
                ping_interval=20,
                ping_timeout=20
            ) as websocket:
                self.websocket = websocket
                self.connected = True
                print("Connected to server!")
                
                if self.on_connect:
                    self.on_connect()
                
                # Run send and receive tasks concurrently with stop event
                try:
                    await asyncio.gather(
                        self._receive_messages(),
                        self._send_messages(),
                        self._wait_for_stop()
                    )
                except asyncio.CancelledError:
                    pass  # Expected when stopping
        except ConnectionRefusedError:
            print(f"Could not connect to server at {self.uri}")
            print("Make sure the server is running!")
        except asyncio.CancelledError:
            pass  # Expected when stopping
        except Exception as e:
            if self.running:  # Only print error if we didn't intentionally stop
                print(f"Connection error: {e}")
        finally:
            self.connected = False
            self.websocket = None
            if self.on_disconnect and self.running:
                self.on_disconnect()
    
    async def _wait_for_stop(self) -> None:
        """Wait for the stop signal."""
        if self._stop_event:
            await self._stop_event.wait()
            raise asyncio.CancelledError()
    
    async def _receive_messages(self) -> None:
        """Receive messages from server and add to delayed queue."""
        try:
            async for message in self.websocket:
                if not self.running:
                    break
                try:
                    data = json.loads(message)
                    # Add to delayed queue to simulate latency
                    self.incoming_queue.add_message(data)
                except json.JSONDecodeError:
                    print("Received invalid JSON from server")
        except asyncio.CancelledError:
            pass  # Expected when stopping
        except websockets.exceptions.ConnectionClosed:
            if self.running:
                print("Server connection closed")
    
    async def _send_messages(self) -> None:
        """Send queued messages to server."""
        try:
            while self.running and self.connected:
                try:
                    # Check for messages to send
                    try:
                        message = self.outgoing_queue.get_nowait()
                        if self.websocket:
                            await self.websocket.send(json.dumps(message))
                    except Empty:
                        pass
                    
                    await asyncio.sleep(0.01)  # Small delay to prevent busy loop
                except websockets.exceptions.ConnectionClosed:
                    break
        except asyncio.CancelledError:
            pass  # Expected when stopping
    
    def send_input(self, dx: int, dy: int, force: bool = False) -> None:
        """
        Send player input to server.
        Throttled to INPUT_SEND_RATE per second unless force=True.
        """
        current_time = time.time()
        
        if not force and current_time - self.last_input_send_time < self.input_send_interval:
            return
        
        self.last_input_send_time = current_time
        self.outgoing_queue.put({
            "type": "input",
            "dx": dx,
            "dy": dy
        })
    
    def get_messages(self) -> list:
        """Get all messages that have passed their delay time."""
        return self.incoming_queue.get_ready_messages()
    
    def is_connected(self) -> bool:
        """Check if connected to server."""
        return self.connected


class GameNetworkState:
    """
    Manages the network-related game state on the client side.
    Processes messages from the server and maintains local state.
    """
    
    def __init__(self):
        self.player_id: Optional[int] = None
        self.player_color: str = "gray"
        self.waiting_for_players = True
        self.game_started = False
        self.game_over = False
        self.winner: Optional[int] = None
        self.final_scores: Dict[int, int] = {}
        
        # Latest state from server
        self.last_server_state: Optional[dict] = None
        self.last_state_timestamp: float = 0
    
    def process_message(self, message: dict) -> None:
        """Process a message from the server."""
        msg_type = message.get("type")
        
        if msg_type == "assign":
            self.player_id = message.get("player_id")
            self.player_color = message.get("color", "gray")
            print(f"Assigned as Player {self.player_id} ({self.player_color})")
        
        elif msg_type == "waiting":
            self.waiting_for_players = True
            print(message.get("message", "Waiting..."))
        
        elif msg_type == "game_start":
            self.waiting_for_players = False
            self.game_started = True
            print("Game started!")
        
        elif msg_type == "state":
            self.last_server_state = message
            self.last_state_timestamp = message.get("timestamp", time.time())
            if message.get("game_state") == "playing":
                self.waiting_for_players = False
                self.game_started = True
        
        elif msg_type == "coin_collected":
            player_id = message.get("player_id")
            new_score = message.get("new_score")
            print(f"Player {player_id} collected a coin! Score: {new_score}")
        
        elif msg_type == "game_over":
            self.game_over = True
            self.winner = message.get("winner")
            self.final_scores = message.get("final_scores", {})
            print(f"Game Over! Winner: Player {self.winner}")
        
        elif msg_type == "player_disconnected":
            player_id = message.get("player_id")
            print(f"Player {player_id} disconnected")
        
        elif msg_type == "error":
            print(f"Server error: {message.get('message')}")
