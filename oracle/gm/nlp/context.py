"""
Conversation Context - Tracks recent conversation for pronoun/reference resolution.

This module provides the ConversationContext class that maintains a rolling history
of conversation turns, tracking what entities (NPCs, locations, items) were most
recently mentioned so that pronouns ("him", "it", "there") can be resolved correctly.

Example:
    context = ConversationContext()

    # After "Talk to Grimjaw about the artifact"
    context.record_turn(ConversationTurn(
        user_input="Talk to Grimjaw about the artifact",
        intent_action="talk_to",
        target="Grimjaw",
        topic="the artifact",
        resolved_entities={"npc": "Grimjaw the Fence"}
    ))

    # Now "Ask him about it" can resolve:
    context.last_mentioned_npc  # "Grimjaw the Fence"
    context.current_topic       # "the artifact"
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from collections import deque


@dataclass
class ConversationTurn:
    """
    A single turn in the conversation history.

    Records what the user said, what intent was recognized,
    and what entities were resolved.
    """
    user_input: str
    intent_action: str
    target: Optional[str] = None
    topic: Optional[str] = None
    resolved_entities: Dict[str, Any] = field(default_factory=dict)
    gm_response: Optional[str] = None

    # Metadata
    oracle_used: bool = False
    oracle_result: Optional[str] = None


class ConversationContext:
    """
    Tracks recent conversation for pronoun and reference resolution.

    Maintains a rolling window of recent conversation turns and
    tracks the most recently mentioned entities of each type.
    This enables resolution of:
    - Pronouns: "him", "her", "it", "them", "there"
    - Demonstratives: "that thing", "that place", "that person"
    - Implicit references: "about it", "from there"

    Usage:
        context = ConversationContext()

        # Record a turn
        context.record_turn(ConversationTurn(...))

        # Get last mentioned NPC for "ask him"
        npc_name = context.last_mentioned_npc

        # Get current topic for "tell me more about it"
        topic = context.current_topic
    """

    def __init__(self, max_history: int = 5):
        """
        Initialize conversation context.

        Args:
            max_history: Maximum number of turns to keep in history.
                         Older turns are automatically dropped.
        """
        self.history: deque[ConversationTurn] = deque(maxlen=max_history)

        # Most recently mentioned entities by type
        self.last_mentioned_npc: Optional[str] = None
        self.last_mentioned_location: Optional[str] = None
        self.last_mentioned_item: Optional[str] = None
        self.last_mentioned_thread: Optional[str] = None

        # Current conversation topic (what we're discussing)
        self.current_topic: Optional[str] = None

        # Most recent target of any type
        self._last_target: Optional[str] = None

    def record_turn(self, turn: ConversationTurn):
        """
        Record a conversation turn and update tracked entities.

        This should be called after each user input is processed,
        with the resolved entities from that interaction.

        Args:
            turn: The conversation turn to record
        """
        self.history.append(turn)

        # Update entity tracking from resolved entities
        resolved = turn.resolved_entities

        if resolved.get("npc"):
            self.last_mentioned_npc = resolved["npc"]
            self._last_target = resolved["npc"]

        if resolved.get("location"):
            self.last_mentioned_location = resolved["location"]
            self._last_target = resolved["location"]

        if resolved.get("item"):
            self.last_mentioned_item = resolved["item"]
            self._last_target = resolved["item"]

        if resolved.get("thread"):
            self.last_mentioned_thread = resolved["thread"]

        # Update from raw target if no resolved entities
        if turn.target and not any(resolved.values()):
            self._last_target = turn.target

        # Update current topic
        if turn.topic:
            self.current_topic = turn.topic

    def get_last_target(self, entity_type: Optional[str] = None) -> Optional[str]:
        """
        Get the most recently mentioned entity of a given type.

        Args:
            entity_type: The type of entity to retrieve:
                - "npc": Last mentioned NPC
                - "location": Last mentioned location
                - "item": Last mentioned item
                - "thread": Last mentioned plot thread
                - None: Most recent target of any type

        Returns:
            The entity name/reference, or None if not found
        """
        if entity_type == "npc":
            return self.last_mentioned_npc
        elif entity_type == "location":
            return self.last_mentioned_location
        elif entity_type == "item":
            return self.last_mentioned_item
        elif entity_type == "thread":
            return self.last_mentioned_thread
        else:
            # Return most recent anything
            return self._last_target

    def get_last_oracle_result(self) -> Optional[str]:
        """
        Get the most recent oracle result from history.

        Useful for follow-up questions about what the oracle said.

        Returns:
            The oracle result string, or None if no recent oracle use
        """
        for turn in reversed(self.history):
            if turn.oracle_used and turn.oracle_result:
                return turn.oracle_result
        return None

    def get_last_action(self) -> Optional[str]:
        """
        Get the most recent action/intent.

        Returns:
            The intent action string, or None if no history
        """
        if self.history:
            return self.history[-1].intent_action
        return None

    def get_context_summary(self) -> Dict[str, Any]:
        """
        Get a summary of current context for debugging or display.

        Returns:
            Dictionary with current context state
        """
        return {
            "turns": len(self.history),
            "last_npc": self.last_mentioned_npc,
            "last_location": self.last_mentioned_location,
            "last_item": self.last_mentioned_item,
            "last_thread": self.last_mentioned_thread,
            "current_topic": self.current_topic,
            "last_action": self.get_last_action(),
        }

    def clear(self):
        """Clear all context (e.g., when starting a new scene)."""
        self.history.clear()
        self.last_mentioned_npc = None
        self.last_mentioned_location = None
        self.last_mentioned_item = None
        self.last_mentioned_thread = None
        self.current_topic = None
        self._last_target = None

    def get_recent_npcs(self, limit: int = 3) -> List[str]:
        """
        Get recently mentioned NPCs from conversation history.

        Args:
            limit: Maximum number of NPCs to return

        Returns:
            List of NPC names, most recent first
        """
        npcs = []
        seen = set()

        for turn in reversed(self.history):
            npc = turn.resolved_entities.get("npc")
            if npc and npc not in seen:
                npcs.append(npc)
                seen.add(npc)
                if len(npcs) >= limit:
                    break

        return npcs
