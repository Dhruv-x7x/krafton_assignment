"""
Entity Interpolation for smooth rendering of remote entities.
Implements linear interpolation between position snapshots to create
smooth visual movement even with delayed/infrequent network updates.
"""

import time
from dataclasses import dataclass, field
from typing import List, Tuple, Optional

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from shared.constants import INTERPOLATION_DELAY, POSITION_BUFFER_SIZE


@dataclass
class PositionSnapshot:
    """A single position snapshot with timestamp."""
    timestamp: float
    x: float
    y: float


class InterpolatedEntity:
    """
    Manages position interpolation for a remote entity.
    Stores a buffer of recent position snapshots and interpolates
    between them to create smooth rendering.
    """
    
    def __init__(self, render_delay: float = INTERPOLATION_DELAY):
        self.position_buffer: List[PositionSnapshot] = []
        self.render_delay = render_delay  # Render behind the latest data for interpolation room
        self.max_buffer_size = POSITION_BUFFER_SIZE
        
        # Current interpolated position
        self.current_x: float = 0.0
        self.current_y: float = 0.0
        
        # Additional entity data
        self.score: int = 0
        self.color: str = "gray"
        self.entity_id: int = 0
    
    def add_snapshot(self, timestamp: float, x: float, y: float) -> None:
        """
        Add a new position snapshot to the buffer.
        Maintains chronological order and limits buffer size.
        """
        snapshot = PositionSnapshot(timestamp, x, y)
        
        # Insert in chronological order (usually at the end)
        if not self.position_buffer or timestamp >= self.position_buffer[-1].timestamp:
            self.position_buffer.append(snapshot)
        else:
            # Find correct insertion point (rare case of out-of-order packets)
            for i, existing in enumerate(self.position_buffer):
                if timestamp < existing.timestamp:
                    self.position_buffer.insert(i, snapshot)
                    break
        
        # Limit buffer size by removing oldest snapshots
        while len(self.position_buffer) > self.max_buffer_size:
            self.position_buffer.pop(0)
    
    def get_interpolated_position(self, current_time: float) -> Tuple[float, float]:
        """
        Get the interpolated position for rendering.
        Returns (x, y) tuple.
        """
        if not self.position_buffer:
            return self.current_x, self.current_y
        
        # Calculate render time (behind the latest data to allow interpolation)
        render_time = current_time - self.render_delay
        
        # Find two snapshots to interpolate between
        before: Optional[PositionSnapshot] = None
        after: Optional[PositionSnapshot] = None
        
        for i, snapshot in enumerate(self.position_buffer):
            if snapshot.timestamp <= render_time:
                before = snapshot
            else:
                after = snapshot
                break
        
        # Handle edge cases
        if before is None and after is None:
            # No snapshots at all - shouldn't happen if buffer is populated
            return self.current_x, self.current_y
        
        if before is None:
            # Render time is before all snapshots - use earliest
            self.current_x = self.position_buffer[0].x
            self.current_y = self.position_buffer[0].y
            return self.current_x, self.current_y
        
        if after is None:
            # Render time is after all snapshots - use latest
            # This can happen if we're not receiving updates fast enough
            self.current_x = before.x
            self.current_y = before.y
            return self.current_x, self.current_y
        
        # Interpolate between before and after
        time_diff = after.timestamp - before.timestamp
        if time_diff <= 0:
            self.current_x = after.x
            self.current_y = after.y
        else:
            # Calculate interpolation factor (0 to 1)
            t = (render_time - before.timestamp) / time_diff
            t = max(0.0, min(1.0, t))  # Clamp to [0, 1]
            
            # Linear interpolation
            self.current_x = before.x + (after.x - before.x) * t
            self.current_y = before.y + (after.y - before.y) * t
        
        return self.current_x, self.current_y
    
    def set_immediate_position(self, x: float, y: float) -> None:
        """Set position immediately without interpolation (for local player)."""
        self.current_x = x
        self.current_y = y
    
    def clear_buffer(self) -> None:
        """Clear the position buffer."""
        self.position_buffer.clear()


