"""NPC generator using setting-aware component pools."""

import random
from dataclasses import dataclass, field
from typing import Optional, Protocol, Any


class MoodManager(Protocol):
    """Protocol for mood system integration."""

    @property
    def current_mood(self) -> str:
        """Return current mood state."""
        ...

    def influence_roll(self, base_roll: int) -> int:
        """Modify a roll based on current mood."""
        ...


class TableLoader(Protocol):
    """Protocol for loading data tables from settings."""

    def load_table(self, setting: str, category: str, table_name: str) -> list[str]:
        """Load a table of strings from a setting's data."""
        ...

    def get_available_settings(self) -> list[str]:
        """Return list of available settings."""
        ...


@dataclass
class NPCComponent:
    """Individual component of an NPC."""
    name: str
    role: str
    trait: str
    secret: str
    disposition: str


@dataclass
class NPC:
    """A generated NPC with all components."""
    name: str
    role: str
    trait: str
    secret: str
    disposition: str
    setting: str
    mood_influence: str = ""

    @classmethod
    def from_component(cls, component: NPCComponent, setting: str, mood: str = "") -> "NPC":
        """Create NPC from a component."""
        return cls(
            name=component.name,
            role=component.role,
            trait=component.trait,
            secret=component.secret,
            disposition=component.disposition,
            setting=setting,
            mood_influence=mood
        )

    def __str__(self) -> str:
        """Format NPC as a displayable card."""
        lines = [
            "+" + "-" * 40 + "+",
            f"| {'NPC':^38} |",
            "+" + "-" * 40 + "+",
            f"| Name: {self.name:<32} |",
            f"| Role: {self.role:<32} |",
            f"| Trait: {self.trait:<31} |",
            f"| Disposition: {self.disposition:<25} |",
            "+" + "-" * 40 + "+",
            f"| Secret: {self.secret:<30} |",
            "+" + "-" * 40 + "+",
        ]
        if self.mood_influence:
            lines.insert(-1, f"| Mood: {self.mood_influence:<32} |")
        return "\n".join(lines)


