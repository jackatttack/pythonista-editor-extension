"""Getting the keyboard out of the way. Pythonista only.

dismiss() ends editing in every window, so it also closes the keyboard the
editor opened, not just the deck's own text fields. The deck calls it on
any tap that is not on a text field, when a list starts being dragged, and
when the console slides into view.
"""
from objc_util import ObjCClass, on_main_thread


@on_main_thread
def dismiss():
    app = ObjCClass('UIApplication').sharedApplication()
    for window in app.windows():
        window.endEditing_(True)


class DismissOnDrag:
    """ScrollView delegate: a finger dragging the list closes the keyboard.

    Checks dragging, so the list scrolling itself (to show a match) while
    you type does not close it.
    """

    def scrollview_did_scroll(self, scrollview):
        if scrollview.dragging:
            dismiss()