"""
Pygame Renderer for the Coin Collector game client.
Handles all visual rendering of the game state.
"""

import pygame
from typing import Dict, List, Optional, Tuple

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from shared.constants import (
    GAME_WIDTH, GAME_HEIGHT, PLAYER_RADIUS, COIN_RADIUS,
    PLAYER_COLORS, COIN_COLOR, BACKGROUND_COLOR, TEXT_COLOR,
    WAITING_TEXT_COLOR, GAME_DURATION
)


class GameRenderer:
    """
    Handles all Pygame rendering for the game.
    """
    
    def __init__(self):
        # Initialize Pygame
        pygame.init()
        pygame.font.init()
        
        # Create window
        self.screen = pygame.display.set_mode((GAME_WIDTH, GAME_HEIGHT))
        pygame.display.set_caption("Coin Collector - Multiplayer")
        
        # Fonts
        self.font_large = pygame.font.Font(None, 48)
        self.font_medium = pygame.font.Font(None, 36)
        self.font_small = pygame.font.Font(None, 24)
        
        # Clock for framerate
        self.clock = pygame.time.Clock()
        
        # Color map for player colors (string to RGB)
        self.color_map = {
            "blue": (50, 100, 255),
            "red": (255, 50, 50),
            "green": (50, 255, 50),
            "yellow": (255, 255, 50),
            "gray": (150, 150, 150)
        }
    
    def get_color(self, color_name: str) -> Tuple[int, int, int]:
        """Convert color name to RGB tuple."""
        return self.color_map.get(color_name, (150, 150, 150))
    
    def render_waiting_screen(self) -> None:
        """Render the waiting for players screen."""
        self.screen.fill(BACKGROUND_COLOR)
        
        # Title
        title = self.font_large.render("Coin Collector", True, TEXT_COLOR)
        title_rect = title.get_rect(center=(GAME_WIDTH // 2, GAME_HEIGHT // 3))
        self.screen.blit(title, title_rect)
        
        # Waiting message
        waiting_text = self.font_medium.render("Waiting for players...", True, WAITING_TEXT_COLOR)
        waiting_rect = waiting_text.get_rect(center=(GAME_WIDTH // 2, GAME_HEIGHT // 2))
        self.screen.blit(waiting_text, waiting_rect)
        
        # Instructions
        instructions = self.font_small.render("Need 2 players to start", True, WAITING_TEXT_COLOR)
        inst_rect = instructions.get_rect(center=(GAME_WIDTH // 2, GAME_HEIGHT // 2 + 40))
        self.screen.blit(instructions, inst_rect)
        
        pygame.display.flip()
    
    def render_connecting_screen(self) -> None:
        """Render the connecting to server screen."""
        self.screen.fill(BACKGROUND_COLOR)
        
        # Title
        title = self.font_large.render("Coin Collector", True, TEXT_COLOR)
        title_rect = title.get_rect(center=(GAME_WIDTH // 2, GAME_HEIGHT // 3))
        self.screen.blit(title, title_rect)
        
        # Connecting message
        connecting_text = self.font_medium.render("Connecting to server...", True, WAITING_TEXT_COLOR)
        connecting_rect = connecting_text.get_rect(center=(GAME_WIDTH // 2, GAME_HEIGHT // 2))
        self.screen.blit(connecting_text, connecting_rect)
        
        pygame.display.flip()
    
    def render_disconnected_screen(self) -> None:
        """Render the disconnected screen."""
        self.screen.fill(BACKGROUND_COLOR)
        
        # Error message
        error_text = self.font_large.render("Disconnected from Server", True, (255, 100, 100))
        error_rect = error_text.get_rect(center=(GAME_WIDTH // 2, GAME_HEIGHT // 2))
        self.screen.blit(error_text, error_rect)
        
        # Instructions
        instructions = self.font_small.render("Press ESC to exit", True, WAITING_TEXT_COLOR)
        inst_rect = instructions.get_rect(center=(GAME_WIDTH // 2, GAME_HEIGHT // 2 + 50))
        self.screen.blit(instructions, inst_rect)
        
        pygame.display.flip()
    
    def render_game_over_screen(self, winner: Optional[int], scores: Dict[int, int],
                                 local_player_id: int) -> None:
        """Render the game over screen."""
        self.screen.fill(BACKGROUND_COLOR)
        
        # Game Over title
        title = self.font_large.render("Game Over!", True, TEXT_COLOR)
        title_rect = title.get_rect(center=(GAME_WIDTH // 2, GAME_HEIGHT // 4))
        self.screen.blit(title, title_rect)
        
        # Winner announcement
        if winner:
            if winner == local_player_id:
                winner_text = "You Win!"
                winner_color = (50, 255, 50)  # Green
            else:
                winner_text = f"Player {winner} Wins!"
                winner_color = (255, 100, 100)  # Red
            
            winner_surface = self.font_large.render(winner_text, True, winner_color)
            winner_rect = winner_surface.get_rect(center=(GAME_WIDTH // 2, GAME_HEIGHT // 2 - 30))
            self.screen.blit(winner_surface, winner_rect)
        
        # Final scores
        y_offset = GAME_HEIGHT // 2 + 30
        for player_id, score in sorted(scores.items()):
            label = f"Player {player_id}: {score} points"
            if player_id == local_player_id:
                label += " (You)"
            score_surface = self.font_medium.render(label, True, TEXT_COLOR)
            score_rect = score_surface.get_rect(center=(GAME_WIDTH // 2, y_offset))
            self.screen.blit(score_surface, score_rect)
            y_offset += 35
        
        # Instructions
        instructions = self.font_small.render("Press ESC to exit", True, WAITING_TEXT_COLOR)
        inst_rect = instructions.get_rect(center=(GAME_WIDTH // 2, GAME_HEIGHT - 50))
        self.screen.blit(instructions, inst_rect)
        
        pygame.display.flip()
    
    def render_game(self, local_player_pos: Tuple[float, float], local_player_id: int,
                    local_player_color: str, local_player_score: int,
                    remote_players: Dict[int, dict], coins: List[dict],
                    game_time: float = 0) -> None:
        """
        Render the main game state.
        
        Args:
            local_player_pos: (x, y) of local player
            local_player_id: ID of local player
            local_player_color: Color name of local player
            local_player_score: Score of local player
            remote_players: Dict of remote player data {id: {x, y, score, color}}
            coins: List of coin data [{id, x, y}]
            game_time: Current game time in seconds
        """
        self.screen.fill(BACKGROUND_COLOR)
        
        # Draw game boundary
        pygame.draw.rect(self.screen, (60, 60, 70), (0, 0, GAME_WIDTH, GAME_HEIGHT), 3)
        
        # Draw coins
        for coin in coins:
            pygame.draw.circle(
                self.screen,
                COIN_COLOR,
                (int(coin['x']), int(coin['y'])),
                COIN_RADIUS
            )
            # Add a slight shine effect
            pygame.draw.circle(
                self.screen,
                (255, 240, 150),
                (int(coin['x'] - 3), int(coin['y'] - 3)),
                COIN_RADIUS // 3
            )
        
        # Draw remote players
        for player_id, player_data in remote_players.items():
            if player_id == local_player_id:
                continue  # Skip local player, we draw them separately
            
            x, y = int(player_data['x']), int(player_data['y'])
            color = self.get_color(player_data.get('color', 'gray'))
            
            # Draw player circle
            pygame.draw.circle(self.screen, color, (x, y), PLAYER_RADIUS)
            pygame.draw.circle(self.screen, TEXT_COLOR, (x, y), PLAYER_RADIUS, 2)
            
            # Draw player label
            label = self.font_small.render(f"P{player_id}", True, TEXT_COLOR)
            label_rect = label.get_rect(center=(x, y - PLAYER_RADIUS - 15))
            self.screen.blit(label, label_rect)
        
        # Draw local player (on top)
        local_x, local_y = int(local_player_pos[0]), int(local_player_pos[1])
        local_color = self.get_color(local_player_color)
        
        # Draw player circle with highlight to show it's the local player
        pygame.draw.circle(self.screen, local_color, (local_x, local_y), PLAYER_RADIUS)
        pygame.draw.circle(self.screen, (255, 255, 255), (local_x, local_y), PLAYER_RADIUS, 3)
        
        # Draw "YOU" label
        you_label = self.font_small.render("YOU", True, TEXT_COLOR)
        you_rect = you_label.get_rect(center=(local_x, local_y - PLAYER_RADIUS - 15))
        self.screen.blit(you_label, you_rect)
        
        # Draw UI - Scores
        self._render_scores(local_player_id, local_player_score, local_player_color, remote_players)
        
        # Draw timer if game has duration
        if GAME_DURATION:
            remaining = max(0, GAME_DURATION - game_time)
            self._render_timer(remaining)
        
        # Draw controls hint
        controls_text = self.font_small.render("WASD or Arrow Keys to move", True, WAITING_TEXT_COLOR)
        controls_rect = controls_text.get_rect(center=(GAME_WIDTH // 2, GAME_HEIGHT - 20))
        self.screen.blit(controls_text, controls_rect)
        
        pygame.display.flip()
    
    def _render_scores(self, local_player_id: int, local_player_score: int,
                       local_player_color: str, remote_players: Dict[int, dict]) -> None:
        """Render score display."""
        # Background panel
        panel_rect = pygame.Rect(10, 10, 180, 80)
        pygame.draw.rect(self.screen, (20, 20, 30), panel_rect)
        pygame.draw.rect(self.screen, (60, 60, 70), panel_rect, 2)
        
        # Title
        title = self.font_small.render("SCORES", True, TEXT_COLOR)
        self.screen.blit(title, (20, 15))
        
        # Local player score
        local_color = self.get_color(local_player_color)
        local_text = self.font_small.render(f"You (P{local_player_id}): {local_player_score}", True, local_color)
        self.screen.blit(local_text, (20, 40))
        
        # Remote player scores
        y_offset = 60
        for player_id, player_data in remote_players.items():
            if player_id == local_player_id:
                continue
            color = self.get_color(player_data.get('color', 'gray'))
            score_text = self.font_small.render(f"P{player_id}: {player_data.get('score', 0)}", True, color)
            self.screen.blit(score_text, (20, y_offset))
            y_offset += 20
    
    def _render_timer(self, remaining_time: float) -> None:
        """Render game timer."""
        minutes = int(remaining_time // 60)
        seconds = int(remaining_time % 60)
        time_str = f"{minutes}:{seconds:02d}"
        
        # Timer background
        timer_surface = self.font_medium.render(time_str, True, TEXT_COLOR)
        timer_rect = timer_surface.get_rect(midtop=(GAME_WIDTH // 2, 10))
        
        # Background
        bg_rect = timer_rect.inflate(20, 10)
        pygame.draw.rect(self.screen, (20, 20, 30), bg_rect)
        pygame.draw.rect(self.screen, (60, 60, 70), bg_rect, 2)
        
        # Timer text
        self.screen.blit(timer_surface, timer_rect)
    
    def tick(self, fps: int = 60) -> float:
        """
        Tick the clock and return delta time.
        Returns delta time in seconds.
        """
        return self.clock.tick(fps) / 1000.0
    
    def quit(self) -> None:
        """Clean up Pygame resources."""
        pygame.quit()
