"""
Game Master Intelligence System

A procedural AI Game Master that provides narrative responses,
interprets oracle results, and manages solo RPG sessions.

This module is shared between the Oracle GUI and Birthright Campaign Manager.

Components:
- GameMasterBrain: Central orchestrator for all GM functions
- SessionMemory: Tracks context (NPCs, scenes, threads, facts)
- NarrativeResponder: Template-based text generation
- EnhancedResponder: Fiction-aware responses with meaning tables and pacing
- GMPersonality: Tone, style, and voice configuration
- GMOrchestrator: Smart NLP-powered intent routing (via brain.orchestrator)

Enhanced Features:
- MeaningTableReader: Action + Subject combinations for oracle elaborations
- ComplicationGenerator: Fiction-aware complications referencing active NPCs/threads
- PacingEngine: Push/Pause/Pull beat tracking for dramatic rhythm
- NPCMemoryTracker: Relationship history with promises, lies, conversation topics

The brain supports two processing modes:
- brain.process_input(): Traditional substring-based detection
- brain.process_smart(): NLP intent recognition via orchestrator
"""

from oracle.gm.brain import GameMasterBrain, OracleResult, DiceResult
from oracle.gm.personality import GMPersonality, GMStyle, GMTone, PERSONALITIES
from oracle.gm.memory import SessionMemory, TrackedEntity, PlotThread, MemoryEntry
from oracle.gm.responder import NarrativeResponder
from oracle.gm.enhanced_responder import EnhancedResponder

__all__ = [
    # Core classes
    "GameMasterBrain",
    "GMPersonality",
    "GMStyle",
    "GMTone",
    "SessionMemory",
    "NarrativeResponder",
    "EnhancedResponder",
    # Data classes
    "OracleResult",
    "DiceResult",
    "TrackedEntity",
    "PlotThread",
    "MemoryEntry",
    # Presets
    "PERSONALITIES",
]

# Optional: Expose orchestrator for direct access
# (Usually accessed via brain.orchestrator property)
try:
    from oracle.gm.orchestrator import GMOrchestrator, OrchestrationResult
    __all__.extend(["GMOrchestrator", "OrchestrationResult"])
except ImportError:
    pass  # Orchestrator not available (shouldn't happen)

# Optional: Expose NLP components
try:
    from oracle.gm.nlp import PatternMatcher, Intent, EntityResolver
    __all__.extend(["PatternMatcher", "Intent", "EntityResolver"])
except ImportError:
    pass  # NLP not available (shouldn't happen)

# Optional: Expose enhancement systems
try:
    from oracle.gm.meaning import MeaningTableReader, MeaningRoll
    from oracle.gm.complication_generator import ComplicationGenerator, Complication
    from oracle.gm.pacing import PacingEngine, BeatType
    from oracle.gm.npc_memory import NPCMemoryTracker, NPCConversationLog
    __all__.extend([
        "MeaningTableReader", "MeaningRoll",
        "ComplicationGenerator", "Complication",
        "PacingEngine", "BeatType",
        "NPCMemoryTracker", "NPCConversationLog",
    ])
except ImportError:
    pass  # Enhancement systems not available
