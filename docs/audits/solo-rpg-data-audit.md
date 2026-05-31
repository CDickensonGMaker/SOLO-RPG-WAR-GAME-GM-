# Solo RPG Data Structure Audit

**Date:** 2026-05-30
**Project:** Oracle Solo RPG Assistant
**Location:** `C:\Users\caleb\oracle\oracle\data\`

---

## Overview

This audit documents the complete data structure for the Solo RPG mode of Oracle. Data is stored in TOML files organized by **setting** (genre/world) and **content type** (NPCs, locations, encounters, etc.). The system uses a fallback mechanism: setting-specific content overrides core defaults.

---

## Directory Structure

```
oracle/data/
|
+-- core/                          # Setting-agnostic content (fallback)
|   +-- encounters/
|   |   +-- neutral.toml
|   +-- complications/             # (empty - uses setting-specific)
|   +-- locations/                 # (empty - uses setting-specific)
|   +-- npcs/                      # (empty - uses setting-specific)
|   +-- backstory_elements.toml
|   +-- battle_events.toml
|   +-- character_quirks.toml
|   +-- combat_narration.toml
|   +-- combat_situations.toml
|   +-- consequences.toml
|   +-- descriptors.toml
|   +-- dialogue_prompts.toml
|   +-- directions.toml
|   +-- discoveries.toml
|   +-- downtime.toml
|   +-- environment_hazards.toml
|   +-- factions.toml
|   +-- loot.toml
|   +-- motivations.toml
|   +-- oracle_events.toml
|   +-- pacing.toml
|   +-- perception_checks.toml
|   +-- plot_twists.toml
|   +-- quests.toml
|   +-- reactions.toml
|   +-- rumors.toml
|   +-- scene_prompts.toml
|   +-- senses.toml
|   +-- treasure_hoards.toml
|   +-- weather.toml
|
+-- fantasy/                       # Fantasy setting
|   +-- complications/
|   |   +-- grimdark.toml
|   |   +-- hopeful.toml
|   |   +-- neutral.toml
|   +-- encounters/
|   |   +-- combat.toml
|   |   +-- exploration.toml
|   |   +-- monsters.toml
|   |   +-- social.toml
|   +-- locations/
|   |   +-- dungeons.toml
|   |   +-- settlements.toml
|   |   +-- wilderness.toml
|   +-- npcs/
|       +-- dispositions.toml
|       +-- names.toml
|       +-- roles.toml
|       +-- secrets.toml
|       +-- traits.toml
|
+-- scifi_military/                # Sci-Fi Military setting
|   +-- complications/
|   |   +-- grimdark.toml
|   |   +-- hopeful.toml
|   |   +-- neutral.toml
|   +-- encounters/
|   |   +-- combat.toml
|   |   +-- social.toml
|   |   +-- xenos.toml
|   +-- locations/
|   |   +-- bases.toml
|   |   +-- planets.toml
|   |   +-- ships.toml
|   +-- npcs/
|       +-- dispositions.toml
|       +-- names.toml
|       +-- roles.toml
|       +-- secrets.toml
|       +-- traits.toml
|
+-- cyberpunk/                     # Cyberpunk setting
|   +-- complications/
|   |   +-- grimdark.toml
|   |   +-- hopeful.toml
|   |   +-- neutral.toml
|   +-- encounters/
|   |   +-- combat.toml
|   |   +-- netrunning.toml
|   |   +-- social.toml
|   +-- locations/
|   |   +-- buildings.toml
|   |   +-- net.toml
|   |   +-- streets.toml
|   +-- npcs/
|       +-- dispositions.toml
|       +-- names.toml
|       +-- roles.toml
|       +-- secrets.toml
|       +-- traits.toml
|
+-- historical/                    # Historical setting
|   +-- complications/
|   |   +-- grimdark.toml
|   |   +-- hopeful.toml
|   |   +-- neutral.toml
|   +-- encounters/
|   |   +-- combat.toml
|   |   +-- political.toml
|   |   +-- social.toml
|   |   +-- travel.toml
|   +-- locations/
|   |   +-- military.toml
|   |   +-- sea.toml
|   |   +-- settlements.toml
|   |   +-- wilderness.toml
|   +-- npcs/
|       +-- dispositions.toml
|       +-- names.toml
|       +-- roles.toml
|       +-- secrets.toml
|       +-- traits.toml
|
+-- weird_war/                     # Weird War setting
|   +-- complications/
|   |   +-- grimdark.toml
|   |   +-- hopeful.toml
|   |   +-- neutral.toml
|   +-- encounters/
|   |   +-- combat.toml
|   |   +-- horror.toml
|   |   +-- social.toml
|   +-- locations/
|   |   +-- buildings.toml
|   |   +-- features.toml
|   |   +-- trenches.toml
|   +-- npcs/
|       +-- dispositions.toml
|       +-- names.toml
|       +-- roles.toml
|       +-- secrets.toml
|       +-- traits.toml
|
+-- birthright/                    # Birthright Campaign (separate system)
|   +-- bloodlines/
|   +-- campaigns/
|   +-- cerilia/anuire/
|   +-- creatures/
|   +-- domains/
|   +-- magic/
|   +-- politics/
|   +-- regency/
|   +-- rules/
|   +-- warfare/
|
+-- wargames/                      # Wargame System (separate system)
    +-- age_of_fantasy/
    +-- grimdark_future/
    +-- old_world/
    +-- oldhammer_2e/
    +-- trench_crusade/
