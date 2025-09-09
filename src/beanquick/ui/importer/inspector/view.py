"""
Inspector Panel View - Pure UI presentation layer.
"""
import sys
import logging
from typing import Optional, Callable

import toga
from toga.style import Pack
from toga.style.pack import CENTER, COLUMN, BOLD  # type: ignore

from beanquick.ui.importer.inspector.entry_saver import PreviewContentAdapter

logger = logging.getLogger(__name__)

if sys.platform == 'darwin':
    try:
        from toga_cocoa.libs import NSColor
    except ImportError:
        NSColor = None

class InspectorPanelView:
    """Pure UI presentation layer for Inspector Panel.
    
    Responsibilities:
    - Create and layout UI components
    - Handle UI state transitions (content/no-selection)
    - Delegate user events to controller
    - Provide clean API for data updates
    """
    
    def __init__(self, on_tab_select: Optional[Callable[[str], None]] = None):
        """Initialize the view with minimal dependencies.
        """
        # UI Components
        self._option_container: Optional[toga.OptionContainer] = None
        self._transaction_panel: Optional[toga.ScrollContainer] = None
        self._no_selection_container: Optional[toga.Box] = None
        self._content_container: Optional[toga.Box] = None
        self._preview_panel: Optional[toga.ScrollContainer] = None
        self._preview_container: Optional[toga.Box] = None
        
        # Child components - will be injected by controller
        self._entry_preview = None
        self._all_transactions_preview = None
        self._entry_saver = None
        self._rule_workspace = None
        self._source_data_display = None
        
        # Rule container visibility state
        self._rule_container_widget = None
        self._rule_container_visible = False

        # Callback for tab selection
        self._on_tab_select = on_tab_select
    
    def create_widget(self) -> toga.ScrollContainer:
        """Create the main panel widget.
        
        Returns:
            toga.ScrollContainer: The main panel container
        """
        if self._option_container is None:
            self._create_no_selection_state()
            self._create_preview_container()

            self._transaction_panel = toga.ScrollContainer(
                style=Pack(flex=1),
                content=self._no_selection_container
            )

            self._preview_panel= toga.ScrollContainer(
                style=Pack(flex=1),
                content=self._preview_container
            )

            assert self._transaction_panel is not None
            assert self._preview_panel is not None
            
            if sys.platform == "darwin" and NSColor:
                try:
                    # self._transaction_panel._impl.native.backgroundColor = NSColor.windowBackgroundColor
                    self._transaction_panel._impl.native.drawsBackground = False
                    self._preview_panel._impl.native.drawsBackground = False
                except (AttributeError, TypeError):
                    pass  # Fallback to default styling

            self._option_container = toga.OptionContainer(
                content=[
                    ("Info", self._transaction_panel),
                    ("Preview", self._preview_panel)
                ],
                style=Pack(flex=1, direction=COLUMN, margin_top=10),
                on_select=self._handle_tab_select
            )
        
        return self._option_container
    
    def _handle_tab_select(self, widget: toga.OptionContainer, **kwargs):
        """Handle tab selection changes.
        
        Args:
            widget: The OptionContainer that had a selection change
            **kwargs: Additional arguments for future compatibility
        """
        if widget.current_tab and self._on_tab_select:
            tab_name = widget.current_tab.text
            logger.debug(f"Tab selected: {tab_name}")
            self._on_tab_select(tab_name)
    
    def set_components(
            self, entry_preview,
            all_transactions_preview, entry_saver,
            rule_workspace, source_data_display,
        ):
        """Inject child components (dependency injection pattern).
        
        This method allows the controller to inject the required child components
        into the view after initialization. This follows the dependency injection
        pattern to keep the view loosely coupled from its dependencies.
        
        Args:
            entry_preview: EntryPreview instance for displaying transaction details in Info tab
            all_transactions_preview: EntryPreview instance for displaying all transactions in Preview tab
            entry_saver: EntrySaver component for handling transaction persistence
            rule_workspace: RuleWorkspace component for rule management functionality
            source_data_display: SourceDataDisplay component for showing source import data
        """
        self._entry_preview = entry_preview
        self._all_transactions_preview = all_transactions_preview
        self._entry_saver = entry_saver
        self._rule_workspace = rule_workspace
        self._source_data_display = source_data_display

    def show_transaction_content(self):
        """Switch to content view showing transaction details."""
        if not self._transaction_panel:
            return
        
        if not self._content_container:
            self._create_content_container()
        
        self._transaction_panel.content = self._content_container
        
    def show_no_selection(self):
        """Switch to 'No Selection' state view."""
        if not self._transaction_panel or not self._no_selection_container:
            return
        
        self._transaction_panel.content = self._no_selection_container
     
    def _create_no_selection_state(self) -> None:
        """Create the no selection state container."""
        no_selection_label = toga.Label(
            "No Selection",
            style=Pack(
                font_weight=BOLD,
                text_align=CENTER,
            )
        )

        self._no_selection_container = toga.Box(
            style=Pack(
                direction=COLUMN,
                flex=1,
                align_items=CENTER
            ),
            children=[
                toga.Box(style=Pack(flex=1)),
                no_selection_label,
                toga.Box(style=Pack(flex=1)),
            ]
        )
    
    def _create_preview_container(self) -> None:
        """Create the preview container for the Preview tab."""
        if not self._all_transactions_preview or not self._entry_saver:
            raise RuntimeError("Components must be set before creating content container")

        self._preview_container = toga.Box(
            style=Pack(direction=COLUMN, flex=1, margin=(0, 10, 10)),
            children=[
                self._all_transactions_preview.create_widget(),
                self._entry_saver.create_widget(),
            ]
        )

        content_adapter = PreviewContentAdapter(self._all_transactions_preview)
        self._entry_saver.set_content_source(content_adapter)

    def _create_content_container(self) -> None:
        """Create the content container with child components."""
        if not self._entry_preview or not self._rule_workspace or not self._source_data_display:
            raise RuntimeError("Components must be set before creating content container")
        
        self._content_container = toga.Box(
            style=Pack(
                direction=COLUMN,
                flex=1,
                margin=(0, 10, 10),
            ),
            children=[
                self._entry_preview.create_widget(),
                self._source_data_display.create_widget(),
                self._rule_workspace.create_widget(),
            ]
        )