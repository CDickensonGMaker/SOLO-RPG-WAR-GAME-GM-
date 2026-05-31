"""
Data importers for various wargame data formats.

Supports:
- BSData/BattleScribe XML (.cat, .gst, .catz, .gstz)
- JSON exports from New Recruit
- Custom TOML format
- PDF rulebooks and modules (text extraction with table detection)

BSData/BattleScribe File Structure:
    - .gst = Game System (root file defining core rules)
    - .cat = Catalogue (faction-specific data)
    - .gstz/.catz = Zipped versions of the above

Example Usage:
    >>> from oracle.importers import import_bsdata, export_to_toml
    >>> units = import_bsdata("path/to/space_marines.cat")
    >>> for unit in units:
    ...     print(f"{unit.name}: {unit.points} pts")
    >>> export_to_toml(units, "output/factions")

    >>> from oracle.importers import import_pdf
    >>> content = import_pdf("rulebook.pdf", max_pages=50)
    >>> for page in content.pages:
    ...     print(f"Page {page.number}: {len(page.tables)} tables found")
"""

import xml.etree.ElementTree as ET
import zipfile
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Any, Union
import re

# Try tomllib (3.11+) or tomli
try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None  # type: ignore

# Try PyMuPDF for PDF reading
try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None  # type: ignore

# Try pytesseract for OCR support
try:
    import pytesseract
    from PIL import Image
    import io
    PYTESSERACT_AVAILABLE = True
except ImportError:
    pytesseract = None  # type: ignore
    Image = None  # type: ignore
    PYTESSERACT_AVAILABLE = False

# Configure logging
logger = logging.getLogger(__name__)


class ImportError(Exception):
    """Base exception for import errors."""
    pass


class FileFormatError(ImportError):
    """Raised when file format is unsupported or corrupted."""
    pass


class ParseError(ImportError):
    """Raised when parsing fails."""
    pass


class ValidationError(ImportError):
    """Raised when imported data fails validation."""
    pass


class OCRNotAvailableError(ImportError):
    """Raised when OCR is requested but Tesseract is not installed."""
    pass


class EncryptedPDFError(ImportError):
    """Raised when trying to read an encrypted/password-protected PDF."""
    pass


# OCR installation instructions
OCR_INSTALL_MESSAGE = """
OCR requires Tesseract. Install with:
- Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki
- Mac: brew install tesseract
- Linux: apt install tesseract-ocr
Then: pip install pytesseract pillow
"""

# Maximum recommended file size (100MB)
MAX_RECOMMENDED_FILE_SIZE = 100 * 1024 * 1024  # 100MB in bytes


@dataclass
class ImportedUnit:
    """
    A unit imported from external data.

    This is an intermediate representation that can be converted to
    the internal UnitProfile format or exported to TOML.

    Attributes:
        name: Unit name
        faction: Faction/catalogue name
        stats: Dictionary of stat names to values
        weapons: List of weapon dictionaries
        abilities: List of special ability/rule names
        keywords: List of keywords/categories
        points: Points cost for army building
        models: Model count or range (e.g., "5-10")
        source_file: Original file this was imported from
    """
    name: str
    faction: str
    stats: dict[str, Any] = field(default_factory=dict)
    weapons: list[dict[str, Any]] = field(default_factory=list)
    abilities: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    points: int = 0
    models: str = "1"
    source_file: str = ""
    unit_type: str = "infantry"

    def __post_init__(self):
        """Validate and normalize imported data."""
        # Ensure name is non-empty
        if not self.name or not self.name.strip():
            self.name = "Unknown Unit"

        # Normalize faction name
        if not self.faction:
            self.faction = "Unknown Faction"

        # Ensure points is non-negative
        if self.points < 0:
            self.points = 0

        # Deduplicate keywords and abilities
        self.keywords = list(dict.fromkeys(self.keywords))
        self.abilities = list(dict.fromkeys(self.abilities))

    def to_toml_dict(self) -> dict[str, Any]:
        """
        Convert to TOML-compatible dictionary.

        Returns:
            Dictionary ready for TOML serialization
        """
        result = {
            "name": self.name,
            "type": self._infer_unit_type(),
            "points": self.points,
            "models": self.models,
            "stats": self.stats,
        }

        if self.weapons:
            result["weapons"] = self.weapons

        if self.abilities:
            result["special_rules"] = self.abilities

        if self.keywords:
            result["keywords"] = self.keywords

        return result

    def _infer_unit_type(self) -> str:
        """
        Infer unit type from keywords and name.

        Returns:
            Inferred unit type string
        """
        name_lower = self.name.lower()
        keywords_lower = [k.lower() for k in self.keywords]

        # Check for vehicle indicators
        vehicle_keywords = ["vehicle", "tank", "transport", "walker", "dreadnought"]
        if any(kw in keywords_lower or kw in name_lower for kw in vehicle_keywords):
            return "vehicle"

        # Check for monster/beast indicators
        monster_keywords = ["monster", "beast", "creature", "daemon", "demon"]
        if any(kw in keywords_lower or kw in name_lower for kw in monster_keywords):
            return "monster"

        # Check for character indicators
        character_keywords = ["character", "hero", "leader", "champion", "captain", "lord"]
        if any(kw in keywords_lower or kw in name_lower for kw in character_keywords):
            return "character"

        # Check for cavalry
        cavalry_keywords = ["cavalry", "mounted", "bike", "biker", "rider"]
        if any(kw in keywords_lower or kw in name_lower for kw in cavalry_keywords):
            return "cavalry"

        # Check for swarm
        swarm_keywords = ["swarm", "horde"]
        if any(kw in keywords_lower or kw in name_lower for kw in swarm_keywords):
            return "swarm"

        # Check for flyer
        flyer_keywords = ["flyer", "aircraft", "flying"]
        if any(kw in keywords_lower or kw in name_lower for kw in flyer_keywords):
            return "flyer"

        # Default to infantry
        return self.unit_type or "infantry"

    def __str__(self) -> str:
        """Human-readable string representation."""
        return f"{self.name} ({self.faction}) - {self.points} pts"


