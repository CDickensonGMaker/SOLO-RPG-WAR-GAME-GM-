"""
Session Memory - Tracks context for the GM to provide coherent responses.

The memory system maintains:
- Recent conversation history
- Active NPCs and their states
- Current scene/location
- Plot threads and their status
- Important facts established in the session
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
from collections import deque
import json


@dataclass
class MemoryEntry:
    """A single memory/conversation entry."""
    timestamp: str
    entry_type: str  # "user", "gm", "event", "roll", "note"
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "type": self.entry_type,
            "content": self.content,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MemoryEntry":
        return cls(
            timestamp=data.get("timestamp", ""),
            entry_type=data.get("type", "note"),
            content=data.get("content", ""),
            metadata=data.get("metadata", {})
        )


@dataclass
class TrackedEntity:
    """An NPC, location, or item being tracked."""
    name: str
    entity_type: str  # "npc", "location", "item", "faction"
    description: str = ""
    traits: List[str] = field(default_factory=list)
    status: str = "active"  # active, inactive, dead, destroyed
    disposition: int = 0  # -100 to 100 for NPCs
    notes: List[str] = field(default_factory=list)
    last_mentioned: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "type": self.entity_type,
            "description": self.description,
            "traits": self.traits,
            "status": self.status,
            "disposition": self.disposition,
            "notes": self.notes,
            "last_mentioned": self.last_mentioned
        }


@dataclass
class PlotThread:
    """A narrative thread being tracked."""
    name: str
    description: str
    status: str = "active"  # active, resolved, abandoned
    importance: int = 5  # 1-10
    related_entities: List[str] = field(default_factory=list)
    developments: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "status": self.status,
            "importance": self.importance,
            "related_entities": self.related_entities,
            "developments": self.developments
        }


class SessionMemory:
    """
    Maintains session context for the GM.

    Tracks conversation history, entities, plot threads, and
    established facts to provide coherent, contextual responses.
    """

    def __init__(self, max_history: int = 50):
        # Conversation history (limited size)
        self.history: deque = deque(maxlen=max_history)

        # Tracked entities
        self.entities: Dict[str, TrackedEntity] = {}

        # Plot threads
        self.threads: Dict[str, PlotThread] = {}

        # Established facts (things the GM should remember)
        self.facts: List[str] = []

        # Current scene context
        self.current_scene: Dict[str, Any] = {
            "location": "Unknown",
            "description": "",
            "mood": "neutral",
            "present_npcs": [],
            "time_of_day": "day",
            "weather": "clear"
        }

        # Session metadata
        self.session_start: str = datetime.now().isoformat()
        self.mode: str = "rpg"  # rpg, wargame, birthright
        self.setting: str = "fantasy"

        # Chaos and mood tracking
        self.chaos_factor: int = 5
        self.tension_level: int = 5

    def add_message(self, content: str, msg_type: str = "user",
                    metadata: Dict[str, Any] = None):
        """Add a message to history."""
        entry = MemoryEntry(
            timestamp=datetime.now().isoformat(),
            entry_type=msg_type,
            content=content,
            metadata=metadata or {}
        )
        self.history.append(entry)

        # Extract and track any mentioned entities
        self._extract_mentions(content)

    def add_gm_response(self, content: str, metadata: Dict[str, Any] = None):
        """Add a GM response to history."""
        self.add_message(content, "gm", metadata)

    def add_event(self, content: str, event_type: str = "narrative"):
        """Add a game event to history."""
        self.add_message(content, "event", {"event_type": event_type})

    def add_roll(self, roll_type: str, result: Any, interpretation: str = ""):
        """Add a roll result to history."""
        self.add_message(
            f"{roll_type}: {result}",
            "roll",
            {"roll_type": roll_type, "result": result, "interpretation": interpretation}
        )

    def _extract_mentions(self, text: str):
        """Extract entity mentions and update last_mentioned."""
        text_lower = text.lower()
        for entity_id, entity in self.entities.items():
            if entity.name.lower() in text_lower:
                entity.last_mentioned = datetime.now().isoformat()

    def track_entity(self, name: str, entity_type: str,
                     description: str = "", traits: List[str] = None,
                     disposition: int = 0) -> TrackedEntity:
        """Add or update a tracked entity."""
        entity_id = name.lower().replace(" ", "_")

        if entity_id in self.entities:
            # Update existing
            entity = self.entities[entity_id]
            if description:
                entity.description = description
            if traits:
                entity.traits = traits
            entity.disposition = disposition
        else:
            # Create new
            entity = TrackedEntity(
                name=name,
                entity_type=entity_type,
                description=description,
                traits=traits or [],
                disposition=disposition,
                last_mentioned=datetime.now().isoformat()
            )
            self.entities[entity_id] = entity

        return entity

    def get_entity(self, name: str) -> Optional[TrackedEntity]:
        """Get a tracked entity by name."""
        entity_id = name.lower().replace(" ", "_")
        return self.entities.get(entity_id)

    def add_thread(self, name: str, description: str,
                   importance: int = 5) -> PlotThread:
        """Add a plot thread."""
        thread_id = name.lower().replace(" ", "_")
        thread = PlotThread(
            name=name,
            description=description,
            importance=importance
        )
        self.threads[thread_id] = thread
        return thread

    def update_thread(self, name: str, development: str):
        """Add a development to a thread."""
        thread_id = name.lower().replace(" ", "_")
        if thread_id in self.threads:
            self.threads[thread_id].developments.append(development)

    def resolve_thread(self, name: str):
        """Mark a thread as resolved."""
        thread_id = name.lower().replace(" ", "_")
        if thread_id in self.threads:
            self.threads[thread_id].status = "resolved"

    def add_fact(self, fact: str):
        """Add an established fact."""
        if fact not in self.facts:
            self.facts.append(fact)

    def set_scene(self, location: str = None, description: str = None,
                  mood: str = None, npcs: List[str] = None,
                  time_of_day: str = None, weather: str = None):
        """Update the current scene."""
        if location:
            self.current_scene["location"] = location
        if description:
            self.current_scene["description"] = description
        if mood:
            self.current_scene["mood"] = mood
        if npcs is not None:
            self.current_scene["present_npcs"] = npcs
        if time_of_day:
            self.current_scene["time_of_day"] = time_of_day
        if weather:
            self.current_scene["weather"] = weather

    def get_recent_context(self, count: int = 10) -> List[MemoryEntry]:
        """Get recent conversation context."""
        return list(self.history)[-count:]

    def get_context_summary(self) -> str:
        """Get a summary of current context for GM processing."""
        summary_parts = []

        # Scene
        scene = self.current_scene
        summary_parts.append(
            f"Location: {scene['location']} ({scene['mood']} mood, {scene['time_of_day']}, {scene['weather']})"
        )

        # Present NPCs
        if scene["present_npcs"]:
            summary_parts.append(f"Present: {', '.join(scene['present_npcs'])}")

        # Active threads
        active_threads = [t for t in self.threads.values() if t.status == "active"]
        if active_threads:
            thread_names = [t.name for t in sorted(active_threads, key=lambda x: -x.importance)[:3]]
            summary_parts.append(f"Active plots: {', '.join(thread_names)}")

        # Chaos/tension
        summary_parts.append(f"Chaos: {self.chaos_factor}, Tension: {self.tension_level}")

        return " | ".join(summary_parts)

    def get_active_npcs(self) -> List[TrackedEntity]:
        """Get all active NPCs."""
        return [e for e in self.entities.values()
                if e.entity_type == "npc" and e.status == "active"]

    def get_active_threads(self) -> List[PlotThread]:
        """Get all active plot threads."""
        return [t for t in self.threads.values() if t.status == "active"]

    def to_dict(self) -> dict:
        """Serialize memory to dictionary."""
        return {
            "history": [e.to_dict() for e in self.history],
            "entities": {k: v.to_dict() for k, v in self.entities.items()},
            "threads": {k: v.to_dict() for k, v in self.threads.items()},
            "facts": self.facts,
            "current_scene": self.current_scene,
            "session_start": self.session_start,
            "mode": self.mode,
            "setting": self.setting,
            "chaos_factor": self.chaos_factor,
            "tension_level": self.tension_level
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SessionMemory":
        """Deserialize memory from dictionary."""
        memory = cls()

        # Restore history
        for entry_data in data.get("history", []):
            memory.history.append(MemoryEntry.from_dict(entry_data))

        # Restore entities
        for entity_id, entity_data in data.get("entities", {}).items():
            memory.entities[entity_id] = TrackedEntity(**entity_data)

        # Restore threads
        for thread_id, thread_data in data.get("threads", {}).items():
            memory.threads[thread_id] = PlotThread(**thread_data)

        memory.facts = data.get("facts", [])
        memory.current_scene = data.get("current_scene", memory.current_scene)
        memory.session_start = data.get("session_start", memory.session_start)
        memory.mode = data.get("mode", "rpg")
        memory.setting = data.get("setting", "fantasy")
        memory.chaos_factor = data.get("chaos_factor", 5)
        memory.tension_level = data.get("tension_level", 5)

        return memory

    def save(self, path: str):
        """Save memory to file."""
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: str) -> "SessionMemory":
        """Load memory from file."""
        with open(path, 'r') as f:
            return cls.from_dict(json.load(f))
