from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from beta_site.scripts import build_kit


class BetaKitTests(unittest.TestCase):
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
