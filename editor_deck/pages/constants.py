"""Constants page: tune the open script's top-level settings.

Every top-level UPPER_CASE name set to a plain value gets a control for
its kind: a switch for True/False, a slider and field for numbers, a
swatch and colour panel for '#RRGGBB' colours, and a field for text and
other literals. Each change is written into the script straight away, so
it sits in the editor's undo history and the next run uses it. A
'# range: 16-128' comment after a number sets its slider range.

Ported from Action Deck's Tune Constants; the finding and formatting is
pure (constants_model.py). The page reloads by itself when you switch
scripts or edit by hand, but never while you are typing in one of its
fields or the colour panel is open.
"""
import ast
import colorsys
import os
import time

import ui

from .. import constants_model as model
from .. import editor_bridge as bridge
from .. import keyboard
from ..style import BOLD, COLOURS, FONT

TITLE_HEIGHT = 30
SECTION_HEIGHT = 24
ROW_HEIGHT = 48
NUMBER_ROW_HEIGHT = 84
ROW_GAP = 6
PAD = 10
VALUE_FIELD_WIDTH = 96
SWATCH_WIDTH = 48
HEX_LABEL_WIDTH = 92
COLOUR_PANEL_HEIGHT = 236
REFRESH_SECONDS = 1.0
SLIDER_SETTLE_SECONDS = 0.35   # a dragged slider writes once it has been still this long

HELP = {
    'bool': ('Switch', 'Flips a True/False constant and writes it into the script '
             'straight away.'),
    'number': ('Number', 'Drag the slider: the number follows as you drag and is written '
               'into the script once you stop. Or type a value and press Return. The '
               'slider spans 0 to twice the value, or the range in a "# range: 16-128" '
               'comment after it; typing outside the range widens it. Items of a list '
               "or dict, like EXAMPLE[0] or SETTINGS['speed'], work the same way."),
    'colour': ('Colour', 'Tap the swatch to open hue, saturation and brightness sliders. '
               'Apply writes the new hex code into the script; Cancel leaves it as it was.'),
    'text': ('Text', 'Edit the value and press Return (or tap away) to write it. Lists, '
             'tuples and dicts are edited as Python source and must still parse.'),
    'reload': ('↻  Reload', 'Reads the script again. The page also reloads by itself when '
               'you switch scripts or edit by hand, except while you are typing here.'),
}


def make_value_field(text, monospaced, delegate):
    field = ui.TextField()
    field.text = text
    field.font = (FONT if monospaced else BOLD, 13)
    field.text_color = COLOURS['text']
    field.background_color = COLOURS['button']
    field.bordered = False
    field.corner_radius = 8
    field.autocorrection_type = False
    field.spellchecking_type = False
    field.autocapitalization_type = ui.AUTOCAPITALIZE_NONE
    field.delegate = delegate
    return field


# --- Rows ---------------------------------------------------------------------
class ConstantRow(ui.View):
    """One constant: its name, plus a control chosen by its kind (subclasses).

    write() is the single path to the script. It keeps self.constant in
    step with what the file now says, so the row can show it. In help mode
    the controls stop taking touches and a tap explains the row instead.
    """

    help_key = 'text'
    row_height = ROW_HEIGHT

    def __init__(self, page, constant):
        self.page = page
        self.constant = constant
        self.controls = []
        self.background_color = COLOURS['card']
        self.corner_radius = 10
        self.border_width = 1
        self.border_color = COLOURS['border']

        self.name_label = ui.Label()
        self.name_label.text = constant.name
        self.name_label.font = (BOLD, 12)
        self.name_label.text_color = COLOURS['text']
        self.add_subview(self.name_label)

    def add_control(self, control):
        self.add_subview(control)
        self.controls.append(control)

    def write(self, new_value):
        """Write new_value to the open script; return the text written, or None."""
        written = bridge.write_constant(self.constant.name, new_value)
        if written is not None:
            self.constant.source_text = written
            self.constant.value = ast.literal_eval(written)
            self.page.note_own_write()
        return written

    def set_help_mode(self, on):
        for control in self.controls:
            control.touch_enabled = not on
        self.border_color = COLOURS['accent'] if on else COLOURS['border']

    def touch_began(self, touch):
        keyboard.dismiss()

    def touch_ended(self, touch):
        if self.page.deck.help_mode:
            self.page.explain(self.help_key)

    # --- Text field delegate (number and text rows) ---------------------------
    def textfield_did_begin_editing(self, textfield):
        self.page.editing = True

    def textfield_did_end_editing(self, textfield):
        self.page.editing = False
        self.typed(textfield)

    def textfield_should_return(self, textfield):
        textfield.end_editing()
        return True

    def typed(self, field):
        pass


