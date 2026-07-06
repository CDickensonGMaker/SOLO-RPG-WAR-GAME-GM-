# Oracle Enhancement Plan: From 30% to Adventure

## The Diagnosis: Why It Feels Mechanical

After analyzing the codebase and researching solo RPG design, here's what's creating the gap:

### Solo RPG Mode Problems

| Issue | Current State | Adventure Feels Like |
|-------|---------------|---------------------|
| **Generic Elaborations** | "unexpected allies appear" | "Grimjaw's old war buddy stumbles in, bleeding from an ambush" |
| **No Meaning Tables** | Fixed elaboration lists | Mythic-style Action + Subject combinations that surprise |
| **Flat "ANDs" and "BUTs"** | "Yes, but there's a catch" | "Yes, but the merchant's eyes flick to the back room - he's not alone" |
| **No Pacing System** | Every beat feels equal | Push/Pause/Pull rhythm with tension tracking |
| **NPCs Lack Memory** | Each interaction is fresh | "Last time you promised to return that stolen chalice..." |
| **No Scene Bangs** | Scenes start neutrally | "You arrive just as the inn erupts in flames" |
| **Complications Ignore Fiction** | Generic obstacles | Complications that pull from active threads and NPCs |

### Wargame Mode Problems

| Issue | Current State | Adventure Feels Like |
|-------|---------------|---------------------|
| **No Commander Personality** | Anonymous tactical output | "Von Krieger advances his Panzers - he's testing your flanks" |
| **Pure Mechanics** | Threat assessment lists | Narrated tactical drama with uncertainty |
| **No Fog of War** | AI knows everything | AI bluffs, feints, makes mistakes |
| **Static Keywords** | Hard-coded threat list | TOML-driven, game-specific threats |
| **No Battle Narrative** | Data readouts | "The left flank buckles under massed fire!" |

---

## Research Findings

### From Mythic GME 2nd Edition
- **45+ Meaning Tables**: Action + Subject combinations for context-specific interpretation
- **Chaos Snowball**: Bad situations compound, success breeds stability
- **"I Dunno" Rule**: Don't overthink - first logical interpretation wins
- **Scene Interrupts**: Scenes can be altered (odd) or interrupted (even) based on chaos

### From Pacing Research ([TTRPG Games](https://www.ttrpg-games.com/blog/ultimate-guide-to-rpg-pacing-and-tension/), [Alexandrian](https://thealexandrian.net/wordpress/31509/roleplaying-games/the-art-of-pacing))
- **Push/Pause/Pull System**: Scenes categorized by energy state
- **Tension Ladder (1-5)**: Track dramatic intensity
- **3:1 Ratio**: Horror uses 3 tension beats to 1 rest beat
- **3 T's (ICRPG)**: Threats, Timers, Treats - every scene needs them
- **Frame Past the Entrance**: Skip boring setup, start at the conflict

### From LLM RPG Research ([Ian Bicking](https://ianbicking.org/blog/2024/04/roleplaying-by-llm), [Interactive LLM NPCs](https://github.com/AkshitIreddy/Interactive-LLM-Powered-NPCs))
- **Character Sheets as Context**: Copy personality/backstory into prompts
- **Lists Over Singles**: LLMs brainstorm better in list form
- **Voice Consistency**: "Vex speaks in clipped sentences" beats paragraphs of backstory
- **Memory Matters**: Track what each NPC knows vs doesn't know

---

## The Enhancement Plan

### Phase 1: Meaning Tables (The Mythic Secret Sauce)
**Goal**: Oracle results feel surprising and connected to fiction

**Add to `oracle/data/core/`:**
```
meaning_tables/
  actions.toml        # 100 verbs: "Betrays", "Protects", "Reveals"...
  subjects.toml       # 100 nouns: "The Secret", "A Promise", "The Enemy"...
  context_actions/    # Context-specific actions
    combat.toml       # "Flanks", "Retreats", "Surrenders"
    social.toml       # "Confides", "Manipulates", "Insults"
    exploration.toml  # "Discovers", "Triggers", "Avoids"
```

**Modify `responder.py`:**
- When generating elaborations, combine Action + Subject
- Filter by current context (combat, social, exploration)
- Connect to active NPCs/threads when possible

