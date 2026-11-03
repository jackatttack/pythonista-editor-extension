"""Find results as HTML, for the Find page's WebView.

Pure Python (no ui, no editor), so tests/test_find_html.py checks it headless.

The look is ported from Forge Landing's code viewer
(forge/adapters/pythonista/render/code.py): the same syntax colours and
line-numbered rows. The marking is new. The viewer marks its query as
case-insensitive text, which would disagree with the Find page's Aa and
Word toggles, so here each match is marked from find_model's exact span,
and every match on a line gets its own mark.

The page shell (page_html) is loaded once. After that the Find page swaps
results in with showResults(html, current) and moves the outline with
setCurrent(index), both through eval_js.
"""
import html
import io
import keyword
import token
import tokenize

LINK_SCHEME = 'editordeck://match/'    # tapping a match loads this plus its index

# --- Look (editable) ----------------------------------------------------------
SYNTAX_COLOURS = {
    'kw': '#ff6b7a',
    'fn': '#68D3C2',
    'cls': '#68D3C2',
    'self': '#68D3C2',
    'builtin': '#68D3C2',
    'str': '#FF9F43',
    'num': '#B58CFF',
    'com': '#8a8a8a',
}
FONT_SIZE = 12


BUILTINS = {
    'print', 'len', 'range', 'str', 'int', 'float', 'list', 'dict', 'set',
    'tuple', 'open', 'bool', 'enumerate', 'zip', 'min', 'max', 'sum', 'abs',
    'isinstance', 'getattr', 'setattr', 'hasattr', 'super', 'sorted', 'any',
    'all', 'map', 'filter', 'repr', 'type', 'round', 'object', 'Exception',
}


# --- Syntax colouring ---------------------------------------------------------
def token_class(tok, previous_name):
    """CSS class for one token, or None to leave it in the text colour."""
    if tok.type == token.NAME:
        if previous_name == 'def':
            return 'fn'
        if previous_name == 'class':
            return 'cls'
        if keyword.iskeyword(tok.string):
            return 'kw'
        if tok.string == 'self':
            return 'self'
        if tok.string in BUILTINS:
            return 'builtin'
        return None
    if tok.type == token.STRING:
        return 'str'
    if tok.type == token.NUMBER:
        return 'num'
    if tok.type == tokenize.COMMENT:
        return 'com'
    if token.tok_name.get(tok.type, '').startswith('FSTRING'):
        return 'str'          # Python 3.12+ splits f-strings into parts
    return None


def syntax_classes(text):
    """{line number: [(start, end, css class), ...]} for Python source.

    Columns are character positions within the line. Half-typed code that
    stops tokenizing keeps the colours found before the error, so a broken
    script still shows its matches, just less coloured.
    """
    lines = text.split('\n')
    classes = {}
    previous_name = None
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            css = token_class(tok, previous_name)
            previous_name = tok.string if tok.type == token.NAME else None
            if css is None:
                continue
            (start_row, start_col), (end_row, end_col) = tok.start, tok.end
            for row in range(start_row, end_row + 1):     # strings can span lines
                line_length = len(lines[row - 1]) if row <= len(lines) else 0
                first = start_col if row == start_row else 0
                last = end_col if row == end_row else line_length
                classes.setdefault(row, []).append((first, last, css))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        pass
    return classes


_cache = {'text': None, 'classes': {}}


def cached_syntax_classes(text):
    """syntax_classes, remembered for the last script (it is re-shown often)."""
    if _cache['text'] != text:
        _cache['text'] = text
        _cache['classes'] = syntax_classes(text)
    return _cache['classes']


# --- One line -----------------------------------------------------------------
def escape(text):
    return html.escape(text, quote=False)


def coloured(line, start, end, css_at):
    """line[start:end] as HTML, one span per run of the same syntax colour."""
    pieces = []
    run_start = start
    for position in range(start, end + 1):
        if position == end or css_at[position] != css_at[run_start]:
            if position > run_start:
                text = escape(line[run_start:position])
                css = css_at[run_start]
                pieces.append('<span class="%s">%s</span>' % (css, text) if css else text)
            run_start = position
    return ''.join(pieces)


def preview_html(index, old_html, replacement):
    """A match shown as Replace would change it: old struck through, new beside it.

    Both marks carry the match index, so a tap on either selects the match.
    """
    new = ''
    if replacement:
        new = '<mark data-m="%d" class="new">%s</mark>' % (index, escape(replacement))
    return '<mark data-m="%d" class="old">%s</mark>%s' % (index, old_html, new)


def line_html(line, classes, marks, preview=None):
    """One source line in full: syntax colours, and each match in a <mark>.

    marks are (start column, end column, match index), in order. Each mark
    carries its match index so a tap can say which match it was.
    """
    css_at = [None] * len(line)
    for start, end, css in classes:
        for position in range(max(start, 0), min(end, len(line))):
            css_at[position] = css
    out = []
    position = 0
    for start, end, index in marks:
        start, end = max(start, position), min(end, len(line))
        if start >= end:
            continue
        out.append(coloured(line, position, start, css_at))
        found = coloured(line, start, end, css_at)
        if preview is not None and index in preview:      # {match index: replacement}
            out.append(preview_html(index, found, preview[index]))
        else:
            out.append('<mark data-m="%d">%s</mark>' % (index, found))
        position = end
    out.append(coloured(line, position, len(line), css_at))
    return ''.join(out)


# --- The results ----------------------------------------------------------------
def line_blocks(hit_lines, line_count, context_lines):
    """Merged (first, last) line ranges: each hit line with its context.

    Ranges that touch or overlap become one block, so nearby matches share
    their context instead of repeating it.
    """
    blocks = []
    for line in sorted(set(hit_lines)):
        first = max(1, line - context_lines)
        last = min(line_count, line + context_lines)
        if blocks and first <= blocks[-1][1] + 1:
            blocks[-1] = (blocks[-1][0], max(blocks[-1][1], last))
        else:
            blocks.append((first, last))
    return blocks


