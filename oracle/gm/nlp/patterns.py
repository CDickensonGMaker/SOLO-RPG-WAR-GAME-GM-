"""
Pattern-Based Intent Recognition - Zero Dependencies.

Uses regex patterns to recognize common game intents from natural language.
This is Layer 1 of the NLP system - always available, instant, no external deps.

Supported intents:
- ask_oracle: Yes/no questions ("Is the door locked?")
- talk_to: NPC interaction ("ask the merchant about...")
- persuade: Social influence ("convince the guard to help")
- intimidate: Threaten/frighten ("threaten the prisoner")
- deceive: Lie/bluff ("lie to the merchant")
- search: Looking for things ("search the room for clues")
- travel: Movement ("go to the tavern")
- flee: Escape/retreat ("run away")
- investigate: Examination ("examine the symbol")
- defend: Defensive actions ("take cover", "block")
- fight: Combat initiation ("attack the goblin")
- craft: Create items ("forge a sword")
- trade: Buy/sell ("buy supplies")
- use: Item usage ("use the key on the door")
- listen: Eavesdrop ("listen at the door")
- follow: Track/pursue ("follow the thief")
- observe: Stealth/perception ("watch the guards")
- pray: Spiritual ("pray to the gods")
- rest: Recovery ("make camp")
- interact: Object manipulation ("open the chest")
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from oracle.gm.memory import TrackedEntity, PlotThread


@dataclass
class Intent:
    """
    A parsed intent from user input.

    Attributes:
        action: The intent type (talk_to, search, travel, etc.)
        target: Primary target of the action (NPC name, location, item)
        topic: Secondary context (what to ask about, what to search for)
        raw_input: The original user input
        confidence: How confident the match is (0.0-1.0)
        extras: Additional extracted data (item, direction, etc.)
    """
    action: str
    target: Optional[str] = None
    topic: Optional[str] = None
    raw_input: str = ""
    confidence: float = 1.0
    extras: Dict[str, Any] = field(default_factory=dict)

    # Resolved entities (populated by EntityResolver)
    resolved_npc: Optional[TrackedEntity] = None
    resolved_location: Optional[str] = None
    resolved_thread: Optional[PlotThread] = None
    resolved_item: Optional[TrackedEntity] = None


class PatternMatcher:
    """
    Rule-based intent recognition using regex patterns.

    This is the primary intent parser - fast, reliable, no dependencies.
    Falls back gracefully when patterns don't match.

    Usage:
        matcher = PatternMatcher()
        intent = matcher.match("ask the guard about the missing artifact")
        if intent:
            print(f"Intent: {intent.action}, Target: {intent.target}")
    """

    # Common prefixes players use that don't affect intent (EXPANDED per Steps 1-2)
    PREFIX_PATTERNS: List[re.Pattern] = [
        # Existing patterns
        re.compile(r"^i(?:'m| am) going to\s+", re.IGNORECASE),
        re.compile(r"^i(?:'d| would) like to\s+", re.IGNORECASE),
        re.compile(r"^i want to\s+", re.IGNORECASE),
        re.compile(r"^i(?:'ll| will)\s+", re.IGNORECASE),
        re.compile(r"^i wish to\s+", re.IGNORECASE),
        re.compile(r"^i try to\s+", re.IGNORECASE),
        re.compile(r"^i attempt to\s+", re.IGNORECASE),
        re.compile(r"^let(?:'s| us| me)\s+", re.IGNORECASE),
        re.compile(r"^(?:can|could|may|might|shall|should) (?:i|we)\s+", re.IGNORECASE),

        # NEW - Polite/indirect prefixes (Step 1)
        re.compile(r"^(?:i\s+)?think\s+i(?:'ll|'d)\s+", re.IGNORECASE),
        re.compile(r"^(?:i\s+)?guess\s+i(?:'ll|'d)\s+", re.IGNORECASE),
        re.compile(r"^(?:i\s+)?suppose\s+i\s+should\s+", re.IGNORECASE),
        re.compile(r"^i'm\s+going\s+to\s+", re.IGNORECASE),
        re.compile(r"^i'll\s+(?:try\s+to|just)\s+", re.IGNORECASE),
        re.compile(r"^maybe\s+i\s+should\s+", re.IGNORECASE),
        re.compile(r"^time\s+to\s+", re.IGNORECASE),
        re.compile(r"^i\s+need\s+to\s+", re.IGNORECASE),
        re.compile(r"^i\s+have\s+to\s+", re.IGNORECASE),
        re.compile(r"^i\s+must\s+", re.IGNORECASE),
        re.compile(r"^i\s+decide\s+to\s+", re.IGNORECASE),
        re.compile(r"^i\s+choose\s+to\s+", re.IGNORECASE),
        re.compile(r"^gonna\s+", re.IGNORECASE),
        re.compile(r"^wanna\s+", re.IGNORECASE),
        re.compile(r"^lemme\s+", re.IGNORECASE),

        re.compile(r"^i\s+", re.IGNORECASE),  # Simple "I" at start (keep last)
    ]

    # Idiomatic phrases that map to intents (Step 2)
    IDIOM_MAPPINGS: Dict[str, Tuple[str, Optional[str]]] = {
        # Talk-to idioms
        "have a word with": ("talk_to", "target"),
        "speak with": ("talk_to", "target"),
        "chat with": ("talk_to", "target"),
        "inquire about": ("talk_to", "topic"),
        "question about": ("talk_to", "topic"),
        "strike up a conversation": ("talk_to", None),

        # Search idioms
        "look around": ("search", None),
        "take a look": ("search", None),
        "scope out": ("search", "target"),
        "check out": ("investigate", "target"),
        "have a look at": ("investigate", "target"),
        "poke around": ("search", None),
        "nose around": ("search", None),

        # Travel idioms
        "head over to": ("travel", "target"),
        "make my way to": ("travel", "target"),
        "set out for": ("travel", "target"),
        "leave for": ("travel", "target"),
        "get going to": ("travel", "target"),
        "make for": ("travel", "target"),

        # Oracle idioms
        "any signs of": ("ask_oracle", "topic"),
        "what about": ("investigate", "target"),
        "i wonder if": ("ask_oracle", "topic"),
        "is there any": ("ask_oracle", "topic"),

        # Observe idioms
        "keep an eye on": ("observe", "target"),
        "lie low": ("observe", None),
        "stay alert": ("observe", None),
        "keep watch": ("observe", None),

        # Fight idioms
        "take down": ("fight", "target"),
        "go after": ("fight", "target"),
        "take on": ("fight", "target"),

        # Rest idioms
        "catch my breath": ("rest", None),
        "take a breather": ("rest", None),
        "recover my strength": ("rest", None),
    }

    # Flexible name pattern - matches multi-word names like "Captain John Smith"
    NAME = r"[a-z]+(?:\s+[a-z]+)*"

    def __init__(self):
        self._compile_patterns()

    def _strip_prefixes(self, text: str) -> str:
        """
        Remove common player speech prefixes that don't affect intent.

        Examples:
            "I want to search the room" -> "search the room"
            "Can I examine the door?" -> "examine the door"
            "Let me ask the guard" -> "ask the guard"
        """
        for pattern in self.PREFIX_PATTERNS:
            text = pattern.sub("", text)
        return text.strip()

    def _compile_patterns(self):
        """Compile regex patterns for each intent type."""
        NAME = self.NAME  # Shorthand

        # Patterns are (intent_name, compiled_regex, capture_group_names)
        # Order matters - more specific patterns should come first
        self.patterns: List[Tuple[str, re.Pattern, List[str]]] = [

            # === ORACLE / QUESTIONS ===
            # Direct oracle invocation
            ("ask_oracle", re.compile(
                r"^(?:oracle|fate|ask the oracle)[,:]?\s*(.+?)(?:\?)?$",
                re.IGNORECASE
            ), ["topic"]),

            # === SOCIAL SKILLS (before talk_to) ===
            # Persuade/Convince
            ("persuade", re.compile(
                rf"(?:persuade|convince|negotiate|bargain|haggle|reason\s+with|"
                rf"appeal\s+to|plead\s+with)\s+(?:the\s+)?({NAME})",
                re.IGNORECASE
            ), ["target"]),

            # Intimidate
            ("intimidate", re.compile(
                rf"(?:intimidate|threaten|menace|frighten|scare|cow|bully|"
                rf"coerce|pressure)\s+(?:the\s+)?({NAME})",
                re.IGNORECASE
            ), ["target"]),

            # Charm/Seduce
            ("charm", re.compile(
                rf"(?:charm|seduce|flatter|beguile|sweet[\s-]?talk|flirt\s+with|"
                rf"ingratiate|woo)\s+(?:the\s+)?({NAME})",
                re.IGNORECASE
            ), ["target"]),

            # Deceive/Lie
            ("deceive", re.compile(
                rf"(?:deceive|lie\s+to|bluff|trick|mislead|con|fool|dupe)\s+"
                rf"(?:the\s+)?({NAME})",
                re.IGNORECASE
            ), ["target"]),

            # === QUERY STATE (player status queries - must come first) ===
            # "what curse/condition/effect is affecting me?"
            ("query_state", re.compile(
                r"what\s+(?:type\s+of\s+)?(?:curse|condition|affliction|effect|complication|"
                r"status|problem|issue)\s+(?:is|are)\s+(?:afflicting|affecting|on|hitting)\s+"
                r"(?:me|us|my\s+character)(?:\?)?$",
                re.IGNORECASE
            ), ["effect_type"]),

            # "what's happening/going on to me?"
            ("query_state", re.compile(
                r"what(?:'s|\s+is)\s+(?:happening|going\s+on|wrong)\s+"
                r"(?:to|with)\s+(?:me|us|my\s+character)(?:\?)?$",
                re.IGNORECASE
            ), []),

            # "what are my effects/conditions/curses?"
            ("query_state", re.compile(
                r"what\s+(?:are\s+)?(?:my|the)\s+(?:active\s+)?(?:effects|conditions|curses|"
                r"complications|afflictions|status\s+effects)(?:\?)?$",
                re.IGNORECASE
            ), []),

            # "am I cursed/poisoned/affected?"
            ("query_state", re.compile(
                r"am\s+I\s+(?:cursed|poisoned|affected|afflicted|wounded|injured|"
                r"under\s+any\s+effect)(?:\?)?$",
                re.IGNORECASE
            ), []),

            # "what effects are on me?" / "what's on me?"
            ("query_state", re.compile(
                r"what\s+(?:effects?|conditions?|curses?|afflictions?|status)\s+"
                r"(?:is|are)\s+(?:on|affecting)\s+(?:me|us)(?:\?)?$",
                re.IGNORECASE
            ), []),

            # === RECALL LORE (must come before talk_to to catch "tell me about X") ===
            # These patterns retrieve stable world info from WorldModel
            ("recall_lore", re.compile(
                r"(?:tell\s+me\s+about|what\s+is|what\s+are|what\'s|describe|explain|"
                r"what\s+do\s+(?:I|we)\s+know\s+about|learn\s+(?:more\s+)?about)\s+"
                r"(?:the\s+)?(.+?)(?:\?)?$",
                re.IGNORECASE
            ), ["target"]),

            # "where is X" / "where is X located" - location queries
            ("recall_lore", re.compile(
                r"where\s+is\s+(?:the\s+)?(.+?)(?:\s+located)?(?:\?)?$",
                re.IGNORECASE
            ), ["target"]),

            # "info on X" / "information about X"
            ("recall_lore", re.compile(
                r"(?:info(?:rmation)?\s+(?:on|about)|details\s+(?:on|about))\s+(?:the\s+)?(.+?)(?:\?)?$",
                re.IGNORECASE
            ), ["target"]),

            # === TALK / CONVERSATION ===
            # "ask [the] NPC about topic" - NOTE: "tell me about" now goes to recall_lore above
            ("talk_to", re.compile(
                rf"(?:ask|speak\s+to|talk\s+to|speak\s+with|talk\s+with)\s+"
                rf"(?:the\s+)?({NAME})\s+"
                rf"(?:about|regarding|concerning|if|whether)\s+(.+)",
                re.IGNORECASE
            ), ["target", "topic"]),

            # "tell [NPC] about [topic]" - distinct from "tell me about"
            ("talk_to", re.compile(
                rf"tell\s+(?:the\s+)?({NAME})\s+"
                rf"(?:about|regarding|concerning)\s+(.+)",
                re.IGNORECASE
            ), ["target", "topic"]),

            # "talk to [the] NPC" (no topic)
            ("talk_to", re.compile(
                rf"(?:talk|speak|converse)\s+(?:to|with)\s+(?:the\s+)?({NAME})",
                re.IGNORECASE
            ), ["target"]),

            # "ask [the] NPC" (starting conversation, no topic)
            ("talk_to", re.compile(
                rf"^ask\s+(?:the\s+)?({NAME})\s*$",
                re.IGNORECASE
            ), ["target"]),

            # "greet [the] NPC"
            ("talk_to", re.compile(
                rf"(?:greet|hail|approach|call\s+out\s+to)\s+(?:the\s+)?({NAME})",
                re.IGNORECASE
            ), ["target"]),

            # === SEARCH ===
            # "search [location] for [target]"
            ("search", re.compile(
                rf"(?:search|look|hunt|find|scour|rummage)\s+"
                rf"(?:the\s+)?({NAME})\s+"
                rf"(?:for|to find)\s+(.+)",
                re.IGNORECASE
            ), ["location", "target"]),

            # "search for [target]"
            ("search", re.compile(
                r"(?:search|look|hunt|find)\s+(?:for|around\s+for)\s+(.+)",
                re.IGNORECASE
            ), ["target"]),

            # "search [location]" (no "for X")
            ("search", re.compile(
                rf"^(?:search|scour|check|explore)\s+(?:the\s+)?({NAME})$",
                re.IGNORECASE
            ), ["target"]),

            # "search around" / "search nearby"
            ("search", re.compile(
                r"(?:search|look)\s+(?:around|nearby|here|everywhere)",
                re.IGNORECASE
            ), []),

            # "look in/through [target]"
            ("search", re.compile(
                r"(?:look|search)\s+(?:in|inside|around|through)\s+(?:the\s+)?(.+)",
                re.IGNORECASE
            ), ["target"]),

            # === FOLLOW / TRACK (before travel) ===
            ("follow", re.compile(
                rf"(?:follow|trail|track|tail|shadow|pursue|stalk)\s+"
                rf"(?:the\s+)?({NAME})",
                re.IGNORECASE
            ), ["target"]),

            # === FLEE / ESCAPE (before travel) ===
            ("flee", re.compile(
                r"(?:flee|escape|retreat|run\s+away|withdraw|fall\s+back|"
                r"disengage|get\s+away|bolt)",
                re.IGNORECASE
            ), []),

            # === TRAVEL / MOVEMENT ===
            # "go to [location]"
            ("travel", re.compile(
                r"(?:go|travel|head|walk|run|move|proceed|journey|venture)\s+"
                r"(?:to|toward|towards|into|inside)\s+(?:the\s+)?(.+)",
                re.IGNORECASE
            ), ["target"]),

            # "enter [location]"
            ("travel", re.compile(
                r"(?:enter|leave|exit|depart)\s+(?:the\s+)?(.+)",
                re.IGNORECASE
            ), ["target"]),

            # Directional movement
            ("travel", re.compile(
                r"(?:go|head|move|walk|run)\s+(north|south|east|west|up|down|left|right|forward|back)",
                re.IGNORECASE
            ), ["target"]),

            # === INVESTIGATE / EXAMINE ===
            # "examine [target]" - active investigation, uses oracle
            ("investigate", re.compile(
                r"(?:examine|investigate|inspect|study|analyze|scrutinize|check|look\s+at)\s+"
                r"(?:the\s+)?(.+)",
                re.IGNORECASE
            ), ["target"]),

            # "what about [target]" / "how about" - partial queries go to investigate
            ("investigate", re.compile(
                r"(?:what\s+about|how\s+about|more\s+about)\s+(?:the\s+)?(.+?)(?:\?)?$",
                re.IGNORECASE
            ), ["target"]),

            # === DEFENSIVE (before fight) ===
            ("defend", re.compile(
                r"(?:defend|block|parry|dodge|evade|duck|sidestep|shield|"
                r"protect\s+myself|take\s+cover|brace)",
                re.IGNORECASE
            ), []),

            # === COMBAT ===
            # "attack [target]"
            ("fight", re.compile(
                rf"(?:attack|fight|strike|hit|shoot|kill|slay|engage|assault|charge)\s+"
                rf"(?:the\s+)?({NAME})",
                re.IGNORECASE
            ), ["target"]),

            # "draw my weapon"
            ("fight", re.compile(
                r"(?:draw|ready|prepare|raise)\s+(?:my\s+)?(?:weapon|sword|gun|blade|staff)",
                re.IGNORECASE
            ), []),

            # === CRAFT ===
            ("craft", re.compile(
                r"(?:craft|create|make|build|construct|forge|brew|cook|"
                r"assemble|fabricate|repair|fix|mend)\s+"
                r"(?:a\s+|an\s+|the\s+|some\s+|my\s+)?(?!camp\b)(.+)",
                re.IGNORECASE
            ), ["target"]),

            # === TRADE ===
            # Buy
            ("trade", re.compile(
                r"(?:buy|purchase|acquire|procure|order)\s+"
                r"(?:a\s+|an\s+|the\s+|some\s+)?(.+?)(?:\s+from\s+.+)?$",
                re.IGNORECASE
            ), ["target"]),

            # Sell
            ("trade", re.compile(
                r"(?:sell|barter|offer|pawn|fence)\s+"
                r"(?:my\s+|the\s+|some\s+)?(.+?)(?:\s+to\s+.+)?$",
                re.IGNORECASE
            ), ["target"]),

            # === USE ITEM ===
            # "use [item] on [target]"
            ("use", re.compile(
                rf"(?:use|apply|activate|employ)\s+(?:the\s+)?({NAME})\s+"
                rf"(?:on|with|against)\s+(?:the\s+)?(.+)",
                re.IGNORECASE
            ), ["item", "target"]),

            # "use [item]"
            ("use", re.compile(
                r"(?:use|activate|employ|wield|equip)\s+(?:the\s+|my\s+)?(.+)",
                re.IGNORECASE
            ), ["item"]),

            # "cast [spell] on [target]"
            ("use", re.compile(
                rf"(?:cast|invoke|channel)\s+({NAME})\s+"
                rf"(?:on|at|against)\s+(?:the\s+)?(.+)",
                re.IGNORECASE
            ), ["item", "target"]),

            # === LISTEN ===
            ("listen", re.compile(
                r"(?:listen|eavesdrop|strain\s+to\s+hear)\s*"
                r"(?:to|at|for|through)?\s*(?:the\s+)?(.+)?",
                re.IGNORECASE
            ), ["target"]),

            # === OBSERVE / STEALTH ===
            # "watch [target]"
            ("observe", re.compile(
                rf"(?:watch|observe|spy\s+on|keep\s+an\s+eye\s+on|surveil|monitor)\s+"
                rf"(?:the\s+)?({NAME})",
                re.IGNORECASE
            ), ["target"]),

            # "hide" / "sneak"
            ("observe", re.compile(
                r"(?:hide|sneak|stealth|conceal\s+myself|stay\s+hidden|remain\s+unseen)",
                re.IGNORECASE
            ), []),

            # === PRAY / SPIRITUAL ===
            # Pray with target
            ("pray", re.compile(
                r"(?:pray|meditate|commune|worship|give\s+thanks|seek\s+guidance)\s+"
                r"(?:to|at|before)\s+(?:the\s+)?(.+)",
                re.IGNORECASE
            ), ["target"]),

            # Pray without target
            ("pray", re.compile(
                r"(?:pray|meditate|commune\s+with\s+nature|seek\s+inner\s+peace|"
                r"center\s+myself|focus\s+my\s+mind)",
                re.IGNORECASE
            ), []),

            # === REST / RECOVERY ===
            ("rest", re.compile(
                r"(?:rest|sleep|camp|make\s+camp|recover|heal|take\s+a\s+break|wait)",
                re.IGNORECASE
            ), []),

            # === INTERACT WITH OBJECTS ===
            # "open [target]"
            ("interact", re.compile(
                r"(?:open|close|lock|unlock|push|pull|move|lift|turn|flip|press|activate)\s+"
                r"(?:the\s+)?(.+)",
                re.IGNORECASE
            ), ["target"]),

            # "pick up [item]"
            ("interact", re.compile(
                r"(?:pick\s+up|grab|take|collect|gather|loot)\s+(?:the\s+)?(.+)",
                re.IGNORECASE
            ), ["target"]),

            # === LOOK / DESCRIBE (scene queries) ===
            ("describe", re.compile(
                r"(?:look\s+around|describe|where\s+am\s+i|what\s+do\s+i\s+see)",
                re.IGNORECASE
            ), []),

            # === ASSESS (Step 5) - Evaluate situations/threats ===
            ("assess", re.compile(
                r"(?:how\s+(?:dangerous|risky|safe|hostile|friendly|strong|powerful|"
                r"difficult|hard|easy)\s+(?:is|are|does))\s+(.+?)(?:\?)?$",
                re.IGNORECASE
            ), ["target"]),

            ("assess", re.compile(
                r"(?:assess|evaluate|gauge|size\s+up|appraise)\s+(?:the\s+)?(.+)",
                re.IGNORECASE
            ), ["target"]),

            ("assess", re.compile(
                r"(?:what\s+are\s+my\s+(?:chances|odds)|can\s+I\s+take)\s+(.+?)(?:\?)?$",
                re.IGNORECASE
            ), ["target"]),

            # === RECALL (Step 6) - Memory queries ===
            ("recall", re.compile(
                r"(?:what\s+do\s+(?:I|we)\s+know\s+about)\s+(.+?)(?:\?)?$",
                re.IGNORECASE
            ), ["topic"]),

            ("recall", re.compile(
                r"(?:remind\s+me\s+about|recap|summarize|review)\s+(.+)",
                re.IGNORECASE
            ), ["topic"]),

            ("recall", re.compile(
                r"(?:what\s+did\s+(?:I|we)\s+learn\s+about)\s+(.+?)(?:\?)?$",
                re.IGNORECASE
            ), ["topic"]),

            ("recall", re.compile(
                r"(?:tell\s+me\s+what\s+(?:I|we)\s+know)\s*(?:about\s+)?(.+)?",
                re.IGNORECASE
            ), ["topic"]),

            # === SENSE (Step 7) - Perception checks ===
            ("sense", re.compile(
                r"(?:what\s+do\s+I\s+(?:hear|see|smell|sense|feel|notice))",
                re.IGNORECASE
            ), []),

            ("sense", re.compile(
                r"(?:listen|peer|sniff|strain\s+my\s+(?:ears|eyes)|"
                r"look\s+more\s+closely|pay\s+attention)",
                re.IGNORECASE
            ), []),

            ("sense", re.compile(
                r"(?:do\s+I\s+(?:hear|see|smell|sense|notice)\s+anything)",
                re.IGNORECASE
            ), []),
        ]

        # Yes/no question starters for oracle detection
        self.yes_no_starters = {
            "is", "are", "do", "does", "did", "will", "would",
            "could", "can", "should", "has", "have", "was", "were",
            "am", "might", "may", "shall",
            # Contractions
            "isn't", "aren't", "don't", "doesn't", "didn't",
            "won't", "wouldn't", "couldn't", "can't", "shouldn't",
            "hasn't", "haven't", "wasn't", "weren't",
        }

    def match(self, user_input: str) -> Optional[Intent]:
        """
        Try to match input against patterns.

        Args:
            user_input: Raw user input string

        Returns:
            Intent if a pattern matches, None otherwise
        """
        user_input = user_input.strip()
        if not user_input:
            return None

        # Check for yes/no questions BEFORE stripping prefixes
        if self._is_yes_no_question(user_input):
            # Step 4: Check if it's really an action disguised as a question
            action_intent = self._classify_question(user_input)
            if action_intent:
                # Route to action handler instead of oracle
                intent = Intent(
                    action=action_intent,
                    raw_input=user_input,
                    confidence=0.85
                )
                # Try to extract target from the question
                cleaned = self._strip_prefixes(user_input.rstrip("?"))
                for _, pattern, groups in self.patterns:
                    match = pattern.search(cleaned)
                    if match:
                        for i, group_name in enumerate(groups):
                            if i < len(match.groups()) and match.group(i + 1):
                                value = match.group(i + 1).strip()
                                if group_name == "target":
                                    intent.target = value
                                elif group_name == "topic":
                                    intent.topic = value
                        break
                return intent

            # True yes/no question - oracle query
            return Intent(
                action="ask_oracle",
                topic=user_input.rstrip("?").strip(),
                raw_input=user_input,
                confidence=0.9
            )

        # Strip common player speech prefixes
        # "I want to search the room" -> "search the room"
        cleaned = self._strip_prefixes(user_input)

        # Try each pattern in order against cleaned input
        for intent_name, pattern, groups in self.patterns:
            match = pattern.search(cleaned)
            if match:
                intent = Intent(
                    action=intent_name,
                    raw_input=user_input,  # Keep original
                    confidence=0.85
                )

                # Extract named groups
                for i, group_name in enumerate(groups):
                    if i < len(match.groups()) and match.group(i + 1):
                        value = match.group(i + 1).strip()

                        # Map group to Intent field
                        if group_name == "target":
                            intent.target = value
                        elif group_name == "topic":
                            intent.topic = value
                        elif group_name == "location":
                            # Location goes to extras, target stays None
                            intent.extras["location"] = value
                        elif group_name == "item":
                            intent.extras["item"] = value
                        else:
                            intent.extras[group_name] = value

                return intent

        # No pattern matched
        return None

    def _is_yes_no_question(self, text: str) -> bool:
        """
        Check if input is a yes/no question (Step 3 - Enhanced).

        Returns True for questions like:
        - "Is the door locked?"
        - "Do they trust me?"
        - "Will the guards notice?"
        - "I wonder if it's safe?"
        - "Any sign of danger?"
        """
        text = text.strip()

        # Must end with question mark
        if not text.endswith("?"):
            return False

        text_lower = text.lower()

        # Get first word
        words = text_lower.split()
        if not words:
            return False

        first_word = words[0]

        # Check if it starts with a yes/no indicator
        if first_word in self.yes_no_starters:
            return True

        # NEW - Indirect question patterns (Step 3)
        indirect_patterns = [
            r"^(?:i\s+wonder\s+(?:if|whether))",
            r"^(?:any\s+(?:sign|chance|way|hope))",
            r"^(?:do\s+you\s+think)",
            r"^(?:is\s+there\s+any)",
            r"^(?:am\s+i\s+(?:able|safe|in\s+danger))",
        ]
        for pattern in indirect_patterns:
            if re.match(pattern, text_lower):
                return True

        return False

    def _classify_question(self, text: str) -> Optional[str]:
        """
        Classify a question as oracle query or action request (Step 4).

        Some questions like "Can I search the room?" are really action requests,
        not oracle queries. This method distinguishes them.

        Args:
            text: The question text

        Returns:
            Intent name if this is an action-disguised-as-question, None for true oracle
        """
        text_lower = text.lower()

        # Action-disguised-as-question patterns
        action_patterns = [
            (r"^can\s+i\s+(?:search|look|find)", "search"),
            (r"^can\s+i\s+(?:talk|speak|ask)\s+", "talk_to"),
            (r"^can\s+i\s+(?:go|head|travel)\s+", "travel"),
            (r"^should\s+i\s+(?:attack|fight)", "fight"),
            (r"^what\s+(?:do\s+i\s+see|can\s+i\s+see|is\s+here)", "search"),
            (r"^what\s+do\s+i\s+(?:hear|smell|sense)", "sense"),
            (r"^can\s+i\s+(?:hide|sneak)", "observe"),
            (r"^can\s+i\s+(?:rest|sleep|camp)", "rest"),
            (r"^can\s+i\s+(?:use|activate)", "use"),
        ]

        for pattern, intent in action_patterns:
            if re.match(pattern, text_lower):
                return intent

        return None  # True oracle question

    def match_idiom(self, user_input: str) -> Optional[Intent]:
        """
        Try to match input against idiomatic phrases (Step 2).

        Handles common phrasings like "have a word with", "take a look", etc.

        Args:
            user_input: Raw user input string

        Returns:
            Intent if an idiom matches, None otherwise
        """
        text_lower = user_input.lower().strip()

        for idiom, (intent_name, capture_type) in self.IDIOM_MAPPINGS.items():
            if idiom in text_lower:
                # Extract what comes after the idiom
                idx = text_lower.find(idiom)
                after = text_lower[idx + len(idiom):].strip()

                intent = Intent(
                    action=intent_name,
                    raw_input=user_input,
                    confidence=0.75  # Slightly lower than pattern match
                )

                # Set target or topic based on capture type
                if capture_type == "target" and after:
                    # Clean up common prefixes
                    after = re.sub(r"^(?:the|a|an)\s+", "", after)
                    intent.target = after.rstrip("?.!")
                elif capture_type == "topic" and after:
                    intent.topic = after.rstrip("?.!")

                return intent

        return None

    def get_supported_intents(self) -> List[str]:
        """Get list of all supported intent types."""
        return list(set(name for name, _, _ in self.patterns))


# Module-level cached matcher for quick_match
_default_matcher: Optional[PatternMatcher] = None


def quick_match(user_input: str) -> Optional[Intent]:
    """
    Convenience function for one-off matching.

    Uses a cached PatternMatcher to avoid recompiling patterns.
    For explicit control, create a PatternMatcher instance instead.
    """
    global _default_matcher
    if _default_matcher is None:
        _default_matcher = PatternMatcher()
    return _default_matcher.match(user_input)
