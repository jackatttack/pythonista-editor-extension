"""Headless checks for editor_deck/diff_model.py: the diff shown before Replace."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from editor_deck import diff_model   # noqa: E402

failures = []


def check(name, condition):
    print(('ok    ' if condition else 'FAIL  ') + name)
    if not condition:
        failures.append(name)


def numbered(count, changed=None):
    lines = ['line %d' % number for number in range(1, count + 1)]
    for number, text in (changed or {}).items():
        lines[number - 1] = text
    return '\n'.join(lines) + '\n'


old = numbered(20)

same = diff_model.line_diff(old, old)
check('identical: nothing changed', not same.changed and same.groups == [])

one = diff_model.line_diff(old, numbered(20, {10: 'line ten'}))
kinds = [row.kind for row in one.groups[0]] if one.groups else []
check('one change: one block', len(one.groups) == 1)
check('one change: 3 context, del, add, 3 context',
      kinds == ['same'] * 3 + ['del', 'add'] + ['same'] * 3)
check('one change: counts', one.added == 1 and one.removed == 1)
check('removed line keeps its old number',
      [row.number for row in one.groups[0] if row.kind == 'del'] == [10])

inserted = diff_model.line_diff(old, old.replace('line 5\n', 'line 5\nnew a\nnew b\n'))
check('insert only: two added, none removed', inserted.added == 2 and inserted.removed == 0)
check('added lines take new numbers',
      [row.number for row in inserted.groups[0] if row.kind == 'add'] == [6, 7])

apart = diff_model.line_diff(old, numbered(20, {2: 'two', 18: 'eighteen'}))
check('far-apart changes: two blocks', len(apart.groups) == 2)

check('summary', diff_model.summary(one) == '+1  −1 lines')
check('summary singular', diff_model.summary(diff_model.line_diff('a\n', 'a\nb\n')) == '+1  −0 line')

code_old = 'def area(width):\n    return width\n'
code_new = 'def area(width, height):\n    return width * height\n'
diff = diff_model.line_diff(code_old, code_new)
page = diff_model.diff_html(diff, code_old, code_new)
check('rows marked del and add', '<div class="row del">' in page and '<div class="row add">' in page)
check('syntax colours kept', '<span class="kw">def</span>' in page)
check('signs shown', '<span class="sign">−</span>' in page and '<span class="sign">+</span>' in page)

short = diff_model.diff_html(one, old, numbered(20, {10: 'line ten'}), limit=2)
check('long diff notes the limit', 'Showing the first 2 of 8 lines.' in short)

print('%d failed' % len(failures) if failures else 'all passed')
if failures:
    raise SystemExit(1)