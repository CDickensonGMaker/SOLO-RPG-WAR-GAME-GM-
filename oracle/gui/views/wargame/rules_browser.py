"""
Rules Browser Panel - Searchable rules reference for wargames.

Provides:
- Search by rule name or keyword
- Filter by category/tag
- Full rule text display
- System-specific rules filtering
"""

from typing import Callable, Optional, List
import dearpygui.dearpygui as dpg

from oracle.gui.models.wargame_data import get_wargame_data, WargameDataModel
from oracle.gamesystems import RuleReference, GameSystem


# Callback types
RuleSelectedCallback = Callable[[RuleReference], None]


class RulesBrowserPanel:
    """
    Searchable rules reference browser.

    Displays rules from the currently selected game system with
    search and filtering capabilities.
    """

    def __init__(
        self,
        parent: str,
        on_rule_selected: Optional[RuleSelectedCallback] = None,
        width: int = 350,
        height: int = -1,
    ):
        """
        Create the rules browser panel.

        Args:
            parent: Parent DearPyGui item tag
            on_rule_selected: Callback when a rule is clicked
            width: Panel width
            height: Panel height (-1 for auto)
        """
        self.parent = parent
        self._on_rule_selected = on_rule_selected
        self.width = width
        self.height = height

        self._wargame_data = get_wargame_data()
        self._rules: List[RuleReference] = []
        self._filtered_rules: List[RuleReference] = []
        self._selected_rule: Optional[RuleReference] = None
        self._search_query = ""
        self._category_filter = "All"

        # UI tags
        self._tag = f"rules_browser_{id(self)}"
        self._search_tag = f"{self._tag}_search"
        self._category_tag = f"{self._tag}_category"
        self._list_tag = f"{self._tag}_list"
        self._detail_tag = f"{self._tag}_detail"
        self._detail_name_tag = f"{self._tag}_detail_name"
        self._detail_text_tag = f"{self._tag}_detail_text"
        self._detail_keywords_tag = f"{self._tag}_detail_keywords"
        self._detail_examples_tag = f"{self._tag}_detail_examples"

        # Register observer
        self._wargame_data.add_observer(self._on_system_changed)

        self._build()
        self._load_rules()

    def _build(self):
        """Build the UI components."""
        with dpg.child_window(
            parent=self.parent,
            width=self.width,
            height=self.height,
            border=True,
            tag=f"{self._tag}_root"
        ):
            dpg.add_text("Rules Reference", color=(140, 180, 140))
            dpg.add_separator()

            # Search bar
            dpg.add_text("Search:", color=(150, 150, 150))
            dpg.add_input_text(
                hint="Search rules...",
                callback=self._on_search,
                tag=self._search_tag,
                width=-1,
            )

            dpg.add_spacer(height=5)

            # Category filter
            dpg.add_text("Category:", color=(150, 150, 150))
            dpg.add_combo(
                items=["All"],
                default_value="All",
                callback=self._on_category_change,
                tag=self._category_tag,
                width=-1,
            )

            dpg.add_spacer(height=10)
            dpg.add_separator()

            # Rules list
            dpg.add_text("Rules:", color=(150, 150, 150))
            with dpg.child_window(
                height=200,
                border=True,
                tag=self._list_tag,
            ):
                dpg.add_text("Select a game system to view rules",
                           color=(100, 100, 100),
                           tag=f"{self._tag}_placeholder")

            dpg.add_spacer(height=10)
            dpg.add_separator()

            # Rule detail view
            with dpg.collapsing_header(
                label="Rule Details",
                default_open=True,
                tag=self._detail_tag,
            ):
                dpg.add_text(
                    "No rule selected",
                    tag=self._detail_name_tag,
                    color=(200, 200, 140),
                    wrap=self.width - 40,
                )
                dpg.add_spacer(height=5)
                dpg.add_text(
                    "",
                    tag=self._detail_text_tag,
                    wrap=self.width - 40,
                )
                dpg.add_spacer(height=5)
                dpg.add_text(
                    "",
                    tag=self._detail_keywords_tag,
                    color=(140, 140, 180),
                    wrap=self.width - 40,
                )
                dpg.add_spacer(height=5)
                dpg.add_text(
                    "",
                    tag=self._detail_examples_tag,
                    color=(120, 160, 120),
                    wrap=self.width - 40,
                )

    def _load_rules(self):
        """Load rules from the current game system."""
        if not self._wargame_data.current_system:
            self._rules = []
            self._filtered_rules = []
            self._update_list()
            return

        # Get all rules from the wargame data model
        rules_dict = self._wargame_data.rules
        self._rules = list(rules_dict.values())

        # Extract categories from rule keywords
        categories = set(["All"])
        for rule in self._rules:
            for kw in rule.keywords:
                categories.add(kw.title())

        # Update category dropdown
        category_list = sorted(categories)
        dpg.configure_item(self._category_tag, items=category_list)

        # Apply current filter
        self._apply_filter()

    def _apply_filter(self):
        """Apply search and category filters to rules list."""
        self._filtered_rules = []

        for rule in self._rules:
            # Search filter
            if self._search_query:
                query_lower = self._search_query.lower()
                if not (
                    query_lower in rule.name.lower() or
                    query_lower in rule.description.lower() or
                    any(query_lower in kw.lower() for kw in rule.keywords)
                ):
                    continue

            # Category filter
            if self._category_filter != "All":
                if not any(
                    self._category_filter.lower() == kw.lower()
                    for kw in rule.keywords
                ):
                    continue

            self._filtered_rules.append(rule)

        # Sort alphabetically
        self._filtered_rules.sort(key=lambda r: r.name.lower())

        self._update_list()

    def _update_list(self):
        """Update the rules list display."""
        # Clear existing list
        dpg.delete_item(self._list_tag, children_only=True)

        if not self._filtered_rules:
            dpg.add_text(
                "No rules found" if self._rules else "Select a game system",
                parent=self._list_tag,
                color=(100, 100, 100),
            )
            return

        # Add rule buttons
        for rule in self._filtered_rules:
            # Truncate long names
            display_name = rule.name
            if len(display_name) > 35:
                display_name = display_name[:32] + "..."

            dpg.add_button(
                label=display_name,
                callback=lambda s, a, u: self._select_rule(u),
                user_data=rule,
                parent=self._list_tag,
                width=-1,
            )

    def _select_rule(self, rule: RuleReference):
        """Select and display a rule's details."""
        self._selected_rule = rule

        # Update detail view
        dpg.set_value(self._detail_name_tag, f">> {rule.name}")
        dpg.set_value(self._detail_text_tag, rule.description)

        # Keywords
        if rule.keywords:
            keywords_text = f"Keywords: {', '.join(rule.keywords)}"
        else:
            keywords_text = ""
        dpg.set_value(self._detail_keywords_tag, keywords_text)

        # Examples
        if rule.examples:
            examples_text = "Examples:\n" + "\n".join(f"  - {ex}" for ex in rule.examples)
        else:
            examples_text = ""
        dpg.set_value(self._detail_examples_tag, examples_text)

        # Callback
        if self._on_rule_selected:
            self._on_rule_selected(rule)

    def _on_search(self, sender, app_data, user_data):
        """Handle search input change."""
        self._search_query = app_data
        self._apply_filter()

    def _on_category_change(self, sender, app_data, user_data):
        """Handle category filter change."""
        self._category_filter = app_data
        self._apply_filter()

    def _on_system_changed(self, event: str, data):
        """Handle game system change."""
        if event == "system_changed":
            self._load_rules()
            # Clear selection
            self._selected_rule = None
            dpg.set_value(self._detail_name_tag, "No rule selected")
            dpg.set_value(self._detail_text_tag, "")
            dpg.set_value(self._detail_keywords_tag, "")
            dpg.set_value(self._detail_examples_tag, "")

    def search(self, query: str):
        """
        Programmatically search for rules.

        Args:
            query: Search string
        """
        self._search_query = query
        dpg.set_value(self._search_tag, query)
        self._apply_filter()

    def get_rule(self, name: str) -> Optional[RuleReference]:
        """
        Get a rule by exact name.

        Args:
            name: Rule name

        Returns:
            RuleReference if found
        """
        name_lower = name.lower()
        for rule in self._rules:
            if rule.name.lower() == name_lower:
                return rule
        return None

    def get_rules_by_keyword(self, keyword: str) -> List[RuleReference]:
        """
        Get all rules with a specific keyword.

        Args:
            keyword: Keyword to filter by

        Returns:
            List of matching rules
        """
        keyword_lower = keyword.lower()
        return [
            r for r in self._rules
            if any(keyword_lower in kw.lower() for kw in r.keywords)
        ]

    @property
    def current_rules(self) -> List[RuleReference]:
        """Get currently filtered rules."""
        return self._filtered_rules.copy()

    @property
    def selected_rule(self) -> Optional[RuleReference]:
        """Get currently selected rule."""
        return self._selected_rule

    def _rebuild_in_parent(self, new_parent: str):
        """Rebuild the panel content in a new parent (for pop-out support)."""
        # Delete existing root if it exists
        root_tag = f"{self._tag}_root"
        if dpg.does_item_exist(root_tag):
            dpg.delete_item(root_tag)

        # Update parent and rebuild
        self.parent = new_parent
        self._build()
        self._load_rules()


