"""Snippets page: saved title-and-value pairs, one tap from the clipboard.

From Clipboard opens the new-snippet sheet with the clipboard's text in
it; New opens it empty. Tapping a snippet copies its value and slides the
console away, so you are back in the open script ready to paste. Each
row's ✕ deletes it after a second tap.

Storage is snippets_store.py (data/snippets.json beside the editor_deck
package). If that file cannot be read, the page says so and will not
save over it.
"""
import time

import clipboard
import ui

from .. import editor_bridge as bridge
from .. import keyboard, snippets_store
from ..style import BOLD, COLOURS, FONT

BUTTON_HEIGHT = 36
ROW_HEIGHT = 52
ROW_GAP = 6
GAP = 8
DELETE_WIDTH = 64
CONFIRM_SECONDS = 3.0

HELP = {
    'from_clipboard': ('📋  From Clipboard', "Starts a new snippet holding the clipboard's "
                       'text, with its first line as the title. Rename it if you like, then '
                       'Save.'),
    'new': ('＋  New', 'Starts an empty snippet: give it a title and type the value, then Save.'),
    'row': ('Snippets', 'Tap a snippet to copy its value to the clipboard; the console slides '
            'away so you land in the open script, ready to paste.'),
    'delete': ('✕  Delete', 'Deletes that snippet. Needs a second tap within 3 seconds.'),
}


def make_button(title, action, tint=None):
    button = ui.Button()
    button.title = title
    button.font = (BOLD, 13)
    button.tint_color = tint or COLOURS['text']
    button.background_color = COLOURS['button']
    button.corner_radius = 8
    button.border_width = 1
    button.border_color = COLOURS['border']
    button.action = action
    return button              # frame is set in layout(), after the title


class SnippetRow(ui.View):
    """One snippet: its title, the first line of its value, and a ✕."""

    def __init__(self, page, index, snippet):
        self.page = page
        self.index = index
        self.armed_until = None
        self.background_color = COLOURS['card']
        self.corner_radius = 10
        self.border_width = 1
        self.border_color = COLOURS['border']

        self.title_label = ui.Label()
        self.title_label.text = snippet['title']
        self.title_label.font = (BOLD, 13)
        self.title_label.text_color = COLOURS['text']
        self.add_subview(self.title_label)

        self.preview_label = ui.Label()
        self.preview_label.text = snippets_store.first_line(snippet['value'])
        self.preview_label.font = (FONT, 11)
        self.preview_label.text_color = COLOURS['muted']
        self.add_subview(self.preview_label)

        self.delete_button = make_button('✕', self.delete_tapped)
        self.delete_button.border_width = 0
        self.add_subview(self.delete_button)

    def layout(self):
        text_width = self.width - DELETE_WIDTH - 18
        self.title_label.frame = (12, 6, text_width, 22)
        self.preview_label.frame = (12, 28, text_width, 18)
        self.delete_button.frame = (self.width - DELETE_WIDTH - 6, 8, DELETE_WIDTH,
                                    self.height - 16)

    def set_help_mode(self, on):
        self.border_color = COLOURS['accent'] if on else COLOURS['border']

    def touch_began(self, touch):
        keyboard.dismiss()

    def touch_ended(self, touch):
        x, y = touch.location
        if 0 <= x <= self.width and 0 <= y <= self.height:
            self.page.row_tapped(self.index)

    # --- Two-tap delete -------------------------------------------------------
    def delete_tapped(self, sender):
        keyboard.dismiss()
        if self.page.deck.help_mode:
            return self.page.explain('delete')
        now = time.time()
        if self.armed_until is not None and now <= self.armed_until:
            self.page.delete(self.index)
        else:
            self.armed_until = now + CONFIRM_SECONDS
            self.delete_button.title = 'Delete?'
            self.delete_button.tint_color = COLOURS['danger']

    def tick(self, now):
        if self.armed_until is not None and now > self.armed_until:
            self.armed_until = None
            self.delete_button.title = '✕'
            self.delete_button.tint_color = COLOURS['text']


class SnippetSheet(ui.View):
    """New-snippet sheet over the page: a title field, a value box, Cancel and Save."""

    def __init__(self, title, value, on_save, on_cancel):
        self.on_save = on_save
        self.on_cancel = on_cancel
        self.background_color = COLOURS['panel']

        self.heading = ui.Label()
        self.heading.text = 'New snippet'
        self.heading.font = (BOLD, 15)
        self.heading.text_color = COLOURS['accent']
        self.add_subview(self.heading)

        self.title_field = ui.TextField()
        self.title_field.text = title
        self.title_field.placeholder = 'Title'
        self.style_input(self.title_field)
        self.title_field.bordered = False
        self.add_subview(self.title_field)

        self.value_box = ui.TextView()
        self.value_box.text = value
        self.style_input(self.value_box)
        self.add_subview(self.value_box)

        self.cancel_button = make_button('Cancel', self.cancel_tapped)
        self.save_button = make_button('Save', self.save_tapped, COLOURS['accent'])
        self.add_subview(self.cancel_button)
        self.add_subview(self.save_button)

    def style_input(self, view):
        view.font = (FONT, 13)
        view.text_color = COLOURS['text']
        view.background_color = COLOURS['card']
        view.corner_radius = 8
        view.autocorrection_type = False
        view.spellchecking_type = False
        view.autocapitalization_type = ui.AUTOCAPITALIZE_NONE

    def layout(self):
        # Buttons share the top row with the heading, so the keyboard
        # (which rises from the bottom) can never cover them.
        width, height = self.width, self.height
        button_width = 76
        self.save_button.frame = (width - button_width, 0, button_width, BUTTON_HEIGHT)
        self.cancel_button.frame = (width - 2 * button_width - GAP, 0, button_width, BUTTON_HEIGHT)
        self.heading.frame = (0, 0, width - 2 * button_width - 2 * GAP, BUTTON_HEIGHT)
        field_top = BUTTON_HEIGHT + GAP
        self.title_field.frame = (0, field_top, width, 36)
        box_top = field_top + 36 + GAP
        self.value_box.frame = (0, box_top, width, max(height - box_top, 60))

    def touch_began(self, touch):
        keyboard.dismiss()

    def save_tapped(self, sender):
        self.on_save(self.title_field.text or '', self.value_box.text or '')

    def cancel_tapped(self, sender):
        self.on_cancel()