def results_html(text, matches, context_lines=0, note='', preview=None):
    """HTML for the results: blocks of numbered lines with every match marked.

    matches are find_model Matches for text; their list positions are the
    indices the page uses for Next, Replace and taps.
    """
    lines = text.split('\n')
    classes = cached_syntax_classes(text)
    marks_by_line = {}
    for index, match in enumerate(matches):
        start = match.column
        marks_by_line.setdefault(match.line_number, []).append(
            (start, start + (match.end - match.start), index))

    out = []
    for first, last in line_blocks(marks_by_line, len(lines), context_lines):
        out.append('<div class="block">')
        for number in range(first, last + 1):
            marks = marks_by_line.get(number, [])
            code = line_html(lines[number - 1], classes.get(number, []), marks, preview)
            if marks:
                out.append('<div class="row hit" data-tap="%d">' % marks[0][2])
            else:
                out.append('<div class="row ctx">')
            out.append('<span class="ln">%d</span><span class="code">%s</span></div>'
                       % (number, code))
        out.append('</div>')
    if note:
        out.append(message_html(note))
    return ''.join(out)


def message_html(text):
    """A quiet line of text in place of results (empty query, no matches)."""
    return '<div class="note">%s</div>' % escape(text)


# --- The page shell -------------------------------------------------------------
def css_colour(value):
    """A CSS colour from a Pythonista one: a '#hex' or name as is, an RGB(A) tuple as rgba()."""
    if isinstance(value, str):
        return value
    red, green, blue = (round(part * 255) for part in value[:3])
    alpha = value[3] if len(value) > 3 else 1.0
    return 'rgba(%d, %d, %d, %.3f)' % (red, green, blue, alpha)


PAGE_SCRIPT = """
function showResults(html, current) {
    document.getElementById('results').innerHTML = html;
    setCurrent(current);
}
function setFontSize(px) {
    document.body.style.fontSize = px + 'px';
}
function setCurrent(index) {
    var old = document.querySelectorAll('.current');
    for (var i = 0; i < old.length; i++) { old[i].classList.remove('current'); }
    if (index < 0) { return; }
    var mark = document.querySelector('mark[data-m="' + index + '"]');
    if (!mark) { return; }
    mark.classList.add('current');
    var row = mark.closest('.row');
    if (row) { row.classList.add('current'); }
    mark.scrollIntoView({block: 'nearest', inline: 'nearest'});
}
document.addEventListener('click', function (event) {
    var target = event.target.closest('mark[data-m], .row[data-tap]');
    if (!target) { return; }
    var index = target.getAttribute('data-m') || target.getAttribute('data-tap');
    window.location.href = '%(scheme)s' + index;
});
"""


def page_html(colours, extra_css='', extra_script=''):
    """The results page, loaded once. colours is the deck's style.COLOURS.

    Plain CSS on purpose. On device (2026-11-03), position: sticky line
    numbers and opacity on context rows inside a sideways-scrolling block
    painted rows in the wrong places and hid the marks, so neither is used:
    line numbers scroll with their line, and context lines are greyed by
    colour instead.
    """
    values = {
        'background': css_colour(colours.get('panel', colours['card'])),
        'card': css_colour(colours['card']),
        'text': css_colour(colours['text']),
        'muted': css_colour(colours['muted']),
        'accent': css_colour(colours['accent']),
        'size': FONT_SIZE,
    }
    syntax_css = '\n'.join('.%s { color: %s; }' % item for item in SYNTAX_COLOURS.items())
    css = """
html, body { margin: 0; padding: 0; background: %(background)s; color: %(text)s;
    font: %(size)dpx Menlo, monospace; -webkit-text-size-adjust: none; }
.block { background: %(card)s; border-radius: 6px; margin: 0 0 6px 0; padding: 4px 0;
    overflow-x: auto; }
.row { display: flex; min-width: max-content; min-height: 1.65em; line-height: 1.65em; }
.row.hit { cursor: pointer; }
.row.current { background: rgba(255, 255, 255, 0.08); box-shadow: inset 3px 0 0 %(accent)s; }
.ln { flex: 0 0 40px; padding-right: 10px; text-align: right; color: %(muted)s;
    -webkit-user-select: none; }
.code { white-space: pre; tab-size: 4; padding-right: 12px; }
.row.ctx .code, .row.ctx .code span { color: %(muted)s; }
.sign { flex: 0 0 16px; color: %(muted)s; -webkit-user-select: none; }
.row.add { background: rgba(98, 210, 111, 0.16); }
.row.del { background: rgba(255, 90, 95, 0.16); }
.row.add .sign { color: #62D26F; }
.row.del .sign { color: #FF5A5F; }
mark { background: %(accent)s; color: #111111; border-radius: 3px; padding: 1px 0;
    cursor: pointer; }
mark span { color: #111111 !important; }
mark.current { box-shadow: 0 0 0 2px %(text)s; }
mark.old { background: #FF5A5F; text-decoration: line-through; }
mark.new { background: #62D26F; margin-left: 2px; }
.note { padding: 10px 4px; color: %(muted)s; font-family: -apple-system, sans-serif; }
""" % values
    script = PAGE_SCRIPT % {'scheme': LINK_SCHEME} + extra_script
    return ('<!doctype html><html><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<style>%s\n%s\n%s</style></head><body><div id="results"></div>'
            '<script>%s</script></body></html>' % (css, syntax_css, extra_css, script))