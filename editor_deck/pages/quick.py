"""Quick page: tools for the open script, in labelled groups of tiles.

Tools that change the open script, or make a new one, bring the editor
forward afterwards so you land on the result (bridge.bring_editor_forward).
Copy tools leave you in the deck.
"""
import os

import clipboard
import ui

from .. import editor_bridge as bridge
from .. import keyboard
from ..style import BOLD, COLOURS
from .rename_sheet import RenameSheet
from .tiles import TILE_GAP, TILE_HEIGHT, Tool, ToolTile

MINIMISE_AFTER_ACTION = False   # True: fold the deck away after each tool
CONSTANTS_PAGE = 2              # index of the Constants tab
COLUMNS = 2
HEADING_HEIGHT = 22
SECTION_GAP = 14


class ClearPressOnScroll:
    """ScrollView delegate: any scroll clears every tile's highlight, and a
    finger dragging the page closes the keyboard."""

    def __init__(self, tiles):
        self.tiles = tiles

    def scrollview_did_scroll(self, scrollview):
        if scrollview.dragging:
            keyboard.dismiss()
        for tile in self.tiles:
            if tile.pressed_at is not None:
                tile.release_press()


class QuickPage(ui.View):
    """Groups of ToolTiles in a ScrollView. ui.ScrollView cannot be
    subclassed, so the page holds one and lays the tiles out inside it."""

    def __init__(self, deck):
        self.deck = deck
        self.rename_sheet = None
        self.sections = []      # (heading label, [tiles])
        self.tiles = []

        self.scroll = ui.ScrollView()
        self.scroll.shows_vertical_indicator = True
        self.scroll_delegate = ClearPressOnScroll(self.tiles)
        self.scroll.delegate = self.scroll_delegate
        self.add_subview(self.scroll)

        self.add_section('COPY', [
            Tool('📋', 'Copy Script',
                 'Copies the whole open script to the clipboard, including edits '
                 'you have not saved yet. Handy for pasting into a chat. You stay '
                 'in the deck.', self.copy_script),
            Tool('📂', 'Copy Path',
                 "Copies the open script's full file path to the clipboard, the "
                 'kind of path open() and os functions expect. You stay in the deck.',
                 self.copy_path),
            Tool('▶️', 'Run URL',
                 'Copies a pythonista3:// link that opens Pythonista and runs this '
                 'script, for Shortcuts or a home-screen bookmark. Only works for '
                 'scripts inside Documents.', self.copy_run_url),
            Tool('📝', 'Open URL',
                 'Copies a pythonista3:// link that opens this script in the editor '
                 'without running it. Only works for scripts inside Documents.',
                 self.copy_open_url),
        ])
        self.add_section('SCRIPT', [
            Tool('🗒️', 'Scratch Pad',
                 'Creates a blank scratch_pad.py in the same folder as the open '
                 'script (scratch_pad_2.py and so on when taken) and opens it in a '
                 'new tab, ready for quick work.', self.open_scratch_pad),
            Tool('✏️', 'Rename',
                 "Renames the open script in its folder using Pythonista's own "
                 'rename, so its tab follows. Leave off the extension to keep the '
                 'current one. Names that already exist are refused.', self.open_rename),
            Tool('📄', 'Duplicate',
                 'Saves a copy of the open script beside it (demo_copy.py, then '
                 'demo_copy_2.py), unsaved edits included, and opens the copy in a '
                 'new tab.', self.duplicate_script),
            Tool('🎛️', 'Constants',
                 "Switches to the Constants page, where the script's top-level "
                 'settings can be tuned with sliders, switches and colour pickers.',
                 self.open_constants, tint=COLOURS['accent']),
        ])
        self.add_section('CLIPBOARD', [
            Tool('📥', 'Replace',
                 "Replaces the entire open script with the clipboard's text, then "
                 'shows you the editor. Use it to drop in a whole new version from a '
                 'chat.', self.replace_with_clipboard, tint=COLOURS['warn']),
            Tool('➕', 'Append',
                 "Adds the clipboard's text to the end of the open script, on a new "
                 'line, then shows you the editor.', self.append_clipboard),
        ])
        self.add_section('DANGER', [
            Tool('🧹', 'Clear',
                 'Removes every line from the open script, leaving it blank, then '
                 'shows you the editor. Needs a second tap within 3 seconds.',
                 self.clear_script, tint=COLOURS['danger'], confirm=True),
            Tool('🗑️', 'Delete',
                 "Closes the open script's tab and permanently deletes its file. "
                 'There is no undo and it does not go to a bin. Needs a second tap '
                 'within 3 seconds.', self.delete_script,
                 tint=COLOURS['danger'], confirm=True),
        ])

    def add_section(self, heading, tools):
        label = ui.Label()
        label.text = heading
        label.font = (BOLD, 11)
        label.text_color = COLOURS['muted']
        self.scroll.add_subview(label)
        tiles = [ToolTile(tool, self.explain) for tool in tools]
        for tile in tiles:
            self.scroll.add_subview(tile)
        self.sections.append((label, tiles))
        self.tiles.extend(tiles)

    def layout(self):
        width = self.width
        self.scroll.frame = (0, 0, width, self.height)
        column_width = (width - TILE_GAP * (COLUMNS - 1)) / COLUMNS
        y = 0
        for heading, tiles in self.sections:
            heading.frame = (2, y, width, HEADING_HEIGHT)
            y += HEADING_HEIGHT
            for index, tile in enumerate(tiles):
                row, column = divmod(index, COLUMNS)
                tile.frame = (column * (column_width + TILE_GAP),
                              y + row * (TILE_HEIGHT + TILE_GAP),
                              column_width, TILE_HEIGHT)
            rows = (len(tiles) + COLUMNS - 1) // COLUMNS
            y += rows * (TILE_HEIGHT + TILE_GAP) - TILE_GAP + SECTION_GAP
        self.scroll.content_size = (width, max(y, self.height + 1))
        if self.rename_sheet is not None:
            self.rename_sheet.frame = (0, 0, width, self.height)

    def tick(self, now):
        for tile in self.tiles:
            tile.tick(now)

    # --- Help mode ------------------------------------------------------------
    def set_help_mode(self, on):
        for tile in self.tiles:
            tile.set_help_mode(on)

    def explain(self, tool):
        self.deck.show_help('%s  %s' % (tool.icon, tool.title), tool.description)

    def done(self, reveal=False):
        """After a tool: show the editor if it changed or opened a script."""
        if reveal:
            bridge.bring_editor_forward()
        if MINIMISE_AFTER_ACTION:
            self.deck.minimise()

    # --- Copy -----------------------------------------------------------------
    def copy_script(self):
        if not bridge.active_path():
            bridge.hud('No open script', 'error')
            return
        bridge.copy_text(bridge.active_text(), 'Script copied')
        self.done()

    def copy_path(self):
        path = bridge.active_path()
        if path:
            bridge.copy_text(path, 'Path copied')
            self.done()
        else:
            bridge.hud('No open script', 'error')

    def copy_run_url(self):
        self.copy_url('run')

    def copy_open_url(self):
        self.copy_url('open')

    def copy_url(self, action):
        url = bridge.script_url(action)
        if url:
            bridge.copy_text(url, '%s URL copied' % action.title())
            self.done()
        else:
            bridge.hud('No URL for this file', 'error', 1.2)

    # --- Script ---------------------------------------------------------------
    def open_scratch_pad(self):
        if bridge.open_scratch_pad():       # opens and shows it itself
            self.done()

    def open_rename(self):
        path = bridge.active_path()
        if not path:
            bridge.hud('No open script', 'error')
            return
        if self.rename_sheet is not None:
            return
        self.rename_sheet = RenameSheet(os.path.basename(path), self.rename_to, self.close_rename)
        self.rename_sheet.frame = (0, 0, self.width, self.height)
        self.add_subview(self.rename_sheet)
        self.rename_sheet.focus()

    def rename_to(self, typed):
        if bridge.rename_active_script(typed):
            self.close_rename()
            self.done(reveal=True)
        # On a problem the HUD says why and the sheet stays open to fix it.

    def close_rename(self):
        sheet, self.rename_sheet = self.rename_sheet, None
        if sheet is not None:
            sheet.field.end_editing()
            self.remove_subview(sheet)

    def duplicate_script(self):
        copy_path = bridge.duplicate_active_script()
        if copy_path:
            bridge.open_script(copy_path)
            self.done()

    def open_constants(self):
        self.deck.select_page(CONSTANTS_PAGE)

    # --- Clipboard ------------------------------------------------------------
    def replace_with_clipboard(self):
        if bridge.replace_active_text(clipboard.get() or ''):
            bridge.hud('Script replaced')
            self.done(reveal=True)

    def append_clipboard(self):
        if not bridge.active_path():
            bridge.hud('No open script', 'error')
            return
        if bridge.append_to_active_text(clipboard.get() or ''):
            bridge.hud('Clipboard appended')
            self.done(reveal=True)

    # --- Danger ---------------------------------------------------------------
    def clear_script(self):
        if bridge.replace_active_text(''):
            bridge.hud('Script cleared')
            self.done(reveal=True)

    def delete_script(self):
        if bridge.delete_active_script():   # closes the tab and shows the editor itself
            self.done()