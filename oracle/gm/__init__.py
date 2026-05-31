"""
Game Master Intelligence System

A procedural AI Game Master that provides narrative responses,
interprets oracle results, and manages solo RPG sessions.

This module is shared between the Oracle GUI and Birthright Campaign Manager.
"""

from oracle.gm.brain import GameMasterBrain
from oracle.gm.personality import GMPersonality, GMStyle
from oracle.gm.memory import SessionMemory
from oracle.gm.responder import NarrativeResponder

__all__ = [
    "GameMasterBrain",
    "GMPersonality",
    "GMStyle",
    "SessionMemory",
    "NarrativeResponder"
]
