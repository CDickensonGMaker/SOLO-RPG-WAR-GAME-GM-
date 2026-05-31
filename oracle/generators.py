"""Procedural generators for quests, NPCs, encounters, and more.

This module provides a suite of generators that combine random table results
to create rich, varied content for solo RPG play. Each generator can work
with loaded tables or fall back to sensible built-in defaults.
"""

import random
from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING
from enum import Enum

if TYPE_CHECKING:
    from .tables import TableLoader
    from .mood import MoodManager


class Difficulty(Enum):
    """Encounter difficulty levels."""
    TRIVIAL = "trivial"
    EASY = "easy"
    MODERATE = "moderate"
    HARD = "hard"
    DEADLY = "deadly"


# =============================================================================
# Fallback Data - Used when tables aren't loaded
# =============================================================================

FALLBACK_OBJECTIVES = [
    "Retrieve a stolen artifact",
    "Rescue a kidnapped person",
    "Escort someone to safety",
    "Investigate strange occurrences",
    "Eliminate a dangerous threat",
    "Deliver a sensitive package",
    "Negotiate a truce between factions",
    "Find a missing person",
    "Clear out a dangerous location",
    "Gather intelligence on an enemy",
    "Protect a location from attack",
    "Recover lost knowledge",
    "Hunt down a fugitive",
    "Break a curse or enchantment",
    "Sabotage enemy operations",
    "Establish contact with an ally",
    "Acquire rare materials",
    "Uncover a conspiracy",
    "Prevent an assassination",
    "Reclaim ancestral territory",
]

FALLBACK_QUEST_GIVERS = [
    "A desperate merchant",
    "A mysterious stranger",
    "A local authority figure",
    "A religious leader",
    "A grieving family member",
    "An old friend in trouble",
    "A dying warrior with unfinished business",
    "A guild representative",
    "A noble with a secret",
    "A village elder",
    "A scholar seeking fieldwork",
    "A retired adventurer",
    "A child who witnessed something terrible",
    "A spirit bound to this world",
    "A reformed criminal seeking redemption",
]

FALLBACK_LOCATIONS = [
    "An abandoned fortress",
    "Deep within ancient ruins",
    "A treacherous mountain pass",
    "The depths of a cursed forest",
    "A sprawling underground complex",
    "A remote island",
    "The heart of enemy territory",
    "A haunted battlefield",
    "Within a major city",
    "A sacred temple",
    "A lawless frontier town",
    "Aboard a vessel at sea",
    "A crumbling manor house",
    "The sewers beneath the city",
    "A mysterious pocket dimension",
]

FALLBACK_COMPLICATIONS = [
    "A rival party seeks the same goal",
    "The information you have is outdated",
    "A traitor lurks within your group",
    "The weather turns dangerous",
    "Your equipment is sabotaged",
    "Local authorities are hostile",
    "The target has powerful protection",
    "Time is running out",
    "An innocent will suffer if you succeed",
    "The path requires a skill you lack",
    "A blood debt must be settled first",
    "The location has shifted or moved",
    "Your presence has been anticipated",
    "A curse affects all who enter",
    "Two factions want opposite outcomes",
]

FALLBACK_REWARDS = [
    "A substantial sum of gold",
    "A powerful magical item",
    "Political favor and influence",
    "Valuable information",
    "Land and title",
    "Access to forbidden knowledge",
    "A powerful ally",
    "Debt forgiveness",
    "Training from a master",
    "A rare resource cache",
    "Legal immunity for past deeds",
    "A ship or vehicle",
    "Guild membership",
    "A family heirloom",
    "Freedom for a loved one",
]

FALLBACK_STAKES = [
    "Failure means war",
    "Innocents will die",
    "An ancient evil will awaken",
    "A bloodline will end",
    "The balance of power shifts permanently",
    "A plague spreads unchecked",
    "A portal to darkness opens",
    "A city falls to ruin",
    "Sacred knowledge is lost forever",
    "A powerful weapon falls into wrong hands",
    "Your reputation is destroyed",
    "An ally becomes an enemy",
    "The land itself is corrupted",
    "A soul is damned eternally",
    "History itself may be rewritten",
]

FALLBACK_TWISTS = [
    "The quest giver is the true villain",
    "The target is actually innocent",
    "There's a traitor in your midst",
    "The reward doesn't exist",
    "Completing the quest serves the enemy",
    "Your actions have already been predicted",
    "The 'enemy' was trying to prevent something worse",
    "Two quests are actually one",
    "The objective has already been achieved by others",
    "Success triggers a greater catastrophe",
    "The quest giver has been dead for years",
    "You've been here before and don't remember",
    "The location exists outside normal time",
    "Your employer is testing you, not hiring you",
    "The artifact is sentient and has its own agenda",
]

FALLBACK_ENCOUNTER_TYPES = ["combat", "social", "exploration", "hazard"]

FALLBACK_ENCOUNTER_DESCRIPTIONS = {
    "combat": [
        "Hostile creatures emerge from hiding",
        "An ambush from organized enemies",
        "A territorial beast defends its domain",
        "Bandits demand tribute or blood",
        "The undead rise from unmarked graves",
        "A patrol spots you and attacks",
        "Rival adventurers want what you have",
        "A summoned creature breaks free",
    ],
    "social": [
        "A merchant offers suspicious deals",
        "Travelers share rumors of the road",
        "A noble demands your service",
        "Religious pilgrims block your path",
        "A beggar knows more than they should",
        "Soldiers question your business here",
        "A con artist spins elaborate lies",
        "A former ally recognizes you",
    ],
    "exploration": [
        "An ancient door bears strange markings",
        "The path splits in multiple directions",
        "A hidden cache lies partially exposed",
        "Strange sounds echo from below",
        "Evidence of a recent battle",
        "A puzzle mechanism blocks progress",
        "Natural beauty conceals danger",
        "Signs of habitation, but no inhabitants",
    ],
    "hazard": [
        "The ground gives way beneath your feet",
        "Toxic spores fill the air",
        "A magical trap activates",
        "The structure begins to collapse",
        "Extreme weather strikes suddenly",
        "A natural disaster approaches",
        "The air itself becomes unbreathable",
        "Dangerous terrain must be crossed",
    ],
}

