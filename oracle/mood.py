"""Mood state machine for managing game tone and atmosphere.

The mood system controls table selection and procedural generation by
tracking the current mode (RPG vs wargame), setting (fantasy, scifi, etc.),
and various tonal dimensions like stakes, weirdness, and pacing.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class Mode(Enum):
    """Primary gameplay mode."""
    RPG = "rpg"
    WARGAME = "wargame"


class Setting(Enum):
    """Game world setting/genre."""
    SCIFI_MILITARY = ("scifi_military", "Sci-Fi Military")
    FANTASY = ("fantasy", "Fantasy")
    CYBERPUNK = ("cyberpunk", "Cyberpunk")
    HISTORICAL = ("historical", "Historical")
    WEIRD_WAR = ("weird_war", "Weird War")

    def __init__(self, folder: str, display: str):
        self.folder = folder
        self.display = display


class Tone(Enum):
    """Overall narrative tone."""
    GRIMDARK = ("grimdark", "Grimdark", -2)
    GRITTY = ("gritty", "Gritty", -1)
    NEUTRAL = ("neutral", "Neutral", 0)
    HOPEFUL = ("hopeful", "Hopeful", 1)
    CAMPY = ("campy", "Campy", 2)

    def __init__(self, folder: str, display: str, weight: int):
        self.folder = folder
        self.display = display
        self.weight = weight


class Stakes(Enum):
    """How deadly/consequential the game is."""
    LETHAL = ("lethal", "Lethal", -2)
    DANGEROUS = ("dangerous", "Dangerous", -1)
    BALANCED = ("balanced", "Balanced", 0)
    HEROIC = ("heroic", "Heroic", 1)
    PULPY = ("pulpy", "Pulpy", 2)

    def __init__(self, folder: str, display: str, weight: int):
        self.folder = folder
        self.display = display
        self.weight = weight


class Weirdness(Enum):
    """How supernatural/strange the world is."""
    GROUNDED = ("grounded", "Grounded", 0)
    LOW_MAGIC = ("low_magic", "Low Magic/Tech", 1)
    HIGH_STRANGENESS = ("high_strangeness", "High Strangeness", 2)
    GONZO = ("gonzo", "Gonzo", 3)

    def __init__(self, folder: str, display: str, level: int):
        self.folder = folder
        self.display = display
        self.level = level


class Pace(Enum):
    """Narrative pacing and tension."""
    SLOW_BURN = ("slow_burn", "Slow Burn", -2)
    TENSE = ("tense", "Tense", -1)
    BALANCED = ("balanced", "Balanced", 0)
    ACTION_HEAVY = ("action_heavy", "Action-Heavy", 1)
    FRANTIC = ("frantic", "Frantic", 2)

    def __init__(self, folder: str, display: str, weight: int):
        self.folder = folder
        self.display = display
        self.weight = weight


class Scale(Enum):
    """Wargame battle scale."""
    SKIRMISH = ("skirmish", "Skirmish", 5, 15)
    STANDARD = ("standard", "Standard", 20, 50)
    LARGE = ("large", "Large Battle", 60, 200)

    def __init__(self, folder: str, display: str, min_units: int, max_units: int):
        self.folder = folder
        self.display = display
        self.min_units = min_units
        self.max_units = max_units


# Setting defaults - each setting has characteristic defaults
SETTING_DEFAULTS: dict[Setting, dict] = {
    Setting.SCIFI_MILITARY: {
        "tone": Tone.GRITTY,
        "stakes": Stakes.DANGEROUS,
        "weirdness": Weirdness.LOW_MAGIC,
        "pace": Pace.ACTION_HEAVY,
    },
    Setting.FANTASY: {
        "tone": Tone.NEUTRAL,
        "stakes": Stakes.BALANCED,
        "weirdness": Weirdness.LOW_MAGIC,
        "pace": Pace.BALANCED,
    },
    Setting.CYBERPUNK: {
        "tone": Tone.GRITTY,
        "stakes": Stakes.DANGEROUS,
        "weirdness": Weirdness.LOW_MAGIC,
        "pace": Pace.TENSE,
    },
    Setting.HISTORICAL: {
        "tone": Tone.NEUTRAL,
        "stakes": Stakes.DANGEROUS,
        "weirdness": Weirdness.GROUNDED,
        "pace": Pace.BALANCED,
    },
    Setting.WEIRD_WAR: {
        "tone": Tone.GRIMDARK,
        "stakes": Stakes.LETHAL,
        "weirdness": Weirdness.HIGH_STRANGENESS,
        "pace": Pace.TENSE,
    },
}

# Named presets for quick mood configuration
PRESETS: dict[str, dict] = {
    "heroic": {
        "tone": Tone.HOPEFUL,
        "stakes": Stakes.HEROIC,
        "weirdness": Weirdness.LOW_MAGIC,
        "pace": Pace.ACTION_HEAVY,
    },
    "grimdark": {
        "tone": Tone.GRIMDARK,
        "stakes": Stakes.LETHAL,
        "weirdness": Weirdness.HIGH_STRANGENESS,
        "pace": Pace.TENSE,
    },
    "pulp": {
        "tone": Tone.CAMPY,
        "stakes": Stakes.PULPY,
        "weirdness": Weirdness.HIGH_STRANGENESS,
        "pace": Pace.FRANTIC,
    },
    "noir": {
        "tone": Tone.GRITTY,
        "stakes": Stakes.DANGEROUS,
        "weirdness": Weirdness.GROUNDED,
        "pace": Pace.SLOW_BURN,
    },
    "horror": {
        "tone": Tone.GRIMDARK,
        "stakes": Stakes.LETHAL,
        "weirdness": Weirdness.HIGH_STRANGENESS,
        "pace": Pace.SLOW_BURN,
    },
    "action": {
        "tone": Tone.NEUTRAL,
        "stakes": Stakes.BALANCED,
        "weirdness": Weirdness.LOW_MAGIC,
        "pace": Pace.FRANTIC,
    },
    "balanced": {
        "tone": Tone.NEUTRAL,
        "stakes": Stakes.BALANCED,
        "weirdness": Weirdness.LOW_MAGIC,
        "pace": Pace.BALANCED,
    },
}


@dataclass
class MoodState:
    """Current mood configuration for the game session."""
    mode: Mode = Mode.RPG
    setting: Setting = Setting.FANTASY
    tone: Tone = Tone.NEUTRAL
    stakes: Stakes = Stakes.BALANCED
    weirdness: Weirdness = Weirdness.LOW_MAGIC
    pace: Pace = Pace.BALANCED
    scale: Scale = Scale.STANDARD

    def __str__(self) -> str:
        lines = [
            f"Mode: {self.mode.value.upper()}",
            f"Setting: {self.setting.display}",
            f"Tone: {self.tone.display}",
            f"Stakes: {self.stakes.display}",
            f"Weirdness: {self.weirdness.display}",
            f"Pace: {self.pace.display}",
        ]
        if self.mode == Mode.WARGAME:
            lines.append(f"Scale: {self.scale.display}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Export state as a dictionary for serialization."""
        return {
            "mode": self.mode.value,
            "setting": self.setting.folder,
            "tone": self.tone.folder,
            "stakes": self.stakes.folder,
            "weirdness": self.weirdness.folder,
            "pace": self.pace.folder,
            "scale": self.scale.folder,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MoodState":
        """Create state from a dictionary."""
        return cls(
            mode=Mode(data.get("mode", "rpg")),
            setting=_setting_from_folder(data.get("setting", "fantasy")),
            tone=_tone_from_folder(data.get("tone", "neutral")),
            stakes=_stakes_from_folder(data.get("stakes", "balanced")),
            weirdness=_weirdness_from_folder(data.get("weirdness", "low_magic")),
            pace=_pace_from_folder(data.get("pace", "balanced")),
            scale=_scale_from_folder(data.get("scale", "standard")),
        )


def _setting_from_folder(folder: str) -> Setting:
    """Look up Setting enum by folder name."""
    for s in Setting:
        if s.folder == folder:
            return s
    return Setting.FANTASY


def _tone_from_folder(folder: str) -> Tone:
    """Look up Tone enum by folder name."""
    for t in Tone:
        if t.folder == folder:
            return t
    return Tone.NEUTRAL


def _stakes_from_folder(folder: str) -> Stakes:
    """Look up Stakes enum by folder name."""
    for s in Stakes:
        if s.folder == folder:
            return s
    return Stakes.BALANCED


def _weirdness_from_folder(folder: str) -> Weirdness:
    """Look up Weirdness enum by folder name."""
    for w in Weirdness:
        if w.folder == folder:
            return w
    return Weirdness.LOW_MAGIC


def _pace_from_folder(folder: str) -> Pace:
    """Look up Pace enum by folder name."""
    for p in Pace:
        if p.folder == folder:
            return p
    return Pace.BALANCED


def _scale_from_folder(folder: str) -> Scale:
    """Look up Scale enum by folder name."""
    for s in Scale:
        if s.folder == folder:
            return s
    return Scale.STANDARD


class MoodManager:
    """Manages the current mood state and provides table path resolution."""

    def __init__(self, data_root: Optional[Path] = None):
        """Initialize the mood manager.

        Args:
            data_root: Root path for table data. Defaults to oracle/data.
        """
        self.state = MoodState()
        self._data_root = data_root or self._default_data_root()

    def _default_data_root(self) -> Path:
        """Get the default data root path."""
        return Path(__file__).parent / "data"

    @property
    def data_root(self) -> Path:
        """Root path for table data files."""
        return self._data_root

    @data_root.setter
    def data_root(self, path: Path):
        """Set the data root path."""
        self._data_root = path

    def set_mode(self, mode: Mode) -> None:
        """Set the gameplay mode (RPG or wargame)."""
        self.state.mode = mode

    def set_setting(self, setting: Setting, apply_defaults: bool = True) -> None:
        """Set the game setting/genre.

        Args:
            setting: The Setting enum value to use.
            apply_defaults: If True, apply setting-specific default mood values.
        """
        self.state.setting = setting
        if apply_defaults and setting in SETTING_DEFAULTS:
            defaults = SETTING_DEFAULTS[setting]
            self.state.tone = defaults["tone"]
            self.state.stakes = defaults["stakes"]
            self.state.weirdness = defaults["weirdness"]
            self.state.pace = defaults["pace"]

    def set_tone(self, tone: Tone) -> None:
        """Set the narrative tone."""
        self.state.tone = tone

    def set_stakes(self, stakes: Stakes) -> None:
        """Set the stakes/lethality level."""
        self.state.stakes = stakes

    def set_weirdness(self, weirdness: Weirdness) -> None:
        """Set the weirdness/magic level."""
        self.state.weirdness = weirdness

    def set_pace(self, pace: Pace) -> None:
        """Set the narrative pace."""
        self.state.pace = pace

    def set_scale(self, scale: Scale) -> None:
        """Set the wargame scale (only relevant in WARGAME mode)."""
        self.state.scale = scale

    def apply_preset(self, name: str) -> bool:
        """Apply a named mood preset.

        Args:
            name: The preset name (e.g., "heroic", "grimdark", "pulp").

        Returns:
            True if preset was found and applied, False otherwise.
        """
        preset = PRESETS.get(name.lower())
        if preset is None:
            return False

        self.state.tone = preset["tone"]
        self.state.stakes = preset["stakes"]
        self.state.weirdness = preset["weirdness"]
        self.state.pace = preset["pace"]
        return True

    def list_presets(self) -> list[str]:
        """List available preset names."""
        return list(PRESETS.keys())

    def get_table_path(self, table_name: str, mood_specific: bool = True) -> Path:
        """Get the path to a table file based on current mood.

        Resolution order:
        1. data/{setting}/{table_name}/{tone}.toml (if mood_specific)
        2. data/{setting}/{table_name}/neutral.toml
        3. data/core/{table_name}/neutral.toml

        Args:
            table_name: Name of the table (e.g., "encounters", "npcs").
            mood_specific: If True, try tone-specific file first.

        Returns:
            Path to the most specific existing table file.
        """
        setting_folder = self.state.setting.folder
        tone_folder = self.state.tone.folder

        # Try mood-specific file first
        if mood_specific:
            mood_path = self._data_root / setting_folder / table_name / f"{tone_folder}.toml"
            if mood_path.exists():
                return mood_path

        # Fall back to neutral in setting
        setting_neutral = self._data_root / setting_folder / table_name / "neutral.toml"
        if setting_neutral.exists():
            return setting_neutral

        # Fall back to core
        core_path = self._data_root / "core" / table_name / "neutral.toml"
        if core_path.exists():
            return core_path

        # Return the most specific path even if it doesn't exist
        # (caller can check existence or let load fail)
        if mood_specific:
            return self._data_root / setting_folder / table_name / f"{tone_folder}.toml"
        return setting_neutral

    def get_all_table_paths(self, table_name: str) -> list[Path]:
        """Get all possible table paths in fallback order.

        Useful for debugging or showing what files would be checked.

        Args:
            table_name: Name of the table.

        Returns:
            List of paths in resolution order.
        """
        setting_folder = self.state.setting.folder
        tone_folder = self.state.tone.folder

        return [
            self._data_root / setting_folder / table_name / f"{tone_folder}.toml",
            self._data_root / setting_folder / table_name / "neutral.toml",
            self._data_root / "core" / table_name / "neutral.toml",
        ]


# Module-level manager instance
_manager = MoodManager()


def get_state() -> MoodState:
    """Get the current mood state."""
    return _manager.state


def set_mode(mode: Mode) -> None:
    """Set the gameplay mode."""
    _manager.set_mode(mode)


def set_setting(setting: Setting, apply_defaults: bool = True) -> None:
    """Set the game setting."""
    _manager.set_setting(setting, apply_defaults)


def set_tone(tone: Tone) -> None:
    """Set the narrative tone."""
    _manager.set_tone(tone)


def set_stakes(stakes: Stakes) -> None:
    """Set the stakes level."""
    _manager.set_stakes(stakes)


def set_weirdness(weirdness: Weirdness) -> None:
    """Set the weirdness level."""
    _manager.set_weirdness(weirdness)


def set_pace(pace: Pace) -> None:
    """Set the narrative pace."""
    _manager.set_pace(pace)


def set_scale(scale: Scale) -> None:
    """Set the wargame scale."""
    _manager.set_scale(scale)


def apply_preset(name: str) -> bool:
    """Apply a named preset."""
    return _manager.apply_preset(name)


def list_presets() -> list[str]:
    """List available presets."""
    return _manager.list_presets()


def get_table_path(table_name: str, mood_specific: bool = True) -> Path:
    """Get path to a table file based on current mood."""
    return _manager.get_table_path(table_name, mood_specific)
