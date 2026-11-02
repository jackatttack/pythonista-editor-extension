"""The open script, as the Editor Deck sees it. Pythonista only.

Editor positions count UTF-16 units, not Python characters (see the
pythonista-editor guide). Whole-buffer writes go straight to the active
tab's text view, measured by that view's own length, because
editor.replace_text can never replace the last character. When the tab
cannot be found, writes fall back to editor.replace_text.
"""
import os
from urllib.parse import quote

import clipboard
import console
import editor
from objc_util import NSRange, ObjCClass, on_main_thread, sel

from . import constants_model

DOCUMENTS = os.path.expanduser('~/Documents')


# --- Feedback ---------------------------------------------------------------
def hud(message, style='success', duration=1.0):
    """A short HUD message, with a print fallback."""
    try:
        console.hud_alert(str(message), style, duration)
    except Exception:
        print('[Editor Deck]', message)


def copy_text(text, message='Copied'):
    clipboard.set(text or '')
    hud(message)


# --- Reading the open script ------------------------------------------------
def active_path():
    """The open script's full path, or '' when nothing is open."""
    try:
        return editor.get_path() or ''
    except Exception:
        return ''


def active_text():
    """The open script's text exactly as the editor holds it, saved or not."""
    try:
        return editor.get_text() or ''
    except Exception:
        return ''


def active_relative_path():
    """The open script's path relative to Documents, or '' when outside it."""
    path = active_path()
    if not path:
        return ''
    try:
        relative = os.path.relpath(path, DOCUMENTS)
    except Exception:
        return ''
    if relative == '..' or relative.startswith('..' + os.sep):
        return ''
    return relative.replace(os.sep, '/')


def utf16_length(text):
    return len(text.encode('utf-16-le')) // 2


def utf16_offset(text, index):
    """The editor position of Python character index in text."""
    return utf16_length(text[:index])


def script_url(action):
    """A pythonista3:// URL that runs ('run') or opens ('open') the script, or ''."""
    relative = active_relative_path()
    if action not in ('run', 'open') or not relative:
        return ''
    return 'pythonista3://%s?action=%s' % (quote(relative, safe='/'), action)


# --- Pythonista's own controllers -------------------------------------------
# Found by labs/tab_methods_probe.py and labs/console_controls_probe.py
# (2026-11-02). The root is a sliding container whose "accessory" is the
# console; the detail controller holds the editor tabs.
EDITOR_REVEAL_SECONDS = 0.25


def _pythonista_controllers():
    """(root, detail) controllers, or (None, None) outside Pythonista's editor."""
    app = ObjCClass('UIApplication').sharedApplication()
    for window in app.windows():
        root = window.rootViewController()
        if root is None or not root.respondsToSelector_(sel('detailViewController')):
            continue
        detail = root.detailViewController()
        if detail is not None and detail.respondsToSelector_(sel('tabViewControllers')):
            return root, detail
    return None, None


@on_main_thread
def console_visible():
    """True while the console is on screen (slid in, or docked beside the editor)."""
    root, _ = _pythonista_controllers()
    try:
        return bool(root.accessoryDocked() or root.accessoryVisible())
    except Exception:
        return True


@on_main_thread
def bring_editor_forward():
    """Slide the console away so the editor shows. Leaves a docked console alone."""
    root, _ = _pythonista_controllers()
    try:
        if root is None or not root.respondsToSelector_(sel('hideAccessoryWithAnimationDuration:')):
            return
        if root.accessoryDocked() or not root.accessoryVisible():
            return
        root.hideAccessoryWithAnimationDuration_(EDITOR_REVEAL_SECONDS)
    except Exception as error:
        print('Editor Deck: could not show the editor (%r)' % (error,))


# --- Writing the open script ------------------------------------------------
def _active_text_view():
    """The text view of the tab showing the open script, or None."""
    path = active_path()
    _, detail = _pythonista_controllers()
    if not path or detail is None:
        return None
    wanted = os.path.realpath(path)
    for tab in detail.tabViewControllers():
        if not tab.isViewLoaded():
            continue
        tab_path = tab.filePath()
        if tab_path is not None and os.path.realpath(str(tab_path)) == wanted:
            return tab.editorView().textView()
    return None


# Suspected (2026-11-02): setting a truly empty buffer through the text view
# crashes Pythonista. Action Deck's Clear never emptied it (replace_text
# leaves the last character), so the deck leaves one newline instead.
EMPTY_SCRIPT = '\n'


