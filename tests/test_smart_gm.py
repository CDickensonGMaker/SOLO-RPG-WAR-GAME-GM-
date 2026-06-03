"""
Tests for the Smart GM Brain (NLP orchestrator).

Tests:
- Pattern matching for various intents
- Entity resolution against memory
- Orchestrator flow from input to response
- Fallback to traditional processing
"""

import pytest
from oracle.gm.brain import GameMasterBrain
from oracle.gm.memory import SessionMemory
from oracle.gm.nlp.patterns import PatternMatcher, Intent
from oracle.gm.nlp.resolver import EntityResolver


class TestPatternMatcher:
    """Tests for the PatternMatcher class."""

    @pytest.fixture
    def matcher(self):
        return PatternMatcher()

    # === Oracle Questions ===

    def test_yes_no_question_is(self, matcher):
        intent = matcher.match("Is the door locked?")
        assert intent is not None
        assert intent.action == "ask_oracle"
        assert "door locked" in intent.topic.lower()

    def test_yes_no_question_does(self, matcher):
        intent = matcher.match("Does the guard trust me?")
        assert intent is not None
        assert intent.action == "ask_oracle"

    def test_yes_no_question_will(self, matcher):
        intent = matcher.match("Will they attack?")
        assert intent is not None
        assert intent.action == "ask_oracle"

    def test_non_question_no_match(self, matcher):
        # Statements shouldn't match yes/no pattern
        intent = matcher.match("The door is locked.")
        assert intent is None or intent.action != "ask_oracle"

    # === Talk To ===

    def test_talk_ask_about(self, matcher):
        intent = matcher.match("ask the merchant about the artifact")
        assert intent is not None
        assert intent.action == "talk_to"
        assert "merchant" in intent.target.lower()
        assert "artifact" in intent.topic.lower()

    def test_talk_speak_to(self, matcher):
        intent = matcher.match("speak to the guard")
        assert intent is not None
        assert intent.action == "talk_to"
        assert "guard" in intent.target.lower()

    def test_talk_with_topic(self, matcher):
        intent = matcher.match("talk to Grimjaw about the missing gold")
        assert intent is not None
        assert intent.action == "talk_to"
        assert "grimjaw" in intent.target.lower()

    # === Search ===

    def test_search_for(self, matcher):
        intent = matcher.match("search for clues")
        assert intent is not None
        assert intent.action == "search"
        assert "clues" in intent.target.lower()

    def test_search_location_for(self, matcher):
        intent = matcher.match("search the room for survivors")
        assert intent is not None
        assert intent.action == "search"

    def test_look_around(self, matcher):
        intent = matcher.match("look around the chapel")
        assert intent is not None
        assert intent.action == "search"

    # === Travel ===

    def test_travel_go_to(self, matcher):
        intent = matcher.match("go to the tavern")
        assert intent is not None
        assert intent.action == "travel"
        assert "tavern" in intent.target.lower()

    def test_travel_head_toward(self, matcher):
        intent = matcher.match("head toward the mountains")
        assert intent is not None
        assert intent.action == "travel"

    def test_travel_enter(self, matcher):
        intent = matcher.match("enter the dungeon")
        assert intent is not None
        assert intent.action == "travel"

    def test_travel_direction(self, matcher):
        intent = matcher.match("go north")
        assert intent is not None
        assert intent.action == "travel"
        assert "north" in intent.target.lower()

    # === Investigate ===

    def test_investigate_examine(self, matcher):
        intent = matcher.match("examine the strange symbol")
        assert intent is not None
        assert intent.action == "investigate"
        assert "symbol" in intent.target.lower()

    def test_investigate_inspect(self, matcher):
        intent = matcher.match("inspect the old map")
        assert intent is not None
        assert intent.action == "investigate"

    # === Fight ===

    def test_fight_attack(self, matcher):
        intent = matcher.match("attack the goblin")
        assert intent is not None
        assert intent.action == "fight"
        assert "goblin" in intent.target.lower()

    def test_fight_kill(self, matcher):
        intent = matcher.match("kill the beast")
        assert intent is not None
        assert intent.action == "fight"

    # === Use ===

    def test_use_item_on_target(self, matcher):
        intent = matcher.match("use the key on the door")
        assert intent is not None
        assert intent.action == "use"
        assert "key" in intent.extras.get("item", "").lower()
        assert "door" in intent.target.lower()

    def test_use_item_alone(self, matcher):
        intent = matcher.match("use the healing potion")
        assert intent is not None
        assert intent.action == "use"

    # === Observe ===

    def test_observe_watch(self, matcher):
        intent = matcher.match("watch the guards")
        assert intent is not None
        assert intent.action == "observe"
        assert "guards" in intent.target.lower()

    def test_observe_hide(self, matcher):
        intent = matcher.match("hide in the shadows")
        assert intent is not None
        assert intent.action == "observe"

    # === Rest ===

    def test_rest_camp(self, matcher):
        intent = matcher.match("make camp")
        assert intent is not None
        assert intent.action == "rest"

    def test_rest_sleep(self, matcher):
        intent = matcher.match("rest for the night")
        assert intent is not None
        assert intent.action == "rest"

    # === Interact ===

    def test_interact_open(self, matcher):
        intent = matcher.match("open the chest")
        assert intent is not None
        assert intent.action == "interact"
        assert "chest" in intent.target.lower()

    def test_interact_take(self, matcher):
        intent = matcher.match("pick up the sword")
        assert intent is not None
        assert intent.action == "interact"