class BSDataImporter:
    """
    Imports BattleScribe/BSData XML files (.cat, .gst, .catz, .gstz).

    BSData is the open-source data repository for BattleScribe army builder.
    Files use XML with specific namespaces for game systems and catalogues.

    XML namespaces:
    - http://www.battlescribe.net/schema/gameSystemSchema
    - http://www.battlescribe.net/schema/catalogueSchema

    Example:
        >>> importer = BSDataImporter()
        >>> units = importer.import_file(Path("space_marines.cat"))
        >>> importer.export_to_toml(Path("output"), "Space Marines")
    """

    # Known BattleScribe XML namespaces
    NAMESPACES = {
        'bs': 'http://www.battlescribe.net/schema/catalogueSchema',
        'gs': 'http://www.battlescribe.net/schema/gameSystemSchema',
    }

    # Profile type mappings (lowercase)
    STAT_PROFILE_TYPES = {
        'unit', 'model', 'infantry', 'vehicle', 'monster',
        'cavalry', 'character', 'beast', 'swarm', 'hero',
        'abilities'  # Some systems put stats in abilities profile
    }

    WEAPON_PROFILE_TYPES = {
        'weapon', 'ranged weapon', 'melee weapon', 'ranged weapons',
        'melee weapons', 'shooting', 'combat', 'attack'
    }

    def __init__(self):
        """Initialize the importer."""
        self.units: list[ImportedUnit] = []
        self.rules: dict[str, str] = {}
        self.profiles: dict[str, dict[str, Any]] = {}
        self._current_namespace: dict[str, str] = {}
        self._shared_profiles: dict[str, dict[str, Any]] = {}
        self._shared_rules: dict[str, str] = {}

    def import_file(self, filepath: Union[str, Path]) -> list[ImportedUnit]:
        """
        Import a BSData file (catalogue or game system).

        Args:
            filepath: Path to .cat, .gst, .catz, or .gstz file

        Returns:
            List of ImportedUnit objects

        Raises:
            FileFormatError: If file format is unsupported
            ParseError: If XML parsing fails
            FileNotFoundError: If file doesn't exist
        """
        filepath = Path(filepath)

        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {filepath}")

        suffix = filepath.suffix.lower()

        try:
            # Handle zipped files
            if suffix in ['.catz', '.gstz']:
                return self._import_zipped(filepath)

            # Handle raw XML
            if suffix in ['.cat', '.gst']:
                return self._import_xml(filepath)

            raise FileFormatError(
                f"Unsupported file format: {suffix}. "
                f"Supported: .cat, .gst, .catz, .gstz"
            )
        except ET.ParseError as e:
            raise ParseError(f"Failed to parse XML in {filepath}: {e}") from e
        except zipfile.BadZipFile as e:
            raise FileFormatError(f"Invalid zip file {filepath}: {e}") from e

    def _import_zipped(self, filepath: Path) -> list[ImportedUnit]:
        """
        Import a zipped BSData file.

        Args:
            filepath: Path to .catz or .gstz file

        Returns:
            List of imported units
        """
        logger.debug(f"Importing zipped file: {filepath}")

        with zipfile.ZipFile(filepath, 'r') as zf:
            # Find the XML file inside
            xml_files = [
                n for n in zf.namelist()
                if n.lower().endswith(('.cat', '.gst'))
            ]

            if not xml_files:
                raise FileFormatError(
                    f"No catalogue or game system file found in archive: {filepath}"
                )

            # Parse the first (usually only) XML file
            xml_name = xml_files[0]
            logger.debug(f"Found XML file in archive: {xml_name}")

            with zf.open(xml_name) as f:
                content = f.read()
                # Handle potential encoding issues
                try:
                    xml_str = content.decode('utf-8')
                except UnicodeDecodeError:
                    xml_str = content.decode('latin-1')

                return self._parse_xml(xml_str, filepath.name)

    def _import_xml(self, filepath: Path) -> list[ImportedUnit]:
        """
        Import a raw XML BSData file.

        Args:
            filepath: Path to .cat or .gst file

        Returns:
            List of imported units
        """
        logger.debug(f"Importing XML file: {filepath}")

        # Try UTF-8 first, fall back to latin-1
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            with open(filepath, 'r', encoding='latin-1') as f:
                content = f.read()

        return self._parse_xml(content, filepath.name)

    def _parse_xml(self, xml_content: str, source: str) -> list[ImportedUnit]:
        """
        Parse BSData XML content.

        Args:
            xml_content: XML string content
            source: Source filename for reference

        Returns:
            List of imported units
        """
        root = ET.fromstring(xml_content)

        # Determine namespace from root element
        ns = self._extract_namespace(root)
        self._current_namespace = {'bs': ns} if ns else {}

        # Extract catalogue/game system name
        catalogue_name = root.get('name', 'Unknown')
        logger.info(f"Parsing catalogue: {catalogue_name}")

        # First pass: collect shared profiles and rules
        self._collect_shared_resources(root)

        units: list[ImportedUnit] = []

        # Find all selection entries (units)
        for element in root.iter():
            tag = self._strip_namespace(element.tag)

            if tag == 'selectionEntry':
                entry_type = element.get('type', '').lower()

                if entry_type == 'unit':
                    unit = self._parse_selection_entry(
                        element, catalogue_name, source
                    )
                    if unit:
                        units.append(unit)
                elif entry_type == 'model' and not self._has_parent_unit(element, root):
                    # Single model entries that aren't part of a unit
                    unit = self._parse_selection_entry(
                        element, catalogue_name, source
                    )
                    if unit:
                        units.append(unit)

        # Also process shared selection entries
        for shared in root.iter():
            tag = self._strip_namespace(shared.tag)

            if tag == 'sharedSelectionEntries':
                for entry in shared:
                    entry_type = entry.get('type', '').lower()
                    if entry_type == 'unit':
                        unit = self._parse_selection_entry(
                            entry, catalogue_name, source
                        )
                        if unit:
                            units.append(unit)

        self.units.extend(units)
        logger.info(f"Imported {len(units)} units from {source}")

        return units

    def _extract_namespace(self, element: ET.Element) -> str:
        """
        Extract namespace URI from element tag.

        Args:
            element: XML element

        Returns:
            Namespace URI or empty string
        """
        ns_match = re.match(r'\{(.+?)\}', element.tag)
        return ns_match.group(1) if ns_match else ''

    def _strip_namespace(self, tag: str) -> str:
        """
        Strip namespace prefix from tag.

        Args:
            tag: Full tag with possible namespace

        Returns:
            Tag name without namespace
        """
        if '}' in tag:
            return tag.split('}', 1)[1]
        return tag

    def _collect_shared_resources(self, root: ET.Element) -> None:
        """
        Collect shared profiles and rules for reference.

        Args:
            root: Root XML element
        """
        # Collect shared profiles
        for element in root.iter():
            tag = self._strip_namespace(element.tag)

            if tag == 'sharedProfiles':
                for profile in element:
                    profile_id = profile.get('id', '')
                    if profile_id:
                        self._shared_profiles[profile_id] = self._parse_profile(profile)

            elif tag == 'sharedRules':
                for rule in element:
                    rule_id = rule.get('id', '')
                    rule_name = rule.get('name', '')
                    if rule_id and rule_name:
                        self._shared_rules[rule_id] = rule_name

    def _parse_profile(self, profile: ET.Element) -> dict[str, Any]:
        """
        Parse a profile element into a dictionary.

        Args:
            profile: Profile XML element

        Returns:
            Dictionary of profile data
        """
        result = {
            'name': profile.get('name', ''),
            'type': profile.get('typeName', ''),
            'characteristics': {}
        }

        for child in profile.iter():
            tag = self._strip_namespace(child.tag)
            if tag == 'characteristic':
                char_name = child.get('name', '')
                char_value = child.text or ''
                if char_name:
                    result['characteristics'][char_name] = char_value

        return result

    def _has_parent_unit(self, element: ET.Element, root: ET.Element) -> bool:
        """
        Check if an element is nested within a unit entry.

        This is a simplified check - BSData structure can be complex.

        Args:
            element: Element to check
            root: Root element to search from

        Returns:
            True if element appears to be nested in a unit
        """
        # This would require parent tracking which ElementTree doesn't provide easily
        # For now, assume standalone models are valid units
        return False

    def _parse_selection_entry(
        self,
        entry: ET.Element,
        faction: str,
        source: str
    ) -> Optional[ImportedUnit]:
        """
        Parse a single selection entry (unit).

        Args:
            entry: Selection entry XML element
            faction: Faction/catalogue name
            source: Source filename

        Returns:
            ImportedUnit or None if entry should be skipped
        """
        name = entry.get('name', 'Unknown')

        # Skip hidden entries
        if entry.get('hidden', '').lower() == 'true':
            logger.debug(f"Skipping hidden entry: {name}")
            return None

        stats: dict[str, Any] = {}
        weapons: list[dict[str, Any]] = []
        abilities: list[str] = []
        keywords: list[str] = []
        points = 0
        models = "1"

        # Parse all child elements
        for child in entry.iter():
            tag = self._strip_namespace(child.tag)

            if tag == 'profile':
                self._process_profile(child, stats, weapons, abilities)

            elif tag == 'cost':
                points = self._parse_cost(child, points)

            elif tag == 'categoryLink':
                cat_name = child.get('name', '')
                if cat_name and cat_name not in keywords:
                    keywords.append(cat_name)

            elif tag == 'constraint':
                models = self._parse_constraint(child, models)

            elif tag == 'infoLink':
                # Resolve linked profiles/rules
                self._resolve_info_link(child, stats, weapons, abilities)

        # Clean up and validate
        if not stats and not weapons and not abilities:
            logger.debug(f"Skipping empty entry: {name}")
            return None

        return ImportedUnit(
            name=name,
            faction=faction,
            stats=stats,
            weapons=weapons,
            abilities=abilities,
            keywords=keywords,
            points=points,
            models=models,
            source_file=source,
        )

    def _process_profile(
        self,
        profile: ET.Element,
        stats: dict[str, Any],
        weapons: list[dict[str, Any]],
        abilities: list[str]
    ) -> None:
        """
        Process a profile element and update stats/weapons/abilities.

        Args:
            profile: Profile XML element
            stats: Stats dict to update
            weapons: Weapons list to update
            abilities: Abilities list to update
        """
        profile_type = profile.get('typeName', '').lower()
        profile_name = profile.get('name', '')

        if profile_type in self.STAT_PROFILE_TYPES:
            # This is a stat profile
            for child in profile.iter():
                tag = self._strip_namespace(child.tag)
                if tag == 'characteristic':
                    char_name = child.get('name', '')
                    char_value = child.text or ''
                    if char_name:
                        stats[char_name] = self._normalize_stat_value(char_value)

        elif profile_type in self.WEAPON_PROFILE_TYPES:
            # This is a weapon profile
            weapon = self._parse_weapon_profile(profile, profile_name)
            if weapon:
                weapons.append(weapon)

        elif profile_type in ('ability', 'abilities', 'special rule', 'special rules'):
            if profile_name and profile_name not in abilities:
                abilities.append(profile_name)

    def _parse_weapon_profile(
        self,
        profile: ET.Element,
        name: str
    ) -> Optional[dict[str, Any]]:
        """
        Parse a weapon profile into a dictionary.

        Args:
            profile: Weapon profile XML element
            name: Weapon name

        Returns:
            Weapon dictionary or None
        """
        weapon: dict[str, Any] = {"name": name}
        weapon_abilities: list[str] = []

        for child in profile.iter():
            tag = self._strip_namespace(child.tag)
            if tag == 'characteristic':
                char_name = child.get('name', '').lower()
                char_value = child.text or ''

                # Map common BattleScribe field names to standardized names
                if 'range' in char_name:
                    weapon['range'] = char_value
                elif char_name in ('s', 'strength', 'str'):
                    weapon['strength'] = char_value
                elif char_name in ('ap', 'armour penetration', 'armor penetration'):
                    weapon['ap'] = char_value
                elif char_name in ('d', 'damage', 'dam'):
                    weapon['damage'] = char_value
                elif char_name in ('a', 'attacks', 'shots'):
                    weapon['shots'] = char_value
                elif char_name in ('type', 'abilities', 'keywords'):
                    if char_value:
                        weapon_abilities.append(char_value)
                elif char_name in ('ws', 'bs', 'skill'):
                    weapon['skill'] = char_value

        if weapon_abilities:
            weapon['abilities'] = weapon_abilities

        return weapon if len(weapon) > 1 else None

    def _parse_cost(self, cost: ET.Element, current: int) -> int:
        """
        Parse a cost element.

        Args:
            cost: Cost XML element
            current: Current points value

        Returns:
            Updated points value
        """
        cost_name = cost.get('name', '').lower()

        # Look for points cost
        if 'pts' in cost_name or 'points' in cost_name or cost_name == '':
            value_str = cost.get('value', '0')
            try:
                return int(float(value_str))
            except ValueError:
                logger.debug(f"Could not parse cost value: {value_str}")

        return current

    def _parse_constraint(self, constraint: ET.Element, current: str) -> str:
        """
        Parse a constraint element for model counts.

        Args:
            constraint: Constraint XML element
            current: Current models string

        Returns:
            Updated models string
        """
        field_type = constraint.get('field', '')
        constraint_type = constraint.get('type', '')
        value = constraint.get('value', '')

        if field_type == 'selections':
            if constraint_type == 'min':
                # Store min for potential range
                if '-' not in current:
                    current = f"{value}-{current.split('-')[-1] if '-' in current else current}"
            elif constraint_type == 'max':
                # Update max value
                if '-' in current:
                    parts = current.split('-')
                    current = f"{parts[0]}-{value}"
                else:
                    min_val = current if current != value else "1"
                    if min_val != value:
                        current = f"{min_val}-{value}"
                    else:
                        current = value

        return current

    def _resolve_info_link(
        self,
        link: ET.Element,
        stats: dict[str, Any],
        weapons: list[dict[str, Any]],
        abilities: list[str]
    ) -> None:
        """
        Resolve an infoLink to shared profiles/rules.

        Args:
            link: InfoLink XML element
            stats: Stats dict to update
            weapons: Weapons list to update
            abilities: Abilities list to update
        """
        target_id = link.get('targetId', '')
        link_type = link.get('type', '').lower()

        if link_type == 'profile' and target_id in self._shared_profiles:
            profile_data = self._shared_profiles[target_id]
            profile_type = profile_data.get('type', '').lower()

            if profile_type in self.STAT_PROFILE_TYPES:
                for name, value in profile_data.get('characteristics', {}).items():
                    stats[name] = self._normalize_stat_value(value)

            elif profile_type in self.WEAPON_PROFILE_TYPES:
                weapon = {
                    'name': profile_data.get('name', 'Unknown'),
                    **profile_data.get('characteristics', {})
                }
                weapons.append(weapon)

        elif link_type == 'rule' and target_id in self._shared_rules:
            rule_name = self._shared_rules[target_id]
            if rule_name and rule_name not in abilities:
                abilities.append(rule_name)

    def _normalize_stat_value(self, value: str) -> Union[int, str]:
        """
        Normalize a stat value, converting to int if possible.

        Args:
            value: Raw stat value string

        Returns:
            Integer if numeric, otherwise original string
        """
        if not value:
            return value

        # Try to parse as integer
        try:
            # Handle values like "3+" or "4+"
            clean = value.rstrip('+').strip()
            if clean.isdigit():
                return int(clean)
        except (ValueError, AttributeError):
            pass

        return value

    def export_to_toml(
        self,
        output_dir: Union[str, Path],
        faction_name: Optional[str] = None
    ) -> Union[Path, list[Path]]:
        """
        Export imported units to TOML format.

        Args:
            output_dir: Directory to write TOML files
            faction_name: Optional faction filter (export only this faction)

        Returns:
            Path to output file/directory

        Raises:
            ValidationError: If no units to export
        """
        if not self.units:
            raise ValidationError("No units to export")

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Group by faction
        by_faction: dict[str, list[ImportedUnit]] = {}
        for unit in self.units:
            faction = unit.faction
            if faction not in by_faction:
                by_faction[faction] = []
            by_faction[faction].append(unit)

        # Write each faction
        output_files: list[Path] = []
        for faction, units in by_faction.items():
            if faction_name and faction.lower() != faction_name.lower():
                continue

            filename = self._sanitize_filename(faction) + ".toml"
            filepath = output_dir / filename

            toml_content = self._units_to_toml(faction, units)

            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(toml_content)

            output_files.append(filepath)
            logger.info(f"Exported {len(units)} units to {filepath}")

        if not output_files:
            raise ValidationError(
                f"No units found for faction: {faction_name}"
            )

        return output_files[0] if len(output_files) == 1 else output_files

    def _sanitize_filename(self, name: str) -> str:
        """
        Sanitize a string for use as a filename.

        Args:
            name: Original string

        Returns:
            Safe filename string
        """
        # Replace problematic characters
        safe = name.lower()
        safe = re.sub(r'[<>:"/\\|?*]', '_', safe)
        safe = re.sub(r'\s+', '_', safe)
        safe = re.sub(r'_+', '_', safe)
        safe = safe.strip('_')
        return safe or 'unknown'

    def _units_to_toml(self, faction: str, units: list[ImportedUnit]) -> str:
        """
        Convert units to TOML string.

        Args:
            faction: Faction name for header
            units: List of units to convert

        Returns:
            TOML-formatted string
        """
        lines = [
            f'# Faction data imported from BSData/BattleScribe',
            f'# Source: {units[0].source_file if units else "unknown"}',
            f'',
            f'name = "{self._escape_toml_string(faction)}"',
            f'description = "Imported from BSData"',
            f'',
        ]

        for unit in units:
            lines.extend(self._unit_to_toml_lines(unit))

        return '\n'.join(lines)

    def _unit_to_toml_lines(self, unit: ImportedUnit) -> list[str]:
        """
        Convert a single unit to TOML lines.

        Args:
            unit: Unit to convert

        Returns:
            List of TOML lines
        """
        lines = [
            '[[units]]',
            f'name = "{self._escape_toml_string(unit.name)}"',
            f'type = "{unit._infer_unit_type()}"',
            f'points = {unit.points}',
            f'models = "{unit.models}"',
        ]

        if unit.abilities:
            abilities_str = ', '.join(
                f'"{self._escape_toml_string(a)}"' for a in unit.abilities
            )
            lines.append(f'special_rules = [{abilities_str}]')

        if unit.keywords:
            keywords_str = ', '.join(
                f'"{self._escape_toml_string(k)}"' for k in unit.keywords
            )
            lines.append(f'keywords = [{keywords_str}]')

        # Stats section
        if unit.stats:
            lines.append('')
            lines.append('[units.stats]')
            for stat, value in unit.stats.items():
                clean_stat = self._clean_toml_key(stat)
                if isinstance(value, int):
                    lines.append(f'{clean_stat} = {value}')
                else:
                    lines.append(f'{clean_stat} = "{self._escape_toml_string(str(value))}"')

        # Weapons section
        for weapon in unit.weapons:
            lines.append('')
            lines.append('[[units.weapons]]')
            for key, value in weapon.items():
                clean_key = self._clean_toml_key(key)
                if isinstance(value, list):
                    val_str = ', '.join(
                        f'"{self._escape_toml_string(str(v))}"' for v in value
                    )
                    lines.append(f'{clean_key} = [{val_str}]')
                elif isinstance(value, int):
                    lines.append(f'{clean_key} = {value}')
                else:
                    lines.append(f'{clean_key} = "{self._escape_toml_string(str(value))}"')

        lines.append('')
        return lines

    def _escape_toml_string(self, s: str) -> str:
        """
        Escape a string for TOML.

        Args:
            s: String to escape

        Returns:
            Escaped string
        """
        return s.replace('\\', '\\\\').replace('"', '\\"')

    def _clean_toml_key(self, key: str) -> str:
        """
        Clean a string for use as a TOML key.

        Args:
            key: Original key string

        Returns:
            Clean TOML key
        """
        clean = key.replace(' ', '_').replace('+', '_plus').replace('-', '_')
        clean = re.sub(r'[^a-zA-Z0-9_]', '', clean)
        clean = re.sub(r'_+', '_', clean)
        clean = clean.strip('_').lower()

        # Ensure key doesn't start with a number
        if clean and clean[0].isdigit():
            clean = '_' + clean

        return clean or 'unknown'

    def clear(self) -> None:
        """Clear all imported data."""
        self.units.clear()
        self.rules.clear()
        self.profiles.clear()
        self._shared_profiles.clear()
        self._shared_rules.clear()


