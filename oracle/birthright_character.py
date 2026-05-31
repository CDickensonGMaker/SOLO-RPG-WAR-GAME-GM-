"""Birthright character sheet system for Oracle.

Provides character creation, management, and display for
Birthright 5e campaign play.
"""

import json
import random
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Any


class Culture(Enum):
    """Cerilian human cultures."""
    ANUIREAN = "Anuirean"
    BRECHT = "Brecht"
    KHINASI = "Khinasi"
    RJURIK = "Rjurik"
    VOS = "Vos"
    SIDHELIEN = "Sidhelien"  # Elf
    KARAMHUL = "Karamhul"    # Dwarf
    HALFLING = "Halfling"


class BloodlineDerivation(Enum):
    """Divine bloodline derivations."""
    ANDUIRAS = "Anduiras"
    BASAIA = "Basaïa"
    BRENNA = "Brenna"
    MASELA = "Masela"
    REYNIR = "Reynir"
    VORYNN = "Vorynn"
    AZRAI = "Azrai"
    NONE = "None"


class BloodlineStrength(Enum):
    """Bloodline strength categories."""
    NONE = "None"
    TAINTED = "Tainted"
    MINOR = "Minor"
    MAJOR = "Major"
    GREAT = "Great"
    TRUE = "True"


# Random tables for character generation
ANUIREAN_MALE_NAMES = [
    "Aeric", "Boeruine", "Caelan", "Darien", "Erin", "Faelan", "Gavin",
    "Heirl", "Ilien", "Jael", "Kael", "Laerme", "Mhoried", "Naevan",
    "Oeric", "Parnien", "Quintus", "Roele", "Suris", "Tael", "Uthred",
    "Vandiel", "Willem", "Xander", "Ybran", "Zanthus"
]

ANUIREAN_FEMALE_NAMES = [
    "Aelwyn", "Brienna", "Caeleste", "Daera", "Eliene", "Faeryl",
    "Gaelwyn", "Helena", "Ilara", "Jaelyn", "Kaela", "Laera", "Marlae",
    "Naela", "Orellia", "Paela", "Quenara", "Rosele", "Seriene", "Taela",
    "Ursula", "Vaela", "Wynna", "Xaela", "Ysabelle", "Zaela"
]

ANUIREAN_FAMILY_NAMES = [
    "Avan", "Boeruine", "Diem", "Enlien", "Flaertes", "Ghoried",
    "Halien", "Isilviere", "Jhared", "Kalien", "Liesle", "Mhoried",
    "Nichaleir", "Osoer", "Petraeus", "Roesone", "Swordhawk", "Tael",
    "Ulsain", "Vandermast", "Wierech"
]

CLASS_OPTIONS = [
    "Fighter", "Paladin", "Ranger", "Rogue", "Cleric", "Wizard",
    "Sorcerer", "Bard", "Warlock", "Barbarian", "Druid", "Monk"
]

BACKGROUNDS = [
    "Noble", "Knight", "Soldier", "Merchant", "Sage", "Acolyte",
    "Folk Hero", "Outlander", "Criminal", "Entertainer", "Guild Artisan"
]

# Bloodline ability pools by derivation
BLOOD_ABILITIES = {
    BloodlineDerivation.ANDUIRAS: [
        "Battlewise", "Courage", "Divine Aura", "Iron Will",
        "Leadership", "Protection from Evil"
    ],
    BloodlineDerivation.BASAIA: [
        "Detect Illusion", "Detect Lie", "Light of Reason",
        "Mebhaighl Sense", "Resistance (Fire)", "True Seeing"
    ],
    BloodlineDerivation.BRENNA: [
        "Character Reading", "Direction Sense", "Persuasion",
        "Travel", "Fortune's Favor", "Detect Lie"
    ],
    BloodlineDerivation.MASELA: [
        "Elemental Control (Water)", "Sea Song", "Water Breathing",
        "Resistance (Cold)", "Weather Control", "Healing"
    ],
    BloodlineDerivation.REYNIR: [
        "Animal Affinity", "Forest Walk", "Healing",
        "Poison Sense", "Nature's Wrath", "Regeneration"
    ],
    BloodlineDerivation.VORYNN: [
        "Mebhaighl Sense", "Shadow Form", "Unreadable Thoughts",
        "Detect Illusion", "Alter Appearance", "Heightened Ability"
    ],
    BloodlineDerivation.AZRAI: [
        "Blood History", "Death Touch", "Fear",
        "Poison Touch", "Shadow Form", "Touch of Decay"
    ],
}

