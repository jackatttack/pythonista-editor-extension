# Editor Deck

A tool panel for Pythonista that lives in the console. Swipe across to the
console and the deck is there, working on the script you have open: quick
file tools, find and replace, a constants tuner and saved snippets, one tap
each. For anyone writing Python on an iPhone or iPad who is tired of the
long way round.

## Install

Paste this into a new script in Pythonista and run it:

    import urllib.request
    url = ('https://raw.githubusercontent.com/'
           'jackatttack/pythonista-editor-extension/main/install.py')
    source = urllib.request.urlopen(url).read()
    exec(compile(source, 'install.py', 'exec'), {'__name__': '__main__'})

It installs everything into `Documents/Editor Deck/` and opens the launcher.
Run the same snippet again any time to update; your snippets are kept.

## Open the deck

Run `Editor Deck/launch_editor_deck.py`. The deck docks in the console and
stays there after the script finishes, while you edit any other script.

Tip: add `launch_editor_deck.py` to Pythonista's wrench menu, so the deck is
one tap away from whatever you are editing. (This is a manual step.)

## The pages

**Quick** — two-column tools for the open script:
copy the script, its path, or a `pythonista3://` run or open link; a fresh
scratch pad beside it; rename; duplicate; replace or append from the
clipboard; clear and delete (each needs a second tap). Tools that change or
open a script slide the console away, so you land on the result.

**Find** — type to see every match with its line number, live. Match case
and whole word, Next, Replace and Replace All. Plain text: brackets and dots
match literally and the replacement goes in exactly as typed. Tap a match
to jump to it.

**Constants** — tune the open script's top-level settings without hunting
through the code. Every `UPPER_CASE` name set to a plain value gets a
control: a switch for True/False, a slider for numbers, a colour picker for
`'#RRGGBB'` strings and a field for text. Lists, tuples and dicts of plain
values open up item by item. Changes are written into the script straight
away and sit in the editor's undo history.

    TILE_SIZE = 64          # range: 16-128   <- sets the slider's range
    ACCENT = '#FF6FAE'      # colour picker
    SHOW_GRID = True        # switch
    SPEEDS = [0.5, 1.0, 2]  # three sliders, SPEEDS[0] to SPEEDS[2]

**Snippets** — keep title-and-value pairs, saved from the clipboard or typed
out. Tap one to copy it and go straight back to your script to paste.

Around the pages: chips for every open tab (tap to switch), **?** for help
mode (every control explains itself instead of running), **▾** to fold the
deck into a small square in the corner (tap it to unfold), and **✕** to
close.

## Notes

- Built for Pythonista 3 on iPhone and iPad. Docking in the console,
  renaming and closing tabs use Pythonista internals through `objc_util`;
  a future Pythonista update could change them.
- Delete removes the file for good. There is no bin.
- Snippets live in `Editor Deck/data/snippets.json`.
- The paper fold animation comes from boardkit in
  [Maths Games](https://github.com/jackatttack/mathsgames).
- Tests: run `tests/smoke_editor_deck.py`.

## Licence

MIT. See LICENSE.