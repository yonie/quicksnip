import importlib
import os
import sys
import unittest

os.environ["GDK_BACKEND"] = "broadway"


class TestVersion(unittest.TestCase):
    def test_version_is_set(self):
        module = importlib.import_module("quicksnip")
        self.assertEqual(module.VERSION, "1.0.2")

    def test_max_undo_steps(self):
        module = importlib.import_module("quicksnip")
        self.assertEqual(module.MAX_UNDO_STEPS, 20)


class TestMainFunction(unittest.TestCase):
    def test_main_exists(self):
        module = importlib.import_module("quicksnip")
        self.assertTrue(callable(getattr(module, "main", None)))


class TestPaintAppClass(unittest.TestCase):
    def test_class_exists(self):
        module = importlib.import_module("quicksnip")
        self.assertTrue(hasattr(module, "PaintApp"))

    def test_has_expected_methods(self):
        module = importlib.import_module("quicksnip")
        methods = [
            "save_undo_state",
            "undo",
            "on_key_press",
            "on_configure",
            "show_toast",
            "hide_toast",
            "show_help",
            "center_image",
            "fit_to_window",
            "update_zoomed_surface",
            "on_scroll",
            "load_from_file",
            "paste_image",
            "on_draw",
            "on_button_press",
            "on_motion",
            "on_button_release",
            "clear_canvas",
            "save_image",
            "copy_image",
        ]
        for method in methods:
            self.assertTrue(
                hasattr(module.PaintApp, method), f"PaintApp missing method: {method}"
            )

    def test_load_initial_file_returns_source_remove(self):
        module = importlib.import_module("quicksnip")
        self.assertEqual(module.GLib.SOURCE_REMOVE, 0)


if __name__ == "__main__":
    unittest.main()
