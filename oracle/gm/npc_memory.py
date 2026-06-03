"""
NPC Memory System - Persistent relationship tracking for NPCs.

Extends SessionMemory with detailed conversation logs for each NPC,
tracking what was discussed, promises made, lies told, and how the
relationship has changed over time.

This enables NPCs to remember past interactions:
- "You again. Did you find what you were looking for?"
- "Last time you promised to bring back the chalice..."
- "I trusted you once. That won't happen again."

Usage:
    tracker = NPCMemoryTracker(memory)
    tracker.log_conversation("Grimjaw", topic="artifact location")
    tracker.log_promise("Grimjaw", "Will bring back the chalice")
    tracker.log_lie("Grimjaw", "Claimed to be a merchant")

    # Later, when meeting Grimjaw again:
    context = tracker.get_relationship_context("Grimjaw")
    # Returns: past topics, unfulfilled promises, known lies, disposition history
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple, TYPE_CHECKING
from enum import Enum

if TYPE_CHECKING:
    from oracle.gm.memory import SessionMemory, TrackedEntity


class InteractionType(Enum):
    """Types of NPC interactions."""
    CONVERSATION = "conversation"
    PROMISE = "promise"
    LIE = "lie"
    TRADE = "trade"
    COMBAT = "combat"
    HELP_GIVEN = "help_given"
    HELP_RECEIVED = "help_received"
    BETRAYAL = "betrayal"
    FAVOR = "favor"


@dataclass
class NPCInteraction:
    """A single interaction with an NPC."""
    timestamp: str
    interaction_type: InteractionType
    content: str
    fulfilled: Optional[bool] = None  # For promises
    discovered: Optional[bool] = None  # For lies
    disposition_change: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "type": self.interaction_type.value,
            "content": self.content,
            "fulfilled": self.fulfilled,
            "discovered": self.discovered,
            "disposition_change": self.disposition_change,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "NPCInteraction":
        return cls(
            timestamp=data.get("timestamp", ""),
            interaction_type=InteractionType(data.get("type", "conversation")),
            content=data.get("content", ""),
            fulfilled=data.get("fulfilled"),
            discovered=data.get("discovered"),
            disposition_change=data.get("disposition_change", 0),
            metadata=data.get("metadata", {}),
        )


@dataclass
class NPCConversationLog:
    """Complete conversation history with a single NPC."""
    npc_name: str
    first_met: str = ""
    times_met: int = 0
    interactions: List[NPCInteraction] = field(default_factory=list)
    disposition_history: List[Tuple[str, int, str]] = field(default_factory=list)  # (timestamp, value, reason)
    known_topics: List[str] = field(default_factory=list)  # Topics this NPC knows about
    revealed_to_player: List[str] = field(default_factory=list)  # What NPC has told player
    player_revealed: List[str] = field(default_factory=list)  # What player has told NPC

    def to_dict(self) -> dict:
        return {
            "npc_name": self.npc_name,
            "first_met": self.first_met,
            "times_met": self.times_met,
            "interactions": [i.to_dict() for i in self.interactions],
            "disposition_history": self.disposition_history,
            "known_topics": self.known_topics,
            "revealed_to_player": self.revealed_to_player,
            "player_revealed": self.player_revealed,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "NPCConversationLog":
        log = cls(
            npc_name=data.get("npc_name", ""),
            first_met=data.get("first_met", ""),
            times_met=data.get("times_met", 0),
            disposition_history=data.get("disposition_history", []),
            known_topics=data.get("known_topics", []),
            revealed_to_player=data.get("revealed_to_player", []),
            player_revealed=data.get("player_revealed", []),
        )
        for interaction_data in data.get("interactions", []):
            log.interactions.append(NPCInteraction.from_dict(interaction_data))
        return log

    def get_unfulfilled_promises(self) -> List[NPCInteraction]:
        """Get promises the player made but hasn't fulfilled."""
        return [i for i in self.interactions
                if i.interaction_type == InteractionType.PROMISE
                and i.fulfilled is False]

    def get_undiscovered_lies(self) -> List[NPCInteraction]:
        """Get lies the player told that NPC hasn't discovered."""
        return [i for i in self.interactions
                if i.interaction_type == InteractionType.LIE
                and i.discovered is False]

    def get_discovered_lies(self) -> List[NPCInteraction]:
        """Get lies the NPC has discovered."""
        return [i for i in self.interactions
                if i.interaction_type == InteractionType.LIE
                and i.discovered is True]

    def get_recent_interactions(self, count: int = 5) -> List[NPCInteraction]:
        """Get recent interactions."""
        return self.interactions[-count:]