@on_main_thread
def replace_active_text(text):
    """Replace the whole open script with text. Returns True on success.

    Empty text becomes EMPTY_SCRIPT, so the buffer is never truly empty.
    """
    if not active_path():
        hud('No open script', 'error')
        return False
    text = text or EMPTY_SCRIPT
    try:
        text_view = _active_text_view()
        if text_view is not None:
            whole = ObjCClass('OMTextRange').rangeWithNSRange_(
                NSRange(0, text_view.text().length()))
            text_view.replaceRange_withText_(whole, text or '')
        else:
            # Fallback: misses the final character (pythonista-editor guide).
            editor.replace_text(0, utf16_length(active_text()), text or '')
        return True
    except Exception as error:
        hud('Replace failed: %s' % error, 'error', 1.2)
        return False


def append_to_active_text(addition):
    """Add text to the end of the script with exactly one joining newline."""
    if not addition:
        return True
    current = active_text()
    joiner = '' if not current or current.endswith('\n') else '\n'
    return replace_active_text(current + joiner + addition)


# --- Files ------------------------------------------------------------------
SCRATCH_STEM = 'scratch_pad'


def next_free_path(folder, stem, extension):
    """folder/stem.ext if free, else stem_2.ext, stem_3.ext ..."""
    candidate = os.path.join(folder, stem + extension)
    number = 2
    while os.path.exists(candidate):
        candidate = os.path.join(folder, '%s_%d%s' % (stem, number, extension))
        number += 1
    return candidate


def next_duplicate_path(path):
    """A free sibling name: example.py -> example_copy.py -> example_copy_2.py ..."""
    folder, filename = os.path.split(path)
    stem, extension = os.path.splitext(filename)
    return next_free_path(folder, stem + '_copy', extension)


def open_scratch_pad():
    """Create a blank scratch_pad.py beside the open script and open it in a new tab.

    Always a fresh file: scratch_pad.py, then scratch_pad_2.py and so on.
    With no script open it goes in Documents. Returns the path, or ''.
    """
    path = active_path()
    folder = os.path.dirname(path) if path else DOCUMENTS
    target = next_free_path(folder, SCRATCH_STEM, '.py')
    try:
        with open(target, 'w', encoding='utf-8') as handle:
            handle.write('')
    except Exception as error:
        hud('Scratch pad failed: %s' % error, 'error', 1.2)
        return ''
    open_script(target)
    hud('Opened %s' % os.path.basename(target))
    return target


# --- Ranges inside the open script ------------------------------------------
@on_main_thread
def replace_range(start, end, new_text):
    """Replace characters start..end (Python indices into active_text()).

    Goes through the active tab's text view, so edits near the end of the
    script land. Returns True on success.
    """
    text = active_text()
    if start == 0 and end >= len(text) and not new_text:
        new_text = EMPTY_SCRIPT          # never leave the buffer truly empty
    first, last = utf16_offset(text, start), utf16_offset(text, end)
    try:
        text_view = _active_text_view()
        if text_view is not None:
            span = ObjCClass('OMTextRange').rangeWithNSRange_(NSRange(first, last - first))
            text_view.replaceRange_withText_(span, new_text)
        else:
            editor.replace_text(first, last, new_text)
        return True
    except Exception as error:
        hud('Replace failed: %s' % error, 'error', 1.2)
        return False


def select_range(start, end, reveal=False):
    """Select characters start..end in the open script and scroll to them;
    with reveal, slide the console away so the selection shows."""
    text = active_text()
    try:
        editor.set_selection(utf16_offset(text, start), utf16_offset(text, end), scroll=True)
    except Exception as error:
        hud('Could not select: %s' % error, 'error', 1.2)
        return
    if reveal:
        bring_editor_forward()
def write_constant(name, new_value):
    """Set one top-level constant in the open script.

    Re-reads the script and finds the constant again by name first, so the
    offsets are never stale. Returns the text written, or None after a HUD
    saying why.
    """
    try:
        source = active_text()
        constant = constants_model.locate_constant(source, name)
        if constant is None:
            hud('%s not found' % name, 'error', 1.2)
            return None
        text = constants_model.format_constant_value(constant, new_value)
        if text != constant.source_text and not replace_range(constant.start, constant.end, text):
            return None
        return text
    except Exception as error:
        hud('Could not set %s: %s' % (name, error), 'error', 1.4)
        return None
