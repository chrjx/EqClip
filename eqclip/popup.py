"""A small floating window that shows the transcribed Markdown + LaTeX.

Built directly on AppKit (NSPanel/NSTextView) rather than Tkinter because
rumps already runs its own NSApplication event loop -- mixing in Tkinter's
separate mainloop on the same process is a common source of hangs/crashes,
whereas plain AppKit windows share rumps' run loop for free.
"""

import objc
from AppKit import (
    NSApp,
    NSBackingStoreBuffered,
    NSButton,
    NSFloatingWindowLevel,
    NSFont,
    NSMakeRect,
    NSPanel,
    NSPasteboard,
    NSPasteboardTypeString,
    NSScrollView,
    NSTextView,
    NSViewHeightSizable,
    NSViewWidthSizable,
    NSWindowStyleMaskClosable,
    NSWindowStyleMaskMiniaturizable,
    NSWindowStyleMaskResizable,
    NSWindowStyleMaskTitled,
)
from Foundation import NSObject

# Keep hard references so the windows and their button targets aren't
# garbage-collected while still on screen. NSPanel instances don't support
# arbitrary Python attribute assignment, so pair (panel, target) tuples
# here instead of stashing the target on the panel itself.
_open_windows = []


class _ButtonTarget(NSObject):
    def initWithText_window_(self, text, window):
        self = objc.super(_ButtonTarget, self).init()
        if self is None:
            return None
        self._text = text
        self._window = window
        return self

    def copyText_(self, sender):
        pb = NSPasteboard.generalPasteboard()
        pb.clearContents()
        pb.setString_forType_(self._text, NSPasteboardTypeString)
        sender.setTitle_("Copied ✓")

    def closeWindow_(self, sender):
        self._window.close()
        _open_windows[:] = [
            pair for pair in _open_windows if pair[0] is not self._window
        ]


def show_transcript_window(title, text):
    width, height = 640, 480
    rect = NSMakeRect(200, 200, width, height)
    style = (
        NSWindowStyleMaskTitled
        | NSWindowStyleMaskClosable
        | NSWindowStyleMaskResizable
        | NSWindowStyleMaskMiniaturizable
    )
    panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
        rect, style, NSBackingStoreBuffered, False
    )
    panel.setTitle_(title)
    panel.setLevel_(NSFloatingWindowLevel)
    panel.setReleasedWhenClosed_(False)

    content = panel.contentView()
    button_bar_height = 40

    scroll_rect = NSMakeRect(0, button_bar_height, width, height - button_bar_height)
    scroll = NSScrollView.alloc().initWithFrame_(scroll_rect)
    scroll.setHasVerticalScroller_(True)
    scroll.setAutoresizingMask_(NSViewWidthSizable | NSViewHeightSizable)

    text_view = NSTextView.alloc().initWithFrame_(scroll.contentView().bounds())
    text_view.setEditable_(False)
    text_view.setSelectable_(True)
    mono = NSFont.fontWithName_size_("Menlo", 12) or NSFont.systemFontOfSize_(12)
    text_view.setFont_(mono)
    text_view.setString_(text)
    text_view.setVerticallyResizable_(True)
    text_view.setHorizontallyResizable_(False)
    text_view.setAutoresizingMask_(NSViewWidthSizable)

    scroll.setDocumentView_(text_view)
    content.addSubview_(scroll)

    target = _ButtonTarget.alloc().initWithText_window_(text, panel)

    copy_button = NSButton.alloc().initWithFrame_(NSMakeRect(10, 5, 150, 30))
    copy_button.setTitle_("Copy to Clipboard")
    copy_button.setBezelStyle_(1)
    copy_button.setTarget_(target)
    copy_button.setAction_("copyText:")
    content.addSubview_(copy_button)

    close_button = NSButton.alloc().initWithFrame_(NSMakeRect(width - 90, 5, 80, 30))
    close_button.setTitle_("Close")
    close_button.setBezelStyle_(1)
    close_button.setTarget_(target)
    close_button.setAction_("closeWindow:")
    content.addSubview_(close_button)

    # Prevent GC of the target/panel for as long as the window is open.
    _open_windows.append((panel, target))

    panel.makeKeyAndOrderFront_(None)
    NSApp.activateIgnoringOtherApps_(True)