FALLBACK_ENVIRONMENTS = [
    "Dense forest with limited visibility",
    "Open plains with no cover",
    "Cramped underground tunnels",
    "A grand hall with many pillars",
    "Treacherous rocky terrain",
    "Knee-deep water and mud",
    "A rickety wooden structure",
    "Thick fog obscures everything",
    "Extreme cold saps your strength",
    "Oppressive heat makes concentration difficult",
    "Magical darkness resists light",
    "Multiple elevation levels",
]

FALLBACK_OUTCOMES = [
    "Decisive victory",
    "Victory with significant cost",
    "Narrow escape",
    "Mutual retreat",
    "Unexpected ally intervention",
    "The situation transforms entirely",
    "A third party benefits",
    "Pyrrhic victory",
    "Negotiated settlement",
    "Lasting consequences emerge later",
]

FALLBACK_SCENE_TYPES = ["opening", "transition", "climax", "resolution"]

FALLBACK_SCENE_PROMPTS = {
    "opening": [
        "The adventure begins with an unexpected summons",
        "A chance encounter reveals a larger plot",
        "You arrive at a place that feels wrong",
        "A desperate plea for help reaches you",
        "The calm before the storm - something is coming",
        "An old debt comes due",
        "You witness something you weren't meant to see",
        "A mysterious invitation arrives",
    ],
    "transition": [
        "Travel reveals more about your companions",
        "A rest stop becomes memorable",
        "Unexpected delays test patience",
        "A minor victory lifts spirits",
        "New information recontextualizes everything",
        "A quiet moment before the next challenge",
        "Supplies run low and decisions must be made",
        "The weather mirrors the mood",
    ],
    "climax": [
        "All paths converge at this moment",
        "The true enemy reveals themselves",
        "Everything hangs in the balance",
        "Sacrifice becomes necessary",
        "The plan falls apart and improvisation begins",
        "A desperate last stand",
        "The truth finally comes out",
        "Loyalties are tested beyond breaking",
    ],
    "resolution": [
        "The dust settles and costs are counted",
        "Unexpected consequences become clear",
        "New beginnings emerge from endings",
        "Rewards are distributed, some fairly",
        "Farewells must be said",
        "The world has changed, subtly but permanently",
        "A new threat rises from the ashes",
        "Peace, however temporary, is achieved",
    ],
}

FALLBACK_MOODS = [
    "Tense anticipation",
    "Grim determination",
    "Quiet hope",
    "Creeping dread",
    "Bittersweet nostalgia",
    "Righteous anger",
    "Weary resignation",
    "Wild excitement",
    "Solemn reverence",
    "Dark humor",
    "Desperate urgency",
    "Calm acceptance",
]

FALLBACK_SENSORY_DETAILS = [
    "The smell of smoke and ash",
    "Cold wind cutting through clothing",
    "Distant thunder rumbling",
    "The taste of copper and fear",
    "Shadows dancing at the edge of vision",
    "An unnatural silence",
    "The ground trembling slightly",
    "Strange lights in the distance",
    "An overwhelming stench of decay",
    "The sound of running water nearby",
    "Oppressive humidity",
    "The crackle of flames",
]

FALLBACK_NPC_ROLES = [
    "A scarred veteran",
    "A nervous young messenger",
    "A calculating merchant",
    "A zealous priest",
    "A weary traveler",
    "A suspicious guard",
    "A helpful local",
    "A mysterious stranger",
    "A boisterous entertainer",
    "A quiet observer",
]

FALLBACK_DEVELOPMENTS = [
    "An unexpected arrival changes everything",
    "Hidden motives are revealed",
    "Violence erupts suddenly",
    "An opportunity presents itself",
    "Trust is betrayed",
    "A deal is proposed",
    "Information comes to light",
    "Someone makes a desperate move",
    "The environment shifts",
    "A countdown begins",
]

FALLBACK_LOCATION_TYPES = [
    "settlement", "wilderness", "dungeon", "landmark", "ruin"
]

FALLBACK_LOCATION_NAMES_BY_TYPE = {
    "settlement": [
        "Haven's Rest", "Crossroads", "The Last Light", "Trader's Hope",
        "Broken Wheel", "Three Sisters", "Mudhollow", "Iron Gate",
    ],
    "wilderness": [
        "The Whispering Woods", "Deadman's Mire", "Thunder Peak",
        "The Scarred Lands", "Howling Pass", "Crystal Lake",
    ],
    "dungeon": [
        "The Forgotten Depths", "Bone Warren", "Shadow Vault",
        "The Sunken Temple", "Wyrm's Throat", "Echo Chambers",
    ],
    "landmark": [
        "The Standing Stones", "Weeping Statue", "The Great Bridge",
        "Tower of Stars", "The Frozen Falls", "World's Edge",
    ],
    "ruin": [
        "The Shattered Citadel", "Lost Arcadia", "The Burnt Palace",
        "Fallen Spire", "The Broken Keep", "Dust and Memory",
    ],
}

FALLBACK_LOCATION_FEATURES = [
    "Multiple entry points create tactical options",
    "A central gathering area dominates the space",
    "Water features throughout",
    "Elevated positions offer advantages",
    "Narrow chokepoints control movement",
    "Natural light filters in from above",
    "Ancient mechanisms still function",
    "Valuable resources lie exposed",
    "Defensible positions dot the area",
    "Hidden passages connect sections",
]

