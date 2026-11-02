"""Editor Deck: open the tool panel in Pythonista's console.

Run this with the play button, or add it to the editor's wrench menu so
the deck is one tap away from any script. The deck docks in the console
and stays there while you work; its ✕ closes it.

Running it again re-docks a fresh deck, picking up any update.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

# Drop cached deck modules so an update takes effect without restarting.
for module_name in list(sys.modules):
    if module_name == 'editor_deck' or module_name.startswith('editor_deck.'):
        del sys.modules[module_name]

import editor_deck

if editor_deck.show_deck():
    print('Editor Deck is open in the console.')