**Example Result:**
- OLD: "Yes, and unexpected allies appear"
- NEW: "Yes, and... [rolls: Reveals + The Secret] ...the merchant reveals he's been hiding your father's journal"

### Phase 2: Fiction-Aware Complications
**Goal**: "ANDs" and "BUTs" reference the actual story

**Create `oracle/gm/complication_generator.py`:**
```python
class ComplicationGenerator:
    def generate(self, oracle_result: str, memory: SessionMemory) -> str:
        # Pull from active fiction
        active_npcs = memory.get_present_npcs()
        active_threads = memory.get_active_threads()
        current_location = memory.current_scene["location"]

        # Weight complications toward active fiction
        if oracle_result in ["yes_but", "no_but"]:
            return self._generate_complication(active_npcs, active_threads)
        elif oracle_result in ["yes_and", "no_and"]:
            return self._generate_escalation(active_npcs, active_threads)
```

**Example Result:**
- OLD: "Yes, but there's a catch"
- NEW: "Yes, but Grimjaw's eyes narrow - he remembers you from the Blackmoor raid"

### Phase 3: Pacing Engine
**Goal**: Scenes have rhythm - tension rises and falls

**Add to `oracle/gm/pacing.py`:**
```python
class PacingEngine:
    # Scene energy states
    PUSH = "push"    # Action, pressure, stakes rising
    PAUSE = "pause"  # Breathing room, character moments
    PULL = "pull"    # Revelation, mystery deepens, new hooks

    tension_level: int  # 1-5 scale
    beats_since_pause: int

    def suggest_beat(self) -> str:
        """Suggest next beat type based on pacing rules."""
        # 3:1 tension to rest for dramatic scenes
        if self.beats_since_pause >= 3:
            return self.PAUSE
        if self.tension_level >= 4:
            return self.PUSH  # Climax building
        ...

    def get_scene_bang(self) -> str:
        """Generate a dramatic opening hook."""
        # Frame past the entrance
        ...
```

**Add to `oracle/data/core/pacing.toml`:**
```toml
[scene_bangs]
combat = [
  "You arrive just as weapons are drawn",
  "The first shot rings out before you see the enemy",
  "The bodies aren't cold yet",
]
social = [
  "An argument is already in progress",
  "Someone important is leaving as you arrive",
  "The room falls silent when you enter",
]
```

### Phase 4: NPC Memory and Voice
**Goal**: NPCs remember you and sound distinct

**Enhance `SessionMemory` with NPC conversation tracking:**
```python
@dataclass
class NPCConversationLog:
    npc_name: str
    topics_discussed: List[str]
    promises_made: List[str]    # "Promised to find the artifact"
    lies_told: List[str]        # "Claimed to be a merchant"
    disposition_changes: List[Tuple[int, str]]  # (+10, "saved his daughter")
```

**Enhance `VoiceGenerator` with personality templates:**
- Create archetype voices: Grizzled Veteran, Nervous Scholar, Cunning Merchant
- Each archetype has speech patterns, vocabulary limits, knowledge domains
- NPCs can reference past interactions

**Example:**
- FIRST MEETING: "State your business."
- SECOND MEETING: "You again. Did you find what you were looking for?"
- AFTER BETRAYAL: "I trusted you once. That won't happen again."

### Phase 5: Wargame Commander Personalities
**Goal**: Feel like you're facing a thinking opponent

**Create `oracle/wargame_commander.py`:**
```python
class CommanderPersonality:
    name: str
    archetype: str  # "Cautious_Planner", "Aggressive_Blitzer", "Cunning_Feinter"
    voice_patterns: List[str]
    signature_moves: List[str]
    weaknesses: List[str]

COMMANDERS = {
    "von_krieger": CommanderPersonality(
        name="Marshal von Krieger",
        archetype="Aggressive_Blitzer",
        voice_patterns=["We attack at dawn.", "Hesitation is death."],
        signature_moves=["Alpha strike on exposed units", "Refuses to retreat"],
        weaknesses=["Overextends", "Ignores rear guard"],
    ),
    ...
}
```

