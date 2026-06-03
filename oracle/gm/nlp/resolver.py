"""
Entity Resolver - Links references to tracked entities in session memory.

This is Layer 2 of the NLP system. After PatternMatcher extracts raw text
references like "the merchant" or "missing artifact", the EntityResolver
links them to actual TrackedEntity and PlotThread objects in memory.

This enables contextual responses:
- "the merchant" → Grimjaw the Fence (NPC, disposition -10)
- "the artifact" → linked to "Find the Relic" thread
- "here" → current scene location

Enhanced with pronoun resolution (Steps 9-10):
- "him" / "her" → last mentioned NPC
- "it" → last mentioned item or topic
- "there" → last mentioned location
"""

from typing import Optional, List, Tuple
from difflib import SequenceMatcher

from oracle.gm.memory import SessionMemory, TrackedEntity, PlotThread
from oracle.gm.nlp.patterns import Intent
from oracle.gm.nlp.context import ConversationContext


class EntityResolver:
    """
    Resolves entity references against session memory.

    Uses fuzzy matching and context to find the most likely entity
    when given a partial or informal reference.

    Enhanced with pronoun resolution to handle "him", "her", "it", etc.
    by tracking conversation context.

    Usage:
        resolver = EntityResolver(session_memory)
        npc = resolver.resolve_npc("the merchant")
        # Returns TrackedEntity for Grimjaw if he has "merchant" trait

        # With context:
        resolver.context.record_turn(...)  # After talking to Grimjaw
        resolved = resolver.resolve_pronoun("him")  # Returns "Grimjaw"
    """

    # Pronouns mapped to entity types (Step 9)
    PRONOUNS = {
        "he": "npc",
        "him": "npc",
        "his": "npc",
        "she": "npc",
        "her": "npc",
        "hers": "npc",
        "they": "npc",
        "them": "npc",
        "their": "npc",
        "it": "item",  # or current topic
        "its": "item",
        "that": None,  # contextual - could be anything
        "this": None,
        "there": "location",
        "here": "location",
    }

    def __init__(self, memory: SessionMemory):
        self.memory = memory
        self.context = ConversationContext()

        # Minimum similarity ratio for fuzzy matching
        self.min_similarity = 0.6

    def resolve_intent(self, intent: Intent) -> Intent:
        """
        Resolve all entity references in an Intent.

        Populates resolved_npc, resolved_location, resolved_thread
        fields based on intent target and context.

        Args:
            intent: The parsed Intent with raw target/topic strings

        Returns:
            The same Intent with resolved_* fields populated
        """
        # Try to resolve target as NPC
        if intent.target:
            npc = self.resolve_npc(intent.target)
            if npc:
                intent.resolved_npc = npc

            # If not an NPC, try as location
            if not npc:
                location = self.resolve_location(intent.target)
                if location:
                    intent.resolved_location = location

            # Also try as item
            item = self.resolve_item(intent.target)
            if item:
                intent.resolved_item = item

        # Try to resolve topic as thread
        if intent.topic:
            thread = self.resolve_thread(intent.topic)
            if thread:
                intent.resolved_thread = thread

            # Topic might also reference an NPC
            if not intent.resolved_npc:
                npc = self.resolve_npc(intent.topic)
                if npc:
                    intent.resolved_npc = npc

        # Handle extras (location, item from pattern)
        if "location" in intent.extras:
            location = self.resolve_location(intent.extras["location"])
            if location:
                intent.resolved_location = location

        if "item" in intent.extras:
            item = self.resolve_item(intent.extras["item"])
            if item:
                intent.resolved_item = item

        return intent

    def resolve_npc(self, reference: str) -> Optional[TrackedEntity]:
        """
        Resolve an NPC reference like 'the merchant' or 'Grimjaw'.

        Matching priority:
        1. Exact name match
        2. Partial name match (fuzzy)
        3. Trait/role match ("merchant", "guard")
        4. Present NPCs in current scene

        Args:
            reference: The NPC reference text

        Returns:
            TrackedEntity if found, None otherwise
        """
        if not reference:
            return None

        reference_lower = reference.lower().strip()

        # Remove common prefixes
        for prefix in ["the", "a", "an", "that", "this"]:
            if reference_lower.startswith(prefix + " "):
                reference_lower = reference_lower[len(prefix) + 1:]

        # 1. Exact name match
        for entity in self.memory.entities.values():
            if entity.entity_type == "npc" and entity.status == "active":
                if reference_lower == entity.name.lower():
                    return entity

        # 2. Partial name match (name contains reference or vice versa)
        for entity in self.memory.entities.values():
            if entity.entity_type == "npc" and entity.status == "active":
                name_lower = entity.name.lower()
                if reference_lower in name_lower or name_lower in reference_lower:
                    return entity

        # 3. Fuzzy name match
        best_match: Optional[TrackedEntity] = None
        best_ratio = 0.0

        for entity in self.memory.entities.values():
            if entity.entity_type == "npc" and entity.status == "active":
                ratio = SequenceMatcher(
                    None, reference_lower, entity.name.lower()
                ).ratio()

                if ratio > best_ratio and ratio >= self.min_similarity:
                    best_ratio = ratio
                    best_match = entity

        if best_match:
            return best_match

        # 4. Trait/role match
        for entity in self.memory.entities.values():
            if entity.entity_type == "npc" and entity.status == "active":
                # Check traits
                for trait in entity.traits:
                    if reference_lower in trait.lower():
                        return entity
                    if trait.lower() in reference_lower:
                        return entity

                # Check description
                if reference_lower in entity.description.lower():
                    return entity

        # 5. Present NPCs in current scene (last resort)
        present = self.memory.current_scene.get("present_npcs", [])
        for npc_name in present:
            if reference_lower in npc_name.lower():
                return self.memory.get_entity(npc_name)

        return None

    def resolve_location(self, reference: str) -> Optional[str]:
        """
        Resolve a location reference.

        Args:
            reference: Location reference text ("here", "the tavern", etc.)

        Returns:
            Location name string if resolved, None otherwise
        """
        if not reference:
            return None

        reference_lower = reference.lower().strip()

        # Remove common prefixes
        for prefix in ["the", "a", "an", "to", "into"]:
            if reference_lower.startswith(prefix + " "):
                reference_lower = reference_lower[len(prefix) + 1:]

        # Special references
        if reference_lower in ["here", "this place", "current location"]:
            return self.memory.current_scene.get("location", "Unknown")

        # Check if reference matches current location
        current = self.memory.current_scene.get("location", "")
        if current and reference_lower in current.lower():
            return current

        # Check tracked locations
        for entity in self.memory.entities.values():
            if entity.entity_type == "location":
                if reference_lower in entity.name.lower():
                    return entity.name
                if entity.name.lower() in reference_lower:
                    return entity.name

        # Return as-is for new location (travel to unknown places)
        return reference.strip()

    def resolve_thread(self, reference: str) -> Optional[PlotThread]:
        """
        Resolve a plot thread reference.

        Args:
            reference: Thread reference text

        Returns:
            PlotThread if found, None otherwise
        """
        if not reference:
            return None

        reference_lower = reference.lower().strip()

        # Check active threads
        for thread in self.memory.get_active_threads():
            # Name match
            if reference_lower in thread.name.lower():
                return thread
            if thread.name.lower() in reference_lower:
                return thread

            # Description match
            if reference_lower in thread.description.lower():
                return thread

        # Fuzzy matching on thread names
        best_match: Optional[PlotThread] = None
        best_ratio = 0.0

        for thread in self.memory.get_active_threads():
            ratio = SequenceMatcher(
                None, reference_lower, thread.name.lower()
            ).ratio()

            if ratio > best_ratio and ratio >= self.min_similarity:
                best_ratio = ratio
                best_match = thread

        return best_match

    def resolve_item(self, reference: str) -> Optional[TrackedEntity]:
        """
        Resolve an item reference.

        Args:
            reference: Item reference text

        Returns:
            TrackedEntity if found, None otherwise
        """
        if not reference:
            return None

        reference_lower = reference.lower().strip()

        # Remove common prefixes
        for prefix in ["the", "a", "an", "my", "your"]:
            if reference_lower.startswith(prefix + " "):
                reference_lower = reference_lower[len(prefix) + 1:]

        # Check tracked items
        for entity in self.memory.entities.values():
            if entity.entity_type == "item" and entity.status == "active":
                if reference_lower in entity.name.lower():
                    return entity
                if entity.name.lower() in reference_lower:
                    return entity

        return None

    def get_present_npcs(self) -> List[TrackedEntity]:
        """Get all NPCs present in the current scene."""
        present_names = self.memory.current_scene.get("present_npcs", [])
        npcs = []

        for name in present_names:
            entity = self.memory.get_entity(name)
            if entity and entity.entity_type == "npc":
                npcs.append(entity)

        return npcs

    def get_best_candidates(self, reference: str,
                            entity_type: str = "npc",
                            limit: int = 3) -> List[Tuple[TrackedEntity, float]]:
        """
        Get best matching entities with similarity scores.

        Useful for disambiguation when multiple entities could match.

        Args:
            reference: The reference text to match
            entity_type: Type filter ("npc", "location", "item")
            limit: Maximum results to return

        Returns:
            List of (entity, similarity_score) tuples, sorted by score
        """
        reference_lower = reference.lower().strip()
        candidates = []

        for entity in self.memory.entities.values():
            if entity.entity_type != entity_type:
                continue
            if entity.status != "active":
                continue

            # Calculate similarity
            name_ratio = SequenceMatcher(
                None, reference_lower, entity.name.lower()
            ).ratio()

            # Boost for exact substring match
            if reference_lower in entity.name.lower():
                name_ratio = max(name_ratio, 0.8)

            # Trait/description bonus
            trait_bonus = 0.0
            for trait in entity.traits:
                if reference_lower in trait.lower():
                    trait_bonus = 0.2
                    break

            if reference_lower in entity.description.lower():
                trait_bonus = max(trait_bonus, 0.15)

            total_score = name_ratio + trait_bonus
            candidates.append((entity, total_score))

        # Sort by score descending
        candidates.sort(key=lambda x: x[1], reverse=True)

        return candidates[:limit]

    # =========================================================================
    # Pronoun Resolution (Steps 9-10)
    # =========================================================================

    def resolve_pronoun(self, pronoun: str) -> Optional[str]:
        """
        Resolve a pronoun to a tracked entity using conversation context.

        Args:
            pronoun: The pronoun to resolve ("him", "it", "there", etc.)

        Returns:
            The resolved entity name, or None if cannot resolve
        """
        pronoun_lower = pronoun.lower().strip()

        # Check if it's a known pronoun
        if pronoun_lower not in self.PRONOUNS:
            return None

        entity_type = self.PRONOUNS[pronoun_lower]

        # Special cases
        if pronoun_lower == "here":
            return self.memory.current_scene.get("location")

        if pronoun_lower == "there":
            return self.context.get_last_target("location")

        # Get from context based on type
        return self.context.get_last_target(entity_type)

    def resolve_reference(self, reference: str) -> Optional[str]:
        """
        Resolve any reference - name, description, or pronoun.

        This is the unified entry point for resolution.

        Args:
            reference: The reference text (could be name, pronoun, etc.)

        Returns:
            Resolved entity name, or None if cannot resolve
        """
        if not reference:
            return None

        reference_lower = reference.lower().strip()

        # Check if it's a pronoun
        if reference_lower in self.PRONOUNS:
            return self.resolve_pronoun(reference)

        # Check for demonstrative references
        demonstratives = {
            "that thing": "item",
            "that person": "npc",
            "that place": "location",
            "that guy": "npc",
            "that woman": "npc",
            "that man": "npc",
        }
        if reference_lower in demonstratives:
            return self.context.get_last_target(demonstratives[reference_lower])

        # Try NPC resolution
        npc = self.resolve_npc(reference)
        if npc:
            return npc.name

        # Try location resolution
        location = self.resolve_location(reference)
        if location:
            return location

        # Try item resolution
        item = self.resolve_item(reference)
        if item:
            return item.name

        return reference  # Return as-is if can't resolve

    def is_pronoun(self, text: str) -> bool:
        """Check if text is a pronoun."""
        return text.lower().strip() in self.PRONOUNS

    def resolve_implicit_topic(self, topic: str) -> Optional[str]:
        """
        Resolve implicit topic references like "about it" or "from there".

        Args:
            topic: The topic text (might be "it", "that", etc.)

        Returns:
            Resolved topic, or the current conversation topic
        """
        topic_lower = topic.lower().strip()

        # Check for pronoun references
        if topic_lower in ["it", "that", "this", "them"]:
            return self.context.current_topic

        # Check for references to previous context
        if topic_lower in ["the same", "the same thing", "that topic"]:
            return self.context.current_topic

        return topic  # Return as-is
