"""TUI shell for the Oracle system using prompt_toolkit and rich."""

import json
import shlex
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory
from prompt_toolkit.output import create_output
import sys
import os
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from oracle.dice import roll as dice_roll, DiceResult
from oracle.fate import (
    Oracle,
    Likelihood,
    OracleResult,
    Answer,
)
from oracle.tables import load_table, roll_on, list_tables

# Birthright support (optional - graceful fallback if not present)
try:
    from oracle.windows import open_window_by_name, list_available_windows
    from oracle.birthright_character import (
        BirthrightCharacter, format_character_sheet,
        save_character, load_character, list_characters,
        BloodlineStrength, Culture
    )
    BIRTHRIGHT_AVAILABLE = True
except ImportError:
    BIRTHRIGHT_AVAILABLE = False


class Mode(Enum):
    """Operating mode for the oracle."""
    RPG = "rpg"
    WARGAME = "wargame"


class Doctrine(Enum):
    """AI tactical doctrine types."""
    AGGRESSIVE = "aggressive"
    DEFENSIVE = "defensive"
    BALANCED = "balanced"
    GUERRILLA = "guerrilla"
    BLITZ = "blitz"


class Scale(Enum):
    """Battle scale for wargame mode."""
    SKIRMISH = "skirmish"      # Squad level
    TACTICAL = "tactical"      # Platoon/Company
    OPERATIONAL = "operational"  # Battalion/Regiment
    STRATEGIC = "strategic"     # Division+


