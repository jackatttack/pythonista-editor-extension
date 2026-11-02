"""Finding Pythonista's console and keeping one Editor Deck docked in it.

Pythonista only. Call these on the main thread (shell.show_deck does).

Why builtins: docked views outlive the script, but Pythonista clears the
script's globals when it ends, so the live deck is parked on builtins
and replaced by name on the next run. The view tag is a second safety
net: any view carrying it is removed before a new deck docks.
"""
import builtins

from objc_util import ObjCClass

KEEP_ALIVE_NAME = '_consolekit_editor_deck'
STATE_NAME = '_consolekit_editor_deck_state'
DECK_VIEW_TAG = 0x4445434B   # 'DECK' in ASCII; marks the panel and the square


# --- Finding the console ----------------------------------------------------
def class_name(view):
    name = view._get_objc_classname()
    return name.decode() if isinstance(name, bytes) else str(name)


def search_views(view, inside_editor):
    name = class_name(view)
    if name == 'OMTextEditorView':
        inside_editor = True
    elif name == 'OMTextView' and not inside_editor:
        return view
    for subview in view.subviews():
        found = search_views(subview, inside_editor)
        if found is not None:
            return found
    return None


def find_console_text_view():
    """The console is the first OMTextView with no OMTextEditorView above it."""
    app = ObjCClass('UIApplication').sharedApplication()
    for window in app.windows():
        found = search_views(window, inside_editor=False)
        if found is not None:
            return found
    return None


# --- One deck at a time -----------------------------------------------------
def remove_tagged_views(container):
    """Remove every view a deck left in the console container."""
    for subview in list(container.subviews()):
        if subview.tag() == DECK_VIEW_TAG:
            subview.removeFromSuperview()


def current_deck():
    return getattr(builtins, KEEP_ALIVE_NAME, None)


def keep_alive(deck):
    setattr(builtins, KEEP_ALIVE_NAME, deck)


def release(deck):
    if current_deck() is deck:
        setattr(builtins, KEEP_ALIVE_NAME, None)


def close_previous_deck():
    old_deck = current_deck()
    if old_deck is not None:
        try:
            old_deck.close()
        except Exception:
            pass


# --- Remembered between runs ------------------------------------------------
def saved_state():
    """Page and minimised flag, kept until Pythonista quits."""
    state = getattr(builtins, STATE_NAME, None)
    if state is None:
        state = {'page': 0, 'minimised': False}
        setattr(builtins, STATE_NAME, state)
    return state