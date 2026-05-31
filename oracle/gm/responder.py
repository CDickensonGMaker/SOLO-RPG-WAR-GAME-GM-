"""
Narrative Responder - Generates contextual narrative responses.

Uses templates, tables, and procedural generation to create
GM responses that feel natural and contextually appropriate.
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import random
import re

from oracle.gm.personality import GMPersonality, GMTone
from oracle.gm.memory import SessionMemory


@dataclass
class ResponseTemplate:
    """A template for generating responses."""
    pattern: str
    variations: List[str]
    tone_modifiers: Dict[str, List[str]] = None

    def generate(self, context: Dict[str, Any], tone: GMTone = GMTone.NEUTRAL) -> str:
        """Generate a response from this template."""
        # Pick a variation
        text = random.choice(self.variations)

        # Apply context substitutions
        for key, value in context.items():
            text = text.replace(f"{{{key}}}", str(value))

        # Apply tone modifiers if available
        if self.tone_modifiers and tone.value in self.tone_modifiers:
            modifier = random.choice(self.tone_modifiers[tone.value])
            text = modifier.format(text=text)

        return text


class NarrativeResponder:
    """
    Generates narrative responses based on context and templates.

    This is the core response generation system that makes the GM
    feel intelligent and contextually aware.
    """

    def __init__(self, personality: GMPersonality = None):
        self.personality = personality or GMPersonality()
        self._init_templates()

    def _init_templates(self):
        """Initialize response templates."""

        # Oracle interpretation templates
        self.oracle_templates = {
            "yes_and": [
                "Yes, and more than you might expect. {elaboration}",
                "Absolutely! In fact, {elaboration}",
                "Yes — and the implications run deeper. {elaboration}",
                "Indeed so, and {elaboration}",
                "Yes, emphatically. Moreover, {elaboration}",
            ],
            "yes": [
                "Yes.",
                "It is so.",
                "The answer is yes.",
                "Indeed.",
                "That is correct.",
                "Yes, that happens.",
            ],
            "yes_but": [
                "Yes, but {complication}",
                "Yes... though {complication}",
                "It is so, however {complication}",
                "Yes, with a caveat: {complication}",
                "The answer is yes, but be warned — {complication}",
            ],
            "no_but": [
                "No, but {silver_lining}",
                "Not quite, though {silver_lining}",
                "The answer is no... however, {silver_lining}",
                "No, yet {silver_lining}",
                "It fails, but {silver_lining}",
            ],
            "no": [
                "No.",
                "It is not so.",
                "The answer is no.",
                "That does not come to pass.",
                "No, that doesn't happen.",
            ],
            "no_and": [
                "No, and worse — {escalation}",
                "Absolutely not. Furthermore, {escalation}",
                "No — and the situation deteriorates. {escalation}",
                "Not only does it fail, but {escalation}",
                "No, and {escalation}",
            ],
        }

        # Scene description templates
        self.scene_templates = {
            "arrival": [
                "You arrive at {location}. {description}",
                "Before you lies {location}. {description}",
                "{location} stretches out ahead. {description}",
                "You find yourself at {location}. {description}",
            ],
            "transition": [
                "The scene shifts. {description}",
                "Time passes... {description}",
                "Meanwhile, {description}",
                "The story continues. {description}",
            ],
            "danger": [
                "Danger! {description}",
                "Something is wrong. {description}",
                "Your instincts scream warning. {description}",
                "Trouble finds you. {description}",
            ],
        }

        # NPC interaction templates
        self.npc_templates = {
            "greeting_friendly": [
                "{npc_name} greets you warmly. \"{greeting}\"",
                "A smile crosses {npc_name}'s face as they see you. \"{greeting}\"",
                "{npc_name} approaches with evident pleasure. \"{greeting}\"",
            ],
            "greeting_neutral": [
                "{npc_name} acknowledges your presence. \"{greeting}\"",
                "{npc_name} looks up as you approach. \"{greeting}\"",
                "You encounter {npc_name}. They say, \"{greeting}\"",
            ],
            "greeting_hostile": [
                "{npc_name} eyes you with suspicion. \"{greeting}\"",
                "A cold reception from {npc_name}. \"{greeting}\"",
                "{npc_name}'s expression hardens. \"{greeting}\"",
            ],
            "reaction_positive": [
                "{npc_name} nods approvingly.",
                "This pleases {npc_name}.",
                "{npc_name} seems satisfied by this.",
                "A favorable response from {npc_name}.",
            ],
            "reaction_negative": [
                "{npc_name} frowns at this.",
                "Displeasure crosses {npc_name}'s face.",
                "{npc_name} is not happy about this.",
                "This does not sit well with {npc_name}.",
            ],
        }

        # Action result templates
        self.action_templates = {
            "success": [
                "Success! {result}",
                "You succeed. {result}",
                "It works. {result}",
                "Your efforts pay off. {result}",
                "Well done. {result}",
            ],
            "failure": [
                "You fail. {result}",
                "It doesn't work. {result}",
                "Your attempt falls short. {result}",
                "Unfortunately, {result}",
                "Failure. {result}",
            ],
            "partial": [
                "Partial success. {result}",
                "It works, partially. {result}",
                "Some progress, but {result}",
                "You achieve part of your goal. {result}",
            ],
            "critical_success": [
                "Critical success! {result}",
                "Exceptional! {result}",
                "Beyond your wildest hopes — {result}",
                "The stars align in your favor. {result}",
            ],
            "critical_failure": [
                "Critical failure! {result}",
                "Disaster strikes. {result}",
                "Everything goes wrong. {result}",
                "Catastrophe! {result}",
            ],
        }

        # Elaboration generators for oracle results
        self.elaborations = {
            "positive": [
                "unexpected allies appear",
                "additional resources become available",
                "the situation improves beyond expectations",
                "a hidden opportunity reveals itself",
                "fortune smiles upon you",
            ],
            "complication": [
                "there's a catch",
                "it comes at a cost",
                "complications arise",
                "there are strings attached",
                "the victory is not complete",
                "an obstacle remains",
            ],
            "silver_lining": [
                "you learn something valuable",
                "a new opportunity emerges",
                "not all is lost",
                "there is still hope",
                "you gain insight from the failure",
            ],
            "escalation": [
                "the situation worsens",
                "new threats emerge",
                "your position weakens",
                "enemies take notice",
                "time runs short",
                "resources are depleted",
            ],
        }

        # Random event triggers
        self.random_events = {
            "positive": [
                "An unexpected ally makes their presence known.",
                "Fortune favors you with a stroke of luck.",
                "A resource you needed appears.",
                "Someone offers unexpected help.",
                "The situation shifts in your favor.",
            ],
            "negative": [
                "An old enemy resurfaces.",
                "Complications arise from an unexpected quarter.",
                "Something you relied upon fails.",
                "A new threat emerges.",
                "The situation grows more dire.",
            ],
            "neutral": [
                "A stranger arrives with news.",
                "Something changes in the environment.",
                "An opportunity presents itself — but so does risk.",
                "Events elsewhere affect the current situation.",
                "A choice must be made.",
            ],
        }

    def interpret_oracle(self, answer: str, question: str,
                         memory: SessionMemory = None) -> str:
        """
        Generate a narrative interpretation of an oracle result.

        Args:
            answer: Oracle result (yes_and, yes, yes_but, no_but, no, no_and)
            question: The question that was asked
            memory: Session memory for context

        Returns:
            Narrative interpretation
        """
        templates = self.oracle_templates.get(answer, self.oracle_templates["yes"])
        base = random.choice(templates)

        # Generate elaboration based on answer type
        context = {"question": question}

        if answer == "yes_and":
            context["elaboration"] = random.choice(self.elaborations["positive"])
        elif answer == "yes_but":
            context["complication"] = random.choice(self.elaborations["complication"])
        elif answer == "no_but":
            context["silver_lining"] = random.choice(self.elaborations["silver_lining"])
        elif answer == "no_and":
            context["escalation"] = random.choice(self.elaborations["escalation"])

        # Apply context
        response = base
        for key, value in context.items():
            response = response.replace(f"{{{key}}}", value)

        # Apply personality formatting
        response = self.personality.format_response(response)

        return response

    def describe_scene(self, location: str, mood: str = "neutral",
                       scene_type: str = "arrival",
                       details: Dict[str, Any] = None) -> str:
        """Generate a scene description."""
        templates = self.scene_templates.get(scene_type, self.scene_templates["arrival"])
        base = random.choice(templates)

        # Generate description based on mood
        description = self._generate_mood_description(mood, details or {})

        context = {
            "location": location,
            "description": description
        }

        response = base
        for key, value in context.items():
            response = response.replace(f"{{{key}}}", value)

        return self.personality.format_response(response)

    def _generate_mood_description(self, mood: str, details: Dict) -> str:
        """Generate description text based on mood."""
        mood_descriptors = {
            "peaceful": ["calm", "serene", "quiet", "tranquil"],
            "tense": ["uneasy", "watchful", "alert", "strained"],
            "dangerous": ["threatening", "ominous", "perilous", "deadly"],
            "mysterious": ["strange", "enigmatic", "puzzling", "secretive"],
            "festive": ["joyful", "celebratory", "lively", "merry"],
            "grim": ["somber", "dark", "foreboding", "bleak"],
            "neutral": ["ordinary", "unremarkable", "typical", "normal"],
        }

        descriptor = random.choice(mood_descriptors.get(mood, mood_descriptors["neutral"]))

        templates = [
            f"The atmosphere is {descriptor}.",
            f"A {descriptor} feeling pervades the area.",
            f"There is something {descriptor} about this place.",
            f"You sense a {descriptor} quality here.",
        ]

        return random.choice(templates)

    def npc_interaction(self, npc_name: str, disposition: int,
                        interaction_type: str = "greeting") -> str:
        """Generate an NPC interaction response."""
        # Determine template category based on disposition
        if disposition > 30:
            category = f"{interaction_type}_friendly"
        elif disposition < -30:
            category = f"{interaction_type}_hostile"
        else:
            category = f"{interaction_type}_neutral"

        templates = self.npc_templates.get(category, self.npc_templates.get(f"{interaction_type}_neutral", ["..."]))
        base = random.choice(templates)

        # Generate contextual greeting/dialogue
        greeting = self._generate_npc_dialogue(npc_name, disposition, interaction_type)

        context = {
            "npc_name": npc_name,
            "greeting": greeting
        }

        response = base
        for key, value in context.items():
            response = response.replace(f"{{{key}}}", value)

        return self.personality.format_response(response)

    def _generate_npc_dialogue(self, npc_name: str, disposition: int,
                               interaction_type: str) -> str:
        """Generate NPC dialogue based on disposition."""
        if disposition > 50:
            lines = [
                "It's good to see you, friend!",
                "Ah, a welcome sight indeed.",
                "I was hoping you'd come.",
            ]
        elif disposition > 20:
            lines = [
                "Well met.",
                "Good to see you.",
                "Welcome.",
            ]
        elif disposition > -20:
            lines = [
                "Yes? What is it?",
                "State your business.",
                "Can I help you?",
            ]
        elif disposition > -50:
            lines = [
                "What do you want?",
                "Make it quick.",
                "I have nothing to say to you.",
            ]
        else:
            lines = [
                "You have nerve showing your face here.",
                "Leave. Now.",
                "We have nothing to discuss.",
            ]

        return random.choice(lines)

    def action_result(self, success_level: str, action: str,
                      details: str = "") -> str:
        """Generate a response for an action result."""
        templates = self.action_templates.get(success_level, self.action_templates["success"])
        base = random.choice(templates)

        context = {
            "action": action,
            "result": details if details else self._generate_result_details(success_level, action)
        }

        response = base
        for key, value in context.items():
            response = response.replace(f"{{{key}}}", value)

        return self.personality.format_response(response)

    def _generate_result_details(self, success_level: str, action: str) -> str:
        """Generate details for an action result."""
        if success_level in ["success", "critical_success"]:
            details = [
                "You achieve your goal.",
                "The outcome is favorable.",
                "It goes as planned.",
            ]
        elif success_level == "partial":
            details = [
                "Some progress is made, but challenges remain.",
                "Partial victory, with complications.",
                "The goal is partially achieved.",
            ]
        else:
            details = [
                "The attempt does not succeed.",
                "Things don't go as planned.",
                "The outcome is unfavorable.",
            ]

        return random.choice(details)

    def random_event(self, event_type: str = None,
                     memory: SessionMemory = None) -> str:
        """Generate a random event based on context."""
        if event_type is None:
            # Determine event type based on context
            if memory and memory.chaos_factor > 6:
                event_type = random.choice(["positive", "negative", "negative"])
            elif memory and memory.chaos_factor < 4:
                event_type = random.choice(["positive", "positive", "neutral"])
            else:
                event_type = random.choice(["positive", "negative", "neutral"])

        events = self.random_events.get(event_type, self.random_events["neutral"])
        event = random.choice(events)

        return self.personality.format_response(event)

    def generate_response(self, user_input: str, memory: SessionMemory,
                          response_type: str = "conversation") -> str:
        """
        Generate a contextual response to user input.

        This is the main method for generating conversational responses.
        """
        # Analyze input
        input_lower = user_input.lower()

        # Check for specific intents
        if any(word in input_lower for word in ["where am i", "look around", "describe"]):
            return self.describe_scene(
                memory.current_scene["location"],
                memory.current_scene["mood"]
            )

        elif any(word in input_lower for word in ["who is here", "anyone here", "npcs"]):
            npcs = memory.current_scene.get("present_npcs", [])
            if npcs:
                return f"Present in {memory.current_scene['location']}: {', '.join(npcs)}."
            else:
                return "You appear to be alone here."

        elif any(word in input_lower for word in ["what's happening", "status", "situation"]):
            return memory.get_context_summary()

        else:
            # Generic conversational response
            responses = [
                f"I understand. The situation in {memory.current_scene['location']} continues to unfold.",
                "Noted. What would you like to do?",
                "The Oracle awaits your next question or action.",
                "I hear you. How shall we proceed?",
                self.personality.get_affirmation() + " What next?",
            ]
            return random.choice(responses)
