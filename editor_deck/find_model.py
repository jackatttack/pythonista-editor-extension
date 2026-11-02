"""Find & Replace for the Editor Deck, as pure Python.

No ui, no editor: it runs anywhere (Pythonista, PythonIDE, desktop) and the
smoke test checks it headless. Offsets are Python character indices; the
page converts them to the editor's UTF-16 positions through editor_bridge.

Searches are plain text, not regex: the query is escaped, and the
replacement is inserted exactly as typed (backslashes included).
"""
import bisect
import re

MAX_MATCHES = 500       # matches listed; count_matches still counts them all


class Match:
    """One match: start and end offsets, plus where it sits for the list."""

    def __init__(self, start, end, line_number, line_text, column):
        self.start = start
        self.end = end
        self.line_number = line_number
        self.line_text = line_text
        self.column = column

    def __repr__(self):
        return 'Match(%d, %d, line %d)' % (self.start, self.end, self.line_number)


def pattern_for(query, match_case=False, whole_word=False):
    """The compiled search for query, or None for an empty query.

    Whole word means no word character directly before or after, so it
    also behaves for queries that start or end with punctuation.
    """
    if not query:
        return None
    body = re.escape(query)
    if whole_word:
        body = r'(?<!\w)%s(?!\w)' % body
    return re.compile(body, 0 if match_case else re.IGNORECASE)


def line_start_offsets(text):
    """Offset where each line starts; index 0 is line 1."""
    starts = [0]
    position = text.find('\n')
    while position >= 0:
        starts.append(position + 1)
        position = text.find('\n', position + 1)
    return starts


def find_matches(text, query, match_case=False, whole_word=False, limit=MAX_MATCHES):
    """Up to limit Matches for query in text, in order."""
    pattern = pattern_for(query, match_case, whole_word)
    if pattern is None:
        return []
    starts = line_start_offsets(text)
    matches = []
    for found in pattern.finditer(text):
        line_index = bisect.bisect_right(starts, found.start()) - 1
        line_start = starts[line_index]
        line_end = text.find('\n', line_start)
        if line_end < 0:
            line_end = len(text)
        matches.append(Match(found.start(), found.end(), line_index + 1,
                             text[line_start:line_end], found.start() - line_start))
        if len(matches) >= limit:
            break
    return matches


def count_matches(text, query, match_case=False, whole_word=False):
    pattern = pattern_for(query, match_case, whole_word)
    return 0 if pattern is None else sum(1 for _ in pattern.finditer(text))


def replace_all(text, query, replacement, match_case=False, whole_word=False):
    """(new text, number replaced). The replacement is used literally."""
    pattern = pattern_for(query, match_case, whole_word)
    if pattern is None:
        return text, 0
    return pattern.subn(lambda found: replacement, text)


def index_at_or_after(matches, position):
    """Index of the first match starting at or after position, wrapping to 0."""
    for index, match in enumerate(matches):
        if match.start >= position:
            return index
    return 0