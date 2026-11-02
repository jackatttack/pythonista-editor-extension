"""RenameSheet: a small sheet over the Quick page for renaming the script.

A text field prefilled with the current name, plus Cancel and Rename.
Return also renames. The sheet only collects the name; QuickPage does the
rename and decides whether the sheet closes (it stays open on a problem).
"""
import ui

from ..style import BOLD, COLOURS, FONT

FIELD_HEIGHT = 40
BUTTON_HEIGHT = 40


class RenameSheet(ui.View):

    def __init__(self, current_name, on_rename, on_cancel):
        self.on_rename = on_rename
        self.on_cancel = on_cancel
        self.background_color = COLOURS['panel']

        self.title_label = ui.Label()
        self.title_label.text = 'Rename script'
        self.title_label.font = (BOLD, 15)
        self.title_label.text_color = COLOURS['accent']
        self.add_subview(self.title_label)

        self.field = ui.TextField()
        self.field.text = current_name
        self.field.font = (FONT, 15)
        self.field.text_color = COLOURS['text']
        self.field.background_color = COLOURS['card']
        self.field.bordered = False
        self.field.corner_radius = 8
        self.field.autocapitalization_type = ui.AUTOCAPITALIZE_NONE
        self.field.autocorrection_type = False
        self.field.spellchecking_type = False
        self.field.clear_button_mode = 'while_editing'
        self.field.delegate = self
        self.add_subview(self.field)

        self.cancel_button = self.make_button('Cancel', COLOURS['text'], self.cancel_tapped)
        self.rename_button = self.make_button('Rename', COLOURS['accent'], self.rename_tapped)

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
        width = self.width
        self.title_label.frame = (0, 0, width, 24)
        self.field.frame = (0, 32, width, FIELD_HEIGHT)
        half = (width - 8) / 2
        top = 32 + FIELD_HEIGHT + 12
        self.cancel_button.frame = (0, top, half, BUTTON_HEIGHT)
        self.rename_button.frame = (half + 8, top, half, BUTTON_HEIGHT)

    def focus(self):
        self.field.begin_editing()

    # --- Actions --------------------------------------------------------------
    def rename_tapped(self, sender):
        self.on_rename(self.field.text)

    def cancel_tapped(self, sender):
        self.on_cancel()

    def textfield_should_return(self, textfield):
        self.on_rename(textfield.text)
        return False