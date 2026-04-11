from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from visual_annotation_mcp.security import assert_file_path_allowed, assert_url_allowed


class SecurityTests(unittest.TestCase):
    def test_url_allowlist_blocks_disallowed_host(self) -> None:
        original = os.environ.get("VISUAL_ANNOTATION_ALLOWED_HOSTS")
        try:
            os.environ["VISUAL_ANNOTATION_ALLOWED_HOSTS"] = "example.com"
            assert_url_allowed("https://example.com/path")
            with self.assertRaises(ValueError):
                assert_url_allowed("https://not-allowed.test/")
        finally:
            if original is None:
                os.environ.pop("VISUAL_ANNOTATION_ALLOWED_HOSTS", None)
            else:
                os.environ["VISUAL_ANNOTATION_ALLOWED_HOSTS"] = original

    def test_file_path_allowlist_rejects_outside_root(self) -> None:
        original = os.environ.get("VISUAL_ANNOTATION_ALLOWED_PATHS")
        try:
            with tempfile.TemporaryDirectory() as root_dir, tempfile.TemporaryDirectory() as outside_dir:
                root = Path(root_dir)
                outside = Path(outside_dir)
                inside_file = root / "allowed.txt"
                outside_file = outside / "blocked.txt"
                inside_file.write_text("ok", encoding="utf-8")
                outside_file.write_text("no", encoding="utf-8")

                os.environ["VISUAL_ANNOTATION_ALLOWED_PATHS"] = str(root)

                resolved_inside = assert_file_path_allowed(str(inside_file))
                self.assertEqual(resolved_inside, inside_file.resolve())

                with self.assertRaises(ValueError):
                    assert_file_path_allowed(str(outside_file))
        finally:
            if original is None:
                os.environ.pop("VISUAL_ANNOTATION_ALLOWED_PATHS", None)
            else:
                os.environ["VISUAL_ANNOTATION_ALLOWED_PATHS"] = original


if __name__ == "__main__":
    unittest.main()
