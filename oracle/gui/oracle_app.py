"""
Oracle - GM-Driven Solo Game Master

A conversational solo RPG/Wargame experience where the GM drives the action.
The player responds to situations rather than managing everything manually.
"""

import re
import random
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime

import dearpygui.dearpygui as dpg

from oracle.gm.brain import GameMasterBrain
from oracle.gm.personality import PERSONALITIES, GMPersonality
from oracle.gm.memory import SessionMemory
from oracle.generators import (
    QuestGenerator,
    SceneGenerator,
    LocationGenerator,
    EncounterGenerator,
    PlotTwistGenerator,
    GeneratedQuest,
    GeneratedScene,
    GeneratedLocation,
    Difficulty,
)
from oracle.fate import Oracle, Likelihood, OracleResult
from oracle.dice import DiceRoller
from oracle.wargame import WargameAI, Doctrine, Aggression
from oracle.tables import TableLoader
from oracle.mood import MoodManager, Setting, Tone, Mode


# =============================================================================
# Configuration
# =============================================================================

SETTINGS = ["fantasy", "cyberpunk", "scifi_military", "historical", "weird_war"]
MOODS = ["grimdark", "neutral", "hopeful"]
PERSONALITIES_LIST = ["classic", "dark_narrator", "tavern_keeper", "war_commander", "mystical_seer"]
GAME_SYSTEMS = [
    "Generic",
    "Oldhammer 2E",
    "40K 10th Edition",
    "Kill Team",
    "The Old World",
    "Grimdark Future",
    "Trench Crusade",
    "Age of Fantasy",
]
DOCTRINES = ["horde", "elite", "defensive", "alpha_strike", "guerrilla"]

# Color scheme
COLORS = {
    "gm": (200, 180, 140),
    "user": (100, 180, 220),
    "system": (150, 150, 150),
    "oracle_yes": (140, 200, 140),
    "oracle_no": (200, 140, 140),
    "dice": (140, 180, 220),
    "header": (200, 180, 140),
    "subheader": (180, 160, 120),
    "muted": (120, 120, 120),
}


@dataclass
class ChatMessage:
    """A chat message in the conversation."""
    text: str
    sender: str  # "gm", "user", "system"
    msg_type: str = "normal"  # "normal", "oracle", "dice", "event", "scene"
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class SessionConfig:
    """Configuration for the current session."""
    game_type: str = "rpg"  # "rpg" or "wargame"
    setting: str = "fantasy"
    mood: str = "neutral"
    personality: str = "classic"
    chaos: int = 5
    # Wargame-specific
    game_system: str = "Generic"
    doctrine: str = "elite"
    aggression: str = "balanced"


@dataclass
class WargameState:
    """State tracking for wargame mode."""
    turn: int = 1
    phase: str = "deployment"  # deployment, movement, shooting, combat, morale, end
    player_casualties: int = 0
    enemy_casualties: int = 0
    player_units: List[str] = field(default_factory=list)
    enemy_units: List[str] = field(default_factory=list)
    objectives: List[Dict[str, Any]] = field(default_factory=list)
    battle_log: List[str] = field(default_factory=list)
    scenario: str = ""
    victory_conditions: str = ""


# =============================================================================
# Main Application
# =============================================================================

