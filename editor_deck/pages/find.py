"""Find page: find and replace in the open script.

Type in Find and every line with a match is shown below in full, indentation
included, syntax coloured, with each match marked. It updates as you type
and when the script changes. The ± chip adds lines of context above and
below each match. Next steps through the matches and Replace swaps the
outlined one, both without leaving the deck. Replace All swaps every match
and shows you the editor; tapping a match jumps to it in the editor.

The searching is pure (find_model.py) and so is the results HTML
(find_html.py). This page shows the results in a WebView, which runs its
JavaScript queued until the page has loaded (the Math deck's pattern), and
talks to the editor through editor_bridge.
"""
import json

import clipboard
import ui

from .. import editor_bridge as bridge
from .. import find_html, find_model, keyboard
from ..style import BOLD, COLOURS, FONT

FIELD_HEIGHT = 36
BUTTON_HEIGHT = 36
CHIP_HEIGHT = 30
GAP = 8
REFRESH_SECONDS = 1.0     # how often matches are re-checked against the script
MAX_SHOWN_MATCHES = 200   # matches drawn in the results; the count still covers them all
CONTEXT_STEPS = (0, 2, 5) # lines shown above and below each match; the ± chip cycles them

HELP = {
    'find_paste': ('📋  Paste into Find', "Fills the Find box with the clipboard's text."),
    'replace_paste': ('📋  Paste into Replace',
                      "Fills the Replace box with the clipboard's text."),
    'case': ('Aa  Match case', 'When on, capitals must match: "Name" will not find "name". '
             'Off by default.'),
    'word': ('Word  Whole word', 'When on, only whole words match: "cat" will not find the '
             '"cat" inside "concatenate". Off by default.'),
    'context': ('±  Context lines', 'How many lines to show above and below each match: '
                '0, 2 or 5. Tap to cycle. Nearby matches share one block.'),
    'next': ('Next ▸', 'Selects the next match in the script and outlines it below, '
             'without leaving the deck. Wraps round to the first match at the end.'),
    'replace': ('Replace', 'Replaces the outlined match (or the first one) with the Replace '
                'text and shows you the change in the editor. Back in the deck, the next '
                'match is outlined, ready for the next Replace.'),
    'replace_all': ('Replace All', 'Replaces every match in the script at once, then shows '
                    'you the editor. The Replace text is used exactly as typed.'),
    'row': ('Matches', 'Each line with a match is shown in full, indentation included, with '
            'every match marked. Tap a mark to select that match in the editor, or '
            'elsewhere on the line for its first match. Long lines scroll sideways.'),
}


class FindPage(ui.View):

    def __init__(self, deck):
        self.deck = deck
        self.match_case = False
        self.whole_word = False
        self.context_step = 0      # index into CONTEXT_STEPS
        self.text = ''             # the script text the matches were found in
        self.matches = []
        self.current = -1
        self.buttons = []          # every button, for the help-mode look
        self.dirty = True          # matches need recomputing on the next tick
        self.last_key = None
        self.next_refresh = 0.0
        self.scripts = []          # JavaScript waiting for the results page to load
        self.web_ready = False

        self.find_field = self.make_field('Find')
        self.replace_field = self.make_field('Replace with')
        self.find_paste = self.make_button('📋', 'find_paste', self.paste_into_find)
        self.replace_paste = self.make_button('📋', 'replace_paste', self.paste_into_replace)
        self.case_chip = self.make_button('Aa', 'case', self.toggle_case)
        self.word_chip = self.make_button('Word', 'word', self.toggle_word)
        self.context_chip = self.make_button(self.context_title(), 'context', self.cycle_context)

        self.count_label = ui.Label()
        self.count_label.font = (FONT, 12)
        self.count_label.text_color = COLOURS['muted']
        self.count_label.alignment = ui.ALIGN_RIGHT
        self.add_subview(self.count_label)

        self.next_button = self.make_button('Next ▸', 'next', self.next_match)
        self.replace_button = self.make_button('Replace', 'replace', self.replace_current)
        self.replace_all_button = self.make_button('Replace All', 'replace_all', self.replace_all)

        self.results = ui.WebView()
        self.results.background_color = COLOURS.get('panel', COLOURS['card'])
        self.results.scales_page_to_fit = False
        self.results.delegate = self
        self.add_subview(self.results)
        self.show_toggle_states()
        self.results.load_html(find_html.page_html(COLOURS))

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
        self.context_chip.frame = (132, y, 48, CHIP_HEIGHT)
        self.count_label.frame = (188, y, width - 188, CHIP_HEIGHT)

        y += CHIP_HEIGHT + GAP
        button_width = (width - 2 * GAP) / 3
        for column, button in enumerate((self.next_button, self.replace_button,
                                         self.replace_all_button)):
            button.frame = (column * (button_width + GAP), y, button_width, BUTTON_HEIGHT)

        y += BUTTON_HEIGHT + GAP
        self.results.frame = (0, y, width, max(self.height - y, 40))

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
        for chip, on in ((self.case_chip, self.match_case),
                         (self.word_chip, self.whole_word),
                         (self.context_chip, CONTEXT_STEPS[self.context_step] > 0)):
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
        self.text = text
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
        self.show_results()

    def show_results(self):
        """Redraw the results page from the current matches."""
        if not (self.find_field.text or ''):
            body = find_html.message_html('Type above to find in the script.')
        elif not self.matches:
            body = find_html.message_html('No matches.')
        else:
            shown = self.matches[:MAX_SHOWN_MATCHES]
            note = ''
            if len(self.matches) > MAX_SHOWN_MATCHES:
                note = 'Showing the first %d matches.' % MAX_SHOWN_MATCHES
            body = find_html.results_html(self.text, shown,
                                          CONTEXT_STEPS[self.context_step], note)
        self.run_script('showResults(%s, %d)' % (json.dumps(body), self.shown_current()))

    def shown_current(self):
        """The outlined match's index on the page, or -1 if it is not drawn."""
        return self.current if 0 <= self.current < MAX_SHOWN_MATCHES else -1

    def outline_current(self):
        self.run_script('setCurrent(%d)' % self.shown_current())

    def refresh_now(self):
        """Recompute from the script straight away (after an edit)."""
        self.last_key = None
        self.dirty = True
        self.tick(self.next_refresh)

    # --- The results page -----------------------------------------------------
    def run_script(self, script):
        """Run JavaScript on the results page, queued until it has loaded."""
        self.scripts.append(script)
        self.push_scripts()

    def push_scripts(self):
        if not self.web_ready:
            return
        scripts, self.scripts = self.scripts, []
        for script in scripts:
            try:
                self.results.eval_js(script)
            except Exception:
                pass

    def webview_did_finish_load(self, webview):
        self.web_ready = True
        self.push_scripts()

    def webview_should_start_load(self, webview, url, nav_type):
        """A tapped match arrives as a link; take it here instead of loading it."""
        if not url.startswith(find_html.LINK_SCHEME):
            return True
        try:
            index = int(url[len(find_html.LINK_SCHEME):])
        except ValueError:
            return False
        if 0 <= index < len(self.matches):     # the page may be a tick behind
            self.row_tapped(index)
        return False

    # --- Actions --------------------------------------------------------------
    def context_title(self):
        return '±%d' % CONTEXT_STEPS[self.context_step]

    def cycle_context(self):
        self.context_step = (self.context_step + 1) % len(CONTEXT_STEPS)
        self.context_chip.title = self.context_title()
        self.layout()             # keep the chip's frame after the title change
        self.show_toggle_states()
        self.show_results()

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
        keyboard.dismiss()
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