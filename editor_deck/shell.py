"""The Editor Deck shell: a paged panel docked in Pythonista's console.

The panel covers the console with a header (title, open file, close), a
row of page tabs and a page body. The minimise button sits in the
panel's bottom-right corner; minimising folds the panel up into a small
square in that same spot, and tapping the square unfolds it again
(fold_flourish.py; a plain fade when boardkit cannot be imported).

Sprint 1: the pages are placeholders. Quick actions, Find & Replace and
Constants arrive one sprint at a time.

Stability rules learned the hard way in Pythonista: views are built on
the main thread, motion is ui.animate on frame and alpha with no
completion or a frame clock set once, and never ui.delay.
"""
import os
import time

import editor
import ui
from objc_util import on_main_thread

from . import dock, editor_bridge, fold_flourish, geometry, keyboard
from .help_card import HelpCard
from .pages.constants_sheet import ConstantsSheet
from .pages.find import FindPage
from .pages.outline import OutlinePage
from .pages.quick import QuickPage
from .pages.snippets import SnippetsPage
from .tab_strip import TabStrip
from .style import BOLD, COLOURS, FONT

# --- Look -------------------------------------------------------------------
# Colours and fonts are shared with the pages: style.py.
SQUARE_ICON = '🛠'
PANEL_RADIUS = 14

# --- Size (points) ----------------------------------------------------------
SIDE_MARGIN = 8
TOP_MARGIN = 8
INPUT_BAR_CLEARANCE = 56     # keep the console's input bar uncovered
CONTENT_PADDING = 12
HEADER_HEIGHT = 44
TAB_STRIP_HEIGHT = 28        # the open-tab chips under the header
TABS_HEIGHT = 32
HEADER_BUTTON_SIZE = 32
SQUARE_SIZE = geometry.SQUARE_SIZE
CORNER_INSET = geometry.CORNER_INSET
SQUARE_RADIUS = 12

# --- Motion and timing (seconds) --------------------------------------------
USE_FOLD_FLOURISH = True     # False: plain fades, even when boardkit is there
FADE_SECONDS = 0.18          # the plain fade
CONTENT_FADE_SECONDS = 0.12  # the panel's content over the settled paper
SQUARE_FADE_SECONDS = 0.12
CLOCK_INTERVAL = 0.25        # set once on the panel, never changed
FILE_CHECK_SECONDS = 1.0     # how often the header re-reads the open file

PAGE_TITLES = ['Quick', 'Find', 'Outline', 'Snippets']


def spaced(text):
    return ' '.join(text)


def style_corner_square(view):
    """The look shared by the minimise button and the minimised square."""
    view.background_color = COLOURS['button']
    view.corner_radius = SQUARE_RADIUS
    view.border_width = 1
    view.border_color = COLOURS['accent']


# --- The minimised square ---------------------------------------------------
class DeckSquare(ui.View):
    """The minimised deck. A tap brings the panel back."""

    def __init__(self, deck):
        self.deck = deck
        style_corner_square(self)
        self.frame = (0, 0, SQUARE_SIZE, SQUARE_SIZE)

        icon = ui.Label()
        icon.text = SQUARE_ICON
        icon.font = ('<system>', 22)
        icon.alignment = ui.ALIGN_CENTER
        icon.touch_enabled = False
        icon.frame = (0, 0, SQUARE_SIZE, SQUARE_SIZE)
        self.add_subview(icon)

    def touch_ended(self, touch):
        self.deck.restore()


# --- Pages ------------------------------------------------------------------
# The pages live in pages/: quick.py, find.py, outline.py and snippets.py.
# Constants opens as a sheet over them (constants_sheet.py), from Quick.


