"""
Configuration settings for the Birthright Campaign Manager GUI.
"""

from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Any
import json

# Paths
ORACLE_ROOT = Path(__file__).parent.parent
DATA_PATH = ORACLE_ROOT / "data" / "birthright"
CAMPAIGNS_PATH = DATA_PATH / "campaigns"
SESSIONS_PATH = ORACLE_ROOT.parent / "sessions"
SAVES_PATH = SESSIONS_PATH / "birthright_campaigns"

# Ensure directories exist
SAVES_PATH.mkdir(parents=True, exist_ok=True)


@dataclass
class WindowConfig:
    """Window layout configuration."""
    width: int = 1600
    height: int = 900
    title: str = "Birthright Campaign Manager"

    # Panel sizes (proportions of window)
    dashboard_width: float = 0.22
    event_log_width: float = 0.38
    map_width: float = 0.40

    # Colors (RGBA as 0-1 floats)
    bg_color: tuple = (0.1, 0.1, 0.12, 1.0)
    panel_bg: tuple = (0.15, 0.15, 0.18, 1.0)
    accent_color: tuple = (0.7, 0.5, 0.2, 1.0)  # Gold/bronze for Birthright theme
    text_color: tuple = (0.9, 0.88, 0.82, 1.0)  # Warm white

    # Faction colors
    faction_colors: Dict[str, tuple] = field(default_factory=lambda: {
        "anuire": (0.7, 0.2, 0.2, 1.0),      # Red
        "khinasi": (0.8, 0.6, 0.2, 1.0),     # Gold
        "brecht": (0.2, 0.4, 0.7, 1.0),      # Blue
        "rjurik": (0.2, 0.6, 0.3, 1.0),      # Green
        "vos": (0.4, 0.2, 0.4, 1.0),         # Purple
        "sidhelien": (0.3, 0.7, 0.6, 1.0),   # Teal
        "awnshegh": (0.1, 0.1, 0.1, 1.0),    # Black
        "neutral": (0.5, 0.5, 0.5, 1.0),     # Gray
    })


@dataclass
class GameConfig:
    """Gameplay configuration."""
    auto_save: bool = True
    auto_save_turns: int = 1
    oracle_chaos_default: int = 5
    show_oracle_rolls: bool = True
    show_npc_ai: bool = False

    # Event generation
    random_event_chance: int = 30  # Percent
    chaos_event_modifier: int = 2  # Extra % per chaos point

    # Relationship display
    show_hidden_dispositions: bool = False
    relationship_threshold_ally: int = 40
    relationship_threshold_friendly: int = 20
    relationship_threshold_hostile: int = -20
    relationship_threshold_enemy: int = -40


@dataclass
class CampaignConfig:
    """Per-campaign configuration."""
    campaign_id: str = ""
    difficulty: str = "standard"  # easy, standard, hard, legendary
    starting_year: int = 551
    starting_season: str = "spring"

    # Difficulty modifiers
    difficulty_modifiers: Dict[str, float] = field(default_factory=lambda: {
        "easy": 0.8,
        "standard": 1.0,
        "hard": 1.2,
        "legendary": 1.5
    })


class ConfigManager:
    """Manages application configuration with persistence."""

    def __init__(self, config_path: Path = None):
        self.config_path = config_path or (SAVES_PATH / "config.json")
        self.window = WindowConfig()
        self.game = GameConfig()
        self.campaign = CampaignConfig()
        self._load()

    def _load(self):
        """Load configuration from file."""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    data = json.load(f)
                self._apply_dict(data)
            except (json.JSONDecodeError, KeyError):
                pass  # Use defaults

    def _apply_dict(self, data: Dict[str, Any]):
        """Apply dictionary values to config objects."""
        if 'window' in data:
            for k, v in data['window'].items():
                if hasattr(self.window, k):
                    setattr(self.window, k, v)
        if 'game' in data:
            for k, v in data['game'].items():
                if hasattr(self.game, k):
                    setattr(self.game, k, v)
        if 'campaign' in data:
            for k, v in data['campaign'].items():
                if hasattr(self.campaign, k):
                    setattr(self.campaign, k, v)

    def save(self):
        """Save configuration to file."""
        data = {
            'window': {
                'width': self.window.width,
                'height': self.window.height,
            },
            'game': {
                'auto_save': self.game.auto_save,
                'auto_save_turns': self.game.auto_save_turns,
                'oracle_chaos_default': self.game.oracle_chaos_default,
                'show_oracle_rolls': self.game.show_oracle_rolls,
                'show_npc_ai': self.game.show_npc_ai,
            },
            'campaign': {
                'difficulty': self.campaign.difficulty,
            }
        }
        with open(self.config_path, 'w') as f:
            json.dump(data, f, indent=2)

    def get_difficulty_modifier(self) -> float:
        """Get the current difficulty modifier."""
        return self.campaign.difficulty_modifiers.get(
            self.campaign.difficulty, 1.0
        )


# Global config instance
config = ConfigManager()