# Default pools for fallback when no table loader or setting data available
DEFAULT_POOLS = {
    "core": {
        "names": [
            "Marcus", "Elena", "Viktor", "Sasha", "Dmitri",
            "Lyra", "Theron", "Kira", "Roland", "Vera",
            "Johan", "Miriam", "Aleksei", "Natasha", "Conrad"
        ],
        "roles": [
            "Merchant", "Guard", "Scholar", "Traveler", "Artisan",
            "Healer", "Entertainer", "Laborer", "Official", "Outcast",
            "Veteran", "Pilgrim", "Messenger", "Hunter", "Smith"
        ],
        "traits": [
            "Suspicious", "Generous", "Ambitious", "Melancholic", "Cheerful",
            "Secretive", "Boisterous", "Cautious", "Reckless", "Calculating",
            "Loyal", "Treacherous", "Pious", "Cynical", "Naive"
        ],
        "secrets": [
            "Hiding from their past",
            "Seeking revenge",
            "Has a forbidden love",
            "Knows a dangerous truth",
            "Owes a powerful debt",
            "Is not who they claim",
            "Guards a hidden treasure",
            "Plans betrayal",
            "Serves a secret master",
            "Fears discovery",
            "Seeks a lost relative",
            "Carries stolen goods",
            "Witnessed a crime",
            "Hides a curse",
            "Protects a fugitive"
        ],
        "dispositions": [
            "Friendly", "Hostile", "Neutral", "Wary", "Helpful",
            "Dismissive", "Curious", "Fearful", "Aggressive", "Indifferent"
        ]
    },
    "fantasy": {
        "names": [
            "Aldric", "Seraphina", "Thorin", "Elara", "Grimwald",
            "Isolde", "Caspian", "Morgana", "Fenris", "Celestine",
            "Bramble", "Aelindra", "Gorath", "Sylvana", "Ragnor"
        ],
        "roles": [
            "Wizard", "Knight", "Bard", "Ranger", "Alchemist",
            "Priest", "Thief", "Blacksmith", "Noble", "Farmer",
            "Hedge Witch", "Sellsword", "Innkeeper", "Sage", "Hermit"
        ],
        "traits": [
            "Mystical", "Honorable", "Cunning", "Wild", "Scholarly",
            "Superstitious", "Battle-scarred", "Ethereal", "Gruff", "Enigmatic",
            "Zealous", "World-weary", "Fey-touched", "Stoic", "Mischievous"
        ],
        "secrets": [
            "Bound to a dark pact",
            "Of noble blood in hiding",
            "Cursed by a witch",
            "Seeks a legendary artifact",
            "Was once a monster",
            "Communes with spirits",
            "Knows the true king",
            "Carries dragon blood",
            "Banished from their order",
            "Owes a fey debt",
            "Haunted by fallen comrades",
            "Knows forbidden magic",
            "Hunted by assassins",
            "Guards an ancient secret",
            "Their soul is not their own"
        ],
        "dispositions": [
            "Noble", "Treacherous", "Enigmatic", "Stalwart", "Mercenary",
            "Pious", "Suspicious", "Welcoming", "Desperate", "Calculating"
        ]
    },
    "scifi_military": {
        "names": [
            "Commander Reyes", "Dr. Chen", "Sergeant Volkov", "Specialist Tanaka", "Captain Okonkwo",
            "Lieutenant Hayes", "Private Martinez", "Agent Kowalski", "Admiral Sterling", "Corporal Singh",
            "Operative Nash", "Major Petrov", "Technician Zhao", "Pilot Fernandez", "Colonel Brooks"
        ],
        "roles": [
            "Officer", "Medic", "Engineer", "Pilot", "Intelligence",
            "Marine", "Scientist", "Diplomat", "Mercenary", "Refugee",
            "Smuggler", "Technician", "Commander", "Scout", "Contractor"
        ],
        "traits": [
            "By-the-book", "Shell-shocked", "Ambitious", "Paranoid", "Pragmatic",
            "Idealistic", "Cynical", "Cold", "Compassionate", "Ruthless",
            "Broken", "Driven", "Calculating", "Reckless", "Haunted"
        ],
        "secrets": [
            "War crimes in their past",
            "Double agent",
            "Synthetic/clone origin",
            "Lost their unit",
            "Black ops history",
            "Knows the war is a lie",
            "Addicted to combat stims",
            "Owes the cartel",
            "AWOL from another faction",
            "Carries classified intel",
            "Family held hostage",
            "Prototype implant",
            "Witnessed atrocity",
            "Defector",
            "Terminal condition"
        ],
        "dispositions": [
            "Professional", "Hostile", "Cooperative", "Paranoid", "Desperate",
            "Calculating", "Weary", "Aggressive", "Neutral", "Wary"
        ]
    },
    "cyberpunk": {
        "names": [
            "Zero", "Nyx", "Razor", "Chrome", "Glitch",
            "Binary", "Spectre", "Neon", "Vector", "Null",
            "Hack", "Static", "Cipher", "Pixel", "Ghost"
        ],
        "roles": [
            "Netrunner", "Solo", "Fixer", "Corp Drone", "Street Doc",
            "Techie", "Media", "Nomad", "Exec", "Rockerboy",
            "Dealer", "Cop", "Bodyguard", "Smuggler", "Info Broker"
        ],
        "traits": [
            "Paranoid", "Chromed-out", "Analog purist", "Burned out", "Hungry",
            "Jaded", "Idealistic", "Violent", "Slick", "Desperate",
            "Calculating", "Reckless", "Modified", "Clean", "Broken"
        ],
        "secrets": [
            "Corp extraction target",
            "Has a kill switch",
            "Stolen identity",
            "Deep corporate mole",
            "Carries a virus payload",
            "Knows too much",
            "Debt to the Yakuza",
            "Former black ops",
            "AI symbiont",
            "Witness to corp crime",
            "Underground legend",
            "Wanted for data theft",
            "Experimental subject",
            "Faked their death",
            "Synth who doesn't know"
        ],
        "dispositions": [
            "Hostile", "Transactional", "Paranoid", "Predatory", "Desperate",
            "Professional", "Chaotic", "Cold", "Opportunistic", "Wary"
        ]
    },
    "historical": {
        "names": [
            "William", "Catherine", "Heinrich", "Isabella", "Giovanni",
            "Margaret", "Charles", "Elisabeth", "Frederick", "Anne",
            "Robert", "Maria", "Thomas", "Eleanor", "James"
        ],
        "roles": [
            "Nobleman", "Peasant", "Merchant", "Soldier", "Clergy",
            "Artisan", "Servant", "Scholar", "Outlaw", "Official",
            "Traveler", "Healer", "Entertainer", "Sailor", "Laborer"
        ],
        "traits": [
            "Pious", "Ambitious", "Superstitious", "Worldly", "Humble",
            "Proud", "Suspicious", "Generous", "Cruel", "Just",
            "Secretive", "Bold", "Cautious", "Scholarly", "Simple"
        ],
        "secrets": [
            "Illegitimate birth",
            "Heretical beliefs",
            "Hidden wealth",
            "Forbidden love",
            "Criminal past",
            "Noble in hiding",
            "Spy for enemy",
            "Practitioner of forbidden arts",
            "Witnessed regicide",
            "Escaped prisoner",
            "Debt to powerful lord",
            "Stolen identity",
            "Plague survivor",
            "Knows state secrets",
            "Runaway from servitude"
        ],
        "dispositions": [
            "Deferential", "Haughty", "Suspicious", "Welcoming", "Fearful",
            "Calculating", "Pious", "Mercenary", "Loyal", "Scheming"
        ]
    },
    "weird_war": {
        "names": [
            "Sergeant Black", "Dr. Voss", "Private Kane", "Agent Cross", "Captain Hollow",
            "Lieutenant Grey", "Corporal Strange", "Major Thorne", "Operative Shade", "Colonel Ward",
            "Nurse Grim", "Chaplain Crow", "Pilot Raven", "Scout Marsh", "Medic Ashe"
        ],
        "roles": [
            "Occult Specialist", "Soldier", "Field Medic", "Intelligence Officer", "Chaplain",
            "Engineer", "Sniper", "Resistance Fighter", "Scientist", "Pilot",
            "Deserter", "War Correspondent", "Civilian", "POW", "Partisan"
        ],
        "traits": [
            "Shell-shocked", "Touched by the Other", "Fanatical", "Skeptical", "Haunted",
            "Desperate", "Ruthless", "Compassionate", "Paranoid", "Driven",
            "Broken", "Faithful", "Cynical", "Mad", "Stoic"
        ],
        "secrets": [
            "Made a pact",
            "Saw things in the trenches",
            "Carries cursed object",
            "Enemy sympathizer",
            "Knows the true enemy",
            "Experimented on",
            "Undead but aware",
            "Ancestral curse",
            "Witnessed summoning",
            "Hunts their own side",
            "Family serves the enemy",
            "Psychic awakening",
            "Died and came back",
            "Knows the war's true purpose",
            "They cannot die"
        ],
        "dispositions": [
            "Desperate", "Paranoid", "Battle-hardened", "Broken", "Zealous",
            "Wary", "Hostile", "Cooperative", "Manic", "Resigned"
        ]
    }
}

