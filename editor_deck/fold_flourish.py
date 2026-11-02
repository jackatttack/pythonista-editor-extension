"""The fold flourish: the deck unfolds out of its corner square as paper
when it opens, and folds back into it when minimised.

Borrowed from Maths Games: boardkit/folds.py plans and shapes the sheets
and boardkit/fold_layer.py plays them. Releases bundle those two files in
editor_deck/boardkit; in development, deck_lab.py puts the Maths Games
project on the import path instead, so the animation keeps one home.
When neither is there, available() is False and the deck falls back to
a plain fade.

The paper sits under the panel. Opening: sheets unfold from the corner
until the panel's area is covered, then the panel fades in over them.
Minimising: the panel fades out to blank paper, then the sheets lift off
back into the corner (the corner piece last), then the square appears.
"""
import random
import time

import ui

# --- Editable feel ----------------------------------------------------------
PIECE_SIZE = 80                 # points per paper square, roughly
SHEET_SECONDS = 0.24            # one sheet's turn, before speed-up
SPREAD_SECONDS = 0.42           # the last sheet starts by about then...
MIN_SPEED = 0.15                # ...unless that needs more speed-up than this allows
HANDOFF = (0.55, 0.55)          # equal ends: a clean diagonal wave; spread them to wander
PAPER_COLOUR = '#15171e'        # settled paper: matches the panel, so hand-over is seamless
SHEET_COLOUR = '#1d2029'        # a sheet in motion, a touch lighter than settled paper
SHEET_EDGE_COLOUR = '#2b2f3a'   # thin outline on moving sheets, so the turn reads
SHEET_EDGE_WIDTH = 1.0
BLEED = 0.5                     # overlap between squares so no seams show
CLEAR = (0, 0, 0, 0)            # see-through: None is not transparent on a docked view


def _load_boardkit():
    """(folds module, FoldLayer class): the copy bundled in a release
    (editor_deck/boardkit), else a boardkit on the import path; or
    (None, None) to fall back to a fade."""
    try:
        from .boardkit import folds as fold_engine
        from .boardkit.fold_layer import FoldLayer as base_layer
        return fold_engine, base_layer
    except ImportError:
        pass
    try:
        from boardkit import folds as fold_engine
        from boardkit.fold_layer import FoldLayer as base_layer
        return fold_engine, base_layer
    except Exception as error:
        print('Editor Deck: fold flourish off, using a fade (%r)' % (error,))
        return None, None


folds, FoldLayer = _load_boardkit()


def available():
    return folds is not None


if FoldLayer is not None:
    class DockedFoldLayer(FoldLayer):
        """boardkit's FoldLayer, for a view docked in the console.

        A docked view's Python superview is None (see the
        pythonista-console-docking guide), so FoldLayer's own update()
        would idle forever there. Check the native superview instead.
        """

        def update(self):
            if self.objc_instance.superview() is None or self.show is None:
                return
            if self.show.done(time.time()):
                self.finish()
                return
            self.set_needs_display()
else:
    DockedFoldLayer = None


def shaded(colour, shade):
    red, green, blue, alpha = ui.parse_color(colour)
    return (red * shade, green * shade, blue * shade, alpha)


class PaperShow:
    """Paper unfolding out of, or folding back into, the bottom-right square.

    width, height  the area to cover, in the paper layer's own coordinates
    folding_up     False: unfold from the corner over the area (opening)
                   True: lift off the area back into the corner (minimising)
    start          when the first sheet moves, in time.time() seconds
    on_finished    called once when the show ends or a tap skips it
    """

    def __init__(self, width, height, folding_up, start, on_finished=None, rng=None):
        columns = max(2, int(round(width / float(PIECE_SIZE))))
        rows = max(2, int(round(height / float(PIECE_SIZE))))
        self.pieces = folds.SquarePieces((0, 0, width, height), rows, columns, bleed=BLEED)
        self.corner = (rows - 1, columns - 1)
        self.folding_up = folding_up
        self.on_finished = on_finished

        offsets, parents, seconds = folds.scatter(
            self.pieces.neighbours, set(self.pieces.pieces()), [self.corner],
            rng or random.Random(), fold_seconds=SHEET_SECONDS, handoff=HANDOFF,
            spread_seconds=SPREAD_SECONDS, min_speed=MIN_SPEED)
        self.folds = folds.plan(offsets, parents, seconds, start, reverse=folding_up)
        self.end = max(fold.start + fold.seconds for fold in self.folds)

    # --- the show contract (boardkit FoldLayer) -------------------------------
    def done(self, now):
        return now >= self.end

    def draw(self, now):
        moving = []
        ui.set_color(PAPER_COLOUR)
        for fold in self.folds:
            corners = self.pieces.corners(fold.piece)
            if self.is_covered(fold, now):
                (left, top), _, (right, bottom), _ = corners
                ui.Path.rect(left, top, right - left, bottom - top).fill()
                continue
            drawn = folds.shape(fold, corners, self.hinge(fold), now)
            if drawn is not None:
                moving.append(drawn)
        for points, shade, turn_amount in moving:
            path = ui.Path()
            path.move_to(*points[0])
            for point in points[1:]:
                path.line_to(*point)
            path.close()
            ui.set_color(shaded(SHEET_COLOUR, shade))
            path.fill()
            path.line_width = SHEET_EDGE_WIDTH
            ui.set_color(SHEET_EDGE_COLOUR)
            path.stroke()

    def finished(self):
        callback, self.on_finished = self.on_finished, None
        if callback is not None:
            callback()

    # --- helpers --------------------------------------------------------------
    def is_covered(self, fold, now):
        """Whether this piece shows settled paper at now.

        Unfolding, a piece is covered once its sheet has landed. Folding up,
        it stays covered until its sheet starts to lift.
        """
        if self.folding_up:
            return now < fold.start
        return folds.done(fold, now)

    def hinge(self, fold):
        if fold.parent is None:
            return None
        return self.pieces.hinge(fold.piece, fold.parent)