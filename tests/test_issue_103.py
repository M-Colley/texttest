import ast
import os
import re
import unittest

from texttestlib.default.gtkgui import iconnames

GTKGUI_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "texttestlib", "default", "gtkgui")


def iterGuiSources():
    for root, _, files in os.walk(GTKGUI_DIR):
        for fileName in files:
            if fileName.endswith(".py"):
                path = os.path.join(root, fileName)
                with open(path, encoding="utf-8") as f:
                    yield path, f.read()


def findStockIdLiterals():
    literals = set()
    for path, source in iterGuiSources():
        tree = ast.parse(source, path)
        clipboardClasses = [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef) and
                            any(getattr(base, "id", None) == "ClipboardAction" for base in node.bases)]
        # ClipboardAction derives its stock ID from getName()
        methods = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "_getStockId"]
        for cls in clipboardClasses:
            methods += [node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == "getName"]
        for node in methods:
            for child in ast.walk(node):
                if isinstance(child, ast.Return) and isinstance(child.value, ast.Constant) and isinstance(child.value.value, str):
                    literals.add(child.value.value)
    return literals


def findDialogStockConstants():
    constants = set()
    for _, source in iterGuiSources():
        constants.update(re.findall(r"Gtk\.STOCK_(DIALOG_[A-Z]+)", source))
    return constants


class FakeIconTheme:
    def __init__(self, names):
        self.names = set(names)

    def has_icon(self, name):
        return name in self.names


class TestIssue103IconNames(unittest.TestCase):
    def test_every_action_stock_id_has_a_themed_icon_name(self):
        literals = findStockIdLiterals()
        self.assertGreater(len(literals), 20)
        self.assertIn("copy", literals)
        unmapped = sorted(lit for lit in literals if "gtk-" + lit not in iconnames.stockIconNames)
        self.assertEqual(unmapped, [])

    def test_every_dialog_stock_constant_has_a_themed_icon_name(self):
        constants = findDialogStockConstants()
        self.assertIn("DIALOG_WARNING", constants)
        for constant in constants:
            stockId = "gtk-" + constant.lower().replace("_", "-")
            self.assertIn(stockId, iconnames.stockIconNames)

    def test_mapped_icon_names_follow_freedesktop_naming(self):
        for stockId, candidates in iconnames.stockIconNames.items():
            self.assertTrue(stockId.startswith("gtk-"))
            for name in candidates:
                self.assertFalse(name.startswith("gtk-"), stockId + " maps to legacy name " + name)

    def test_no_legacy_stock_image_or_renderer_usage_remains(self):
        for path, source in iterGuiSources():
            self.assertNotIn("new_from_stock", source, path)
            self.assertNotIn("'stock_id'", source, path)

    def test_get_icon_name_prefers_first_available_candidate(self):
        theme = FakeIconTheme(["emblem-ok", "object-select"])
        self.assertEqual(iconnames.getIconName("gtk-apply", theme), "object-select")
        theme = FakeIconTheme(["emblem-ok"])
        self.assertEqual(iconnames.getIconName("gtk-apply", theme), "emblem-ok")

    def test_get_icon_name_falls_back_to_symbolic_variant(self):
        theme = FakeIconTheme(["object-select-symbolic"])
        self.assertEqual(iconnames.getIconName("gtk-apply", theme), "object-select-symbolic")
        theme = FakeIconTheme(["document-open-symbolic"])
        self.assertEqual(iconnames.getIconName("gtk-open", theme), "document-open-symbolic")

    def test_get_icon_name_without_matching_theme_entry_uses_first_candidate(self):
        theme = FakeIconTheme([])
        self.assertEqual(iconnames.getIconName("gtk-refresh", theme), "view-refresh")

    def test_get_icon_name_passes_through_unknown_and_empty_names(self):
        theme = FakeIconTheme(["my-custom-icon"])
        self.assertEqual(iconnames.getIconName("my-custom-icon", theme), "my-custom-icon")
        self.assertIsNone(iconnames.getIconName(None, theme))
        self.assertEqual(iconnames.getIconName("", theme), "")


def loadGtk():
    try:
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk
        if Gtk.IconTheme.get_default() is None:
            return None
        return Gtk
    except Exception:
        return None


class TestIssue103WithGtk(unittest.TestCase):
    def setUp(self):
        self.Gtk = loadGtk()
        if self.Gtk is None:
            self.skipTest("GTK 3 with a default display is not available")

    def test_all_mapped_icons_resolve_in_default_theme(self):
        theme = self.Gtk.IconTheme.get_default()
        missing = []
        for stockId in iconnames.stockIconNames:
            name = iconnames.getIconName(stockId)
            if not theme.has_icon(name):
                missing.append((stockId, name))
        self.assertEqual(missing, [])

    def test_actions_and_images_use_icon_names(self):
        action = self.Gtk.Action(name="Approve", label="_Approve", tooltip="Approve tests",
                                 icon_name=iconnames.getIconName("gtk-apply"))
        self.assertIsNone(action.get_stock_id())
        self.assertEqual(action.get_icon_name(), iconnames.getIconName("gtk-apply"))
        image = self.Gtk.Image.new_from_icon_name(iconnames.getIconName("gtk-dialog-warning"), self.Gtk.IconSize.DIALOG)
        self.assertEqual(image.get_storage_type(), self.Gtk.ImageType.ICON_NAME)

    def test_stock_items_register_with_themed_icons(self):
        from texttestlib.default.gtkgui import stockitems
        window = self.Gtk.Window()
        stockitems.register(window)
        iconSet = self.Gtk.IconFactory.lookup_default("texttest-stock-load")
        self.assertIsNotNone(iconSet)
        window.destroy()


if __name__ == "__main__":
    unittest.main()
