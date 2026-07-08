"""
Game State - Global state management for the Birthright Campaign Manager.

Coordinates between campaigns, tracks world state, and manages save/load.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from pathlib import Path
import json
import tomllib
from datetime import datetime

from oracle.gui.models.campaign import CampaignState, Relationship
from oracle.gui.config import CAMPAIGNS_PATH, SAVES_PATH, DATA_PATH


@dataclass
class WorldState:
    """Global world state tracked across campaigns."""

    # Political state
    iron_throne_status: str = "vacant"
    anuire_unity: int = 30
    temple_schism_resolved: bool = False

    # Military state
    gorgon_threat_level: int = 60
    awnshegh_coordination: int = 20
    total_war_active: bool = False

    # Magical state
    mebhaighl_health: int = 100
    magian_status: str = "bound"
    corruption_spread: int = 0

    # Espionage state
    spider_network_strength: int = 80
    spider_identity_known: bool = False

    # Alliance state
    cerilian_alliance_formed: bool = False
    alliance_members: List[str] = field(default_factory=list)
    alliance_cohesion: int = 0

    # Divine state
    bloodline_awakening_widespread: bool = False
    ascension_imminent: bool = False
    new_god_risen: bool = False

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorldState":
        """Create from dictionary."""
        state = cls()
        for key, value in data.items():
            if hasattr(state, key):
                setattr(state, key, value)
        return state

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "iron_throne_status": self.iron_throne_status,
            "anuire_unity": self.anuire_unity,
            "temple_schism_resolved": self.temple_schism_resolved,
            "gorgon_threat_level": self.gorgon_threat_level,
            "awnshegh_coordination": self.awnshegh_coordination,
            "total_war_active": self.total_war_active,
            "mebhaighl_health": self.mebhaighl_health,
            "magian_status": self.magian_status,
            "corruption_spread": self.corruption_spread,
            "spider_network_strength": self.spider_network_strength,
            "spider_identity_known": self.spider_identity_known,
            "cerilian_alliance_formed": self.cerilian_alliance_formed,
            "alliance_members": self.alliance_members,
            "alliance_cohesion": self.alliance_cohesion,
            "bloodline_awakening_widespread": self.bloodline_awakening_widespread,
            "ascension_imminent": self.ascension_imminent,
            "new_god_risen": self.new_god_risen,
        }


@dataclass
class PlayerLegacy:
    """Player state that persists across campaigns."""
    character_name: str = ""
    bloodline_derivation: str = ""
    bloodline_score: int = 0
    titles: List[str] = field(default_factory=list)
    achievements: List[str] = field(default_factory=list)
    completed_campaigns: List[str] = field(default_factory=list)
    legendary_items: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlayerLegacy":
        """Create from dictionary."""
        return cls(
            character_name=data.get("character_name", ""),
            bloodline_derivation=data.get("bloodline_derivation", ""),
            bloodline_score=data.get("bloodline_score", 0),
            titles=data.get("titles", []),
            achievements=data.get("achievements", []),
            completed_campaigns=data.get("completed_campaigns", []),
            legendary_items=data.get("legendary_items", [])
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "character_name": self.character_name,
            "bloodline_derivation": self.bloodline_derivation,
            "bloodline_score": self.bloodline_score,
            "titles": self.titles,
            "achievements": self.achievements,
            "completed_campaigns": self.completed_campaigns,
            "legendary_items": self.legendary_items
        }


@dataclass
class CampaignInfo:
    """Metadata about an available campaign."""
    id: str
    name: str
    tagline: str
    theme: str
    difficulty: str
    description_short: str
    description_long: str
    recommended_bloodlines: List[str]
    prerequisites: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_toml(cls, campaign_id: str, data: Dict[str, Any]) -> "CampaignInfo":
        """Create from campaign TOML data."""
        campaign = data.get("campaign", {})
        desc = campaign.get("description", {})

        return cls(
            id=campaign_id,
            name=campaign.get("name", campaign_id),
            tagline=campaign.get("tagline", ""),
            theme=campaign.get("theme", ""),
            difficulty=campaign.get("difficulty", "standard"),
            description_short=desc.get("short", ""),
            description_long=desc.get("long", ""),
            recommended_bloodlines=campaign.get("recommended_bloodline", []),
            prerequisites=data.get("campaign_graph", {}).get("prerequisites", {}).get(campaign_id, {})
        )


class GameState:
    """
    Central game state manager.

    Handles:
    - Loading campaign definitions
    - Managing active campaign state
    - Tracking world state
    - Save/load operations
    """

    def __init__(self):
        self.world_state = WorldState()
        self.player_legacy = PlayerLegacy()
        self.active_campaign: Optional[CampaignState] = None
        self.available_campaigns: Dict[str, CampaignInfo] = {}
        self.npc_persistent_state: Dict[str, Dict[str, Any]] = {}
        self.last_error: Optional[str] = None  # readable reason for last failed save/load

        # Load campaign definitions
        self._load_campaign_definitions()

    def _load_campaign_definitions(self):
        """Load all campaign TOML files."""
        campaign_files = [
            "iron_throne.toml",
            "gorgons_shadow.toml",
            "web_of_shadows.toml",
            "sources_of_power.toml",
            "cerilian_alliance.toml",
            "chosen_bloodline.toml"
        ]

        for filename in campaign_files:
            path = CAMPAIGNS_PATH / filename
            if path.exists():
                try:
                    with open(path, "rb") as f:
                        data = tomllib.load(f)
                    campaign_id = filename.replace(".toml", "")
                    self.available_campaigns[campaign_id] = CampaignInfo.from_toml(
                        campaign_id, data
                    )
                except tomllib.TOMLDecodeError as e:
                    print(f"Error loading {filename}: {e}")

    def get_unlocked_campaigns(self) -> List[CampaignInfo]:
        """Get campaigns the player can start based on prerequisites."""
        unlocked = []
        completed = set(self.player_legacy.completed_campaigns)

        for campaign_id, info in self.available_campaigns.items():
            if campaign_id in completed:
                continue

            prereqs = info.prerequisites
            if not prereqs:
                # No prerequisites, always available
                unlocked.append(info)
            elif "requires_any" in prereqs:
                # Need any one of these
                if any(c in completed for c in prereqs["requires_any"]):
                    unlocked.append(info)
            elif "requires_count" in prereqs:
                # Need N campaigns from the list
                count = prereqs["requires_count"]
                from_list = prereqs.get("from", [])
                if len(completed.intersection(from_list)) >= count:
                    unlocked.append(info)

        return unlocked

    def start_campaign(self, campaign_id: str, character_id: str,
                       character_name: str) -> Optional[CampaignState]:
        """Start a new campaign."""
        if campaign_id not in self.available_campaigns:
            return None

        info = self.available_campaigns[campaign_id]

        # Load campaign data for starting parameters
        path = CAMPAIGNS_PATH / f"{campaign_id}.toml"
        try:
            with open(path, "rb") as f:
                data = tomllib.load(f)
        except (IOError, tomllib.TOMLDecodeError):
            return None

        campaign = data.get("campaign", {})
        starting_year = campaign.get("starting_year", 551)
        starting_season = campaign.get("starting_season", "spring")

        # Create campaign state
        state = CampaignState.new_campaign(
            campaign_id=campaign_id,
            campaign_name=info.name,
            character_id=character_id,
            character_name=character_name,
            starting_year=starting_year,
            starting_season=starting_season
        )

        # Initialize tracking variables from campaign definition
        if "tracking" in data:
            tracking = data["tracking"]
            variables = tracking.get("variables", [])
            for var in variables:
                state.variables[var] = 0

            # Apply starting state from act 1
            acts = data.get("acts", {})
            if "act_1" in acts and "starting_state" in acts["act_1"]:
                for key, value in acts["act_1"]["starting_state"].items():
                    state.variables[key] = value

        # Initialize NPC relationships
        npcs = data.get("npcs", {})
        for npc_id, npc_data in npcs.items():
            disposition = npc_data.get("disposition_base", 0)

            # Check for persistent state from previous campaigns
            if npc_id in self.npc_persistent_state:
                persistent = self.npc_persistent_state[npc_id]
                if "disposition" in persistent:
                    # Blend persistent and base disposition
                    carry = 0.8  # 80% carry from previous
                    disposition = int(
                        persistent["disposition"] * carry +
                        disposition * (1 - carry)
                    )

            state.relationships[npc_id] = Relationship(
                npc_id=npc_id,
                npc_name=npc_data.get("name", npc_id),
                disposition=disposition,
                known=True,
                met=False
            )

        # Load initial events
        events = data.get("events", {})
        from oracle.gui.models.campaign import DomainEvent
        for event_id, event_data in events.items():
            event = DomainEvent.from_dict(event_id, event_data)
            state.add_event(event)

        # Set as active
        self.active_campaign = state

        # Update player legacy
        if character_name and not self.player_legacy.character_name:
            self.player_legacy.character_name = character_name

        return state

    def complete_campaign(self, victory_type: str):
        """Record campaign completion."""
        if not self.active_campaign:
            return

        campaign_id = self.active_campaign.campaign_id
        self.active_campaign.victory_achieved = victory_type

        # Update player legacy
        if campaign_id not in self.player_legacy.completed_campaigns:
            self.player_legacy.completed_campaigns.append(campaign_id)

        # Persist NPC states
        for npc_id, rel in self.active_campaign.relationships.items():
            if npc_id not in self.npc_persistent_state:
                self.npc_persistent_state[npc_id] = {}
            self.npc_persistent_state[npc_id]["disposition"] = rel.disposition

        # Apply world state changes based on victory type
        self._apply_campaign_outcome(campaign_id, victory_type)

    def _apply_campaign_outcome(self, campaign_id: str, victory_type: str):
        """Apply world state changes from campaign outcome."""
        # These match the triggers defined in connections.toml
        if campaign_id == "iron_throne":
            if victory_type == "claim_throne":
                self.world_state.iron_throne_status = "claimed_player"
                self.world_state.anuire_unity += 30
            elif "avan" in victory_type:
                self.world_state.iron_throne_status = "claimed_avan"

        elif campaign_id == "gorgons_shadow":
            if victory_type in ["gorgon_slain", "gorgon_driven_back"]:
                self.world_state.gorgon_threat_level -= 40
            elif victory_type == "conquest":
                self.world_state.gorgon_threat_level = 100

        elif campaign_id == "web_of_shadows":
            if victory_type == "spider_destroyed":
                self.world_state.spider_network_strength = 0
            elif victory_type == "spider_exposed":
                self.world_state.spider_identity_known = True
                self.world_state.spider_network_strength -= 50

        elif campaign_id == "sources_of_power":
            if victory_type == "magian_bound":
                self.world_state.magian_status = "defeated"
                self.world_state.mebhaighl_health = 100
            elif victory_type == "magical_death":
                self.world_state.mebhaighl_health = 0

        elif campaign_id == "cerilian_alliance":
            if victory_type in ["awnshegh_defeated", "lasting_alliance"]:
                self.world_state.cerilian_alliance_formed = True
                self.world_state.awnshegh_coordination = 0

    def save_all(self, save_name: str = "autosave") -> bool:
        """Save complete game state."""
        save_dir = SAVES_PATH / save_name
        save_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Save world state
            world_path = save_dir / "world_state.json"
            with open(world_path, 'w') as f:
                json.dump(self.world_state.to_dict(), f, indent=2)

            # Save player legacy
            legacy_path = save_dir / "player_legacy.json"
            with open(legacy_path, 'w') as f:
                json.dump(self.player_legacy.to_dict(), f, indent=2)

            # Save NPC persistent state
            npc_path = save_dir / "npc_state.json"
            with open(npc_path, 'w') as f:
                json.dump(self.npc_persistent_state, f, indent=2)

            # Save active campaign if any
            if self.active_campaign:
                campaign_path = save_dir / "active_campaign.json"
                self.active_campaign.save(campaign_path)

            # Save metadata
            meta_path = save_dir / "meta.json"
            with open(meta_path, 'w') as f:
                json.dump({
                    "version": "1.0",
                    "saved_at": datetime.now().isoformat(),
                    "has_active_campaign": self.active_campaign is not None,
                    "active_campaign_id": self.active_campaign.campaign_id if self.active_campaign else None,
                    "completed_campaigns": self.player_legacy.completed_campaigns
                }, f, indent=2)

            self.last_error = None
            return True

        except OSError as e:
            self.last_error = str(e)
            print(f"Save failed: {e}")
            return False

    def load_save(self, save_name: str) -> bool:
        """Load complete game state from save."""
        save_dir = SAVES_PATH / save_name
        if not save_dir.exists():
            return False

        try:
            # Load world state
            world_path = save_dir / "world_state.json"
            if world_path.exists():
                with open(world_path, 'r') as f:
                    self.world_state = WorldState.from_dict(json.load(f))

            # Load player legacy
            legacy_path = save_dir / "player_legacy.json"
            if legacy_path.exists():
                with open(legacy_path, 'r') as f:
                    self.player_legacy = PlayerLegacy.from_dict(json.load(f))

            # Load NPC persistent state
            npc_path = save_dir / "npc_state.json"
            if npc_path.exists():
                with open(npc_path, 'r') as f:
                    self.npc_persistent_state = json.load(f)

            # Load active campaign
            campaign_path = save_dir / "active_campaign.json"
            if campaign_path.exists():
                self.active_campaign = CampaignState.load(campaign_path)

            self.last_error = None
            return True

        except (OSError, json.JSONDecodeError) as e:
            self.last_error = str(e)
            print(f"Load failed: {e}")
            return False

    def list_saves(self) -> List[Dict[str, Any]]:
        """List available save files."""
        saves = []
        if not SAVES_PATH.exists():
            return saves

        for save_dir in SAVES_PATH.iterdir():
            if save_dir.is_dir():
                meta_path = save_dir / "meta.json"
                if meta_path.exists():
                    try:
                        with open(meta_path, 'r') as f:
                            meta = json.load(f)
                        meta["name"] = save_dir.name
                        saves.append(meta)
                    except (IOError, json.JSONDecodeError):
                        pass

        # Sort by save time, newest first
        saves.sort(key=lambda x: x.get("saved_at", ""), reverse=True)
        return saves
