import ctypes
import importlib
import sys
import types
import unittest
from unittest import mock


class TestIssue40(unittest.TestCase):
    def _load_guiplugins(self):
        fake_gi = mock.MagicMock()
        fake_gtk = mock.MagicMock()
        fake_gtk.get_major_version.return_value = 3
        fake_gtk.get_minor_version.return_value = 24
        fake_gtk.get_micro_version.return_value = 0
        fake_gobject = mock.MagicMock()
        fake_gdk = mock.MagicMock()
        fake_pango = mock.MagicMock()

        fake_repo = mock.MagicMock()
        fake_repo.Gtk = fake_gtk
        fake_repo.GObject = fake_gobject
        fake_repo.Gdk = fake_gdk
        fake_repo.Pango = fake_pango

        patched = {
            "gi": fake_gi,
            "gi.repository": fake_repo,
            "gi.repository.Gtk": fake_gtk,
            "gi.repository.GObject": fake_gobject,
            "gi.repository.Gdk": fake_gdk,
            "gi.repository.Pango": fake_pango,
        }
        patcher = mock.patch.dict(sys.modules, patched)
        patcher.start()
        self.addCleanup(patcher.stop)

        for mod_name in list(sys.modules):
            if mod_name.startswith("texttestlib.default.gtkgui"):
                sys.modules.pop(mod_name, None)

        guiplugins = importlib.import_module("texttestlib.default.gtkgui.guiplugins")
        return guiplugins, fake_gtk

    def test_windows_mounted_network_drives_added_and_local_only_disabled(self):
        guiplugins, fake_gtk = self._load_guiplugins()
        fake_chooser = mock.MagicMock()
        fake_gtk.FileChooserWidget.new.return_value = fake_chooser

        # Simulate C: (fixed=3), D: (CDROM=5, skipped), Z: (remote network=4)
        bitmask = (1 << 2) | (1 << 3) | (1 << 25)
        drive_types = {"C:\\": 3, "D:\\": 5, "Z:\\": 4}
        fake_kernel32 = types.SimpleNamespace(
            GetLogicalDrives=lambda: bitmask,
            GetDriveTypeW=lambda d: drive_types.get(d, 0),
        )
        fake_windll = types.SimpleNamespace(kernel32=fake_kernel32)

        dialog_gui = object.__new__(guiplugins.ActionDialogGUI)
        dialog_gui.getTooltip = lambda: "Reconnect to previously run tests"
        dialog_gui.set_filename_is_working = lambda: False

        option = mock.MagicMock()
        option.selectFile = False
        option.selectDir = True
        option.saveFile = False
        option.getValue.return_value = ""
        option.getDirectories.return_value = ([r"Z:\nightjob"], "")

        with mock.patch.object(guiplugins.os, "name", "nt"), mock.patch.object(
            ctypes, "windll", fake_windll, create=True
        ):
            drives = dialog_gui.getWindowsDriveFolders()
            self.assertEqual(drives, ["C:\\", "Z:\\"])

            chooser = dialog_gui.createFileChooser(option)

        self.assertIs(chooser, fake_chooser)
        added = [c.args[0] for c in fake_chooser.add_shortcut_folder.call_args_list]
        self.assertEqual(added, [r"Z:\nightjob", "C:\\", "Z:\\"])
        fake_chooser.set_local_only.assert_called_once_with(False)

    def test_posix_file_chooser_keeps_local_only_and_no_windows_drives(self):
        guiplugins, fake_gtk = self._load_guiplugins()
        fake_chooser = mock.MagicMock()
        fake_gtk.FileChooserWidget.new.return_value = fake_chooser

        dialog_gui = object.__new__(guiplugins.ActionDialogGUI)
        dialog_gui.getTooltip = lambda: "Reconnect"
        dialog_gui.set_filename_is_working = lambda: False

        option = mock.MagicMock()
        option.selectFile = False
        option.selectDir = True
        option.saveFile = False
        option.getValue.return_value = ""
        option.getDirectories.return_value = (["/tmp/runs"], "/tmp/runs")

        with mock.patch.object(guiplugins.os, "name", "posix"):
            self.assertEqual(dialog_gui.getWindowsDriveFolders(), [])
            dialog_gui.createFileChooser(option)

        added = [c.args[0] for c in fake_chooser.add_shortcut_folder.call_args_list]
        self.assertEqual(added, ["/tmp/runs"])
        fake_chooser.set_local_only.assert_called_once_with(True)


if __name__ == "__main__":
    unittest.main()
