"""Find page: find and replace in the open script.

Type in Find and every match is listed below with its line number,
updating as you type and when the script changes. Next steps through the
matches and Replace swaps the outlined one, both without leaving the deck.
Replace All swaps every match and shows you the editor; tapping a row
jumps to that match in the editor.

The searching is pure (find_model.py); this page shows it and talks to
the editor through editor_bridge.
"""
import clipboard
import ui

from .. import editor_bridge as bridge
from .. import find_model, keyboard
from ..style import BOLD, COLOURS, FONT

FIELD_HEIGHT = 36
BUTTON_HEIGHT = 36
CHIP_HEIGHT = 30
ROW_HEIGHT = 34
ROW_GAP = 2
GAP = 8
REFRESH_SECONDS = 1.0     # how often matches are re-checked against the script
MAX_LIST_ROWS = 200
SNIPPET_LEAD = 18         # characters of the line shown before a match

HELP = {
    'find_paste': ('📋  Paste into Find', "Fills the Find box with the clipboard's text."),
    'replace_paste': ('📋  Paste into Replace',
                      "Fills the Replace box with the clipboard's text."),
    'case': ('Aa  Match case', 'When on, capitals must match: "Name" will not find "name". '
             'Off by default.'),
    'word': ('Word  Whole word', 'When on, only whole words match: "cat" will not find the '
             '"cat" inside "concatenate". Off by default.'),
    'next': ('Next ▸', 'Selects the next match in the script and outlines it in the list, '
             'without leaving the deck. Wraps round to the first match at the end.'),
    'replace': ('Replace', 'Replaces the outlined match (or the first one) with the Replace '
                'text and shows you the change in the editor. Back in the deck, the next '
                'match is outlined, ready for the next Replace.'),
    'replace_all': ('Replace All', 'Replaces every match in the script at once, then shows '
                    'you the editor. The Replace text is used exactly as typed.'),
    'row': ('Matches', 'Each row is one match: its line number and the line around it. '
            'Tap a row to select that match in the editor and show it.'),
}


class MatchRow(ui.View):
    """One match in the list: line number and a snippet of its line."""

    def __init__(self, index, match, on_tap):
        self.index = index
        self.on_tap = on_tap
        self.background_color = COLOURS['card']
        self.corner_radius = 6
        self.border_color = COLOURS['accent']
        self.border_width = 0

        self.line_label = ui.Label()
        self.line_label.text = str(match.line_number)
        self.line_label.font = (FONT, 11)
        self.line_label.text_color = COLOURS['muted']
        self.line_label.alignment = ui.ALIGN_RIGHT
        self.add_subview(self.line_label)

        self.text_label = ui.Label()
        self.text_label.text = match.line_text[max(0, match.column - SNIPPET_LEAD):].strip()
        self.text_label.font = (FONT, 12)
        self.text_label.text_color = COLOURS['text']
        self.add_subview(self.text_label)

    def layout(self):
        self.line_label.frame = (0, 0, 40, self.height)
        self.text_label.frame = (50, 0, self.width - 56, self.height)

    def set_current(self, on):
        self.border_width = 1 if on else 0

    def touch_began(self, touch):
        keyboard.dismiss()

    def touch_ended(self, touch):
        x, y = touch.location
        if 0 <= x <= self.width and 0 <= y <= self.height:
            self.on_tap(self.index)