class SnippetsPage(ui.View):

    def __init__(self, deck):
        self.deck = deck
        self.store_path = snippets_store.default_store_path()
        self.snippets, self.problem = snippets_store.load(self.store_path)
        self.rows = []
        self.sheet = None

        self.clipboard_button = make_button('📋 From Clipboard', self.from_clipboard_tapped)
        self.new_button = make_button('＋ New', self.new_tapped)
        self.add_subview(self.clipboard_button)
        self.add_subview(self.new_button)

        self.scroll = ui.ScrollView()
        self.scroll.shows_vertical_indicator = True
        self.scroll_delegate = keyboard.DismissOnDrag()
        self.scroll.delegate = self.scroll_delegate
        self.add_subview(self.scroll)

        self.message_label = ui.Label()
        self.message_label.font = (FONT, 13)
        self.message_label.text_color = COLOURS['muted']
        self.message_label.alignment = ui.ALIGN_CENTER
        self.message_label.number_of_lines = 0
        self.add_subview(self.message_label)
        self.build_rows()

    # --- Layout ---------------------------------------------------------------
    def layout(self):
        width, height = self.width, self.height
        half = (width - GAP) / 2
        self.clipboard_button.frame = (0, 0, half, BUTTON_HEIGHT)
        self.new_button.frame = (half + GAP, 0, half, BUTTON_HEIGHT)
        top = BUTTON_HEIGHT + GAP
        self.scroll.frame = (0, top, width, max(height - top, 40))
        self.message_label.frame = (10, top + 20, width - 20, 100)
        self.place_rows()
        if self.sheet is not None:
            self.sheet.frame = (0, 0, width, height)

    def build_rows(self):
        for row in self.rows:
            self.scroll.remove_subview(row)
        self.rows = [SnippetRow(self, index, snippet) for index, snippet in enumerate(self.snippets)]
        for row in self.rows:
            row.set_help_mode(self.deck.help_mode)
            self.scroll.add_subview(row)
        if self.problem:
            self.message_label.text = self.problem + ' Snippets will not be saved until it is fixed.'
        elif not self.snippets:
            self.message_label.text = 'No snippets yet. Save one from the clipboard or make a new one.'
        else:
            self.message_label.text = ''
        self.message_label.hidden = not self.message_label.text
        self.place_rows()

    def place_rows(self):
        width = self.scroll.width
        y = 0
        for row in self.rows:
            row.frame = (0, y, width, ROW_HEIGHT)
            y += ROW_HEIGHT + ROW_GAP
        self.scroll.content_size = (width, y)

    def tick(self, now):
        for row in self.rows:
            row.tick(now)

    # --- Help mode ------------------------------------------------------------
    def explain(self, key):
        self.deck.show_help(*HELP[key])

    def set_help_mode(self, on):
        for row in self.rows:
            row.set_help_mode(on)
        for button in (self.clipboard_button, self.new_button):
            button.border_color = COLOURS['accent'] if on else COLOURS['border']

    def touch_began(self, touch):
        keyboard.dismiss()

    # --- Actions --------------------------------------------------------------
    def row_tapped(self, index):
        if self.deck.help_mode:
            return self.explain('row')
        snippet = self.snippets[index]
        bridge.copy_text(snippet['value'], 'Copied “%s”' % snippet['title'])
        bridge.bring_editor_forward()

    def from_clipboard_tapped(self, sender):
        keyboard.dismiss()
        if self.deck.help_mode:
            return self.explain('from_clipboard')
        value = clipboard.get() or ''
        if not value.strip():
            return bridge.hud('The clipboard is empty', 'error')
        self.open_sheet(snippets_store.suggest_title(value), value)

    def new_tapped(self, sender):
        keyboard.dismiss()
        if self.deck.help_mode:
            return self.explain('new')
        self.open_sheet('', '')

    def open_sheet(self, title, value):
        if self.sheet is not None:
            return
        self.sheet = SnippetSheet(title, value, self.save_new, self.close_sheet)
        self.sheet.frame = (0, 0, self.width, self.height)
        self.add_subview(self.sheet)
        if not value:
            self.sheet.title_field.begin_editing()

    def close_sheet(self):
        sheet, self.sheet = self.sheet, None
        if sheet is not None:
            keyboard.dismiss()
            self.remove_subview(sheet)

    def save_new(self, title, value):
        if not value.strip():
            return bridge.hud('A snippet needs a value', 'error')
        if self.store(snippets_store.add(self.snippets, title, value)):
            self.close_sheet()
            bridge.hud('Snippet saved')

    def delete(self, index):
        if self.store(snippets_store.remove(self.snippets, index)):
            bridge.hud('Snippet deleted')

    def store(self, snippets):
        """Save snippets and show them. Refuses while the file could not be read."""
        if self.problem:
            bridge.hud('Snippets file unreadable; not saved', 'error', 1.4)
            return False
        try:
            snippets_store.save(self.store_path, snippets)
        except Exception as error:
            bridge.hud('Could not save: %s' % error, 'error', 1.4)
            return False
        self.snippets = snippets
        self.build_rows()
        return True