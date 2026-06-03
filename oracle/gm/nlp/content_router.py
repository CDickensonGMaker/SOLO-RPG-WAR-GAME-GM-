"""
Content Router - Domain-Aware TOML Content Retrieval.

Routes content requests to the appropriate game system's TOML tables.
A Warhammer 40K session gets grimdark Gothic content, while D&D gets
heroic fantasy, and historical gets gritty realism.

The router understands Oracle's data directory structure:
- oracle/data/core/          - Universal content for all systems
- oracle/data/fantasy/       - D&D-style heroic fantasy
- oracle/data/scifi_military/ - Military sci-fi
- oracle/data/cyberpunk/     - Noir cyberpunk
- oracle/data/weird_war/     - Weird war (Trench Crusade style)
- oracle/data/historical/    - Historical (WWI/WWII)
- oracle/data/wargames/      - Wargame-specific content

Usage:
    router = ContentRouter(data_root, active_system="fantasy")

    # Get a complication from the active system's tables
    complication = router.pull_complication(mood="grimdark")

    # Get a discovery for search results
    discovery = router.pull_discovery(context="room_search")

    # Get sensory details
    sound = router.pull_sensory("sounds_tense")
"""

from pathlib import Path
from typing import Optional, List, Dict, Any
import random

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # Python < 3.11 fallback


