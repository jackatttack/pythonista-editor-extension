"""Saved snippets for the Editor Deck: a title and a value each, in one JSON file.

Pure Python (json and os only), so it runs anywhere and the smoke test
checks it headless. The file looks like

    {"version": 1, "snippets": [{"title": "...", "value": "..."}, ...]}

newest first. Saving writes a temporary file and swaps it in, so a crash
mid-save cannot leave a half-written file. A file that cannot be read is
reported, never silently replaced.
"""
import json
import os

TITLE_LENGTH = 40
FILE_VERSION = 1


def default_store_path():
    """data/snippets.json in the folder that holds the editor_deck package."""
    package = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(os.path.dirname(package), 'data', 'snippets.json')


def load(path):
    """(snippets, problem). problem is '' when the file read cleanly or is
    missing (a fresh start), else a sentence saying what went wrong."""
    if not os.path.exists(path):
        return [], ''
    try:
        with open(path, 'r', encoding='utf-8') as handle:
            data = json.load(handle)
        items = data.get('snippets', []) if isinstance(data, dict) else []
    except (ValueError, OSError) as error:
        return [], 'Could not read %s (%s).' % (os.path.basename(path), error)
    snippets = [{'title': item['title'], 'value': item['value']} for item in items
                if isinstance(item, dict) and isinstance(item.get('title'), str)
                and isinstance(item.get('value'), str)]
    return snippets, ''


def save(path, snippets):
    folder = os.path.dirname(path)
    if folder and not os.path.isdir(folder):
        os.makedirs(folder)
    temporary = path + '.tmp'
    with open(temporary, 'w', encoding='utf-8') as handle:
        json.dump({'version': FILE_VERSION, 'snippets': snippets}, handle,
                  ensure_ascii=False, indent=1)
    os.replace(temporary, path)


def suggest_title(value):
    """The first non-blank line of value, shortened to TITLE_LENGTH."""
    for line in (value or '').split('\n'):
        line = line.strip()
        if line:
            return line if len(line) <= TITLE_LENGTH else line[:TITLE_LENGTH - 1] + '…'
    return 'Untitled'


def add(snippets, title, value):
    """A new list with this snippet first. A blank title is suggested from the value."""
    title = (title or '').strip() or suggest_title(value)
    return [{'title': title, 'value': value}] + list(snippets)


def remove(snippets, index):
    return [snippet for position, snippet in enumerate(snippets) if position != index]


def first_line(value):
    """The value's first non-blank line, for a row's preview."""
    for line in (value or '').split('\n'):
        if line.strip():
            return line.strip()
    return ''