class NewRecruitImporter:
    """
    Imports army lists from New Recruit JSON exports.

    New Recruit is a mobile army builder app that can export rosters as JSON.

    Example:
        >>> importer = NewRecruitImporter()
        >>> units = importer.import_file(Path("my_army.json"))
    """

    def __init__(self):
        """Initialize the importer."""
        self.units: list[ImportedUnit] = []

    def import_file(self, filepath: Union[str, Path]) -> list[ImportedUnit]:
        """
        Import a New Recruit JSON export.

        Args:
            filepath: Path to JSON file

        Returns:
            List of ImportedUnit objects

        Raises:
            FileNotFoundError: If file doesn't exist
            ParseError: If JSON parsing fails
        """
        filepath = Path(filepath)

        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {filepath}")

        if not filepath.suffix.lower() == '.json':
            raise FileFormatError(
                f"Expected .json file, got: {filepath.suffix}"
            )

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ParseError(f"Failed to parse JSON: {e}") from e

        return self._parse_roster(data, str(filepath))

    def _parse_roster(
        self,
        data: dict[str, Any],
        source: str
    ) -> list[ImportedUnit]:
        """
        Parse a New Recruit roster structure.

        Args:
            data: Parsed JSON data
            source: Source filename

        Returns:
            List of imported units
        """
        units: list[ImportedUnit] = []

        # Handle different possible structures
        forces = data.get('forces', [])
        if not forces:
            # Try alternate structure
            forces = data.get('roster', {}).get('forces', [])

        for force in forces:
            faction = self._extract_faction_name(force)

            selections = force.get('selections', [])
            if not selections:
                selections = force.get('units', [])

            for selection in selections:
                unit = self._parse_selection(selection, faction, source)
                if unit:
                    units.append(unit)

        # Handle flat unit list
        if not units and 'units' in data:
            faction = data.get('faction', data.get('army', 'Unknown'))
            for selection in data['units']:
                unit = self._parse_selection(selection, faction, source)
                if unit:
                    units.append(unit)

        self.units.extend(units)
        logger.info(f"Imported {len(units)} units from {source}")

        return units

    def _extract_faction_name(self, force: dict[str, Any]) -> str:
        """
        Extract faction name from force data.

        Args:
            force: Force dictionary

        Returns:
            Faction name string
        """
        # Try various possible locations
        if 'catalogue' in force and isinstance(force['catalogue'], dict):
            return force['catalogue'].get('name', 'Unknown')

        return force.get('faction', force.get('catalogueName', 'Unknown'))

    def _parse_selection(
        self,
        selection: dict[str, Any],
        faction: str,
        source: str
    ) -> Optional[ImportedUnit]:
        """
        Parse a selection entry.

        Args:
            selection: Selection dictionary
            faction: Faction name
            source: Source filename

        Returns:
            ImportedUnit or None
        """
        name = selection.get('name', selection.get('unit_name', 'Unknown'))

        if not name or name == 'Unknown':
            return None

        stats: dict[str, Any] = {}
        weapons: list[dict[str, Any]] = []
        abilities: list[str] = []
        keywords: list[str] = []

        # Parse profiles
        for profile in selection.get('profiles', []):
            profile_type = profile.get('typeName', profile.get('type', ''))

            if profile_type.lower() in ('unit', 'model', ''):
                for char in profile.get('characteristics', []):
                    char_name = char.get('name', '')
                    char_value = char.get('value', '')
                    if char_name:
                        stats[char_name] = char_value

            elif 'weapon' in profile_type.lower():
                weapon = {'name': profile.get('name', 'Unknown')}
                for char in profile.get('characteristics', []):
                    key = char.get('name', '').lower()
                    value = char.get('value', '')
                    if key:
                        weapon[key] = value
                weapons.append(weapon)

        # Parse abilities
        for ability in selection.get('abilities', []):
            if isinstance(ability, dict):
                ability_name = ability.get('name', '')
            else:
                ability_name = str(ability)

            if ability_name and ability_name not in abilities:
                abilities.append(ability_name)

        # Parse keywords
        for kw in selection.get('keywords', []):
            if isinstance(kw, dict):
                kw_name = kw.get('name', '')
            else:
                kw_name = str(kw)

            if kw_name and kw_name not in keywords:
                keywords.append(kw_name)

        # Extract points
        points = self._extract_points(selection)

        # Extract model count
        models = str(selection.get('models', selection.get('count', 1)))

        return ImportedUnit(
            name=name,
            faction=faction,
            stats=stats,
            weapons=weapons,
            abilities=abilities,
            keywords=keywords,
            points=points,
            models=models,
            source_file=source,
        )

    def _extract_points(self, selection: dict[str, Any]) -> int:
        """
        Extract points cost from selection.

        Args:
            selection: Selection dictionary

        Returns:
            Points value
        """
        # Try various possible locations
        if 'costs' in selection:
            costs = selection['costs']
            if isinstance(costs, dict):
                pts = costs.get('pts', costs.get('points', 0))
            else:
                pts = 0
        else:
            pts = selection.get('points', selection.get('cost', 0))

        try:
            return int(float(pts))
        except (ValueError, TypeError):
            return 0

    def clear(self) -> None:
        """Clear all imported data."""
        self.units.clear()