# Number of abilities by strength
ABILITIES_BY_STRENGTH = {
    BloodlineStrength.NONE: 0,
    BloodlineStrength.TAINTED: 0,
    BloodlineStrength.MINOR: 1,
    BloodlineStrength.MAJOR: 2,
    BloodlineStrength.GREAT: 3,
    BloodlineStrength.TRUE: 4,
}


@dataclass
class AbilityScores:
    """D&D 5e ability scores."""
    strength: int = 10
    dexterity: int = 10
    constitution: int = 10
    intelligence: int = 10
    wisdom: int = 10
    charisma: int = 10

    def modifier(self, ability: str) -> int:
        """Get modifier for an ability."""
        score = getattr(self, ability.lower(), 10)
        return (score - 10) // 2

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "AbilityScores":
        return cls(**data)

    @classmethod
    def roll_4d6_drop_lowest(cls) -> "AbilityScores":
        """Generate random ability scores using 4d6 drop lowest."""
        def roll_ability():
            rolls = sorted([random.randint(1, 6) for _ in range(4)])
            return sum(rolls[1:])  # Drop lowest

        scores = [roll_ability() for _ in range(6)]
        scores.sort(reverse=True)

        return cls(
            strength=scores[0],
            dexterity=scores[1],
            constitution=scores[2],
            intelligence=scores[3],
            wisdom=scores[4],
            charisma=scores[5]
        )

    @classmethod
    def standard_array(cls) -> "AbilityScores":
        """Use standard array."""
        return cls(
            strength=15,
            dexterity=14,
            constitution=13,
            intelligence=12,
            wisdom=10,
            charisma=8
        )


@dataclass
class Bloodline:
    """Character's divine bloodline."""
    derivation: BloodlineDerivation = BloodlineDerivation.NONE
    strength: BloodlineStrength = BloodlineStrength.NONE
    score: int = 0  # 0-100+ scale if using that option
    abilities: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "derivation": self.derivation.value,
            "strength": self.strength.value,
            "score": self.score,
            "abilities": self.abilities,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Bloodline":
        return cls(
            derivation=BloodlineDerivation(data.get("derivation", "None")),
            strength=BloodlineStrength(data.get("strength", "None")),
            score=data.get("score", 0),
            abilities=data.get("abilities", []),
        )

    @classmethod
    def generate_random(cls, strength: Optional[BloodlineStrength] = None) -> "Bloodline":
        """Generate a random bloodline."""
        # Random derivation (weighted - Azrai rarer)
        derivations = list(BloodlineDerivation)
        derivations.remove(BloodlineDerivation.NONE)
        weights = [15, 15, 15, 15, 15, 15, 10]  # Azrai slightly rarer
        derivation = random.choices(derivations, weights=weights)[0]

        # Random strength if not specified
        if strength is None:
            strength = random.choices(
                [BloodlineStrength.TAINTED, BloodlineStrength.MINOR,
                 BloodlineStrength.MAJOR, BloodlineStrength.GREAT],
                weights=[20, 40, 30, 10]
            )[0]

        # Calculate score
        score_ranges = {
            BloodlineStrength.TAINTED: (1, 14),
            BloodlineStrength.MINOR: (15, 34),
            BloodlineStrength.MAJOR: (35, 54),
            BloodlineStrength.GREAT: (55, 74),
            BloodlineStrength.TRUE: (75, 100),
        }
        low, high = score_ranges.get(strength, (0, 0))
        score = random.randint(low, high)

        # Assign abilities
        num_abilities = ABILITIES_BY_STRENGTH.get(strength, 0)
        ability_pool = BLOOD_ABILITIES.get(derivation, [])
        abilities = random.sample(ability_pool, min(num_abilities, len(ability_pool)))

        return cls(
            derivation=derivation,
            strength=strength,
            score=score,
            abilities=abilities,
        )