class FindPage(ui.View):

    def __init__(self, deck):
        self.deck = deck
        self.match_case = False
        self.whole_word = False
        self.matches = []
        self.current = -1
        self.rows = []
        self.buttons = []          # every button, for the help-mode look
        self.dirty = True          # matches need recomputing on the next tick
        self.last_key = None
        self.next_refresh = 0.0

        self.find_field = self.make_field('Find')
        self.replace_field = self.make_field('Replace with')
        self.find_paste = self.make_button('📋', 'find_paste', self.paste_into_find)
        self.replace_paste = self.make_button('📋', 'replace_paste', self.paste_into_replace)
        self.case_chip = self.make_button('Aa', 'case', self.toggle_case)
        self.word_chip = self.make_button('Word', 'word', self.toggle_word)

        self.count_label = ui.Label()
        self.count_label.font = (FONT, 12)
        self.count_label.text_color = COLOURS['muted']
        self.count_label.alignment = ui.ALIGN_RIGHT
        self.add_subview(self.count_label)

        self.next_button = self.make_button('Next ▸', 'next', self.next_match)
        self.replace_button = self.make_button('Replace', 'replace', self.replace_current)
        self.replace_all_button = self.make_button('Replace All', 'replace_all', self.replace_all)

        self.list_scroll = ui.ScrollView()
        self.list_scroll.shows_vertical_indicator = True
        self.list_delegate = keyboard.DismissOnDrag()
        self.list_scroll.delegate = self.list_delegate
        self.add_subview(self.list_scroll)
        self.show_toggle_states()

    # --- Building -------------------------------------------------------------
    def make_field(self, placeholder):
        field = ui.TextField()
        field.placeholder = placeholder
        field.font = (FONT, 14)
        field.text_color = COLOURS['text']
        field.background_color = COLOURS['card']
        field.bordered = False
        field.corner_radius = 8
        field.autocapitalization_type = ui.AUTOCAPITALIZE_NONE
        field.autocorrection_type = False
        field.spellchecking_type = False
        field.clear_button_mode = 'while_editing'
        field.delegate = self
        self.add_subview(field)
        return field

    def make_button(self, title, help_key, action):
        button = ui.Button()
        button.title = title
        button.font = (BOLD, 13)
        button.tint_color = COLOURS['text']
        button.background_color = COLOURS['button']
        button.corner_radius = 8
        button.border_width = 1
        button.border_color = COLOURS['border']
        button.action = lambda sender: self.press(help_key, action)
        self.add_subview(button)
        self.buttons.append(button)
        return button             # frame is set in layout(), after the title

    def layout(self):
        width = self.width
        field_width = width - FIELD_HEIGHT - GAP
        self.find_field.frame = (0, 0, field_width, FIELD_HEIGHT)
        self.find_paste.frame = (width - FIELD_HEIGHT, 0, FIELD_HEIGHT, FIELD_HEIGHT)
        y = FIELD_HEIGHT + GAP
        self.replace_field.frame = (0, y, field_width, FIELD_HEIGHT)
        self.replace_paste.frame = (width - FIELD_HEIGHT, y, FIELD_HEIGHT, FIELD_HEIGHT)

        y += FIELD_HEIGHT + GAP
        self.case_chip.frame = (0, y, 52, CHIP_HEIGHT)
        self.word_chip.frame = (60, y, 64, CHIP_HEIGHT)
        self.count_label.frame = (132, y, width - 132, CHIP_HEIGHT)

        y += CHIP_HEIGHT + GAP
        button_width = (width - 2 * GAP) / 3
        for column, button in enumerate((self.next_button, self.replace_button,
                                         self.replace_all_button)):
            button.frame = (column * (button_width + GAP), y, button_width, BUTTON_HEIGHT)

        y += BUTTON_HEIGHT + GAP
        self.list_scroll.frame = (0, y, width, max(self.height - y, 40))
        self.place_rows()

    # --- Help mode ------------------------------------------------------------
    def touch_began(self, touch):
        keyboard.dismiss()      # a tap on the page between controls

    def press(self, help_key, action):
        keyboard.dismiss()
        if self.deck.help_mode:
            title, text = HELP[help_key]
            self.deck.show_help(title, text)
            return
        action()

    def set_help_mode(self, on):
        for button in self.buttons:
            button.border_color = COLOURS['accent'] if on else COLOURS['border']
        if not on:
            self.show_toggle_states()

    def show_toggle_states(self):
        for chip, on in ((self.case_chip, self.match_case), (self.word_chip, self.whole_word)):
            chip.tint_color = COLOURS['accent'] if on else COLOURS['muted']
            chip.border_color = COLOURS['accent'] if on else COLOURS['border']

    # --- Keeping the matches current ------------------------------------------
    def textfield_did_change(self, textfield):
        self.dirty = True

    def textfield_should_return(self, textfield):
        textfield.end_editing()
        return True

    def tick(self, now):
        if self.hidden:
            return
        if not self.dirty and now < self.next_refresh:
            return
        self.next_refresh = now + REFRESH_SECONDS
        self.dirty = False
        text = bridge.active_text()
        key = (text, self.find_field.text or '', self.match_case, self.whole_word)
        if key != self.last_key:
            self.last_key = key
            self.show_matches(text)

    def show_matches(self, text):
        query = self.find_field.text or ''
        self.matches = find_model.find_matches(text, query, self.match_case, self.whole_word)
        total = len(self.matches)
        if total >= find_model.MAX_MATCHES:
            total = find_model.count_matches(text, query, self.match_case, self.whole_word)
        if self.current >= len(self.matches):
            self.current = len(self.matches) - 1
        if not query:
            self.count_label.text = ''
        elif total == 0:
            self.count_label.text = 'No matches'
        else:
            self.count_label.text = '%d match%s' % (total, '' if total == 1 else 'es')
        self.build_rows()

    def build_rows(self):
        for row in self.rows:
            self.list_scroll.remove_subview(row)
        self.rows = [MatchRow(index, match, self.row_tapped)
                     for index, match in enumerate(self.matches[:MAX_LIST_ROWS])]
        for row in self.rows:
            self.list_scroll.add_subview(row)
        self.place_rows()
        self.outline_current()

    def place_rows(self):
        width = self.list_scroll.width
        y = 0
        for row in self.rows:
            row.frame = (0, y, width, ROW_HEIGHT)
            y += ROW_HEIGHT + ROW_GAP
        self.list_scroll.content_size = (width, y)

    def outline_current(self):
        for row in self.rows:
            row.set_current(row.index == self.current)
        if 0 <= self.current < len(self.rows):
            self.scroll_to_row(self.rows[self.current])

    def scroll_to_row(self, row):
        """Scroll the list just far enough to show row.
        (Pythonista's ScrollView has no scroll_rect_to_visible.)"""
        scroll = self.list_scroll
        top = scroll.content_offset[1]
        if row.y < top:
            top = row.y
        elif row.y + row.height > top + scroll.height:
            top = row.y + row.height - scroll.height
        else:
            return
        lowest = max(scroll.content_size[1] - scroll.height, 0)
        scroll.content_offset = (0, min(max(top, 0), lowest))

    def refresh_now(self):
        """Recompute from the script straight away (after an edit)."""
        self.last_key = None
        self.dirty = True
        self.tick(self.next_refresh)

    # --- Actions --------------------------------------------------------------
    def paste_into_find(self):
        self.find_field.text = clipboard.get() or ''
        self.dirty = True

    def paste_into_replace(self):
        self.replace_field.text = clipboard.get() or ''

    def toggle_case(self):
        self.match_case = not self.match_case
        self.show_toggle_states()
        self.dirty = True

    def toggle_word(self):
        self.whole_word = not self.whole_word
        self.show_toggle_states()
        self.dirty = True

    def row_tapped(self, index):
        if self.deck.help_mode:
            self.deck.show_help(*HELP['row'])
            return
        self.current = index
        self.outline_current()
        match = self.matches[index]
        bridge.select_range(match.start, match.end, reveal=True)

    def next_match(self):
        if not self.matches:
            bridge.hud('No matches', 'error')
            return
        self.current = (self.current + 1) % len(self.matches)
        self.outline_current()
        match = self.matches[self.current]
        bridge.select_range(match.start, match.end)

    def replace_current(self):
        if not self.matches:
            bridge.hud('No matches', 'error')
            return
        index = self.current if 0 <= self.current < len(self.matches) else 0
        match = self.matches[index]
        query = self.find_field.text or ''
        text = bridge.active_text()
        still_there = any(found.start == match.start and found.end == match.end
                          for found in find_model.find_matches(text, query, self.match_case,
                                                               self.whole_word))
        if not still_there:
            self.refresh_now()
            bridge.hud('Script changed; try again', 'error', 1.2)
            return
        replacement = self.replace_field.text or ''
        if not bridge.replace_range(match.start, match.end, replacement):
            return
        self.refresh_now()
        if self.matches:
            # Outline the next match after the inserted text, ready for the next
            # Replace (so replacing "a" with "aa" moves on instead of looping).
            self.current = find_model.index_at_or_after(self.matches,
                                                        match.start + len(replacement))
            self.outline_current()
        # Show what just changed: the inserted text, selected in the editor.
        bridge.select_range(match.start, match.start + len(replacement), reveal=True)
        bridge.hud('Replaced 1')

    def replace_all(self):
        query = self.find_field.text or ''
        if not query:
            bridge.hud('Type something to find', 'error')
            return
        text = bridge.active_text()
        new_text, count = find_model.replace_all(text, query, self.replace_field.text or '',
                                                 self.match_case, self.whole_word)
        if not count:
            bridge.hud('No matches', 'error')
            return
        if bridge.replace_active_text(new_text):
            self.current = -1
            self.refresh_now()
            bridge.hud('Replaced %d' % count)
            bridge.bring_editor_forward()