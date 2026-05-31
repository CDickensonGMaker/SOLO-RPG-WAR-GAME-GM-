"""Session state and persistence for solo RPG sessions."""

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Any


class Disposition(Enum):
    """NPC disposition toward the player."""
    ALLY = "ally"
    NEUTRAL = "neutral"
    ENEMY = "enemy"
    UNKNOWN = "unknown"


class ThreadStatus(Enum):
    """Status of a narrative thread."""
    ACTIVE = "active"
    RESOLVED = "resolved"


@dataclass
class Scene:
    """A scene in the session."""
    number: int
    description: str
    chaos_at_start: int

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "number": self.number,
            "description": self.description,
            "chaos_at_start": self.chaos_at_start
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Scene":
        """Create from dictionary."""
        return cls(
            number=data["number"],
            description=data["description"],
            chaos_at_start=data["chaos_at_start"]
        )


@dataclass
class TrackedNPC:
    """An NPC being tracked in the session."""
    name: str
    disposition: Disposition = Disposition.UNKNOWN

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "disposition": self.disposition.value
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TrackedNPC":
        """Create from dictionary."""
        return cls(
            name=data["name"],
            disposition=Disposition(data["disposition"])
        )


@dataclass
class Thread:
    """A narrative thread or plot hook."""
    description: str
    status: ThreadStatus = ThreadStatus.ACTIVE

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "description": self.description,
            "status": self.status.value
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Thread":
        """Create from dictionary."""
        return cls(
            description=data["description"],
            status=ThreadStatus(data["status"])
        )


@dataclass
class Note:
    """A session note or observation."""
    text: str
    timestamp: str
    scene_number: int

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "text": self.text,
            "timestamp": self.timestamp,
            "scene_number": self.scene_number
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Note":
        """Create from dictionary."""
        return cls(
            text=data["text"],
            timestamp=data["timestamp"],
            scene_number=data["scene_number"]
        )


@dataclass
class Session:
    """Complete session state."""
    mode: str
    setting: str
    mood: str
    scenes: list[Scene] = field(default_factory=list)
    npcs: list[TrackedNPC] = field(default_factory=list)
    threads: list[Thread] = field(default_factory=list)
    notes: list[Note] = field(default_factory=list)
    chaos: int = 5
    current_scene: int = 0
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        """Set timestamps if not provided."""
        now = datetime.now().isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "mode": self.mode,
            "setting": self.setting,
            "mood": self.mood,
            "scenes": [s.to_dict() for s in self.scenes],
            "npcs": [n.to_dict() for n in self.npcs],
            "threads": [t.to_dict() for t in self.threads],
            "notes": [n.to_dict() for n in self.notes],
            "chaos": self.chaos,
            "current_scene": self.current_scene,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Session":
        """Create from dictionary."""
        return cls(
            mode=data["mode"],
            setting=data["setting"],
            mood=data["mood"],
            scenes=[Scene.from_dict(s) for s in data.get("scenes", [])],
            npcs=[TrackedNPC.from_dict(n) for n in data.get("npcs", [])],
            threads=[Thread.from_dict(t) for t in data.get("threads", [])],
            notes=[Note.from_dict(n) for n in data.get("notes", [])],
            chaos=data.get("chaos", 5),
            current_scene=data.get("current_scene", 0),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", "")
        )