@dataclass
class Domain:
    """Character's domain holdings (if regent)."""
    name: str = ""
    provinces: list[str] = field(default_factory=list)
    law_holdings: int = 0
    temple_holdings: int = 0
    guild_holdings: int = 0
    source_holdings: int = 0
    regency_points: int = 0
    gold_bars: int = 0
    armies: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Domain":
        return cls(**data)


@dataclass
class BirthrightCharacter:
    """Complete Birthright character sheet."""
    # Identity
    name: str = ""
    title: str = ""
    culture: Culture = Culture.ANUIREAN
    character_class: str = "Fighter"
    level: int = 1
    background: str = "Noble"
    alignment: str = "Lawful Neutral"

    # Abilities
    ability_scores: AbilityScores = field(default_factory=AbilityScores)

    # Combat
    armor_class: int = 10
    hit_points: int = 10
    max_hit_points: int = 10
    hit_dice: str = "1d10"
    speed: int = 30

    # Proficiencies
    proficiency_bonus: int = 2
    saving_throws: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=lambda: ["Common (Anuirean)"])

    # Equipment
    equipment: list[str] = field(default_factory=list)
    weapons: list[str] = field(default_factory=list)
    armor: str = ""
    gold: int = 0

    # Birthright-specific
    bloodline: Bloodline = field(default_factory=Bloodline)
    domain: Optional[Domain] = None
    is_regent: bool = False

    # Backstory
    personality_traits: list[str] = field(default_factory=list)
    ideals: list[str] = field(default_factory=list)
    bonds: list[str] = field(default_factory=list)
    flaws: list[str] = field(default_factory=list)
    backstory: str = ""

    # Notes
    notes: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "title": self.title,
            "culture": self.culture.value,
            "character_class": self.character_class,
            "level": self.level,
            "background": self.background,
            "alignment": self.alignment,
            "ability_scores": self.ability_scores.to_dict(),
            "armor_class": self.armor_class,
            "hit_points": self.hit_points,
            "max_hit_points": self.max_hit_points,
            "hit_dice": self.hit_dice,
            "speed": self.speed,
            "proficiency_bonus": self.proficiency_bonus,
            "saving_throws": self.saving_throws,
            "skills": self.skills,
            "languages": self.languages,
            "equipment": self.equipment,
            "weapons": self.weapons,
            "armor": self.armor,
            "gold": self.gold,
            "bloodline": self.bloodline.to_dict(),
            "domain": self.domain.to_dict() if self.domain else None,
            "is_regent": self.is_regent,
            "personality_traits": self.personality_traits,
            "ideals": self.ideals,
            "bonds": self.bonds,
            "flaws": self.flaws,
            "backstory": self.backstory,
            "notes": self.notes,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "BirthrightCharacter":
        """Create from dictionary."""
        return cls(
            name=data.get("name", ""),
            title=data.get("title", ""),
            culture=Culture(data.get("culture", "Anuirean")),
            character_class=data.get("character_class", "Fighter"),
            level=data.get("level", 1),
            background=data.get("background", "Noble"),
            alignment=data.get("alignment", "Lawful Neutral"),
            ability_scores=AbilityScores.from_dict(data.get("ability_scores", {})),
            armor_class=data.get("armor_class", 10),
            hit_points=data.get("hit_points", 10),
            max_hit_points=data.get("max_hit_points", 10),
            hit_dice=data.get("hit_dice", "1d10"),
            speed=data.get("speed", 30),
            proficiency_bonus=data.get("proficiency_bonus", 2),
            saving_throws=data.get("saving_throws", []),
            skills=data.get("skills", []),
            languages=data.get("languages", ["Common (Anuirean)"]),
            equipment=data.get("equipment", []),
            weapons=data.get("weapons", []),
            armor=data.get("armor", ""),
            gold=data.get("gold", 0),
            bloodline=Bloodline.from_dict(data.get("bloodline", {})),
            domain=Domain.from_dict(data["domain"]) if data.get("domain") else None,
            is_regent=data.get("is_regent", False),
            personality_traits=data.get("personality_traits", []),
            ideals=data.get("ideals", []),
            bonds=data.get("bonds", []),
            flaws=data.get("flaws", []),
            backstory=data.get("backstory", ""),
            notes=data.get("notes", []),
            created_at=data.get("created_at", datetime.now().isoformat()),
        )

    def save(self, filepath: Path) -> None:
        """Save character to JSON file."""
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, filepath: Path) -> "BirthrightCharacter":
        """Load character from JSON file."""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)

    @classmethod
    def generate_random(
        cls,
        culture: Optional[Culture] = None,
        character_class: Optional[str] = None,
        is_regent: bool = True,
        bloodline_strength: Optional[BloodlineStrength] = None
    ) -> "BirthrightCharacter":
        """Generate a random Birthright character."""

        # Random culture if not specified
        if culture is None:
            culture = random.choices(
                list(Culture),
                weights=[40, 15, 15, 10, 10, 5, 3, 2]  # Anuirean most common
            )[0]

        # Random class if not specified
        if character_class is None:
            character_class = random.choice(CLASS_OPTIONS)

        # Generate name based on culture
        if culture == Culture.ANUIREAN:
            gender = random.choice(["male", "female"])
            if gender == "male":
                first_name = random.choice(ANUIREAN_MALE_NAMES)
            else:
                first_name = random.choice(ANUIREAN_FEMALE_NAMES)
            family_name = random.choice(ANUIREAN_FAMILY_NAMES)
            name = f"{first_name} {family_name}"
        else:
            # Placeholder for other cultures
            name = f"Character of {culture.value}"

        # Generate ability scores
        ability_scores = AbilityScores.roll_4d6_drop_lowest()

        # Generate bloodline
        bloodline = Bloodline.generate_random(bloodline_strength)

        # Calculate derived stats
        con_mod = ability_scores.modifier("constitution")

        # Hit dice by class
        hit_dice_by_class = {
            "Fighter": "d10", "Paladin": "d10", "Ranger": "d10",
            "Rogue": "d8", "Cleric": "d8", "Bard": "d8", "Warlock": "d8",
            "Monk": "d8", "Druid": "d8",
            "Wizard": "d6", "Sorcerer": "d6",
            "Barbarian": "d12",
        }
        hit_die = hit_dice_by_class.get(character_class, "d8")
        hit_die_max = int(hit_die[1:])
        max_hp = hit_die_max + con_mod

        # Generate domain if regent
        domain = None
        if is_regent:
            domain = Domain(
                name=f"The {family_name} Lands" if culture == Culture.ANUIREAN else "Domain",
                provinces=[f"{name}'s Province"],
                law_holdings=random.randint(1, 3),
                temple_holdings=random.randint(0, 2),
                guild_holdings=random.randint(0, 2),
                source_holdings=random.randint(0, 1),
                regency_points=random.randint(10, 30),
                gold_bars=random.randint(5, 20),
            )

        # Generate title
        titles_by_regent = [
            "Baron", "Baroness", "Count", "Countess", "Duke", "Duchess",
            "Lord", "Lady", "Thane", "Guilder", "Patriarch", "Archpriest"
        ]
        titles_by_non_regent = [
            "Sir", "Dame", "Knight", "Squire", "Captain", "Champion"
        ]
        title = random.choice(titles_by_regent if is_regent else titles_by_non_regent)

        return cls(
            name=name,
            title=title,
            culture=culture,
            character_class=character_class,
            level=1,
            background=random.choice(BACKGROUNDS),
            ability_scores=ability_scores,
            hit_points=max_hp,
            max_hit_points=max_hp,
            hit_dice=f"1{hit_die}",
            bloodline=bloodline,
            domain=domain,
            is_regent=is_regent,
            languages=["Common (Anuirean)", "Low Brecht"] if culture == Culture.ANUIREAN else ["Common"],
            personality_traits=[
                f"I am proud of my {bloodline.derivation.value} heritage.",
            ] if bloodline.derivation != BloodlineDerivation.NONE else [],
            bonds=[
                "My domain and its people are my responsibility.",
            ] if is_regent else [],
        )