**Add battle narration layer:**
```python
def narrate_decision(decision: TacticalDecision, commander: Commander) -> str:
    """Turn mechanical decision into narrative."""
    # OLD: "DECISION: Focus fire on highest threat"
    # NEW: "Von Krieger's tanks pivot as one. 'Concentrate fire!'
    #       The Leman Russ squadron unleashes hell on your exposed flank."
```

**Add uncertainty/fog of war:**
- AI sometimes misidentifies threats
- Commander personality affects risk tolerance
- Bluffs and feints based on doctrine

### Phase 6: Local LLM Integration (Optional Enhancement)
**Goal**: Hybrid mode for richer responses when available

**Create `oracle/gm/llm_enhancer.py`:**
```python
class LLMEnhancer:
    """Optional LLM enhancement for narrative responses."""

    def __init__(self, endpoint: str = "http://localhost:1234/v1"):
        self.enabled = self._check_availability()

    def enhance_oracle_response(
        self,
        base_response: str,
        context: SessionMemory
    ) -> str:
        """Use LLM to enrich procedural response."""
        prompt = self._build_prompt(base_response, context)
        # Returns enhanced version or falls back to base_response
```

**Design character sheets as prompt context:**
```python
def build_npc_prompt(npc: TrackedEntity) -> str:
    return f"""You are {npc.name}, a {npc.description}.
Traits: {', '.join(npc.traits)}
Disposition toward player: {npc.disposition}/100
You know: {npc.revealed_knowledge}
You hide: {npc.hidden_knowledge}
Speak in character. Use {npc.voice_style}."""
```

---

## Implementation Order

1. **Meaning Tables** (Week 1) - Most impact for least code
2. **Fiction-Aware Complications** (Week 2) - Connects oracle to story
3. **Pacing Engine** (Week 3) - Rhythm and tension tracking
4. **NPC Memory** (Week 4) - Persistent relationships
5. **Wargame Commanders** (Week 5) - Personality for tactical AI
6. **LLM Integration** (Optional) - Enhancement layer

---

## File Changes Summary

### New Files
- `oracle/data/core/meaning_tables/actions.toml`
- `oracle/data/core/meaning_tables/subjects.toml`
- `oracle/gm/complication_generator.py`
- `oracle/gm/pacing.py`
- `oracle/gm/npc_memory.py`
- `oracle/wargame_commander.py`
- `oracle/gm/llm_enhancer.py` (optional)

### Modified Files
- `oracle/gm/responder.py` - Use meaning tables, fiction-aware complications
- `oracle/gm/brain.py` - Integrate pacing engine
- `oracle/gm/memory.py` - NPC conversation logs
- `oracle/gm/nlp/voice.py` - Archetype voices
- `oracle/wargame.py` - Commander personalities, narration layer

---

## Success Metrics

| Metric | Current (30%) | Target (100%) |
|--------|---------------|---------------|
| Oracle responses reference current NPCs | Never | 40% of time |
| Complications connect to active threads | Never | 60% of time |
| NPCs remember past interactions | Never | Always |
| Scenes have dramatic opening hooks | Never | 80% of time |
| Wargame AI has personality | Never | Always |
| Tension varies scene-to-scene | Flat | Clear rhythm |

---

## Sources

- [Mythic GME 2e](https://www.wordmillgames.com/mythic-gme.html) - Meaning tables, chaos system
- [TTRPG Games Pacing Guide](https://www.ttrpg-games.com/blog/ultimate-guide-to-rpg-pacing-and-tension/) - Tension ladder, 3:1 ratio
- [The Alexandrian: Art of Pacing](https://thealexandrian.net/wordpress/31509/roleplaying-games/the-art-of-pacing) - Scene framing, bangs
- [Hands-Free RPG Pacing](https://scriptorum.itch.io/hands-free-rpg/devlog/1501690/pacing-for-rpgs) - Push/Pause/Pull system
- [LLM Roleplay Observations](https://ianbicking.org/blog/2024/04/roleplaying-by-llm) - Lists over singles, memory importance
- [Interactive LLM NPCs](https://github.com/AkshitIreddy/Interactive-LLM-Powered-NPCs) - Character sheets as context
- [Best LLM for Roleplay 2026](https://www.noviai.ai/models-prompts/best-llm-for-roleplay/) - Model recommendations
