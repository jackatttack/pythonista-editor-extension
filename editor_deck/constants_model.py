"""Finding and rewriting a script's top-level constants, as pure Python.

Ported from Action Deck's Tune Constants (clipboard_menu_v2.py). No ui and
no editor, so it runs anywhere and the smoke test checks it headless.

Only module-level UPPER_CASE names assigned a plain literal are editable.
Anything computed (ROOT = os.path...) is skipped, because rewriting it
would change more than a value. An optional trailing comment sets a
number's slider range:

    TILE_SIZE = 64  # range: 16-128
"""
import ast
import re

CONSTANT_NAME_PATTERN = re.compile(r'^[A-Z][A-Z0-9_]*$')
HEX_COLOUR_PATTERN = re.compile(r'^#(?:[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})$')
RANGE_HINT_PATTERN = re.compile(
    r'#.*?\brange:\s*(-?\d+(?:\.\d+)?)\s*(?:-|to|\.\.)\s*(-?\d+(?:\.\d+)?)'
)


class EditableConstant(object):
    """One top-level constant as it appears in the source right now.

    start and end are character offsets of the value expression, so
    source_text == source[start:end], the text after '=' without any
    comment. They go stale after any edit: look the constant up again by
    name before writing (locate_constant does this).
    """

    def __init__(self, name, value, kind, source_text, line,
                 start, end, section, slider_range):
        self.name = name
        self.value = value
        self.kind = kind                  # bool, int, float, colour, text or literal
        self.source_text = source_text
        self.line = line
        self.start = start
        self.end = end
        self.section = section            # nearest banner title above, or ''
        self.slider_range = slider_range  # (low, high) for numbers, else None

    def __repr__(self):
        return 'EditableConstant(%s = %s, %s)' % (self.name, self.source_text, self.kind)


def classify_constant_value(value):
    """Name the kind of control a value gets. bool comes first: True is an int."""
    if isinstance(value, bool):
        return 'bool'
    if isinstance(value, int):
        return 'int'
    if isinstance(value, float):
        return 'float'
    if isinstance(value, str):
        return 'colour' if HEX_COLOUR_PATTERN.match(value) else 'text'
    return 'literal'


def default_slider_range(value):
    """A starting range when no '# range:' hint is given: 0 to twice the value."""
    if value == 0:
        return (0, 10) if isinstance(value, int) else (0.0, 1.0)
    low, high = sorted((0, value * 2))
    return (low, high)


def find_editable_constants(source):
    """Every editable top-level constant in source, in file order.

    A list, tuple or dict made only of plain values (numbers, bools,
    strings) is opened up: each item becomes its own constant, named like
    EXAMPLE[2] or SETTINGS['speed'], in a section named after it, so items
    can be tuned one by one. Anything nested, ** unpacking and empty ones
    stay a single raw-source constant.

    Raises SyntaxError if the source does not parse; the page reports that
    rather than guessing.
    """
    tree = ast.parse(source)
    lines = source.split('\n')
    line_starts = _line_start_offsets(lines)
    section_titles = _section_titles(lines)

    def make(name, value_node, value, section, read_range_hint):
        start = _character_offset(lines, line_starts, value_node.lineno, value_node.col_offset)
        end = _character_offset(lines, line_starts, value_node.end_lineno,
                                value_node.end_col_offset)
        kind = classify_constant_value(value)
        slider_range = None
        if kind in ('int', 'float'):
            hint = None
            if read_range_hint:
                end_column = end - line_starts[value_node.end_lineno - 1]
                hint = RANGE_HINT_PATTERN.search(lines[value_node.end_lineno - 1][end_column:])
            if hint:
                number = int if kind == 'int' else float
                slider_range = (number(float(hint.group(1))), number(float(hint.group(2))))
            else:
                slider_range = default_slider_range(value)
        return EditableConstant(name=name, value=value, kind=kind,
                                source_text=source[start:end], line=value_node.lineno,
                                start=start, end=end, section=section,
                                slider_range=slider_range)

    # A name assigned twice: Python keeps the last value, so only that one is editable.
    assignments = []
    for node in tree.body:
        name, value_node = _constant_assignment(node)
        if name is None:
            continue
        try:
            value = ast.literal_eval(value_node)
        except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
            continue  # computed, not a plain literal
        assignments.append((name, node, value_node, value))
    last_node_by_name = dict((name, node) for name, node, _, _ in assignments)

    constants = []
    for name, node, value_node, value in assignments:
        if last_node_by_name[name] is not node:
            continue
        section = _section_for_line(section_titles, node.lineno)
        items = _scalar_items(value_node)
        if items:
            group_section = '%s · %s' % (section, name) if section else name
            for label, item_node, item_value in items:
                constants.append(make('%s[%s]' % (name, label), item_node, item_value,
                                      group_section, read_range_hint=False))
        else:
            constants.append(make(name, value_node, value, section, read_range_hint=True))
    return constants


