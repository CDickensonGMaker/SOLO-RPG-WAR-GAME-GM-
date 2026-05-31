"""
Relationship Controller - Manages NPC relationships and graph visualization.

Handles:
- NPC relationship tracking
- Relationship graph generation for visualization
- Disposition calculations
- Alliance and rivalry networks
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from oracle.gui.models.campaign import (
    CampaignState, Relationship, RelationshipType
)


class RelationshipEdge(Enum):
    """Types of relationships for graph edges."""
    ALLIANCE = "alliance"
    RIVALRY = "rivalry"
    NEUTRAL = "neutral"
    PLAYER = "player"


@dataclass
class NPCNode:
    """Node in the relationship graph."""
    id: str
    name: str
    title: str
    disposition: int
    relationship_type: RelationshipType
    known: bool
    met: bool
    position: Tuple[float, float] = (0, 0)
    color: Tuple[float, float, float, float] = (0.5, 0.5, 0.5, 1.0)


@dataclass
class RelationshipEdgeData:
    """Edge data for relationship graph."""
    source: str
    target: str
    edge_type: RelationshipEdge
    weight: float
    color: Tuple[float, float, float, float]


class RelationshipController:
    """
    Manages NPC relationships and provides data for visualization.

    The relationship system tracks how NPCs feel about the player
    and each other, enabling complex political dynamics.
    """

    def __init__(self, campaign_state: CampaignState):
        self.campaign = campaign_state

        # NPC-to-NPC relationships (loaded from campaign data)
        self._npc_relationships: Dict[str, Dict[str, int]] = {}

        # Position cache for graph layout
        self._node_positions: Dict[str, Tuple[float, float]] = {}

    def get_player_relationships(self) -> List[Relationship]:
        """Get all relationships with the player."""
        return list(self.campaign.relationships.values())

    def get_relationship(self, npc_id: str) -> Optional[Relationship]:
        """Get specific NPC relationship."""
        return self.campaign.relationships.get(npc_id)

    def modify_relationship(self, npc_id: str, amount: int,
                           reason: str = "") -> bool:
        """Modify an NPC's disposition toward the player."""
        rel = self.campaign.relationships.get(npc_id)
        if rel:
            rel.modify(amount, reason)
            return True
        return False

    def get_allies(self) -> List[Relationship]:
        """Get NPCs with positive disposition."""
        return [
            r for r in self.campaign.relationships.values()
            if r.disposition > 20 and r.known
        ]

    def get_enemies(self) -> List[Relationship]:
        """Get NPCs with negative disposition."""
        return [
            r for r in self.campaign.relationships.values()
            if r.disposition < -20 and r.known
        ]

    def get_neutral(self) -> List[Relationship]:
        """Get NPCs with neutral disposition."""
        return [
            r for r in self.campaign.relationships.values()
            if -20 <= r.disposition <= 20 and r.known
        ]

    def get_relationship_color(self, disposition: int) -> Tuple[float, float, float, float]:
        """Get color based on disposition value."""
        if disposition >= 40:
            return (0.2, 0.8, 0.2, 1.0)  # Green - Devoted
        elif disposition >= 20:
            return (0.4, 0.7, 0.4, 1.0)  # Light Green - Ally
        elif disposition > 0:
            return (0.6, 0.8, 0.6, 1.0)  # Pale Green - Friendly
        elif disposition == 0:
            return (0.6, 0.6, 0.6, 1.0)  # Gray - Neutral
        elif disposition > -20:
            return (0.8, 0.6, 0.6, 1.0)  # Pale Red - Unfriendly
        elif disposition > -40:
            return (0.8, 0.4, 0.4, 1.0)  # Light Red - Hostile
        else:
            return (0.8, 0.2, 0.2, 1.0)  # Red - Enemy

    def build_graph_data(self) -> Dict[str, Any]:
        """
        Build data structure for relationship graph visualization.

        Returns a dictionary with nodes and edges for rendering.
        """
        nodes = []
        edges = []

        # Player node at center
        nodes.append(NPCNode(
            id="player",
            name=self.campaign.character_name,
            title="Regent",
            disposition=0,
            relationship_type=RelationshipType.NEUTRAL,
            known=True,
            met=True,
            position=(0.5, 0.5),
            color=(0.7, 0.5, 0.2, 1.0)  # Gold for player
        ))

        # NPC nodes arranged in a circle around player
        relationships = list(self.campaign.relationships.values())
        n = len(relationships)

        import math
        for i, rel in enumerate(relationships):
            angle = 2 * math.pi * i / max(n, 1)
            radius = 0.35

            # Position in normalized coordinates (0-1)
            x = 0.5 + radius * math.cos(angle)
            y = 0.5 + radius * math.sin(angle)

            nodes.append(NPCNode(
                id=rel.npc_id,
                name=rel.npc_name,
                title="",
                disposition=rel.disposition,
                relationship_type=rel.relationship_type,
                known=rel.known,
                met=rel.met,
                position=(x, y),
                color=self.get_relationship_color(rel.disposition)
            ))

            # Edge to player
            edge_type = RelationshipEdge.NEUTRAL
            if rel.disposition > 20:
                edge_type = RelationshipEdge.ALLIANCE
            elif rel.disposition < -20:
                edge_type = RelationshipEdge.RIVALRY

            edges.append(RelationshipEdgeData(
                source="player",
                target=rel.npc_id,
                edge_type=edge_type,
                weight=abs(rel.disposition) / 100.0,
                color=self.get_relationship_color(rel.disposition)
            ))

        # Add NPC-to-NPC edges if we have that data
        for source_id, targets in self._npc_relationships.items():
            for target_id, disposition in targets.items():
                if source_id in [n.id for n in nodes] and target_id in [n.id for n in nodes]:
                    edge_type = RelationshipEdge.NEUTRAL
                    if disposition > 20:
                        edge_type = RelationshipEdge.ALLIANCE
                    elif disposition < -20:
                        edge_type = RelationshipEdge.RIVALRY

                    edges.append(RelationshipEdgeData(
                        source=source_id,
                        target=target_id,
                        edge_type=edge_type,
                        weight=abs(disposition) / 100.0,
                        color=self.get_relationship_color(disposition)
                    ))

        return {
            "nodes": nodes,
            "edges": edges
        }

    def format_relationship_for_display(self, rel: Relationship) -> Dict[str, Any]:
        """Format relationship for GUI display."""
        return {
            "npc_id": rel.npc_id,
            "npc_name": rel.npc_name,
            "disposition": rel.disposition,
            "disposition_bar": (rel.disposition + 100) / 200.0,  # 0-1 range
            "type": rel.relationship_type.value,
            "type_label": rel.relationship_type.value.replace("_", " ").title(),
            "color": self.get_relationship_color(rel.disposition),
            "known": rel.known,
            "met": rel.met,
            "recent_notes": rel.notes[-3:] if rel.notes else []
        }

    def get_disposition_description(self, disposition: int) -> str:
        """Get textual description of disposition level."""
        if disposition >= 80:
            return "Utterly devoted to your cause"
        elif disposition >= 60:
            return "A true and loyal ally"
        elif disposition >= 40:
            return "Strongly supportive"
        elif disposition >= 20:
            return "Friendly and cooperative"
        elif disposition > 0:
            return "Somewhat positively inclined"
        elif disposition == 0:
            return "Completely neutral"
        elif disposition > -20:
            return "Somewhat negatively inclined"
        elif disposition > -40:
            return "Openly unfriendly"
        elif disposition > -60:
            return "Hostile and opposed"
        elif disposition > -80:
            return "A bitter enemy"
        else:
            return "Implacable hatred"

    def get_relationship_summary(self) -> Dict[str, int]:
        """Get summary counts of relationship types."""
        summary = {
            "devoted": 0,
            "ally": 0,
            "friendly": 0,
            "neutral": 0,
            "unfriendly": 0,
            "hostile": 0,
            "enemy": 0
        }

        for rel in self.campaign.relationships.values():
            if not rel.known:
                continue

            if rel.disposition >= 40:
                summary["devoted"] += 1
            elif rel.disposition >= 20:
                summary["ally"] += 1
            elif rel.disposition > 0:
                summary["friendly"] += 1
            elif rel.disposition == 0:
                summary["neutral"] += 1
            elif rel.disposition > -20:
                summary["unfriendly"] += 1
            elif rel.disposition > -40:
                summary["hostile"] += 1
            else:
                summary["enemy"] += 1

        return summary