```

---

## Settings Overview

The system defines 5 solo RPG settings via the `Setting` enum in `oracle/mood.py`:

| Setting | Folder | Display Name | Default Tone |
|---------|--------|--------------|--------------|
| Sci-Fi Military | `scifi_military` | Sci-Fi Military | Gritty |
| Fantasy | `fantasy` | Fantasy | Neutral |
| Cyberpunk | `cyberpunk` | Cyberpunk | Gritty |
| Historical | `historical` | Historical | Neutral |
| Weird War | `weird_war` | Weird War | Grimdark |

---

## Content Types Per Setting

### Required Content Categories

Each setting MUST have these directories with content:

| Category | Contents | Tone Variants |
|----------|----------|---------------|
| `npcs/` | names, roles, traits, secrets, dispositions | No (setting-specific only) |
| `locations/` | 3 location types per setting | No (setting-specific only) |
| `encounters/` | 3-4 encounter types per setting | No (setting-specific only) |
| `complications/` | grimdark, neutral, hopeful | Yes (mood variants) |

### NPC Content (per setting)

| File | Purpose | Example Entries |
|------|---------|-----------------|
| `names.toml` | Character names by culture/type | "Aldric", "Commander Reyes", "Zero" |
| `roles.toml` | Occupations/positions | "innkeeper", "Officer", "Netrunner" |
| `traits.toml` | Personality characteristics | "Suspicious", "Shell-shocked", "Chromed-out" |
| `secrets.toml` | Hidden motivations/backgrounds | "Bound to a dark pact", "Double agent" |
| `dispositions.toml` | Initial attitude toward PCs | "Friendly", "Hostile", "Transactional" |

### Location Types (setting-specific)

| Setting | Location Files |
|---------|---------------|
| Fantasy | dungeons, settlements, wilderness |
| Sci-Fi Military | bases, planets, ships |
| Cyberpunk | buildings, net, streets |
| Historical | military, sea, settlements, wilderness |
| Weird War | buildings, features, trenches |

### Encounter Types (setting-specific)

| Setting | Encounter Files |
|---------|----------------|
| Fantasy | combat, exploration, monsters, social |
| Sci-Fi Military | combat, social, xenos |
| Cyberpunk | combat, netrunning, social |
| Historical | combat, political, social, travel |
| Weird War | combat, horror, social |

---

## Core Data Files (Setting-Agnostic)

These files apply to ALL settings and provide generic content:

| File | Purpose | Size |
|------|---------|------|
| `oracle_events.toml` | Random oracle events (positive/negative/neutral) | 11KB |
| `pacing.toml` | Scene shifts, interruptions, time skips | 8KB |
| `descriptors.toml` | General adjectives and descriptions | 7KB |
| `directions.toml` | Compass and spatial directions | 4KB |
| `motivations.toml` | Character motivations | 7KB |
| `weather.toml` | Weather conditions | 15KB |
| `character_quirks.toml` | Personality quirks | 20KB |
| `backstory_elements.toml` | Background story elements | 20KB |
| `discoveries.toml` | Things to find/discover | 20KB |
| `plot_twists.toml` | Story twists and revelations | 22KB |
| `quests.toml` | Quest/mission generators | 37KB |
| `loot.toml` | Treasure and items | 36KB |
| `rumors.toml` | Gossip and information | 21KB |
| `reactions.toml` | NPC reactions | 22KB |
| `senses.toml` | Sensory descriptions | 25KB |
| `consequences.toml` | Action consequences | 17KB |
| `combat_narration.toml` | Combat descriptions | 31KB |
| `combat_situations.toml` | Combat scenarios | 25KB |
| `environment_hazards.toml` | Environmental dangers | 20KB |
| `perception_checks.toml` | What characters notice | 17KB |
| `scene_prompts.toml` | Scene setup prompts | 18KB |
| `dialogue_prompts.toml` | Conversation starters | 22KB |
| `downtime.toml` | Between-adventure activities | 41KB |
| `treasure_hoards.toml` | Treasure generation | 27KB |
| `factions.toml` | Generic factions | 37KB |
| `battle_events.toml` | Battle happenings | 10KB |

---

## TOML Schema Patterns

### Pattern 1: Simple String List (names.toml example)

```toml
[names]
human_common = [
  "Aldric", "Brom", "Cedric", ...
]
elven = [
  "Aelindor", "Baelorin", ...
]
```

### Pattern 2: Weighted Entries (roles.toml example)

```toml
[roles]
entries = [
  { text = "innkeeper", weight = 3 },
  { text = "wizard", weight = 1 },
  ...
]
```

**Weight meaning:** Higher weight = more common (1-3 typical range)

### Pattern 3: Categorized Weighted Entries (oracle_events.toml example)

```toml
[events]
positive = [
  { text = "An unexpected ally appears", weight = 2 },
  ...
]
negative = [
  { text = "A trusted ally betrays you", weight = 1 },
  ...
]
neutral = [
  { text = "Something you assumed was true is revealed false", weight = 2 },
  ...
]
```

### Pattern 4: Multiple Tables in One File (pacing.toml example)

```toml
[scene_shifts]
entries = [ ... ]

