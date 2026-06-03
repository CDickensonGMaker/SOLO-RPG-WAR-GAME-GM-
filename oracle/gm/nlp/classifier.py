"""
Optional spaCy-Based Intent Classifier.

This is Layer 3 of the NLP system - enhanced NLP using spaCy.
Only available when spaCy is installed: pip install oracle[nlp]

Provides:
- Better entity extraction (handles typos, variations)
- Intent classification for ambiguous inputs
- Dependency parsing for complex sentences

This layer is OPTIONAL. Oracle works fine with just patterns.py.
"""

from typing import Dict, List, Optional, Tuple

# Check if spaCy is available
try:
    import spacy
    from spacy.tokens import Doc
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False
    spacy = None
    Doc = None


class SpacyIntentClassifier:
    """
    Enhanced intent classification using spaCy.

    Provides better natural language understanding for:
    - Ambiguous inputs that don't match simple patterns
    - Entity extraction with typo tolerance
    - Complex multi-part sentences

    Usage:
        # Check availability first
        if SPACY_AVAILABLE:
            classifier = SpacyIntentClassifier()
            entities = classifier.extract_entities("Ask Grimjaw about the artifact")
            # {'persons': ['Grimjaw'], 'locations': [], 'objects': ['artifact']}

    Requires:
        pip install oracle[nlp]
        python -m spacy download en_core_web_sm
    """

    def __init__(self, model_name: str = "en_core_web_sm"):
        """
        Initialize the classifier.

        Args:
            model_name: spaCy model to load. Options:
                - "en_core_web_sm" (default, ~12MB, fast)
                - "en_core_web_md" (~40MB, better vectors)
                - "en_core_web_lg" (~560MB, best accuracy)

        Raises:
            ImportError: If spaCy is not installed
            OSError: If the model is not downloaded
        """
        if not SPACY_AVAILABLE:
            raise ImportError(
                "spaCy is not installed. Install with: pip install oracle[nlp]\n"
                "Then download a model: python -m spacy download en_core_web_sm"
            )

        try:
            self.nlp = spacy.load(model_name)
        except OSError as e:
            raise OSError(
                f"spaCy model '{model_name}' not found. Download with:\n"
                f"python -m spacy download {model_name}"
            ) from e

        # Custom entity patterns for tabletop gaming
        self._add_custom_patterns()

    def _add_custom_patterns(self):
        """Add custom entity patterns for tabletop RPG context."""
        # spaCy's default NER doesn't know about fantasy terms
        # We could add a custom EntityRuler here if needed
        pass

    def extract_entities(self, text: str) -> Dict[str, List[str]]:
        """
        Extract named entities from text.

        Args:
            text: Input text to analyze

        Returns:
            Dict with entity categories:
            - persons: Character/NPC names
            - locations: Place names
            - objects: Items, artifacts
            - organizations: Factions, groups
        """
        doc = self.nlp(text)

        entities = {
            "persons": [],
            "locations": [],
            "objects": [],
            "organizations": [],
        }

        for ent in doc.ents:
            if ent.label_ == "PERSON":
                entities["persons"].append(ent.text)
            elif ent.label_ in ("GPE", "LOC", "FAC"):
                entities["locations"].append(ent.text)
            elif ent.label_ == "ORG":
                entities["organizations"].append(ent.text)
            elif ent.label_ in ("PRODUCT", "WORK_OF_ART"):
                entities["objects"].append(ent.text)

        # Also extract noun chunks as potential objects
        for chunk in doc.noun_chunks:
            # Skip if it's already captured
            if chunk.text.lower() not in [e.lower() for e in entities["persons"]]:
                if chunk.root.pos_ == "NOUN":
                    # Check if it might be an object/item
                    if any(word in chunk.text.lower() for word in
                           ["key", "sword", "weapon", "artifact", "item",
                            "potion", "scroll", "book", "ring", "amulet"]):
                        if chunk.text not in entities["objects"]:
                            entities["objects"].append(chunk.text)

        return entities

    def get_main_verb(self, text: str) -> Optional[str]:
        """
        Extract the main action verb from a sentence.

        Args:
            text: Input text

        Returns:
            The lemmatized main verb, or None if not found

        Example:
            get_main_verb("I want to search the room") -> "search"
        """
        doc = self.nlp(text)

        # Find the root verb
        for token in doc:
            if token.dep_ == "ROOT" and token.pos_ == "VERB":
                return token.lemma_

        # Fallback: find any verb
        for token in doc:
            if token.pos_ == "VERB":
                return token.lemma_

        return None

    def get_verb_object(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract verb and its direct object.

        Args:
            text: Input text

        Returns:
            Tuple of (verb_lemma, object_text)

        Example:
            get_verb_object("search the old chest") -> ("search", "the old chest")
        """
        doc = self.nlp(text)

        verb = None
        obj = None

        for token in doc:
            if token.dep_ == "ROOT" and token.pos_ == "VERB":
                verb = token.lemma_

                # Find direct object
                for child in token.children:
                    if child.dep_ in ("dobj", "pobj"):
                        # Get the full noun phrase
                        obj_span = doc[child.left_edge.i:child.right_edge.i + 1]
                        obj = obj_span.text
                        break

        return verb, obj

    def classify_intent(self, text: str) -> str:
        """
        Classify the intent of ambiguous text.

        Uses verb analysis and sentence structure to guess intent.
        Falls back to "generic" for truly ambiguous inputs.

        Args:
            text: Input text

        Returns:
            Intent category string
        """
        doc = self.nlp(text)

        # Get main verb
        main_verb = self.get_main_verb(text)

        if not main_verb:
            return "generic"

        # Map verbs to intents
        verb_intent_map = {
            # Talk
            "ask": "talk_to", "speak": "talk_to", "talk": "talk_to",
            "tell": "talk_to", "say": "talk_to", "greet": "talk_to",

            # Search
            "search": "search", "look": "search", "find": "search",
            "hunt": "search", "seek": "search",

            # Travel
            "go": "travel", "travel": "travel", "move": "travel",
            "walk": "travel", "run": "travel", "head": "travel",
            "enter": "travel", "leave": "travel",

            # Investigate
            "examine": "investigate", "investigate": "investigate",
            "inspect": "investigate", "study": "investigate",
            "analyze": "investigate", "check": "investigate",

            # Fight
            "attack": "fight", "fight": "fight", "kill": "fight",
            "hit": "fight", "strike": "fight", "shoot": "fight",

            # Use
            "use": "use", "activate": "use", "cast": "use",
            "apply": "use", "employ": "use",

            # Observe
            "watch": "observe", "observe": "observe", "hide": "observe",
            "sneak": "observe", "spy": "observe",

            # Rest
            "rest": "rest", "sleep": "rest", "camp": "rest",
            "wait": "rest", "recover": "rest",

            # Interact
            "open": "interact", "close": "interact", "take": "interact",
            "grab": "interact", "push": "interact", "pull": "interact",
        }

        return verb_intent_map.get(main_verb, "generic")

    def similarity(self, text1: str, text2: str) -> float:
        """
        Calculate semantic similarity between two texts.

        Requires a model with word vectors (md or lg).

        Args:
            text1: First text
            text2: Second text

        Returns:
            Similarity score 0.0-1.0
        """
        doc1 = self.nlp(text1)
        doc2 = self.nlp(text2)

        # Check if vectors are available
        if not doc1.has_vector or not doc2.has_vector:
            return 0.0

        return doc1.similarity(doc2)


def check_spacy_available() -> bool:
    """Check if spaCy and a model are available."""
    if not SPACY_AVAILABLE:
        return False

    try:
        spacy.load("en_core_web_sm")
        return True
    except OSError:
        return False


def get_spacy_status() -> str:
    """Get a human-readable status of spaCy availability."""
    if not SPACY_AVAILABLE:
        return "spaCy not installed. Install with: pip install oracle[nlp]"

    try:
        nlp = spacy.load("en_core_web_sm")
        return f"spaCy available: {nlp.meta['name']} v{nlp.meta['version']}"
    except OSError:
        return "spaCy installed but model missing. Run: python -m spacy download en_core_web_sm"
