from rubicon.objc import SEL, NSPoint, at, objc_method, objc_property
from travertino.size import at_least
from toga.constants import CENTER, JUSTIFY, LEFT, RIGHT
from toga_cocoa.colors import native_color
from toga.colors import color as parse_color


import toga
from toga_cocoa.libs import (
    NSBezelBorder,
    NSColor,
    NSIndexSet,
    NSRange,
    NSScrollView,
    NSTableColumn,
    NSTableView,
    NSSortDescriptor,
    NSTableViewAnimation,
    NSTableViewColumnAutoresizingStyle,
    NSTextAlignment,
)

from toga_cocoa.widgets.base import Widget
from toga_cocoa.widgets.internal.cells import TogaIconView


class CustomTogaTable(NSTableView):
    interface = objc_property(object, weak=True)
    impl = objc_property(object, weak=True)

    # NSTableView methods
    @objc_method
    def canDragRowsWithIndexes_atPoint_(
        self,
        rowIndexes,
        mouseDownPoint: NSPoint,
    ) -> bool:
        # Disable all drags
        return False

    # TableDataSource methods
    @objc_method
    def numberOfRowsInTableView_(self, table) -> int:
        return len(self.interface.data) if self.interface.data else 0

    @objc_method
    def tableView_viewForTableColumn_row_(self, table, column, row: int):
        data_row = self.interface.data[row]
        col_identifier = str(column.identifier)

        value = getattr(data_row, col_identifier, None)

        # if the value is a widget itself, just draw the widget!
        if isinstance(value, toga.Widget):
            return value._impl.native
        
        # Default color is None
        color_val = None
        icon = None

        # If the value is a dictionary, unpack it
        if isinstance(value, dict):
            color_val = value.get("color")
            value = value.get("value")

        # Allow for an (icon, value) tuple as the simple case
        # for encoding an icon in a table cell. Otherwise, look
        # for an icon attribute.
        elif isinstance(value, tuple):
            icon, value = value
        else:
            try:
                icon = value.icon
            except AttributeError:
                icon = None

        if value is None:
            value = self.interface.missing_value

        # creates a NSTableCellView from interface-builder template (does not exist)
        # or reuses an existing view which is currently not needed for painting
        # returns None (nil) if both fails
        identifier = at(f"CellView_{self.interface.id}")
        tcv = self.makeViewWithIdentifier(identifier, owner=self)

        if not tcv:  # there is no existing view to reuse so create a new one
            tcv = TogaIconView.alloc().init()
            tcv.identifier = identifier
        
        tcv.setText(str(value))

        # Determine text alignment
        alignment = LEFT  # Default alignment
        
        # Check if column has specific alignment in column_options
        if hasattr(self.interface, "column_options") and col_identifier in self.interface.column_options:
            column_opts = self.interface.column_options[col_identifier]
            if "alignment" in column_opts:
                alignment = column_opts["alignment"]
        
        # Convert to NSTextAlignment
        if alignment == RIGHT:
            tcv.textField.alignment = NSTextAlignment(RIGHT)
        elif alignment == CENTER:
            tcv.textField.alignment = NSTextAlignment(CENTER)
        elif alignment == JUSTIFY:
            tcv.textField.alignment = NSTextAlignment(JUSTIFY)
        else:  # LEFT or default
            tcv.textField.alignment = NSTextAlignment(LEFT)

        if color_val:
            # If a color is found, convert it to a native NSColor and apply it.
            try:
                tcv.textField.textColor = native_color(parse_color(color_val))
            except Exception as e:
                print(f"Error setting text color: {e}")

        if icon:
            tcv.setImage(icon._impl.native)
        else:
            tcv.setImage(None)

        return tcv

    @objc_method
    def tableView_pasteboardWriterForRow_(self, table, row) -> None:  # pragma: no cover
        # this seems to be required to prevent issue 21562075 in AppKit
        return None

    # TableDelegate methods
    @objc_method
    def selectionShouldChangeInTableView_(self, table) -> bool:
        # Explicitly allow selection on the table.
        # TODO: return False to disable selection.
        return True

    @objc_method
    def tableViewSelectionDidChange_(self, notification) -> None:
        self.interface.on_select()

    # 2021-09-04: Commented out this method because it appears to be a
    # source of significant slowdown when the table has a lot of data
    # (10k rows). AFAICT, it's only needed if we want custom row heights
    # for each row. Since we don't currently support custom row heights,
    # we're paying the cost for no benefit.
    # @objc_method
    # def tableView_heightOfRow_(self, table, row: int) -> float:
    #     default_row_height = self.rowHeight
    #     margin = 2
    #
    #     # get all views in column
    #     data_row = self.interface.data[row]
    #
    #     heights = [default_row_height]
    #
    #     for column in self.tableColumns:
    #         col_identifier = str(column.identifier)
    #         value = getattr(data_row, col_identifier, None)
    #         if isinstance(value, toga.Widget):
    #             # if the cell value is a widget, use its height
    #             heights.append(
    #                 value._impl.native.intrinsicContentSize().height + margin
    #             )
    #
    #     return max(heights)

    @objc_method
    def tableView_sortDescriptorsDidChange_(self, notification) -> None:
        """This method is called by AppKit when the user clicks a column header."""
        # Get the new sort descriptor (usually only one).
        descriptor = self.sortDescriptors[0]
        
        # Get the accessor for the column and the sort direction.
        key = str(descriptor.key)
        ascending = bool(descriptor.ascending)

        def sort_key_function(row):
            value = getattr(row, key)
            # If the cell's data is a dictionary (e.g., {"value": 150, "color": "green"}),
            # extract the actual value to use for sorting.
            if isinstance(value, dict):
                return value.get("value")
            return value

        self.interface.data._data.sort(
            key=sort_key_function,
            reverse=not ascending
        )

        # Tell the table view to refresh its data to show the new order.
        self.reloadData()

    # target methods
    @objc_method
    def onDoubleClick_(self, sender) -> None:
        clicked = self.interface.data[self.clickedRow]

        self.interface.on_activate(row=clicked)


