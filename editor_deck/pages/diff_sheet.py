"""DiffSheet: what Replace from clipboard would change, before it changes anything.

Covers the Quick page like RenameSheet: a header with the line counts, the
diff in a WebView styled like Find, and Cancel and Replace. Replace is the
second tap of the two-tap Replace; QuickPage applies it and closes the
sheet. The sheet only shows; it never touches the editor itself.
"""
import json

import ui

from .. import find_html
from ..style import BOLD, COLOURS, FONT

HEADER_HEIGHT = 46
BUTTON_HEIGHT = 40
GAP = 8


class DiffSheet(ui.View):

    def __init__(self, diff_html, summary, on_confirm, on_cancel):
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel
        self.background_color = COLOURS['panel']
        self.scripts = []          # JavaScript waiting for the page to load
        self.web_ready = False

        self.title_label = ui.Label()
        self.title_label.text = 'Replace with clipboard?'
        self.title_label.font = (BOLD, 15)
        self.title_label.text_color = COLOURS['accent']
        self.add_subview(self.title_label)

        self.summary_label = ui.Label()
        self.summary_label.text = summary
        self.summary_label.font = (FONT, 12)
        self.summary_label.text_color = COLOURS['muted']
        self.add_subview(self.summary_label)

        self.web = ui.WebView()
        self.web.background_color = COLOURS.get('panel', COLOURS['card'])
        self.web.scales_page_to_fit = False
        self.web.delegate = self
        self.add_subview(self.web)

        self.cancel_button = self.make_button('Cancel', COLOURS['text'], self.cancel_tapped)
        self.replace_button = self.make_button('Replace', COLOURS['warn'], self.replace_tapped)

        self.web.load_html(find_html.page_html(COLOURS))
        self.run_script('showResults(%s, -1)' % json.dumps(diff_html))

    def make_button(self, title, colour, action):
        button = ui.Button()
        button.title = title
        button.font = (BOLD, 15)
        button.tint_color = colour
        button.background_color = COLOURS['button']
        button.corner_radius = 8
        button.action = action
        self.add_subview(button)
        return button     # frame is set in layout(), after the title

    def layout(self):
        width, height = self.width, self.height
        self.title_label.frame = (0, 0, width, 24)
        self.summary_label.frame = (0, 24, width, 18)
        buttons_top = height - BUTTON_HEIGHT
        self.web.frame = (0, HEADER_HEIGHT, width, max(buttons_top - GAP - HEADER_HEIGHT, 40))
        half = (width - GAP) / 2
        self.cancel_button.frame = (0, buttons_top, half, BUTTON_HEIGHT)
        self.replace_button.frame = (half + GAP, buttons_top, half, BUTTON_HEIGHT)

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
                self.web.eval_js(script)
            except Exception:
                pass

    def webview_did_finish_load(self, webview):
        self.web_ready = True
        self.push_scripts()

    def webview_should_start_load(self, webview, url, nav_type):
        return not url.startswith(find_html.LINK_SCHEME)

    # --- Actions ----------------------------------------------------------------
    def replace_tapped(self, sender):
        self.on_confirm()

    def cancel_tapped(self, sender):
        self.on_cancel()