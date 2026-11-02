"""Editor Deck: a paged tool panel docked in Pythonista's console.

    import editor_deck
    editor_deck.show_deck()     # dock (or re-dock) the deck
    editor_deck.close_deck()    # remove it
"""
from .shell import show_deck, close_deck