class Table(Widget):
    def create(self):
        # Create a table view, and put it in a scroll view.
        # The scroll view is the native, because it's the outer container.
        self.native = NSScrollView.alloc().init()
        self.native.hasVerticalScroller = True
        self.native.hasHorizontalScroller = False
        self.native.autohidesScrollers = True
        self.native.borderType = NSBezelBorder

        self.native_table = CustomTogaTable.alloc().init()
        self.native_table.interface = self.interface
        self.native_table.impl = self
        # self.native_table.columnAutoresizingStyle = 0
        self.native_table.columnAutoresizingStyle = (
            NSTableViewColumnAutoresizingStyle.Uniform
        )
        self.native_table.usesAlternatingRowBackgroundColors = True
        self.native_table.allowsMultipleSelection = self.interface.multiple_select
        self.native_table.allowsColumnReordering = False

        # Create columns for the table
        self.columns = []
        if self.interface.headings:
            for index, (heading, accessor) in enumerate(
                zip(self.interface.headings, self.interface.accessors)
            ):
                self._insert_column(index, heading, accessor)
        else:
            self.native_table.setHeaderView(None)
            for index, accessor in enumerate(self.interface.accessors):
                self._insert_column(index, None, accessor)

        self.native_table.delegate = self.native_table
        self.native_table.dataSource = self.native_table
        self.native_table.target = self.native_table
        self.native_table.doubleAction = SEL("onDoubleClick:")

        # Embed the table view in the scroll view
        self.native.documentView = self.native_table

        # Add the layout constraints
        self.add_constraints()

    def change_source(self, source):
        self.native_table.reloadData()

    def insert(self, index, item):
        # set parent = None if inserting to the root item
        index_set = NSIndexSet.indexSetWithIndex(index)

        self.native_table.insertRowsAtIndexes(
            index_set, withAnimation=NSTableViewAnimation.EffectNone
        )

    def change(self, item):
        row_index = self.interface.data.index(item)
        row_indexes = NSIndexSet.indexSetWithIndex(row_index)
        column_indexes = NSIndexSet.indexSetWithIndexesInRange(
            NSRange(0, len(self.columns))
        )

        self.native_table.reloadDataForRowIndexes(
            row_indexes, columnIndexes=column_indexes
        )

    def remove(self, index, item):
        indexes = NSIndexSet.indexSetWithIndex(index)
        self.native_table.removeRowsAtIndexes(
            indexes, withAnimation=NSTableViewAnimation.EffectNone
        )

    def clear(self):
        self.native_table.reloadData()

    def get_selection(self):
        if self.interface.multiple_select:
            selection = []

            current_index = self.native_table.selectedRowIndexes.firstIndex
            for i in range(self.native_table.selectedRowIndexes.count):
                selection.append(current_index)
                current_index = (
                    self.native_table.selectedRowIndexes.indexGreaterThanIndex(
                        current_index
                    )
                )

            return selection
        else:
            index = self.native_table.selectedRow
            if index != -1:
                return index
            else:
                return None

    def scroll_to_row(self, row):
        self.native_table.scrollRowToVisible(row)

    def rehint(self):
        self.interface.intrinsic.width = at_least(self.interface._MIN_WIDTH)
        self.interface.intrinsic.height = at_least(self.interface._MIN_HEIGHT)
        self.apply_column_options()

    def apply_column_options(self):
        """Applies column settings from the interface's `column_options` dict."""
        if not hasattr(self.interface, "column_options"):
            return

        # Create a mapping from accessor to native column object for easy lookup.
        native_columns = {
            str(col.identifier): col for col in self.native_table.tableColumns
        }

        for accessor, options in self.interface.column_options.items():
            column = native_columns.get(accessor)
            if column:
                if "width" in options:
                    column.width = options["width"]
                if "min_width" in options:
                    column.minWidth = options["min_width"]
                if "max_width" in options:
                    column.maxWidth = options["max_width"]

    def _insert_column(self, index, heading, accessor):
        # This method is now simplified, the width logic is moved.
        column = NSTableColumn.alloc().initWithIdentifier(accessor)
        sort_descriptor = NSSortDescriptor.alloc().initWithKey(
            accessor, ascending=True
        )
        column.sortDescriptorPrototype = sort_descriptor
        self.columns.insert(index, column)
        self.native_table.addTableColumn(column)
        if index != len(self.columns) - 1:
            self.native_table.moveColumn(len(self.columns) - 1, toColumn=index)

        if heading is not None:
            column.headerCell.stringValue = heading

    def insert_column(self, index, heading, accessor):
        self._insert_column(index, heading, accessor)
        self.native_table.sizeToFit()

    def remove_column(self, index):
        column = self.columns[index]
        self.native_table.removeTableColumn(column)

        # delete column and identifier
        self.columns.remove(column)
        self.native_table.sizeToFit()
