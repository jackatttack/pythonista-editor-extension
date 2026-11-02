"""Tool tiles: the Quick page's buttons, laid out two to a row.

A tile shows an icon and a short title; tap runs its tool. In help mode
(the ? button) tiles change look and a tap explains the tool instead,
through on_help; nothing runs.

A tool made with confirm=True needs a second tap within CONFIRM_SECONDS,
for tools that destroy work. The deck runs on the main thread, so a
blocking console.alert is not an option. The page's tick(now), called
from the deck's clock, disarms tiles and clears stuck highlights.
"""
import time

import ui

from .. import keyboard
from ..style import BOLD, COLOURS

TILE_HEIGHT = 56
TILE_GAP = 8
TILE_RADIUS = 10
CONFIRM_SECONDS = 3.0
PRESS_TIMEOUT_SECONDS = 1.0   # safety net: a highlight never outlives this
CONFIRM_TITLE = 'Tap again'


class Tool:
    """What a tile does: icon, short title, the full explanation shown in
    help mode, the action to run, an optional tint and whether to confirm."""

    def __init__(self, icon, title, description, action, tint=None, confirm=False):
        self.icon = icon
        self.title = title
        self.description = description
        self.action = action
        self.tint = tint
        self.confirm = confirm


class ToolTile(ui.View):

    def __init__(self, tool, on_help):
        self.tool = tool
        self.on_help = on_help
        self.tint = tool.tint or COLOURS['text']
        self.help_mode = False
        self.armed_until = None
        self.pressed_at = None

        self.background_color = COLOURS['card']
        self.corner_radius = TILE_RADIUS
        self.border_width = 1
        self.border_color = COLOURS['border']

        self.icon_label = ui.Label()
        self.icon_label.text = tool.icon
        self.icon_label.font = ('<system>', 20)
        self.icon_label.alignment = ui.ALIGN_CENTER
        self.add_subview(self.icon_label)

        self.title_label = ui.Label()
        self.title_label.text = tool.title
        self.title_label.font = (BOLD, 13)
        self.title_label.text_color = self.tint
        self.title_label.number_of_lines = 2
        self.add_subview(self.title_label)

        self.help_badge = ui.Label()
        self.help_badge.text = '?'
        self.help_badge.font = (BOLD, 12)
        self.help_badge.text_color = COLOURS['accent']
        self.help_badge.alignment = ui.ALIGN_CENTER
        self.help_badge.hidden = True
        self.add_subview(self.help_badge)

        self.press = ui.View()
        self.press.background_color = COLOURS['accent']
        self.press.corner_radius = TILE_RADIUS
        self.press.alpha = 0.0
        self.press.touch_enabled = False
        self.add_subview(self.press)

    def layout(self):
        self.icon_label.frame = (6, 0, 34, self.height)
        self.title_label.frame = (42, 0, self.width - 60, self.height)
        self.help_badge.frame = (self.width - 18, 4, 14, 14)
        self.press.frame = (0, 0, self.width, self.height)

    # --- Help mode ------------------------------------------------------------
    def set_help_mode(self, on):
        self.help_mode = on
        if self.armed_until is not None:
            self.disarm()
        self.help_badge.hidden = not on
        self.background_color = COLOURS['help'] if on else COLOURS['card']
        self.border_color = self.resting_border()

    def resting_border(self):
        return COLOURS['accent'] if self.help_mode else COLOURS['border']

    # --- Touches --------------------------------------------------------------
    def touch_began(self, touch):
        keyboard.dismiss()
        self.pressed_at = time.time()
        self.press.alpha = 0.15

    def touch_cancelled(self, touch):
        self.release_press()

    def release_press(self):
        """Forget the touch and clear the highlight. Also called when the
        page scrolls, which does not always cancel the touch here."""
        self.pressed_at = None
        self.press.alpha = 0.0

    def touch_ended(self, touch):
        self.release_press()
        x, y = touch.location
        if not (0 <= x <= self.width and 0 <= y <= self.height):
            return      # finger slid off the tile: nothing runs
        if self.help_mode:
            self.on_help(self.tool)
            return
        if not self.tool.confirm:
            self.tool.action()
            return
        now = time.time()
        if self.armed_until is not None and now <= self.armed_until:
            self.disarm()
            self.tool.action()
        else:
            self.arm(now)

    # --- Two-tap confirm ------------------------------------------------------
    def arm(self, now):
        self.armed_until = now + CONFIRM_SECONDS
        self.title_label.text = CONFIRM_TITLE
        self.title_label.text_color = COLOURS['danger']
        self.border_color = COLOURS['danger']

    def disarm(self):
        self.armed_until = None
        self.title_label.text = self.tool.title
        self.title_label.text_color = self.tint
        self.border_color = self.resting_border()

    def tick(self, now):
        if self.armed_until is not None and now > self.armed_until:
            self.disarm()
        if self.pressed_at is not None and now - self.pressed_at > PRESS_TIMEOUT_SECONDS:
            self.release_press()