class LocalPlayerPredictor:
    """
    Handles client-side prediction for the local player.
    Provides responsive controls while still respecting server authority.
    """
    
    def __init__(self, player_speed: float):
        self.player_speed = player_speed
        
        # Predicted position
        self.x: float = 0.0
        self.y: float = 0.0
        
        # Last confirmed position from server
        self.server_x: float = 0.0
        self.server_y: float = 0.0
        
        # Input state
        self.dx: int = 0
        self.dy: int = 0
        
        # Reconciliation settings
        # With 200ms latency each way, server position is ~400ms behind
        # At 200 pixels/sec, that's up to 80 pixels of expected difference
        self.max_allowed_drift: float = 100.0  # Allow more drift before correcting
        self.snap_threshold: float = 150.0     # Snap if beyond this
        self.reconciliation_factor: float = 0.05  # Slower correction (was 0.1)
    
    def set_input(self, dx: int, dy: int) -> None:
        """Set current input direction."""
        self.dx = dx
        self.dy = dy
    
    def update(self, delta_time: float, game_width: float, game_height: float, 
               player_radius: float) -> Tuple[float, float]:
        """
        Update predicted position based on input.
        Returns (x, y) of predicted position.
        """
        import math
        
        if self.dx != 0 or self.dy != 0:
            # Normalize diagonal movement
            magnitude = math.sqrt(self.dx ** 2 + self.dy ** 2)
            normalized_dx = self.dx / magnitude
            normalized_dy = self.dy / magnitude
            
            # Apply movement
            new_x = self.x + normalized_dx * self.player_speed * delta_time
            new_y = self.y + normalized_dy * self.player_speed * delta_time
            
            # Clamp to game boundaries
            self.x = max(player_radius, min(game_width - player_radius, new_x))
            self.y = max(player_radius, min(game_height - player_radius, new_y))
        
        return self.x, self.y
    
    def apply_server_correction(self, server_x: float, server_y: float) -> None:
        """
        Apply server position update.
        
        With 200ms simulated latency each way (~400ms round trip), the server
        position we receive is significantly behind our predicted position.
        We should trust our prediction unless the discrepancy is too large,
        which would indicate desync or cheating.
        """
        self.server_x = server_x
        self.server_y = server_y
        
        # Calculate distance from server position
        dx = server_x - self.x
        dy = server_y - self.y
        distance = (dx ** 2 + dy ** 2) ** 0.5
        
        if distance > self.snap_threshold:
            # Very large discrepancy - snap immediately (possible teleport/desync)
            self.x = server_x
            self.y = server_y
        elif distance > self.max_allowed_drift:
            # Moderate discrepancy - slowly correct toward server
            # Only correct the excess beyond allowed drift
            correction_strength = (distance - self.max_allowed_drift) / distance
            self.x += dx * correction_strength * self.reconciliation_factor
            self.y += dy * correction_strength * self.reconciliation_factor
        # else: Within acceptable drift range - trust client prediction completely
    
    def set_position(self, x: float, y: float) -> None:
        """Set position directly (for initialization)."""
        self.x = x
        self.y = y
        self.server_x = x
        self.server_y = y


class EntityManager:
    """
    Manages all interpolated entities in the game.
    """
    
    def __init__(self):
        self.entities: dict[int, InterpolatedEntity] = {}
    
    def get_or_create_entity(self, entity_id: int) -> InterpolatedEntity:
        """Get an existing entity or create a new one."""
        if entity_id not in self.entities:
            entity = InterpolatedEntity()
            entity.entity_id = entity_id
            self.entities[entity_id] = entity
        return self.entities[entity_id]
    
    def update_entity(self, entity_id: int, timestamp: float, x: float, y: float,
                      score: int = 0, color: str = "gray") -> None:
        """Update an entity with new data from the server."""
        entity = self.get_or_create_entity(entity_id)
        entity.add_snapshot(timestamp, x, y)
        entity.score = score
        entity.color = color
    
    def remove_entity(self, entity_id: int) -> None:
        """Remove an entity."""
        if entity_id in self.entities:
            del self.entities[entity_id]
    
    def get_interpolated_positions(self, current_time: float) -> dict:
        """Get all interpolated positions for rendering."""
        positions = {}
        for entity_id, entity in self.entities.items():
            x, y = entity.get_interpolated_position(current_time)
            positions[entity_id] = {
                'x': x,
                'y': y,
                'score': entity.score,
                'color': entity.color
            }
        return positions