def locate_constant(source, name):
    """Find one constant by name in the current source, or None."""
    for constant in find_editable_constants(source):
        if constant.name == name:
            return constant
    return None


def format_constant_value(constant, new_value):
    """Write new_value as source text in the style of the constant's current text.

    Keeps the original quote character, hex digit case and decimal places
    where it can. Raises ValueError if the result would not read back as a
    valid literal of the same value.
    """
    kind = constant.kind
    if kind == 'bool':
        text = 'True' if new_value else 'False'
    elif kind == 'int':
        text = str(int(round(new_value)))
    elif kind == 'float':
        text = _format_decimal(new_value, constant.source_text)
    elif kind == 'colour':
        new_value = _match_hex_case(new_value, constant.value)
        text = _format_string(new_value, constant.source_text)
    elif kind == 'text':
        text = _format_string(new_value, constant.source_text)
    else:
        text = repr(new_value)

    try:
        read_back = ast.literal_eval(text)
    except (ValueError, SyntaxError):
        raise ValueError('%s: %r is not a valid literal' % (constant.name, text))
    if kind in ('colour', 'text') and read_back != new_value:
        raise ValueError('%s: %r does not read back as %r' % (constant.name, text, new_value))
    return text


def replace_constant_in_source(source, name, new_value_text):
    """source with one constant's value text replaced. Pure; used by tests."""
    constant = locate_constant(source, name)
    if constant is None:
        raise KeyError(name)
    return source[:constant.start] + new_value_text + source[constant.end:]


def hex_to_rgba(hex_colour):
    """'#RRGGBB' or '#RRGGBBAA' -> (red, green, blue, alpha), each 0 to 1."""
    digits = hex_colour.lstrip('#')
    channels = [int(digits[index:index + 2], 16) / 255.0
                for index in range(0, len(digits), 2)]
    if len(channels) == 3:
        channels.append(1.0)
    return tuple(channels)


def rgba_to_hex(red, green, blue, alpha=1.0, include_alpha=False):
    """Channels from 0 to 1 -> '#RRGGBB', or '#RRGGBBAA' when include_alpha."""
    channels = [red, green, blue] + ([alpha] if include_alpha else [])
    return '#' + ''.join('%02X' % int(round(max(0.0, min(1.0, channel)) * 255))
                         for channel in channels)


# --- Internals ----------------------------------------------------------------
SCALAR_TYPES = (bool, int, float, str)
KEY_TYPES = (str, int)


def _plain_value(node):
    """(True, value) when node is a plain number, bool or string literal, else (False, None)."""
    try:
        value = ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
        return False, None
    return type(value) in SCALAR_TYPES, value


