"""Pure layout maths for the Editor Deck.

No ui and no objc_util, so it runs anywhere (Pythonista, PythonIDE,
desktop) and the smoke test can check it headless. Frames are
(x, y, width, height) tuples in the console container's coordinates.
"""

SQUARE_SIZE = 48         # the minimised deck, and the minimise button
CORNER_INSET = 8         # gap between that square and the panel's corner
MINIMUM_PANEL_HEIGHT = 120


def panel_frame(console_frame, side_margin, top_margin, bottom_clearance):
    """The expanded deck's frame: the console, inset on every side.

    bottom_clearance keeps the console's input bar uncovered.
    """
    x, y, width, height = console_frame
    panel_height = max(height - top_margin - bottom_clearance, MINIMUM_PANEL_HEIGHT)
    return (x + side_margin, y + top_margin, width - 2 * side_margin, panel_height)


def corner_square_origin(panel, size=SQUARE_SIZE, inset=CORNER_INSET):
    """Origin of the square in the panel's bottom-right corner.

    The minimise button and the minimised square share this spot, so
    opening and closing the deck is one tap in one place.
    """
    x, y, width, height = panel
    return (x + width - size - inset, y + height - size - inset)