class SwitchRow(ConstantRow):
    help_key = 'bool'

    def __init__(self, page, constant):
        super().__init__(page, constant)
        self.switch = ui.Switch()
        self.switch.value = constant.value
        self.switch.action = self.switched
        self.add_control(self.switch)

    def layout(self):
        self.name_label.frame = (PAD, 0, self.width - 3 * PAD - 51, self.height)
        self.switch.frame = (self.width - PAD - 51, (self.height - 31) / 2, 51, 31)

    def switched(self, sender):
        if self.write(bool(sender.value)) is None:
            sender.value = self.constant.value


class NumberRow(ConstantRow):
    """int and float constants: a typed field plus a slider.

    The field follows the slider live as it is dragged; the value is
    written into the script once the slider has been still for
    SLIDER_SETTLE_SECONDS (flush, from the page's tick), so a drag makes
    one edit, not dozens. A typed value outside the range widens it.
    """

    help_key = 'number'
    row_height = NUMBER_ROW_HEIGHT

    def __init__(self, page, constant):
        super().__init__(page, constant)
        self.is_whole = constant.kind == 'int'
        self.low, self.high = constant.slider_range

        self.field = make_value_field(constant.source_text, True, self)
        self.field.keyboard_type = ui.KEYBOARD_NUMBERS
        self.add_control(self.field)

        self.pending_value = None      # dragged to, not yet written
        self.pending_since = 0.0
        self.slider = ui.Slider()
        self.slider.continuous = True
        self.slider.tint_color = COLOURS['accent']
        self.slider.action = self.slid
        self.add_control(self.slider)
        self.place_slider(constant.value)

    def layout(self):
        self.name_label.frame = (PAD, 6, self.width - 3 * PAD - VALUE_FIELD_WIDTH, 34)
        self.field.frame = (self.width - PAD - VALUE_FIELD_WIDTH, 6, VALUE_FIELD_WIDTH, 34)
        self.slider.frame = (PAD, 44, self.width - 2 * PAD, 34)

    def place_slider(self, value):
        span = self.high - self.low
        fraction = 0.0 if span == 0 else (value - self.low) / float(span)
        self.slider.value = max(0.0, min(1.0, fraction))

    def slid(self, sender):
        value = self.low + sender.value * (self.high - self.low)
        if self.is_whole:
            value = int(round(value))
        try:
            self.field.text = model.format_constant_value(self.constant, value)
        except ValueError:
            self.field.text = str(value)
        self.pending_value = value
        self.pending_since = time.time()

    def flush(self, now, force=False):
        """Write a dragged value once the slider has settled (or at once with force)."""
        if self.pending_value is None:
            return
        if not force and now - self.pending_since < SLIDER_SETTLE_SECONDS:
            return
        value, self.pending_value = self.pending_value, None
        written = self.write(value)
        self.field.text = written if written is not None else self.constant.source_text

    def typed(self, field):
        text = (field.text or '').strip()
        if text == self.constant.source_text:
            return
        try:
            value = float(text)
        except ValueError:
            bridge.hud('%s needs a number' % self.constant.name, 'error', 1.2)
            field.text = self.constant.source_text
            return
        if self.is_whole:
            value = int(round(value))
        self.low = min(self.low, value)
        self.high = max(self.high, value)
        written = self.write(value)
        field.text = written if written is not None else self.constant.source_text
        self.place_slider(self.constant.value)


