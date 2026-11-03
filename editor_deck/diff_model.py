"""Line diff for Replace from clipboard, as pure Python.

No ui, no editor: tests/test_diff_model.py checks it headless. The Quick
page shows the result in a DiffSheet before anything is replaced, drawn
with find_html's line colouring and page so it looks like Find.
"""
import difflib

from . import find_html

CONTEXT_LINES = 3     # unchanged lines shown around each change
MAX_ROWS = 1500       # rows drawn; a note says when the diff is longer

SIGNS = {'same': ' ', 'add': '+', 'del': '−'}
ROW_CLASSES = {'same': 'ctx', 'add': 'add', 'del': 'del'}


class DiffRow:
    """One line of the diff.

    kind is 'same', 'add' or 'del'. number is the line number on its side:
    the old script for removed lines, the new text otherwise.
    """

    def __init__(self, kind, number, text, side):
        self.kind = kind
        self.number = number
        self.text = text
        self.side = side      # 'old' or 'new': which text's colours apply

    def __repr__(self):
        return 'DiffRow(%s, %d)' % (self.kind, self.number)


class Diff:
    """The changed blocks (lists of DiffRows) and how many lines each way."""

    def __init__(self, groups, added, removed):
        self.groups = groups
        self.added = added
        self.removed = removed

    @property
    def changed(self):
        return bool(self.added or self.removed)


def line_diff(old_text, new_text, context=CONTEXT_LINES):
    """The Diff from old_text to new_text, compared line by line."""
    old_lines = old_text.split('\n')
    new_lines = new_text.split('\n')
    matcher = difflib.SequenceMatcher(None, old_lines, new_lines, autojunk=False)
    groups, added, removed = [], 0, 0
    for group in matcher.get_grouped_opcodes(context):
        rows = []
        for tag, old_start, old_end, new_start, new_end in group:
            if tag == 'equal':
                for index in range(new_start, new_end):
                    rows.append(DiffRow('same', index + 1, new_lines[index], 'new'))
                continue
            for index in range(old_start, old_end):      # replace and delete
                rows.append(DiffRow('del', index + 1, old_lines[index], 'old'))
                removed += 1
            for index in range(new_start, new_end):      # replace and insert
                rows.append(DiffRow('add', index + 1, new_lines[index], 'new'))
                added += 1
        groups.append(rows)
    return Diff(groups if (added or removed) else [], added, removed)


def summary(diff):
    """A short line for the sheet's header, such as '+12  −4 lines'."""
    return '+%d  −%d line%s' % (diff.added, diff.removed,
                                '' if diff.added + diff.removed == 1 else 's')


def diff_html(diff, old_text, new_text, limit=MAX_ROWS):
    """HTML for the diff: one block per change, for find_html's page."""
    classes = {'old': find_html.syntax_classes(old_text),
               'new': find_html.syntax_classes(new_text)}
    total = sum(len(rows) for rows in diff.groups)
    out = []
    shown = 0
    for rows in diff.groups:
        if shown >= limit:
            break
        out.append('<div class="block">')
        for row in rows:
            if shown >= limit:
                break
            code = find_html.line_html(row.text, classes[row.side].get(row.number, []), [])
            out.append('<div class="row %s"><span class="ln">%d</span>'
                       '<span class="sign">%s</span><span class="code">%s</span></div>'
                       % (ROW_CLASSES[row.kind], row.number, SIGNS[row.kind], code))
            shown += 1
        out.append('</div>')
    if total > shown:
        out.append(find_html.message_html('Showing the first %d of %d lines.' % (shown, total)))
    return ''.join(out)