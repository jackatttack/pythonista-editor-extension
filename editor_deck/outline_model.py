"""The open script's outline (classes, functions, methods), as pure Python.

No ui, no editor: tests/test_outline_model.py checks it headless. The
Outline page draws outline_html() with Find's viewer (find_html.py).

The structure comes from ast, which gives exact start and end lines. While
the script does not parse (half-typed code), it comes from the def and class
lines instead, nested by indentation, so the outline never goes blank.

Each class or function is a <details> block: collapsed it is one row (its
def or class line), open it shows its code, with nested definitions folded
inside. Top-level code between definitions gets rows of its own.
"""
import ast
import re

from . import find_html

LINE_LINK = 'editordeck://line/'   # ↗ loads this plus the line number
LABEL_LENGTH = 60                  # characters of a top-level row's first line

HEADER = re.compile(r'^(\s*)(?:async\s+)?(def|class)\s+(\w+)')


class Node:
    """A class or function: lines start..end (decorators included), header
    is its def or class line, children are definitions directly inside it."""

    def __init__(self, kind, name, start, header, end, parent=''):
        self.kind = kind          # 'class' or 'def'
        self.name = name
        self.start = start
        self.header = header
        self.end = end
        self.qualname = parent + '.' + name if parent else name
        self.children = []

    def __repr__(self):
        return 'Node(%s %s, %d-%d)' % (self.kind, self.qualname, self.start, self.end)


# --- Finding the outline ------------------------------------------------------
def outline(text):
    """(top-level Nodes, exact). exact is False when the script does not parse
    and the def/class line scan was used instead."""
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return scan_outline(text), False
    return nodes_from_ast(tree.body, ''), True


def nodes_from_ast(statements, parent):
    nodes = []
    for item in statements:
        if isinstance(item, ast.ClassDef):
            kind = 'class'
        elif isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            kind = 'def'
        else:
            continue
        start = min([item.lineno] + [decorator.lineno for decorator in item.decorator_list])
        node = Node(kind, item.name, start, item.lineno, item.end_lineno, parent)
        node.children = nodes_from_ast(item.body, node.qualname)
        nodes.append(node)
    return nodes


def indent_of(line):
    return len(line) - len(line.lstrip())


def scan_outline(text):
    """The outline from def and class lines alone, nested by indentation.

    A definition ends at its last non-blank line before the next code line
    indented no deeper than its own header.
    """
    lines = text.split('\n')
    roots, stack = [], []          # stack: (indent, node) of open definitions
    for index, line in enumerate(lines):
        found = HEADER.match(line)
        if not found:
            continue
        indent = len(found.group(1).expandtabs(4))
        end = index
        for later in range(index + 1, len(lines)):
            stripped = lines[later].strip()
            if not stripped:
                continue
            if indent_of(lines[later].expandtabs(4)) <= indent and not stripped.startswith('#'):
                break
            end = later
        while stack and stack[-1][0] >= indent:
            stack.pop()
        parent = stack[-1][1] if stack else None
        node = Node(found.group(2), found.group(3), index + 1, index + 1, end + 1,
                    parent.qualname if parent else '')
        (parent.children if parent else roots).append(node)
        stack.append((indent, node))
    return roots


def count_nodes(nodes):
    return sum(1 + count_nodes(node.children) for node in nodes)


# --- Drawing it ---------------------------------------------------------------
def outline_html(text, nodes, exact=True):
    """HTML for the Outline page: nested <details>, every line shown once."""
    lines = text.split('\n')
    classes = find_html.cached_syntax_classes(text)
    out = []
    if not exact:
        out.append(find_html.message_html(
            'The script does not parse right now, so this outline comes from '
            'its def and class lines.'))
    out.append(span_html(1, len(lines), nodes, lines, classes, True, [0]))
    return ''.join(out)


def span_html(first, last, children, lines, classes, top, counter):
    """Lines first..last: children as folding blocks, the code between as rows.

    At the top level the code between definitions folds too (one row per
    stretch); inside a definition it is shown as it is.
    """
    out = []
    line = first
    for child in children:
        if child.start > line:
            out.append(gap_html(line, child.start - 1, lines, classes, top, counter))
        out.append(node_html(child, lines, classes, counter))
        line = max(line, child.end + 1)
    if line <= last:
        out.append(gap_html(line, last, lines, classes, top, counter))
    return ''.join(out)


