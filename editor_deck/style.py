"""The Editor Deck's shared look, used by the shell and every page."""
from . import fold_flourish

COLOURS = {
    'panel': fold_flourish.PAPER_COLOUR,   # the panel is the settled fold paper
    'border': '#2b2f3a',
    'text': '#e8e8ee',
    'muted': '#8a8fa0',
    'accent': '#ff6fae',
    'button': '#22252e',
    'card': '#1c1f27',
    'help': '#1a2430',       # tiles while help mode is on
    'warn': '#ffb454',
    'danger': '#ff5c6c',
}
FONT = 'Menlo'
BOLD = 'Menlo-Bold'