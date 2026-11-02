"""TabStrip: a row of chips, one per open editor tab, under the deck's header.

The selected tab's chip is highlighted; tap a chip to switch to that tab.
The shell calls show(paths, selected) on its clock; chips are rebuilt only
when the open tabs or the selection actually change.
"""
import os

import ui

from .style import COLOURS, FONT

CHIP_GAP = 6
CHIP_MIN_WIDTH = 60
CHIP_MAX_WIDTH = 180
CHIP_POINTS_PER_CHARACTER = 7.5   # Menlo 12 is fixed-width


class TabStrip(ui.View):

    def __init__(self, on_select):
        self.on_select = on_select
        self.shown = None
        self.chips = []
        self.scroll = ui.ScrollView()
        self.scroll.shows_horizontal_indicator = False
        self.add_subview(self.scroll)

    def show(self, paths, selected):
        key = (tuple(paths), selected)
        if key == self.shown:
            return
        self.shown = key
        for chip in self.chips:
            self.scroll.remove_subview(chip)
        self.chips = [self.make_chip(path, path == selected) for path in paths]
        for chip in self.chips:
            self.scroll.add_subview(chip)
        self.place_chips()

    def make_chip(self, path, is_selected):
        chip = ui.Button()
        chip.title = os.path.basename(path)
        chip.name = path                    # which tab this chip opens
        chip.font = (FONT, 12)
        chip.tint_color = COLOURS['accent'] if is_selected else COLOURS['text']
        chip.background_color = COLOURS['card']
        chip.corner_radius = 8
        chip.border_width = 1
        chip.border_color = COLOURS['accent'] if is_selected else COLOURS['border']
        chip.action = self.chip_tapped
        return chip                         # frame is set in place_chips(), after the title

    def place_chips(self):
        x = 0
        for chip in self.chips:
            width = len(chip.title) * CHIP_POINTS_PER_CHARACTER + 20
            width = min(max(width, CHIP_MIN_WIDTH), CHIP_MAX_WIDTH)
            chip.frame = (x, 0, width, self.height)
            x += width + CHIP_GAP
        self.scroll.content_size = (max(x - CHIP_GAP, 0), self.height)

    def layout(self):
        self.scroll.frame = (0, 0, self.width, self.height)
        self.place_chips()

    def chip_tapped(self, sender):
        self.on_select(sender.name)