class TOMLImporter:
    """
    Imports units from custom TOML format.

    This is the native format used by Oracle for storing game data.

    Example:
        >>> importer = TOMLImporter()
        >>> units = importer.import_file(Path("factions/space_marines.toml"))
    """

    def __init__(self):
        """Initialize the importer."""
        self.units: list[ImportedUnit] = []

    def import_file(self, filepath: Union[str, Path]) -> list[ImportedUnit]:
        """
        Import units from a TOML file.

        Args:
            filepath: Path to TOML file

        Returns:
            List of ImportedUnit objects

        Raises:
            FileNotFoundError: If file doesn't exist
            ParseError: If TOML parsing fails
            ImportError: If tomllib/tomli not available
        """
        if tomllib is None:
            raise ImportError(
                "TOML support requires Python 3.11+ or 'tomli' package. "
                "Install with: pip install tomli"
            )

        filepath = Path(filepath)

        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {filepath}")

        if filepath.suffix.lower() != '.toml':
            raise FileFormatError(
                f"Expected .toml file, got: {filepath.suffix}"
            )

        try:
            with open(filepath, 'rb') as f:
                data = tomllib.load(f)
        except Exception as e:
            raise ParseError(f"Failed to parse TOML: {e}") from e

        return self._parse_toml(data, str(filepath))

    def _parse_toml(
        self,
        data: dict[str, Any],
        source: str
    ) -> list[ImportedUnit]:
        """
        Parse TOML data structure.

        Args:
            data: Parsed TOML data
            source: Source filename

        Returns:
            List of imported units
        """
        units: list[ImportedUnit] = []

        faction = data.get('name', data.get('faction', 'Unknown'))

        for unit_data in data.get('units', []):
            unit = ImportedUnit(
                name=unit_data.get('name', 'Unknown'),
                faction=faction,
                stats=unit_data.get('stats', {}),
                weapons=unit_data.get('weapons', []),
                abilities=unit_data.get('special_rules', []),
                keywords=unit_data.get('keywords', []),
                points=unit_data.get('points', 0),
                models=str(unit_data.get('models', 1)),
                source_file=source,
                unit_type=unit_data.get('type', 'infantry'),
            )
            units.append(unit)

        self.units.extend(units)
        logger.info(f"Imported {len(units)} units from {source}")

        return units

    def clear(self) -> None:
        """Clear all imported data."""
        self.units.clear()


# =============================================================================
# Module-level convenience functions
# =============================================================================

def import_bsdata(filepath: Union[str, Path]) -> list[ImportedUnit]:
    """
    Import a BSData/BattleScribe file.

    Args:
        filepath: Path to .cat, .gst, .catz, or .gstz file

    Returns:
        List of ImportedUnit objects
    """
    importer = BSDataImporter()
    return importer.import_file(filepath)


def import_newrecruit(filepath: Union[str, Path]) -> list[ImportedUnit]:
    """
    Import a New Recruit JSON export.

    Args:
        filepath: Path to JSON file

    Returns:
        List of ImportedUnit objects
    """
    importer = NewRecruitImporter()
    return importer.import_file(filepath)


def import_toml(filepath: Union[str, Path]) -> list[ImportedUnit]:
    """
    Import units from a TOML file.

    Args:
        filepath: Path to TOML file

    Returns:
        List of ImportedUnit objects
    """
    importer = TOMLImporter()
    return importer.import_file(filepath)


def export_to_toml(
    units: list[ImportedUnit],
    output_dir: Union[str, Path],
    faction_name: Optional[str] = None
) -> Union[Path, list[Path]]:
    """
    Export imported units to TOML format.

    Args:
        units: List of units to export
        output_dir: Directory to write TOML files
        faction_name: Optional faction filter

    Returns:
        Path to output file(s)
    """
    importer = BSDataImporter()
    importer.units = units
    return importer.export_to_toml(output_dir, faction_name)


