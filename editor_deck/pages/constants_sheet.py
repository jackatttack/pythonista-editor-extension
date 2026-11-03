"""ConstantsSheet: the Constants tuner as a sheet over the deck's pages.

Constants is a tool you reach for, not a tab: Quick's Constants tile opens
this sheet, Done (or switching tab) closes it. It holds an unchanged
ConstantsPage. The shell owns the sheet and ticks it like a page, and the
sheet always passes ticks on, so a slider moved just before Done is still
written: a hidden ConstantsPage flushes its settled values at once.
"""
import ui

from .. import keyboard
from ..style import BOLD, COLOURS
from .constants import ConstantsPage

HEADER_HEIGHT = 34
GAP = 6

HELP_DONE = ('Done', 'Closes the Constants tuner and goes back to the page you were on. '
             'Values you changed are already written to the script.')


class ConstantsSheet(ui.View):

    def __init__(self, deck):
        self.deck = deck
        self.background_color = COLOURS['panel']

        self.title_label = ui.Label()
        self.title_label.text = 'Constants'
        self.title_label.font = (BOLD, 15)
        self.title_label.text_color = COLOURS['accent']
        self.add_subview(self.title_label)

        self.done_button = ui.Button()
        self.done_button.title = 'Done'
        self.done_button.font = (BOLD, 14)
        self.done_button.tint_color = COLOURS['text']
        self.done_button.background_color = COLOURS['button']
        self.done_button.corner_radius = 8
        self.done_button.border_width = 1
        self.done_button.border_color = COLOURS['border']
        self.done_button.action = self.done_tapped
        self.add_subview(self.done_button)

        self.page = ConstantsPage(deck)
        self.add_subview(self.page)
        self.hidden = True
        self.page.hidden = True

    def layout(self):
        width = self.width
        self.title_label.frame = (0, 0, width - 84, HEADER_HEIGHT)
        self.done_button.frame = (width - 76, 0, 76, HEADER_HEIGHT - 4)
        top = HEADER_HEIGHT + GAP
        self.page.frame = (0, top, width, max(self.height - top, 40))

    def open(self):
        keyboard.dismiss()
        self.hidden = False
        self.page.hidden = False
        self.bring_to_front()

    def close(self):
        if self.hidden:
            return
        keyboard.dismiss()
        self.page.hidden = True   # its next tick flushes any settled slider at once
        self.hidden = True

    # --- Called by the shell, like a page ---------------------------------------
    def tick(self, now):
        self.page.tick(now)

    def set_help_mode(self, on):
        self.done_button.border_color = COLOURS['accent'] if on else COLOURS['border']
        self.page.set_help_mode(on)

    def done_tapped(self, sender):
        if self.deck.help_mode:
            self.deck.show_help(*HELP_DONE)
            return
        self.close()