# Mood influence on NPC generation
MOOD_INFLUENCES = {
    "tense": ["Paranoid", "Wary", "Hostile", "Desperate"],
    "dark": ["Melancholic", "Haunted", "Broken", "Cynical"],
    "action": ["Aggressive", "Bold", "Reckless", "Driven"],
    "mystery": ["Secretive", "Enigmatic", "Calculating", "Suspicious"],
    "calm": ["Friendly", "Helpful", "Welcoming", "Neutral"],
    "horror": ["Fearful", "Mad", "Paranoid", "Haunted"]
}


class DefaultMoodManager:
    """Default mood manager that returns neutral values."""

    def __init__(self):
        self._current_mood = "neutral"

    @property
    def current_mood(self) -> str:
        return self._current_mood

    @current_mood.setter
    def current_mood(self, value: str):
        self._current_mood = value

    def influence_roll(self, base_roll: int) -> int:
        return base_roll


class DefaultTableLoader:
    """Default table loader using built-in pools."""

    def load_table(self, setting: str, category: str, table_name: str) -> list[str]:
        """Load table from default pools."""
        setting_data = DEFAULT_POOLS.get(setting, DEFAULT_POOLS["core"])
        return setting_data.get(table_name, [])

    def get_available_settings(self) -> list[str]:
        """Return available settings."""
        return list(DEFAULT_POOLS.keys())