FALLBACK_HAZARDS = [
    "Unstable structures threaten collapse",
    "Poisonous flora grows unchecked",
    "Traps remain active from past inhabitants",
    "The air carries disease",
    "Extreme temperatures test endurance",
    "Magical anomalies warp reality",
    "Predators hunt these grounds",
    "Flooding is a constant risk",
    "Radiation or corruption lingers",
    "The terrain itself is treacherous",
]

FALLBACK_INHABITANTS = [
    "Territorial creatures lair here",
    "Bandits use this as a hideout",
    "Refugees have made this home",
    "A cult performs rituals here",
    "Traders pass through regularly",
    "Soldiers maintain a presence",
    "The undead roam without purpose",
    "Scavengers pick through remains",
    "A hermit seeks solitude",
    "Something ancient sleeps here",
]

FALLBACK_SECRETS = [
    "A hidden cache of supplies",
    "A passage to somewhere unexpected",
    "Evidence of a terrible crime",
    "An artifact of power",
    "The truth about a historical event",
    "A survivor who shouldn't be alive",
    "A portal to another place",
    "Written records of value",
    "A sleeping guardian",
    "The source of local legends",
]

FALLBACK_BETRAYALS = [
    "Your closest ally has been working for the enemy all along",
    "The quest giver hired another group to eliminate you after completion",
    "A trusted contact sold your plans to the highest bidder",
    "The reward was a trap designed to identify and eliminate threats",
    "Your employer intends to blame you for their crimes",
]

FALLBACK_REVELATIONS = [
    "The villain is related to a party member",
    "The artifact you seek is already in your possession, transformed",
    "The 'ancient evil' was actually a containment measure",
    "Two separate threats are actually one entity",
    "The prophecy was mistranslated - the meaning is opposite",
    "Your actions have been part of a larger ritual",
    "The mentor figure created the problem they trained you to solve",
]

FALLBACK_ESCALATIONS = [
    "A more powerful entity takes interest in the conflict",
    "The scope expands from local to regional",
    "Time pressure intensifies dramatically",
    "Resources become critically scarce",
    "Collateral damage spirals out of control",
    "Personal stakes are raised when loved ones are targeted",
    "The enemy reveals they were holding back",
]


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class GeneratedQuest:
    """A procedurally generated quest/mission.

    Attributes:
        objective: The primary goal of the quest.
        quest_giver: Who is offering this quest.
        location: Where the quest takes place.
        complications: List of obstacles or challenges.
        reward: What is offered for completion.
        stakes: What happens if the quest fails.
        twist: Optional plot twist for complex quests.
    """
    objective: str
    quest_giver: str
    location: str
    complications: list[str]
    reward: str
    stakes: str
    twist: Optional[str] = None

    def __str__(self) -> str:
        """Return a rich formatted string representation."""
        lines = [
            "=" * 60,
            "QUEST",
            "=" * 60,
            "",
            f"Objective: {self.objective}",
            f"Quest Giver: {self.quest_giver}",
            f"Location: {self.location}",
            "",
            "Complications:",
        ]
        for comp in self.complications:
            lines.append(f"  - {comp}")
        lines.extend([
            "",
            f"Reward: {self.reward}",
            f"Stakes: {self.stakes}",
        ])
        if self.twist:
            lines.extend(["", f"Twist: {self.twist}"])
        lines.append("=" * 60)
        return "\n".join(lines)


@dataclass
class GeneratedEncounter:
    """A procedurally generated encounter.

    Attributes:
        type: The encounter category (combat, social, exploration, hazard).
        description: What the encounter involves.
        difficulty: How challenging the encounter is.
        complications: Additional factors affecting the encounter.
        environment: The physical setting and conditions.
        possible_outcomes: Ways the encounter might resolve.
    """
    type: str
    description: str
    difficulty: Difficulty
    complications: list[str]
    environment: str
    possible_outcomes: list[str]

    def __str__(self) -> str:
        """Return a rich formatted string representation."""
        lines = [
            "-" * 50,
            f"ENCOUNTER: {self.type.upper()}",
            "-" * 50,
            "",
            f"Description: {self.description}",
            f"Difficulty: {self.difficulty.value.title()}",
            f"Environment: {self.environment}",
            "",
            "Complications:",
        ]
        for comp in self.complications:
            lines.append(f"  - {comp}")
        lines.append("")
        lines.append("Possible Outcomes:")
        for outcome in self.possible_outcomes:
            lines.append(f"  - {outcome}")
        lines.append("-" * 50)
        return "\n".join(lines)


@dataclass
class GeneratedScene:
    """A procedurally generated scene prompt.

    Attributes:
        type: The scene category (opening, transition, climax, resolution).
        prompt: The main scene setup.
        mood: The emotional tone of the scene.
        sensory_details: Atmospheric details to enhance immersion.
        npcs_present: Characters involved in the scene.
        potential_developments: Ways the scene might evolve.
    """
    type: str
    prompt: str
    mood: str
    sensory_details: list[str]
    npcs_present: list[str]
    potential_developments: list[str]

    def __str__(self) -> str:
        """Return a rich formatted string representation."""
        lines = [
            "~" * 50,
            f"SCENE: {self.type.upper()}",
            "~" * 50,
            "",
            f"Setup: {self.prompt}",
            f"Mood: {self.mood}",
            "",
            "Sensory Details:",
        ]
        for detail in self.sensory_details:
            lines.append(f"  - {detail}")
        if self.npcs_present:
            lines.append("")
            lines.append("NPCs Present:")
            for npc in self.npcs_present:
                lines.append(f"  - {npc}")
        lines.append("")
        lines.append("Potential Developments:")
        for dev in self.potential_developments:
            lines.append(f"  - {dev}")
        lines.append("~" * 50)
        return "\n".join(lines)


