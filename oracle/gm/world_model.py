"""
World Model - Persistent Entity Management for Oracle GM.

The WorldModel provides stable, queryable entities that persist across the session.
Instead of rolling random attributes every time someone asks "tell me about X",
the WorldModel:

1. Checks if an entity already exists in memory -> returns it
2. Checks if authored lore exists for the entity -> creates from lore
3. Rolls new procedural attributes ONCE -> stores and returns

This gives players consistent answers when asking about the same thing twice.

Usage:
    world_model = WorldModel(memory, content_router)

    # First call creates entity with rolled/authored attributes
    iron_gate = world_model.get_or_create_entity("Iron Gate", "location")

    # Second call returns the SAME entity with SAME attributes
    iron_gate_again = world_model.get_or_create_entity("Iron Gate", "location")
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, Optional, List, TYPE_CHECKING
from datetime import datetime
import random

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # Python < 3.11 fallback

if TYPE_CHECKING:
    from oracle.gm.memory import SessionMemory, TrackedEntity
    from oracle.gm.nlp.content_router import ContentRouter


class WorldModel:
    """
    Manages persistent world entities with stable attributes.

    The core principle: entities are instantiated ONCE with either authored
    or procedurally-generated attributes, then RETRIEVED on subsequent queries.

    This solves the problem of asking "tell me about X" and getting random
    oracle responses each time instead of consistent world information.
    """

    def __init__(self, memory: "SessionMemory", content_router: Optional["ContentRouter"] = None):
        """
        Initialize the WorldModel.

        Args:
            memory: SessionMemory instance for entity storage
            content_router: ContentRouter for TOML content (optional)
        """
        self.memory = memory
        self.content = content_router
        self._lore_cache: Dict[str, Dict] = {}

    def get_or_create_entity(
        self,
        name: str,
        entity_type: str,
        context: Optional[Dict[str, Any]] = None
    ) -> "TrackedEntity":
        """
        Get an existing entity or create a new one with stable attributes.

        This is the main entry point for the WorldModel. It ensures that
        asking about the same entity twice returns consistent information.

        Args:
            name: Entity name (e.g., "Iron Gate", "Captain Varn")
            entity_type: Type of entity ("location", "npc", "item", "faction")
            context: Optional context for generation (mood, scene, etc.)

        Returns:
            TrackedEntity with stable attributes
        """
        from oracle.gm.memory import TrackedEntity

        # Normalize entity ID
        entity_id = self._normalize_id(name)

        # 1. Check if entity already exists in memory
        if entity_id in self.memory.entities:
            entity = self.memory.entities[entity_id]
            entity.last_mentioned = datetime.now().isoformat()
            return entity

        # 2. Check for authored lore
        lore = self._load_authored_lore(name, entity_type)
        if lore:
            entity = self._create_from_lore(name, entity_type, lore)
        else:
            # 3. Roll new procedural entity
            entity = self._roll_new_entity(name, entity_type, context)

        # Store in memory
        self.memory.entities[entity_id] = entity

        return entity

    def _normalize_id(self, name: str) -> str:
        """Normalize entity name to ID format."""
        return name.lower().replace(" ", "_").replace("-", "_")

    def _load_authored_lore(self, name: str, entity_type: str) -> Optional[Dict]:
        """
        Check authored lore TOML files for this entity.

        Args:
            name: Entity name
            entity_type: Entity type (location, npc, item, faction)

        Returns:
            Lore dict if found, None otherwise
        """
        if not self.content:
            return None

        # Build lore path based on entity type
        # e.g., oracle/data/fantasy/lore/locations.toml
        setting = self.memory.setting
        entity_id = self._normalize_id(name)

        # Check cache first
        cache_key = f"{setting}/{entity_type}/{entity_id}"
        if cache_key in self._lore_cache:
            return self._lore_cache[cache_key]

        # Try to load lore file
        lore_path = self.content.data_root / setting / "lore" / f"{entity_type}s.toml"

        if not lore_path.exists():
            return None

        try:
            with open(lore_path, "rb") as f:
                lore_table = tomllib.load(f)

            # Look for this entity in the lore table
            # Structure: [locations.iron_gate] or [npcs.captain_varn]
            type_key = f"{entity_type}s"
            if type_key in lore_table:
                entity_lore = lore_table[type_key].get(entity_id)
                if entity_lore:
                    self._lore_cache[cache_key] = entity_lore
                    return entity_lore
        except Exception:
            pass

        return None

    def _create_from_lore(
        self,
        name: str,
        entity_type: str,
        lore: Dict
    ) -> "TrackedEntity":
        """
        Create an entity from authored lore data.

        Args:
            name: Entity name
            entity_type: Entity type
            lore: Lore dict from TOML

        Returns:
            TrackedEntity populated from lore
        """
        from oracle.gm.memory import TrackedEntity

        # Use name from lore if provided, otherwise use passed name
        entity_name = lore.get("name", name)

        # Build attributes from lore fields
        attributes = {}

        # Standard lore fields that go into attributes
        lore_fields = ["features", "hazards", "history", "secrets",
                       "inhabitants", "rumors", "connections", "inventory",
                       "motivations", "weaknesses", "strengths"]

        for field in lore_fields:
            if field in lore:
                attributes[field] = lore[field]

        # Create entity with lore data
        entity = TrackedEntity(
            name=entity_name,
            entity_type=entity_type,
            description=lore.get("description", ""),
            traits=lore.get("traits", []),
            disposition=lore.get("disposition", 0),
            last_mentioned=datetime.now().isoformat(),
            attributes=attributes,
            discovered=True,  # Authored lore is considered "known"
            revealed_attributes={"description"},  # Basic info revealed
            source="authored",
            lore_id=self._normalize_id(name)
        )

        return entity

    def _roll_new_entity(
        self,
        name: str,
        entity_type: str,
        context: Optional[Dict[str, Any]] = None
    ) -> "TrackedEntity":
        """
        Create a new entity with procedurally rolled attributes.

        Args:
            name: Entity name
            entity_type: Entity type
            context: Optional context for generation

        Returns:
            TrackedEntity with rolled attributes
        """
        from oracle.gm.memory import TrackedEntity

        context = context or {}
        mood = context.get("mood", "neutral")

        # Roll attributes based on entity type
        if entity_type == "location":
            attributes = self._roll_location_attributes(mood)
        elif entity_type == "npc":
            attributes = self._roll_npc_attributes(mood)
        elif entity_type == "item":
            attributes = self._roll_item_attributes()
        elif entity_type == "faction":
            attributes = self._roll_faction_attributes()
        else:
            attributes = {}

        # Generate basic description
        description = self._generate_description(name, entity_type, mood)

        # Roll traits
        traits = self._roll_traits(entity_type)

        entity = TrackedEntity(
            name=name,
            entity_type=entity_type,
            description=description,
            traits=traits,
            disposition=0 if entity_type != "npc" else random.randint(-30, 30),
            last_mentioned=datetime.now().isoformat(),
            attributes=attributes,
            discovered=False,  # Procedural entities start undiscovered
            revealed_attributes=set(),
            source="procedural",
            lore_id=None
        )

        return entity

    def _roll_location_attributes(self, mood: str = "neutral") -> Dict[str, Any]:
        """Roll attributes for a location entity."""
        attributes = {
            "danger_level": random.choice(["safe", "cautious", "dangerous", "deadly"]),
            "discoveries": [],  # Populated by search results
        }

        # Roll features based on mood
        if self.content:
            feature = self.content.pull_location_feature()
            if feature:
                attributes["features"] = [feature]
        else:
            features = [
                "Multiple entry points create tactical options",
                "Elevated positions offer advantages",
                "Narrow passages limit movement",
                "Open areas provide little cover",
                "Natural concealment available",
            ]
            attributes["features"] = [random.choice(features)]

        # Roll hazards
        hazard_chance = 0.3 if mood in ["dangerous", "hostile"] else 0.15
        if random.random() < hazard_chance:
            hazards = [
                "Predators hunt these grounds",
                "Unstable terrain threatens the unwary",
                "Environmental dangers lurk",
                "Hostile forces patrol the area",
                "Traps have been set here",
            ]
            attributes["hazards"] = [random.choice(hazards)]

        return attributes

    def _roll_npc_attributes(self, mood: str = "neutral") -> Dict[str, Any]:
        """Roll attributes for an NPC entity."""
        attributes = {
            "knowledge_topics": [],  # What they know about
            "secrets": [],
            "relationships": {},
        }

        # Roll what topics they might know about
        topic_count = random.randint(1, 3)
        topics = [
            "local rumors", "recent events", "nearby dangers",
            "trade opportunities", "political intrigue", "hidden paths",
            "ancient history", "local customs", "useful contacts"
        ]
        attributes["knowledge_topics"] = random.sample(topics, min(topic_count, len(topics)))

        # Chance of having a secret
        if random.random() < 0.4:
            if self.content:
                secret = self.content.pull_npc_secret()
                if secret:
                    attributes["secrets"] = [secret]
            else:
                secrets = [
                    "Has a hidden agenda",
                    "Knows more than they reveal",
                    "Has a dark past",
                    "Is not who they claim to be",
                ]
                attributes["secrets"] = [random.choice(secrets)]

        return attributes

    def _roll_item_attributes(self) -> Dict[str, Any]:
        """Roll attributes for an item entity."""
        return {
            "condition": random.choice(["pristine", "good", "worn", "damaged", "ruined"]),
            "value": random.choice(["worthless", "common", "valuable", "rare", "priceless"]),
            "history": [],
        }

    def _roll_faction_attributes(self) -> Dict[str, Any]:
        """Roll attributes for a faction entity."""
        return {
            "power_level": random.choice(["minor", "moderate", "major", "dominant"]),
            "disposition_to_player": random.randint(-50, 50),
            "goals": [],
            "rivals": [],
            "allies": [],
        }

    def _generate_description(self, name: str, entity_type: str, mood: str) -> str:
        """Generate a basic description for a new entity."""
        if entity_type == "location":
            templates = [
                f"{name} - a place where travelers may find respite or danger",
                f"This is {name}, a notable location in the region",
                f"{name} awaits, its nature not yet fully understood",
            ]
        elif entity_type == "npc":
            templates = [
                f"{name}, a figure whose true nature remains to be revealed",
                f"This is {name}, encountered in your travels",
                f"{name} stands before you, their intentions unclear",
            ]
        elif entity_type == "item":
            templates = [
                f"{name}, an item of uncertain provenance",
                f"This is {name}, its full properties unknown",
                f"{name} catches your attention",
            ]
        else:
            templates = [
                f"{name} - more information may be discovered",
            ]

        return random.choice(templates)

    def _roll_traits(self, entity_type: str) -> List[str]:
        """Roll traits for an entity based on type."""
        trait_count = random.randint(1, 3)

        if entity_type == "location":
            traits = [
                "remote", "well-traveled", "ancient", "forgotten",
                "contested", "sacred", "dangerous", "mysterious",
            ]
        elif entity_type == "npc":
            if self.content:
                traits = []
                for _ in range(trait_count):
                    trait = self.content.pull_npc_trait()
                    if trait:
                        traits.append(trait)
                if traits:
                    return traits
            traits = [
                "cautious", "friendly", "suspicious", "helpful",
                "greedy", "honest", "secretive", "talkative",
            ]
        elif entity_type == "item":
            traits = [
                "well-crafted", "ancient", "ornate", "practical",
                "mysterious", "damaged", "valuable", "common",
            ]
        else:
            traits = ["notable", "significant", "obscure"]

        return random.sample(traits, min(trait_count, len(traits)))

    def update_entity(self, entity_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update an entity's attributes.

        Args:
            entity_id: Entity ID
            updates: Dict of updates to apply

        Returns:
            True if entity was updated, False if not found
        """
        normalized_id = self._normalize_id(entity_id)

        if normalized_id not in self.memory.entities:
            return False

        entity = self.memory.entities[normalized_id]

        # Apply updates
        for key, value in updates.items():
            if key == "status":
                entity.status = value
            elif key == "disposition":
                entity.disposition = value
            elif key == "discovered":
                entity.discovered = value
            elif key in entity.attributes:
                entity.attributes[key] = value
            else:
                entity.attributes[key] = value

        entity.last_mentioned = datetime.now().isoformat()
        return True

    def reveal_attribute(self, entity_id: str, attribute: str) -> bool:
        """
        Mark an attribute as revealed to the player.

        Args:
            entity_id: Entity ID
            attribute: Attribute name to reveal

        Returns:
            True if revealed, False if entity not found
        """
        normalized_id = self._normalize_id(entity_id)

        if normalized_id not in self.memory.entities:
            return False

        entity = self.memory.entities[normalized_id]
        entity.revealed_attributes.add(attribute)
        return True

    def add_discovery(self, entity_id: str, discovery: str) -> bool:
        """
        Add a discovery to a location entity.

        Args:
            entity_id: Entity ID (usually a location)
            discovery: Discovery text to add

        Returns:
            True if added, False if entity not found
        """
        normalized_id = self._normalize_id(entity_id)

        if normalized_id not in self.memory.entities:
            return False

        entity = self.memory.entities[normalized_id]

        if "discoveries" not in entity.attributes:
            entity.attributes["discoveries"] = []

        entity.attributes["discoveries"].append(discovery)
        return True

    def get_known_info(self, entity_id: str) -> Dict[str, Any]:
        """
        Get the known/revealed information about an entity.

        Only returns attributes that have been revealed to the player.

        Args:
            entity_id: Entity ID

        Returns:
            Dict of known information, empty if not found
        """
        normalized_id = self._normalize_id(entity_id)

        if normalized_id not in self.memory.entities:
            return {}

        entity = self.memory.entities[normalized_id]

        known = {
            "name": entity.name,
            "type": entity.entity_type,
        }

        # Add description if revealed
        if "description" in entity.revealed_attributes:
            known["description"] = entity.description

        # Add traits if revealed
        if "traits" in entity.revealed_attributes:
            known["traits"] = entity.traits

        # Add revealed attributes
        for attr in entity.revealed_attributes:
            if attr in entity.attributes:
                known[attr] = entity.attributes[attr]

        # Add discoveries (always visible once found)
        if "discoveries" in entity.attributes and entity.attributes["discoveries"]:
            known["discoveries"] = entity.attributes["discoveries"]

        return known