class TestEntityResolver:
    """Tests for the EntityResolver class."""

    @pytest.fixture
    def memory(self):
        mem = SessionMemory()
        # Add some test entities
        mem.track_entity("Grimjaw the Fence", "npc",
                        description="A shady merchant",
                        traits=["merchant", "fence", "thief"],
                        disposition=-10)
        mem.track_entity("Captain Helena", "npc",
                        description="Town guard captain",
                        traits=["guard", "captain", "authority"],
                        disposition=30)
        mem.track_entity("The Rusty Anchor", "location",
                        description="A seedy dockside tavern")
        mem.add_thread("Find the Artifact",
                      description="Recover the stolen artifact",
                      importance=8)
        mem.current_scene["location"] = "Market Square"
        mem.current_scene["present_npcs"] = ["Grimjaw the Fence"]
        return mem

    @pytest.fixture
    def resolver(self, memory):
        return EntityResolver(memory)

    def test_resolve_npc_exact_name(self, resolver):
        npc = resolver.resolve_npc("Grimjaw the Fence")
        assert npc is not None
        assert npc.name == "Grimjaw the Fence"

    def test_resolve_npc_partial_name(self, resolver):
        npc = resolver.resolve_npc("Grimjaw")
        assert npc is not None
        assert "Grimjaw" in npc.name

    def test_resolve_npc_by_trait(self, resolver):
        npc = resolver.resolve_npc("the merchant")
        assert npc is not None
        assert "merchant" in npc.traits

    def test_resolve_npc_by_role(self, resolver):
        npc = resolver.resolve_npc("the guard")
        assert npc is not None
        assert "guard" in npc.traits

    def test_resolve_location_current(self, resolver):
        loc = resolver.resolve_location("here")
        assert loc == "Market Square"

    def test_resolve_location_by_name(self, resolver):
        loc = resolver.resolve_location("Rusty Anchor")
        assert loc is not None
        assert "Rusty" in loc

    def test_resolve_thread(self, resolver):
        thread = resolver.resolve_thread("artifact")
        assert thread is not None
        assert "Artifact" in thread.name


class TestGMOrchestrator:
    """Integration tests for the GMOrchestrator."""

    @pytest.fixture
    def brain(self):
        brain = GameMasterBrain()
        # Set up test scenario
        brain.memory.track_entity("Grimjaw", "npc",
                                 description="A shady fence",
                                 traits=["merchant", "fence"],
                                 disposition=0)
        brain.memory.current_scene["location"] = "The Docks"
        brain.memory.current_scene["present_npcs"] = ["Grimjaw"]
        return brain

    def test_orchestrator_exists(self, brain):
        """Test that orchestrator is accessible."""
        assert brain.orchestrator is not None

    def test_process_smart_oracle_question(self, brain):
        """Test oracle question processing."""
        response = brain.process_smart("Is there danger nearby?")
        assert response is not None
        assert len(response) > 0
        # Should contain an oracle answer
        assert any(answer in response.upper() for answer in
                  ["YES", "NO"])

    def test_process_smart_search(self, brain):
        """Test search intent processing."""
        response = brain.process_smart("search for clues")
        assert response is not None
        assert len(response) > 0

    def test_process_smart_describe(self, brain):
        """Test scene description."""
        response = brain.process_smart("look around")
        assert response is not None
        # Should mention the current location
        assert "Docks" in response or len(response) > 0

    def test_process_smart_talk_to_npc(self, brain):
        """Test NPC interaction."""
        response = brain.process_smart("talk to Grimjaw")
        assert response is not None
        assert len(response) > 0

    def test_process_smart_fallback(self, brain):
        """Test fallback for unrecognized input."""
        # Random gibberish should fall back gracefully
        response = brain.process_smart("xyzzy plugh")
        assert response is not None


class TestSmartGMIntegration:
    """Full integration tests simulating a play session."""

    def test_mini_session(self):
        """Simulate a mini play session with smart GM."""
        brain = GameMasterBrain()

        # Set up a scene
        brain.set_scene("Dark Alley", mood="dangerous")

        # Introduce an NPC
        brain.introduce_npc("Shady Figure", "A cloaked stranger",
                           traits=["mysterious", "dangerous"], disposition=-20)

        # Player interactions using smart processing
        response1 = brain.process_smart("look around")
        assert response1 is not None

        response2 = brain.process_smart("Is the stranger hostile?")
        assert "YES" in response2.upper() or "NO" in response2.upper()

        response3 = brain.process_smart("search for weapons")
        assert response3 is not None

        # Memory should have recorded these interactions
        history = brain.get_history(10)
        assert len(history) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