def auto_import(filepath: Union[str, Path]) -> list[ImportedUnit]:
    """
    Automatically detect file format and import.

    Args:
        filepath: Path to import file

    Returns:
        List of ImportedUnit objects

    Raises:
        FileFormatError: If format cannot be detected
    """
    filepath = Path(filepath)
    suffix = filepath.suffix.lower()

    if suffix in ['.cat', '.gst', '.catz', '.gstz']:
        return import_bsdata(filepath)
    elif suffix == '.json':
        return import_newrecruit(filepath)
    elif suffix == '.toml':
        return import_toml(filepath)
    else:
        raise FileFormatError(
            f"Cannot auto-detect format for: {suffix}. "
            f"Supported: .cat, .gst, .catz, .gstz, .json, .toml"
        )


# =============================================================================
# PDF Import Support
# =============================================================================

@dataclass
class PDFTable:
    """
    A table extracted from a PDF, potentially a random roll table.

    Attributes:
        title: Detected table title/header
        rows: List of row data (each row is a list of cell strings)
        page: Page number where table was found
        die_type: Detected die type if this is a roll table (d6, d20, d100, etc.)
        is_roll_table: Whether this appears to be a random roll table
        table_type: Classification of table type:
            - 'roll': Has dice notation (d6, d20, etc.) or "Roll" column with results
            - 'stat': Has game stat column headers (M, WS, BS, S, T, W for Warhammer;
                      AC, HP, STR, DEX for D&D)
            - 'reference': Lookup tables, price lists, equipment lists
            - 'unknown': Anything else or filtered content (TOC, version history)
    """
    title: str = ""
    rows: list[list[str]] = field(default_factory=list)
    page: int = 0
    die_type: str = ""
    is_roll_table: bool = False
    table_type: str = "unknown"  # 'roll', 'stat', 'reference', 'unknown'

    def to_oracle_table(self) -> dict[str, Any]:
        """Convert to Oracle table format for TOML export."""
        entries = []
        for row in self.rows:
            if len(row) >= 2:
                # First column is roll/number, rest is result
                roll_val = row[0].strip()
                result = " ".join(row[1:]).strip()
                if result:
                    entries.append({"roll": roll_val, "result": result})
            elif len(row) == 1 and row[0].strip():
                entries.append({"result": row[0].strip()})

        return {
            "name": self.title or "Unnamed Table",
            "die": self.die_type or "d20",
            "entries": entries
        }


@dataclass
class PDFPage:
    """
    Content extracted from a single PDF page.

    Attributes:
        number: 1-indexed page number
        text: Raw extracted text
        tables: Tables found on this page
        headings: Detected section headings
        needs_ocr: Whether this page may need OCR (has images but little text)
        has_images: Whether this page contains images
    """
    number: int
    text: str = ""
    tables: list[PDFTable] = field(default_factory=list)
    headings: list[str] = field(default_factory=list)
    needs_ocr: bool = False
    has_images: bool = False


@dataclass
class PDFContent:
    """
    Complete content extracted from a PDF.

    Attributes:
        filename: Original filename
        title: Document title (from metadata or first heading)
        pages: List of extracted pages
        total_pages: Total page count in document
        tables: All tables found across all pages
        metadata: PDF metadata (author, subject, etc.)
    """
    filename: str
    title: str = ""
    pages: list[PDFPage] = field(default_factory=list)
    total_pages: int = 0
    tables: list[PDFTable] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)

    def get_all_text(self) -> str:
        """Get all text content concatenated."""
        return "\n\n".join(page.text for page in self.pages)

    def get_roll_tables(self) -> list[PDFTable]:
        """Get only tables that appear to be random roll tables."""
        return [t for t in self.tables if t.is_roll_table]

    def get_stat_tables(self) -> list[PDFTable]:
        """Get only tables that appear to be stat blocks."""
        return [t for t in self.tables if t.table_type == "stat"]

    def get_reference_tables(self) -> list[PDFTable]:
        """Get only tables classified as reference tables."""
        return [t for t in self.tables if t.table_type == "reference"]

    def get_tables_by_type(self, table_type: str) -> list[PDFTable]:
        """
        Get tables filtered by type.

        Args:
            table_type: One of 'roll', 'stat', 'reference', 'unknown'

        Returns:
            List of PDFTable objects matching the specified type
        """
        return [t for t in self.tables if t.table_type == table_type]

    def suggest_ocr(self) -> bool:
        """
        Check if OCR might improve text extraction for this document.

        Returns:
            True if OCR is recommended (pages have images but little text)
        """
        if not self.pages:
            return False

        pages_needing_ocr = sum(1 for page in self.pages if page.needs_ocr)
        # Suggest OCR if more than 30% of pages might need it
        return pages_needing_ocr > len(self.pages) * 0.3

    def get_pages_needing_ocr(self) -> list[int]:
        """Get list of page numbers that may benefit from OCR."""
        return [page.number for page in self.pages if page.needs_ocr]

    def export_tables_to_toml(self, output_path: Union[str, Path]) -> Path:
        """Export all roll tables to TOML format."""
        output_path = Path(output_path)

        roll_tables = self.get_roll_tables()
        if not roll_tables:
            raise ValidationError("No roll tables found in PDF")

        lines = [
            f'# Tables extracted from: {self.filename}',
            f'# Title: {self.title}',
            f'# Total tables: {len(roll_tables)}',
            '',
        ]

        for table in roll_tables:
            oracle_data = table.to_oracle_table()
            lines.append(f'[[tables]]')
            lines.append(f'name = "{oracle_data["name"]}"')
            lines.append(f'die = "{oracle_data["die"]}"')
            lines.append('')

            for entry in oracle_data["entries"]:
                lines.append('[[tables.entries]]')
                if "roll" in entry:
                    lines.append(f'roll = "{entry["roll"]}"')
                lines.append(f'result = "{entry["result"]}"')
                lines.append('')

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

        return output_path

    def save_tables(self, output_dir: Union[str, Path]) -> Path:
        """
        Save all tables organized by type to separate TOML files.

        Creates a folder structure like:
            oracle/data/imports/{pdf_name}/
                roll_tables.toml
                stat_tables.toml
                reference_tables.toml
                all_tables.toml

        Args:
            output_dir: Base directory for imports (e.g., 'oracle/data/imports')

        Returns:
            Path to the created folder containing the TOML files

        Raises:
            ValidationError: If no tables found in PDF
        """
        if not self.tables:
            raise ValidationError("No tables found in PDF")

        output_dir = Path(output_dir)

        # Create folder named after the PDF (sanitize filename)
        pdf_name = Path(self.filename).stem
        safe_name = re.sub(r'[<>:"/\\|?*]', '_', pdf_name)
        safe_name = re.sub(r'\s+', '_', safe_name).lower()
        folder_path = output_dir / safe_name
        folder_path.mkdir(parents=True, exist_ok=True)

        files_created = []

        # Helper to escape TOML strings
        def escape_toml(s: str) -> str:
            return s.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')

        # Group tables by type
        tables_by_type: dict[str, list[PDFTable]] = {
            'roll': [],
            'stat': [],
            'reference': [],
            'unknown': []
        }

        for table in self.tables:
            tables_by_type.get(table.table_type, tables_by_type['unknown']).append(table)

        # Save roll tables
        if tables_by_type['roll']:
            roll_path = folder_path / "roll_tables.toml"
            lines = [
                f'# Roll tables extracted from: {self.filename}',
                f'# Total: {len(tables_by_type["roll"])}',
                '',
            ]
            for table in tables_by_type['roll']:
                lines.append('[[tables]]')
                lines.append(f'name = "{escape_toml(table.title or "Unnamed Table")}"')
                lines.append(f'die = "{table.die_type or "d20"}"')
                lines.append(f'page = {table.page}')
                lines.append('')
                for row in table.rows:
                    if len(row) >= 2:
                        lines.append('[[tables.entries]]')
                        lines.append(f'roll = "{escape_toml(row[0])}"')
                        lines.append(f'result = "{escape_toml(" ".join(row[1:]))}"')
                        lines.append('')
            with open(roll_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))
            files_created.append(roll_path)

        # Save stat tables
        if tables_by_type['stat']:
            stat_path = folder_path / "stat_tables.toml"
            lines = [
                f'# Stat tables extracted from: {self.filename}',
                f'# Total: {len(tables_by_type["stat"])}',
                '',
            ]
            for table in tables_by_type['stat']:
                lines.append('[[stat_blocks]]')
                lines.append(f'name = "{escape_toml(table.title or "Unnamed Stat Block")}"')
                lines.append(f'page = {table.page}')
                # First row is likely headers
                if table.rows:
                    headers = [escape_toml(h) for h in table.rows[0] if h]
                    headers_str = ", ".join(f'"{h}"' for h in headers)
                    lines.append(f'headers = [{headers_str}]')
                lines.append('')
                for i, row in enumerate(table.rows[1:], 1):
                    lines.append(f'[[stat_blocks.entries]]')
                    for j, cell in enumerate(row):
                        if cell and j < len(table.rows[0]) and table.rows[0][j]:
                            col_name = re.sub(r'[^a-zA-Z0-9_]', '_', table.rows[0][j].lower())
                            lines.append(f'{col_name} = "{escape_toml(cell)}"')
                    lines.append('')
            with open(stat_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))
            files_created.append(stat_path)

        # Save reference tables
        if tables_by_type['reference']:
            ref_path = folder_path / "reference_tables.toml"
            lines = [
                f'# Reference tables extracted from: {self.filename}',
                f'# Total: {len(tables_by_type["reference"])}',
                '',
            ]
            for table in tables_by_type['reference']:
                lines.append('[[references]]')
                lines.append(f'name = "{escape_toml(table.title or "Unnamed Reference")}"')
                lines.append(f'page = {table.page}')
                lines.append('')
                for row in table.rows:
                    if row:
                        lines.append('[[references.entries]]')
                        data_str = ", ".join(f'"{escape_toml(cell)}"' for cell in row if cell)
                        lines.append(f'data = [{data_str}]')
                        lines.append('')
            with open(ref_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))
            files_created.append(ref_path)

        # Save summary of all tables
        summary_path = folder_path / "summary.toml"
        lines = [
            f'# Table extraction summary for: {self.filename}',
            f'# Title: {self.title}',
            '',
            '[source]',
            f'filename = "{escape_toml(self.filename)}"',
            f'title = "{escape_toml(self.title)}"',
            f'total_pages = {self.total_pages}',
            '',
            '[counts]',
            f'roll_tables = {len(tables_by_type["roll"])}',
            f'stat_tables = {len(tables_by_type["stat"])}',
            f'reference_tables = {len(tables_by_type["reference"])}',
            f'unknown_tables = {len(tables_by_type["unknown"])}',
            f'total = {len(self.tables)}',
            '',
        ]
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        files_created.append(summary_path)

        logger.info(f"Saved {len(files_created)} files to {folder_path}")
        return folder_path