@dataclass
class GeneratedLocation:
    """A procedurally generated location.

    Attributes:
        name: The location's name.
        type: The location category.
        description: Overall description.
        features: Notable features and landmarks.
        hazards: Dangers present at this location.
        inhabitants: Who or what lives here.
        secrets: Hidden elements to discover.
    """
    name: str
    type: str
    description: str
    features: list[str]
    hazards: list[str]
    inhabitants: list[str]
    secrets: list[str]

    def __str__(self) -> str:
        """Return a rich formatted string representation."""
        lines = [
            "#" * 50,
            f"LOCATION: {self.name}",
            f"Type: {self.type.title()}",
            "#" * 50,
            "",
            f"Description: {self.description}",
            "",
            "Features:",
        ]
        for feat in self.features:
            lines.append(f"  - {feat}")
        if self.hazards:
            lines.append("")
            lines.append("Hazards:")
            for haz in self.hazards:
                lines.append(f"  - {haz}")
        if self.inhabitants:
            lines.append("")
            lines.append("Inhabitants:")
            for inh in self.inhabitants:
                lines.append(f"  - {inh}")
        if self.secrets:
            lines.append("")
            lines.append("Secrets:")
            for sec in self.secrets:
                lines.append(f"  - {sec}")
        lines.append("#" * 50)
        return "\n".join(lines)


# =============================================================================
# Generator Classes
# =============================================================================

class QuestGenerator:
    """Generates procedural quests by combining table results.

    The generator pulls from multiple tables to create varied and
    interesting quests. Higher complexity adds more complications
    and increases the chance of plot twists.

    Attributes:
        tables: TableLoader instance for accessing random tables.
        rng: Random number generator for consistent results.
    """

    def __init__(self, table_loader: Optional["TableLoader"] = None, rng: Optional[random.Random] = None):
        """Initialize the quest generator.

        Args:
            table_loader: TableLoader for accessing tables. If None, uses fallback data.
            rng: Random number generator. Defaults to standard random.
        """
        self.tables = table_loader
        self.rng = rng or random.Random()

    def _roll_from_table_or_fallback(
        self,
        table_name: str,
        fallback: list[str],
        setting: str = "core",
        mood: str = "neutral"
    ) -> str:
        """Roll on a table if available, otherwise use fallback data.

        Args:
            table_name: Name of the table to try loading.
            fallback: List of fallback options if table unavailable.
            setting: Setting folder for table resolution.
            mood: Mood folder for table resolution.

        Returns:
            A randomly selected string result.
        """
        if self.tables:
            table = self.tables.load_table(table_name, setting, mood)
            if table and not table.is_empty():
                from .tables import TableRoller
                roller = TableRoller(self.rng)
                entry = roller.roll(table)
                if entry:
                    return entry.text
        return self.rng.choice(fallback)

    def generate(self, complexity: int = 2) -> GeneratedQuest:
        """Generate a quest with given complexity.

        Complexity affects the number of complications and likelihood
        of plot twists:
        - 1: Simple quest, 1 complication, no twist
        - 2: Standard quest, 1-2 complications, rare twist (20%)
        - 3: Complex quest, 2-3 complications, occasional twist (40%)
        - 4: Intricate quest, 3-4 complications, likely twist (60%)
        - 5: Epic quest, 4-5 complications, guaranteed twist

        Args:
            complexity: Quest complexity from 1-5.

        Returns:
            A GeneratedQuest instance.
        """
        complexity = max(1, min(5, complexity))

        # Roll for core elements
        objective = self._roll_from_table_or_fallback("objectives", FALLBACK_OBJECTIVES)
        quest_giver = self._roll_from_table_or_fallback("quest_givers", FALLBACK_QUEST_GIVERS)
        location = self._roll_from_table_or_fallback("locations", FALLBACK_LOCATIONS)
        reward = self._roll_from_table_or_fallback("rewards", FALLBACK_REWARDS)
        stakes = self._roll_from_table_or_fallback("stakes", FALLBACK_STAKES)

        # Determine number of complications based on complexity
        min_complications = complexity
        max_complications = complexity + 1
        num_complications = self.rng.randint(min_complications, max_complications)
        num_complications = min(num_complications, 5)  # Cap at 5

        complications = []
        used_complications = set()
        for _ in range(num_complications):
            comp = self._roll_from_table_or_fallback("complications", FALLBACK_COMPLICATIONS)
            # Avoid exact duplicates
            attempts = 0
            while comp in used_complications and attempts < 10:
                comp = self._roll_from_table_or_fallback("complications", FALLBACK_COMPLICATIONS)
                attempts += 1
            used_complications.add(comp)
            complications.append(comp)

        # Determine if there's a twist based on complexity
        twist_chance = (complexity - 1) * 0.2  # 0%, 20%, 40%, 60%, 80%
        if complexity >= 5:
            twist_chance = 1.0

        twist = None
        if self.rng.random() < twist_chance:
            twist = self._roll_from_table_or_fallback("twists", FALLBACK_TWISTS)

        return GeneratedQuest(
            objective=objective,
            quest_giver=quest_giver,
            location=location,
            complications=complications,
            reward=reward,
            stakes=stakes,
            twist=twist
        )