@dataclass
class Mood:
    """Current narrative/tactical mood aspects."""
    tension: int = 5       # 1-10, affects random event likelihood
    horror: int = 3        # 1-10, affects complication severity
    action: int = 5        # 1-10, affects encounter intensity
    mystery: int = 5       # 1-10, affects clue/revelation frequency

    def to_dict(self) -> dict:
        return {
            "tension": self.tension,
            "horror": self.horror,
            "action": self.action,
            "mystery": self.mystery,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Mood":
        return cls(**data)


@dataclass
class SessionState:
    """Persistent session state."""
    mode: Mode = Mode.RPG
    setting: str = "fantasy"
    chaos: int = 5
    mood: Mood = field(default_factory=Mood)
    scenes: list[dict] = field(default_factory=list)
    threads: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    npcs: list[dict] = field(default_factory=list)
    # Wargame-specific
    aggression: int = 5      # 1-10
    doctrine: Doctrine = Doctrine.BALANCED
    scale: Scale = Scale.TACTICAL

    def to_dict(self) -> dict:
        return {
            "mode": self.mode.value,
            "setting": self.setting,
            "chaos": self.chaos,
            "mood": self.mood.to_dict(),
            "scenes": self.scenes,
            "threads": self.threads,
            "notes": self.notes,
            "npcs": self.npcs,
            "aggression": self.aggression,
            "doctrine": self.doctrine.value,
            "scale": self.scale.value,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SessionState":
        return cls(
            mode=Mode(data.get("mode", "rpg")),
            setting=data.get("setting", "fantasy"),
            chaos=data.get("chaos", 5),
            mood=Mood.from_dict(data.get("mood", {})),
            scenes=data.get("scenes", []),
            threads=data.get("threads", []),
            notes=data.get("notes", []),
            npcs=data.get("npcs", []),
            aggression=data.get("aggression", 5),
            doctrine=Doctrine(data.get("doctrine", "balanced")),
            scale=Scale(data.get("scale", "tactical")),
        )


@dataclass
class CommandResult:
    """Result of a command execution."""
    success: bool
    message: str = ""
    style: str = ""  # rich style for coloring
    panel_title: str = ""
    should_exit: bool = False


class OracleCLI:
    """Interactive CLI for the Oracle system."""

    SETTINGS = ["fantasy", "scifi_military", "cyberpunk", "historical", "weird_war", "birthright"]

    COMMANDS = [
        "roll", "ask", "chaos", "table", "npc", "scene", "thread",
        "note", "journal", "save", "load", "mood", "help", "quit", "exit",
        "import",
        # Wargame commands
        "wargame", "rpg", "aggression", "doctrine", "scale", "decide",
        "priority", "morale", "event",
        # Birthright commands
        "window", "windows", "ref", "character", "char", "newchar", "loadchar",
        "domain", "regency", "bloodline",
    ]

    def __init__(self):
        self.console = Console()
        self.oracle = Oracle()
        self.state = SessionState()

        # Birthright character (if playing Birthright setting)
        self.character: Optional[Any] = None  # BirthrightCharacter when loaded

        # Set up history file in user's home
        history_path = Path.home() / ".oracle_history"

        # Handle terminal compatibility issues (Windows + non-native terminals)
        try:
            self.session: PromptSession = PromptSession(
                history=FileHistory(str(history_path)),
                completer=WordCompleter(self.COMMANDS, ignore_case=True),
            )
        except Exception as e:
            # Fallback: force TERM to be Windows-compatible
            if "NoConsoleScreenBufferError" in str(type(e).__name__) or "xterm" in str(e):
                # Remove TERM that confuses prompt_toolkit on Windows
                old_term = os.environ.get("TERM")
                if old_term:
                    del os.environ["TERM"]
                try:
                    self.session = PromptSession(
                        history=FileHistory(str(history_path)),
                        completer=WordCompleter(self.COMMANDS, ignore_case=True),
                    )
                finally:
                    # Restore TERM if it was set
                    if old_term:
                        os.environ["TERM"] = old_term
            else:
                raise

    def run(self):
        """Main entry point - run the CLI."""
        self._show_banner()
        self._startup_flow()
        self._main_loop()

    def _show_banner(self):
        """Display the welcome banner."""
        banner = Text()
        banner.append("ORACLE", style="bold cyan")
        banner.append(" - Solo Tabletop Game Master Emulator\n", style="dim")
        banner.append("Type 'help' for commands, 'quit' to exit", style="dim")

        self.console.print(Panel(banner, border_style="cyan"))

    def _startup_flow(self):
        """Interactive startup to configure the session."""
        self.console.print("\n[bold]Session Setup[/bold]\n")

        # Select mode
        self.console.print("Select mode:")
        self.console.print("  [cyan]1[/cyan] - RPG (solo roleplaying)")
        self.console.print("  [cyan]2[/cyan] - Wargame (tactical AI)")

        while True:
            try:
                choice = self.session.prompt("Mode [1]: ").strip() or "1"
                if choice == "1":
                    self.state.mode = Mode.RPG
                    break
                elif choice == "2":
                    self.state.mode = Mode.WARGAME
                    break
                else:
                    self.console.print("[red]Invalid choice[/red]")
            except (EOFError, KeyboardInterrupt):
                return

        # Select setting
        self.console.print("\nSelect setting:")
        for i, setting in enumerate(self.SETTINGS, 1):
            display_name = setting.replace("_", " ").title()
            self.console.print(f"  [cyan]{i}[/cyan] - {display_name}")

        while True:
            try:
                choice = self.session.prompt("Setting [1]: ").strip() or "1"
                idx = int(choice) - 1
                if 0 <= idx < len(self.SETTINGS):
                    self.state.setting = self.SETTINGS[idx]
                    break
                else:
                    self.console.print("[red]Invalid choice[/red]")
            except ValueError:
                self.console.print("[red]Enter a number[/red]")
            except (EOFError, KeyboardInterrupt):
                return

        # Optional mood adjustment
        self.console.print("\nAdjust mood? (Enter to skip, or 'mood' to adjust)")
        try:
            if self.session.prompt("> ").strip().lower() == "mood":
                self._adjust_mood_interactive()
        except (EOFError, KeyboardInterrupt):
            pass

        # Sync chaos with oracle
        self.oracle.chaos = self.state.chaos

        self.console.print(f"\n[green]Session started![/green]")
        self.console.print(
            f"Mode: [cyan]{self.state.mode.value.upper()}[/cyan] | "
            f"Setting: [cyan]{self.state.setting.replace('_', ' ').title()}[/cyan] | "
            f"Chaos: [cyan]{self.state.chaos}[/cyan]\n"
        )

    def _adjust_mood_interactive(self):
        """Interactive mood adjustment."""
        aspects = ["tension", "horror", "action", "mystery"]
        self.console.print("\nSet mood aspects (1-10):")

        for aspect in aspects:
            current = getattr(self.state.mood, aspect)
            try:
                value = self.session.prompt(f"  {aspect.title()} [{current}]: ").strip()
                if value:
                    setattr(self.state.mood, aspect, max(1, min(10, int(value))))
            except (ValueError, EOFError, KeyboardInterrupt):
                pass

    def _main_loop(self):
        """Main command loop."""
        prompt_style = "wargame" if self.state.mode == Mode.WARGAME else "rpg"
        prompt_text = f"[{prompt_style}]> "

        while True:
            try:
                user_input = self.session.prompt(prompt_text).strip()
                if not user_input:
                    continue

                result = self._execute_command(user_input)

                if result.should_exit:
                    self.console.print("[dim]Farewell, adventurer.[/dim]")
                    break

                if result.message:
                    if result.panel_title:
                        self.console.print(Panel(
                            result.message,
                            title=result.panel_title,
                            border_style=result.style or "white"
                        ))
                    elif result.style:
                        self.console.print(f"[{result.style}]{result.message}[/{result.style}]")
                    else:
                        self.console.print(result.message)

            except KeyboardInterrupt:
                self.console.print("\n[dim]Use 'quit' to exit[/dim]")
            except EOFError:
                break

    def _execute_command(self, input_text: str) -> CommandResult:
        """Parse and execute a command."""
        # Parse command and arguments
        try:
            parts = shlex.split(input_text)
        except ValueError:
            parts = input_text.split()

        if not parts:
            return CommandResult(success=False)

        cmd = parts[0].lower()
        args = parts[1:]

        # Command dispatch
        handlers = {
            # Common commands
            "roll": self._cmd_roll,
            "ask": self._cmd_ask,
            "chaos": self._cmd_chaos,
            "table": self._cmd_table,
            "npc": self._cmd_npc,
            "scene": self._cmd_scene,
            "thread": self._cmd_thread,
            "note": self._cmd_note,
            "journal": self._cmd_journal,
            "save": self._cmd_save,
            "load": self._cmd_load,
            "mood": self._cmd_mood,
            "help": self._cmd_help,
            "quit": self._cmd_quit,
            "exit": self._cmd_quit,
            "import": self._cmd_import,
            # Mode switching
            "wargame": self._cmd_wargame_mode,
            "rpg": self._cmd_rpg_mode,
            # Wargame commands
            "aggression": self._cmd_aggression,
            "doctrine": self._cmd_doctrine,
            "scale": self._cmd_scale,
            "decide": self._cmd_decide,
            "priority": self._cmd_priority,
            "morale": self._cmd_morale,
            "event": self._cmd_event,
            # Birthright commands
            "window": self._cmd_window,
            "windows": self._cmd_windows,
            "ref": self._cmd_window,
            "character": self._cmd_character,
            "char": self._cmd_character,
            "newchar": self._cmd_newchar,
            "loadchar": self._cmd_loadchar,
            "domain": self._cmd_domain,
            "regency": self._cmd_regency,
            "bloodline": self._cmd_bloodline,
        }

        handler = handlers.get(cmd)
        if handler:
            return handler(args, input_text)
        else:
            return CommandResult(
                success=False,
                message=f"Unknown command: {cmd}. Type 'help' for available commands.",
                style="red"
            )

    # -------------------------------------------------------------------------
    # Common Commands
    # -------------------------------------------------------------------------

    def _cmd_roll(self, args: list[str], raw: str) -> CommandResult:
        """Roll dice with expression."""
        if not args:
            return CommandResult(
                success=False,
                message="Usage: roll <expression> (e.g., roll 2d6+3, roll d20 adv)",
                style="yellow"
            )

        expression = " ".join(args)
        try:
            result: DiceResult = dice_roll(expression)
            return CommandResult(
                success=True,
                message=str(result),
                panel_title=f"Rolling {expression}",
                style="cyan"
            )
        except ValueError as e:
            return CommandResult(
                success=False,
                message=str(e),
                style="red"
            )

    def _cmd_ask(self, args: list[str], raw: str) -> CommandResult:
        """Ask the oracle a yes/no question."""
        # Parse likelihood flags
        likelihood = Likelihood.EVEN
        question_parts = []

        for arg in args:
            lower_arg = arg.lower()
            if lower_arg == "--likely":
                likelihood = Likelihood.LIKELY
            elif lower_arg == "--unlikely":
                likelihood = Likelihood.UNLIKELY
            elif lower_arg == "--certain":
                likelihood = Likelihood.CERTAIN
            elif lower_arg == "--impossible":
                likelihood = Likelihood.IMPOSSIBLE
            else:
                question_parts.append(arg)

        question = " ".join(question_parts).strip('"\'')

        if not question:
            return CommandResult(
                success=False,
                message="Usage: ask \"<question>\" [--likely|--unlikely|--certain|--impossible]",
                style="yellow"
            )

        result: OracleResult = self.oracle.ask(question, likelihood)

        # Color based on answer
        if result.answer in (Answer.YES, Answer.YES_AND, Answer.YES_BUT):
            style = "green"
        else:
            style = "red"

        message = f"Q: {question}\n\n"
        message += f"Roll: {result.roll} vs {result.threshold} "
        message += f"(Chaos: {result.chaos}, {result.likelihood.display})\n\n"
        message += f"[bold]{result.answer.value}[/bold]"

        if result.random_event:
            message += "\n\n[bold yellow]RANDOM EVENT TRIGGERED![/bold yellow]"

        return CommandResult(
            success=True,
            message=message,
            panel_title="Oracle Speaks",
            style=style
        )

    def _cmd_chaos(self, args: list[str], raw: str) -> CommandResult:
        """Show or modify chaos level."""
        if not args:
            return CommandResult(
                success=True,
                message=f"Chaos Factor: {self.oracle.chaos}",
                style="cyan"
            )

        arg = args[0].lower()
        if arg == "up":
            new_val = self.oracle.chaos_up()
            self.state.chaos = new_val
            return CommandResult(
                success=True,
                message=f"Chaos increased to {new_val}",
                style="yellow"
            )
        elif arg == "down":
            new_val = self.oracle.chaos_down()
            self.state.chaos = new_val
            return CommandResult(
                success=True,
                message=f"Chaos decreased to {new_val}",
                style="cyan"
            )
        else:
            try:
                value = int(arg)
                self.oracle.chaos = value
                self.state.chaos = self.oracle.chaos
                return CommandResult(
                    success=True,
                    message=f"Chaos set to {self.oracle.chaos}",
                    style="cyan"
                )
            except ValueError:
                return CommandResult(
                    success=False,
                    message="Usage: chaos [up|down|<number>]",
                    style="red"
                )

    def _cmd_table(self, args: list[str], raw: str) -> CommandResult:
        """Roll on a random table or list available tables."""
        if not args:
            return CommandResult(
                success=False,
                message="Usage: table <name> [--setting <setting>] [--mood <mood>]\n       table list [--setting <setting>]",
                style="yellow"
            )

        # Parse arguments
        table_name = None
        setting = self.state.setting
        mood = "neutral"

        i = 0
        while i < len(args):
            arg = args[i]
            if arg == "--setting" and i + 1 < len(args):
                setting = args[i + 1]
                i += 2
            elif arg == "--mood" and i + 1 < len(args):
                mood = args[i + 1]
                i += 2
            elif not arg.startswith("--"):
                table_name = arg
                i += 1
            else:
                i += 1

        # Handle 'table list' command
        if table_name == "list":
            available = list_tables(setting)
            if not available:
                # Try core as fallback
                available = list_tables("core")
                if available:
                    setting = "core"

            if available:
                lines = [f"Available tables in '{setting}':"]
                for t in available:
                    lines.append(f"  - {t}")
                return CommandResult(
                    success=True,
                    message="\n".join(lines),
                    style="cyan"
                )
            else:
                return CommandResult(
                    success=False,
                    message="No tables found. Add .toml files to oracle/data/<setting>/<table>/",
                    style="yellow"
                )

        if not table_name:
            return CommandResult(
                success=False,
                message="Usage: table <name> [--setting <setting>] [--mood <mood>]",
                style="yellow"
            )

        # Roll on the table
        result = roll_on(table_name, setting, mood)

        if result is None:
            # Table not found - provide helpful message
            available = list_tables(setting) or list_tables("core")
            hint = ""
            if available:
                hint = f"\nAvailable tables: {', '.join(available[:5])}"
                if len(available) > 5:
                    hint += f" (+{len(available) - 5} more)"

            return CommandResult(
                success=False,
                message=f"Table '{table_name}' not found in {setting}/{mood}.{hint}",
                style="yellow"
            )

        # Format the result
        message = f"[bold]{result.entry.text}[/bold]"
        if result.entry.tags:
            message += f"\n[dim]Tags: {', '.join(result.entry.tags)}[/dim]"

        return CommandResult(
            success=True,
            message=message,
            panel_title=f"{result.table_name}",
            style="cyan"
        )

    def _cmd_npc(self, args: list[str], raw: str) -> CommandResult:
        """Generate a random NPC."""
        setting = args[0] if args else self.state.setting

        # Basic NPC generation (placeholder - will expand with data files)
        import random
        traits = ["cunning", "brave", "cowardly", "greedy", "kind", "mysterious", "aggressive", "cautious"]
        motivations = ["wealth", "power", "revenge", "love", "survival", "knowledge", "justice", "freedom"]

        npc = {
            "trait": random.choice(traits),
            "motivation": random.choice(motivations),
            "setting": setting,
            "generated": datetime.now().isoformat(),
        }
        self.state.npcs.append(npc)

        message = f"Trait: [cyan]{npc['trait'].title()}[/cyan]\n"
        message += f"Motivation: [cyan]{npc['motivation'].title()}[/cyan]"

        return CommandResult(
            success=True,
            message=message,
            panel_title="NPC Generated",
            style="cyan"
        )

    def _cmd_scene(self, args: list[str], raw: str) -> CommandResult:
        """Log a scene description."""
        description = " ".join(args).strip('"\'')
        if not description:
            return CommandResult(
                success=False,
                message="Usage: scene \"<description>\"",
                style="yellow"
            )

        scene = {
            "description": description,
            "chaos": self.oracle.chaos,
            "timestamp": datetime.now().isoformat(),
        }
        self.state.scenes.append(scene)

        return CommandResult(
            success=True,
            message=f"Scene #{len(self.state.scenes)} logged.",
            style="green"
        )

    def _cmd_thread(self, args: list[str], raw: str) -> CommandResult:
        """Add a plot thread."""
        thread = " ".join(args).strip('"\'')
        if not thread:
            if self.state.threads:
                # Show existing threads
                lines = ["Active Threads:"]
                for i, t in enumerate(self.state.threads, 1):
                    lines.append(f"  {i}. {t}")
                return CommandResult(
                    success=True,
                    message="\n".join(lines),
                    style="cyan"
                )
            return CommandResult(
                success=False,
                message="Usage: thread \"<description>\" or thread (to list)",
                style="yellow"
            )

        self.state.threads.append(thread)
        return CommandResult(
            success=True,
            message=f"Thread added: {thread}",
            style="green"
        )

    def _cmd_note(self, args: list[str], raw: str) -> CommandResult:
        """Add a session note."""
        note = " ".join(args).strip('"\'')
        if not note:
            return CommandResult(
                success=False,
                message="Usage: note \"<text>\"",
                style="yellow"
            )

        self.state.notes.append(note)
        return CommandResult(
            success=True,
            message=f"Note added.",
            style="green"
        )

    def _cmd_journal(self, args: list[str], raw: str) -> CommandResult:
        """Display session journal."""
        table = Table(title="Session Journal", border_style="cyan")
        table.add_column("Category", style="cyan")
        table.add_column("Count", justify="right")
        table.add_column("Details")

        table.add_row(
            "Mode",
            "",
            self.state.mode.value.upper()
        )
        table.add_row(
            "Setting",
            "",
            self.state.setting.replace("_", " ").title()
        )
        table.add_row(
            "Chaos",
            "",
            str(self.oracle.chaos)
        )
        table.add_row(
            "Scenes",
            str(len(self.state.scenes)),
            self.state.scenes[-1]["description"][:40] + "..." if self.state.scenes else "-"
        )
        table.add_row(
            "Threads",
            str(len(self.state.threads)),
            ", ".join(self.state.threads[:3]) + ("..." if len(self.state.threads) > 3 else "") or "-"
        )
        table.add_row(
            "Notes",
            str(len(self.state.notes)),
            self.state.notes[-1][:40] + "..." if self.state.notes else "-"
        )
        table.add_row(
            "NPCs",
            str(len(self.state.npcs)),
            "-"
        )

        if self.state.mode == Mode.WARGAME:
            table.add_row("Aggression", "", str(self.state.aggression))
            table.add_row("Doctrine", "", self.state.doctrine.value.title())
            table.add_row("Scale", "", self.state.scale.value.title())

        self.console.print(table)
        return CommandResult(success=True)

    def _cmd_save(self, args: list[str], raw: str) -> CommandResult:
        """Save session to file."""
        filename = args[0] if args else f"oracle_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        if not filename.endswith(".json"):
            filename += ".json"

        path = Path(filename)
        try:
            with open(path, "w") as f:
                json.dump(self.state.to_dict(), f, indent=2)
            return CommandResult(
                success=True,
                message=f"Session saved to {path.absolute()}",
                style="green"
            )
        except Exception as e:
            return CommandResult(
                success=False,
                message=f"Failed to save: {e}",
                style="red"
            )

    def _cmd_load(self, args: list[str], raw: str) -> CommandResult:
        """Load session from file."""
        if not args:
            return CommandResult(
                success=False,
                message="Usage: load <filename>",
                style="yellow"
            )

        filename = args[0]
        if not filename.endswith(".json"):
            filename += ".json"

        path = Path(filename)
        try:
            with open(path, "r") as f:
                data = json.load(f)
            self.state = SessionState.from_dict(data)
            self.oracle.chaos = self.state.chaos
            return CommandResult(
                success=True,
                message=f"Session loaded from {path}",
                style="green"
            )
        except FileNotFoundError:
            return CommandResult(
                success=False,
                message=f"File not found: {filename}",
                style="red"
            )
        except Exception as e:
            return CommandResult(
                success=False,
                message=f"Failed to load: {e}",
                style="red"
            )

    def _cmd_mood(self, args: list[str], raw: str) -> CommandResult:
        """Show or adjust mood aspects."""
        if not args:
            # Show current mood
            mood = self.state.mood
            lines = [
                f"Tension: {mood.tension}/10",
                f"Horror: {mood.horror}/10",
                f"Action: {mood.action}/10",
                f"Mystery: {mood.mystery}/10",
            ]
            return CommandResult(
                success=True,
                message="\n".join(lines),
                panel_title="Current Mood",
                style="cyan"
            )

        if len(args) < 2:
            return CommandResult(
                success=False,
                message="Usage: mood [aspect value] (e.g., mood tension 8)",
                style="yellow"
            )

        aspect = args[0].lower()
        try:
            value = max(1, min(10, int(args[1])))
        except ValueError:
            return CommandResult(
                success=False,
                message="Value must be a number 1-10",
                style="red"
            )

        if hasattr(self.state.mood, aspect):
            setattr(self.state.mood, aspect, value)
            return CommandResult(
                success=True,
                message=f"{aspect.title()} set to {value}",
                style="green"
            )
        else:
            return CommandResult(
                success=False,
                message=f"Unknown aspect: {aspect}. Use: tension, horror, action, mystery",
                style="red"
            )

    def _cmd_import(self, args: list[str], raw: str) -> CommandResult:
        """Import data from external files (PDF, BSData, etc.)."""
        if not args:
            return CommandResult(
                success=False,
                message="Usage: import pdf <filepath> [--max-pages N]\n       import bsdata <filepath>",
                style="yellow"
            )

        import_type = args[0].lower()

        if import_type == "pdf":
            return self._import_pdf(args[1:])
        elif import_type == "bsdata":
            return self._import_bsdata(args[1:])
        else:
            return CommandResult(
                success=False,
                message=f"Unknown import type: {import_type}. Use: pdf, bsdata",
                style="red"
            )

    def _import_pdf(self, args: list[str]) -> CommandResult:
        """Import tables from a PDF file."""
        if not args:
            return CommandResult(
                success=False,
                message="Usage: import pdf <filepath> [--max-pages N]",
                style="yellow"
            )

        # Parse arguments
        filepath = None
        max_pages = None

        i = 0
        while i < len(args):
            arg = args[i]
            if arg == "--max-pages" and i + 1 < len(args):
                try:
                    max_pages = int(args[i + 1])
                except ValueError:
                    pass
                i += 2
            elif not arg.startswith("--"):
                filepath = arg
                i += 1
            else:
                i += 1

        if not filepath:
            return CommandResult(
                success=False,
                message="Usage: import pdf <filepath> [--max-pages N]",
                style="yellow"
            )

        # Check if PyMuPDF is available
        try:
            from oracle.importers import import_pdf, PDFContent
        except ImportError as e:
            return CommandResult(
                success=False,
                message=f"PDF import requires PyMuPDF. Install with: pip install pymupdf\nError: {e}",
                style="red"
            )

        # Import the PDF with progress display
        filepath_obj = Path(filepath)
        if not filepath_obj.exists():
            return CommandResult(
                success=False,
                message=f"File not found: {filepath}",
                style="red"
            )

        self.console.print(f"[dim]Importing {filepath_obj.name}...[/dim]")

        def progress_callback(current: int, total: int, message: str):
            self.console.print(f"[dim]  [{current}/{total}] {message}[/dim]", end="\r")

        try:
            content: PDFContent = import_pdf(
                filepath_obj,
                max_pages=max_pages,
                progress_callback=progress_callback
            )
        except Exception as e:
            return CommandResult(
                success=False,
                message=f"Failed to import PDF: {e}",
                style="red"
            )

        # Clear progress line
        self.console.print(" " * 60, end="\r")

        # Summarize results
        roll_tables = content.get_roll_tables()
        lines = [
            f"Title: {content.title or content.filename}",
            f"Pages processed: {len(content.pages)}/{content.total_pages}",
            f"Tables found: {len(content.tables)}",
            f"Roll tables: {len(roll_tables)}",
        ]

        # Save extracted tables if any
        if roll_tables:
            # Create output directory
            output_dir = Path.cwd() / "data" / "imports"
            output_dir.mkdir(parents=True, exist_ok=True)

            # Generate output filename
            stem = filepath_obj.stem.lower().replace(" ", "_")
            output_path = output_dir / f"{stem}_tables.toml"

            try:
                content.export_tables_to_toml(output_path)
                lines.append(f"\nTables saved to: {output_path}")

                # List first few tables
                lines.append("\nExtracted tables:")
                for table in roll_tables[:5]:
                    lines.append(f"  - {table.title or 'Unnamed'} ({table.die_type}, {len(table.rows)} entries)")
                if len(roll_tables) > 5:
                    lines.append(f"  ... and {len(roll_tables) - 5} more")
            except Exception as e:
                lines.append(f"\n[red]Failed to save tables: {e}[/red]")

        return CommandResult(
            success=True,
            message="\n".join(lines),
            panel_title="PDF Import Complete",
            style="green"
        )

    def _import_bsdata(self, args: list[str]) -> CommandResult:
        """Import units from BSData/BattleScribe files."""
        if not args:
            return CommandResult(
                success=False,
                message="Usage: import bsdata <filepath>",
                style="yellow"
            )

        filepath = args[0]
        filepath_obj = Path(filepath)

        if not filepath_obj.exists():
            return CommandResult(
                success=False,
                message=f"File not found: {filepath}",
                style="red"
            )

        try:
            from oracle.importers import import_bsdata, export_to_toml
        except ImportError as e:
            return CommandResult(
                success=False,
                message=f"BSData import failed: {e}",
                style="red"
            )

        self.console.print(f"[dim]Importing {filepath_obj.name}...[/dim]")

        try:
            units = import_bsdata(filepath_obj)

            if not units:
                return CommandResult(
                    success=False,
                    message="No units found in file.",
                    style="yellow"
                )

            # Save to TOML
            output_dir = Path.cwd() / "data" / "imports" / "factions"
            output_dir.mkdir(parents=True, exist_ok=True)

            output_path = export_to_toml(units, output_dir)

            lines = [
                f"Units imported: {len(units)}",
                f"Saved to: {output_path}",
                "",
                "Sample units:",
            ]
            for unit in units[:5]:
                lines.append(f"  - {unit.name} ({unit.points} pts)")
            if len(units) > 5:
                lines.append(f"  ... and {len(units) - 5} more")

            return CommandResult(
                success=True,
                message="\n".join(lines),
                panel_title="BSData Import Complete",
                style="green"
            )

        except Exception as e:
            return CommandResult(
                success=False,
                message=f"Import failed: {e}",
                style="red"
            )

    def _cmd_help(self, args: list[str], raw: str) -> CommandResult:
        """Show help information."""
        table = Table(title="Oracle Commands", border_style="cyan")
        table.add_column("Command", style="cyan")
        table.add_column("Description")

        common_commands = [
            ("roll <expr>", "Roll dice (e.g., 2d6+3, d20 adv)"),
            ("ask \"<question>\"", "Oracle yes/no (--likely, --unlikely, --certain, --impossible)"),
            ("chaos [up|down|N]", "Show/modify chaos factor (1-9)"),
            ("table <name>", "Roll on a random table (table list to see available)"),
            ("table list", "List available tables for current setting"),
            ("npc [setting]", "Generate random NPC"),
            ("scene \"<desc>\"", "Log a scene"),
            ("thread \"<desc>\"", "Add plot thread (no args to list)"),
            ("note \"<text>\"", "Add a note"),
            ("journal", "Display session state"),
            ("mood [aspect N]", "Show/change mood aspects"),
            ("save [filename]", "Save session to JSON"),
            ("load <filename>", "Load session from JSON"),
            ("import pdf <path>", "Import tables from PDF (--max-pages N)"),
            ("import bsdata <path>", "Import units from BattleScribe files"),
            ("help", "Show this help"),
            ("quit/exit", "Exit Oracle"),
        ]

        wargame_commands = [
            ("wargame", "Enter wargame mode"),
            ("rpg", "Enter RPG mode"),
            ("aggression <1-10>", "Set AI aggression level"),
            ("doctrine <type>", "Set doctrine (aggressive/defensive/balanced/guerrilla/blitz)"),
            ("scale <size>", "Set scale (skirmish/tactical/operational/strategic)"),
            ("decide \"<situation>\"", "Get tactical recommendation"),
            ("priority \"<targets>\"", "Determine target priority"),
            ("morale <casualties%>", "Check unit morale"),
            ("event", "Generate random battle event"),
        ]

        for cmd, desc in common_commands:
            table.add_row(cmd, desc)

        table.add_row("", "")
        table.add_row("[bold]WARGAME MODE[/bold]", "")

        for cmd, desc in wargame_commands:
            table.add_row(cmd, desc)

        self.console.print(table)
        return CommandResult(success=True)

    def _cmd_quit(self, args: list[str], raw: str) -> CommandResult:
        """Exit the CLI."""
        return CommandResult(success=True, should_exit=True)

    # -------------------------------------------------------------------------
    # Mode Switching
    # -------------------------------------------------------------------------

    def _cmd_wargame_mode(self, args: list[str], raw: str) -> CommandResult:
        """Switch to wargame mode."""
        self.state.mode = Mode.WARGAME
        return CommandResult(
            success=True,
            message="Switched to WARGAME mode. Tactical AI active.",
            style="yellow"
        )

    def _cmd_rpg_mode(self, args: list[str], raw: str) -> CommandResult:
        """Switch to RPG mode."""
        self.state.mode = Mode.RPG
        return CommandResult(
            success=True,
            message="Switched to RPG mode.",
            style="cyan"
        )

    # -------------------------------------------------------------------------
    # Wargame Commands
    # -------------------------------------------------------------------------

    def _cmd_aggression(self, args: list[str], raw: str) -> CommandResult:
        """Set AI aggression level."""
        if not args:
            return CommandResult(
                success=True,
                message=f"Aggression: {self.state.aggression}/10",
                style="cyan"
            )

        try:
            value = max(1, min(10, int(args[0])))
            self.state.aggression = value
            return CommandResult(
                success=True,
                message=f"Aggression set to {value}",
                style="yellow"
            )
        except ValueError:
            return CommandResult(
                success=False,
                message="Usage: aggression <1-10>",
                style="red"
            )

    def _cmd_doctrine(self, args: list[str], raw: str) -> CommandResult:
        """Set tactical doctrine."""
        if not args:
            return CommandResult(
                success=True,
                message=f"Doctrine: {self.state.doctrine.value.title()}",
                style="cyan"
            )

        try:
            self.state.doctrine = Doctrine(args[0].lower())
            return CommandResult(
                success=True,
                message=f"Doctrine set to {self.state.doctrine.value.title()}",
                style="yellow"
            )
        except ValueError:
            valid = ", ".join(d.value for d in Doctrine)
            return CommandResult(
                success=False,
                message=f"Invalid doctrine. Use: {valid}",
                style="red"
            )

    def _cmd_scale(self, args: list[str], raw: str) -> CommandResult:
        """Set battle scale."""
        if not args:
            return CommandResult(
                success=True,
                message=f"Scale: {self.state.scale.value.title()}",
                style="cyan"
            )

        try:
            self.state.scale = Scale(args[0].lower())
            return CommandResult(
                success=True,
                message=f"Scale set to {self.state.scale.value.title()}",
                style="yellow"
            )
        except ValueError:
            valid = ", ".join(s.value for s in Scale)
            return CommandResult(
                success=False,
                message=f"Invalid scale. Use: {valid}",
                style="red"
            )

    def _cmd_decide(self, args: list[str], raw: str) -> CommandResult:
        """Get tactical decision recommendation."""
        situation = " ".join(args).strip('"\'')
        if not situation:
            return CommandResult(
                success=False,
                message='Usage: decide "<tactical situation>"',
                style="yellow"
            )

        import random

        # Generate recommendation based on doctrine and aggression
        doctrine = self.state.doctrine
        aggression = self.state.aggression

        actions_by_doctrine = {
            Doctrine.AGGRESSIVE: ["Attack immediately", "Flank and assault", "Press the advantage", "Pursue retreating forces"],
            Doctrine.DEFENSIVE: ["Hold position", "Establish defensive perimeter", "Fall back to cover", "Await reinforcements"],
            Doctrine.BALANCED: ["Advance cautiously", "Probe enemy defenses", "Secure flanks before moving", "Maintain reserves"],
            Doctrine.GUERRILLA: ["Hit and run", "Set ambush", "Avoid direct engagement", "Target supply lines"],
            Doctrine.BLITZ: ["Maximum speed advance", "Bypass strongpoints", "Maintain momentum", "Exploit any gap"],
        }

        base_actions = actions_by_doctrine[doctrine]

        # Modify by aggression
        if aggression >= 7:
            action = random.choice(base_actions[:2])  # More aggressive options
        elif aggression <= 3:
            action = random.choice(base_actions[2:])  # More cautious options
        else:
            action = random.choice(base_actions)

        # Add chaos element
        if self.oracle.d100() <= self.oracle.chaos * 10:
            complications = [
                "Enemy reinforcements arriving",
                "Weather deteriorating",
                "Supply situation critical",
                "Friendly unit requesting support",
                "Intelligence reports enemy movement",
            ]
            action += f" [yellow](Complication: {random.choice(complications)})[/yellow]"

        message = f"Situation: {situation}\n\n"
        message += f"Doctrine: {doctrine.value.title()}, Aggression: {aggression}/10\n\n"
        message += f"Recommendation: [bold]{action}[/bold]"

        return CommandResult(
            success=True,
            message=message,
            panel_title="Tactical Decision",
            style="yellow"
        )

    def _cmd_priority(self, args: list[str], raw: str) -> CommandResult:
        """Determine target priority."""
        targets = " ".join(args).strip('"\'')
        if not targets:
            return CommandResult(
                success=False,
                message='Usage: priority "<comma-separated targets>"',
                style="yellow"
            )

        import random

        target_list = [t.strip() for t in targets.split(",")]

        # Shuffle based on doctrine
        if self.state.doctrine == Doctrine.AGGRESSIVE:
            # Prioritize whatever sounds most valuable/threatening
            random.shuffle(target_list)
        elif self.state.doctrine == Doctrine.DEFENSIVE:
            # Reverse (nearest threats first assumed)
            target_list = target_list[::-1]
        else:
            random.shuffle(target_list)

        lines = ["Target Priority:"]
        for i, target in enumerate(target_list, 1):
            lines.append(f"  {i}. {target}")

        return CommandResult(
            success=True,
            message="\n".join(lines),
            panel_title="Target Priority",
            style="yellow"
        )

    def _cmd_morale(self, args: list[str], raw: str) -> CommandResult:
        """Check unit morale based on casualties."""
        if not args:
            return CommandResult(
                success=False,
                message="Usage: morale <casualties_percent>",
                style="yellow"
            )

        try:
            casualties = float(args[0].rstrip("%"))
        except ValueError:
            return CommandResult(
                success=False,
                message="Casualties must be a number (percentage)",
                style="red"
            )

        # Roll against morale threshold
        # Base threshold decreases with casualties
        base_threshold = 70 - int(casualties * 0.5)

        # Aggression affects morale resistance
        threshold = base_threshold + (self.state.aggression - 5) * 2

        roll = self.oracle.d100()

        if roll <= threshold:
            status = "[green]HOLDING[/green]"
            detail = "Unit maintains cohesion."
        elif roll <= threshold + 20:
            status = "[yellow]WAVERING[/yellow]"
            detail = "Unit shaken but holding."
        else:
            status = "[red]BREAKING[/red]"
            detail = "Unit begins to rout!"

        message = f"Casualties: {casualties}%\n"
        message += f"Roll: {roll} vs {threshold}\n\n"
        message += f"Status: {status}\n{detail}"

        return CommandResult(
            success=True,
            message=message,
            panel_title="Morale Check",
            style="yellow"
        )

    def _cmd_event(self, args: list[str], raw: str) -> CommandResult:
        """Generate random battle event."""
        import random

        events_by_scale = {
            Scale.SKIRMISH: [
                "Sniper spotted!",
                "Hidden IED/trap discovered",
                "Civilian in crossfire",
                "Radio interference",
                "Enemy reinforcements (fire team)",
                "Friendly wounded needs extraction",
                "Enemy attempting to flank",
                "Ammo running low",
            ],
            Scale.TACTICAL: [
                "Artillery barrage incoming",
                "Air support available",
                "Enemy armor approaching",
                "Supply convoy ambushed",
                "Friendly unit requesting support",
                "Enemy attempting breakthrough",
                "Weather changing",
                "Communications compromised",
            ],
            Scale.OPERATIONAL: [
                "Strategic reserve committed",
                "Enemy counterattack on secondary front",
                "Supply lines interdicted",
                "Political pressure to advance",
                "Intelligence reports enemy weakness",
                "Friendly unit encircled",
                "Enemy strategic withdrawal detected",
                "Allied force coordination issues",
            ],
            Scale.STRATEGIC: [
                "Enemy theater-level offensive",
                "Allied nation joining conflict",
                "War weariness affecting morale",
                "New weapons technology deployed",
                "Peace negotiations begin",
                "Neutral nation protests violations",
                "Economic sanctions affecting supply",
                "Key leader eliminated",
            ],
        }

        event = random.choice(events_by_scale[self.state.scale])

        return CommandResult(
            success=True,
            message=event,
            panel_title=f"Battle Event ({self.state.scale.value.title()})",
            style="yellow"
        )

    # -------------------------------------------------------------------------
    # Birthright Commands
    # -------------------------------------------------------------------------

    def _cmd_window(self, args: list[str], raw: str) -> CommandResult:
        """Open a pop-out reference window."""
        if not BIRTHRIGHT_AVAILABLE:
            return CommandResult(
                success=False,
                message="Birthright modules not available. Check installation.",
                style="red"
            )

        if not args:
            windows = list_available_windows()
            lines = ["Available reference windows:"]
            for name, desc in windows:
                lines.append(f"  [cyan]{name}[/cyan] - {desc}")
            lines.append("\nUsage: window <name>")
            return CommandResult(
                success=True,
                message="\n".join(lines),
                style="white"
            )

        window_name = args[0].lower()
        char_data = self.character.to_dict() if self.character else None

        if open_window_by_name(window_name, char_data):
            return CommandResult(
                success=True,
                message=f"Opened {window_name} reference window.",
                style="green"
            )
        else:
            return CommandResult(
                success=False,
                message=f"Could not open window: {window_name}",
                style="red"
            )

    def _cmd_windows(self, args: list[str], raw: str) -> CommandResult:
        """List available reference windows."""
        if not BIRTHRIGHT_AVAILABLE:
            return CommandResult(
                success=False,
                message="Birthright modules not available.",
                style="red"
            )

        windows = list_available_windows()
        lines = ["[bold]Available Reference Windows[/bold]\n"]
        for name, desc in windows:
            lines.append(f"  [cyan]{name:18}[/cyan] {desc}")
        lines.append("\n[dim]Use 'window <name>' to open a reference window.[/dim]")

        return CommandResult(
            success=True,
            message="\n".join(lines),
            panel_title="Reference Windows",
            style="cyan"
        )

    def _cmd_character(self, args: list[str], raw: str) -> CommandResult:
        """Display current character sheet."""
        if not BIRTHRIGHT_AVAILABLE:
            return CommandResult(
                success=False,
                message="Birthright modules not available.",
                style="red"
            )

        if self.character is None:
            return CommandResult(
                success=False,
                message="No character loaded. Use 'newchar' to create or 'loadchar' to load one.",
                style="yellow"
            )

        sheet = format_character_sheet(self.character)
        return CommandResult(
            success=True,
            message=sheet,
            panel_title=f"{self.character.title} {self.character.name}",
            style="cyan"
        )

    def _cmd_newchar(self, args: list[str], raw: str) -> CommandResult:
        """Create a new Birthright character."""
        if not BIRTHRIGHT_AVAILABLE:
            return CommandResult(
                success=False,
                message="Birthright modules not available.",
                style="red"
            )

        # Parse arguments
        is_regent = True
        strength = None

        for arg in args:
            if arg.lower() == "commoner":
                is_regent = False
            elif arg.lower() in ["tainted", "minor", "major", "great", "true"]:
                strength = BloodlineStrength(arg.title())

        # Generate random character
        self.character = BirthrightCharacter.generate_random(
            is_regent=is_regent,
            bloodline_strength=strength
        )

        # Auto-save
        filepath = save_character(self.character)

        sheet = format_character_sheet(self.character)
        return CommandResult(
            success=True,
            message=f"{sheet}\n\n[dim]Character saved to: {filepath}[/dim]",
            panel_title="New Character Created",
            style="green"
        )

    def _cmd_loadchar(self, args: list[str], raw: str) -> CommandResult:
        """Load a saved character."""
        if not BIRTHRIGHT_AVAILABLE:
            return CommandResult(
                success=False,
                message="Birthright modules not available.",
                style="red"
            )

        characters = list_characters()

        if not args:
            if not characters:
                return CommandResult(
                    success=False,
                    message="No saved characters found. Use 'newchar' to create one.",
                    style="yellow"
                )
            lines = ["Saved characters:"]
            for char_name in characters:
                lines.append(f"  [cyan]{char_name}[/cyan]")
            lines.append("\nUsage: loadchar <name>")
            return CommandResult(
                success=True,
                message="\n".join(lines),
                style="white"
            )

        char_name = args[0]
        if not char_name.endswith(".json"):
            char_name += ".json"

        try:
            self.character = load_character(char_name)
            sheet = format_character_sheet(self.character)
            return CommandResult(
                success=True,
                message=sheet,
                panel_title=f"Loaded: {self.character.name}",
                style="green"
            )
        except FileNotFoundError:
            return CommandResult(
                success=False,
                message=f"Character not found: {char_name}",
                style="red"
            )

    def _cmd_domain(self, args: list[str], raw: str) -> CommandResult:
        """Display domain information."""
        if not BIRTHRIGHT_AVAILABLE:
            return CommandResult(
                success=False,
                message="Birthright modules not available.",
                style="red"
            )

        if self.character is None or not self.character.is_regent:
            return CommandResult(
                success=False,
                message="No regent character loaded. Create one with 'newchar'.",
                style="yellow"
            )

        d = self.character.domain
        lines = [
            f"[bold]{d.name}[/bold]",
            "",
            f"Provinces: {', '.join(d.provinces) or 'None'}",
            "",
            "Holdings:",
            f"  Law:    {d.law_holdings}",
            f"  Temple: {d.temple_holdings}",
            f"  Guild:  {d.guild_holdings}",
            f"  Source: {d.source_holdings}",
            "",
            "Resources:",
            f"  Regency Points: {d.regency_points} RP",
            f"  Gold Bars:      {d.gold_bars} GB",
        ]
        if d.armies:
            lines.append("")
            lines.append(f"Armies: {', '.join(d.armies)}")

        return CommandResult(
            success=True,
            message="\n".join(lines),
            panel_title="Domain Status",
            style="cyan"
        )

    def _cmd_regency(self, args: list[str], raw: str) -> CommandResult:
        """Adjust regency points."""
        if not BIRTHRIGHT_AVAILABLE:
            return CommandResult(
                success=False,
                message="Birthright modules not available.",
                style="red"
            )

        if self.character is None or not self.character.is_regent:
            return CommandResult(
                success=False,
                message="No regent character loaded.",
                style="yellow"
            )

        if not args:
            return CommandResult(
                success=True,
                message=f"Current Regency: {self.character.domain.regency_points} RP\n\nUsage: regency <+/-amount>",
                style="white"
            )

        try:
            change = int(args[0])
            self.character.domain.regency_points += change
            save_character(self.character)
            return CommandResult(
                success=True,
                message=f"Regency: {self.character.domain.regency_points} RP ({change:+d})",
                style="green" if change >= 0 else "red"
            )
        except ValueError:
            return CommandResult(
                success=False,
                message="Usage: regency <+/-amount>",
                style="yellow"
            )

    def _cmd_bloodline(self, args: list[str], raw: str) -> CommandResult:
        """Display bloodline information."""
        if not BIRTHRIGHT_AVAILABLE:
            return CommandResult(
                success=False,
                message="Birthright modules not available.",
                style="red"
            )

        if self.character is None:
            return CommandResult(
                success=False,
                message="No character loaded.",
                style="yellow"
            )

        b = self.character.bloodline
        if b.derivation.value == "None":
            return CommandResult(
                success=True,
                message="This character is unblooded.",
                style="dim"
            )

        lines = [
            f"[bold]Bloodline of {b.derivation.value}[/bold]",
            "",
            f"Strength: {b.strength.value} (Score: {b.score})",
            "",
            "Blood Abilities:",
        ]
        for ability in b.abilities:
            lines.append(f"  • {ability}")

        return CommandResult(
            success=True,
            message="\n".join(lines),
            panel_title="Bloodline",
            style="magenta"
        )


def run_cli():
    """Main entry point for the CLI."""
    cli = OracleCLI()
    cli.run()
