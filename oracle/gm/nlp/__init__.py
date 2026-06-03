"""
Natural Language Processing for the Smart GM Brain.

This module provides:
- Pattern-based intent recognition (zero dependencies)
- Entity resolution against session memory
- Conversation context tracking (pronoun resolution)
- Domain-aware content routing
- NPC voice differentiation
- Optional spaCy-based classification (requires pip install oracle[nlp])

The NLP system is layered:
1. PatternMatcher - Fast regex-based intent detection (always available)
2. EntityResolver - Links references to tracked entities in memory
3. ConversationContext - Tracks pronouns and recent mentions
4. ContentRouter - Pulls content from domain-specific TOML tables
5. VoiceGenerator - Makes NPCs sound distinct based on traits
6. SpacyIntentClassifier - Enhanced NLP (optional, requires spaCy)
"""

from oracle.gm.nlp.patterns import PatternMatcher, Intent
from oracle.gm.nlp.resolver import EntityResolver
from oracle.gm.nlp.context import ConversationContext, ConversationTurn
from oracle.gm.nlp.content_router import ContentRouter
from oracle.gm.nlp.voice import VoiceGenerator, NPCVoice

__all__ = [
    # Core pattern matching
    "PatternMatcher",
    "Intent",
    # Entity resolution
    "EntityResolver",
    # Conversation context (Steps 8-10)
    "ConversationContext",
    "ConversationTurn",
    # Content routing (Step 11)
    "ContentRouter",
    # NPC voice (Step 12)
    "VoiceGenerator",
    "NPCVoice",
]

# Optional spaCy support - only import if available
try:
    from oracle.gm.nlp.classifier import SpacyIntentClassifier, SPACY_AVAILABLE
    __all__.extend(["SpacyIntentClassifier", "SPACY_AVAILABLE"])
except ImportError:
    SPACY_AVAILABLE = False