class CompactRulesSearch:
    """
    Compact rules search widget for embedding in other panels.

    Provides quick rule lookup without full browser interface.
    """

    def __init__(
        self,
        parent: str,
        on_rule_found: Optional[RuleSelectedCallback] = None,
        width: int = -1,
    ):
        """
        Create compact rules search.

        Args:
            parent: Parent DearPyGui item tag
            on_rule_found: Callback when rule is found
            width: Widget width
        """
        self.parent = parent
        self._on_rule_found = on_rule_found
        self.width = width

        self._wargame_data = get_wargame_data()

        self._tag = f"compact_rules_{id(self)}"
        self._search_tag = f"{self._tag}_search"
        self._result_tag = f"{self._tag}_result"

        self._build()

    def _build(self):
        """Build the UI components."""
        with dpg.group(parent=self.parent, horizontal=True):
            dpg.add_input_text(
                hint="Quick rule lookup...",
                callback=self._on_search,
                on_enter=True,
                tag=self._search_tag,
                width=self.width - 60 if self.width > 0 else -60,
            )
            dpg.add_button(
                label="?",
                callback=self._do_search,
                width=50,
            )

        dpg.add_text(
            "",
            tag=self._result_tag,
            parent=self.parent,
            wrap=self.width - 20 if self.width > 0 else 300,
            color=(180, 180, 140),
        )

    def _on_search(self, sender, app_data, user_data):
        """Handle enter key in search."""
        self._do_search()

    def _do_search(self, sender=None, app_data=None, user_data=None):
        """Execute the search."""
        query = dpg.get_value(self._search_tag)
        if not query:
            dpg.set_value(self._result_tag, "")
            return

        if not self._wargame_data.current_system:
            dpg.set_value(self._result_tag, "No game system selected")
            return

        # Search rules
        results = self._wargame_data.search_rules(query)

        if not results:
            dpg.set_value(self._result_tag, f"No rules found for '{query}'")
            return

        # Show first result
        rule = results[0]
        summary = rule.description[:150] + "..." if len(rule.description) > 150 else rule.description
        dpg.set_value(self._result_tag, f"{rule.name}: {summary}")

        if self._on_rule_found:
            self._on_rule_found(rule)