class SessionManager:
    """Manages session state and persistence."""

    def __init__(self):
        """Initialize session manager with no active session."""
        self._session: Optional[Session] = None

    @property
    def session(self) -> Optional[Session]:
        """Get current session."""
        return self._session

    @property
    def has_session(self) -> bool:
        """Check if a session is active."""
        return self._session is not None

    def new_session(self, mode: str, setting: str, mood: str = "neutral") -> Session:
        """
        Create a new session.

        Args:
            mode: Game mode (e.g., "solo", "gmless", "wargame")
            setting: Setting name (e.g., "fantasy", "scifi_military")
            mood: Initial mood state

        Returns:
            The new session
        """
        self._session = Session(
            mode=mode,
            setting=setting,
            mood=mood,
            chaos=5,
            current_scene=0
        )
        return self._session

    def _require_session(self) -> Session:
        """Ensure a session exists, raise if not."""
        if self._session is None:
            raise RuntimeError("No active session. Call new_session() first.")
        return self._session

    def _update_timestamp(self):
        """Update the session's updated_at timestamp."""
        if self._session:
            self._session.updated_at = datetime.now().isoformat()

    def add_scene(self, description: str) -> Scene:
        """
        Add a new scene to the session.

        Records the current chaos level at scene start and increments
        the scene counter.

        Args:
            description: Brief description of the scene

        Returns:
            The created scene
        """
        session = self._require_session()

        session.current_scene += 1
        scene = Scene(
            number=session.current_scene,
            description=description,
            chaos_at_start=session.chaos
        )
        session.scenes.append(scene)
        self._update_timestamp()

        return scene

    def add_npc(self, name: str, disposition: str = "unknown") -> TrackedNPC:
        """
        Add an NPC to track.

        Args:
            name: NPC's name
            disposition: One of "ally", "neutral", "enemy", "unknown"

        Returns:
            The tracked NPC
        """
        session = self._require_session()

        try:
            disp = Disposition(disposition.lower())
        except ValueError:
            disp = Disposition.UNKNOWN

        npc = TrackedNPC(name=name, disposition=disp)
        session.npcs.append(npc)
        self._update_timestamp()

        return npc

    def update_npc_disposition(self, name: str, disposition: str) -> Optional[TrackedNPC]:
        """
        Update an NPC's disposition.

        Args:
            name: NPC's name to find
            disposition: New disposition value

        Returns:
            The updated NPC or None if not found
        """
        session = self._require_session()

        for npc in session.npcs:
            if npc.name.lower() == name.lower():
                try:
                    npc.disposition = Disposition(disposition.lower())
                except ValueError:
                    npc.disposition = Disposition.UNKNOWN
                self._update_timestamp()
                return npc

        return None

    def add_thread(self, description: str) -> Thread:
        """
        Add a narrative thread.

        Args:
            description: Description of the thread/plot hook

        Returns:
            The created thread
        """
        session = self._require_session()

        thread = Thread(description=description)
        session.threads.append(thread)
        self._update_timestamp()

        return thread

    def resolve_thread(self, index: int) -> Optional[Thread]:
        """
        Mark a thread as resolved.

        Args:
            index: Zero-based index of the thread

        Returns:
            The resolved thread or None if index invalid
        """
        session = self._require_session()

        if 0 <= index < len(session.threads):
            session.threads[index].status = ThreadStatus.RESOLVED
            self._update_timestamp()
            return session.threads[index]

        return None

    def add_note(self, text: str) -> Note:
        """
        Add a session note.

        Args:
            text: Note text

        Returns:
            The created note
        """
        session = self._require_session()

        note = Note(
            text=text,
            timestamp=datetime.now().isoformat(),
            scene_number=session.current_scene
        )
        session.notes.append(note)
        self._update_timestamp()

        return note

    def adjust_chaos(self, delta: int) -> int:
        """
        Adjust chaos level.

        Args:
            delta: Amount to add (negative to decrease)

        Returns:
            New chaos level (clamped to 1-9)
        """
        session = self._require_session()

        session.chaos = max(1, min(9, session.chaos + delta))
        self._update_timestamp()

        return session.chaos

    def set_chaos(self, value: int) -> int:
        """
        Set chaos level directly.

        Args:
            value: New chaos level (will be clamped to 1-9)

        Returns:
            New chaos level
        """
        session = self._require_session()

        session.chaos = max(1, min(9, value))
        self._update_timestamp()

        return session.chaos

    def set_mood(self, mood: str) -> str:
        """
        Set the current mood.

        Args:
            mood: New mood state

        Returns:
            The new mood
        """
        session = self._require_session()

        session.mood = mood
        self._update_timestamp()

        return session.mood

    def save(self, filepath: str | Path) -> Path:
        """
        Save session to JSON file.

        Args:
            filepath: Path to save to

        Returns:
            Path where session was saved
        """
        session = self._require_session()
        self._update_timestamp()

        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(session.to_dict(), f, indent=2, ensure_ascii=False)

        return path

    def load(self, filepath: str | Path) -> Session:
        """
        Load session from JSON file.

        Args:
            filepath: Path to load from

        Returns:
            The loaded session
        """
        path = Path(filepath)

        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self._session = Session.from_dict(data)
        return self._session

    def render_journal(self) -> str:
        """
        Render the session as a formatted journal display.

        Returns:
            Formatted string representation of the session
        """
        session = self._require_session()

        lines = []
        width = 60

        # Header
        lines.append("=" * width)
        lines.append(f"{'SESSION JOURNAL':^{width}}")
        lines.append("=" * width)
        lines.append(f"Mode: {session.mode}  |  Setting: {session.setting}  |  Mood: {session.mood}")
        lines.append(f"Chaos: {session.chaos}  |  Current Scene: {session.current_scene}")
        lines.append("-" * width)

        # Scenes
        if session.scenes:
            lines.append("")
            lines.append("SCENES:")
            lines.append("-" * 30)
            for scene in session.scenes:
                lines.append(f"  [{scene.number}] {scene.description}")
                lines.append(f"      (Chaos at start: {scene.chaos_at_start})")

        # NPCs
        if session.npcs:
            lines.append("")
            lines.append("TRACKED NPCs:")
            lines.append("-" * 30)
            for npc in session.npcs:
                disp_icon = {
                    Disposition.ALLY: "+",
                    Disposition.NEUTRAL: "o",
                    Disposition.ENEMY: "-",
                    Disposition.UNKNOWN: "?"
                }.get(npc.disposition, "?")
                lines.append(f"  [{disp_icon}] {npc.name} ({npc.disposition.value})")

        # Threads
        if session.threads:
            lines.append("")
            lines.append("THREADS:")
            lines.append("-" * 30)
            for i, thread in enumerate(session.threads):
                status_icon = "x" if thread.status == ThreadStatus.RESOLVED else " "
                lines.append(f"  [{status_icon}] {i}: {thread.description}")

        # Notes
        if session.notes:
            lines.append("")
            lines.append("NOTES:")
            lines.append("-" * 30)
            for note in session.notes:
                scene_ref = f"[Scene {note.scene_number}]" if note.scene_number > 0 else "[Pre-session]"
                lines.append(f"  {scene_ref} {note.text}")

        lines.append("")
        lines.append("=" * width)

        return "\n".join(lines)


