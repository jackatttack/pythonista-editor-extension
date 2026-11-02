"""HelpCard: an explanation of one tool, laid over the page body.

Shown by the shell while help mode is on; tap anywhere on it to close.
"""
import ui

from .style import BOLD, COLOURS, FONT

PADDING = 16


class HelpCard(ui.View):

    def __init__(self, title, text, on_close):
        self.on_close = on_close
        self.background_color = COLOURS['panel']
        self.corner_radius = 12
        self.border_width = 1
        self.border_color = COLOURS['accent']

        self.title_label = self.make_label(title, BOLD, 15, COLOURS['accent'])
        self.text_label = self.make_label(text, FONT, 13, COLOURS['text'])
        self.text_label.number_of_lines = 0
        self.hint_label = self.make_label('Tap to close', FONT, 11, COLOURS['muted'])

    def make_label(self, text, font_name, size, colour):
        label = ui.Label()
        label.text = text
        label.font = (font_name, size)
        label.text_color = colour
        self.add_subview(label)
        return label

    def layout(self):
        width = self.width - 2 * PADDING
        self.title_label.frame = (PADDING, 14, width, 22)
        # Fit the text's height at full width, keeping it top-aligned.
        self.text_label.frame = (PADDING, 46, width, 0)
        self.text_label.size_to_fit()
        room = self.height - 46 - 36
        self.text_label.frame = (PADDING, 46, width, min(self.text_label.height, room))
        self.hint_label.frame = (PADDING, self.height - 28, width, 18)

    def touch_ended(self, touch):
        self.on_close()