[interruptions]
entries = [ ... ]

[time_skips]
entries = [ ... ]

[tension_modifiers]
entries = [ ... ]
```

---

## How Settings Are Loaded

### Code Flow

1. **MoodManager** (`oracle/mood.py`) tracks current setting via `MoodState.setting`
2. **TableLoader** (`oracle/tables.py`) resolves table paths with fallback:
   ```
   1. data/{setting}/{table}/{tone}.toml
   2. data/{setting}/{table}/neutral.toml
   3. data/core/{table}/{tone}.toml
   4. data/core/{table}/neutral.toml
   ```
3. **Generators** (`oracle/generators.py`) use TableLoader to get setting-aware content

### Key Functions

```python
# Set the current setting
from oracle.mood import set_setting, Setting
set_setting(Setting.FANTASY)

# Load a table with automatic fallback
from oracle.tables import load_table
table = load_table("encounters", setting="fantasy", mood="grimdark")

# Generate content using current mood
from oracle.generators import generate_encounter
encounter = generate_encounter()
```

---

## Completeness Comparison

### NPC Files (line counts)

| Setting | names | roles | traits | secrets | dispositions | Total |
|---------|-------|-------|--------|---------|--------------|-------|
| Fantasy | 73 | 151 | 122 | 80 | 41 | 467 |
| Sci-Fi Military | 133 | 105 | 121 | 77 | 30 | 466 |
| Cyberpunk | 243 | 65 | 123 | 85 | 30 | 546 |
| Historical | 109 | 91 | 123 | 75 | 44 | 442 |
| Weird War | 120 | 92 | 125 | 89 | 30 | 456 |

**Notes:**
- Cyberpunk has the most names (243 lines)
- Fantasy has the most roles (151 lines)
- All settings have roughly equal trait counts (~120 lines)
- Dispositions are sparse across all settings (30-44 lines)

### Complications Files (line counts)

All settings have consistent complication files:
- grimdark.toml: ~61 lines each
- hopeful.toml: ~58-61 lines each
- neutral.toml: ~59-61 lines each

---

## Missing Content / Gaps

### Core Subdirectories (Empty)

- `core/complications/` - Empty (relies on setting-specific)
- `core/locations/` - Empty (relies on setting-specific)
- `core/npcs/` - Empty (relies on setting-specific)

**Impact:** If no setting is selected, NPC/location generation falls back to hardcoded defaults in `generators.py` and `npc.py`.

### Potential Enhancements

1. **Missing encounter type:** No setting has an "exploration" encounter except Fantasy
2. **Historical setting:** Could use `exploration.toml` for archaeological/discovery encounters
3. **Cyberpunk setting:** Missing `exploration.toml` (could cover urban exploration, abandoned sectors)
4. **Core fallback content:** Consider adding basic `core/npcs/*.toml` for universal NPC traits

---

## Pattern for Adding New Settings

To add a new setting (e.g., "post_apocalyptic"):

### Step 1: Create Directory Structure

```
oracle/data/post_apocalyptic/
    +-- complications/
    |   +-- grimdark.toml
    |   +-- hopeful.toml
    |   +-- neutral.toml
    +-- encounters/
    |   +-- combat.toml
    |   +-- social.toml
    |   +-- [unique_type].toml
    +-- locations/
    |   +-- [type1].toml
    |   +-- [type2].toml
    |   +-- [type3].toml
    +-- npcs/
        +-- names.toml
        +-- roles.toml
        +-- traits.toml
        +-- secrets.toml
        +-- dispositions.toml
```

### Step 2: Register Setting in Code

Edit `oracle/mood.py`:

```python
class Setting(Enum):
    # ... existing settings ...
    POST_APOCALYPTIC = ("post_apocalyptic", "Post-Apocalyptic")
```

Add defaults:

```python
SETTING_DEFAULTS: dict[Setting, dict] = {
    # ... existing defaults ...
    Setting.POST_APOCALYPTIC: {
        "tone": Tone.GRITTY,
        "stakes": Stakes.DANGEROUS,
        "weirdness": Weirdness.LOW_MAGIC,
        "pace": Pace.TENSE,
    },
}
```

### Step 3: TOML File Template

```toml
# [Setting] [Category]
# Brief description

[category_name]
entries = [
  { text = "Entry text here", weight = 2 },
  { text = "Another entry", weight = 1 },
  # ... more entries ...
]
```

### Step 4: Test

```bash
python -m oracle.npc --setting post_apocalyptic
python -m oracle.tables encounters --setting post_apocalyptic
```

---

## Summary

The Oracle data system is well-structured with:
- Clear separation between core (universal) and setting-specific content
- Consistent file naming and TOML schema patterns
- Fallback mechanism for graceful degradation
- Mood/tone variants for complications (grimdark/neutral/hopeful)

All 5 settings have complete NPC and complication content. Location and encounter content varies appropriately by setting theme.

**Total TOML files:** 105+ (including core, settings, birthright, wargames)
**Solo RPG-specific files:** ~85 (core + 5 settings)
