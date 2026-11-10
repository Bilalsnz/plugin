"""Tests for PatchReview's native Hermes approval hook."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("patchreview_under_test", ROOT / "__init__.py")
PLUGIN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PLUGIN)


class FakeContext:
    def __init__(self):
        self.tools = {}
        self.hooks = {}

    def register_tool(self, name, toolset, schema, handler):
        self.tools[name] = handler

    def register_hook(self, name, handler):
        self.hooks[name] = handler


class PatchReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.ctx = FakeContext()
        PLUGIN.register(self.ctx)
        self.hook = self.ctx.hooks["pre_tool_call"]

    def tearDown(self):
        self.temp.cleanup()

    def test_write_uses_native_approval_and_registers_no_model_tools(self):
        target = self.root / "new.txt"
        result = self.hook("write_file", {"path": str(target), "content": "hello"})
        self.assertEqual(result["action"], "approve")
        self.assertIn("Hermes will execute the original", result["message"])
        self.assertFalse(target.exists())
        self.assertEqual(self.ctx.tools, {})

    def test_replace_preview_preserves_unmodified_file_content(self):
        target = self.root / "patch.txt"
        target.write_text("first\nkeep this line\nlast\n", encoding="utf-8")
        result = self.hook("str_replace", {
            "path": str(target), "old_string": "keep this line",
            "new_string": "changed line",
        })
        self.assertEqual(result["action"], "approve")
        self.assertIn("-keep this line", result["message"])
        self.assertIn("+changed line", result["message"])
        self.assertIn("last", result["message"])
        self.assertEqual(target.read_text(encoding="utf-8"), "first\nkeep this line\nlast\n")

    def test_replace_all_is_reflected_in_preview(self):
        target = self.root / "many.txt"
        target.write_text("x\ny\nx\n", encoding="utf-8")
        result = self.hook("str_replace", {
            "path": str(target), "old_string": "x", "new_string": "z",
            "replace_all": True,
        })
        self.assertEqual(result["action"], "approve")
        self.assertEqual(result["message"].count("+z"), 2)

    def test_unparseable_write_is_blocked(self):
        result = self.hook("write_file", {"path": str(self.root / "bad.txt")})
        self.assertEqual(result["action"], "block")

    def test_unrelated_tool_is_ignored(self):
        self.assertIsNone(self.hook("read_file", {"path": "x"}))

    def test_unsupported_patch_payload_is_blocked(self):
        result = self.hook("apply_patch", {"patch": "*** Begin Patch"})
        self.assertEqual(result["action"], "block")


if __name__ == "__main__":
    unittest.main()