from typing import Callable

class PDFImporter:
    """
    Imports content from PDF files with chunked processing for large files.

    Features:
    - Page-by-page extraction (memory efficient)
    - Table detection with roll table recognition
    - Stat block detection (Warhammer, D&D)
    - OCR support for scanned/image-based PDFs
    - Progress callbacks for UI integration
    - Configurable page limits

    Example:
        >>> importer = PDFImporter()
        >>> content = importer.import_file("rulebook.pdf", max_pages=100)
        >>> print(f"Found {len(content.tables)} tables")
        >>> content.export_tables_to_toml("output/tables.toml")

        # With progress callback
        >>> def on_progress(current, total, message):
        ...     print(f"[{current}/{total}] {message}")
        >>> content = importer.import_file("big.pdf", progress_callback=on_progress)

        # With OCR for scanned documents
        >>> content = importer.import_file("scanned.pdf", use_ocr=True)
    """

    # Patterns for detecting roll tables
    DIE_PATTERNS = [
        (r'\bd(\d+)\b', lambda m: f"d{m.group(1)}"),  # d6, d20, d100
        (r'\b(\d+)d(\d+)\b', lambda m: f"{m.group(1)}d{m.group(2)}"),  # 2d6, 3d10
        (r'\b1-(\d+)\b', lambda m: f"d{m.group(1)}"),  # 1-6, 1-20, 1-100
    ]

    # Patterns suggesting a roll table header
    TABLE_HEADER_PATTERNS = [
        r'roll\s+result',
        r'd\d+\s+',
        r'table\s*:',
        r'random\s+',
        r'\d+[-–]\d+\s+',
    ]

    # Warhammer stat table headers (various editions)
    WARHAMMER_STAT_HEADERS = ["M", "WS", "BS", "S", "T", "W", "I", "A", "Ld", "Sv"]

    # D&D/5e stat table headers
    DND_STAT_HEADERS = ["AC", "HP", "STR", "DEX", "CON", "INT", "WIS", "CHA"]

    # Alternative D&D headers (ability scores only)
    DND_ABILITY_HEADERS = ["STR", "DEX", "CON", "INT", "WIS", "CHA"]

    # Patterns to filter out TOC (Table of Contents)
    TOC_INDICATORS = [
        r'table\s+of\s+contents',
        r'contents',
        r'^\s*chapter\s+\d+',
        r'^\s*section\s+\d+',
        r'^\s*appendix\s+[a-z]',
    ]

    # Patterns to filter out version history tables
    VERSION_HISTORY_INDICATORS = [
        r'version\s+history',
        r'revision\s+history',
        r'change\s*log',
        r'^\s*version\s*$',
        r'^\s*date\s*$',
        r'^\s*author\s*$',
        r'^\s*changes?\s*$',
    ]

    # Reference table indicators (equipment, prices, etc.)
    REFERENCE_INDICATORS = [
        r'price',
        r'cost',
        r'weight',
        r'equipment',
        r'weapons?\s+list',
        r'armor\s+list',
        r'items?\s+list',
        r'spell\s+list',
        r'skills?\s+list',
    ]

    # Minimum text length to consider a page as having useful text
    MIN_TEXT_LENGTH = 100

    def __init__(self):
        """Initialize the PDF importer."""
        if fitz is None:
            raise ImportError(
                "PDF support requires PyMuPDF. Install with: pip install pymupdf"
            )
        self.content: Optional[PDFContent] = None

    def import_file(
        self,
        filepath: Union[str, Path],
        max_pages: Optional[int] = None,
        start_page: int = 0,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        use_ocr: bool = False,
        ocr_language: str = "eng",
        timeout: Optional[int] = None
    ) -> PDFContent:
        """
        Import content from a PDF file.

        Args:
            filepath: Path to PDF file
            max_pages: Maximum pages to process (None = all)
            start_page: Page to start from (0-indexed)
            progress_callback: Optional callback(current, total, message)
            use_ocr: Enable OCR for scanned/image-based PDFs
            ocr_language: Tesseract language code (default: "eng")
            timeout: Optional timeout in seconds for processing

        Returns:
            PDFContent with extracted text and tables

        Raises:
            FileNotFoundError: If file doesn't exist
            FileFormatError: If not a valid PDF
            ParseError: If extraction fails
            OCRNotAvailableError: If OCR requested but Tesseract not installed
            EncryptedPDFError: If PDF is encrypted/password-protected
        """
        filepath = Path(filepath)

        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {filepath}")

        if filepath.suffix.lower() != '.pdf':
            raise FileFormatError(f"Expected .pdf file, got: {filepath.suffix}")

        # Check file size and warn if very large
        file_size = filepath.stat().st_size
        if file_size > MAX_RECOMMENDED_FILE_SIZE:
            size_mb = file_size / (1024 * 1024)
            logger.warning(
                f"Large PDF file ({size_mb:.1f}MB). Consider using max_pages "
                f"parameter to limit processing. This may take a while."
            )

        # Validate OCR availability if requested
        if use_ocr:
            if not PYTESSERACT_AVAILABLE:
                raise OCRNotAvailableError(
                    "OCR requested but pytesseract is not installed." + OCR_INSTALL_MESSAGE
                )
            # Test if Tesseract is actually available
            try:
                pytesseract.get_tesseract_version()
            except Exception as e:
                raise OCRNotAvailableError(
                    f"Tesseract not found or not working: {e}" + OCR_INSTALL_MESSAGE
                )

        try:
            doc = fitz.open(filepath)
        except Exception as e:
            raise FileFormatError(f"Cannot open PDF: {e}") from e

        try:
            # Check for encryption
            if doc.is_encrypted:
                doc.close()
                raise EncryptedPDFError(
                    f"PDF is encrypted/password-protected: {filepath}. "
                    f"Please provide an unencrypted version."
                )

            return self._extract_content(
                doc, filepath.name, max_pages, start_page, progress_callback,
                use_ocr=use_ocr, ocr_language=ocr_language
            )
        finally:
            doc.close()

    def _extract_content(
        self,
        doc: Any,  # fitz.Document
        filename: str,
        max_pages: Optional[int],
        start_page: int,
        progress_callback: Optional[Callable[[int, int, str], None]],
        use_ocr: bool = False,
        ocr_language: str = "eng"
    ) -> PDFContent:
        """Extract content from opened PDF document."""
        total_pages = len(doc)
        end_page = total_pages if max_pages is None else min(start_page + max_pages, total_pages)

        # Get metadata
        metadata = {}
        if doc.metadata:
            for key in ['title', 'author', 'subject', 'keywords', 'creator']:
                if doc.metadata.get(key):
                    metadata[key] = doc.metadata[key]

        title = metadata.get('title', '')

        content = PDFContent(
            filename=filename,
            title=title,
            total_pages=total_pages,
            metadata=metadata
        )

        pages_to_process = end_page - start_page
        ocr_prefix = "[OCR] " if use_ocr else ""
        logger.info(f"{ocr_prefix}Processing {pages_to_process} pages from {filename}")

        for i, page_num in enumerate(range(start_page, end_page)):
            if progress_callback:
                progress_callback(i + 1, pages_to_process, f"{ocr_prefix}Extracting page {page_num + 1}")

            try:
                page = doc[page_num]
                pdf_page = self._extract_page(
                    page, page_num + 1,
                    use_ocr=use_ocr, ocr_language=ocr_language,
                    progress_callback=progress_callback,
                    current_page=i + 1, total_pages=pages_to_process
                )
                content.pages.append(pdf_page)

                # Collect tables
                content.tables.extend(pdf_page.tables)

                # Try to get title from first page if not in metadata
                if not content.title and page_num == 0 and pdf_page.headings:
                    content.title = pdf_page.headings[0]

            except Exception as e:
                logger.warning(f"Error extracting page {page_num + 1}: {e}")
                # Continue with other pages - don't fail the whole import
                content.pages.append(PDFPage(number=page_num + 1, text=f"[Error: {e}]"))

        if progress_callback:
            progress_callback(pages_to_process, pages_to_process, f"{ocr_prefix}Extraction complete")

        logger.info(f"Extracted {len(content.pages)} pages, {len(content.tables)} tables")
        return content

    def _extract_page(
        self,
        page: Any,
        page_num: int,
        use_ocr: bool = False,
        ocr_language: str = "eng",
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        current_page: int = 0,
        total_pages: int = 0
    ) -> PDFPage:
        """Extract content from a single page."""
        # Get text with layout preservation
        text = page.get_text("text")

        # Check if page has images
        has_images = len(page.get_images()) > 0

        # Determine if this page needs OCR
        needs_ocr = has_images and len(text.strip()) < self.MIN_TEXT_LENGTH

        # Use OCR if requested and beneficial
        if use_ocr and (needs_ocr or len(text.strip()) < self.MIN_TEXT_LENGTH):
            if progress_callback and current_page and total_pages:
                progress_callback(
                    current_page, total_pages,
                    f"[OCR] Running OCR on page {page_num}..."
                )
            ocr_text = self._extract_page_with_ocr(page, ocr_language)
            if ocr_text and len(ocr_text.strip()) > len(text.strip()):
                text = ocr_text
                if progress_callback and current_page and total_pages:
                    progress_callback(
                        current_page, total_pages,
                        f"[OCR] Page {page_num} extracted ({len(text)} chars)"
                    )

        # Detect headings (larger text, bold, etc.)
        headings = self._detect_headings(page)

        # Detect tables (pass headings for title detection)
        tables = self._detect_tables(page, text, page_num, headings)

        return PDFPage(
            number=page_num,
            text=text,
            tables=tables,
            headings=headings,
            needs_ocr=needs_ocr,
            has_images=has_images
        )

    def _extract_page_with_ocr(self, page: Any, language: str = "eng") -> str:
        """
        Extract text from a page using OCR.

        Args:
            page: PyMuPDF page object
            language: Tesseract language code

        Returns:
            Extracted text from OCR
        """
        if not PYTESSERACT_AVAILABLE:
            return ""

        try:
            # Convert page to image at higher resolution for better OCR
            # Use 300 DPI for good OCR quality
            mat = fitz.Matrix(300 / 72, 300 / 72)  # Scale factor for 300 DPI
            pixmap = page.get_pixmap(matrix=mat)

            # Convert to PIL Image
            img_data = pixmap.tobytes("png")
            image = Image.open(io.BytesIO(img_data))

            # Run OCR
            text = pytesseract.image_to_string(image, lang=language)

            return text.strip()

        except Exception as e:
            logger.warning(f"OCR failed for page: {e}")
            return ""

    def _detect_headings(self, page: Any) -> list[str]:
        """Detect section headings on a page."""
        headings = []

        try:
            blocks = page.get_text("dict")["blocks"]
            for block in blocks:
                if block.get("type") == 0:  # Text block
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            # Look for larger or bold text
                            size = span.get("size", 12)
                            flags = span.get("flags", 0)
                            text = span.get("text", "").strip()

                            # Bold flag is 2^4 = 16
                            is_bold = flags & 16
                            is_large = size >= 14

                            if text and (is_bold or is_large) and len(text) > 3:
                                headings.append(text)
        except Exception as e:
            logger.debug(f"Heading detection failed: {e}")

        return headings[:10]  # Limit to first 10

    def _detect_tables(
        self,
        page: Any,
        text: str,
        page_num: int,
        headings: Optional[list[str]] = None
    ) -> list[PDFTable]:
        """
        Detect and extract tables from a page.

        Args:
            page: PyMuPDF page object
            text: Extracted text from page
            page_num: Page number
            headings: Detected headings on this page for title detection
        """
        tables = []

        # Try to find tables using PyMuPDF's table detection
        try:
            page_tables = page.find_tables()
            for table in page_tables:
                extracted = table.extract()
                if extracted and len(extracted) > 1:
                    pdf_table = self._process_table(extracted, page_num, headings)
                    if pdf_table:
                        tables.append(pdf_table)
        except Exception as e:
            logger.debug(f"Table detection failed: {e}")

        # Also try to detect tables from text patterns
        text_tables = self._detect_text_tables(text, page_num)
        tables.extend(text_tables)

        return tables

    def _is_stat_table(self, header: list[str]) -> tuple[bool, str]:
        """
        Check if header row matches known stat table formats.

        Args:
            header: List of header cell strings

        Returns:
            Tuple of (is_stat_table, stat_system)
        """
        # Normalize header cells
        normalized = [cell.strip().upper() for cell in header if cell.strip()]

        # Check for Warhammer stats (need at least 5 matching headers)
        wh_matches = sum(1 for h in normalized if h in self.WARHAMMER_STAT_HEADERS)
        if wh_matches >= 5:
            return True, "warhammer"

        # Check for D&D stats (need at least 4 matching headers)
        dnd_matches = sum(1 for h in normalized if h in self.DND_STAT_HEADERS)
        if dnd_matches >= 4:
            return True, "dnd"

        # Check for D&D ability scores (all 6)
        ability_matches = sum(1 for h in normalized if h in self.DND_ABILITY_HEADERS)
        if ability_matches >= 5:
            return True, "dnd_abilities"

        return False, ""

    def _process_table(
        self,
        rows: list[list],
        page_num: int,
        headings: Optional[list[str]] = None
    ) -> Optional[PDFTable]:
        """
        Process extracted table data with improved classification and filtering.

        Args:
            rows: Raw table rows
            page_num: Page number where table was found
            headings: Page headings for title detection

        Returns:
            PDFTable with proper classification, or None if filtered out
        """
        if not rows or len(rows) < 2:
            return None

        # Clean up cells and merge fragmented text
        clean_rows = self._clean_and_merge_cells(rows)

        if len(clean_rows) < 2:
            return None

        # Get header info
        header = clean_rows[0]
        header_text = " ".join(header).lower()
        all_text = " ".join(" ".join(row) for row in clean_rows).lower()

        # Filter out TOC and version history tables
        if self._is_toc_or_version_history(header, clean_rows, all_text):
            logger.debug(f"Filtered out TOC/version history table on page {page_num}")
            return None

        is_roll_table = False
        die_type = ""
        table_type = "unknown"

        # First, check if this is a stat table (Warhammer or D&D)
        is_stat, stat_system = self._is_stat_table(header)
        if is_stat:
            table_type = "stat"
            logger.debug(f"Detected {stat_system} stat table on page {page_num}")

            # Find title for stat tables
            title = self._detect_stat_table_title(header)

            return PDFTable(
                title=title,
                rows=clean_rows,
                page=page_num,
                die_type="",
                is_roll_table=False,
                table_type="stat"
            )

        # Check for roll table - require actual dice notation or Roll column
        first_col = [row[0] for row in clean_rows[1:] if row]

        if self._has_dice_notation_or_roll_column(header_text, first_col):
            is_roll_table = True
            table_type = "roll"
            die_type = self._extract_die_type(header_text, first_col)
        # Only consider numbered sequences if they look like dice ranges
        elif self._looks_like_dice_ranges(first_col):
            is_roll_table = True
            table_type = "roll"
            die_type = self._extract_die_type(header_text, first_col)

        # Check for reference table if not a roll table
        if not is_roll_table and self._is_reference_table(header_text, all_text):
            table_type = "reference"

        # Detect title
        title = self._detect_general_table_title(header, headings)

        return PDFTable(
            title=title,
            rows=clean_rows,
            page=page_num,
            die_type=die_type,
            is_roll_table=is_roll_table,
            table_type=table_type
        )

    def _clean_and_merge_cells(self, rows: list[list]) -> list[list[str]]:
        """Clean cells and merge fragmented text."""
        clean_rows = []
        for row in rows:
            clean_row = [str(cell).strip() if cell else "" for cell in row]
            if not any(clean_row):
                continue

            # Merge adjacent cells that appear fragmented
            merged_row = []
            i = 0
            while i < len(clean_row):
                cell = clean_row[i]
                while i + 1 < len(clean_row):
                    next_cell = clean_row[i + 1]
                    if not cell and next_cell:
                        cell = next_cell
                        i += 1
                    elif cell and next_cell and cell.endswith('-'):
                        cell = cell[:-1] + next_cell
                        i += 1
                    elif (cell and next_cell and len(cell) == 1 and
                          cell.isalpha() and next_cell and next_cell[0].islower()):
                        cell = cell + next_cell
                        i += 1
                    else:
                        break
                if cell:
                    merged_row.append(cell)
                i += 1
            if merged_row:
                clean_rows.append(merged_row)
        return clean_rows

    def _is_toc_or_version_history(
        self, header: list[str], rows: list[list[str]], all_text: str
    ) -> bool:
        """Check if table is a TOC or version history."""
        header_text = " ".join(header).lower()

        # Check TOC indicators
        for pattern in self.TOC_INDICATORS:
            if re.search(pattern, all_text, re.IGNORECASE):
                if len(rows) > 2:
                    last_col = [row[-1] if row else "" for row in rows[1:]]
                    page_nums = [int(v.strip()) for v in last_col if re.match(r'^\d+$', v.strip())]
                    if len(page_nums) >= 3 and page_nums == sorted(page_nums):
                        return True

        # Check version history indicators
        for pattern in self.VERSION_HISTORY_INDICATORS:
            if re.search(pattern, header_text, re.IGNORECASE):
                return True

        header_lower = {h.lower().strip() for h in header if h}
        version_headers = {'version', 'date', 'author', 'changes', 'description'}
        if len(header_lower & version_headers) >= 2:
            return True

        return False

    def _has_dice_notation_or_roll_column(self, header_text: str, first_col: list[str]) -> bool:
        """Check for actual dice notation or Roll/Result column."""
        # Check for Roll/Result column
        if re.search(r'\broll\b', header_text) or re.search(r'\bresult\b', header_text):
            return True

        # Check for dice notation
        combined = header_text + " " + " ".join(first_col)
        for pattern, _ in self.DIE_PATTERNS:
            if re.search(pattern, combined, re.IGNORECASE):
                return True
        return False

    def _looks_like_dice_ranges(self, first_col: list[str]) -> bool:
        """Check if first column has dice roll ranges (1-2, 3-4, etc.)."""
        ranges = []
        for val in first_col:
            match = re.match(r'^(\d+)[-–](\d+)$', val.strip())
            if match:
                ranges.append((int(match.group(1)), int(match.group(2))))
            elif re.match(r'^\d+$', val.strip()):
                num = int(val.strip())
                ranges.append((num, num))

        if len(ranges) < 3:
            return False

        ranges.sort()
        if ranges[0][0] != 1:
            return False

        max_val = max(r[1] for r in ranges)
        if max_val in [4, 6, 8, 10, 12, 20, 100]:
            for i in range(len(ranges) - 1):
                if ranges[i][1] + 1 != ranges[i + 1][0]:
                    return False
            return True
        return False

    def _extract_die_type(self, header_text: str, first_col: list[str]) -> str:
        """Extract die type from table content."""
        combined = header_text + " " + " ".join(first_col)
        for pattern, extractor in self.DIE_PATTERNS:
            match = re.search(pattern, combined, re.IGNORECASE)
            if match:
                return extractor(match)

        try:
            nums = [int(re.search(r'(\d+)', v).group(1)) for v in first_col if re.search(r'\d+', v)]
            if nums:
                max_val = max(nums)
                if max_val <= 4: return "d4"
                elif max_val <= 6: return "d6"
                elif max_val <= 8: return "d8"
                elif max_val <= 10: return "d10"
                elif max_val <= 12: return "d12"
                elif max_val <= 20: return "d20"
                elif max_val <= 100: return "d100"
        except (ValueError, AttributeError):
            pass
        return "d20"

    def _is_reference_table(self, header_text: str, all_text: str) -> bool:
        """Check if table is a reference/lookup table."""
        for pattern in self.REFERENCE_INDICATORS:
            if re.search(pattern, header_text, re.IGNORECASE):
                return True
            if re.search(pattern, all_text[:500], re.IGNORECASE):
                return True
        return False

    def _detect_stat_table_title(self, header: list[str]) -> str:
        """Find title for stat tables from non-stat header columns."""
        all_stat = set(self.WARHAMMER_STAT_HEADERS + self.DND_STAT_HEADERS + self.DND_ABILITY_HEADERS)
        for cell in header:
            cell_clean = cell.strip()
            if cell_clean and cell_clean.upper() not in all_stat:
                if cell_clean.lower() not in ['name', 'unit', 'model']:
                    return cell_clean
        return ""

    def _detect_general_table_title(self, header: list[str], headings: Optional[list[str]]) -> str:
        """Detect title from header or page headings."""
        if len(header) == 1 and header[0]:
            title = header[0].strip()
            if not re.match(r'^(roll|result|d\d+|#|\d+|page)$', title.lower()):
                return title

        if headings:
            for heading in reversed(headings):
                heading = heading.strip()
                if not re.match(r'^(page\s+\d+|chapter\s+\d+|\d+)$', heading.lower()):
                    if len(heading) < 60:
                        return heading
        return ""

    def _detect_text_tables(self, text: str, page_num: int) -> list[PDFTable]:
        """Detect tables from text patterns (for PDFs without proper table structure)."""
        tables = []

        # Look for lines that start with numbers followed by content
        lines = text.split('\n')
        current_table_lines = []
        current_title = ""

        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                # Empty line might end a table
                if len(current_table_lines) >= 3:
                    table = self._parse_text_table(current_table_lines, current_title, page_num)
                    if table:
                        tables.append(table)
                current_table_lines = []
                current_title = ""
                continue

            # Check if line looks like a table row
            if re.match(r'^\d+[-–]?\d*\s*[:\.\)]\s*.+', line) or re.match(r'^\d+[-–]\d+\s+.+', line):
                current_table_lines.append(line)
            elif re.search(r'd\d+|roll|table', line, re.IGNORECASE) and not current_table_lines:
                current_title = line

        # Don't forget last table
        if len(current_table_lines) >= 3:
            table = self._parse_text_table(current_table_lines, current_title, page_num)
            if table:
                tables.append(table)

        return tables

    def _parse_text_table(self, lines: list[str], title: str, page_num: int) -> Optional[PDFTable]:
        """Parse a table from text lines."""
        rows = []
        for line in lines:
            # Try to split on common separators
            parts = re.split(r'\s{2,}|[:\.\)]\s+|(?<=\d)\s+(?=[A-Z])', line, maxsplit=1)
            if len(parts) >= 2:
                rows.append([parts[0].strip(), parts[1].strip()])
            else:
                rows.append([line])

        if len(rows) < 3:
            return None

        # Detect die type
        die_type = "d20"
        first_col = [row[0] for row in rows if row]

        for pattern, extractor in self.DIE_PATTERNS:
            match = re.search(pattern, title + " " + " ".join(first_col), re.IGNORECASE)
            if match:
                die_type = extractor(match)
                break

        return PDFTable(
            title=title,
            rows=rows,
            page=page_num,
            die_type=die_type,
            is_roll_table=True
        )

    def clear(self) -> None:
        """Clear imported content."""
        self.content = None