class EncounterGenerator:
    """Generates procedural encounters.

    Creates varied encounters by combining type, description,
    environmental factors, and possible outcomes. Integrates
    with the mood system for tone-appropriate results.

    Attributes:
        tables: TableLoader instance for accessing random tables.
        mood: MoodManager for mood-aware generation.
        rng: Random number generator for consistent results.
    """

    def __init__(
        self,
        table_loader: Optional["TableLoader"] = None,
        mood_manager: Optional["MoodManager"] = None,
        rng: Optional[random.Random] = None
    ):
        """Initialize the encounter generator.

        Args:
            table_loader: TableLoader for accessing tables.
            mood_manager: MoodManager for mood-aware generation.
            rng: Random number generator. Defaults to standard random.
        """
        self.tables = table_loader
        self.mood = mood_manager
        self.rng = rng or random.Random()

    def _get_mood_folder(self) -> str:
        """Get the current mood folder name for table resolution."""
        if self.mood and hasattr(self.mood, 'state'):
            return self.mood.state.tone.folder
        return "neutral"

    def _get_setting_folder(self) -> str:
        """Get the current setting folder name for table resolution."""
        if self.mood and hasattr(self.mood, 'state'):
            return self.mood.state.setting.folder
        return "core"

    def _roll_from_table_or_fallback(
        self,
        table_name: str,
        fallback: list[str],
        setting: Optional[str] = None,
        mood: Optional[str] = None
    ) -> str:
        """Roll on a table if available, otherwise use fallback data."""
        setting = setting or self._get_setting_folder()
        mood = mood or self._get_mood_folder()

        if self.tables:
            table = self.tables.load_table(table_name, setting, mood)
            if table and not table.is_empty():
                from .tables import TableRoller
                roller = TableRoller(self.rng)
                entry = roller.roll(table)
                if entry:
                    return entry.text
        return self.rng.choice(fallback)

    def generate(
        self,
        encounter_type: Optional[str] = None,
        difficulty: Difficulty = Difficulty.MODERATE
    ) -> GeneratedEncounter:
        """Generate an encounter, optionally specifying type and difficulty.

        Args:
            encounter_type: One of 'combat', 'social', 'exploration', 'hazard'.
                          If None, randomly selected.
            difficulty: The encounter difficulty level.

        Returns:
            A GeneratedEncounter instance.
        """
        # Determine encounter type
        if encounter_type is None:
            encounter_type = self.rng.choice(FALLBACK_ENCOUNTER_TYPES)
        encounter_type = encounter_type.lower()

        if encounter_type not in FALLBACK_ENCOUNTER_DESCRIPTIONS:
            encounter_type = "combat"

        # Get description for this type
        descriptions = FALLBACK_ENCOUNTER_DESCRIPTIONS.get(encounter_type, [])
        description = self._roll_from_table_or_fallback(
            f"encounters_{encounter_type}",
            descriptions if descriptions else ["An unexpected encounter"]
        )

        # Get environment
        environment = self._roll_from_table_or_fallback(
            "environments",
            FALLBACK_ENVIRONMENTS
        )

        # Number of complications based on difficulty
        difficulty_to_complications = {
            Difficulty.TRIVIAL: (0, 1),
            Difficulty.EASY: (1, 1),
            Difficulty.MODERATE: (1, 2),
            Difficulty.HARD: (2, 3),
            Difficulty.DEADLY: (3, 4),
        }
        min_comp, max_comp = difficulty_to_complications.get(difficulty, (1, 2))
        num_complications = self.rng.randint(min_comp, max_comp)

        complications = []
        for _ in range(num_complications):
            comp = self._roll_from_table_or_fallback(
                "complications",
                FALLBACK_COMPLICATIONS
            )
            if comp not in complications:
                complications.append(comp)

        # Get possible outcomes
        num_outcomes = self.rng.randint(2, 4)
        outcomes = []
        for _ in range(num_outcomes):
            outcome = self.rng.choice(FALLBACK_OUTCOMES)
            if outcome not in outcomes:
                outcomes.append(outcome)

        return GeneratedEncounter(
            type=encounter_type,
            description=description,
            difficulty=difficulty,
            complications=complications,
            environment=environment,
            possible_outcomes=outcomes
        )

    def generate_combat(self, difficulty: Difficulty = Difficulty.MODERATE) -> GeneratedEncounter:
        """Generate a combat encounter.

        Args:
            difficulty: The encounter difficulty level.

        Returns:
            A combat-type GeneratedEncounter.
        """
        return self.generate(encounter_type="combat", difficulty=difficulty)

    def generate_social(self) -> GeneratedEncounter:
        """Generate a social encounter.

        Social encounters are typically moderate difficulty.

        Returns:
            A social-type GeneratedEncounter.
        """
        return self.generate(encounter_type="social", difficulty=Difficulty.MODERATE)

    def generate_exploration(self) -> GeneratedEncounter:
        """Generate an exploration encounter.

        Returns:
            An exploration-type GeneratedEncounter.
        """
        return self.generate(encounter_type="exploration", difficulty=Difficulty.MODERATE)