class ColourRow(ConstantRow):
    """Hex colour constants: hex code and swatch; tap opens the colour panel."""

    help_key = 'colour'

    def __init__(self, page, constant):
        super().__init__(page, constant)
        self.hex_label = ui.Label()
        self.hex_label.font = (FONT, 12)
        self.hex_label.text_color = COLOURS['muted']
        self.hex_label.alignment = ui.ALIGN_RIGHT
        self.add_subview(self.hex_label)

        self.swatch = ui.Button()
        self.swatch.corner_radius = 8
        self.swatch.border_width = 1
        self.swatch.border_color = COLOURS['border']
        self.swatch.action = self.tapped
        self.add_control(self.swatch)
        self.show_colour()

    def layout(self):
        reserved = HEX_LABEL_WIDTH + SWATCH_WIDTH + 2 * PAD
        self.name_label.frame = (PAD, 0, self.width - PAD - reserved, self.height)
        self.hex_label.frame = (self.width - reserved, 0, HEX_LABEL_WIDTH, self.height)
        self.swatch.frame = (self.width - PAD - SWATCH_WIDTH, 8, SWATCH_WIDTH, self.height - 16)

    def show_colour(self):
        self.swatch.background_color = model.hex_to_rgba(self.constant.value)
        self.hex_label.text = self.constant.value

    def tapped(self, sender):
        keyboard.dismiss()
        self.page.colour_panel.open_for(self)


class TextRow(ConstantRow):
    """Strings, and any other literal (tuples, lists, dicts) as raw source."""

    help_key = 'text'

    def __init__(self, page, constant):
        super().__init__(page, constant)
        self.is_plain_text = constant.kind == 'text'
        self.field = make_value_field(self.shown_text(), not self.is_plain_text, self)
        self.add_control(self.field)

    def layout(self):
        field_width = max(VALUE_FIELD_WIDTH, self.width * 0.55)
        self.name_label.frame = (PAD, 0, self.width - 3 * PAD - field_width, self.height)
        self.field.frame = (self.width - PAD - field_width, 7, field_width, self.height - 14)

    def shown_text(self):
        return self.constant.value if self.is_plain_text else self.constant.source_text

    def typed(self, field):
        if field.text == self.shown_text():
            return
        if self.is_plain_text:
            new_value = field.text
        else:
            try:
                new_value = ast.literal_eval(field.text)
            except (ValueError, SyntaxError):
                bridge.hud('%s is not a valid value' % self.constant.name, 'error', 1.2)
                field.text = self.shown_text()
                return
        self.write(new_value)
        field.text = self.shown_text()


ROW_CLASSES = {
    'bool': SwitchRow,
    'int': NumberRow,
    'float': NumberRow,
    'colour': ColourRow,
    'text': TextRow,
    'literal': TextRow,
}