def format_character_sheet(char: dict | BirthrightCharacter) -> str:
    """Format character as a readable text sheet."""
    if isinstance(char, dict):
        c = BirthrightCharacter.from_dict(char)
    else:
        c = char

    lines = []
    lines.append("=" * 60)
    lines.append(f"  {c.title} {c.name}".center(60))
    lines.append(f"  {c.culture.value} {c.character_class} {c.level}".center(60))
    lines.append("=" * 60)
    lines.append("")

    # Ability Scores
    lines.append("ABILITY SCORES")
    lines.append("-" * 40)
    abilities = [
        ("STR", c.ability_scores.strength),
        ("DEX", c.ability_scores.dexterity),
        ("CON", c.ability_scores.constitution),
        ("INT", c.ability_scores.intelligence),
        ("WIS", c.ability_scores.wisdom),
        ("CHA", c.ability_scores.charisma),
    ]
    ability_line = "  ".join(
        f"{name}: {score:2d} ({(score-10)//2:+d})" for name, score in abilities
    )
    lines.append(ability_line)
    lines.append("")

    # Combat Stats
    lines.append("COMBAT")
    lines.append("-" * 40)
    lines.append(f"  AC: {c.armor_class}  |  HP: {c.hit_points}/{c.max_hit_points}  |  Speed: {c.speed} ft")
    lines.append(f"  Hit Dice: {c.hit_dice}  |  Proficiency: +{c.proficiency_bonus}")
    lines.append("")

    # Bloodline
    lines.append("BLOODLINE")
    lines.append("-" * 40)
    if c.bloodline.derivation != BloodlineDerivation.NONE:
        lines.append(f"  Derivation: {c.bloodline.derivation.value}")
        lines.append(f"  Strength: {c.bloodline.strength.value} (Score: {c.bloodline.score})")
        if c.bloodline.abilities:
            lines.append(f"  Blood Abilities:")
            for ability in c.bloodline.abilities:
                lines.append(f"    • {ability}")
    else:
        lines.append("  Unblooded")
    lines.append("")

    # Domain (if regent)
    if c.is_regent and c.domain:
        lines.append("DOMAIN")
        lines.append("-" * 40)
        lines.append(f"  {c.domain.name}")
        lines.append(f"  Provinces: {', '.join(c.domain.provinces) or 'None'}")
        lines.append(f"  Holdings: Law {c.domain.law_holdings} | Temple {c.domain.temple_holdings} | Guild {c.domain.guild_holdings} | Source {c.domain.source_holdings}")
        lines.append(f"  Resources: {c.domain.regency_points} RP | {c.domain.gold_bars} GB")
        if c.domain.armies:
            lines.append(f"  Armies: {', '.join(c.domain.armies)}")
        lines.append("")

    # Equipment
    if c.weapons or c.armor or c.equipment:
        lines.append("EQUIPMENT")
        lines.append("-" * 40)
        if c.weapons:
            lines.append(f"  Weapons: {', '.join(c.weapons)}")
        if c.armor:
            lines.append(f"  Armor: {c.armor}")
        if c.equipment:
            lines.append(f"  Gear: {', '.join(c.equipment[:5])}")
        lines.append(f"  Gold: {c.gold} gp")
        lines.append("")

    # Background
    lines.append("BACKGROUND")
    lines.append("-" * 40)
    lines.append(f"  {c.background} | {c.alignment}")
    if c.personality_traits:
        lines.append(f"  Traits: {c.personality_traits[0] if c.personality_traits else 'None'}")
    if c.bonds:
        lines.append(f"  Bonds: {c.bonds[0] if c.bonds else 'None'}")
    lines.append("")

    # Notes
    if c.notes:
        lines.append("NOTES")
        lines.append("-" * 40)
        for note in c.notes[:5]:
            lines.append(f"  • {note}")
        lines.append("")

    lines.append("=" * 60)

    return "\n".join(lines)


# Character storage
def get_character_dir() -> Path:
    """Get the character storage directory."""
    char_dir = Path.home() / ".oracle" / "characters"
    char_dir.mkdir(parents=True, exist_ok=True)
    return char_dir


def save_character(character: BirthrightCharacter, filename: Optional[str] = None) -> Path:
    """Save a character to the character directory."""
    if filename is None:
        safe_name = character.name.lower().replace(" ", "_")
        filename = f"{safe_name}.json"

    filepath = get_character_dir() / filename
    character.save(filepath)
    return filepath


def load_character(filename: str) -> BirthrightCharacter:
    """Load a character from the character directory."""
    filepath = get_character_dir() / filename
    return BirthrightCharacter.load(filepath)


def list_characters() -> list[str]:
    """List all saved characters."""
    char_dir = get_character_dir()
    return [f.stem for f in char_dir.glob("*.json")]