class SceneGenerator:
    """Generates scene prompts for solo play.

    Creates evocative scene setups with mood, sensory details,
    NPC presence, and potential developments to inspire play.

    Attributes:
        tables: TableLoader instance for accessing random tables.
        rng: Random number generator for consistent results.
    """

    def __init__(self, table_loader: Optional["TableLoader"] = None, rng: Optional[random.Random] = None):
        """Initialize the scene generator.

        Args:
            table_loader: TableLoader for accessing tables.
            rng: Random number generator. Defaults to standard random.
        """
        self.tables = table_loader
        self.rng = rng or random.Random()

    def _roll_from_table_or_fallback(self, table_name: str, fallback: list[str]) -> str:
        """Roll on a table if available, otherwise use fallback data."""
        if self.tables:
            table = self.tables.load_table(table_name)
            if table and not table.is_empty():
                from .tables import TableRoller
                roller = TableRoller(self.rng)
                entry = roller.roll(table)
                if entry:
                    return entry.text
        return self.rng.choice(fallback)

    def generate(self, scene_type: Optional[str] = None) -> GeneratedScene:
        """Generate a scene prompt.

        Args:
            scene_type: One of 'opening', 'transition', 'climax', 'resolution'.
                       If None, randomly selected.

        Returns:
            A GeneratedScene instance.
        """
        # Determine scene type
        if scene_type is None:
            scene_type = self.rng.choice(FALLBACK_SCENE_TYPES)
        scene_type = scene_type.lower()

        if scene_type not in FALLBACK_SCENE_PROMPTS:
            scene_type = "transition"

        # Get prompt for this type
        prompts = FALLBACK_SCENE_PROMPTS.get(scene_type, [])
        prompt = self._roll_from_table_or_fallback(
            f"scenes_{scene_type}",
            prompts if prompts else ["Something happens"]
        )

        # Get mood
        mood = self._roll_from_table_or_fallback("moods", FALLBACK_MOODS)

        # Get sensory details (2-4)
        num_details = self.rng.randint(2, 4)
        sensory_details = []
        for _ in range(num_details):
            detail = self._roll_from_table_or_fallback(
                "sensory_details",
                FALLBACK_SENSORY_DETAILS
            )
            if detail not in sensory_details:
                sensory_details.append(detail)

        # Get NPCs present (0-3)
        num_npcs = self.rng.randint(0, 3)
        npcs_present = []
        for _ in range(num_npcs):
            npc = self._roll_from_table_or_fallback("npc_roles", FALLBACK_NPC_ROLES)
            if npc not in npcs_present:
                npcs_present.append(npc)

        # Get potential developments (2-4)
        num_developments = self.rng.randint(2, 4)
        developments = []
        for _ in range(num_developments):
            dev = self._roll_from_table_or_fallback(
                "developments",
                FALLBACK_DEVELOPMENTS
            )
            if dev not in developments:
                developments.append(dev)

        return GeneratedScene(
            type=scene_type,
            prompt=prompt,
            mood=mood,
            sensory_details=sensory_details,
            npcs_present=npcs_present,
            potential_developments=developments
        )

    def opening_scene(self) -> GeneratedScene:
        """Generate an opening scene.

        Returns:
            An opening-type GeneratedScene.
        """
        return self.generate(scene_type="opening")

    def transition_scene(self) -> GeneratedScene:
        """Generate a transition scene.

        Returns:
            A transition-type GeneratedScene.
        """
        return self.generate(scene_type="transition")

    def climax_scene(self) -> GeneratedScene:
        """Generate a climax scene.

        Returns:
            A climax-type GeneratedScene.
        """
        return self.generate(scene_type="climax")


class LocationGenerator:
    """Generates procedural locations.

    Creates locations with features, hazards, inhabitants, and
    secrets. Integrates with the mood system for appropriate
    atmosphere.

    Attributes:
        tables: TableLoader instance for accessing random tables.
        mood: MoodManager for mood-aware generation.
        rng: Random number generator for consistent results.
    """

    def __init__(
        self,
        table_loader: Optional["TableLoader"] = None,
        mood_manager: Optional["MoodManager"] = None,
        rng: Optional[random.Random] = None
    ):
        """Initialize the location generator.

        Args:
            table_loader: TableLoader for accessing tables.
            mood_manager: MoodManager for mood-aware generation.
            rng: Random number generator. Defaults to standard random.
        """
        self.tables = table_loader
        self.mood = mood_manager
        self.rng = rng or random.Random()

    def _get_mood_folder(self) -> str:
        """Get the current mood folder name for table resolution."""
        if self.mood and hasattr(self.mood, 'state'):
            return self.mood.state.tone.folder
        return "neutral"

    def _get_setting_folder(self) -> str:
        """Get the current setting folder name for table resolution."""
        if self.mood and hasattr(self.mood, 'state'):
            return self.mood.state.setting.folder
        return "core"

    def _roll_from_table_or_fallback(
        self,
        table_name: str,
        fallback: list[str],
        setting: Optional[str] = None,
        mood: Optional[str] = None
    ) -> str:
        """Roll on a table if available, otherwise use fallback data."""
        setting = setting or self._get_setting_folder()
        mood = mood or self._get_mood_folder()

        if self.tables:
            table = self.tables.load_table(table_name, setting, mood)
            if table and not table.is_empty():
                from .tables import TableRoller
                roller = TableRoller(self.rng)
                entry = roller.roll(table)
                if entry:
                    return entry.text
        return self.rng.choice(fallback)

    def generate(self, location_type: Optional[str] = None) -> GeneratedLocation:
        """Generate a location with features, hazards, inhabitants, secrets.

        Args:
            location_type: One of 'settlement', 'wilderness', 'dungeon',
                          'landmark', 'ruin'. If None, randomly selected.

        Returns:
            A GeneratedLocation instance.
        """
        # Determine location type
        if location_type is None:
            location_type = self.rng.choice(FALLBACK_LOCATION_TYPES)
        location_type = location_type.lower()

        if location_type not in FALLBACK_LOCATION_NAMES_BY_TYPE:
            location_type = "wilderness"

        # Get name for this type
        names = FALLBACK_LOCATION_NAMES_BY_TYPE.get(location_type, ["Unknown Place"])
        name = self._roll_from_table_or_fallback(
            f"location_names_{location_type}",
            names
        )

        # Generate description based on mood and type
        description = self._generate_description(location_type)

        # Get features (2-4)
        num_features = self.rng.randint(2, 4)
        features = []
        for _ in range(num_features):
            feat = self._roll_from_table_or_fallback(
                "location_features",
                FALLBACK_LOCATION_FEATURES
            )
            if feat not in features:
                features.append(feat)

        # Get hazards (0-2 normally, more in dangerous areas)
        mood_folder = self._get_mood_folder()
        hazard_modifier = 1 if mood_folder in ("grimdark", "gritty") else 0
        num_hazards = self.rng.randint(0, 2 + hazard_modifier)
        hazards = []
        for _ in range(num_hazards):
            haz = self._roll_from_table_or_fallback(
                "location_hazards",
                FALLBACK_HAZARDS
            )
            if haz not in hazards:
                hazards.append(haz)

        # Get inhabitants (1-3)
        num_inhabitants = self.rng.randint(1, 3)
        inhabitants = []
        for _ in range(num_inhabitants):
            inh = self._roll_from_table_or_fallback(
                "location_inhabitants",
                FALLBACK_INHABITANTS
            )
            if inh not in inhabitants:
                inhabitants.append(inh)

        # Get secrets (1-2)
        num_secrets = self.rng.randint(1, 2)
        secrets = []
        for _ in range(num_secrets):
            sec = self._roll_from_table_or_fallback(
                "location_secrets",
                FALLBACK_SECRETS
            )
            if sec not in secrets:
                secrets.append(sec)

        return GeneratedLocation(
            name=name,
            type=location_type,
            description=description,
            features=features,
            hazards=hazards,
            inhabitants=inhabitants,
            secrets=secrets
        )

    def _generate_description(self, location_type: str) -> str:
        """Generate a contextual description for the location type."""
        descriptions = {
            "settlement": [
                "A cluster of buildings where travelers find temporary respite",
                "A community carved from the harsh landscape",
                "Civilization's foothold against the wilderness",
                "A place where commerce and secrets flow freely",
            ],
            "wilderness": [
                "Untamed lands where nature holds dominion",
                "Territory where few dare to venture",
                "A stretch of wild country with its own rules",
                "Land that remembers a time before civilization",
            ],
            "dungeon": [
                "Dark passages descending into the unknown",
                "Ancient halls that have witnessed terrible things",
                "A labyrinth where light is a precious commodity",
                "Chambers built for purposes best forgotten",
            ],
            "landmark": [
                "A notable feature visible for miles around",
                "A place that draws travelers and pilgrims alike",
                "Something that defies easy explanation",
                "A point of reference in an otherwise featureless land",
            ],
            "ruin": [
                "The skeleton of something once magnificent",
                "Stones that remember better days",
                "A testament to the impermanence of civilization",
                "Decay reclaiming what was built by hands now dust",
            ],
        }
        options = descriptions.get(location_type, ["A notable location"])
        return self.rng.choice(options)