def import_pdf(
    filepath: Union[str, Path],
    max_pages: Optional[int] = None,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
    use_ocr: bool = False,
    ocr_language: str = "eng"
) -> PDFContent:
    """
    Import content from a PDF file.

    Args:
        filepath: Path to PDF file
        max_pages: Maximum pages to process (None = all)
        progress_callback: Optional callback(current, total, message) for progress
        use_ocr: Enable OCR for scanned/image-based PDFs (requires Tesseract)
        ocr_language: Tesseract language code (default: "eng")

    Returns:
        PDFContent with extracted text and tables

    Raises:
        OCRNotAvailableError: If OCR requested but Tesseract not installed
        EncryptedPDFError: If PDF is encrypted/password-protected

    Example:
        >>> content = import_pdf("dungeon_magazine.pdf")
        >>> print(f"Title: {content.title}")
        >>> print(f"Pages: {content.total_pages}")
        >>> print(f"Roll tables found: {len(content.get_roll_tables())}")

        # With OCR for scanned documents
        >>> content = import_pdf("scanned_rulebook.pdf", use_ocr=True)
        >>> if content.suggest_ocr():
        ...     print("Consider re-running with use_ocr=True for better results")
    """
    importer = PDFImporter()
    return importer.import_file(
        filepath,
        max_pages=max_pages,
        progress_callback=progress_callback,
        use_ocr=use_ocr,
        ocr_language=ocr_language
    )
