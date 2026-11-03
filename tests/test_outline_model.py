"""Headless checks for editor_deck/outline_model.py: the Outline page's structure."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from editor_deck import outline_model   # noqa: E402

failures = []


def check(name, condition):
    print(('ok    ' if condition else 'FAIL  ') + name)
    if not condition:
        failures.append(name)


SAMPLE = '''import os

LIMIT = 3


@dataclass
class Board:
    size = 4

    def move(self, step):
        def helper():
            return step
        return helper()

    async def load(self):
        pass


def main():
    Board().move(1)
'''


def names(nodes):
    return [node.name for node in nodes]


nodes, exact = outline_model.outline(SAMPLE)
board = nodes[0] if nodes else None
check('parsed exactly', exact)
check('top level: Board and main', names(nodes) == ['Board', 'main'])
check('methods nest under the class', board is not None and names(board.children) == ['move', 'load'])
check('nested function nests under its method',
      board is not None and board.children[0].children[0].qualname == 'Board.move.helper')
check('class starts at its decorator, header on the class line, ends at its last line',
      board is not None and (board.start, board.header, board.end) == (6, 7, 16))
check('count of definitions', outline_model.count_nodes(nodes) == 5)

broken = SAMPLE.replace('pass', 'pass(')
scanned, exact = outline_model.outline(broken)
scanned_board = scanned[0] if scanned else None
check('broken script falls back to the line scan', not exact)
check('scan: same top level', names(scanned) == ['Board', 'main'])
check('scan: methods by indentation',
      scanned_board is not None and names(scanned_board.children) == ['move', 'load'])
check('scan: class ends before the next top-level code', scanned_board.end == 16)
check('scan: nested function found', names(scanned_board.children[0].children) == ['helper'])

page = outline_model.outline_html(SAMPLE, nodes, True)
check('class block with its id', '<details class="node class" data-id="Board">' in page)
check('method block with its qualified id', 'data-id="Board.move"' in page)
check('jump goes to the def line', 'data-line="10"' in page)
check('header line coloured in the row',
      '<span class="kw">class</span> <span class="cls">Board</span>:' in page)
check('top-level code folds under its first line', 'import os' in page and 'data-id="top-1"' in page)
check('every code line shown once', page.count('<span class="ln">12</span>') == 1
      and page.count('<span class="ln">8</span>') == 1)
check('blank-only stretches make no row', 'data-id="top-2"' not in page)
check('fallback says so', 'does not parse' in outline_model.outline_html(broken, scanned, False))

print('%d failed' % len(failures) if failures else 'all passed')
if failures:
    raise SystemExit(1)