class PlotTwistGenerator:
    """Generates plot twists and story complications.

    Creates dramatic revelations, betrayals, and escalations
    to add unexpected turns to ongoing narratives.

    Attributes:
        tables: TableLoader instance for accessing random tables.
        rng: Random number generator for consistent results.
    """

    def __init__(self, table_loader: Optional["TableLoader"] = None, rng: Optional[random.Random] = None):
        """Initialize the plot twist generator.

        Args:
            table_loader: TableLoader for accessing tables.
            rng: Random number generator. Defaults to standard random.
        """
        self.tables = table_loader
        self.rng = rng or random.Random()

    def _roll_from_table_or_fallback(self, table_name: str, fallback: list[str]) -> str:
        """Roll on a table if available, otherwise use fallback data."""
        if self.tables:
            table = self.tables.load_table(table_name)
            if table and not table.is_empty():
                from .tables import TableRoller
                roller = TableRoller(self.rng)
                entry = roller.roll(table)
                if entry:
                    return entry.text
        return self.rng.choice(fallback)

    def generate(self, twist_type: Optional[str] = None) -> str:
        """Generate a plot twist.

        Args:
            twist_type: One of 'betrayal', 'revelation', 'escalation'.
                       If None, randomly selected.

        Returns:
            A plot twist description string.
        """
        twist_types = ["betrayal", "revelation", "escalation"]

        if twist_type is None:
            twist_type = self.rng.choice(twist_types)
        twist_type = twist_type.lower()

        if twist_type == "betrayal":
            return self.betrayal()
        elif twist_type == "revelation":
            return self.revelation()
        elif twist_type == "escalation":
            return self.escalation()
        else:
            # Generic twist from fallback
            return self._roll_from_table_or_fallback("twists", FALLBACK_TWISTS)

    def betrayal(self) -> str:
        """Generate a betrayal twist.

        Returns:
            A betrayal-themed plot twist.
        """
        return self._roll_from_table_or_fallback("twists_betrayal", FALLBACK_BETRAYALS)

    def revelation(self) -> str:
        """Generate a revelation twist.

        Returns:
            A revelation-themed plot twist.
        """
        return self._roll_from_table_or_fallback("twists_revelation", FALLBACK_REVELATIONS)

    def escalation(self) -> str:
        """Generate an escalation twist.

        Returns:
            An escalation-themed plot twist.
        """
        return self._roll_from_table_or_fallback("twists_escalation", FALLBACK_ESCALATIONS)


# =============================================================================
# Convenience Functions
# =============================================================================

# Module-level default instances (created lazily)
_default_quest_gen: Optional[QuestGenerator] = None
_default_encounter_gen: Optional[EncounterGenerator] = None
_default_scene_gen: Optional[SceneGenerator] = None
_default_location_gen: Optional[LocationGenerator] = None
_default_twist_gen: Optional[PlotTwistGenerator] = None


def _get_quest_generator() -> QuestGenerator:
    """Get or create the default quest generator."""
    global _default_quest_gen
    if _default_quest_gen is None:
        try:
            from .tables import TableLoader
            _default_quest_gen = QuestGenerator(TableLoader())
        except ImportError:
            _default_quest_gen = QuestGenerator()
    return _default_quest_gen