class OracleApp:
    """
    GM-Driven Oracle Application.

    The GM presents situations and asks "What do you do?"
    The player responds. The GM handles all the mechanics.
    """

    def __init__(self):
        # Core systems
        self.gm: Optional[GameMasterBrain] = None
        self.oracle = Oracle()
        self.dice = DiceRoller()
        self.wargame_ai: Optional[WargameAI] = None

        # Table loading and mood management
        self.table_loader = TableLoader()
        self.mood_manager = MoodManager()

        # Generators (will be reconfigured in _initialize_session with proper setting/mood)
        self.quest_gen: Optional[QuestGenerator] = None
        self.scene_gen: Optional[SceneGenerator] = None
        self.location_gen: Optional[LocationGenerator] = None
        self.encounter_gen: Optional[EncounterGenerator] = None
        self.twist_gen: Optional[PlotTwistGenerator] = None

        # Session state
        self.config = SessionConfig()
        self.messages: List[ChatMessage] = []
        self.session_started = False

        # Current session data (auto-updated by GM)
        self.current_quest: Optional[GeneratedQuest] = None
        self.current_location: Optional[GeneratedLocation] = None
        self.current_scene: Optional[GeneratedScene] = None

        # Wargame state (for wargame mode)
        self.wargame_state: Optional[WargameState] = None

        # UI state
        self.sidebar_collapsed = False

    def run(self):
        """Run the application."""
        dpg.create_context()

        # Register fonts (if available)
        self._setup_fonts()

        # Create viewport
        dpg.create_viewport(
            title="Oracle - Solo Game Master",
            width=1200,
            height=800,
            min_width=800,
            min_height=600,
        )

        # Build startup wizard first
        self._build_startup_wizard()

        dpg.setup_dearpygui()
        dpg.show_viewport()
        dpg.start_dearpygui()
        dpg.destroy_context()

    def _setup_fonts(self):
        """Setup fonts if available."""
        # Use default fonts - could be extended to load custom fonts
        pass

    # =========================================================================
    # STARTUP WIZARD
    # =========================================================================

    def _build_startup_wizard(self):
        """Build the startup wizard modal."""
        viewport_width = dpg.get_viewport_width()
        viewport_height = dpg.get_viewport_height()
        wizard_width = 500
        wizard_height = 520

        with dpg.window(
            label="Oracle - Solo Game Master",
            tag="startup_wizard",
            width=wizard_width,
            height=wizard_height,
            pos=[(viewport_width - wizard_width) // 2, (viewport_height - wizard_height) // 2],
            no_close=True,
            no_collapse=True,
            no_resize=True,
            no_move=False,
        ):
            # Title
            dpg.add_text("ORACLE", color=COLORS["header"])
            dpg.add_text("Solo Game Master", color=COLORS["muted"])
            dpg.add_separator()
            dpg.add_spacer(height=10)

            # Greeting
            dpg.add_text(
                '"Greetings, traveler. Let us set the stage for your tale..."',
                color=COLORS["gm"],
                wrap=wizard_width - 40,
            )
            dpg.add_spacer(height=15)

            # Game Type
            dpg.add_text("GAME TYPE", color=COLORS["subheader"])
            with dpg.group(horizontal=True):
                dpg.add_radio_button(
                    items=["Solo RPG", "Wargame"],
                    tag="wizard_game_type",
                    callback=self._on_game_type_change,
                    default_value="Solo RPG",
                    horizontal=True,
                )
            dpg.add_spacer(height=10)

            # Setting
            dpg.add_text("SETTING", color=COLORS["subheader"])
            dpg.add_combo(
                items=[s.replace("_", " ").title() for s in SETTINGS],
                tag="wizard_setting",
                default_value="Fantasy",
                width=-1,
            )
            dpg.add_spacer(height=10)

            # Mood
            dpg.add_text("MOOD", color=COLORS["subheader"])
            dpg.add_combo(
                items=[m.title() for m in MOODS],
                tag="wizard_mood",
                default_value="Neutral",
                width=-1,
            )
            dpg.add_spacer(height=10)

            # GM Personality
            dpg.add_text("GM PERSONALITY", color=COLORS["subheader"])
            personality_names = {
                "classic": "Classic Oracle",
                "dark_narrator": "Dark Narrator",
                "tavern_keeper": "Tavern Keeper",
                "war_commander": "War Commander",
                "mystical_seer": "Mystical Seer",
            }
            dpg.add_combo(
                items=[personality_names[p] for p in PERSONALITIES_LIST],
                tag="wizard_personality",
                default_value="Classic Oracle",
                width=-1,
            )
            dpg.add_spacer(height=10)

            # Chaos Level
            dpg.add_text("CHAOS LEVEL", color=COLORS["subheader"])
            with dpg.group(horizontal=True):
                dpg.add_slider_int(
                    tag="wizard_chaos",
                    default_value=5,
                    min_value=1,
                    max_value=9,
                    width=-80,
                    callback=self._on_chaos_slider_change,
                )
                dpg.add_text("5", tag="wizard_chaos_label")
            with dpg.group(horizontal=True):
                dpg.add_text("1 = Ordered", color=COLORS["muted"])
                dpg.add_spacer(width=120)
                dpg.add_text("9 = Chaotic", color=COLORS["muted"])

            # Wargame-specific options (hidden by default)
            with dpg.group(tag="wizard_wargame_options", show=False):
                dpg.add_spacer(height=10)
                dpg.add_separator()
                dpg.add_spacer(height=10)

                dpg.add_text("GAME SYSTEM", color=COLORS["subheader"])
                dpg.add_combo(
                    items=GAME_SYSTEMS,
                    tag="wizard_game_system",
                    default_value="Generic",
                    width=-1,
                )

                dpg.add_text("AI DOCTRINE", color=COLORS["subheader"])
                dpg.add_combo(
                    items=[d.replace("_", " ").title() for d in DOCTRINES],
                    tag="wizard_doctrine",
                    default_value="Elite",
                    width=-1,
                )

                dpg.add_text("AI AGGRESSION", color=COLORS["subheader"])
                dpg.add_combo(
                    items=["Passive", "Cautious", "Balanced", "Aggressive", "Reckless"],
                    tag="wizard_aggression",
                    default_value="Balanced",
                    width=-1,
                )

            dpg.add_spacer(height=20)

            # Begin button
            dpg.add_button(
                label="BEGIN ADVENTURE",
                tag="wizard_begin_btn",
                callback=self._on_begin_adventure,
                width=-1,
                height=40,
            )

    def _on_game_type_change(self, sender, app_data, user_data):
        """Handle game type radio button change."""
        is_wargame = app_data == "Wargame"
        dpg.configure_item("wizard_wargame_options", show=is_wargame)

        # Adjust wizard height
        new_height = 620 if is_wargame else 520
        dpg.configure_item("startup_wizard", height=new_height)

    def _on_chaos_slider_change(self, sender, app_data, user_data):
        """Update chaos label."""
        dpg.set_value("wizard_chaos_label", str(app_data))

    def _on_begin_adventure(self):
        """Handle Begin Adventure button click."""
        # Gather configuration
        game_type = dpg.get_value("wizard_game_type")
        self.config.game_type = "wargame" if game_type == "Wargame" else "rpg"

        setting_display = dpg.get_value("wizard_setting")
        self.config.setting = setting_display.lower().replace(" ", "_")

        mood_display = dpg.get_value("wizard_mood")
        self.config.mood = mood_display.lower()

        personality_display = dpg.get_value("wizard_personality")
        personality_map = {
            "Classic Oracle": "classic",
            "Dark Narrator": "dark_narrator",
            "Tavern Keeper": "tavern_keeper",
            "War Commander": "war_commander",
            "Mystical Seer": "mystical_seer",
        }
        self.config.personality = personality_map.get(personality_display, "classic")

        self.config.chaos = dpg.get_value("wizard_chaos")

        # Wargame options
        if self.config.game_type == "wargame":
            self.config.game_system = dpg.get_value("wizard_game_system")

            doctrine_display = dpg.get_value("wizard_doctrine")
            self.config.doctrine = doctrine_display.lower().replace(" ", "_")

            aggression_display = dpg.get_value("wizard_aggression")
            self.config.aggression = aggression_display.lower()

        # Initialize systems
        self._initialize_session()

        # Delete wizard and show main window
        dpg.delete_item("startup_wizard")
        self._build_main_window()

        # Generate opening content
        self._generate_opening()

    # =========================================================================
    # SESSION INITIALIZATION
    # =========================================================================

    def _initialize_session(self):
        """Initialize the GM and other systems for the session."""
        # Get personality
        personality = PERSONALITIES.get(self.config.personality, PERSONALITIES["classic"])

        # Create GM brain
        self.gm = GameMasterBrain(personality=personality)
        self.gm.set_mode(self.config.game_type)
        self.gm.set_setting(self.config.setting)
        self.gm.memory.chaos_factor = self.config.chaos
        self.gm.memory.setting = self.config.setting

        # Set oracle chaos
        self.oracle.chaos = self.config.chaos

        # Configure mood manager with correct setting and tone
        setting_map = {
            "fantasy": Setting.FANTASY,
            "cyberpunk": Setting.CYBERPUNK,
            "scifi_military": Setting.SCIFI_MILITARY,
            "historical": Setting.HISTORICAL,
            "weird_war": Setting.WEIRD_WAR,
        }
        tone_map = {
            "grimdark": Tone.GRIMDARK,
            "neutral": Tone.NEUTRAL,
            "hopeful": Tone.HOPEFUL,
        }

        selected_setting = setting_map.get(self.config.setting, Setting.FANTASY)
        selected_tone = tone_map.get(self.config.mood, Tone.NEUTRAL)

        self.mood_manager.set_setting(selected_setting, apply_defaults=True)
        self.mood_manager.set_tone(selected_tone)

        if self.config.game_type == "wargame":
            self.mood_manager.set_mode(Mode.WARGAME)
        else:
            self.mood_manager.set_mode(Mode.RPG)

        # Create generators with proper setting/mood context
        # These will use tables from the correct setting folder (e.g., cyberpunk/, fantasy/)
        self.quest_gen = QuestGenerator(table_loader=self.table_loader)
        self.scene_gen = SceneGenerator(table_loader=self.table_loader)
        self.location_gen = LocationGenerator(
            table_loader=self.table_loader,
            mood_manager=self.mood_manager
        )
        self.encounter_gen = EncounterGenerator(
            table_loader=self.table_loader,
            mood_manager=self.mood_manager
        )
        self.twist_gen = PlotTwistGenerator(table_loader=self.table_loader)

        # Initialize wargame AI if needed
        if self.config.game_type == "wargame":
            self.wargame_ai = WargameAI()

            # Set doctrine
            doctrine_map = {
                "horde": Doctrine.HORDE,
                "elite": Doctrine.ELITE,
                "defensive": Doctrine.DEFENSIVE,
                "alpha_strike": Doctrine.ALPHA_STRIKE,
                "guerrilla": Doctrine.GUERRILLA,
            }
            self.wargame_ai.doctrine = doctrine_map.get(self.config.doctrine, Doctrine.ELITE)

            # Set aggression
            aggression_map = {
                "passive": Aggression.PASSIVE,
                "cautious": Aggression.CAUTIOUS,
                "balanced": Aggression.BALANCED,
                "aggressive": Aggression.AGGRESSIVE,
                "reckless": Aggression.RECKLESS,
            }
            self.wargame_ai.aggression = aggression_map.get(self.config.aggression, Aggression.BALANCED)

        self.session_started = True

    # =========================================================================
    # MAIN WINDOW
    # =========================================================================

    def _build_main_window(self):
        """Build the main application window."""
        with dpg.window(
            label="Oracle",
            tag="main_window",
            no_close=True,
            no_collapse=True,
            no_title_bar=True,
        ):
            # Make window fill viewport
            dpg.set_primary_window("main_window", True)

            with dpg.group(horizontal=True):
                # Chat area (primary)
                with dpg.child_window(tag="chat_area", width=-280, height=-1, border=False):
                    self._build_chat_area()

                # Sidebar (collapsible session info)
                with dpg.child_window(tag="sidebar", width=270, height=-1, border=True):
                    self._build_sidebar()

    def _build_chat_area(self):
        """Build the main chat area."""
        # Header bar
        with dpg.group(horizontal=True):
            dpg.add_text("ORACLE", color=COLORS["header"])
            dpg.add_text(f" - {self.config.setting.replace('_', ' ').title()}", color=COLORS["muted"])
            dpg.add_spacer()

            # Quick info
            dpg.add_text("Chaos:", color=COLORS["muted"])
            dpg.add_text(str(self.config.chaos), tag="header_chaos", color=COLORS["gm"])

        dpg.add_separator()

        # Chat log
        with dpg.child_window(tag="chat_log", height=-70, border=False):
            dpg.add_text("Preparing your adventure...", color=COLORS["muted"], tag="chat_loading")

        # Input area
        dpg.add_separator()
        with dpg.group():
            dpg.add_input_text(
                tag="chat_input",
                hint="What do you do? (Questions ending in ? auto-trigger Oracle, /roll for dice)",
                width=-1,
                on_enter=True,
                callback=self._on_send,
            )
            with dpg.group(horizontal=True):
                dpg.add_button(label="Send", callback=self._on_send, width=80)
                dpg.add_button(label="Oracle", callback=self._show_oracle_dialog, width=80)
                dpg.add_button(label="Dice", callback=self._show_dice_dialog, width=80)
                dpg.add_spacer()
                dpg.add_button(label="Menu", callback=self._show_menu, width=80)

    def _build_sidebar(self):
        """Build the session info sidebar (read-only, auto-updates)."""
        dpg.add_text("SESSION", color=COLORS["header"])
        dpg.add_separator()

        # Scene section
        dpg.add_text("SCENE", color=COLORS["subheader"])
        with dpg.group(tag="sidebar_scene"):
            dpg.add_text("Loading...", color=COLORS["muted"])
        dpg.add_spacer(height=10)

        # Chaos slider
        dpg.add_text("CHAOS", color=COLORS["subheader"])
        with dpg.group(horizontal=True):
            dpg.add_slider_int(
                tag="sidebar_chaos_slider",
                default_value=self.config.chaos,
                min_value=1,
                max_value=9,
                width=-40,
                callback=self._on_sidebar_chaos_change,
            )
            dpg.add_text(str(self.config.chaos), tag="sidebar_chaos_label")
        dpg.add_spacer(height=10)

        # Quest section
        dpg.add_text("QUEST", color=COLORS["subheader"])
        with dpg.group(tag="sidebar_quest"):
            dpg.add_text("None active", color=COLORS["muted"])
        dpg.add_spacer(height=10)

        # NPCs Present section
        dpg.add_text("NPCs PRESENT", color=COLORS["subheader"])
        with dpg.group(tag="sidebar_npcs"):
            dpg.add_text("None", color=COLORS["muted"])
        dpg.add_spacer(height=10)

        # Threads section
        dpg.add_text("THREADS", color=COLORS["subheader"])
        with dpg.group(tag="sidebar_threads"):
            dpg.add_text("None active", color=COLORS["muted"])
        dpg.add_spacer(height=10)

        dpg.add_separator()

        # Session controls
        with dpg.group(horizontal=True):
            dpg.add_button(label="Save", callback=self._save_session, width=60)
            dpg.add_button(label="Load", callback=self._load_session, width=60)
            dpg.add_button(label="History", callback=self._show_history, width=70)

    # =========================================================================
    # CAMPAIGN GENERATION
    # =========================================================================

    def _generate_opening(self):
        """Generate the opening content for the adventure."""
        # Remove loading text
        if dpg.does_item_exist("chat_loading"):
            dpg.delete_item("chat_loading")

        # Setting-specific location types
        setting_location_types = {
            "fantasy": ["settlement", "wilderness", "dungeon", "landmark"],
            "cyberpunk": ["settlement", "landmark", "ruin"],  # maps to streets/buildings
            "scifi_military": ["settlement", "landmark", "wilderness"],  # maps to ships/planets/bases
            "historical": ["settlement", "wilderness", "landmark"],
            "weird_war": ["settlement", "wilderness", "ruin"],  # maps to trenches/buildings
        }

        # Get appropriate location types for this setting
        location_types = setting_location_types.get(self.config.setting, ["settlement", "wilderness"])
        location_type = random.choice(location_types)

        # Generate location using setting-aware generator
        self.current_location = self.location_gen.generate(location_type)

        # Generate opening scene
        self.current_scene = self.scene_gen.opening_scene()

        # Generate quest hook with setting context
        self.current_quest = self.quest_gen.generate(complexity=2)

        # Set scene in GM memory
        self.gm.memory.set_scene(
            location=self.current_location.name,
            description=self.current_location.description,
            mood=self.current_scene.mood.lower().split()[0] if self.current_scene.mood else "neutral",
            npcs=self.current_scene.npcs_present,
        )

        # Add quest as thread
        self.gm.memory.add_thread(
            self.current_quest.objective[:50],
            self.current_quest.objective,
            importance=7
        )

        # Build the opening narrative with setting-specific flavor
        opening_parts = []

        # Setting-specific flavor text
        setting_intros = {
            "fantasy": "The threads of destiny stir...",
            "cyberpunk": "The neon-lit streets pulse with danger and opportunity...",
            "scifi_military": "Orders have come through. The situation is critical...",
            "historical": "History unfolds around you...",
            "weird_war": "The front line between worlds grows thin...",
        }

        # GM greeting based on personality
        opening_parts.append(self.gm.greet())
        opening_parts.append("")

        # Setting flavor
        intro = setting_intros.get(self.config.setting, "Your story begins...")
        opening_parts.append(f"*{intro}*")
        opening_parts.append("")

        # Location description with setting context
        opening_parts.append(f"You find yourself at **{self.current_location.name}**, {self.current_location.description.lower()}")
        opening_parts.append("")

        # Location features (setting-specific details)
        if self.current_location.features:
            features_text = ". ".join(self.current_location.features[:2])
            opening_parts.append(f"{features_text}.")
            opening_parts.append("")

        # Atmosphere from scene
        if self.current_scene.sensory_details:
            atmosphere = ". ".join(self.current_scene.sensory_details[:3])
            opening_parts.append(f"*{atmosphere}.*")
            opening_parts.append("")

        # Known dangers/hazards
        if self.current_location.hazards:
            opening_parts.append(f"**Warning:** {self.current_location.hazards[0]}")
            opening_parts.append("")

        # NPCs present with more detail
        if self.current_scene.npcs_present:
            opening_parts.append("**Present:**")
            for npc in self.current_scene.npcs_present:
                # Generate a brief disposition hint
                dispositions = ["watches you warily", "seems preoccupied", "eyes you with interest",
                               "appears nervous", "radiates quiet confidence", "looks desperate"]
                disposition_hint = random.choice(dispositions)
                opening_parts.append(f"- {npc} {disposition_hint}")

                # Track NPCs
                self.gm.memory.track_entity(
                    name=npc,
                    entity_type="npc",
                    description=disposition_hint,
                    disposition=random.randint(-20, 20)
                )
            opening_parts.append("")

        # Quest hook with more context
        opening_parts.append(f"{self.current_quest.quest_giver} approaches with urgent business:")
        opening_parts.append(f'*"{self.current_quest.objective}"*')
        opening_parts.append("")

        # Quest details
        opening_parts.append(f"**Location:** {self.current_quest.location}")
        opening_parts.append(f"**Stakes:** {self.current_quest.stakes}")
        opening_parts.append(f"**Reward:** {self.current_quest.reward}")
        opening_parts.append("")

        # Complications hint
        if self.current_quest.complications:
            opening_parts.append(f"*Rumor has it: {self.current_quest.complications[0]}*")
            opening_parts.append("")

        # The prompt
        opening_parts.append("**What do you do?**")

        # Add opening as GM message
        opening_text = "\n".join(opening_parts)
        self._add_message("gm", opening_text, "scene")

        # Refresh sidebar
        self._refresh_sidebar()

    # =========================================================================
    # CHAT & INPUT HANDLING
    # =========================================================================

    def _on_send(self, sender=None, app_data=None):
        """Handle sending user input."""
        text = dpg.get_value("chat_input")
        if not text or not text.strip():
            return

        text = text.strip()
        dpg.set_value("chat_input", "")

        # Process the input
        self._process_input(text)

    def _process_input(self, text: str):
        """Process user input and route appropriately."""
        text_lower = text.lower().strip()

        # Check for dice command
        if text_lower.startswith("/roll ") or text_lower.startswith("/r "):
            self._handle_dice_command(text)
            return

        # Check for oracle question (ends with ?)
        if text.endswith("?"):
            self._handle_oracle_question(text)
            return

        # Otherwise, treat as action/statement
        self._handle_action(text)

    def _handle_dice_command(self, text: str):
        """Handle a dice rolling command."""
        # Extract notation
        if text.lower().startswith("/roll "):
            notation = text[6:].strip()
        elif text.lower().startswith("/r "):
            notation = text[3:].strip()
        else:
            notation = text.strip()

        # Add user message
        self._add_message("user", f"*Rolling {notation}...*")

        try:
            result = self.dice.roll(notation)

            # Format result
            rolls_str = ", ".join(map(str, result.rolls))
            if result.dropped:
                dropped_str = ", ".join(map(str, result.dropped))
                result_text = f"**Rolled [{rolls_str}]** (dropped: {dropped_str})"
            else:
                result_text = f"**Rolled [{rolls_str}]**"

            if result.modifier != 0:
                result_text += f" {'+' if result.modifier > 0 else ''}{result.modifier}"

            result_text += f" = **{result.total}**"

            # GM provides narrative context
            narrative = self._get_roll_narrative(result.total, notation)
            response = f"{result_text}\n\n{narrative}"

            self._add_message("gm", response, "dice")

        except ValueError as e:
            self._add_message("system", f"Invalid dice notation: {notation}")

        self._refresh_sidebar()

    def _get_roll_narrative(self, total: int, notation: str) -> str:
        """Generate narrative context for a dice roll."""
        # Simple interpretation based on common systems
        if "d20" in notation.lower():
            if total >= 20:
                return "*A perfect result! The fates smile upon you.*"
            elif total >= 15:
                return "*A solid success.*"
            elif total >= 10:
                return "*A modest result, neither exceptional nor poor.*"
            elif total >= 5:
                return "*A mediocre outcome. Complications may arise.*"
            else:
                return "*A poor result. Things do not go as planned.*"
        elif "d100" in notation.lower() or "d%" in notation.lower():
            if total <= 10:
                return "*An exceptional result!*"
            elif total <= 30:
                return "*Success.*"
            elif total <= 50:
                return "*A close call.*"
            elif total <= 70:
                return "*Difficulties emerge.*"
            else:
                return "*The situation grows complicated.*"
        else:
            return "*The dice have spoken.*"

    def _handle_oracle_question(self, text: str):
        """Handle an oracle question."""
        question = text.rstrip("?").strip()

        # Add user question
        self._add_message("user", f"*{text}*")

        # Determine likelihood from context clues
        likelihood = self._detect_likelihood(text)

        # Ask oracle
        result = self.oracle.ask(question, likelihood)

        # Format response
        response_parts = []

        # Roll info
        response_parts.append(f"*Rolling... {result.roll} (Chaos: {result.chaos}, Likelihood: {result.likelihood.display})*")
        response_parts.append("")

        # Answer with emphasis
        answer_text = result.answer.value
        if "YES" in answer_text:
            response_parts.append(f"**{answer_text}**")
        else:
            response_parts.append(f"**{answer_text}**")

        # Generate interpretation - use enum name (yes_and, yes, etc.)
        interpretation = self.gm.responder.interpret_oracle(
            result.answer.name.lower(),
            question,
            self.gm.memory
        )
        response_parts.append("")
        response_parts.append(interpretation)

        # Check for random event
        if result.random_event:
            event_type = "positive" if "YES" in answer_text else "negative"
            event = self.gm.responder.random_event(event_type, self.gm.memory)
            response_parts.append("")
            response_parts.append(f"**Random Event!** {event}")

            # Adjust chaos
            self.oracle.chaos_up()
            self.gm.memory.chaos_factor = self.oracle.chaos
            self._add_message("system", f"Chaos increased to {self.oracle.chaos}")

        response = "\n".join(response_parts)
        self._add_message("gm", response, "oracle")

        self._refresh_sidebar()

    def _detect_likelihood(self, question: str) -> Likelihood:
        """Detect likelihood from question phrasing."""
        q_lower = question.lower()

        # Very unlikely indicators
        if any(word in q_lower for word in ["impossible", "no way", "never"]):
            return Likelihood.IMPOSSIBLE
        if any(word in q_lower for word in ["unlikely", "doubtful", "probably not"]):
            return Likelihood.UNLIKELY
        # Very likely indicators
        if any(word in q_lower for word in ["certain", "definitely", "surely"]):
            return Likelihood.CERTAIN
        if any(word in q_lower for word in ["likely", "probably", "most likely"]):
            return Likelihood.LIKELY

        return Likelihood.EVEN

    def _handle_action(self, text: str):
        """Handle a player action or statement."""
        # Add user message
        self._add_message("user", text)

        # Get GM response
        response = self.gm.process_input(text)

        # Maybe generate additional content based on chaos
        # Higher chaos = more random events (~5% at chaos 1, ~50% at chaos 9)
        event_chance = self.gm.memory.chaos_factor / 18
        if random.random() < event_chance:
            response += self._generate_random_event()

        # Check if we should prompt for action
        if not response.strip().endswith("?"):
            response += "\n\n**What do you do?**"

        self._add_message("gm", response)

        self._refresh_sidebar()

    def _generate_random_event(self) -> str:
        """Generate a substantial random event appropriate to the setting."""
        event_type = random.choice(["encounter", "complication", "npc_arrival", "discovery"])

        event_parts = ["\n\n---\n"]

        if event_type == "encounter":
            # Full encounter with details
            encounter = self.encounter_gen.generate()
            event_parts.append(f"**ENCOUNTER: {encounter.type.upper()}**\n")
            event_parts.append(f"{encounter.description}\n")
            event_parts.append(f"\n*Environment: {encounter.environment}*\n")

            if encounter.complications:
                event_parts.append(f"\n**Complication:** {encounter.complications[0]}")
                self.gm.memory.add_thread(
                    f"Deal with: {encounter.complications[0][:30]}",
                    encounter.complications[0],
                    importance=5
                )

            if len(encounter.possible_outcomes) > 1:
                event_parts.append("\n\n*Possible outcomes:*")
                for outcome in encounter.possible_outcomes[:3]:
                    event_parts.append(f"\n- {outcome}")

        elif event_type == "complication":
            # Setting-specific complications
            complications_by_setting = {
                "fantasy": [
                    "A curse begins to manifest on your equipment",
                    "Scouts report enemies moving to cut off your retreat",
                    "The weather turns supernaturally foul",
                    "A blood debt collector arrives to claim what's owed",
                    "Your supplies have been contaminated or stolen",
                ],
                "cyberpunk": [
                    "Your cyberware glitches at the worst moment",
                    "A corporate hit squad has been dispatched",
                    "NET security just traced your last hack",
                    "Your fixer just sold you out to the highest bidder",
                    "Local gang marks you as a target",
                ],
                "scifi_military": [
                    "Enemy reinforcements detected on approach vector",
                    "Your extraction has been delayed - hold position",
                    "Friendly fire incident complicates the situation",
                    "Command has changed objectives mid-mission",
                    "Critical equipment malfunction in hostile territory",
                ],
                "historical": [
                    "Political enemies have learned of your mission",
                    "Disease spreads through your camp",
                    "Supply lines have been cut",
                    "A spy has been discovered among your ranks",
                    "The local population turns hostile",
                ],
                "weird_war": [
                    "Unnatural fog rolls in, hiding something terrible",
                    "Your dead comrades don't stay dead",
                    "Reality fractures - the trenches shift impossibly",
                    "The enemy deploys occult weapons",
                    "Something ancient awakens beneath the battlefield",
                ],
            }

            complications = complications_by_setting.get(
                self.config.setting, ["An unexpected complication arises"]
            )
            complication = random.choice(complications)

            event_parts.append("**NEW COMPLICATION**\n")
            event_parts.append(f"{complication}\n")
            self.gm.memory.add_thread(complication[:40], complication, importance=6)

        elif event_type == "npc_arrival":
            # Setting-specific NPC arrivals
            npc_arrivals_by_setting = {
                "fantasy": [
                    ("A wounded messenger", "carrying vital information"),
                    ("A bounty hunter", "looking for someone matching your description"),
                    ("A traveling merchant", "with unusual wares and stranger stories"),
                    ("A religious zealot", "preaching doom and demanding repentance"),
                    ("An old enemy", "who claims to want peace... for now"),
                ],
                "cyberpunk": [
                    ("A street doc", "offering services with strings attached"),
                    ("A corpo defector", "with data they'll die to protect"),
                    ("A media reporter", "who knows too much about your business"),
                    ("A burned solo", "seeking revenge against a mutual enemy"),
                    ("A fixer's messenger", "with a job you can't refuse"),
                ],
                "scifi_military": [
                    ("A survivor from another unit", "with intel on enemy movements"),
                    ("A civilian caught in the crossfire", "who knows the terrain"),
                    ("An enemy defector", "offering to cooperate"),
                    ("A special operations officer", "taking command of the situation"),
                    ("A war correspondent", "who will record everything"),
                ],
                "historical": [
                    ("A royal messenger", "bearing sealed orders"),
                    ("A local guide", "who knows secrets of the land"),
                    ("A rival faction's envoy", "proposing an alliance"),
                    ("A priest or holy figure", "claiming divine guidance"),
                    ("A famous figure", "whose presence changes everything"),
                ],
                "weird_war": [
                    ("A shell-shocked soldier", "who's seen things in no-man's-land"),
                    ("An occult specialist", "assigned to your unit"),
                    ("A nurse with hollow eyes", "who speaks of walking dead"),
                    ("An enemy prisoner", "who begs for protection from 'them'"),
                    ("A chaplain", "who's lost faith but found something else"),
                ],
            }

            npcs = npc_arrivals_by_setting.get(
                self.config.setting, [("A stranger", "with unknown intentions")]
            )
            npc_name, npc_context = random.choice(npcs)

            event_parts.append("**NEW ARRIVAL**\n")
            event_parts.append(f"{npc_name} appears, {npc_context}.\n")

            self.gm.memory.track_entity(
                name=npc_name, entity_type="npc",
                description=npc_context, disposition=random.randint(-30, 30)
            )
            self.gm.memory.current_scene.setdefault("present_npcs", []).append(npc_name)

        elif event_type == "discovery":
            # Setting-specific discoveries
            discoveries_by_setting = {
                "fantasy": [
                    "an ancient rune that glows when you approach",
                    "a hidden cache of supplies and a cryptic map",
                    "evidence that someone has been following you",
                    "a portal shimmering at the edge of perception",
                    "remains that tell a disturbing story",
                ],
                "cyberpunk": [
                    "a dead drop with encrypted data meant for someone else",
                    "surveillance equipment monitoring your position",
                    "a backdoor into a major corporate network",
                    "a body with high-end chrome, stripped and dumped",
                    "graffiti that's actually a coded message",
                ],
                "scifi_military": [
                    "enemy communications you can intercept",
                    "a hidden weapons cache, origin unknown",
                    "evidence of experiments on prisoners",
                    "a downed ship's black box with vital data",
                    "abandoned fortifications that could be useful",
                ],
                "historical": [
                    "documents that could change the political landscape",
                    "a hidden passage known only to locals",
                    "evidence of betrayal at the highest levels",
                    "a cache of weapons from a previous conflict",
                    "remains that prove a historical lie",
                ],
                "weird_war": [
                    "symbols carved into the trench walls, bleeding",
                    "a journal describing impossible events",
                    "equipment that shouldn't exist yet",
                    "a mass grave where the bodies are wrong",
                    "a door that wasn't there before",
                ],
            }

            discoveries = discoveries_by_setting.get(
                self.config.setting, ["something unexpected"]
            )
            discovery = random.choice(discoveries)

            event_parts.append("**DISCOVERY**\n")
            event_parts.append(f"You notice {discovery}.\n")
            self.gm.memory.add_thread(
                f"Investigate: {discovery[:30]}", f"You discovered {discovery}", importance=4
            )

        event_parts.append("\n---")
        return "".join(event_parts)

    # =========================================================================
    # MESSAGE DISPLAY
    # =========================================================================

    def _add_message(self, sender: str, text: str, msg_type: str = "normal"):
        """Add a message to the chat log."""
        msg = ChatMessage(text=text, sender=sender, msg_type=msg_type)
        self.messages.append(msg)
        self._render_message(msg)

    def _render_message(self, msg: ChatMessage):
        """Render a message in the chat log."""
        if not dpg.does_item_exist("chat_log"):
            return

        with dpg.group(parent="chat_log"):
            # Time and sender
            time_str = msg.timestamp.strftime("%H:%M")

            if msg.sender == "user":
                color = COLORS["user"]
                label = "[You]"
            elif msg.sender == "gm":
                color = COLORS["gm"]
                label = "[GM]"
            else:
                color = COLORS["system"]
                label = "[System]"

            with dpg.group(horizontal=True):
                dpg.add_text(f"{time_str}", color=COLORS["muted"])
                dpg.add_text(label, color=color)

            # Message text with markdown-lite rendering
            self._render_text(msg.text, msg.msg_type)

            dpg.add_spacer(height=8)

    def _render_text(self, text: str, msg_type: str):
        """Render text with basic markdown support."""
        # Split into paragraphs
        paragraphs = text.split("\n\n")

        for para in paragraphs:
            if not para.strip():
                continue

            lines = para.split("\n")
            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # Check for bold **text**
                if "**" in line:
                    parts = re.split(r'\*\*(.+?)\*\*', line)
                    with dpg.group(horizontal=True):
                        for i, part in enumerate(parts):
                            if i % 2 == 1:  # Bold part
                                dpg.add_text(part, color=COLORS["header"])
                            elif part:
                                dpg.add_text(part, wrap=600)
                # Check for italic *text*
                elif line.startswith("*") and line.endswith("*") and len(line) > 2:
                    dpg.add_text(line[1:-1], color=COLORS["muted"], wrap=600)
                else:
                    dpg.add_text(line, wrap=600)

            dpg.add_spacer(height=4)

    # =========================================================================
    # SIDEBAR UPDATES
    # =========================================================================

    def _on_sidebar_chaos_change(self, sender, app_data, user_data):
        """Handle chaos slider change in sidebar."""
        self.config.chaos = app_data
        self.oracle.chaos = app_data
        self.gm.memory.chaos_factor = app_data
        dpg.set_value("sidebar_chaos_label", str(app_data))
        dpg.set_value("header_chaos", str(app_data))

    def _refresh_sidebar(self):
        """Refresh all sidebar sections."""
        if not self.gm:
            return

        # Update scene
        if dpg.does_item_exist("sidebar_scene"):
            dpg.delete_item("sidebar_scene", children_only=True)
            scene = self.gm.memory.current_scene
            with dpg.group(parent="sidebar_scene"):
                dpg.add_text(scene.get("location", "Unknown")[:30], color=COLORS["user"])
                dpg.add_text(f"Mood: {scene.get('mood', 'neutral').title()}", color=COLORS["muted"])
                dpg.add_text(f"Time: {scene.get('time_of_day', 'day').title()}", color=COLORS["muted"])

        # Update quest
        if dpg.does_item_exist("sidebar_quest"):
            dpg.delete_item("sidebar_quest", children_only=True)
            with dpg.group(parent="sidebar_quest"):
                if self.current_quest:
                    # Truncate objective for display
                    obj = self.current_quest.objective[:60]
                    if len(self.current_quest.objective) > 60:
                        obj += "..."
                    dpg.add_text(obj, wrap=250, color=COLORS["user"])
                else:
                    dpg.add_text("None active", color=COLORS["muted"])

        # Update NPCs
        if dpg.does_item_exist("sidebar_npcs"):
            dpg.delete_item("sidebar_npcs", children_only=True)
            with dpg.group(parent="sidebar_npcs"):
                npcs = self.gm.memory.get_active_npcs()
                if npcs:
                    for npc in npcs[:5]:
                        disp = npc.disposition
                        if disp > 30:
                            color = (100, 200, 100)
                            status = "(friendly)"
                        elif disp < -30:
                            color = (200, 100, 100)
                            status = "(hostile)"
                        else:
                            color = COLORS["muted"]
                            status = "(neutral)"
                        dpg.add_text(f"- {npc.name} {status}", color=color)
                else:
                    dpg.add_text("None", color=COLORS["muted"])

        # Update threads
        if dpg.does_item_exist("sidebar_threads"):
            dpg.delete_item("sidebar_threads", children_only=True)
            with dpg.group(parent="sidebar_threads"):
                threads = self.gm.memory.get_active_threads()
                if threads:
                    for thread in threads[:4]:
                        name = thread.name[:40]
                        if len(thread.name) > 40:
                            name += "..."
                        dpg.add_text(f"- {name}", color=COLORS["muted"])
                else:
                    dpg.add_text("None active", color=COLORS["muted"])

        # Update chaos displays
        dpg.set_value("sidebar_chaos_slider", self.gm.memory.chaos_factor)
        dpg.set_value("sidebar_chaos_label", str(self.gm.memory.chaos_factor))
        if dpg.does_item_exist("header_chaos"):
            dpg.set_value("header_chaos", str(self.gm.memory.chaos_factor))

    # =========================================================================
    # DIALOGS
    # =========================================================================

    def _show_oracle_dialog(self):
        """Show the oracle question dialog."""
        if dpg.does_item_exist("oracle_dialog"):
            dpg.delete_item("oracle_dialog")

        with dpg.window(
            label="Ask the Oracle",
            tag="oracle_dialog",
            modal=True,
            width=400,
            height=250,
            pos=[400, 200],
        ):
            dpg.add_text("Ask a yes/no question:", color=COLORS["subheader"])
            dpg.add_input_text(
                tag="oracle_question_input",
                hint="e.g., Is there a guard at the door?",
                width=-1,
                multiline=True,
                height=60,
            )

            dpg.add_spacer(height=10)
            dpg.add_text("Likelihood:", color=COLORS["subheader"])
            dpg.add_combo(
                tag="oracle_likelihood_input",
                items=["Impossible", "Unlikely", "50/50", "Likely", "Certain"],
                default_value="50/50",
                width=-1,
            )

            dpg.add_spacer(height=15)
            with dpg.group(horizontal=True):
                dpg.add_button(label="Ask", callback=self._execute_oracle_dialog, width=100)
                dpg.add_button(label="Cancel", callback=lambda: dpg.delete_item("oracle_dialog"), width=100)

    def _execute_oracle_dialog(self):
        """Execute oracle from dialog."""
        question = dpg.get_value("oracle_question_input")
        likelihood_str = dpg.get_value("oracle_likelihood_input")

        if not question or not question.strip():
            dpg.delete_item("oracle_dialog")
            return

        # Map likelihood
        likelihood_map = {
            "Impossible": Likelihood.IMPOSSIBLE,
            "Unlikely": Likelihood.UNLIKELY,
            "50/50": Likelihood.EVEN,
            "Likely": Likelihood.LIKELY,
            "Certain": Likelihood.CERTAIN,
        }
        likelihood = likelihood_map.get(likelihood_str, Likelihood.EVEN)

        dpg.delete_item("oracle_dialog")

        # Add user question
        self._add_message("user", f"*{question.strip()}?*")

        # Ask oracle
        result = self.oracle.ask(question, likelihood)

        # Format response
        response_parts = []
        response_parts.append(f"*Rolling... {result.roll} (Chaos: {result.chaos}, Likelihood: {result.likelihood.display})*")
        response_parts.append("")

        answer_text = result.answer.value
        response_parts.append(f"**{answer_text}**")

        # Interpretation - use enum name (yes_and, yes, etc.)
        interpretation = self.gm.responder.interpret_oracle(
            result.answer.name.lower(),
            question,
            self.gm.memory
        )
        response_parts.append("")
        response_parts.append(interpretation)

        if result.random_event:
            event_type = "positive" if "YES" in answer_text else "negative"
            event = self.gm.responder.random_event(event_type, self.gm.memory)
            response_parts.append("")
            response_parts.append(f"**Random Event!** {event}")
            self.oracle.chaos_up()
            self.gm.memory.chaos_factor = self.oracle.chaos

        self._add_message("gm", "\n".join(response_parts), "oracle")
        self._refresh_sidebar()

    def _show_dice_dialog(self):
        """Show the dice rolling dialog."""
        if dpg.does_item_exist("dice_dialog"):
            dpg.delete_item("dice_dialog")

        with dpg.window(
            label="Roll Dice",
            tag="dice_dialog",
            modal=True,
            width=350,
            height=200,
            pos=[400, 200],
        ):
            dpg.add_text("Enter dice notation:", color=COLORS["subheader"])
            dpg.add_input_text(
                tag="dice_input",
                hint="e.g., 2d6+3, 1d20, 4d6kh3",
                width=-1,
            )

            dpg.add_spacer(height=10)
            dpg.add_text("Quick rolls:", color=COLORS["muted"])
            with dpg.group(horizontal=True):
                for notation in ["1d20", "2d6", "1d100", "4d6kh3"]:
                    dpg.add_button(
                        label=notation,
                        callback=lambda s, a, u: self._quick_dice(u),
                        user_data=notation,
                        width=70,
                    )

            dpg.add_spacer(height=15)
            with dpg.group(horizontal=True):
                dpg.add_button(label="Roll", callback=self._execute_dice_dialog, width=100)
                dpg.add_button(label="Cancel", callback=lambda: dpg.delete_item("dice_dialog"), width=100)

    def _quick_dice(self, notation: str):
        """Quick roll from dialog."""
        dpg.delete_item("dice_dialog")
        self._handle_dice_command(f"/roll {notation}")

    def _execute_dice_dialog(self):
        """Execute dice roll from dialog."""
        notation = dpg.get_value("dice_input")
        dpg.delete_item("dice_dialog")

        if notation and notation.strip():
            self._handle_dice_command(f"/roll {notation.strip()}")

    def _show_menu(self):
        """Show the menu dialog."""
        if dpg.does_item_exist("menu_dialog"):
            dpg.delete_item("menu_dialog")

        with dpg.window(
            label="Menu",
            tag="menu_dialog",
            modal=True,
            width=300,
            height=250,
            pos=[450, 200],
        ):
            dpg.add_text("Session Options", color=COLORS["header"])
            dpg.add_separator()
            dpg.add_spacer(height=10)

            dpg.add_button(label="Generate New Quest", callback=self._generate_new_quest, width=-1, height=30)
            dpg.add_button(label="Generate Encounter", callback=self._generate_encounter, width=-1, height=30)
            dpg.add_button(label="Change Scene", callback=self._generate_scene_change, width=-1, height=30)
            dpg.add_button(label="Plot Twist", callback=self._generate_twist, width=-1, height=30)

            dpg.add_spacer(height=10)
            dpg.add_separator()
            dpg.add_spacer(height=10)

            dpg.add_button(label="Close", callback=lambda: dpg.delete_item("menu_dialog"), width=-1)

    def _generate_new_quest(self):
        """Generate and present a new quest."""
        dpg.delete_item("menu_dialog")

        quest = self.quest_gen.generate(complexity=random.randint(2, 4))
        self.current_quest = quest

        # Add as thread
        self.gm.memory.add_thread(quest.objective[:50], quest.objective, importance=7)

        response = f"**A new opportunity presents itself:**\n\n"
        response += f"{quest.quest_giver} seeks your aid: \"{quest.objective}\"\n\n"
        response += f"Location: *{quest.location}*\n"
        response += f"Reward: *{quest.reward}*\n"
        response += f"Stakes: *{quest.stakes}*\n\n"
        response += "**Will you accept?**"

        self._add_message("gm", response, "scene")
        self._refresh_sidebar()

    def _generate_encounter(self):
        """Generate and present an encounter."""
        dpg.delete_item("menu_dialog")

        encounter = self.encounter_gen.generate()

        response = f"**{encounter.type.upper()} ENCOUNTER:**\n\n"
        response += f"{encounter.description}\n\n"
        response += f"*Environment: {encounter.environment}*\n"

        if encounter.complications:
            response += f"*Complication: {encounter.complications[0]}*\n"

        response += "\n**What do you do?**"

        self._add_message("gm", response, "event")
        self._refresh_sidebar()

    def _generate_scene_change(self):
        """Generate a scene transition."""
        dpg.delete_item("menu_dialog")

        location = self.location_gen.generate()
        scene = self.scene_gen.transition_scene()

        self.current_location = location
        self.current_scene = scene

        # Update GM memory
        self.gm.memory.set_scene(
            location=location.name,
            description=location.description,
            mood=scene.mood.lower().split()[0] if scene.mood else "neutral",
            npcs=scene.npcs_present,
        )

        response = f"**Scene Transition**\n\n"
        response += f"You arrive at **{location.name}**, {location.description.lower()}\n\n"

        if scene.sensory_details:
            atmosphere = ". ".join(scene.sensory_details[:2])
            response += f"*{atmosphere}*\n\n"

        if scene.npcs_present:
            response += f"Present: {', '.join(scene.npcs_present)}\n\n"

        response += "**What do you do?**"

        self._add_message("gm", response, "scene")
        self._refresh_sidebar()

    def _generate_twist(self):
        """Generate a plot twist."""
        dpg.delete_item("menu_dialog")

        twist_type = random.choice(["betrayal", "revelation", "escalation"])
        twist = self.twist_gen.generate(twist_type)

        response = f"**Plot Twist!** ({twist_type.title()})\n\n"
        response += f"{twist}\n\n"
        response += "**How do you respond?**"

        self._add_message("gm", response, "event")

        # Increase chaos
        self.oracle.chaos_up()
        self.gm.memory.chaos_factor = self.oracle.chaos
        self._add_message("system", f"Chaos increased to {self.oracle.chaos}")

        self._refresh_sidebar()

    # =========================================================================
    # SESSION MANAGEMENT
    # =========================================================================

    def _save_session(self):
        """Save the current session."""
        from pathlib import Path
        import json

        save_dir = Path("oracle_saves")
        save_dir.mkdir(exist_ok=True)

        # Build save data
        save_data = {
            "config": {
                "game_type": self.config.game_type,
                "setting": self.config.setting,
                "mood": self.config.mood,
                "personality": self.config.personality,
                "chaos": self.config.chaos,
                "game_system": self.config.game_system,
                "doctrine": self.config.doctrine,
                "aggression": self.config.aggression,
            },
            "memory": self.gm.memory.to_dict() if self.gm else {},
            "messages": [
                {"text": m.text, "sender": m.sender, "type": m.msg_type}
                for m in self.messages
            ],
            "quest": {
                "objective": self.current_quest.objective if self.current_quest else None,
                "quest_giver": self.current_quest.quest_giver if self.current_quest else None,
            } if self.current_quest else None,
        }

        save_path = save_dir / "quicksave.json"
        with open(save_path, "w") as f:
            json.dump(save_data, f, indent=2)

        self._add_message("system", f"Session saved to {save_path}")

    def _load_session(self):
        """Load a saved session."""
        from pathlib import Path
        import json

        save_path = Path("oracle_saves/quicksave.json")
        if not save_path.exists():
            self._add_message("system", "No save file found.")
            return

        with open(save_path) as f:
            save_data = json.load(f)

        # Restore config
        config_data = save_data.get("config", {})
        self.config = SessionConfig(
            game_type=config_data.get("game_type", "rpg"),
            setting=config_data.get("setting", "fantasy"),
            mood=config_data.get("mood", "neutral"),
            personality=config_data.get("personality", "classic"),
            chaos=config_data.get("chaos", 5),
            game_system=config_data.get("game_system", "Generic"),
            doctrine=config_data.get("doctrine", "elite"),
            aggression=config_data.get("aggression", "balanced"),
        )

        # Re-initialize session
        self._initialize_session()

        # Restore memory
        if save_data.get("memory"):
            self.gm.memory = SessionMemory.from_dict(save_data["memory"])

        # Restore messages
        if dpg.does_item_exist("chat_log"):
            dpg.delete_item("chat_log", children_only=True)

        self.messages = []
        for msg_data in save_data.get("messages", []):
            self._add_message(
                msg_data["sender"],
                msg_data["text"],
                msg_data.get("type", "normal")
            )

        self._refresh_sidebar()
        self._add_message("system", "Session loaded.")

    def _show_history(self):
        """Show session history dialog."""
        if dpg.does_item_exist("history_dialog"):
            dpg.delete_item("history_dialog")

        with dpg.window(
            label="Session History",
            tag="history_dialog",
            width=500,
            height=400,
            pos=[350, 150],
        ):
            dpg.add_text("Recent Session Events", color=COLORS["header"])
            dpg.add_separator()

            with dpg.child_window(height=-40, border=False):
                history = self.gm.memory.get_recent_context(20) if self.gm else []
                if history:
                    for entry in history:
                        color = COLORS["muted"]
                        if entry.entry_type == "gm":
                            color = COLORS["gm"]
                        elif entry.entry_type == "user":
                            color = COLORS["user"]

                        content = entry.content[:100]
                        if len(entry.content) > 100:
                            content += "..."
                        dpg.add_text(f"[{entry.entry_type.upper()}] {content}", color=color, wrap=480)
                        dpg.add_spacer(height=3)
                else:
                    dpg.add_text("No history yet.", color=COLORS["muted"])

            dpg.add_button(label="Close", callback=lambda: dpg.delete_item("history_dialog"), width=-1)


# =============================================================================
# Entry Point
# =============================================================================

def main():
    """Main entry point."""
    app = OracleApp()
    app.run()


if __name__ == "__main__":
    main()
