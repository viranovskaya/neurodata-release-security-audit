from __future__ import annotations

import tempfile
import unittest
import sys
import zipfile
from pathlib import Path
from unittest.mock import patch

from beta_site.scripts import build_kit


class BetaKitTests(unittest.TestCase):
    def test_build_creates_new_archive_but_does_not_rewrite_identical_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "kit.zip"
            with patch.object(build_kit, "DOWNLOADS", root), \
                 patch.object(build_kit, "release_values", return_value={"archive": "kit.zip", "wheel": "synthetic.whl"}), \
                 patch.object(build_kit, "kit_files", return_value={"README.txt": b"verified synthetic file"}), \
                 patch.object(build_kit, "update_archive_hash"), \
                 patch.object(sys, "argv", ["build_kit.py"]):
                build_kit.main()
                with zipfile.ZipFile(archive) as opened:
                    self.assertEqual(b"verified synthetic file", opened.read("README.txt"))
                before = archive.stat().st_mtime_ns
                build_kit.main()
                self.assertEqual(before, archive.stat().st_mtime_ns)

    def test_build_cannot_replace_a_different_versioned_archive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "kit.zip"
            archive.write_bytes(b"already published synthetic archive")
            with patch.object(build_kit, "DOWNLOADS", root), \
                 patch.object(build_kit, "release_values", return_value={"archive": "kit.zip", "wheel": "synthetic.whl"}), \
                 patch.object(build_kit, "kit_files", return_value={"README.txt": b"different bytes"}), \
                 patch.object(build_kit, "update_archive_hash") as update, \
                 patch.object(sys, "argv", ["build_kit.py"]):
                with self.assertRaisesRegex(RuntimeError, "revision"):
                    build_kit.main()
                self.assertEqual(b"already published synthetic archive", archive.read_bytes())
                update.assert_not_called()
    def test_check_accepts_exact_archive_without_rewriting_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "kit.zip"
            files = {"README.txt": b"synthetic verified file"}
            expected = build_kit.write_archive(archive, files)
            before = archive.stat().st_mtime_ns
            with patch.object(build_kit, "DOWNLOADS", root), \
                 patch.object(build_kit, "release_values", return_value={"archive": "kit.zip", "archiveSha256": expected, "wheel": "synthetic.whl"}), \
                 patch.object(build_kit, "kit_files", return_value=files), \
                 patch.object(build_kit, "require_tracked_archive") as tracked, \
                 patch.object(sys, "argv", ["build_kit.py", "--check"]):
                build_kit.main()
                tracked.assert_called_once_with(archive)
            self.assertEqual(before, archive.stat().st_mtime_ns)

    def test_check_rejects_a_changed_tracked_zip_without_repairing_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reference = root / "reference.zip"
            files = {"README.txt": b"synthetic verified file"}
            expected = build_kit.write_archive(reference, files)
            archive = root / "kit.zip"
            archive.write_bytes(b"stale or modified archive")
            with patch.object(build_kit, "DOWNLOADS", root), \
                 patch.object(build_kit, "release_values", return_value={"archive": "kit.zip", "archiveSha256": expected, "wheel": "synthetic.whl"}), \
                 patch.object(build_kit, "kit_files", return_value=files), \
                 patch.object(build_kit, "require_tracked_archive"), \
                 patch.object(sys, "argv", ["build_kit.py", "--check"]):
                with self.assertRaises(RuntimeError):
                    build_kit.main()
            self.assertEqual(b"stale or modified archive", archive.read_bytes())

    def test_demo_symlink_cannot_enter_downloadable_archive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outside = root / "private.txt"
            outside.write_text("private synthetic fixture", encoding="utf-8")
            demo = root / "examples" / "reviewer_demo"
            demo.mkdir(parents=True)
            (demo / "linked.txt").symlink_to(outside)
            constraints = root / ".github" / "constraints"
            constraints.mkdir(parents=True)
            (constraints / "calibration-readers.txt").write_text("", encoding="utf-8")
            (root / "LICENSE").write_text("synthetic", encoding="utf-8")

            with patch.object(build_kit, "REPO", root), patch.object(
                build_kit, "verify_wheel", return_value=b"synthetic wheel"
            ), self.assertRaisesRegex(RuntimeError, "symlink"):
                build_kit.kit_files(Path("ignored.whl"), build_kit.release_values())


if __name__ == "__main__":
    unittest.main()