def _get_encounter_generator() -> EncounterGenerator:
    """Get or create the default encounter generator."""
    global _default_encounter_gen
    if _default_encounter_gen is None:
        try:
            from .tables import TableLoader
            from .mood import MoodManager
            _default_encounter_gen = EncounterGenerator(TableLoader(), MoodManager())
        except ImportError:
            _default_encounter_gen = EncounterGenerator()
    return _default_encounter_gen


def _get_scene_generator() -> SceneGenerator:
    """Get or create the default scene generator."""
    global _default_scene_gen
    if _default_scene_gen is None:
        try:
            from .tables import TableLoader
            _default_scene_gen = SceneGenerator(TableLoader())
        except ImportError:
            _default_scene_gen = SceneGenerator()
    return _default_scene_gen


def _get_location_generator() -> LocationGenerator:
    """Get or create the default location generator."""
    global _default_location_gen
    if _default_location_gen is None:
        try:
            from .tables import TableLoader
            from .mood import MoodManager
            _default_location_gen = LocationGenerator(TableLoader(), MoodManager())
        except ImportError:
            _default_location_gen = LocationGenerator()
    return _default_location_gen


def _get_twist_generator() -> PlotTwistGenerator:
    """Get or create the default plot twist generator."""
    global _default_twist_gen
    if _default_twist_gen is None:
        try:
            from .tables import TableLoader
            _default_twist_gen = PlotTwistGenerator(TableLoader())
        except ImportError:
            _default_twist_gen = PlotTwistGenerator()
    return _default_twist_gen


def generate_quest(complexity: int = 2) -> GeneratedQuest:
    """Generate a quest using default generators.

    Args:
        complexity: Quest complexity from 1-5. Higher values add more
                   complications and increase twist likelihood.

    Returns:
        A GeneratedQuest instance.

    Example:
        >>> quest = generate_quest(complexity=3)
        >>> print(quest)
    """
    return _get_quest_generator().generate(complexity)


def generate_encounter(difficulty: str = "moderate") -> GeneratedEncounter:
    """Generate an encounter using default generators.

    Args:
        difficulty: One of 'trivial', 'easy', 'moderate', 'hard', 'deadly'.

    Returns:
        A GeneratedEncounter instance.

    Example:
        >>> encounter = generate_encounter("hard")
        >>> print(encounter)
    """
    try:
        diff = Difficulty(difficulty.lower())
    except ValueError:
        diff = Difficulty.MODERATE
    return _get_encounter_generator().generate(difficulty=diff)


def generate_scene(scene_type: Optional[str] = None) -> GeneratedScene:
    """Generate a scene prompt.

    Args:
        scene_type: One of 'opening', 'transition', 'climax', 'resolution'.
                   If None, randomly selected.

    Returns:
        A GeneratedScene instance.

    Example:
        >>> scene = generate_scene("opening")
        >>> print(scene)
    """
    return _get_scene_generator().generate(scene_type)


def generate_location(location_type: Optional[str] = None) -> GeneratedLocation:
    """Generate a location.

    Args:
        location_type: One of 'settlement', 'wilderness', 'dungeon',
                      'landmark', 'ruin'. If None, randomly selected.

    Returns:
        A GeneratedLocation instance.

    Example:
        >>> location = generate_location("dungeon")
        >>> print(location)
    """
    return _get_location_generator().generate(location_type)


def generate_twist(twist_type: Optional[str] = None) -> str:
    """Generate a plot twist.

    Args:
        twist_type: One of 'betrayal', 'revelation', 'escalation'.
                   If None, randomly selected.

    Returns:
        A plot twist description string.

    Example:
        >>> twist = generate_twist("revelation")
        >>> print(twist)
    """
    return _get_twist_generator().generate(twist_type)


if __name__ == "__main__":
    import sys
    args = sys.argv[1:]

    if "--help" in args or "-h" in args or not args:
        print("Oracle Procedural Generators")
        print()
        print("Usage: python -m oracle.generators <type> [options]")
        print()
        print("Types:")
        print("  quest       Generate a quest/mission")
        print("  encounter   Generate an encounter")
        print("  scene       Generate a scene prompt")
        print("  location    Generate a location")
        print("  twist       Generate a plot twist")
        print()
        print("Options:")
        print("  --complexity <1-5>   Quest complexity (default: 2)")
        print("  --difficulty <level> Encounter difficulty (trivial/easy/moderate/hard/deadly)")
        print("  --type <subtype>     Specific subtype (e.g., 'opening' for scene)")
        print()
        print("Examples:")
        print("  python -m oracle.generators quest")
        print("  python -m oracle.generators quest --complexity 4")
        print("  python -m oracle.generators encounter --difficulty hard")
        print("  python -m oracle.generators scene --type opening")
        print("  python -m oracle.generators twist --type betrayal")
    else:
        gen_type = args[0] if args else "quest"
        complexity = 2
        difficulty = "moderate"
        subtype = None

        i = 1
        while i < len(args):
            if args[i] == "--complexity" and i + 1 < len(args):
                try:
                    complexity = int(args[i + 1])
                except ValueError:
                    pass
                i += 2
            elif args[i] == "--difficulty" and i + 1 < len(args):
                difficulty = args[i + 1]
                i += 2
            elif args[i] == "--type" and i + 1 < len(args):
                subtype = args[i + 1]
                i += 2
            else:
                i += 1

        try:
            if gen_type == "quest":
                result = generate_quest(complexity)
            elif gen_type == "encounter":
                result = generate_encounter(difficulty)
            elif gen_type == "scene":
                result = generate_scene(subtype)
            elif gen_type == "location":
                result = generate_location(subtype)
            elif gen_type == "twist":
                result = generate_twist(subtype)
            else:
                print(f"Unknown generator type: {gen_type}")
                sys.exit(1)

            print(result)
        except Exception as e:
            print(f"Error: {e}")
