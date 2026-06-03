"""
GM Orchestrator - The Smart GM Brain.

This module orchestrates Oracle's systems based on parsed natural language intent.
It's the "intelligence layer" that:

1. Parses user input into structured intents
2. Resolves entity references against session memory
3. Routes to appropriate handlers (oracle, NPC interaction, scene, etc.)
4. Combines results from multiple systems into coherent narrative
5. Updates memory with new information

The orchestrator is domain-aware - it pulls content from the active game system's
TOML tables, never generic content. A Warhammer 40K session gets grimdark responses,
while D&D gets heroic fantasy.

Enhanced with Phase 2 improvements:
- Steps 5-7: New intents (ASSESS, RECALL, SENSE)
- Steps 8-10: Context tracking and pronoun resolution
- Steps 11-12: ContentRouter and VoiceGenerator integration
- Step 13: Graceful fallback pipeline

Usage:
    brain = GameMasterBrain()
    response = brain.orchestrator.process("ask the merchant about the artifact")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Any, Callable, Optional, TYPE_CHECKING
from pathlib import Path
import random

from oracle.gm.nlp.patterns import PatternMatcher, Intent
from oracle.gm.nlp.resolver import EntityResolver
from oracle.gm.nlp.context import ConversationTurn
from oracle.gm.nlp.content_router import ContentRouter
from oracle.gm.nlp.voice import VoiceGenerator
from oracle.gm.memory import SessionMemory, TrackedEntity, PlotThread
from oracle.gm.world_model import WorldModel

if TYPE_CHECKING:
    from oracle.gm.brain import GameMasterBrain


@dataclass
class OrchestrationResult:
    """
    Result from orchestrating an intent.

    Contains the narrative response plus metadata about what systems were used.
    """
    narrative: str
    oracle_used: bool = False
    oracle_result: str = ""
    oracle_answer: str = ""
    memory_updates: List[Dict[str, Any]] = field(default_factory=list)
    entities_referenced: List[str] = field(default_factory=list)
    intent_used: str = ""


class GMOrchestrator:
    """
    Orchestrates Oracle's systems based on parsed natural language intent.

    The orchestrator is the "smart" layer between raw user input and
    Oracle's existing systems (brain, responder, memory).

    Flow:
    1. PatternMatcher parses input → Intent
    2. EntityResolver links references → resolved entities
    3. Handler executes intent using brain methods
    4. Memory updated with new facts
    5. Narrative response returned

    Example:
        orchestrator = GMOrchestrator(brain)
        result = orchestrator.process("search the chapel for survivors")
        print(result)  # "YES, BUT... You find three guardsmen, but..."
    """

    def __init__(self, brain: "GameMasterBrain"):
        """
        Initialize the orchestrator.

        Args:
            brain: The GameMasterBrain instance to orchestrate
        """
        self.brain = brain
        self.matcher = PatternMatcher()
        self.resolver = EntityResolver(brain.memory)

        # Content router for domain-aware TOML content (Step 11)
        # Try to find the data directory
        data_root = self._find_data_root()
        self.content_router = ContentRouter(data_root) if data_root else None

        # World model for persistent entity management
        # Use the brain's world_model, or create one if needed
        self.world_model = brain.world_model
        # Wire content router to world model if available
        if self.content_router and self.world_model:
            self.world_model.content = self.content_router

        # Voice generator for NPC dialogue (Step 12)
        self.voice_generator = VoiceGenerator()

        # Intent handlers map intent names to handler methods
        self.handlers: Dict[str, Callable[[Intent], OrchestrationResult]] = {
            # Conversation & Social
            "talk_to": self._handle_talk,
            "persuade": self._handle_social,
            "intimidate": self._handle_social,
            "charm": self._handle_social,
            "deceive": self._handle_social,
            # Exploration
            "search": self._handle_search,
            "investigate": self._handle_investigate,
            "listen": self._handle_observe,  # Similar to observe
            "follow": self._handle_follow,
            # Movement
            "travel": self._handle_travel,
            "flee": self._handle_flee,
            # Combat
            "defend": self._handle_defend,
            "fight": self._handle_fight,
            # Items & Actions
            "craft": self._handle_craft,
            "trade": self._handle_trade,
            "use": self._handle_use,
            "interact": self._handle_interact,
            # Stealth & Perception
            "observe": self._handle_observe,
            # Recovery & Spiritual
            "pray": self._handle_pray,
            "rest": self._handle_rest,
            # Meta
            "ask_oracle": self._handle_oracle,
            "describe": self._handle_describe,
            # NEW - Phase 2 intents (Steps 5-7)
            "assess": self._handle_assess,
            "recall": self._handle_recall,
            "sense": self._handle_sense,
            # World Model intents
            "recall_lore": self._handle_recall_lore,
            # Player state queries
            "query_state": self._handle_query_state,
        }

    def _find_data_root(self) -> Optional[Path]:
        """Find the oracle data directory."""
        # Try relative to this file
        here = Path(__file__).parent
        candidates = [
            here.parent / "data",  # oracle/gm/../data = oracle/data
            here.parent.parent / "data",  # one more level up
            Path.cwd() / "oracle" / "data",
        ]
        for path in candidates:
            if path.exists() and (path / "core").exists():
                return path
        return None

    def process(self, user_input: str) -> str:
        """
        Process natural language input and return narrative response.

        This is the main entry point for the smart GM.
        Enhanced with multi-layer fallback (Step 13).

        Args:
            user_input: Raw user input string

        Returns:
            Narrative response string
        """
        # Step 1: Try pattern matching
        intent = self.matcher.match(user_input)

        # Step 2: Try idiom matching if patterns fail (Step 13)
        if intent is None:
            intent = self.matcher.match_idiom(user_input)

        # Step 3: Try fuzzy keyword extraction (Step 13)
        if intent is None:
            intent = self._fuzzy_intent_guess(user_input)

        # Step 4: Fall back to descriptive/generic handler (Step 13)
        if intent is None:
            if self._is_descriptive_action(user_input):
                return self._handle_descriptive(user_input)
            return self._handle_freeform(user_input)

        # Step 5: Resolve pronouns and entities (Steps 9-10)
        self._resolve_entities_enhanced(intent)

        # Step 6: Execute appropriate handler
        handler = self.handlers.get(intent.action, self._handle_generic)
        result = handler(intent)

        # Step 7: Record to conversation context (Step 8)
        self._record_to_context(user_input, intent, result)

        # Step 8: Update memory (avoid double recording)
        if not result.oracle_used:
            self.brain.memory.add_message(user_input, "user")
            if result.narrative:
                self.brain.memory.add_gm_response(result.narrative, {
                    "intent": result.intent_used,
                })

        return result.narrative

    def _resolve_entities_enhanced(self, intent: Intent):
        """
        Enhanced entity resolution with pronoun handling (Steps 9-10).

        Resolves pronouns before standard entity resolution.
        """
        # Handle pronouns in target
        if intent.target:
            target_lower = intent.target.lower().strip()

            # Check for pronouns
            if self.resolver.is_pronoun(target_lower):
                resolved = self.resolver.resolve_pronoun(target_lower)
                if resolved:
                    intent.target = resolved

        # Handle implicit topic references
        if intent.topic:
            topic_lower = intent.topic.lower().strip()
            if topic_lower in ["it", "that", "this", "them"]:
                resolved_topic = self.resolver.resolve_implicit_topic(topic_lower)
                if resolved_topic:
                    intent.topic = resolved_topic

        # Handle missing target using context
        if not intent.target and intent.action in ["talk_to", "investigate", "fight", "follow"]:
            if intent.action == "talk_to":
                intent.target = self.resolver.context.last_mentioned_npc
            else:
                intent.target = self.resolver.context.get_last_target()

        # Standard resolution
        self.resolver.resolve_intent(intent)

    def _record_to_context(self, user_input: str, intent: Intent,
                            result: OrchestrationResult):
        """Record the turn to conversation context (Step 8)."""
        resolved_entities = {}

        if intent.resolved_npc:
            resolved_entities["npc"] = intent.resolved_npc.name
        if intent.resolved_location:
            resolved_entities["location"] = intent.resolved_location
        if intent.resolved_item:
            resolved_entities["item"] = intent.resolved_item.name
        if intent.resolved_thread:
            resolved_entities["thread"] = intent.resolved_thread.name

        turn = ConversationTurn(
            user_input=user_input,
            intent_action=intent.action,
            target=intent.target,
            topic=intent.topic,
            resolved_entities=resolved_entities,
            gm_response=result.narrative[:200] if result.narrative else None,
            oracle_used=result.oracle_used,
            oracle_result=result.oracle_result if result.oracle_used else None,
        )

        self.resolver.context.record_turn(turn)

    def _fuzzy_intent_guess(self, user_input: str) -> Optional[Intent]:
        """
        Last-resort intent extraction via keyword spotting (Step 13).

        Args:
            user_input: The unmatched user input

        Returns:
            Intent with low confidence, or None
        """
        text_lower = user_input.lower()

        KEYWORD_INTENTS = {
            "fight": ["fight", "attack", "kill", "strike", "combat", "battle", "shoot"],
            "talk_to": ["talk", "speak", "ask", "conversation", "chat", "tell", "say"],
            "search": ["search", "look", "find", "hunt", "seek", "check"],
            "travel": ["go", "travel", "head", "move", "walk", "run", "enter", "leave"],
            "rest": ["rest", "sleep", "camp", "wait", "recover"],
            "observe": ["watch", "observe", "hide", "spy", "sneak", "stealth"],
            "investigate": ["examine", "inspect", "study", "investigate", "analyze"],
            "use": ["use", "activate", "equip", "wield", "cast"],
        }

        for intent_name, keywords in KEYWORD_INTENTS.items():
            for keyword in keywords:
                if keyword in text_lower:
                    return Intent(
                        action=intent_name,
                        raw_input=user_input,
                        confidence=0.5  # Low confidence
                    )

        return None

    def _is_descriptive_action(self, user_input: str) -> bool:
        """Check if input describes a player action (Step 13)."""
        text_lower = user_input.lower().strip()

        # Starts with "I" + verb
        if text_lower.startswith("i "):
            words = text_lower.split()
            if len(words) > 1:
                # Check for action verbs
                action_verbs = [
                    "do", "make", "take", "put", "get", "give", "try",
                    "start", "begin", "continue", "stop", "wait",
                ]
                return words[1] in action_verbs

        # Starts with a verb (imperative)
        first_word = text_lower.split()[0] if text_lower.split() else ""
        imperative_starters = ["do", "make", "take", "put", "get", "start", "continue"]
        return first_word in imperative_starters

    def _handle_descriptive(self, user_input: str) -> str:
        """Handle descriptive player actions with scene context (Step 13)."""
        # Clean up the input
        text = user_input.lower().strip()
        if text.startswith("i "):
            action = text[2:].rstrip(".")
        else:
            action = text.rstrip(".")

        location = self.brain.memory.current_scene.get("location", "here")
        mood = self.brain.memory.current_scene.get("mood", "neutral")

        # Build contextual acknowledgment
        base = f"You {action}."

        # Add scene-aware follow-up
        if mood == "dangerous":
            follow_ups = [
                "The tension in the air remains palpable.",
                "You remain alert for any sign of danger.",
                "The sense of threat does not diminish.",
            ]
        elif mood == "mysterious":
            follow_ups = [
                "Questions linger in your mind.",
                f"The mysteries of {location} persist.",
                "Something here defies easy explanation.",
            ]
        elif mood == "calm":
            follow_ups = [
                "A moment of relative peace.",
                f"{location.title()} seems quiet for now.",
                "All seems well, for the moment.",
            ]
        else:
            follow_ups = [
                "What happens next remains to be seen.",
                "The situation continues to develop.",
                "Events are in motion.",
            ]

        return f"{base}\n\n{random.choice(follow_ups)}"

    def _handle_freeform(self, user_input: str) -> str:
        """
        Handle unrecognized input by searching game state for relevant context.
        Last resort before giving up.
        """
        input_lower = user_input.lower()

        # Search for entity mentions
        for entity in self.brain.memory.entities.values():
            if entity.name.lower() in input_lower:
                # Found a relevant entity - return info about it
                return self._format_known_entity(entity).narrative

        # Search thread names/descriptions
        for thread in self.brain.memory.threads.values():
            if any(word in thread.name.lower() or word in thread.description.lower()
                   for word in input_lower.split() if len(word) > 3):
                return f"**{thread.name}:** {thread.description}"

        # Check if asking about current location
        location = self.brain.memory.current_scene.get("location", "")
        if location and location.lower() in input_lower:
            entity = self.world_model.get_or_create_entity(location, "location")
            return self._format_known_entity(entity).narrative

        # Gather full context for guidance response
        context = self._gather_full_context(user_input)
        context_text = self._format_context_narrative(context, focus="all")

        # If we have context, include it; otherwise provide guidance
        if context_text:
            return (
                f"I understand you're asking about something in the world.\n\n"
                f"**Current Context:**\n{context_text}\n\n"
                f"Try asking more specifically:\n"
                f"- 'Tell me about [thing]' for world info\n"
                f"- 'What effects are on me?' for player status\n"
                f"- 'Look around' to describe the scene"
            )
        else:
            return (
                f"I understand you're asking about something in the world. "
                f"Try asking more specifically:\n"
                f"- 'Tell me about [thing]' for world info\n"
                f"- 'What effects are on me?' for player status\n"
                f"- 'Look around' to describe the scene"
            )

    def _fallback(self, user_input: str) -> str:
        """Fall back to brain's existing process_input method."""
        return self.brain.process_input(user_input)

    # =========================================================================
    # Intent Handlers
    # =========================================================================

    def _handle_talk(self, intent: Intent) -> OrchestrationResult:
        """
        Handle talking to an NPC.

        Resolves NPC reference, checks knowledge via oracle if topic given,
        generates appropriate dialogue based on disposition.
        Enhanced with VoiceGenerator for distinctive NPC speech (Step 12).
        Writes revealed topics to NPC entity for persistence.
        """
        npc = intent.resolved_npc

        if npc is None:
            # NPC not found - try to create via WorldModel
            target = intent.target or "someone"
            npc = self.world_model.get_or_create_entity(target, "npc")
            npc.discovered = True

        # Mark NPC as discovered
        if not npc.discovered:
            npc.discovered = True
            npc.revealed_attributes.add("description")

        # Build response based on topic
        if intent.topic:
            # Oracle check: Does NPC know about this topic?
            likelihood = self._disposition_to_likelihood(npc.disposition)

            oracle_result = self.brain.ask_oracle(
                f"Does {npc.name} know about {intent.topic}",
                likelihood=likelihood
            )

            # Generate dialogue content based on oracle result
            if oracle_result.answer in ["yes_and", "yes"]:
                # NPC knows and shares - track this topic
                content = self._get_informative_content(npc, intent.topic)
                if oracle_result.answer == "yes_and":
                    bonus = self._generate_bonus_info(intent.topic)
                    content += f" {bonus}"
                # Record that NPC has shared info about this topic
                npc.revealed_attributes.add(f"topic_{intent.topic.lower().replace(' ', '_')}")
                if "discussed_topics" not in npc.attributes:
                    npc.attributes["discussed_topics"] = []
                npc.attributes["discussed_topics"].append(intent.topic)
            elif oracle_result.answer == "yes_but":
                # Knows but there's a catch
                content = self._get_partial_content(npc, intent.topic)
            elif oracle_result.answer == "no_but":
                # Doesn't know but offers something else
                content = self._get_redirect_content(npc, intent.topic)
            else:
                # Doesn't know
                content = self._get_unhelpful_content(npc, intent.topic)

            # Use VoiceGenerator to frame dialogue with NPC personality (Step 12)
            dialogue = self.voice_generator.generate_frame(
                npc.name,
                npc.traits,
                content
            )

            # Add NPC greeting based on disposition
            greeting = self.voice_generator.generate_greeting(
                npc.name, npc.traits, npc.disposition
            )

            return OrchestrationResult(
                narrative=f"**{oracle_result.answer_text}**\n\n{greeting}\n\n{dialogue}",
                oracle_used=True,
                oracle_result=oracle_result.interpretation,
                oracle_answer=oracle_result.answer,
                entities_referenced=[npc.name],
                intent_used="talk_to"
            )

        # No topic - just a greeting with voice
        greeting = self.voice_generator.generate_greeting(
            npc.name, npc.traits, npc.disposition
        )
        generic_content = self._get_generic_greeting_content(npc)
        dialogue = self.voice_generator.generate_frame(
            npc.name, npc.traits, generic_content
        )

        # Add NPC context
        context_parts = [f"{greeting}\n\n{dialogue}"]

        # Include NPC knowledge topics if known
        if npc.attributes.get("knowledge_topics"):
            topics = npc.attributes["knowledge_topics"]
            context_parts.append(f"\n*{npc.name} seems knowledgeable about: {', '.join(topics[:3])}*")

        # Include disposition hint
        if npc.disposition > 30:
            context_parts.append(f"\n*{npc.name} regards you warmly.*")
        elif npc.disposition < -30:
            context_parts.append(f"\n*{npc.name} regards you with suspicion.*")

        return OrchestrationResult(
            narrative="".join(context_parts),
            entities_referenced=[npc.name],
            intent_used="talk_to"
        )

    def _get_informative_content(self, npc: TrackedEntity, topic: str) -> str:
        """Get dialogue content for NPC sharing information."""
        # Get current location for context
        location = self.brain.memory.current_scene.get("location", "here")

        # Build contextual response based on NPC traits and disposition
        informative_templates = [
            f"Yes, I know about {topic}. Listen carefully...",
            f"Ah, {topic}. I've been waiting for someone to ask about that.",
            f"{topic}? I can tell you what I know, but keep it quiet.",
            f"You want to know about {topic}? Very well. Here's what I've heard.",
            f"I've seen things related to {topic}. Let me tell you.",
        ]

        base = random.choice(informative_templates)

        # Add context based on location or NPC background
        if npc.disposition > 30:
            base += f" Since we're on good terms, I'll tell you everything."
        elif npc.disposition < -30:
            base += f" But this information doesn't come free."

        return base

    def _get_partial_content(self, npc: TrackedEntity, topic: str) -> str:
        """Get dialogue content for NPC with partial knowledge."""
        partial_templates = [
            f"I've heard rumors about {topic}, but I don't know the full story.",
            f"{topic}? I only know pieces. Someone else might know more.",
            f"There's talk about {topic}, but I can only tell you so much.",
            f"I know a bit about {topic}... but there are gaps in what I've heard.",
            f"What I know about {topic} is incomplete, but here's what I can share.",
        ]

        base = random.choice(partial_templates)

        # Pull a complication from TOML to add intrigue
        if self.content_router:
            complication = self.content_router.pull_complication("neutral")
            base += f" Word is, {complication.lower()}"

        return base

    def _get_redirect_content(self, npc: TrackedEntity, topic: str) -> str:
        """Get dialogue content when NPC redirects to something else."""
        # Get other NPCs in scene for redirect
        present_npcs = self.brain.memory.current_scene.get("present_npcs", [])
        other_npcs = [n for n in present_npcs if n != npc.name]

        if other_npcs:
            redirect_target = random.choice(other_npcs)
            return f"I don't know much about {topic}. But {redirect_target} might. Ask them."
        else:
            redirect_templates = [
                f"I can't help you with {topic}. But I've heard things about other matters...",
                f"{topic} isn't my area. However, there's something else you should know.",
                f"That's not something I know about. But since you're here, let me tell you about something else.",
                f"Can't help with {topic}. But there's been strange happenings around here lately.",
            ]
            return random.choice(redirect_templates)

    def _get_unhelpful_content(self, npc: TrackedEntity, topic: str) -> str:
        """Get dialogue content when NPC can't help."""
        if npc.disposition < -30:
            hostile_templates = [
                f"Even if I knew about {topic}, why would I tell you?",
                f"{topic}? Never heard of it. Now leave me be.",
                f"I don't talk about {topic}. Especially not to strangers.",
                f"You're asking the wrong person. And the wrong questions.",
            ]
            return random.choice(hostile_templates)
        else:
            neutral_templates = [
                f"I wish I could help, but {topic} is a mystery to me too.",
                f"Sorry, I don't know anything about {topic}. Truly.",
                f"{topic}? That's beyond what I know. I'm just trying to get by here.",
                f"I've never heard anything about {topic}. You might try elsewhere.",
            ]
            return random.choice(neutral_templates)

    def _get_generic_greeting_content(self, npc: TrackedEntity) -> str:
        """Get generic greeting content based on disposition and traits."""
        location = self.brain.memory.current_scene.get("location", "here")

        if npc.disposition > 30:
            friendly_greetings = [
                "Good to see you again. What brings you by?",
                "Ah, a friendly face! How can I help you today?",
                f"Welcome back. Things have been quiet around {location}.",
                "I was hoping you'd stop by. What's on your mind?",
            ]
            return random.choice(friendly_greetings)
        elif npc.disposition < -30:
            hostile_greetings = [
                "What do you want? Make it quick.",
                "You again. This better be important.",
                "I don't have time for this. Speak your piece.",
                "State your business and be gone.",
            ]
            return random.choice(hostile_greetings)
        else:
            neutral_greetings = [
                "What brings you here?",
                "Can I help you with something?",
                f"You're not from around {location}, are you? What do you need?",
                "Looking for something? Or someone?",
            ]
            return random.choice(neutral_greetings)

    def _handle_search(self, intent: Intent) -> OrchestrationResult:
        """
        Handle searching for something.

        Uses oracle to determine success, then generates appropriate
        discovery or failure narrative.
        Writes discoveries to location entity for persistence.
        """
        target = intent.target or "something"
        location = intent.extras.get("location") or \
                   self.brain.memory.current_scene.get("location", "here")

        # Get or create location entity for tracking discoveries
        location_entity = self.world_model.get_or_create_entity(location, "location")

        # Oracle check for search success
        oracle_result = self.brain.ask_oracle(
            f"Do I find {target}",
            likelihood="even"
        )

        # Generate narrative and track discoveries
        discovery_text = None

        if oracle_result.answer == "yes_and":
            discovery = self._generate_discovery(target, "exceptional")
            bonus = self._generate_bonus_discovery()
            narrative = f"**{oracle_result.answer_text}**\n\n{discovery}\n\n{bonus}"
            discovery_text = f"Found {target} (exceptional): {discovery}"

        elif oracle_result.answer == "yes":
            discovery = self._generate_discovery(target, "success")
            narrative = f"**{oracle_result.answer_text}**\n\n{discovery}"
            discovery_text = f"Found {target}: {discovery}"

        elif oracle_result.answer == "yes_but":
            discovery = self._generate_discovery(target, "partial")
            complication = self._generate_complication()
            narrative = f"**{oracle_result.answer_text}**\n\n{discovery}\n\nHowever, {complication}"
            discovery_text = f"Partial find - {target}: {discovery} (complication: {complication})"

        elif oracle_result.answer == "no_but":
            failure = f"Your search for {target} comes up empty."
            silver_lining = self._generate_silver_lining()
            narrative = f"**{oracle_result.answer_text}**\n\n{failure}\n\nHowever, {silver_lining}"
            # Record the silver lining as a minor discovery
            discovery_text = f"Searched for {target}, found instead: {silver_lining}"

        elif oracle_result.answer == "no":
            narrative = f"**{oracle_result.answer_text}**\n\n" \
                       f"Despite your efforts, you find no trace of {target}."

        else:  # no_and
            failure = f"Not only do you fail to find {target}..."
            escalation = self._generate_escalation()
            narrative = f"**{oracle_result.answer_text}**\n\n{failure}\n\n{escalation}"

        # Write discovery to location entity
        if discovery_text:
            self.world_model.add_discovery(location, discovery_text)

        # Add location context to response
        context = self._gather_full_context()
        if context.get("location"):
            loc = context["location"]
            context_parts = []
            if loc.get("features"):
                context_parts.append(f"*Notable features: {'; '.join(loc['features'][:2])}*")
            if loc.get("hazards"):
                context_parts.append(f"*Hazards: {'; '.join(loc['hazards'][:2])}*")
            if context_parts:
                narrative += "\n\n" + "\n".join(context_parts)

        # Include previous discoveries at this location
        if location_entity.attributes.get("discoveries"):
            prev_discoveries = location_entity.attributes["discoveries"]
            if len(prev_discoveries) > 1:  # More than just current discovery
                narrative += f"\n\n*You've made {len(prev_discoveries)} discoveries here.*"

        return OrchestrationResult(
            narrative=narrative,
            oracle_used=True,
            oracle_result=oracle_result.interpretation,
            oracle_answer=oracle_result.answer,
            intent_used="search"
        )

    def _handle_oracle(self, intent: Intent) -> OrchestrationResult:
        """Handle direct oracle questions."""
        question = intent.topic or intent.raw_input.rstrip("?")
        result = self.brain.ask_oracle(question)

        return OrchestrationResult(
            narrative=f"**{result.answer_text}**\n\n{result.interpretation}",
            oracle_used=True,
            oracle_result=result.interpretation,
            oracle_answer=result.answer,
            intent_used="ask_oracle"
        )

    def _handle_travel(self, intent: Intent) -> OrchestrationResult:
        """
        Handle traveling to a location.

        Creates location entity via WorldModel.
        May trigger random events during travel.
        """
        destination = intent.target or intent.resolved_location or "somewhere"

        # Get or create destination entity via WorldModel
        location_entity = self.world_model.get_or_create_entity(destination, "location")

        # Check for random event during travel (1 in 6 chance)
        event_roll = random.randint(1, 6)

        if event_roll == 1:
            # Random encounter during travel - don't arrive yet
            event = self.brain.responder.random_event("neutral", self.brain.memory)
            narrative = f"As you travel toward {destination}...\n\n{event}\n\n" \
                       f"You have not yet reached your destination."
        else:
            # Successful travel - use brain.set_scene which also uses WorldModel
            response = self.brain.set_scene(destination, mood="neutral")
            narrative = response

        return OrchestrationResult(
            narrative=narrative,
            entities_referenced=[location_entity.name],
            intent_used="travel"
        )

    def _handle_investigate(self, intent: Intent) -> OrchestrationResult:
        """
        Handle investigating/examining something.

        Uses oracle to determine what is discovered.
        """
        target = intent.target or "the area"

        # Oracle check for discovery
        result = self.brain.ask_oracle(
            f"Do I discover something important about {target}",
            likelihood="even"
        )

        if result.answer.startswith("yes"):
            detail = self._generate_investigation_detail(target)
            narrative = f"**{result.answer_text}**\n\n" \
                       f"Your examination of {target} reveals: {detail}"
        else:
            narrative = f"**{result.answer_text}**\n\n" \
                       f"Your investigation of {target} doesn't yield new information."

        # Add related context
        context = self._gather_full_context(target)

        # Check if target is a known entity
        for entity in context.get("related", []):
            if entity.get("attributes"):
                attrs = entity["attributes"]
                attr_hints = []
                if attrs.get("features"):
                    attr_hints.append(f"*Features: {'; '.join(attrs['features'][:2])}*")
                if attrs.get("hazards"):
                    attr_hints.append(f"*Hazards: {'; '.join(attrs['hazards'][:2])}*")
                if attr_hints:
                    narrative += "\n\n" + "\n".join(attr_hints)
                break

        # Add active thread connections
        if context.get("threads"):
            for thread in context["threads"][:2]:
                if target.lower() in thread["name"].lower() or target.lower() in thread["description"].lower():
                    narrative += f"\n\n*This relates to: {thread['name']}*"
                    break

        return OrchestrationResult(
            narrative=narrative,
            oracle_used=True,
            oracle_result=result.interpretation,
            oracle_answer=result.answer,
            intent_used="investigate"
        )

    def _handle_fight(self, intent: Intent) -> OrchestrationResult:
        """
        Handle combat initiation.

        In wargame mode, hands off to tactical AI.
        In RPG mode, uses oracle for initiative.
        Writes combat results to NPC entity status.
        """
        target = intent.target or "your enemy"

        # Check if we're in wargame mode
        if self.brain.memory.mode == "wargame":
            return OrchestrationResult(
                narrative=f"**Combat initiated against {target}!**\n\n"
                         f"The tactical AI will now process the engagement.",
                intent_used="fight"
            )

        # Get or create the NPC entity for tracking
        npc = self.world_model.get_or_create_entity(target, "npc")

        # RPG combat - oracle for initiative
        result = self.brain.ask_oracle("Do I strike first", likelihood="even")

        if result.answer.startswith("yes"):
            narrative = f"**Combat!**\n\n" \
                       f"You act swiftly against {target}! You have the initiative."
            # Player advantage - potential wound to enemy
            if result.answer == "yes_and":
                npc.status = "wounded"
                npc.notes.append("Wounded in combat - player had decisive advantage")
                narrative += f"\n\nYour strike lands true! {target.title()} is wounded."
        else:
            narrative = f"**Combat!**\n\n" \
                       f"{target.title()} reacts before you can strike! They have initiative."
            if result.answer == "no_and":
                # Enemy has significant advantage
                npc.attributes["combat_advantage"] = True
                narrative += "\n\nYou're at a severe disadvantage!"

        # Mark NPC as hostile
        if npc.disposition > -30:
            npc.disposition = max(npc.disposition - 50, -100)

        # Add player and combat context
        context = self._gather_full_context()
        player = context.get("player", {})

        # Show player effects that might affect combat
        if player.get("active_effects"):
            narrative += "\n\n**Your status:**"
            for effect in player["active_effects"]:
                narrative += f"\n- {effect}"

        if player.get("wounds"):
            narrative += f"\n*You carry {len(player['wounds'])} wound(s).*"

        # Show enemy status if known
        if npc.status == "wounded":
            narrative += f"\n\n*{npc.name} appears wounded.*"
        if npc.attributes.get("combat_advantage"):
            narrative += f"\n*{npc.name} has a tactical advantage.*"

        return OrchestrationResult(
            narrative=narrative,
            oracle_used=True,
            oracle_result=result.interpretation,
            oracle_answer=result.answer,
            entities_referenced=[npc.name],
            intent_used="fight"
        )

    def _handle_rest(self, intent: Intent) -> OrchestrationResult:
        """
        Handle resting/camping.

        Checks for interruption via oracle.
        """
        # Oracle check: Is rest interrupted?
        result = self.brain.ask_oracle(
            "Is the rest interrupted",
            likelihood="unlikely"  # Usually rest succeeds
        )

        if result.answer.startswith("yes"):
            interruption = self._generate_interruption()
            narrative = f"**{result.answer_text}**\n\n" \
                       f"Your rest is interrupted! {interruption}"
        else:
            narrative = f"**{result.answer_text}**\n\n" \
                       f"You rest without incident. Time passes peacefully."

        return OrchestrationResult(
            narrative=narrative,
            oracle_used=True,
            oracle_result=result.interpretation,
            oracle_answer=result.answer,
            intent_used="rest"
        )

    def _handle_use(self, intent: Intent) -> OrchestrationResult:
        """
        Handle using an item.

        Context-dependent resolution based on item and target.
        """
        item = intent.extras.get("item") or intent.target or "the item"
        target = intent.target if "item" in intent.extras else None

        if target:
            question = f"Does using {item} on {target} work"
        else:
            question = f"Does using {item} work"

        result = self.brain.ask_oracle(question, likelihood="even")

        if result.answer.startswith("yes"):
            narrative = f"**{result.answer_text}**\n\n" \
                       f"You use {item}" + (f" on {target}" if target else "") + \
                       ". It works!"
        else:
            narrative = f"**{result.answer_text}**\n\n" \
                       f"Your attempt to use {item}" + \
                       (f" on {target}" if target else "") + " fails."

        return OrchestrationResult(
            narrative=narrative,
            oracle_used=True,
            oracle_result=result.interpretation,
            oracle_answer=result.answer,
            intent_used="use"
        )

    def _handle_observe(self, intent: Intent) -> OrchestrationResult:
        """
        Handle observing/hiding/stealth.

        Uses oracle to determine success.
        """
        target = intent.target

        if target:
            # Observing something specific
            result = self.brain.ask_oracle(
                f"Do I notice something important about {target}",
                likelihood="even"
            )

            if result.answer.startswith("yes"):
                observation = self._generate_observation(target)
                narrative = f"**{result.answer_text}**\n\n{observation}"
            else:
                narrative = f"**{result.answer_text}**\n\n" \
                           f"You watch {target} but notice nothing unusual."
        else:
            # Just hiding
            result = self.brain.ask_oracle(
                "Do I remain undetected",
                likelihood="likely"
            )

            if result.answer.startswith("yes"):
                narrative = f"**{result.answer_text}**\n\n" \
                           f"You remain hidden in the shadows."
            else:
                narrative = f"**{result.answer_text}**\n\n" \
                           f"You've been spotted!"

        return OrchestrationResult(
            narrative=narrative,
            oracle_used=True,
            oracle_result=result.interpretation,
            oracle_answer=result.answer,
            intent_used="observe"
        )

    def _handle_interact(self, intent: Intent) -> OrchestrationResult:
        """
        Handle interacting with objects (open, close, take, etc.)

        Uses oracle for uncertain outcomes.
        """
        target = intent.target or "it"

        # Determine the action from raw input
        action_verbs = ["open", "close", "lock", "unlock", "push", "pull",
                       "take", "grab", "pick up", "lift", "turn", "press"]
        action = "interact with"
        for verb in action_verbs:
            if verb in intent.raw_input.lower():
                action = verb
                break

        # Oracle check
        result = self.brain.ask_oracle(
            f"Can I {action} {target}",
            likelihood="likely"
        )

        if result.answer.startswith("yes"):
            narrative = f"**{result.answer_text}**\n\n" \
                       f"You {action} {target} successfully."
        else:
            narrative = f"**{result.answer_text}**\n\n" \
                       f"You cannot {action} {target}."

        return OrchestrationResult(
            narrative=narrative,
            oracle_used=True,
            oracle_result=result.interpretation,
            oracle_answer=result.answer,
            intent_used="interact"
        )

    def _handle_describe(self, intent: Intent) -> OrchestrationResult:
        """Handle scene description requests with WorldModel context."""
        # Get current location from scene
        location = self.brain.memory.current_scene.get("location", "")

        if location:
            # Get the location entity for rich info
            entity = self.world_model.get_or_create_entity(location, "location")
            entity.discovered = True
            entity.revealed_attributes.add("description")

            # Build comprehensive description
            parts = []
            parts.append(f"**{entity.name}**")
            parts.append("")

            if entity.description:
                parts.append(entity.description)
                parts.append("")

            if entity.traits:
                parts.append(f"**Character:** {', '.join(entity.traits)}")

            # Show features, hazards, etc.
            if "features" in entity.attributes and entity.attributes["features"]:
                entity.revealed_attributes.add("features")
                parts.append(f"**Features:** {'; '.join(entity.attributes['features'])}")

            if "hazards" in entity.attributes and entity.attributes["hazards"]:
                entity.revealed_attributes.add("hazards")
                parts.append(f"**Hazards:** {'; '.join(entity.attributes['hazards'])}")

            if "history" in entity.attributes and entity.attributes["history"]:
                entity.revealed_attributes.add("history")
                parts.append(f"**History:** {entity.attributes['history']}")

            # Discoveries made here
            if "discoveries" in entity.attributes and entity.attributes["discoveries"]:
                parts.append("")
                parts.append("**You have discovered:**")
                for disc in entity.attributes["discoveries"]:
                    parts.append(f"- {disc}")

            # Present NPCs
            npcs = self.brain.memory.current_scene.get("present_npcs", [])
            if npcs:
                parts.append("")
                parts.append(f"**Present:** {', '.join(npcs)}")

            # Add player state context
            player = self.brain.memory.entities.get("player")
            if player:
                if player.attributes.get("active_effects"):
                    parts.append("")
                    parts.append("**Affecting You:**")
                    for effect in player.attributes["active_effects"]:
                        parts.append(f"- {effect}")
                if player.attributes.get("wounds"):
                    parts.append(f"*You carry {len(player.attributes['wounds'])} wound(s).*")

            # Add active threads
            active_threads = [t for t in self.brain.memory.threads.values() if t.status == "active"]
            if active_threads:
                parts.append("")
                parts.append("**Unresolved Matters:**")
                for thread in active_threads[:3]:
                    parts.append(f"- {thread.name}")

            narrative = "\n".join(parts)
        else:
            narrative = self.brain.describe_current_scene()

        return OrchestrationResult(
            narrative=narrative,
            intent_used="describe"
        )

    # =========================================================================
    # New Intent Handlers (Social, Craft, Trade, etc.)
    # =========================================================================

    def _handle_social(self, intent: Intent) -> OrchestrationResult:
        """
        Handle social skill attempts (persuade, intimidate, charm, deceive).

        Uses oracle with likelihood based on NPC disposition and skill type.
        Adjusts NPC disposition based on outcome.
        """
        npc = intent.resolved_npc
        skill = intent.action  # persuade, intimidate, charm, deceive
        target_name = intent.target or "them"

        if npc is None:
            # Try to create via WorldModel
            npc = self.world_model.get_or_create_entity(target_name, "npc")

        # Determine likelihood based on skill type and disposition
        if skill == "intimidate":
            # Intimidation harder on friendly NPCs, easier on hostile
            likelihood = "likely" if npc.disposition < 0 else "even"
        elif skill == "charm":
            # Charm easier on neutral/friendly, harder on hostile
            likelihood = "unlikely" if npc.disposition < -30 else "even"
        elif skill == "deceive":
            # Deception affected by trust (higher disposition = more trusting)
            likelihood = "likely" if npc.disposition > 20 else "even"
        else:  # persuade
            likelihood = self._disposition_to_likelihood(npc.disposition)

        result = self.brain.ask_oracle(
            f"Does my attempt to {skill} {npc.name} succeed",
            likelihood=likelihood
        )

        # Use responder's action_result for consistent formatting
        # Also adjust disposition based on outcome
        disposition_change = 0

        if result.answer in ["yes_and", "yes"]:
            success = "critical_success" if result.answer == "yes_and" else "success"
            details = self._generate_social_success(npc, skill)
            narrative = self.brain.responder.action_result(success, skill, details)
            # Successful social interactions improve disposition (except intimidate)
            if skill == "intimidate":
                disposition_change = -15 if result.answer == "yes_and" else -10
            else:
                disposition_change = 15 if result.answer == "yes_and" else 10
        elif result.answer == "yes_but":
            details = self._generate_social_partial(npc, skill)
            narrative = self.brain.responder.action_result("partial", skill, details)
            # Partial success - minor effect
            disposition_change = -5 if skill == "intimidate" else 5
        else:
            success = "critical_failure" if result.answer == "no_and" else "failure"
            details = self._generate_social_failure(npc, skill)
            narrative = self.brain.responder.action_result(success, skill, details)
            # Failed social attempts hurt disposition
            disposition_change = -15 if result.answer == "no_and" else -5

        # Apply disposition change and record it
        if disposition_change != 0:
            old_disposition = npc.disposition
            npc.disposition = max(-100, min(100, npc.disposition + disposition_change))
            npc.notes.append(f"{skill.title()} attempt: {disposition_change:+d} disposition")

        return OrchestrationResult(
            narrative=f"**{result.answer_text}**\n\n{narrative}",
            oracle_used=True,
            oracle_result=result.interpretation,
            oracle_answer=result.answer,
            entities_referenced=[npc.name],
            intent_used=skill
        )

    def _handle_follow(self, intent: Intent) -> OrchestrationResult:
        """Handle following/tracking someone."""
        target = intent.target or "the target"

        result = self.brain.ask_oracle(
            f"Can I follow {target} undetected",
            likelihood="even"
        )

        if result.answer.startswith("yes"):
            narrative = f"**{result.answer_text}**\n\n" \
                       f"You trail {target} at a safe distance, keeping them in sight."
            if result.answer == "yes_and":
                narrative += f"\n\n{self._generate_bonus_discovery()}"
        else:
            narrative = f"**{result.answer_text}**\n\n" \
                       f"You lose track of {target}."
            if result.answer == "no_and":
                narrative += f"\n\nWorse, {self._generate_escalation()}"

        return OrchestrationResult(
            narrative=narrative,
            oracle_used=True,
            oracle_result=result.interpretation,
            oracle_answer=result.answer,
            intent_used="follow"
        )

    def _handle_flee(self, intent: Intent) -> OrchestrationResult:
        """Handle fleeing/escaping."""
        result = self.brain.ask_oracle(
            "Do I escape successfully",
            likelihood="even"
        )

        if result.answer.startswith("yes"):
            narrative = f"**{result.answer_text}**\n\n" \
                       f"You successfully disengage and escape!"
            if result.answer == "yes_and":
                narrative += f"\n\n{self._generate_bonus_discovery()}"
        else:
            narrative = f"**{result.answer_text}**\n\n" \
                       f"Your escape attempt fails!"
            if result.answer == "no_and":
                narrative += f"\n\n{self._generate_escalation()}"

        return OrchestrationResult(
            narrative=narrative,
            oracle_used=True,
            oracle_result=result.interpretation,
            oracle_answer=result.answer,
            intent_used="flee"
        )

    def _handle_defend(self, intent: Intent) -> OrchestrationResult:
        """Handle defensive actions (block, parry, dodge, take cover)."""
        result = self.brain.ask_oracle(
            "Does my defense succeed",
            likelihood="likely"  # Defensive actions generally favored
        )

        if result.answer.startswith("yes"):
            narrative = f"**{result.answer_text}**\n\n" \
                       f"Your defensive stance holds!"
        else:
            narrative = f"**{result.answer_text}**\n\n" \
                       f"Your defense falters!"
            if result.answer == "no_and":
                narrative += f"\n\n{self._generate_escalation()}"

        return OrchestrationResult(
            narrative=narrative,
            oracle_used=True,
            oracle_result=result.interpretation,
            oracle_answer=result.answer,
            intent_used="defend"
        )

    def _handle_craft(self, intent: Intent) -> OrchestrationResult:
        """Handle crafting/creating items."""
        target = intent.target or "the item"

        result = self.brain.ask_oracle(
            f"Do I successfully craft {target}",
            likelihood="even"
        )

        if result.answer in ["yes_and", "yes"]:
            quality = "exceptional" if result.answer == "yes_and" else "good"
            narrative = f"**{result.answer_text}**\n\n" \
                       f"You successfully craft {target}. The quality is {quality}."
        elif result.answer == "yes_but":
            narrative = f"**{result.answer_text}**\n\n" \
                       f"You create {target}, but {self._generate_complication()}"
        elif result.answer == "no_but":
            narrative = f"**{result.answer_text}**\n\n" \
                       f"The crafting fails, but {self._generate_silver_lining()}"
        else:
            narrative = f"**{result.answer_text}**\n\n" \
                       f"Your attempt to craft {target} fails."
            if result.answer == "no_and":
                narrative += f"\n\nWorse, {self._generate_escalation()}"

        return OrchestrationResult(
            narrative=narrative,
            oracle_used=True,
            oracle_result=result.interpretation,
            oracle_answer=result.answer,
            intent_used="craft"
        )

    def _handle_trade(self, intent: Intent) -> OrchestrationResult:
        """Handle buying/selling items."""
        target = intent.target or "goods"

        # Determine if buying or selling from raw input
        is_selling = any(word in intent.raw_input.lower()
                        for word in ["sell", "barter", "pawn", "fence"])
        action = "sell" if is_selling else "buy"

        result = self.brain.ask_oracle(
            f"Is the {action} successful",
            likelihood="likely"
        )

        if result.answer.startswith("yes"):
            if result.answer == "yes_and":
                narrative = f"**{result.answer_text}**\n\n" \
                           f"The trade goes excellently! You {action} {target} at a great price."
            else:
                narrative = f"**{result.answer_text}**\n\n" \
                           f"You {action} {target} at a fair price."
        elif result.answer == "yes_but":
            narrative = f"**{result.answer_text}**\n\n" \
                       f"You {action} {target}, but {self._generate_complication()}"
        else:
            narrative = f"**{result.answer_text}**\n\n" \
                       f"The trade falls through. You cannot {action} {target}."

        return OrchestrationResult(
            narrative=narrative,
            oracle_used=True,
            oracle_result=result.interpretation,
            oracle_answer=result.answer,
            intent_used="trade"
        )

    def _handle_pray(self, intent: Intent) -> OrchestrationResult:
        """Handle prayer/meditation."""
        target = intent.target  # Deity or shrine

        result = self.brain.ask_oracle(
            "Does the prayer bring guidance",
            likelihood="even"
        )

        if result.answer.startswith("yes"):
            narrative = f"**{result.answer_text}**\n\n"
            if target:
                narrative += f"Your prayers to {target} are answered. "
            else:
                narrative += "Your meditation brings clarity. "
            narrative += "A sense of peace and guidance fills you."

            if result.answer == "yes_and":
                narrative += f"\n\nMoreover, {self._generate_bonus_discovery()}"
        else:
            narrative = f"**{result.answer_text}**\n\n" \
                       "The silence stretches on. No answer comes... yet."

        return OrchestrationResult(
            narrative=narrative,
            oracle_used=True,
            oracle_result=result.interpretation,
            oracle_answer=result.answer,
            intent_used="pray"
        )

    def _handle_generic(self, intent: Intent) -> OrchestrationResult:
        """Fallback handler for unrecognized intents."""
        return OrchestrationResult(
            narrative=self._fallback(intent.raw_input),
            intent_used="generic"
        )

    # =========================================================================
    # Context Gathering Methods (Phase 2)
    # =========================================================================

    def _gather_full_context(self, query: str = "") -> Dict[str, Any]:
        """
        Gather ALL relevant context from game state.
        Called by every handler for rich responses.
        """
        context = {
            "location": self._get_location_context(),
            "player": self._get_player_context(),
            "npcs": self._get_npc_context(),
            "threads": self._get_thread_context(),
            "related": self._find_related_entities(query),
        }
        return context

    def _get_location_context(self) -> Dict:
        """Get current location details."""
        loc_name = self.brain.memory.current_scene.get("location", "")
        if not loc_name:
            return {}
        entity = self.world_model.get_or_create_entity(loc_name, "location")
        return {
            "name": entity.name,
            "description": entity.description,
            "features": entity.attributes.get("features", []),
            "hazards": entity.attributes.get("hazards", []),
            "mood": self.brain.memory.current_scene.get("mood", "neutral"),
        }

    def _get_player_context(self) -> Dict:
        """Get player state."""
        player = self.brain.memory.entities.get("player")
        if not player:
            return {}
        return {
            "active_effects": player.attributes.get("active_effects", []),
            "wounds": player.attributes.get("wounds", []),
        }

    def _get_npc_context(self) -> List[Dict]:
        """Get info on present NPCs."""
        present = self.brain.memory.current_scene.get("present_npcs", [])
        npcs = []
        for name in present:
            entity_id = name.lower().replace(" ", "_")
            entity = self.brain.memory.entities.get(entity_id)
            if entity:
                npcs.append({
                    "name": entity.name,
                    "description": entity.description,
                    "disposition": entity.disposition,
                    "knowledge": entity.attributes.get("knowledge_topics", []),
                })
        return npcs

    def _get_thread_context(self) -> List[Dict]:
        """Get active threads (quests, complications)."""
        return [
            {"name": t.name, "description": t.description, "status": t.status}
            for t in self.brain.memory.threads.values()
            if t.status == "active"
        ]

    def _find_related_entities(self, query: str) -> List[Dict]:
        """Find entities mentioned in query."""
        if not query:
            return []
        query_lower = query.lower()
        related = []
        for entity in self.brain.memory.entities.values():
            if entity.name.lower() in query_lower:
                related.append({
                    "name": entity.name,
                    "type": entity.entity_type,
                    "description": entity.description,
                    "attributes": entity.attributes,
                })
        return related

    def _format_context_narrative(self, context: Dict, focus: str = "all") -> str:
        """Format gathered context as narrative prose."""
        parts = []

        if focus in ["all", "location"] and context.get("location"):
            loc = context["location"]
            parts.append(f"**{loc['name']}**")
            if loc.get("description"):
                parts.append(loc["description"])
            if loc.get("features"):
                parts.append(f"*{'; '.join(loc['features'][:3])}*")
            if loc.get("hazards"):
                parts.append(f"**Hazards:** {'; '.join(loc['hazards'])}")

        if focus in ["all", "player"] and context.get("player"):
            player = context["player"]
            if player.get("active_effects"):
                parts.append("\n**Affecting You:**")
                for effect in player["active_effects"]:
                    parts.append(f"- {effect}")

        if focus in ["all", "threads"] and context.get("threads"):
            if context["threads"]:
                parts.append("\n**Unresolved:**")
                for t in context["threads"][:3]:
                    parts.append(f"- {t['name']}")

        if focus in ["all", "npcs"] and context.get("npcs"):
            if context["npcs"]:
                names = [n["name"] for n in context["npcs"]]
                parts.append(f"\n**Present:** {', '.join(names)}")

        return "\n".join(parts) if parts else ""

    def _format_player_state_response(self, context: Dict) -> OrchestrationResult:
        """Format response specifically for player state queries."""
        parts = []

        # Player effects
        player = context.get("player", {})
        if player.get("active_effects"):
            parts.append("**Active Effects on You:**")
            for effect in player["active_effects"]:
                parts.append(f"- {effect}")

        # Complication threads
        for thread in context.get("threads", []):
            desc_lower = thread["description"].lower()
            if any(kw in desc_lower for kw in ["curse", "afflict", "danger", "threat", "complication"]):
                parts.append(f"\n**{thread['name']}:** {thread['description']}")

        if parts:
            return OrchestrationResult(narrative="\n".join(parts), intent_used="query_state")
        else:
            return OrchestrationResult(
                narrative="You have no active effects, curses, or complications at this time.",
                intent_used="query_state"
            )

    def _handle_query_state(self, intent: Intent) -> OrchestrationResult:
        """Handle queries about player state using full context search."""
        context = self._gather_full_context(intent.raw_input)
        return self._format_player_state_response(context)

    # =========================================================================
    # NEW Intent Handlers (Steps 5-7)
    # =========================================================================

    def _handle_assess(self, intent: Intent) -> OrchestrationResult:
        """
        Handle ASSESS intent - evaluating situations/threats (Step 5).

        Answers questions like "How dangerous is the situation?"
        or "Can I take on those guards?"
        """
        target = intent.target or "the situation"

        # Oracle check for assessment
        result = self.brain.ask_oracle(
            f"Is {target} favorable to me",
            likelihood=self._assess_context_likelihood()
        )

        # Generate assessment narrative
        if result.answer.startswith("yes"):
            if result.answer == "yes_and":
                assessment = f"Your assessment of {target} is highly favorable. " \
                            "Not only are conditions in your favor, but you notice " \
                            "an unexpected advantage."
            else:
                assessment = f"You assess {target} and find conditions favorable. " \
                            "You could proceed with reasonable confidence."
        elif result.answer == "yes_but":
            assessment = f"Your assessment of {target} shows mixed signals. " \
                        "You could succeed, but there are complications to consider."
        elif result.answer == "no_but":
            assessment = f"{target.title()} doesn't look favorable, but it's not hopeless. " \
                        "There may be ways to improve your odds."
        else:
            severity = "dire" if result.answer == "no_and" else "unfavorable"
            assessment = f"Your assessment of {target} is {severity}. " \
                        "Caution would be wise."

        return OrchestrationResult(
            narrative=f"**Assessment of {target}:**\n\n{assessment}",
            oracle_used=True,
            oracle_result=result.interpretation,
            oracle_answer=result.answer,
            intent_used="assess"
        )

    def _assess_context_likelihood(self) -> str:
        """Determine likelihood based on current scene context."""
        # Could factor in tension level, chaos, etc.
        tension = self.brain.memory.tension_level
        if tension > 7:
            return "unlikely"
        elif tension > 4:
            return "even"
        else:
            return "likely"

    def _handle_recall(self, intent: Intent) -> OrchestrationResult:
        """
        Handle RECALL intent - querying memory (Step 6).

        Retrieves known information about a topic from session memory.
        """
        topic = intent.topic or intent.target or "recent events"

        # Search memory for relevant facts
        facts = self._search_memory_for_topic(topic)

        if facts:
            narrative = f"**What you know about {topic}:**\n\n"
            for fact in facts:
                narrative += f"- {fact}\n"
        else:
            narrative = f"You don't recall anything specific about {topic}. " \
                       "Perhaps you haven't encountered this yet."

        return OrchestrationResult(
            narrative=narrative,
            intent_used="recall"
        )

    def _search_memory_for_topic(self, topic: str) -> List[str]:
        """Search session memory for facts about a topic."""
        facts = []
        topic_lower = topic.lower()

        # Check established facts
        for fact in self.brain.memory.facts:
            if topic_lower in fact.lower():
                facts.append(fact)

        # Check entities
        for entity in self.brain.memory.entities.values():
            if topic_lower in entity.name.lower() or \
               topic_lower in entity.description.lower():
                facts.append(f"{entity.name}: {entity.description}")
                if entity.traits:
                    facts.append(f"Known traits: {', '.join(entity.traits)}")

        # Check threads
        for thread in self.brain.memory.threads.values():
            if topic_lower in thread.name.lower() or \
               topic_lower in thread.description.lower():
                facts.append(f"Plot thread - {thread.name}: {thread.description}")
                if thread.developments:
                    facts.append(f"Recent: {thread.developments[-1]}")

        # Limit to avoid overwhelming output
        return facts[:5]

    def _handle_sense(self, intent: Intent) -> OrchestrationResult:
        """
        Handle SENSE intent - perception checks (Step 7).

        Handles "What do I hear?", "What do I smell?", etc.
        """
        # Determine which sense from raw input
        sense_type = self._determine_sense_type(intent.raw_input)

        # Oracle check for perception
        result = self.brain.ask_oracle(
            "Do I perceive something notable",
            likelihood="even"
        )

        if result.answer.startswith("yes"):
            # Pull sensory detail from content router
            if self.content_router:
                detail = self.content_router.pull_sensory(sense_type)
            else:
                detail = self._generate_sensory_detail(sense_type)

            if result.answer == "yes_and":
                bonus = self._generate_sensory_bonus()
                narrative = f"**{result.answer_text}**\n\n{detail}\n\nMoreover, {bonus}"
            else:
                narrative = f"**{result.answer_text}**\n\n{detail}"
        else:
            narrative = f"**{result.answer_text}**\n\n" \
                       "Your senses don't detect anything unusual at the moment."

        return OrchestrationResult(
            narrative=narrative,
            oracle_used=True,
            oracle_result=result.interpretation,
            oracle_answer=result.answer,
            intent_used="sense"
        )

    def _determine_sense_type(self, raw_input: str) -> str:
        """Determine which sense category based on input."""
        text_lower = raw_input.lower()

        if "hear" in text_lower or "listen" in text_lower or "sound" in text_lower:
            # Check mood for appropriate sound type
            mood = self.brain.memory.current_scene.get("mood", "neutral")
            if mood in ["dangerous", "tense", "hostile"]:
                return "sounds_tense"
            elif mood in ["calm", "safe", "peaceful"]:
                return "sounds_peaceful"
            return "sounds_tense"

        if "smell" in text_lower or "sniff" in text_lower or "odor" in text_lower:
            mood = self.brain.memory.current_scene.get("mood", "neutral")
            if mood in ["dangerous", "hostile"]:
                return "smells_unpleasant"
            elif mood in ["calm", "safe", "pleasant"]:
                return "smells_pleasant"
            return "smells_neutral"

        if "see" in text_lower or "look" in text_lower or "peer" in text_lower:
            return "sights_details"

        if "feel" in text_lower or "sense" in text_lower:
            return "atmospheric_details"

        return "atmospheric_details"  # Default

    def _generate_sensory_detail(self, sense_type: str) -> str:
        """Generate a sensory detail when content router unavailable."""
        defaults = {
            "sounds_tense": "You hear something moving in the shadows.",
            "sounds_peaceful": "The ambient sounds are calm and unthreatening.",
            "sounds_combat": "The sounds of battle fill the air.",
            "smells_pleasant": "A pleasant scent reaches your nostrils.",
            "smells_unpleasant": "An unpleasant odor hangs in the air.",
            "smells_neutral": "The air carries a mix of familiar scents.",
            "sights_details": "Something catches your eye in the environment.",
            "atmospheric_details": "The atmosphere feels charged with significance.",
        }
        return defaults.get(sense_type, "Your senses pick up something notable.")

    def _generate_sensory_bonus(self) -> str:
        """Generate bonus sensory information for yes_and results."""
        bonuses = [
            "this reveals something important about your surroundings",
            "you notice a detail others might have missed",
            "your heightened awareness pays off",
            "this information could prove valuable",
        ]
        return random.choice(bonuses)

    # =========================================================================
    # World Model Intent Handlers
    # =========================================================================

    def _handle_recall_lore(self, intent: Intent) -> OrchestrationResult:
        """
        Handle recall_lore intent - retrieve stable world information.

        This handler queries the WorldModel for persistent entity information
        instead of rolling random oracle results. Asking about the same
        location/NPC/item twice returns consistent information.

        Args:
            intent: The parsed intent with target

        Returns:
            OrchestrationResult with entity information
        """
        target = intent.target or "the area"

        # Resolve "this place", "here", "this location" to current location
        location_refs = ["this place", "here", "this location", "this area", "the area"]
        if target.lower() in location_refs:
            current_loc = self.brain.memory.current_scene.get("location", "")
            if current_loc:
                target = current_loc

        entity_type = self._infer_entity_type(target)

        # Get or create entity via WorldModel (stable attributes)
        entity = self.world_model.get_or_create_entity(
            target,
            entity_type,
            {"mood": self.brain.memory.current_scene.get("mood", "neutral")}
        )

        if entity.discovered:
            # Return what player knows
            return self._format_known_entity(entity)
        else:
            # First encounter - mark discovered, reveal basics
            entity.discovered = True
            entity.revealed_attributes.add("description")
            if entity.traits:
                entity.revealed_attributes.add("traits")
            return self._format_discovery_entity(entity)

    def _infer_entity_type(self, target: str) -> str:
        """
        Infer entity type from target name and context.

        Args:
            target: The target name

        Returns:
            Entity type string
        """
        target_lower = target.lower()

        # Check if it's the current location
        current_location = self.brain.memory.current_scene.get("location", "").lower()
        if current_location and target_lower in current_location.lower():
            return "location"

        # Check if it matches a known NPC
        for entity_id, entity in self.brain.memory.entities.items():
            if entity.entity_type == "npc" and target_lower in entity.name.lower():
                return "npc"

        # Check present NPCs
        present_npcs = self.brain.memory.current_scene.get("present_npcs", [])
        for npc in present_npcs:
            if target_lower in npc.lower():
                return "npc"

        # Keyword-based inference
        location_keywords = [
            "gate", "tower", "castle", "village", "town", "city",
            "forest", "mountain", "river", "road", "path", "bridge",
            "dungeon", "cave", "temple", "shrine", "tavern", "inn",
            "market", "square", "harbor", "port", "keep", "fortress"
        ]

        npc_keywords = [
            "captain", "guard", "merchant", "blacksmith", "innkeeper",
            "king", "queen", "lord", "lady", "priest", "wizard",
            "soldier", "thief", "beggar", "stranger"
        ]

        item_keywords = [
            "sword", "shield", "armor", "ring", "amulet", "scroll",
            "potion", "key", "book", "artifact", "relic"
        ]

        for keyword in location_keywords:
            if keyword in target_lower:
                return "location"

        for keyword in npc_keywords:
            if keyword in target_lower:
                return "npc"

        for keyword in item_keywords:
            if keyword in target_lower:
                return "item"

        # Default to location for places, otherwise generic
        return "location"

    def _format_known_entity(self, entity: TrackedEntity) -> OrchestrationResult:
        """
        Format response for an entity - always show full context.

        Args:
            entity: The tracked entity

        Returns:
            OrchestrationResult with comprehensive information
        """
        parts = []

        # Header
        parts.append(f"**{entity.name}** ({entity.entity_type.title()})")
        parts.append("")

        # Description - always show
        if entity.description:
            parts.append(entity.description)
            parts.append("")

        # Traits - always show
        if entity.traits:
            parts.append(f"**Character:** {', '.join(entity.traits)}")

        # Show ALL relevant attributes for full context
        # Features
        if "features" in entity.attributes and entity.attributes["features"]:
            features = entity.attributes["features"]
            if isinstance(features, list):
                parts.append(f"**Features:** {'; '.join(features)}")
            else:
                parts.append(f"**Features:** {features}")

        # Hazards
        if "hazards" in entity.attributes and entity.attributes["hazards"]:
            hazards = entity.attributes["hazards"]
            if isinstance(hazards, list):
                parts.append(f"**Hazards:** {'; '.join(hazards)}")
            else:
                parts.append(f"**Hazards:** {hazards}")

        # History
        if "history" in entity.attributes and entity.attributes["history"]:
            parts.append(f"**History:** {entity.attributes['history']}")

        # Danger level
        if "danger_level" in entity.attributes:
            parts.append(f"**Danger:** {entity.attributes['danger_level']}")

        # NPC-specific: knowledge topics
        if entity.entity_type == "npc":
            if "knowledge_topics" in entity.attributes and entity.attributes["knowledge_topics"]:
                topics = entity.attributes["knowledge_topics"]
                parts.append(f"**Knows about:** {', '.join(topics)}")
            if entity.disposition != 0:
                disp_text = "friendly" if entity.disposition > 20 else "hostile" if entity.disposition < -20 else "neutral"
                parts.append(f"**Disposition:** {disp_text} ({entity.disposition:+d})")

        # Discoveries made here
        if "discoveries" in entity.attributes and entity.attributes["discoveries"]:
            parts.append("")
            parts.append("**Discoveries:**")
            for disc in entity.attributes["discoveries"]:
                # Truncate long discovery text
                disc_short = disc[:100] + "..." if len(disc) > 100 else disc
                parts.append(f"- {disc_short}")

        # Status if relevant
        if entity.status != "active":
            parts.append(f"\n*Status: {entity.status}*")

        narrative = "\n".join(parts)

        return OrchestrationResult(
            narrative=narrative,
            entities_referenced=[entity.name],
            intent_used="recall_lore"
        )

    def _format_discovery_entity(self, entity: TrackedEntity) -> OrchestrationResult:
        """
        Format response for first discovery of an entity - show FULL context.

        Args:
            entity: The newly discovered entity

        Returns:
            OrchestrationResult with comprehensive discovery narrative
        """
        # Just use the same comprehensive format as known entities
        # The user wants full context always
        return self._format_known_entity(entity)

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _disposition_to_likelihood(self, disposition: int) -> str:
        """Convert NPC disposition to oracle likelihood."""
        if disposition > 50:
            return "very_likely"
        elif disposition > 20:
            return "likely"
        elif disposition > -20:
            return "even"
        elif disposition > -50:
            return "unlikely"
        else:
            return "very_unlikely"

    def _generate_informative_dialogue(self, npc: TrackedEntity, topic: str) -> str:
        """Generate dialogue where NPC shares information."""
        templates = [
            f'"{topic.title()}? Yes, I know of this,"  says {npc.name}.',
            f'{npc.name} nods slowly. "I can tell you about {topic}."',
            f'"Ah, {topic}," {npc.name} says. "I have knowledge of this matter."',
        ]
        return random.choice(templates)

    def _generate_partial_dialogue(self, npc: TrackedEntity, topic: str) -> str:
        """Generate dialogue where NPC knows but is hesitant."""
        templates = [
            f'{npc.name} hesitates. "I know something of {topic}, but..."',
            f'"About {topic}..." {npc.name} looks around nervously.',
            f'{npc.name} lowers their voice. "I shouldn\'t speak of {topic}, but..."',
        ]
        return random.choice(templates)

    def _generate_redirect_dialogue(self, npc: TrackedEntity, topic: str) -> str:
        """Generate dialogue where NPC redirects to another source."""
        templates = [
            f'{npc.name} shakes their head. "I know nothing of {topic}. '
            f'But perhaps someone else does..."',
            f'"Not {topic}, no," says {npc.name}. "But I\'ve heard rumors..."',
            f'{npc.name} considers. "I cannot help with {topic} specifically, '
            f'but there may be another way."',
        ]
        return random.choice(templates)

    def _generate_unhelpful_dialogue(self, npc: TrackedEntity, topic: str) -> str:
        """Generate dialogue where NPC doesn't help."""
        templates = [
            f'{npc.name} shrugs. "I know nothing of {topic}."',
            f'"Never heard of it," {npc.name} says flatly.',
            f'{npc.name} shakes their head. "{topic}? Means nothing to me."',
        ]
        return random.choice(templates)

    def _generate_bonus_info(self, topic: str) -> str:
        """Generate bonus information for yes_and results."""
        templates = [
            f"Moreover, there's something else you should know...",
            f"And there's more to {topic} than you might expect.",
            f"In fact, the truth runs deeper than anyone realizes.",
        ]
        return random.choice(templates)

    def _generate_discovery(self, target: str, level: str) -> str:
        """Generate a discovery narrative connected to scene context."""
        location = self.brain.memory.current_scene.get("location", "the area")
        mood = self.brain.memory.current_scene.get("mood", "neutral")

        # Pull discovery content from TOML if available
        if self.content_router:
            toml_discovery = self.content_router.pull_discovery(mood)
        else:
            toml_discovery = None

        if level == "exceptional":
            templates = [
                f"Your search of {location} reveals {target} - and something more. {toml_discovery or 'An unexpected find catches your attention.'}",
                f"Not only do you locate {target}, but {location} yields additional secrets.",
                f"Success! You find {target}. Moreover, your keen eye spots something others would have missed.",
            ]
        elif level == "partial":
            templates = [
                f"In {location}, you find traces of {target}. The signs are there, but incomplete.",
                f"There are signs of {target} here. Someone or something has been here recently.",
                f"You locate evidence related to {target}, though not what you hoped for.",
            ]
        else:  # success
            templates = [
                f"Your search of {location} is rewarded. You find {target}.",
                f"Among the shadows of {location}, you locate {target}.",
                f"{target.title()} is here. Your persistence pays off.",
            ]

        base = random.choice(templates)

        # Add scene-specific flavor
        if mood == "dangerous" or mood == "tense":
            base += " You should be cautious - this place holds more than it reveals."
        elif mood == "mysterious":
            base += " Questions remain, but this is a start."

        return base

    def _generate_bonus_discovery(self) -> str:
        """Generate bonus discovery for yes_and, connected to story threads."""
        location = self.brain.memory.current_scene.get("location", "here")

        # Try to tie to an active plot thread
        active_threads = list(self.brain.memory.threads.values())
        if active_threads:
            thread = random.choice(active_threads)
            thread_bonuses = [
                f"This connects to {thread.name} in ways you didn't expect.",
                f"You realize this may relate to your investigation of {thread.name}.",
                f"A clue emerges linking this to {thread.name}.",
            ]
            return random.choice(thread_bonuses)

        # Try to reference present NPCs
        present_npcs = self.brain.memory.current_scene.get("present_npcs", [])
        if present_npcs:
            npc = random.choice(present_npcs)
            return f"You notice {npc} watching you with renewed interest."

        # Fallback to responder or generic
        positives = self.brain.responder.elaborations.get("positive", [])
        if positives:
            return random.choice(positives)

        return f"Something in {location} catches your attention - a fortunate discovery."

    def _generate_complication(self) -> str:
        """Generate a complication connected to scene context."""
        location = self.brain.memory.current_scene.get("location", "here")
        mood = self.brain.memory.current_scene.get("mood", "neutral")

        # Try TOML content first
        if self.content_router:
            return self.content_router.pull_complication(mood)

        # Reference NPCs if present
        present_npcs = self.brain.memory.current_scene.get("present_npcs", [])
        if present_npcs and random.random() > 0.5:
            npc = random.choice(present_npcs)
            npc_complications = [
                f"{npc} notices and looks suspicious",
                f"{npc} asks uncomfortable questions",
                f"you sense {npc} watching your every move",
            ]
            return random.choice(npc_complications)

        # Fallback to responder elaborations
        complications = self.brain.responder.elaborations.get("complication", [])
        if complications:
            return random.choice(complications)

        return f"something in {location} complicates matters"

    def _generate_silver_lining(self) -> str:
        """Generate a silver lining connected to story elements."""
        # Try to reference active threads
        active_threads = list(self.brain.memory.threads.values())
        if active_threads and random.random() > 0.5:
            thread = random.choice(active_threads)
            return f"you gain insight about {thread.name}"

        # Try to reference known entities
        entities = list(self.brain.memory.entities.values())
        if entities and random.random() > 0.5:
            entity = random.choice(entities)
            return f"you learn something new about {entity.name}"

        # Fallback to responder
        silver = self.brain.responder.elaborations.get("silver_lining", [])
        if silver:
            return random.choice(silver)

        return "you learn something valuable from the experience"

    def _generate_escalation(self) -> str:
        """Generate an escalation connected to story tension."""
        location = self.brain.memory.current_scene.get("location", "here")
        mood = self.brain.memory.current_scene.get("mood", "neutral")

        # Try TOML content
        if self.content_router:
            escalation = self.content_router.pull_complication("dangerous")
            if escalation:
                return escalation

        # Increase tension feel based on current mood
        if mood in ["dangerous", "tense", "hostile"]:
            tense_escalations = [
                f"the danger in {location} intensifies",
                "enemies draw closer",
                "time is running out",
                "your position is compromised",
            ]
            return random.choice(tense_escalations)

        # Fallback
        escalations = self.brain.responder.elaborations.get("escalation", [])
        if escalations:
            return random.choice(escalations)

        return "the situation takes a turn for the worse"

    def _generate_investigation_detail(self, target: str) -> str:
        """Generate investigation discovery connected to story context."""
        location = self.brain.memory.current_scene.get("location", "here")
        mood = self.brain.memory.current_scene.get("mood", "neutral")

        # Try to connect to active threads
        active_threads = list(self.brain.memory.threads.values())
        if active_threads and random.random() > 0.4:
            thread = random.choice(active_threads)
            thread_details = [
                f"This seems connected to {thread.name}. The pieces are coming together.",
                f"You find evidence that links {target} to your investigation of {thread.name}.",
                f"The truth about {thread.name} grows clearer. This {target} holds answers.",
            ]
            return random.choice(thread_details)

        # Pull from TOML if available
        if self.content_router:
            discovery = self.content_router.pull_discovery(mood)
            if discovery:
                return f"Examining {target} reveals: {discovery}"

        # Context-aware templates
        if mood in ["mysterious", "unknown"]:
            templates = [
                f"The mystery deepens. {target.title()} holds secrets not easily surrendered.",
                f"Something about {target} defies easy explanation.",
                f"You sense there is more to {target} than meets the eye.",
            ]
        elif mood in ["dangerous", "hostile"]:
            templates = [
                f"Your investigation of {target} reveals danger signs.",
                f"There are warnings here. {target.title()} has been disturbed recently.",
                f"You find evidence of recent violence connected to {target}.",
            ]
        else:
            templates = [
                f"Your examination of {target} in {location} yields results.",
                f"A detail about {target} catches your attention.",
                f"Your careful study of {target} reveals something useful.",
            ]

        return random.choice(templates)

    def _generate_interruption(self) -> str:
        """Generate a rest interruption connected to scene context."""
        location = self.brain.memory.current_scene.get("location", "here")

        # Reference present NPCs if any
        present_npcs = self.brain.memory.current_scene.get("present_npcs", [])
        if present_npcs and random.random() > 0.5:
            npc = random.choice(present_npcs)
            return f"{npc} approaches with urgent news."

        # Use responder's event generator
        return self.brain.responder.random_event("negative", self.brain.memory)

    def _generate_observation(self, target: str) -> str:
        """Generate an observation result connected to story."""
        location = self.brain.memory.current_scene.get("location", "here")

        # Connect to active threads if possible
        active_threads = list(self.brain.memory.threads.values())
        if active_threads and random.random() > 0.5:
            thread = random.choice(active_threads)
            return f"Watching {target}, you notice something that connects to {thread.name}."

        # Reference location context
        templates = [
            f"Observing {target} from your position in {location}, you notice something significant.",
            f"Your vigilance pays off. {target.title()}'s behavior reveals useful information.",
            f"Watching carefully, you catch a detail about {target} that others would miss.",
            f"Your observation of {target} in {location} proves enlightening.",
        ]
        return random.choice(templates)

    def _generate_social_success(self, npc: TrackedEntity, skill: str) -> str:
        """Generate social skill success description."""
        templates = {
            "persuade": [
                f"{npc.name} nods thoughtfully. 'You make a compelling argument.'",
                f"Your words find their mark. {npc.name} is convinced.",
                f"{npc.name} considers your point and agrees.",
            ],
            "intimidate": [
                f"{npc.name}'s eyes widen with fear. They back down.",
                f"Your threatening presence cows {npc.name} into submission.",
                f"{npc.name} visibly trembles. 'Alright, alright...'",
            ],
            "charm": [
                f"{npc.name} smiles warmly at you. Your charm works its magic.",
                f"A blush creeps across {npc.name}'s face. They're smitten.",
                f"{npc.name} laughs at your wit. You've won them over.",
            ],
            "deceive": [
                f"{npc.name} accepts your story without question.",
                f"Your lie is convincing. {npc.name} believes every word.",
                f"{npc.name} nods, none the wiser to your deception.",
            ],
        }
        return random.choice(templates.get(skill, ["Your attempt succeeds."]))

    def _generate_social_partial(self, npc: TrackedEntity, skill: str) -> str:
        """Generate social skill partial success description."""
        templates = [
            f"{npc.name} seems partially convinced, but hesitates.",
            f"Your {skill} attempt works... to a point.",
            f"{npc.name} agrees, but you sense reluctance.",
        ]
        return random.choice(templates)

    def _generate_social_failure(self, npc: TrackedEntity, skill: str) -> str:
        """Generate social skill failure description."""
        templates = {
            "persuade": [
                f"{npc.name} shakes their head firmly. 'I'm not convinced.'",
                f"Your arguments fall on deaf ears.",
            ],
            "intimidate": [
                f"{npc.name} stands firm, unimpressed by your threats.",
                f"Your intimidation attempt only seems to anger {npc.name}.",
            ],
            "charm": [
                f"{npc.name} sees through your flattery.",
                f"Your charm fails to impress {npc.name}.",
            ],
            "deceive": [
                f"{npc.name} narrows their eyes. 'I don't believe you.'",
                f"Your lie is transparent. {npc.name} knows you're lying.",
            ],
        }
        return random.choice(templates.get(skill, ["Your attempt fails."]))