# --- Colour panel ---------------------------------------------------------------
class ColourPanel(ui.View):
    """Hue, saturation and brightness sliders for one colour at a time.

    Made once with the page and shown or hidden. Dragging only moves the
    preview; Apply writes to the script, Cancel discards. Any alpha in an
    '#RRGGBBAA' colour is kept as it was.
    """

    SLIDER_NAMES = ('Hue', 'Saturation', 'Brightness')

    def __init__(self, page):
        self.page = page
        self.row = None
        self.colour_alpha = 1.0
        self.include_alpha = False
        self.background_color = COLOURS['help']
        self.corner_radius = 12
        self.border_width = 1
        self.border_color = COLOURS['accent']
        self.hidden = True

        self.preview = ui.View()
        self.preview.corner_radius = 8
        self.preview.border_width = 1
        self.preview.border_color = COLOURS['border']
        self.add_subview(self.preview)

        self.title_label = self.make_label(BOLD, 13, COLOURS['text'])
        self.hex_label = self.make_label(FONT, 12, COLOURS['muted'])

        self.slider_labels = []
        self.sliders = []
        for slider_name in self.SLIDER_NAMES:
            label = self.make_label(FONT, 11, COLOURS['muted'])
            label.text = slider_name
            slider = ui.Slider()
            slider.continuous = True
            slider.tint_color = COLOURS['accent']
            slider.action = self.slid
            self.add_subview(slider)
            self.slider_labels.append(label)
            self.sliders.append(slider)

        self.cancel_button = self.make_button('Cancel', COLOURS['text'], self.cancel)
        self.apply_button = self.make_button('Apply', COLOURS['accent'], self.apply)

    def make_label(self, font_name, size, colour):
        label = ui.Label()
        label.font = (font_name, size)
        label.text_color = colour
        self.add_subview(label)
        return label

    def make_button(self, title, tint, action):
        button = ui.Button()
        button.title = title
        button.font = (BOLD, 14)
        button.tint_color = tint
        button.background_color = COLOURS['button']
        button.corner_radius = 8
        button.action = action
        self.add_subview(button)
        return button

    def layout(self):
        width = self.width
        self.preview.frame = (PAD, PAD, 44, 44)
        text_left = 2 * PAD + 44
        self.title_label.frame = (text_left, PAD, width - text_left - PAD, 22)
        self.hex_label.frame = (text_left, PAD + 22, width - text_left - PAD, 22)
        y = 2 * PAD + 44
        for label, slider in zip(self.slider_labels, self.sliders):
            label.frame = (PAD, y, 80, 32)
            slider.frame = (PAD + 80, y, width - 2 * PAD - 80, 32)
            y += 36
        button_width = (width - 3 * PAD) / 2.0
        button_top = self.height - PAD - 36
        self.cancel_button.frame = (PAD, button_top, button_width, 36)
        self.apply_button.frame = (2 * PAD + button_width, button_top, button_width, 36)

    def open_for(self, row):
        self.row = row
        hex_colour = row.constant.value
        red, green, blue, self.colour_alpha = model.hex_to_rgba(hex_colour)
        self.include_alpha = len(hex_colour) == 9
        for slider, amount in zip(self.sliders, colorsys.rgb_to_hsv(red, green, blue)):
            slider.value = amount
        self.title_label.text = row.constant.name
        self.show_preview()
        self.hidden = False
        self.bring_to_front()

    def current_hex(self):
        hue, saturation, brightness = [slider.value for slider in self.sliders]
        red, green, blue = colorsys.hsv_to_rgb(hue, saturation, brightness)
        return model.rgba_to_hex(red, green, blue, self.colour_alpha, self.include_alpha)

    def show_preview(self):
        hex_colour = self.current_hex()
        self.preview.background_color = model.hex_to_rgba(hex_colour)
        self.hex_label.text = hex_colour

    def slid(self, sender):
        self.show_preview()

    def apply(self, sender):
        if self.row is not None and self.row.write(self.current_hex()) is not None:
            self.row.show_colour()
        self.hidden = True

    def cancel(self, sender):
        self.hidden = True


