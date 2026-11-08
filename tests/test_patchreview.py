"""Behavioral tests for PatchReview's pre-tool-call guard and review tools."""
import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

DATA_ROOT = None

# Stub Hermes' storage import so tests run without installing Hermes.
plugins = types.ModuleType("plugins")
storage = types.ModuleType("plugins.plugin_storage")
storage.plugin_data_dir = lambda _name: str(DATA_ROOT)
plugins.plugin_storage = storage
sys.modules.setdefault("plugins", plugins)
sys.modules["plugins.plugin_storage"] = storage

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
        global DATA_ROOT
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        DATA_ROOT = self.root / "plugin-data"
        self.ctx = FakeContext()
        PLUGIN.register(self.ctx)
        self.hook = self.ctx.hooks["pre_tool_call"]

    def tearDown(self):
        self.temp.cleanup()

    def stage_write(self, path, content):
        return self.hook("write_file", {"path": str(path), "content": content})

    def proposals(self, status="all"):
        return json.loads(self.ctx.tools["patchreview_list"]({"status": status}))["proposals"]

    def test_write_is_blocked_and_staged_before_disk_change(self):
        target = self.root / "new.txt"
        result = self.stage_write(target, "hello")
        self.assertEqual(result["action"], "block")
        self.assertFalse(target.exists())
        self.assertEqual(len(self.proposals()), 1)

    def test_unparseable_recognized_write_fails_closed(self):
        result = self.hook("write_file", {"path": str(self.root / "unknown.txt")})
        self.assertEqual(result["action"], "block")
        self.assertFalse((self.root / "unknown.txt").exists())
        self.assertEqual(self.proposals(), [])

    def test_empty_string_is_valid_file_content(self):
        target = self.root / "empty.txt"
        result = self.stage_write(target, "")
        self.assertEqual(result["action"], "block")
        self.assertEqual(len(self.proposals()), 1)

    def test_opaque_patch_payload_fails_closed(self):
        result = self.hook("apply_patch", {"patch": "*** Begin Patch"})
        self.assertEqual(result["action"], "block")

    def test_string_replace_requires_existing_exact_match(self):
        target = self.root / "replace.txt"
        target.write_text("alpha", encoding="utf-8")
        result = self.hook("str_replace", {
            "path": str(target), "old_string": "missing", "new_string": "beta"
        })
        self.assertEqual(result["action"], "block")
        self.assertEqual(target.read_text(encoding="utf-8"), "alpha")
        self.assertEqual(self.proposals(), [])

    def test_symbolic_link_target_is_blocked(self):
        real = self.root / "real.txt"
        real.write_text("safe", encoding="utf-8")
        link = self.root / "link.txt"
        link.symlink_to(real)
        result = self.stage_write(link, "changed")
        self.assertEqual(result["action"], "block")
        self.assertEqual(real.read_text(encoding="utf-8"), "safe")
        self.assertEqual(self.proposals(), [])

    def test_unrelated_tool_name_is_not_intercepted(self):
        self.assertIsNone(self.hook("patchreview_accept", {"id": "abc"}))

    def test_accept_applies_staged_content(self):
        target = self.root / "accepted.txt"
        self.stage_write(target, "approved")
        proposal_id = self.proposals("pending")[0]["id"]
        result = json.loads(self.ctx.tools["patchreview_accept"]({"id": proposal_id}))
        self.assertTrue(result["success"])
        self.assertEqual(target.read_text(encoding="utf-8"), "approved")

    def test_accept_refuses_stale_file(self):
        target = self.root / "stale.txt"
        target.write_text("before", encoding="utf-8")
        self.stage_write(target, "proposed")
        proposal_id = self.proposals("pending")[0]["id"]
        target.write_text("changed elsewhere", encoding="utf-8")
        result = json.loads(self.ctx.tools["patchreview_accept"]({"id": proposal_id}))
        self.assertFalse(result["success"])
        self.assertEqual(target.read_text(encoding="utf-8"), "changed elsewhere")

    def test_reject_does_not_write_file(self):
        target = self.root / "rejected.txt"
        self.stage_write(target, "never write")
        proposal_id = self.proposals("pending")[0]["id"]
        result = json.loads(self.ctx.tools["patchreview_reject"]({"id": proposal_id}))
        self.assertTrue(result["success"])
        self.assertFalse(target.exists())

    def test_accept_distinguishes_missing_file_from_empty_file(self):
        target = self.root / "empty-created-after-stage.txt"
        self.stage_write(target, "content")
        proposal_id = self.proposals("pending")[0]["id"]
        target.write_text("", encoding="utf-8")
        result = json.loads(self.ctx.tools["patchreview_accept"]({"id": proposal_id}))
        self.assertFalse(result["success"])
        self.assertEqual(target.read_text(encoding="utf-8"), "")


if __name__ == "__main__":
    unittest.main()
