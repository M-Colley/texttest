
"""
Mapping from the deprecated GTK stock identifiers used throughout the TextTest GUI
to icon names from the freedesktop.org icon naming specification.
GTK themes such as Adwaita no longer ship the legacy "gtk-*" stock icons,
so all icons are looked up by their themed names instead.
"""

# Each stock identifier maps to a tuple of candidate icon names, in order of preference.
# The first candidate available in the current icon theme is used.
stockIconNames = {
    "gtk-about": ("help-about",),
    "gtk-add": ("list-add",),
    "gtk-apply": ("object-select", "emblem-ok"),
    "gtk-cancel": ("process-stop",),
    "gtk-close": ("window-close",),
    "gtk-connect": ("network-transmit-receive", "network-wired"),
    "gtk-convert": ("edit-cut",),
    "gtk-copy": ("edit-copy",),
    "gtk-cut": ("edit-cut",),
    "gtk-delete": ("edit-delete",),
    "gtk-dialog-error": ("dialog-error",),
    "gtk-dialog-info": ("dialog-information",),
    "gtk-dialog-question": ("dialog-question",),
    "gtk-dialog-warning": ("dialog-warning",),
    "gtk-find": ("edit-find",),
    "gtk-go-down": ("go-down",),
    "gtk-go-up": ("go-up",),
    "gtk-goto-bottom": ("go-bottom",),
    "gtk-goto-top": ("go-top",),
    "gtk-index": ("view-list",),
    "gtk-info": ("dialog-information",),
    "gtk-italic": ("format-text-italic",),
    "gtk-media-play": ("media-playback-start",),
    "gtk-media-record": ("media-record",),
    "gtk-new": ("document-new",),
    "gtk-ok": ("object-select", "emblem-ok"),
    "gtk-open": ("document-open",),
    "gtk-paste": ("edit-paste",),
    "gtk-properties": ("document-properties",),
    "gtk-quit": ("application-exit",),
    "gtk-refresh": ("view-refresh",),
    "gtk-revert-to-saved": ("document-revert",),
    "gtk-save": ("document-save",),
    "gtk-save-as": ("document-save-as",),
    "gtk-sort-ascending": ("view-sort-ascending",),
    "gtk-sort-descending": ("view-sort-descending",),
    "gtk-stop": ("process-stop",),
}

symbolicSuffix = "-symbolic"


def getCandidates(stockId):
    candidates = stockIconNames.get(stockId, (stockId,))
    allCandidates = list(candidates)
    for name in candidates:
        if not name.endswith(symbolicSuffix):
            allCandidates.append(name + symbolicSuffix)
    return allCandidates


def getDefaultIconTheme():
    try:
        from gi.repository import Gtk
        return Gtk.IconTheme.get_default()
    except Exception:
        return None


def getIconName(stockId, iconTheme=None):
    """ Return the themed icon name to use for the given (possibly legacy stock) identifier """
    if not stockId:
        return stockId
    candidates = getCandidates(stockId)
    if iconTheme is None:
        iconTheme = getDefaultIconTheme()
    if iconTheme is not None:
        for name in candidates:
            if iconTheme.has_icon(name):
                return name
    return candidates[0]