# --- The panel --------------------------------------------------------------
class DeckView(ui.View):
    """The expanded Editor Deck, plus its square and its fold paper."""

    def __init__(self, text_view):
        self.text_view = text_view
        self.square = DeckSquare(self)
        self.paper = self.make_paper()
        self.minimised = False
        self.laid_out_size = None
        self.console_size = None
        self.next_file_check = 0.0
        self.shown_path = 'not checked yet'
        self.console_was_visible = True

        self.background_color = COLOURS['panel']
        self.corner_radius = PANEL_RADIUS
        self.border_width = 1
        self.border_color = COLOURS['border']

        self.title_label = self.make_label(spaced('EDITOR DECK'), BOLD, 13, COLOURS['accent'])
        self.file_label = self.make_label('', FONT, 11, COLOURS['muted'])
        self.close_button = self.make_button('✕', self.close)

        self.minimise_button = self.make_button('▾', self.minimise)
        style_corner_square(self.minimise_button)
        self.minimise_button.font = (BOLD, 20)

        self.help_mode = False
        self.help_card = None
        self.help_button = self.make_button('?', self.toggle_help)
        style_corner_square(self.help_button)
        self.help_button.font = (BOLD, 20)

        self.tab_strip = TabStrip(self.tab_chosen)
        self.add_subview(self.tab_strip)

        self.tabs = ui.SegmentedControl()
        self.tabs.segments = PAGE_TITLES
        self.tabs.tint_color = COLOURS['accent']
        self.tabs.action = self.tab_changed
        self.add_subview(self.tabs)

        self.body = ui.View()
        self.add_subview(self.body)
        self.pages = [QuickPage(self), FindPage(self), OutlinePage(self), SnippetsPage(self)]
        for page in self.pages:
            self.body.add_subview(page)
        # Constants is a tool, not a tab: a sheet over the pages, opened from Quick.
        self.constants_sheet = ConstantsSheet(self)
        self.body.add_subview(self.constants_sheet)

        self.square.alpha = 0.0
        self.square.touch_enabled = False
        self.update_interval = CLOCK_INTERVAL

    def make_paper(self):
        """The fold layer under the panel, or None when folds are off."""
        if not (USE_FOLD_FLOURISH and fold_flourish.available()):
            return None
        paper = fold_flourish.DockedFoldLayer(skippable=True)
        paper.corner_radius = PANEL_RADIUS
        paper.background_color = COLOURS['panel']    # settled under the open panel
        return paper

    def make_label(self, text, font_name, size, colour):
        label = ui.Label()
        label.text = text
        label.font = (font_name, size)
        label.text_color = colour
        self.add_subview(label)
        return label

    def make_button(self, title, action):
        button = ui.Button()
        button.title = title
        button.font = (BOLD, 16)
        button.tint_color = COLOURS['text']
        button.background_color = COLOURS['button']
        button.corner_radius = 8
        button.action = action
        self.add_subview(button)
        return button     # frame is set in layout(), after the title

    def docked_views(self):
        """Bottom to top: the paper, the panel, the square."""
        views = [self, self.square]
        if self.paper is not None:
            views.insert(0, self.paper)
        return views

    # --- Layout ---------------------------------------------------------------
    def layout(self):
        # UIKit calls layout() whenever subviews change, not only on resize.
        size = (round(self.width), round(self.height))
        if size == self.laid_out_size:
            return
        self.laid_out_size = size

        width, height = self.width, self.height
        pad = CONTENT_PADDING
        button = HEADER_BUTTON_SIZE
        self.close_button.frame = (width - pad - button, 8, button, button)

        text_width = max(width - 2 * pad - button - 6, 40)
        self.title_label.frame = (pad, 8, text_width, 18)
        self.file_label.frame = (pad, 26, text_width, 16)

        strip_top = HEADER_HEIGHT + 4
        self.tab_strip.frame = (pad, strip_top, width - 2 * pad, TAB_STRIP_HEIGHT)
        tabs_top = strip_top + TAB_STRIP_HEIGHT + 8
        self.tabs.frame = (pad, tabs_top, width - 2 * pad, TABS_HEIGHT)

        # Bottom strip: the minimise square in the corner, where the
        # minimised square will appear.
        square_x = width - SQUARE_SIZE - CORNER_INSET
        square_y = height - SQUARE_SIZE - CORNER_INSET
        self.minimise_button.frame = (square_x, square_y, SQUARE_SIZE, SQUARE_SIZE)
        self.help_button.frame = (CORNER_INSET, square_y, SQUARE_SIZE, SQUARE_SIZE)

        body_top = tabs_top + TABS_HEIGHT + 10
        body_bottom = square_y - 8
        self.body.frame = (pad, body_top, width - 2 * pad, max(body_bottom - body_top, 40))
        for page in self.page_views():
            page.frame = (0, 0, self.body.width, self.body.height)
        if self.help_card is not None:
            self.help_card.frame = self.body.frame

    def console_frame(self):
        frame = self.text_view.frame()
        return (frame.origin.x, frame.origin.y, frame.size.width, frame.size.height)

    def fit_to_console(self):
        """Size the panel and paper to the console; put the square on the minimise button."""
        panel = geometry.panel_frame(self.console_frame(), SIDE_MARGIN, TOP_MARGIN,
                                     INPUT_BAR_CLEARANCE)
        self.frame = panel
        if self.paper is not None:
            self.paper.frame = panel
        x, y = geometry.corner_square_origin(panel, SQUARE_SIZE, CORNER_INSET)
        self.square.frame = (x, y, SQUARE_SIZE, SQUARE_SIZE)

    # --- Clock ----------------------------------------------------------------
    def update(self):
        if self.objc_instance.superview() is None:
            return
        size = self.text_view.frame().size
        console_size = (round(size.width), round(size.height))
        if console_size != self.console_size:
            self.console_size = console_size     # first tick, rotation, split view
            self.fit_to_console()
        # Coming over from the editor: put its keyboard away.
        console_visible = editor_bridge.console_visible()
        if console_visible and not self.console_was_visible:
            keyboard.dismiss()
        self.console_was_visible = console_visible

        now = time.time()
        if now >= self.next_file_check:
            self.next_file_check = now + FILE_CHECK_SECONDS
            self.show_open_file()
        for page in self.page_views():
            tick = getattr(page, 'tick', None)
            if tick is not None:
                tick(now)

    def show_open_file(self):
        """Refresh the file name and the open-tab chips (on the clock)."""
        try:
            path = editor.get_path()
        except Exception:
            path = None
        if path != self.shown_path:
            self.shown_path = path
            self.file_label.text = os.path.basename(path) if path else 'No file open'
        try:
            paths, selected = editor_bridge.open_tab_paths()
        except Exception:
            paths, selected = [], ''
        self.tab_strip.show(paths, selected or path or '')

    # --- Pages ----------------------------------------------------------------
    def touch_began(self, touch):
        keyboard.dismiss()      # a tap on the deck's own background

    def tab_changed(self, sender):
        keyboard.dismiss()
        self.select_page(sender.selected_index)

    # --- Help mode ------------------------------------------------------------
    def toggle_help(self, sender=None):
        keyboard.dismiss()
        self.set_help_mode(not self.help_mode)

    def set_help_mode(self, on):
        """In help mode every tool explains itself instead of running."""
        self.help_mode = on
        self.help_button.background_color = COLOURS['accent'] if on else COLOURS['button']
        self.help_button.tint_color = COLOURS['panel'] if on else COLOURS['text']
        for page in self.page_views():
            set_mode = getattr(page, 'set_help_mode', None)
            if set_mode is not None:
                set_mode(on)
        if not on:
            self.close_help()

    def show_help(self, title, text):
        self.close_help()
        self.help_card = HelpCard(title, text, self.close_help)
        self.help_card.frame = self.body.frame
        self.add_subview(self.help_card)

    def close_help(self):
        card, self.help_card = self.help_card, None
        if card is not None:
            self.remove_subview(card)

    def tab_chosen(self, path):
        """A chip in the tab strip was tapped: switch the editor to that tab."""
        keyboard.dismiss()
        editor_bridge.select_tab(path)
        self.next_file_check = 0.0      # refresh the strip on the next tick

    def select_page(self, index):
        index = min(max(int(index), 0), len(self.pages) - 1)
        self.close_constants()
        self.tabs.selected_index = index
        for page_index, page in enumerate(self.pages):
            page.hidden = page_index != index
        dock.saved_state()['page'] = index

    def page_views(self):
        """Every view the clock and help mode reach: the tabs' pages, then the
        Constants sheet (once it exists; layout can run before __init__ ends)."""
        sheet = getattr(self, 'constants_sheet', None)
        return self.pages + ([sheet] if sheet is not None else [])

    def open_constants(self):
        """Show the Constants tuner over the pages (Quick's Constants tile)."""
        self.constants_sheet.open()

    def close_constants(self):
        sheet = getattr(self, 'constants_sheet', None)
        if sheet is not None:
            sheet.close()

    # --- Minimise -------------------------------------------------------------
    def minimise(self, sender=None, animated=True):
        if self.minimised:
            return
        keyboard.dismiss()
        self.minimised = True
        self.touch_enabled = False
        dock.saved_state()['minimised'] = True

        if not animated or self.paper is None:
            self.square.touch_enabled = True
            if self.paper is not None:
                self.paper.hidden = True
            self.fade_to(panel_alpha=0.0, square_alpha=1.0, animated=animated)
            return

        # Content fades to blank paper, then the paper folds into the corner.
        ui.animate(lambda: setattr(self, 'alpha', 0.0), CONTENT_FADE_SECONDS)
        self.paper.background_color = fold_flourish.CLEAR   # from now on the show draws the paper
        self.paper.play(fold_flourish.PaperShow(
            self.width, self.height, folding_up=True,
            start=time.time() + CONTENT_FADE_SECONDS, on_finished=self.folded_up))

    def folded_up(self):
        if not self.minimised:
            return
        # A layer that stops drawing keeps showing its last frame, so the
        # paper is hidden once it has folded away, not just left empty.
        self.paper.hidden = True
        self.square.touch_enabled = True
        ui.animate(lambda: setattr(self.square, 'alpha', 1.0), SQUARE_FADE_SECONDS)

    # --- Restore --------------------------------------------------------------
    def restore(self, sender=None):
        if not self.minimised:
            return
        self.minimised = False
        self.square.touch_enabled = False
        dock.saved_state()['minimised'] = False

        if self.paper is None:
            self.touch_enabled = True
            self.fade_to(panel_alpha=1.0, square_alpha=0.0, animated=True)
            return

        # The square fades as paper unfolds out of its corner.
        ui.animate(lambda: setattr(self.square, 'alpha', 0.0), SQUARE_FADE_SECONDS)
        self.paper.background_color = fold_flourish.CLEAR
        self.paper.hidden = False
        self.paper.play(fold_flourish.PaperShow(
            self.width, self.height, folding_up=False,
            start=time.time(), on_finished=self.unfolded))

    def unfolded(self):
        if self.minimised:
            return
        # Hold the settled paper, then fade the content in over it.
        self.paper.background_color = COLOURS['panel']
        self.touch_enabled = True
        ui.animate(lambda: setattr(self, 'alpha', 1.0), CONTENT_FADE_SECONDS)

    def fade_to(self, panel_alpha, square_alpha, animated):
        def apply():
            self.alpha = panel_alpha
            self.square.alpha = square_alpha
        if animated:
            ui.animate(apply, FADE_SECONDS)
        else:
            apply()

    # --- Close ----------------------------------------------------------------
    def close(self, sender=None):
        """Remove the panel, the square and the paper. Never raises."""
        for view in self.docked_views():
            try:
                view.objc_instance.removeFromSuperview()
            except Exception:
                pass
        dock.saved_state()['minimised'] = False
        dock.release(self)


# --- Docking ----------------------------------------------------------------
@on_main_thread
def show_deck():
    """Dock a fresh Editor Deck in the console, replacing any earlier one.

    Returns True when docked, False when the console cannot be found.
    Never raises.
    """
    try:
        text_view = dock.find_console_text_view()
        if text_view is None:
            print('Editor Deck: could not find the console.')
            return False
        dock.close_previous_deck()
        container = text_view.superview()
        dock.remove_tagged_views(container)

        deck = DeckView(text_view)
        deck.fit_to_console()
        for view in deck.docked_views():          # bottom to top
            view.objc_instance.setTag_(dock.DECK_VIEW_TAG)
            container.addSubview_(view.objc_instance)
        dock.keep_alive(deck)

        state = dock.saved_state()
        deck.select_page(state.get('page', 0))
        if state.get('minimised'):
            deck.minimise(animated=False)
        return True
    except Exception as error:
        print('Editor Deck failed to dock: %r' % error)
        return False


@on_main_thread
def close_deck():
    """Remove the docked deck, if there is one. Never raises."""
    deck = dock.current_deck()
    if deck is not None:
        try:
            deck.close()
        except Exception:
            pass