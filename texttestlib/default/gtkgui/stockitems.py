from gi.repository import Gtk, Gdk
from . import iconnames

# We register our own stock items here, so that dialog buttons can use them.
# The icons are looked up by their themed names, as the legacy GTK stock icons
# are no longer shipped by current icon themes.


def register(window):
    # needs review, StockItems are deprecated MB 2018-12-05
    loadItem = Gtk.StockItem()
    loadItem.stock_id = 'texttest-stock-load'
    loadItem.label = '_Load'
    loadItem.modifier = Gdk.ModifierType.CONTROL_MASK
    loadItem.keyval = Gdk.keyval_from_name('L')
    creditsItem = Gtk.StockItem()
    creditsItem.stock_id = 'texttest-stock-credits'
    creditsItem.label = 'C_redits'

    # We're too lazy to make our own icons,
    # so we use regular themed icons.
    aliases = [('texttest-stock-load', 'gtk-open'),
               ('texttest-stock-credits', 'gtk-about')]

    Gtk.stock_add([loadItem, creditsItem])
    factory = Gtk.IconFactory()
    factory.add_default()
    for new_stock, alias in aliases:
        source = Gtk.IconSource()
        source.set_icon_name(iconnames.getIconName(alias))
        icon_set = Gtk.IconSet()
        icon_set.add_source(source)
        factory.add(new_stock, icon_set)