class NPCGenerator:
    """Generator for setting-aware NPCs."""

    def __init__(
        self,
        mood_manager: Optional[MoodManager] = None,
        table_loader: Optional[TableLoader] = None,
        rng: Optional[random.Random] = None
    ):
        """
        Initialize the NPC generator.

        Args:
            mood_manager: Optional mood system for influencing generation
            table_loader: Optional table loader for custom data
            rng: Optional random number generator for reproducibility
        """
        self.mood_manager = mood_manager or DefaultMoodManager()
        self.table_loader = table_loader or DefaultTableLoader()
        self.rng = rng or random.Random()
        self._current_setting = "core"

    @property
    def current_setting(self) -> str:
        """Get current setting."""
        return self._current_setting

    @current_setting.setter
    def current_setting(self, value: str):
        """Set current setting."""
        available = self.table_loader.get_available_settings()
        if value in available:
            self._current_setting = value
        else:
            raise ValueError(f"Unknown setting: {value}. Available: {available}")

    def _get_pool(self, setting: str, pool_name: str) -> list[str]:
        """Get a pool of values, falling back to defaults if needed."""
        # Try table loader first
        pool = self.table_loader.load_table(setting, "npcs", pool_name)
        if pool:
            return pool

        # Fall back to default pools
        setting_pools = DEFAULT_POOLS.get(setting, DEFAULT_POOLS["core"])
        return setting_pools.get(pool_name, DEFAULT_POOLS["core"].get(pool_name, []))

    def _apply_mood_influence(self, pool: list[str], pool_type: str) -> list[str]:
        """Weight pool based on current mood."""
        mood = self.mood_manager.current_mood

        if mood == "neutral" or pool_type not in ["traits", "dispositions"]:
            return pool

        influenced = MOOD_INFLUENCES.get(mood, [])
        if not influenced:
            return pool

        # Create weighted pool - influenced items appear 3x as often
        weighted = []
        for item in pool:
            if item in influenced:
                weighted.extend([item] * 3)
            else:
                weighted.append(item)

        return weighted if weighted else pool

    def generate(self, setting: Optional[str] = None) -> NPC:
        """
        Generate a random NPC for the specified or current setting.

        Args:
            setting: Optional setting override. Uses current_setting if None.

        Returns:
            Generated NPC with all components
        """
        setting = setting or self._current_setting

        # Get pools for this setting
        names = self._get_pool(setting, "names")
        roles = self._get_pool(setting, "roles")
        traits = self._apply_mood_influence(self._get_pool(setting, "traits"), "traits")
        secrets = self._get_pool(setting, "secrets")
        dispositions = self._apply_mood_influence(
            self._get_pool(setting, "dispositions"), "dispositions"
        )

        # Generate component
        component = NPCComponent(
            name=self.rng.choice(names) if names else "Unknown",
            role=self.rng.choice(roles) if roles else "Wanderer",
            trait=self.rng.choice(traits) if traits else "Unremarkable",
            secret=self.rng.choice(secrets) if secrets else "None apparent",
            disposition=self.rng.choice(dispositions) if dispositions else "Neutral"
        )

        # Create NPC with mood influence note
        mood = self.mood_manager.current_mood
        mood_note = mood if mood != "neutral" else ""

        return NPC.from_component(component, setting, mood_note)

    def generate_batch(self, count: int, setting: Optional[str] = None) -> list[NPC]:
        """
        Generate multiple NPCs.

        Args:
            count: Number of NPCs to generate
            setting: Optional setting override

        Returns:
            List of generated NPCs
        """
        return [self.generate(setting) for _ in range(count)]


# Module-level generator instance
_generator = NPCGenerator()


def generate(setting: Optional[str] = None) -> NPC:
    """Generate an NPC using the default generator."""
    return _generator.generate(setting)


def generate_batch(count: int, setting: Optional[str] = None) -> list[NPC]:
    """Generate multiple NPCs using the default generator."""
    return _generator.generate_batch(count, setting)


def set_setting(setting: str) -> str:
    """Set the current setting."""
    _generator.current_setting = setting
    return _generator.current_setting


def get_settings() -> list[str]:
    """Get available settings."""
    return _generator.table_loader.get_available_settings()


if __name__ == "__main__":
    import sys
    args = sys.argv[1:]

    if "--help" in args or "-h" in args:
        print("Oracle NPC Generator")
        print()
        print("Usage: python -m oracle.npc [options]")
        print()
        print("Options:")
        print("  --setting <name>  Generate for specific setting (fantasy/scifi/cyberpunk/etc)")
        print("  --count <n>       Generate multiple NPCs")
        print("  --list            List available settings")
        print()
        print("Examples:")
        print("  python -m oracle.npc")
        print("  python -m oracle.npc --setting fantasy")
        print("  python -m oracle.npc --setting weird_war --count 3")
    else:
        setting = None
        count = 1

        i = 0
        while i < len(args):
            if args[i] == "--setting" and i + 1 < len(args):
                setting = args[i + 1]
                i += 2
            elif args[i] == "--count" and i + 1 < len(args):
                try:
                    count = int(args[i + 1])
                except ValueError:
                    count = 1
                i += 2
            elif args[i] == "--list":
                print("Available settings:")
                for s in get_settings():
                    print(f"  - {s}")
                sys.exit(0)
            else:
                i += 1

        if count == 1:
            npc = generate(setting)
            print(npc)
        else:
            npcs = generate_batch(count, setting)
            for i, npc in enumerate(npcs, 1):
                print(f"--- NPC {i} ---")
                print(npc)
                print()