class ContentRouter:
    """
    Routes content requests to domain-specific TOML tables.

    The router is aware of the active game system and pulls
    content from the appropriate TOML files, falling back to
    core/universal content when system-specific content isn't available.

    Content is cached to avoid repeated file reads during a session.
    """

    # Map friendly system names to directory names
    SYSTEM_PATHS = {
        "fantasy": "fantasy",
        "scifi": "scifi_military",
        "scifi_military": "scifi_military",
        "cyberpunk": "cyberpunk",
        "weird_war": "weird_war",
        "trench_crusade": "weird_war",
        "historical": "historical",
        "wwi": "historical",
        "wwii": "historical",
        "oldhammer": "wargames/oldhammer_2e",
        "40k": "wargames/oldhammer_2e",
        "warhammer": "wargames/oldhammer_2e",
    }

    def __init__(self, data_root: Path, active_system: str = "fantasy"):
        """
        Initialize the content router.

        Args:
            data_root: Path to oracle/data directory
            active_system: Active game system name
        """
        self.data_root = Path(data_root)
        self.active_system = active_system
        self._table_cache: Dict[str, Dict] = {}

    def set_system(self, system: str):
        """
        Set the active game system.

        Clears the cache since we're switching contexts.

        Args:
            system: New active system name (fantasy, scifi, cyberpunk, etc.)
        """
        if system != self.active_system:
            self.active_system = system
            self._table_cache.clear()

    def get_system_path(self) -> str:
        """Get the directory path for the active system."""
        return self.SYSTEM_PATHS.get(
            self.active_system.lower(),
            self.active_system.lower()
        )

    # =========================================================================
    # Complication / Discovery Pulls
    # =========================================================================

    def pull_complication(self, mood: str = "neutral") -> str:
        """
        Pull a complication from active system's tables.

        Args:
            mood: The mood/tone (grimdark, neutral, hopeful)

        Returns:
            A complication text string
        """
        table = self._load_table(f"complications/{mood}")
        if not table:
            table = self._load_table("complications/neutral")

        entries = self._get_entries(table, "complications")
        if entries:
            return self._weighted_choice(entries)
        return "an unexpected complication arises"

    def pull_discovery(self, context: str = "room_search") -> str:
        """
        Pull a discovery for search results.

        Args:
            context: Search context (body_search, room_search,
                     wilderness_search, debris_search, etc.)

        Returns:
            A discovery text string
        """
        # Try system-specific first, then core
        table = self._load_table(f"discoveries/{context}") or \
                self._load_core_table("discoveries")

        entries = self._get_entries(table, context)
        if entries:
            return self._weighted_choice(entries)
        return "something catches your attention"

    def pull_npc_reaction(self, disposition: int, mood: str = "neutral") -> str:
        """
        Pull an NPC reaction based on disposition.

        Args:
            disposition: NPC disposition (-100 to 100)
            mood: Scene mood (for flavor)

        Returns:
            NPC reaction text
        """
        # Determine reaction category from disposition
        if disposition > 30:
            category = "friendly"
        elif disposition < -30:
            category = "hostile"
        else:
            category = "neutral"

        table = self._load_table(f"npcs/reactions/{category}") or \
                self._load_table("npcs/dispositions")

        entries = self._get_entries(table, category)
        if entries:
            return self._weighted_choice(entries)

        # Default reactions
        defaults = {
            "friendly": "regards you warmly",
            "hostile": "eyes you with suspicion",
            "neutral": "maintains a neutral expression"
        }
        return defaults.get(category, "looks at you")

    # =========================================================================
    # Sensory Detail Pulls
    # =========================================================================

    def pull_sensory(self, sense_type: str) -> str:
        """
        Pull a sensory detail from the senses table.

        Args:
            sense_type: Type of sensory detail:
                - sounds_peaceful, sounds_tense, sounds_combat, sounds_nature
                - smells_pleasant, smells_unpleasant, smells_neutral
                - sights_details, sights_lighting
                - atmospheric_details
                - texture_details
                - taste_details
                - environmental_temperature, environmental_air

        Returns:
            A sensory description string
        """
        table = self._load_core_table("senses")
        entries = self._get_entries(table, sense_type)

        if entries:
            return self._weighted_choice(entries)
        return "you sense something in the environment"

    def pull_sound(self, mood: str = "neutral") -> str:
        """Pull a sound appropriate to the mood."""
        mood_map = {
            "peaceful": "sounds_peaceful",
            "calm": "sounds_peaceful",
            "tense": "sounds_tense",
            "danger": "sounds_tense",
            "combat": "sounds_combat",
            "battle": "sounds_combat",
            "nature": "sounds_nature",
            "outdoor": "sounds_nature",
            "town": "sounds_civilization",
            "city": "sounds_civilization",
        }
        sense_type = mood_map.get(mood.lower(), "sounds_peaceful")
        return self.pull_sensory(sense_type)

    def pull_smell(self, mood: str = "neutral") -> str:
        """Pull a smell appropriate to the mood."""
        mood_map = {
            "pleasant": "smells_pleasant",
            "nice": "smells_pleasant",
            "bad": "smells_unpleasant",
            "unpleasant": "smells_unpleasant",
            "danger": "smells_unpleasant",
            "neutral": "smells_neutral",
        }
        sense_type = mood_map.get(mood.lower(), "smells_neutral")
        return self.pull_sensory(sense_type)

    def pull_atmosphere(self) -> str:
        """Pull an atmospheric detail."""
        return self.pull_sensory("atmospheric_details")

    # =========================================================================
    # Encounter / Event Pulls
    # =========================================================================

    def pull_encounter(self, encounter_type: str = "neutral") -> Optional[Dict]:
        """
        Pull an encounter from system-specific tables.

        Args:
            encounter_type: Type of encounter (combat, social, discovery, etc.)

        Returns:
            Encounter data dict or None
        """
        table = self._load_table(f"encounters/{encounter_type}")
        if table:
            entries = self._get_entries(table, "encounters")
            if entries:
                return random.choice(entries)
        return None

    def pull_plot_twist(self) -> str:
        """Pull a plot twist from core tables."""
        table = self._load_core_table("plot_twists")
        entries = self._get_entries(table, "twists")
        if entries:
            return self._weighted_choice(entries)
        return "the situation takes an unexpected turn"

    def pull_consequence(self, severity: str = "moderate") -> str:
        """
        Pull a consequence for an action.

        Args:
            severity: How severe (minor, moderate, severe)

        Returns:
            Consequence text
        """
        table = self._load_core_table("consequences")
        entries = self._get_entries(table, severity)
        if entries:
            return self._weighted_choice(entries)
        return "there are consequences"

    # =========================================================================
    # NPC Generation
    # =========================================================================

    def pull_npc_name(self) -> str:
        """Pull a random NPC name from system-specific tables."""
        table = self._load_table("npcs/names")

        # Try different entry formats
        for key in ["names", "male", "female", "entries"]:
            entries = self._get_entries(table, key)
            if entries:
                entry = random.choice(entries)
                if isinstance(entry, dict):
                    return entry.get("text", str(entry))
                return str(entry)
        return "Unknown"

    def pull_npc_trait(self) -> str:
        """Pull a random NPC trait."""
        table = self._load_table("npcs/traits") or \
                self._load_core_table("character_quirks")

        entries = self._get_entries(table, "traits") or \
                  self._get_entries(table, "quirks")
        if entries:
            return self._weighted_choice(entries)
        return "unremarkable"

    def pull_npc_secret(self) -> str:
        """Pull a random NPC secret."""
        table = self._load_table("npcs/secrets")
        entries = self._get_entries(table, "secrets")
        if entries:
            return self._weighted_choice(entries)
        return "has a hidden agenda"

    # =========================================================================
    # Location Pulls
    # =========================================================================

    def pull_location_feature(self, location_type: str = "general") -> str:
        """
        Pull a location feature or detail.

        Args:
            location_type: Type of location (trenches, buildings, wilderness, etc.)

        Returns:
            Location feature text
        """
        table = self._load_table(f"locations/{location_type}") or \
                self._load_table("locations/features")

        entries = self._get_entries(table, "features") or \
                  self._get_entries(table, "entries")
        if entries:
            return self._weighted_choice(entries)
        return "an interesting feature catches your eye"

    # =========================================================================
    # Internal Methods
    # =========================================================================

    def _load_table(self, table_path: str) -> Optional[Dict]:
        """
        Load a TOML table, with caching.

        Tries system-specific path first, then core, then shared.

        Args:
            table_path: Relative path to the table (without .toml)

        Returns:
            Parsed TOML dict or None
        """
        system_path = self.get_system_path()
        cache_key = f"{system_path}/{table_path}"

        if cache_key in self._table_cache:
            return self._table_cache[cache_key]

        # Try paths in priority order
        paths = [
            self.data_root / system_path / f"{table_path}.toml",
            self.data_root / system_path / "lore" / f"{table_path}.toml",  # Lore path
            self.data_root / "core" / f"{table_path}.toml",
        ]

        for path in paths:
            if path.exists():
                try:
                    with open(path, "rb") as f:
                        table = tomllib.load(f)
                        self._table_cache[cache_key] = table
                        return table
                except Exception:
                    continue

        return None

    def _load_core_table(self, table_name: str) -> Optional[Dict]:
        """Load a table from the core directory."""
        cache_key = f"core/{table_name}"

        if cache_key in self._table_cache:
            return self._table_cache[cache_key]

        path = self.data_root / "core" / f"{table_name}.toml"

        if path.exists():
            try:
                with open(path, "rb") as f:
                    table = tomllib.load(f)
                    self._table_cache[cache_key] = table
                    return table
            except Exception:
                pass

        return None

    def _get_entries(self, table: Optional[Dict], key: str) -> List:
        """
        Get entries from a table by key.

        Handles both direct entries and nested entries.

        Args:
            table: The loaded TOML table
            key: The key to look up

        Returns:
            List of entries, or empty list
        """
        if not table:
            return []

        # Try direct key
        if key in table:
            data = table[key]
            if isinstance(data, dict) and "entries" in data:
                return data["entries"]
            elif isinstance(data, list):
                return data

        # Try "entries" at top level
        if "entries" in table:
            return table["entries"]

        return []

    def _weighted_choice(self, entries: List) -> str:
        """
        Select an entry using weights if available.

        Args:
            entries: List of entries (dicts with text/weight or strings)

        Returns:
            Selected text string
        """
        if not entries:
            return ""

        # Check if entries have weights
        if isinstance(entries[0], dict) and "weight" in entries[0]:
            # Weighted selection
            total_weight = sum(e.get("weight", 1) for e in entries)
            r = random.uniform(0, total_weight)
            cumulative = 0

            for entry in entries:
                cumulative += entry.get("weight", 1)
                if r <= cumulative:
                    return entry.get("text", str(entry))

        # Simple random selection
        entry = random.choice(entries)
        if isinstance(entry, dict):
            return entry.get("text", str(entry))
        return str(entry)

    def clear_cache(self):
        """Clear the table cache."""
        self._table_cache.clear()