# Module-level manager instance
_manager = SessionManager()


def new_session(mode: str, setting: str, mood: str = "neutral") -> Session:
    """Create a new session using the default manager."""
    return _manager.new_session(mode, setting, mood)


def add_scene(description: str) -> Scene:
    """Add a scene using the default manager."""
    return _manager.add_scene(description)


def add_npc(name: str, disposition: str = "unknown") -> TrackedNPC:
    """Add an NPC using the default manager."""
    return _manager.add_npc(name, disposition)


def add_thread(description: str) -> Thread:
    """Add a thread using the default manager."""
    return _manager.add_thread(description)


def resolve_thread(index: int) -> Optional[Thread]:
    """Resolve a thread using the default manager."""
    return _manager.resolve_thread(index)


def add_note(text: str) -> Note:
    """Add a note using the default manager."""
    return _manager.add_note(text)


def save(filepath: str | Path) -> Path:
    """Save session using the default manager."""
    return _manager.save(filepath)


def load(filepath: str | Path) -> Session:
    """Load session using the default manager."""
    return _manager.load(filepath)


def render_journal() -> str:
    """Render journal using the default manager."""
    return _manager.render_journal()


def get_chaos() -> int:
    """Get current chaos level."""
    return _manager.session.chaos if _manager.session else 5


def set_chaos(value: int) -> int:
    """Set chaos level."""
    return _manager.set_chaos(value)


def chaos_up() -> int:
    """Increase chaos."""
    return _manager.adjust_chaos(1)


def chaos_down() -> int:
    """Decrease chaos."""
    return _manager.adjust_chaos(-1)