# --- The page -----------------------------------------------------------------
class ConstantsPage(ui.View):

    def __init__(self, deck):
        self.deck = deck
        self.items = []            # section labels and rows, in display order
        self.rows = []
        self.editing = False       # a row's field has the keyboard
        self.shown_key = None      # (path, text) the rows were built from
        self.next_refresh = 0.0

        self.title_label = ui.Label()
        self.title_label.font = (BOLD, 12)
        self.title_label.text_color = COLOURS['muted']
        self.add_subview(self.title_label)

        self.reload_button = ui.Button()
        self.reload_button.title = '↻'
        self.reload_button.font = (BOLD, 16)
        self.reload_button.tint_color = COLOURS['text']
        self.reload_button.background_color = COLOURS['button']
        self.reload_button.corner_radius = 8
        self.reload_button.border_width = 1
        self.reload_button.border_color = COLOURS['border']
        self.reload_button.action = self.reload_tapped
        self.add_subview(self.reload_button)

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
        self.message_label.hidden = True
        self.add_subview(self.message_label)

        self.colour_panel = ColourPanel(self)
        self.add_subview(self.colour_panel)

    def layout(self):
        width, height = self.width, self.height
        self.title_label.frame = (0, 0, width - 44, TITLE_HEIGHT)
        self.reload_button.frame = (width - 36, 0, 36, TITLE_HEIGHT)
        top = TITLE_HEIGHT + 6
        self.scroll.frame = (0, top, width, max(height - top, 40))
        self.message_label.frame = (PAD, top + 20, width - 2 * PAD, 120)
        self.colour_panel.frame = (0, height - COLOUR_PANEL_HEIGHT, width, COLOUR_PANEL_HEIGHT)
        self.place_items()

    def place_items(self):
        width = self.scroll.width
        y = 0
        for item in self.items:
            if isinstance(item, ConstantRow):
                item.frame = (0, y, width, item.row_height)
                y += item.row_height + ROW_GAP
            else:
                item.frame = (2, y, width, SECTION_HEIGHT)
                y += SECTION_HEIGHT
        # Room at the end so the last rows can scroll clear of the colour panel.
        self.scroll.content_size = (width, y + COLOUR_PANEL_HEIGHT)

    # --- Keeping in step with the script --------------------------------------
    def tick(self, now):
        # Settled slider drags are written first, even when the page has just
        # been hidden, so a quick page switch never loses a value.
        for row in self.rows:
            flush = getattr(row, 'flush', None)
            if flush is not None:
                flush(now, force=self.hidden)
        if self.hidden or now < self.next_refresh:
            return
        self.next_refresh = now + REFRESH_SECONDS
        if self.editing or not self.colour_panel.hidden:
            return
        if any(getattr(row, 'pending_value', None) is not None for row in self.rows):
            return
        key = (bridge.active_path(), bridge.active_text())
        if key != self.shown_key:
            self.load(*key)

    def note_own_write(self):
        """A row just wrote: the script changed, but the rows already show it."""
        self.shown_key = (bridge.active_path(), bridge.active_text())

    def load(self, path, text):
        self.shown_key = (path, text)
        offset = self.scroll.content_offset
        for item in self.items:
            self.scroll.remove_subview(item)
        self.items = []
        self.rows = []
        self.message_label.hidden = True
        self.title_label.text = os.path.basename(path) if path else 'No file open'

        if not path:
            return self.show_message('Open a script to tune its constants.')
        try:
            constants = model.find_editable_constants(text)
        except SyntaxError as error:
            return self.show_message("The script doesn't parse (line %s), so its constants "
                                     "can't be edited safely." % error.lineno)
        if not constants:
            return self.show_message('No editable constants. Top-level UPPER_CASE names '
                                     'set to plain values appear here.')

        self.title_label.text = '%s · %d constant%s' % (
            os.path.basename(path), len(constants), '' if len(constants) == 1 else 's')
        current_section = None
        for constant in constants:
            if constant.section != current_section:
                current_section = constant.section
                label = ui.Label()
                label.text = (current_section or 'Top of file').upper()
                label.font = (BOLD, 11)
                label.text_color = COLOURS['muted']
                self.items.append(label)
            row = ROW_CLASSES[constant.kind](self, constant)
            row.set_help_mode(self.deck.help_mode)
            self.items.append(row)
            self.rows.append(row)
        for item in self.items:
            self.scroll.add_subview(item)
        self.place_items()
        lowest = max(self.scroll.content_size[1] - self.scroll.height, 0)
        self.scroll.content_offset = (0, min(offset[1], lowest))

    def show_message(self, text):
        self.message_label.text = text
        self.message_label.hidden = False

    # --- Buttons and help -----------------------------------------------------
    def reload_tapped(self, sender):
        keyboard.dismiss()
        if self.deck.help_mode:
            return self.explain('reload')
        self.load(bridge.active_path(), bridge.active_text())

    def explain(self, key):
        self.deck.show_help(*HELP[key])

    def set_help_mode(self, on):
        for row in self.rows:
            row.set_help_mode(on)
        self.reload_button.border_color = COLOURS['accent'] if on else COLOURS['border']
        if on:
            self.colour_panel.hidden = True

    def touch_began(self, touch):
        keyboard.dismiss()