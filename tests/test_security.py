from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from visual_annotation_mcp.security import assert_file_path_allowed, assert_url_allowed


class SecurityTests(unittest.TestCase):
    def test_url_is_denied_by_default(self) -> None:
        original_hosts = os.environ.get("VISUAL_ANNOTATION_ALLOWED_HOSTS")
        original_unrestricted = os.environ.get("VISUAL_ANNOTATION_ALLOW_UNRESTRICTED")
        try:
            os.environ.pop("VISUAL_ANNOTATION_ALLOWED_HOSTS", None)
            os.environ.pop("VISUAL_ANNOTATION_ALLOW_UNRESTRICTED", None)
            with self.assertRaises(ValueError):
                assert_url_allowed("https://example.com/")
        finally:
            if original_hosts is None:
                os.environ.pop("VISUAL_ANNOTATION_ALLOWED_HOSTS", None)
            else:
                os.environ["VISUAL_ANNOTATION_ALLOWED_HOSTS"] = original_hosts
            if original_unrestricted is None:
                os.environ.pop("VISUAL_ANNOTATION_ALLOW_UNRESTRICTED", None)
            else:
                os.environ["VISUAL_ANNOTATION_ALLOW_UNRESTRICTED"] = original_unrestricted

    def test_url_allowlist_blocks_disallowed_host(self) -> None:
        original_hosts = os.environ.get("VISUAL_ANNOTATION_ALLOWED_HOSTS")
        original_unrestricted = os.environ.get("VISUAL_ANNOTATION_ALLOW_UNRESTRICTED")
        try:
            os.environ["VISUAL_ANNOTATION_ALLOWED_HOSTS"] = "example.com"
            os.environ.pop("VISUAL_ANNOTATION_ALLOW_UNRESTRICTED", None)
            assert_url_allowed("https://example.com/path")
            with self.assertRaises(ValueError):
                assert_url_allowed("https://not-allowed.test/")
        finally:
            if original_hosts is None:
                os.environ.pop("VISUAL_ANNOTATION_ALLOWED_HOSTS", None)
            else:
                os.environ["VISUAL_ANNOTATION_ALLOWED_HOSTS"] = original_hosts
            if original_unrestricted is None:
                os.environ.pop("VISUAL_ANNOTATION_ALLOW_UNRESTRICTED", None)
            else:
                os.environ["VISUAL_ANNOTATION_ALLOW_UNRESTRICTED"] = original_unrestricted

    def test_file_access_is_denied_by_default(self) -> None:
        original_paths = os.environ.get("VISUAL_ANNOTATION_ALLOWED_PATHS")
        original_unrestricted = os.environ.get("VISUAL_ANNOTATION_ALLOW_UNRESTRICTED")
        try:
            os.environ.pop("VISUAL_ANNOTATION_ALLOWED_PATHS", None)
            os.environ.pop("VISUAL_ANNOTATION_ALLOW_UNRESTRICTED", None)
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                target = tmp.name
            try:
                with self.assertRaises(ValueError):
                    assert_file_path_allowed(target)
            finally:
                if os.path.exists(target):
                    os.unlink(target)
        finally:
            if original_paths is None:
                os.environ.pop("VISUAL_ANNOTATION_ALLOWED_PATHS", None)
            else:
                os.environ["VISUAL_ANNOTATION_ALLOWED_PATHS"] = original_paths
            if original_unrestricted is None:
                os.environ.pop("VISUAL_ANNOTATION_ALLOW_UNRESTRICTED", None)
            else:
                os.environ["VISUAL_ANNOTATION_ALLOW_UNRESTRICTED"] = original_unrestricted

    def test_file_path_allowlist_rejects_outside_root(self) -> None:
        original_paths = os.environ.get("VISUAL_ANNOTATION_ALLOWED_PATHS")
        original_unrestricted = os.environ.get("VISUAL_ANNOTATION_ALLOW_UNRESTRICTED")
        try:
            with tempfile.TemporaryDirectory() as root_dir, tempfile.TemporaryDirectory() as outside_dir:
                root = Path(root_dir)
                outside = Path(outside_dir)
                inside_file = root / "allowed.txt"
                outside_file = outside / "blocked.txt"
                inside_file.write_text("ok", encoding="utf-8")
                outside_file.write_text("no", encoding="utf-8")

                os.environ["VISUAL_ANNOTATION_ALLOWED_PATHS"] = str(root)
                os.environ.pop("VISUAL_ANNOTATION_ALLOW_UNRESTRICTED", None)

                resolved_inside = assert_file_path_allowed(str(inside_file))
                self.assertEqual(resolved_inside, inside_file.resolve())

                with self.assertRaises(ValueError):
                    assert_file_path_allowed(str(outside_file))
        finally:
            if original_paths is None:
                os.environ.pop("VISUAL_ANNOTATION_ALLOWED_PATHS", None)
            else:
                os.environ["VISUAL_ANNOTATION_ALLOWED_PATHS"] = original_paths
            if original_unrestricted is None:
                os.environ.pop("VISUAL_ANNOTATION_ALLOW_UNRESTRICTED", None)
            else:
                os.environ["VISUAL_ANNOTATION_ALLOW_UNRESTRICTED"] = original_unrestricted

    def test_unrestricted_mode_allows_navigation_and_paths(self) -> None:
        original_hosts = os.environ.get("VISUAL_ANNOTATION_ALLOWED_HOSTS")
        original_paths = os.environ.get("VISUAL_ANNOTATION_ALLOWED_PATHS")
        original_unrestricted = os.environ.get("VISUAL_ANNOTATION_ALLOW_UNRESTRICTED")
        try:
            os.environ.pop("VISUAL_ANNOTATION_ALLOWED_HOSTS", None)
            os.environ.pop("VISUAL_ANNOTATION_ALLOWED_PATHS", None)
            os.environ["VISUAL_ANNOTATION_ALLOW_UNRESTRICTED"] = "1"

            assert_url_allowed("https://example.com/")

            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                target = tmp.name
            try:
                resolved = assert_file_path_allowed(target)
                self.assertEqual(resolved, Path(target).resolve())
            finally:
                if os.path.exists(target):
                    os.unlink(target)
        finally:
            if original_hosts is None:
                os.environ.pop("VISUAL_ANNOTATION_ALLOWED_HOSTS", None)
            else:
                os.environ["VISUAL_ANNOTATION_ALLOWED_HOSTS"] = original_hosts
            if original_paths is None:
                os.environ.pop("VISUAL_ANNOTATION_ALLOWED_PATHS", None)
            else:
                os.environ["VISUAL_ANNOTATION_ALLOWED_PATHS"] = original_paths
            if original_unrestricted is None:
                os.environ.pop("VISUAL_ANNOTATION_ALLOW_UNRESTRICTED", None)
            else:
                os.environ["VISUAL_ANNOTATION_ALLOW_UNRESTRICTED"] = original_unrestricted


if __name__ == "__main__":
    unittest.main()