def rows_html(first, last, lines, classes):
    rows = []
    for number in range(first, last + 1):
        code = find_html.line_html(lines[number - 1], classes.get(number, []), [])
        rows.append('<div class="row"><span class="ln">%d</span>'
                    '<span class="code">%s</span></div>' % (number, code))
    return '<div class="block">%s</div>' % ''.join(rows)


def line_range(first, last):
    return '%d' % first if first == last else '%d–%d' % (first, last)


def gap_html(first, last, lines, classes, top, counter):
    if not top:
        return rows_html(first, last, lines, classes)
    while first <= last and not lines[first - 1].strip():
        first += 1
    while last >= first and not lines[last - 1].strip():
        last -= 1
    if first > last:
        return ''                  # only blank lines: nothing to fold
    counter[0] += 1
    label = lines[first - 1].strip()
    if len(label) > LABEL_LENGTH:
        label = label[:LABEL_LENGTH] + ' …'
    return ('<details class="node gap" data-id="top-%d"><summary><span class="head">'
            '<span class="code">%s</span><span class="where">%s</span></span></summary>'
            '<div class="body">%s</div></details>'
            % (counter[0], find_html.escape(label), line_range(first, last),
               rows_html(first, last, lines, classes)))


def node_html(node, lines, classes, counter):
    header = lines[node.header - 1]
    indent = indent_of(header)
    shifted = [(start - indent, end - indent, css)
               for start, end, css in classes.get(node.header, [])]
    summary = find_html.line_html(header.lstrip(), shifted, [])
    body = span_html(node.start, node.end, node.children, lines, classes, False, counter)
    return ('<details class="node %s" data-id="%s"><summary><span class="head">'
            '<span class="code">%s</span><span class="where">%d</span>'
            '<span class="jump" data-line="%d">↗</span></span></summary>'
            '<div class="body">%s</div></details>'
            % (node.kind, find_html.escape(node.qualname), summary, node.header,
               node.header, body))


# --- The page's extra look and script -------------------------------------------
def outline_css(colours):
    """CSS added to find_html's page for the outline. Plain flow layout: no
    sticky positioning or opacity (they mis-painted in the docked WebView)."""
    values = {
        'card': find_html.css_colour(colours['card']),
        'muted': find_html.css_colour(colours['muted']),
        'accent': find_html.css_colour(colours['accent']),
    }
    return """
details.node { margin: 0 0 4px 0; }
details.node details.node { margin-left: 12px; }
summary { list-style: none; cursor: pointer; }
summary::-webkit-details-marker { display: none; }
.head { display: flex; align-items: center; background: %(card)s; border-radius: 6px;
    padding: 6px 8px; }
.head::before { content: '▸'; color: %(muted)s; flex: 0 0 14px; }
details[open] > summary .head::before { content: '▾'; }
.head .code { flex: 1 1 auto; min-width: 0; overflow: hidden; text-overflow: ellipsis; }
.head .where { color: %(muted)s; padding: 0 6px; font-size: 0.85em; }
.head .jump { color: %(accent)s; padding: 0 2px 0 8px; font-size: 1.25em; }
details.gap > summary .code { color: %(muted)s; }
.body { padding: 4px 0 0 0; }
""" % values


OUTLINE_SCRIPT = """
var openIds = {};
document.addEventListener('toggle', function (event) {
    var node = event.target;
    if (!node.getAttribute || !node.getAttribute('data-id')) { return; }
    if (node.open) { openIds[node.getAttribute('data-id')] = true; }
    else { delete openIds[node.getAttribute('data-id')]; }
}, true);
document.addEventListener('click', function (event) {
    var jump = event.target.closest('[data-line]');
    if (!jump) { return; }
    event.preventDefault();          // a jump does not also fold its row
    window.location.href = '%(link)s' + jump.getAttribute('data-line');
});
function showOutline(html) {
    var top = window.scrollY;
    document.getElementById('results').innerHTML = html;
    var nodes = document.querySelectorAll('details[data-id]');
    for (var i = 0; i < nodes.length; i++) {
        if (openIds[nodes[i].getAttribute('data-id')]) { nodes[i].open = true; }
    }
    window.scrollTo(0, top);
}
function setAllOpen(open) {
    var nodes = document.querySelectorAll('details[data-id]');
    for (var i = 0; i < nodes.length; i++) { nodes[i].open = open; }
}
function forgetOpen() { openIds = {}; window.scrollTo(0, 0); }
""" % {'link': LINE_LINK}