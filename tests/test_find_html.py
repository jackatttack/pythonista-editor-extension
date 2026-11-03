"""Headless checks for editor_deck/find_html.py: whole lines, every match marked."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from editor_deck import find_html, find_model   # noqa: E402

failures = []


def check(name, condition):
    print(('ok    ' if condition else 'FAIL  ') + name)
    if not condition:
        failures.append(name)


def render(text, query, match_case=False, whole_word=False, context=0):
    matches = find_model.find_matches(text, query, match_case, whole_word)
    return matches, find_html.results_html(text, matches, context)


# Blocks merge when they touch, and stay inside the script.
check('blocks, no context', find_html.line_blocks([3, 4, 10], 20, 0) == [(3, 4), (10, 10)])
check('blocks, context 1', find_html.line_blocks([3, 4, 10], 20, 1) == [(2, 5), (9, 11)])
check('blocks clamp at the top', find_html.line_blocks([1], 20, 2) == [(1, 3)])

# Whole line with its indentation; two matches on one line, one inside a comment.
text = 'def a():\n    return a  # a\n'
matches, page = render(text, 'a', whole_word=True)
check('three matches', len(matches) == 3)
check('one mark per match', page.count('<mark ') == 3)
check('indentation kept, comment mark keeps its colour',
      '    <span class="kw">return</span> <mark data-m="1">a</mark>  '
      '<span class="com"># </span><mark data-m="2"><span class="com">a</span></mark>' in page)
check('function name coloured inside its mark',
      '<mark data-m="0"><span class="fn">a</span></mark>' in page)
check('line row taps its first match', '<div class="row hit" data-tap="1">' in page)

# Marks follow find_model, so match case is honoured.
matches, page = render('Name = name\n', 'name', match_case=True)
check('match case: one mark', page.count('<mark ') == 1 and '<mark data-m="0">name</mark>' in page)

# Context lines appear, unmarked.
matches, page = render('one\ntwo\nthree\nfour\n', 'three', context=1)
check('context lines shown', '<span class="ln">2</span>' in page and '<span class="ln">4</span>' in page)
check('context line not tappable', page.count('data-tap') == 1)

# HTML is escaped around marks.
matches, page = render('a <tag> b\n', 'tag')
check('escaped around a mark', '&lt;<mark data-m="0">tag</mark>&gt;' in page)

# Half-typed code still shows its matches.
matches, page = render('def broken(:\n    x = "unterminated\n', 'x')
check('broken source still marked', '<mark data-m="0">x</mark>' in page)

# Replace preview: old struck, new beside it, both carrying the match index.
matches = find_model.find_matches('x = old\n', 'old')
page = find_html.results_html('x = old\n', matches, 0, preview={0: 'new'})
check('preview marks old and new',
      '<mark data-m="0" class="old">old</mark><mark data-m="0" class="new">new</mark>' in page)
page = find_html.results_html('x = old\n', matches, 0, preview={0: ''})
check('preview of a deletion has no new mark', 'class="old"' in page and 'class="new"' not in page)
page = find_html.results_html('x = old\n', matches, 0, preview={0: '<b>'})
check('preview text is escaped', 'class="new">&lt;b&gt;</mark>' in page)
shell = find_html.page_html({'card': '#1b1e27', 'text': 'white', 'muted': (0.5, 0.5, 0.5),
                             'accent': '#ff4fa3'})
check('page shell has the link scheme and script',
      find_html.LINK_SCHEME in shell and 'function showResults' in shell)
check('tuple colour becomes rgba', 'rgba(128, 128, 128, 1.000)' in shell)

print('%d failed' % len(failures) if failures else 'all passed')
if failures:
    raise SystemExit(1)