class NPCMemoryTracker:
    """
    Tracks detailed relationship history with NPCs.

    Works alongside SessionMemory to provide rich conversation history
    that enables NPCs to reference past interactions.
    """

    def __init__(self, memory: "SessionMemory"):
        """
        Initialize the tracker.

        Args:
            memory: The SessionMemory to integrate with
        """
        self.memory = memory
        self.logs: Dict[str, NPCConversationLog] = {}

    def _get_npc_id(self, npc_name: str) -> str:
        """Normalize NPC name to ID."""
        return npc_name.lower().replace(" ", "_")

    def _get_or_create_log(self, npc_name: str) -> NPCConversationLog:
        """Get existing log or create new one."""
        npc_id = self._get_npc_id(npc_name)
        if npc_id not in self.logs:
            self.logs[npc_id] = NPCConversationLog(
                npc_name=npc_name,
                first_met=datetime.now().isoformat(),
            )
        return self.logs[npc_id]

    def log_meeting(self, npc_name: str) -> NPCConversationLog:
        """
        Log that the player met this NPC.

        Args:
            npc_name: The NPC's name

        Returns:
            The NPC's conversation log
        """
        log = self._get_or_create_log(npc_name)
        log.times_met += 1
        return log

    def log_conversation(
        self,
        npc_name: str,
        topic: str,
        summary: str = "",
        disposition_change: int = 0,
    ) -> None:
        """
        Log a conversation topic with an NPC.

        Args:
            npc_name: The NPC's name
            topic: What was discussed
            summary: Brief summary of the conversation
            disposition_change: How much disposition changed (-100 to 100)
        """
        log = self._get_or_create_log(npc_name)

        interaction = NPCInteraction(
            timestamp=datetime.now().isoformat(),
            interaction_type=InteractionType.CONVERSATION,
            content=summary or f"Discussed: {topic}",
            disposition_change=disposition_change,
            metadata={"topic": topic},
        )
        log.interactions.append(interaction)

        # Track topic
        if topic and topic not in log.known_topics:
            log.known_topics.append(topic)

        # Track disposition change
        if disposition_change != 0:
            self._update_disposition(npc_name, disposition_change, f"Conversation about {topic}")

    def log_promise(
        self,
        npc_name: str,
        promise: str,
        to_player: bool = False,
    ) -> None:
        """
        Log a promise made.

        Args:
            npc_name: The NPC's name
            promise: What was promised
            to_player: True if NPC promised player, False if player promised NPC
        """
        log = self._get_or_create_log(npc_name)

        interaction = NPCInteraction(
            timestamp=datetime.now().isoformat(),
            interaction_type=InteractionType.PROMISE,
            content=promise,
            fulfilled=False,
            metadata={"to_player": to_player},
        )
        log.interactions.append(interaction)

    def fulfill_promise(self, npc_name: str, promise_content: str) -> bool:
        """
        Mark a promise as fulfilled.

        Args:
            npc_name: The NPC's name
            promise_content: Content to match against promise

        Returns:
            True if a matching promise was found and fulfilled
        """
        log = self._get_or_create_log(npc_name)

        for interaction in log.interactions:
            if (interaction.interaction_type == InteractionType.PROMISE
                and interaction.fulfilled is False
                and promise_content.lower() in interaction.content.lower()):
                interaction.fulfilled = True
                self._update_disposition(npc_name, 10, f"Fulfilled promise: {promise_content}")
                return True
        return False

    def break_promise(self, npc_name: str, promise_content: str) -> bool:
        """
        Mark a promise as broken (explicitly failed).

        Args:
            npc_name: The NPC's name
            promise_content: Content to match against promise

        Returns:
            True if a matching promise was found and marked broken
        """
        log = self._get_or_create_log(npc_name)

        for interaction in log.interactions:
            if (interaction.interaction_type == InteractionType.PROMISE
                and interaction.fulfilled is False
                and promise_content.lower() in interaction.content.lower()):
                interaction.fulfilled = False
                interaction.metadata["broken"] = True
                self._update_disposition(npc_name, -20, f"Broke promise: {promise_content}")
                return True
        return False

    def log_lie(
        self,
        npc_name: str,
        lie: str,
        what_is_true: str = "",
    ) -> None:
        """
        Log a lie the player told an NPC.

        Args:
            npc_name: The NPC's name
            lie: What the player claimed
            what_is_true: The actual truth (for reference)
        """
        log = self._get_or_create_log(npc_name)

        interaction = NPCInteraction(
            timestamp=datetime.now().isoformat(),
            interaction_type=InteractionType.LIE,
            content=lie,
            discovered=False,
            metadata={"truth": what_is_true} if what_is_true else {},
        )
        log.interactions.append(interaction)

    def discover_lie(self, npc_name: str, lie_content: str) -> bool:
        """
        Mark that an NPC has discovered a lie.

        Args:
            npc_name: The NPC's name
            lie_content: Content to match against lie

        Returns:
            True if a matching lie was found and marked discovered
        """
        log = self._get_or_create_log(npc_name)

        for interaction in log.interactions:
            if (interaction.interaction_type == InteractionType.LIE
                and interaction.discovered is False
                and lie_content.lower() in interaction.content.lower()):
                interaction.discovered = True
                self._update_disposition(npc_name, -30, f"Discovered lie: {lie_content}")
                return True
        return False

    def log_favor(
        self,
        npc_name: str,
        favor: str,
        given_to_npc: bool = True,
    ) -> None:
        """
        Log a favor given or received.

        Args:
            npc_name: The NPC's name
            favor: Description of the favor
            given_to_npc: True if player helped NPC, False if NPC helped player
        """
        log = self._get_or_create_log(npc_name)

        interaction_type = InteractionType.HELP_GIVEN if given_to_npc else InteractionType.HELP_RECEIVED
        disposition_change = 15 if given_to_npc else 5

        interaction = NPCInteraction(
            timestamp=datetime.now().isoformat(),
            interaction_type=interaction_type,
            content=favor,
            disposition_change=disposition_change,
        )
        log.interactions.append(interaction)

        self._update_disposition(npc_name, disposition_change,
                                f"{'Helped' if given_to_npc else 'Received help'}: {favor}")

    def log_betrayal(
        self,
        npc_name: str,
        betrayal: str,
        by_player: bool = True,
    ) -> None:
        """
        Log a betrayal.

        Args:
            npc_name: The NPC's name
            betrayal: Description of the betrayal
            by_player: True if player betrayed NPC, False if NPC betrayed player
        """
        log = self._get_or_create_log(npc_name)

        disposition_change = -50 if by_player else -30

        interaction = NPCInteraction(
            timestamp=datetime.now().isoformat(),
            interaction_type=InteractionType.BETRAYAL,
            content=betrayal,
            disposition_change=disposition_change,
            metadata={"by_player": by_player},
        )
        log.interactions.append(interaction)

        self._update_disposition(npc_name, disposition_change,
                                f"Betrayal: {betrayal}")

    def _update_disposition(self, npc_name: str, change: int, reason: str) -> None:
        """Update NPC disposition in both tracker and SessionMemory."""
        log = self._get_or_create_log(npc_name)
        npc_id = self._get_npc_id(npc_name)

        # Update in SessionMemory
        if npc_id in self.memory.entities:
            entity = self.memory.entities[npc_id]
            old_disposition = entity.disposition
            entity.disposition = max(-100, min(100, entity.disposition + change))

            # Track in history
            log.disposition_history.append((
                datetime.now().isoformat(),
                entity.disposition,
                reason,
            ))

    def get_relationship_context(self, npc_name: str) -> Dict[str, Any]:
        """
        Get full relationship context for an NPC.

        Returns a dictionary with everything needed to generate
        contextual dialogue and reactions.

        Args:
            npc_name: The NPC's name

        Returns:
            Dictionary with relationship context
        """
        npc_id = self._get_npc_id(npc_name)
        log = self.logs.get(npc_id)

        if not log:
            return {
                "known": False,
                "first_meeting": True,
            }

        # Get entity from memory for current disposition
        entity = self.memory.entities.get(npc_id)
        current_disposition = entity.disposition if entity else 0

        # Get unfulfilled promises and undiscovered lies
        unfulfilled_promises = log.get_unfulfilled_promises()
        undiscovered_lies = log.get_undiscovered_lies()
        discovered_lies = log.get_discovered_lies()

        # Determine relationship status
        if current_disposition >= 50:
            status = "friendly"
        elif current_disposition >= 20:
            status = "warm"
        elif current_disposition >= -20:
            status = "neutral"
        elif current_disposition >= -50:
            status = "cold"
        else:
            status = "hostile"

        # Check for trust issues
        has_trust_issues = len(discovered_lies) > 0 or any(
            i.interaction_type == InteractionType.BETRAYAL
            for i in log.interactions
        )

        return {
            "known": True,
            "first_meeting": False,
            "times_met": log.times_met,
            "first_met": log.first_met,
            "disposition": current_disposition,
            "status": status,
            "has_trust_issues": has_trust_issues,
            "unfulfilled_promises": [p.content for p in unfulfilled_promises],
            "undiscovered_lies": len(undiscovered_lies),
            "discovered_lies": [l.content for l in discovered_lies],
            "known_topics": log.known_topics,
            "recent_interactions": [
                {"type": i.interaction_type.value, "content": i.content}
                for i in log.get_recent_interactions(3)
            ],
        }

    def generate_greeting_context(self, npc_name: str) -> str:
        """
        Generate context for how an NPC should greet the player.

        Args:
            npc_name: The NPC's name

        Returns:
            String describing how the NPC should react
        """
        context = self.get_relationship_context(npc_name)

        if not context["known"]:
            return "First meeting - NPC doesn't know the player"

        parts = []

        # Meeting frequency
        if context["times_met"] == 1:
            parts.append("Second meeting - NPC remembers player")
        elif context["times_met"] <= 3:
            parts.append(f"Has met {context['times_met']} times")
        else:
            parts.append("Well acquainted")

        # Disposition
        parts.append(f"Relationship: {context['status']}")

        # Trust issues
        if context["has_trust_issues"]:
            parts.append("Has reason not to trust player")

        # Unfulfilled promises
        if context["unfulfilled_promises"]:
            parts.append(f"Waiting on promise: {context['unfulfilled_promises'][0]}")

        return " | ".join(parts)

    def to_dict(self) -> dict:
        """Serialize tracker to dictionary."""
        return {
            "logs": {k: v.to_dict() for k, v in self.logs.items()}
        }

    @classmethod
    def from_dict(cls, data: dict, memory: "SessionMemory") -> "NPCMemoryTracker":
        """Deserialize tracker from dictionary."""
        tracker = cls(memory)
        for npc_id, log_data in data.get("logs", {}).items():
            tracker.logs[npc_id] = NPCConversationLog.from_dict(log_data)
        return tracker
