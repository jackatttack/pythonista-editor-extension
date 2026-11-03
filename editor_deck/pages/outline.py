"""Outline page: the open script's classes and functions, to skim and open.

Collapsed, it is one row per definition (its def or class line and line
number), nested as in the code, with top-level code between them folded
into rows of its own. Tap a row to open its code in place; ↗ jumps to the
definition in the editor. Expand all shows the whole script.

The outline is pure (outline_model.py) and drawn with Find's viewer
(find_html.py) in a WebView, so opening and closing happen inside the page
with no Python. The page remembers what is open across refreshes and
forgets it when the open file changes.
"""
import json

import ui

from .. import dock
from .. import editor_bridge as bridge
from .. import find_html, find_model, keyboard, outline_model
from ..style import BOLD, COLOURS, FONT

BUTTON_HEIGHT = 32
GAP = 8
REFRESH_SECONDS = 1.0     # how often the outline is re-checked against the script
FONT_SIZES = (7, 8, 9, 10, 11, 12, 13, 14, 16, 18)   # code text sizes A− and A+ step through
DEFAULT_FONT_INDEX = 5    # 12, the size Find uses

HELP = {
    'expand': ('Expand all', 'Opens every class, function and stretch of top-level code, '
               'so the whole script shows, coloured, with line numbers.'),
    'collapse': ('Collapse all', 'Folds everything back to one row per definition, for '
                 'skimming.'),
    'smaller': ('A−  Smaller text', 'Makes the outline and its code smaller, so more fits '
                'without scrolling sideways. Remembered while the deck stays docked.'),
    'bigger': ('A+  Bigger text', 'Makes the outline and its code bigger and easier to '
               'read. Remembered while the deck stays docked.'),
    'outline': ('Outline', 'Each row is a class, function or method (or a stretch of '
                'top-level code), nested as in the script. Tap a row to open its code '
                'in place; tap ↗ to jump to it in the editor.'),
}


class OutlinePage(ui.View):

    def __init__(self, deck):
        self.deck = deck
        self.buttons = []
        self.text = ''
        self.shown_key = None      # (path, text) last drawn
        self.shown_path = None
        self.next_refresh = 0.0
        self.scripts = []          # JavaScript waiting for the page to load
        self.web_ready = False

        self.expand_button = self.make_button('Expand', 'expand',
                                              lambda: self.run_script('setAllOpen(true)'))
        self.collapse_button = self.make_button('Collapse', 'collapse',
                                                lambda: self.run_script('setAllOpen(false)'))
        self.smaller_button = self.make_button('A−', 'smaller', lambda: self.change_font(-1))
        self.bigger_button = self.make_button('A+', 'bigger', lambda: self.change_font(1))
        self.font_index = dock.saved_state().get('outline_font', DEFAULT_FONT_INDEX)

        self.count_label = ui.Label()
        self.count_label.font = (FONT, 12)
        self.count_label.text_color = COLOURS['muted']
        self.count_label.alignment = ui.ALIGN_RIGHT
        self.add_subview(self.count_label)

        self.results = ui.WebView()
        self.results.background_color = COLOURS.get('panel', COLOURS['card'])
        self.results.scales_page_to_fit = False
        self.results.delegate = self
        self.add_subview(self.results)
        self.results.load_html(find_html.page_html(COLOURS, outline_model.outline_css(COLOURS),
                                                   outline_model.OUTLINE_SCRIPT))
        self.apply_font()

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
        x = 0
        for button, button_width in ((self.expand_button, 76), (self.collapse_button, 86),
                                     (self.smaller_button, 40), (self.bigger_button, 40)):
            button.frame = (x, 0, button_width, BUTTON_HEIGHT)
            x += button_width + 6
        self.count_label.frame = (x, 0, max(width - x, 0), BUTTON_HEIGHT)
        top = BUTTON_HEIGHT + GAP
        self.results.frame = (0, top, width, max(self.height - top, 40))

    # --- Help mode ------------------------------------------------------------
    def touch_began(self, touch):
        keyboard.dismiss()

    def press(self, help_key, action):
        keyboard.dismiss()
        if self.deck.help_mode:
            self.deck.show_help(*HELP[help_key])
            return
        action()

    def set_help_mode(self, on):
        for button in self.buttons:
            button.border_color = COLOURS['accent'] if on else COLOURS['border']

    # --- Text size ----------------------------------------------------------------
    def change_font(self, step):
        self.font_index = min(max(self.font_index + step, 0), len(FONT_SIZES) - 1)
        dock.saved_state()['outline_font'] = self.font_index
        self.apply_font()

    def apply_font(self):
        self.run_script('setFontSize(%d)' % FONT_SIZES[self.font_index])

    # --- Keeping in step with the script ----------------------------------------
    def tick(self, now):
        if self.hidden or now < self.next_refresh:
            return
        self.next_refresh = now + REFRESH_SECONDS
        key = (bridge.active_path(), bridge.active_text())
        if key != self.shown_key:
            self.shown_key = key
            self.show_outline(*key)

    def show_outline(self, path, text):
        self.text = text
        if path != self.shown_path:
            self.shown_path = path
            self.run_script('forgetOpen()')
        if not text.strip():
            self.count_label.text = ''
            body = find_html.message_html('The script is empty.')
        else:
            nodes, exact = outline_model.outline(text)
            count = outline_model.count_nodes(nodes)
            self.count_label.text = '%d def%s' % (count, '' if count == 1 else 's')
            body = outline_model.outline_html(text, nodes, exact)
        self.run_script('showOutline(%s)' % json.dumps(body))

    def jump_to_line(self, line):
        keyboard.dismiss()
        if self.deck.help_mode:
            self.deck.show_help(*HELP['outline'])
            return
        starts = find_model.line_start_offsets(self.text)
        if not 1 <= line <= len(starts):
            return
        start = starts[line - 1]
        end = self.text.find('\n', start)
        bridge.select_range(start, len(self.text) if end < 0 else end, reveal=True)

    # --- The page ---------------------------------------------------------------
    def run_script(self, script):
        """Run JavaScript on the page, queued until it has loaded."""
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
        """↗ arrives as a link; take it here instead of loading it."""
        if url.startswith(outline_model.LINE_LINK):
            try:
                self.jump_to_line(int(url[len(outline_model.LINE_LINK):]))
            except ValueError:
                pass
            return False
        return not url.startswith(find_html.LINK_SCHEME)