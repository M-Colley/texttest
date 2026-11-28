import importlib
import sys
import unittest
from unittest import mock


class TestIssue76(unittest.TestCase):
    def _load_adminactions(self):
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

        return importlib.import_module("texttestlib.default.gtkgui.default_gui.adminactions")

    def _make_import_files(self, adminactions, tmp_dir="/tmp/test1"):
        input_options = mock.MagicMock()
        input_options.rootDirectories = [tmp_dir]
        dialog = adminactions.ImportFiles([], False, input_options)
        dialog.setSensitivity = mock.MagicMock()

        app = mock.MagicMock()
        app.name = "myapp"
        app.getStdinName.return_value = "input"
        app.getStdoutName.return_value = "output"
        app.getStderrName.return_value = "errors"
        app.getConfigValue.side_effect = lambda key: {"collate_file": {}, "discard_file": []}.get(key, {})

        test = mock.MagicMock()
        test.app = app
        test.classId.return_value = "test-case"
        test.getDirectory.return_value = tmp_dir
        test.getAllPathNames.return_value = []
        test.getDataFileNames.return_value = ["my_data.xml", "input_dir"]
        test.expandedDefFileStems.return_value = ["testcustomize.py"]
        test.getConfigValue.side_effect = lambda key: {
            "interpreters": {},
            "use_case_record_mode": "disabled",
            "filename_convention_scheme": "classic",
        }[key]

        dialog.currTestSelection = [test]
        return dialog

    def test_combined_stems_order_and_append_app_name_switching(self):
        adminactions = self._load_adminactions()
        dialog = self._make_import_files(adminactions)

        # Opened from Definition Files: definition stems first, followed by data files
        dialog.notifyFileCreationInfo("/tmp/test1", "definition")
        stem_opt = dialog.optionGroup.getOption("stem")
        self.assertEqual(
            stem_opt.possibleValues,
            ["environment", "config", "options", "input", "testcustomize.py", "my_data.xml", "input_dir"],
        )
        self.assertEqual(stem_opt.getValue(), "environment")
        self.assertTrue(dialog.appendAppName)
        self.assertEqual(dialog.optionGroup.getSwitchValue("act"), 1)

        # Switching to a data file stem clears appendAppName and selects copy/import action
        dialog.optionGroup.setValue("stem", "my_data.xml")
        dialog.stemChanged()
        self.assertFalse(dialog.appendAppName)
        self.assertEqual(dialog.optionGroup.getSwitchValue("act"), 0)

        # Switching to testcustomize.py also keeps appendAppName False
        dialog.optionGroup.setValue("stem", "testcustomize.py")
        dialog.stemChanged()
        self.assertFalse(dialog.appendAppName)

        # Opened from Data Files: data stems first, followed by definition files
        dialog.notifyFileCreationInfo("/tmp/test1", "data")
        self.assertEqual(
            stem_opt.possibleValues,
            ["my_data.xml", "input_dir", "environment", "config", "options", "input", "testcustomize.py"],
        )
        self.assertEqual(stem_opt.getValue(), "my_data.xml")
        self.assertFalse(dialog.appendAppName)
        self.assertEqual(dialog.optionGroup.getSwitchValue("act"), 0)

        # Switching to a definition stem from Data Files enables appendAppName
        dialog.optionGroup.setValue("stem", "options")
        dialog.stemChanged()
        self.assertTrue(dialog.appendAppName)
        self.assertEqual(dialog.optionGroup.getSwitchValue("act"), 1)

        # Approved files remain separate and always append app name
        dialog.notifyFileCreationInfo("/tmp/test1", "approved")
        self.assertEqual(stem_opt.possibleValues, ["output", "errors"])
        self.assertTrue(dialog.appendAppName)


if __name__ == "__main__":
    unittest.main()