# --- Tabs -------------------------------------------------------------------
def open_script(path, reveal=True):
    """Open path in a tab (its existing tab if already open) and, with
    reveal, slide the console away so it shows."""
    editor.open_file(path, new_tab=True)
    if reveal:
        bring_editor_forward()


def select_tab(path):
    """Switch to the tab showing path, leaving the console where it is."""
    try:
        open_script(path, reveal=False)
    except Exception as error:
        hud('Could not switch tab: %s' % error, 'error', 1.2)


@on_main_thread
def open_tab_paths():
    """(path of every open editor tab in tab order, the selected tab's path)."""
    _, detail = _pythonista_controllers()
    if detail is None:
        return [], ''
    paths = []
    for tab in detail.tabViewControllers():
        if not tab.respondsToSelector_(sel('filePath')):
            continue
        tab_path = tab.filePath()
        if tab_path is not None:
            paths.append(str(tab_path))
    selected = detail.selectedFilePath()
    return paths, (str(selected) if selected is not None else '')


@on_main_thread
def delete_active_script():
    """Close the open script's tab, then delete its file. Returns True on success.

    The tab is closed first (Pythonista's closeSelectedTab:) and must be gone
    before the file is touched: an open tab could write the file back.
    """
    path = active_path()
    if not path:
        hud('No open script', 'error')
        return False
    name = os.path.basename(path)
    wanted = os.path.realpath(path)
    _, detail = _pythonista_controllers()
    if detail is None or not detail.respondsToSelector_(sel('closeSelectedTab:')):
        hud('Delete unavailable here', 'error', 1.2)
        return False
    selected = detail.selectedFilePath()
    if selected is None or os.path.realpath(str(selected)) != wanted:
        hud('%s is not the selected tab; kept' % name, 'error', 1.4)
        return False
    detail.closeSelectedTab_(None)
    if any(os.path.realpath(tab_path) == wanted for tab_path in open_tab_paths()[0]):
        hud('Tab did not close; %s kept' % name, 'error', 1.4)
        return False
    try:
        os.remove(path)
    except Exception as error:
        hud('Delete failed: %s' % error, 'error', 1.2)
        return False
    bring_editor_forward()
    hud('Deleted %s' % name)
    return True
# --- Renaming ---------------------------------------------------------------
def clean_new_name(typed, old_name):
    """(new file name, problem). Pure; problem is '' when the name is usable.

    A name typed without an extension keeps the old file's extension.
    """
    name = (typed or '').strip()
    if not name:
        return '', 'Enter a name'
    if '/' in name or name in ('.', '..'):
        return '', 'No slashes in a name'
    if not os.path.splitext(name)[1]:
        name += os.path.splitext(old_name)[1]
    if name == old_name:
        return '', 'That is already its name'
    return name, ''


@on_main_thread
def rename_active_script(typed):
    """Rename the open script in its folder, through Pythonista's own rename
    (renameFileFrom:to:, full paths), so the open tab follows the file.
    Returns the new path, or '' with a HUD saying why not.
    """
    path = active_path()
    if not path:
        hud('No open script', 'error')
        return ''
    folder, old_name = os.path.split(path)
    new_name, problem = clean_new_name(typed, old_name)
    if problem:
        hud(problem, 'error', 1.2)
        return ''
    target = os.path.join(folder, new_name)
    if os.path.exists(target):
        hud('%s already exists' % new_name, 'error', 1.2)
        return ''
    _, detail = _pythonista_controllers()
    if detail is None:
        hud('Rename unavailable here', 'error', 1.2)
        return ''
    try:
        detail.renameFileFrom_to_(path, target)
    except Exception as error:
        hud('Rename failed: %s' % error, 'error', 1.2)
        return ''
    if not os.path.exists(target):
        hud('Rename failed', 'error', 1.2)
        return ''
    hud('Renamed to %s' % new_name)
    return target


def duplicate_active_script():
    """Save the editor's text (unsaved edits included) beside the script.

    Returns the new path, or '' on failure.
    """
    path = active_path()
    if not path:
        hud('No open script', 'error')
        return ''
    destination = next_duplicate_path(path)
    try:
        with open(destination, 'w', encoding='utf-8') as handle:
            handle.write(active_text())
    except Exception as error:
        hud('Duplicate failed: %s' % error, 'error', 1.2)
        return ''
    hud('Created %s' % os.path.basename(destination))
    return destination