def _scalar_items(value_node):
    """[(label, item node, value)] for a non-empty list, tuple or dict of plain
    values, else None. The label goes between the brackets of the item's
    name: an index for lists and tuples, the key's repr for dicts.
    """
    if isinstance(value_node, (ast.List, ast.Tuple)):
        items = []
        for index, item_node in enumerate(value_node.elts):
            plain, value = _plain_value(item_node)
            if not plain:
                return None
            items.append((str(index), item_node, value))
        return items or None
    if isinstance(value_node, ast.Dict):
        by_label = {}      # a repeated key keeps its first place but its last value, as Python does
        for key_node, item_node in zip(value_node.keys, value_node.values):
            if key_node is None:
                return None            # ** unpacking
            plain_key, key = _plain_value(key_node)
            plain, value = _plain_value(item_node)
            if not (plain_key and type(key) in KEY_TYPES and plain):
                return None
            by_label[repr(key)] = (item_node, value)
        return [(label, node, value) for label, (node, value) in by_label.items()] or None
    return None
def _constant_assignment(node):
    """(name, value node) for NAME = value or NAME: type = value, else (None, None)."""
    if isinstance(node, ast.Assign) and len(node.targets) == 1:
        target, value_node = node.targets[0], node.value
    elif isinstance(node, ast.AnnAssign) and node.value is not None:
        target, value_node = node.target, node.value
    else:
        return None, None
    if isinstance(target, ast.Name) and CONSTANT_NAME_PATTERN.match(target.id):
        return target.id, value_node
    return None, None


def _line_start_offsets(lines):
    """Character offset where each line starts; index 0 is line 1."""
    starts = [0]
    for line in lines[:-1]:
        starts.append(starts[-1] + len(line) + 1)
    return starts


def _character_offset(lines, line_starts, lineno, byte_column):
    """Turn ast's (line, UTF-8 byte column) into a character offset.

    ast counts columns in bytes, so an 'é' or an emoji earlier on the line
    would otherwise shift the edit by a few characters.
    """
    line_text = lines[lineno - 1]
    column = len(line_text.encode('utf-8')[:byte_column].decode('utf-8'))
    return line_starts[lineno - 1] + column


def _is_rule_comment(line):
    """True for a comment made only of = or - characters, like '# ======'."""
    text = line.strip()
    if not text.startswith('#'):
        return False
    body = text.lstrip('#').strip()
    return len(body) >= 3 and set(body) <= set('=-')


def _section_titles(lines):
    """Map line number -> title for banner comments such as

        # ======
        # Editable appearance
        # ======

    A title is a non-rule comment line directly under a rule line.
    """
    titles = {}
    for index in range(1, len(lines)):
        if not _is_rule_comment(lines[index - 1]):
            continue
        text = lines[index].strip()
        if text.startswith('#') and not _is_rule_comment(text):
            title = text.lstrip('#').strip()
            if title:
                titles[index + 1] = title
    return titles


def _section_for_line(section_titles, lineno):
    """The nearest banner title above a line, or ''."""
    above = [line for line in section_titles if line < lineno]
    return section_titles[max(above)] if above else ''


def _format_decimal(value, original_text):
    """Format a float with the original's decimal places, between 2 and 4."""
    decimals = 2
    if '.' in original_text:
        decimals = min(4, max(2, len(original_text.split('.')[1].strip())))
    text = ('%.*f' % (decimals, value)).rstrip('0')
    if text.endswith('.'):
        text += '0'
    return text


def _format_string(value, original_text):
    """Quote value with the original quote character when that stays a plain literal."""
    quote_character = original_text[:1]
    if quote_character not in ('"', "'") or original_text[:3] in ('"""', "'''"):
        return repr(value)
    escaped = value.replace('\\', '\\\\').replace(quote_character, '\\' + quote_character)
    escaped = escaped.replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
    return quote_character + escaped + quote_character


def _match_hex_case(new_hex, old_hex):
    """'#1e90ff' becomes '#1E90FF' when the old colour used capitals, and the reverse."""
    digits = old_hex[1:]
    if digits.upper() == digits and digits.lower() != digits:
        return new_hex.upper()
    if digits.lower() == digits and digits.upper() != digits:
        return new_hex.lower()
    return new_hex