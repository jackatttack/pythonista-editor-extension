"""Headless checks for the Editor Deck: geometry maths and clean imports.

Builds no views, so it is safe to run on a background thread.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
if PROJECT not in sys.path:
    sys.path.insert(0, PROJECT)
for module_name in list(sys.modules):
    if module_name == 'editor_deck' or module_name.startswith('editor_deck.'):
        del sys.modules[module_name]

from editor_deck import geometry
print('    testing %s' % os.path.dirname(os.path.dirname(os.path.abspath(geometry.__file__))))

CONSOLE = (0, 0, 400, 600)


def check(name, actual, expected):
    if actual != expected:
        raise AssertionError('%s: expected %r, got %r' % (name, expected, actual))
    print('ok  %s' % name)


check('panel frame insets the console', geometry.panel_frame(CONSOLE, 8, 8, 56), (8, 8, 384, 536))
check('panel frame keeps a minimum height',
      geometry.panel_frame((0, 0, 400, 100), 8, 8, 56)[3], geometry.MINIMUM_PANEL_HEIGHT)
check('corner square sits in the panel bottom right',
      geometry.corner_square_origin((8, 8, 384, 536), 48, 8), (8 + 384 - 56, 8 + 536 - 56))
check('corner square follows an offset panel',
      geometry.corner_square_origin((20, 100, 200, 300), 48, 8), (20 + 200 - 56, 100 + 300 - 56))

from editor_deck import shell, dock
check('four pages', shell.PAGE_TITLES, ['Quick', 'Find', 'Constants', 'Snippets'])
check('show_deck is callable', callable(shell.show_deck), True)
check('deck tag is set', dock.DECK_VIEW_TAG > 0, True)

import random
from editor_deck import fold_flourish
if fold_flourish.available():
    START = 100.0
    opening = fold_flourish.PaperShow(384, 536, folding_up=False, start=START,
                                      rng=random.Random(1))
    check('unfold covers nothing at the start',
          any(opening.is_covered(fold, START) for fold in opening.folds), False)
    check('unfold covers everything once done',
          all(opening.is_covered(fold, opening.end) for fold in opening.folds), True)
    check('unfold starts from the corner',
          [fold.piece for fold in opening.folds if fold.parent is None], [opening.corner])
    print('    unfold takes %.2fs over %d squares' % (opening.end - START, len(opening.folds)))
    check('unfold is under a second', opening.end - START < 1.0, True)

    closing = fold_flourish.PaperShow(384, 536, folding_up=True, start=START,
                                      rng=random.Random(1))
    check('fold-up is fully covered until it starts',
          all(closing.is_covered(fold, START - 0.001) for fold in closing.folds), True)
    corner_fold = [fold for fold in closing.folds if fold.piece == closing.corner][0]
    check('fold-up lifts the corner last',
          corner_fold.start, max(fold.start for fold in closing.folds))

    calls = []
    opening.on_finished = lambda: calls.append('done')
    opening.finished()
    opening.finished()
    check('finished calls back once', calls, ['done'])
else:
    print('skip  fold flourish: boardkit not importable')
import tempfile
from editor_deck import editor_bridge
check('utf16 length counts an emoji as two', editor_bridge.utf16_length('a👋'), 3)
with tempfile.TemporaryDirectory() as folder:
    original = os.path.join(folder, 'demo.py')
    first = editor_bridge.next_duplicate_path(original)
    check('first duplicate name', os.path.basename(first), 'demo_copy.py')
    open(first, 'w').close()
    check('second duplicate name',
          os.path.basename(editor_bridge.next_duplicate_path(original)), 'demo_copy_2.py')
from editor_deck.pages import quick, tiles
QUICK_ACTIONS = ('copy_script', 'copy_path', 'copy_run_url', 'copy_open_url',
                 'open_scratch_pad', 'open_rename', 'duplicate_script', 'open_constants',
                 'replace_with_clipboard', 'append_clipboard', 'clear_script', 'delete_script')
check('quick page has all twelve tools',
      [name for name in QUICK_ACTIONS if not hasattr(quick.QuickPage, name)], [])
from editor_deck import tab_strip
check('tab strip loads', callable(tab_strip.TabStrip), True)
with tempfile.TemporaryDirectory() as folder:
    first = editor_bridge.next_free_path(folder, 'scratch_pad', '.py')
    check('first scratch pad name', os.path.basename(first), 'scratch_pad.py')
    open(first, 'w').close()
    check('second scratch pad name',
          os.path.basename(editor_bridge.next_free_path(folder, 'scratch_pad', '.py')),
          'scratch_pad_2.py')
check('rename keeps the old extension', editor_bridge.clean_new_name('tools', 'demo.py'), ('tools.py', ''))
check('rename takes a typed extension', editor_bridge.clean_new_name(' notes.txt ', 'demo.py'), ('notes.txt', ''))
check('rename refuses blank', editor_bridge.clean_new_name('  ', 'demo.py')[1], 'Enter a name')
check('rename refuses slashes', editor_bridge.clean_new_name('a/b', 'demo.py')[1], 'No slashes in a name')
check('rename refuses the same name', editor_bridge.clean_new_name('demo', 'demo.py')[1],
      'That is already its name')
check('editor empties to one newline', editor_bridge.EMPTY_SCRIPT, '\n')
from editor_deck import find_model
SAMPLE = 'cat concatenate Cat'
check('find ignores case by default', len(find_model.find_matches(SAMPLE, 'cat')), 3)
check('find can match case', len(find_model.find_matches(SAMPLE, 'cat', match_case=True)), 2)
check('find can match whole words', len(find_model.find_matches(SAMPLE, 'cat', whole_word=True)), 2)
check('find whole word and case', len(find_model.find_matches(SAMPLE, 'cat', True, True)), 1)
LINES = 'a\nfoo bar\nfoo'
check('find gives line numbers', [m.line_number for m in find_model.find_matches(LINES, 'foo')], [2, 3])
check('find gives line text', find_model.find_matches(LINES, 'bar')[0].line_text, 'foo bar')
check('find treats brackets literally', len(find_model.find_matches('f(x) + (x)', '(x)')), 2)
check('replace all inserts text literally', find_model.replace_all('a.b', '.', r'\1'), ('a\\1b', 1))
check('replace all counts', find_model.replace_all('aXbXc', 'x', '-')[1], 2)
check('empty query finds nothing', find_model.find_matches('abc', ''), [])
check('next match wraps', find_model.index_at_or_after(find_model.find_matches('ab ab', 'ab'), 99), 0)
check('utf16 offset after an emoji', editor_bridge.utf16_offset('👋b', 1), 2)
from editor_deck.pages import find as find_page
check('find page loads', callable(find_page.FindPage), True)
from editor_deck import constants_model as cm
CONSTANTS_SAMPLE = '''# -*- coding: utf-8 -*-
import os

# ==========
# Colours
# ==========

ACCENT = '#6596ff'
WARNING = "#FFC857"  # amber
TITLE = 'Café ☕'

# ==========
# Sizes
# ==========

TILE_SIZE = 64  # range: 16-128
SPEED: float = 0.25
DEBUG = False
EMOJI_GAP = {'🙂': 1}; AFTER = 5
ROOT = os.path.expanduser('~')
lower_case = 3
DOUBLE_TILE = TILE_SIZE * 2
'''
found = {c.name: c for c in cm.find_editable_constants(CONSTANTS_SAMPLE)}
check('constants: only plain top-level UPPER_CASE literals', list(found),
      ['ACCENT', 'WARNING', 'TITLE', 'TILE_SIZE', 'SPEED', 'DEBUG', "EMOJI_GAP['🙂']", 'AFTER'])
check('constants: kinds', [found[n].kind for n in ('ACCENT', 'TITLE', 'TILE_SIZE', 'SPEED', 'DEBUG',
      "EMOJI_GAP['🙂']")], ['colour', 'text', 'int', 'float', 'bool', 'int'])
check('constants: a dict entry after an emoji key lands on its value',
      CONSTANTS_SAMPLE[found["EMOJI_GAP['🙂']"].start:found["EMOJI_GAP['🙂']"].end], '1')
check('constants: range hint', found['TILE_SIZE'].slider_range, (16, 128))
check('constants: sections', (found['ACCENT'].section, found['TILE_SIZE'].section), ('Colours', 'Sizes'))
check('constants: offsets survive accents', CONSTANTS_SAMPLE[found['TITLE'].start:found['TITLE'].end], "'Café ☕'")
check('constants: offsets survive emoji', CONSTANTS_SAMPLE[found['AFTER'].start:found['AFTER'].end], '5')
check('constants: colour keeps quotes and case', cm.format_constant_value(found['WARNING'], '#1e90ff'), '"#1E90FF"')
check('constants: float keeps decimals', cm.format_constant_value(found['SPEED'], 0.3), '0.3')
check('constants: replace keeps the comment',
      'TILE_SIZE = 96  # range: 16-128' in cm.replace_constant_in_source(CONSTANTS_SAMPLE, 'TILE_SIZE', '96'), True)
check('constants: hex round trip', cm.rgba_to_hex(*cm.hex_to_rgba('#1E90FF')[:3]), '#1E90FF')
LIST_SAMPLE = "EXAMPLE = [1, 1.0, 'hey', '#000000', -2]  # tweakables\nNESTED = [1, [2]]\nEMPTY = []\n"
listed = {c.name: c for c in cm.find_editable_constants(LIST_SAMPLE)}
check('lists: each plain item is its own constant', list(listed),
      ['EXAMPLE[0]', 'EXAMPLE[1]', 'EXAMPLE[2]', 'EXAMPLE[3]', 'EXAMPLE[4]', 'NESTED', 'EMPTY'])
check('lists: item kinds', [listed['EXAMPLE[%d]' % i].kind for i in range(5)],
      ['int', 'float', 'text', 'colour', 'int'])
check('lists: items share a section named after the list', listed['EXAMPLE[2]'].section, 'EXAMPLE')
check('lists: nested stays one raw constant', listed['NESTED'].kind, 'literal')
check('lists: an item is replaced in place',
      cm.replace_constant_in_source(LIST_SAMPLE, 'EXAMPLE[2]', "'yo'").split('\n')[0],
      "EXAMPLE = [1, 1.0, 'yo', '#000000', -2]  # tweakables")
check('lists: a negative item rewrites', cm.replace_constant_in_source(
      LIST_SAMPLE, 'EXAMPLE[4]', cm.format_constant_value(listed['EXAMPLE[4]'], 7)).split('\n')[0],
      "EXAMPLE = [1, 1.0, 'hey', '#000000', 7]  # tweakables")
check('lists: last assignment wins', [c.name for c in cm.find_editable_constants(
      "A = [1, 2, 3]\nA = [9]\n")], ['A[0]'])
DICT_SAMPLE = ("SETTINGS = {'speed': 1.5, 'name': \"x\", 'tint': '#FF0000', 3: True}  # knobs\n"
               "DEEP = {'a': {'b': 1}}\nTWICE = {'a': 1, 'a': 2}\n")
keyed = {c.name: c for c in cm.find_editable_constants(DICT_SAMPLE)}
check('dicts: each plain entry is its own constant', list(keyed),
      ["SETTINGS['speed']", "SETTINGS['name']", "SETTINGS['tint']", 'SETTINGS[3]', 'DEEP',
       "TWICE['a']"])
check('dicts: entry kinds', [keyed[n].kind for n in ("SETTINGS['speed']", "SETTINGS['name']",
      "SETTINGS['tint']", 'SETTINGS[3]')], ['float', 'text', 'colour', 'bool'])
check('dicts: entries share a section named after the dict', keyed["SETTINGS['tint']"].section,
      'SETTINGS')
check('dicts: nested stays one raw constant', keyed['DEEP'].kind, 'literal')
check('dicts: a repeated key keeps the last value', keyed["TWICE['a']"].value, 2)
check('dicts: an entry is replaced in place', cm.replace_constant_in_source(
      DICT_SAMPLE, "SETTINGS['speed']", cm.format_constant_value(keyed["SETTINGS['speed']"], 2.0)
      ).split('\n')[0],
      "SETTINGS = {'speed': 2.0, 'name': \"x\", 'tint': '#FF0000', 3: True}  # knobs")
check('dicts: unpacking is skipped', cm.find_editable_constants('A = {**B}\n'), [])
from editor_deck.pages import constants as constants_page
check('constants page loads', callable(constants_page.ConstantsPage), True)
from editor_deck import snippets_store as ss
check('snippets: title from the first real line', ss.suggest_title('\n  def main():\n    pass'), 'def main():')
check('snippets: long titles shortened', len(ss.suggest_title('x' * 100)), ss.TITLE_LENGTH)
check('snippets: blank value is Untitled', ss.suggest_title('  \n'), 'Untitled')
stored = ss.add(ss.add([], 'first', 'a'), '', 'print(1)')
check('snippets: newest first, blank title suggested', [s['title'] for s in stored], ['print(1)', 'first'])
check('snippets: remove by index', [s['title'] for s in ss.remove(stored, 0)], ['first'])
with tempfile.TemporaryDirectory() as folder:
    store_path = os.path.join(folder, 'data', 'snippets.json')
    check('snippets: missing file is a fresh start', ss.load(store_path), ([], ''))
    ss.save(store_path, stored + [{'title': 'emoji', 'value': '👋 é'}])
    check('snippets: save and load round trip', ss.load(store_path)[0][-1]['value'], '👋 é')
    with open(store_path, 'w', encoding='utf-8') as handle:
        handle.write('{broken')
    check('snippets: unreadable file is reported', bool(ss.load(store_path)[1]), True)
from editor_deck.pages import snippets as snippets_page
check('snippets page loads', callable(snippets_page.SnippetsPage), True)
print('editor deck smoke: all passed')