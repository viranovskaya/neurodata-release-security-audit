"""Tests for the loopback-only browser interface."""

from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from neurodata_security_audit.local_ui import _LocalAuditServer


class LocalUiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.token = "test-local-token"
        self.server = _LocalAuditServer(0, self.token)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def _post(self, payload: dict[str, str], *, token: str | None = None):
        headers = {
            "Content-Type": "application/json",
            "Origin": self.base_url,
        }
        if token is not None:
            headers["X-Local-Token"] = token
        request = Request(
            f"{self.base_url}/api/scan",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        return urlopen(request, timeout=10)

    def test_page_explains_that_data_stays_local(self) -> None:
        with urlopen(f"{self.base_url}/", timeout=5) as response:
            page = response.read().decode("utf-8")
        self.assertIn("Your dataset stays on this computer", page)
        self.assertIn("127.0.0.1", page)
        self.assertIn("does not upload dataset files", page)
        self.assertIn("sessionStorage", page)
        self.assertEqual(self.server.server_address[0], "127.0.0.1")

    def test_scan_requires_session_token(self) -> None:
        with self.assertRaises(HTTPError) as caught:
            self._post({"dataset": "/tmp/data", "output": "/tmp/report"})
        self.assertEqual(caught.exception.code, 403)

    def test_scan_writes_reports_outside_dataset_and_serves_html(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dataset = root / "dataset"
            dataset.mkdir()
            (dataset / "dataset_description.json").write_text(
                '{"Name": "Synthetic local UI fixture", "BIDSVersion": "1.10.0"}',
                encoding="utf-8",
            )
            output = root / "reports"

            with self._post(
                {"dataset": str(dataset), "output": str(output)},
                token=self.token,
            ) as response:
                result = json.loads(response.read())

            self.assertTrue((output / "audit.json").is_file())
            self.assertTrue((output / "audit.md").is_file())
            self.assertTrue((output / "audit.html").is_file())
            self.assertEqual(
                list(dataset.iterdir()),
                [dataset / "dataset_description.json"],
            )
            self.assertTrue(result["report_url"].startswith("/report/"))
            with urlopen(self.base_url + result["report_url"], timeout=5) as response:
                report_page = response.read().decode("utf-8")
            self.assertIn("NeuroData", report_page)

    def test_report_folder_inside_dataset_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            dataset = Path(directory) / "dataset"
            dataset.mkdir()
            with self.assertRaises(HTTPError) as caught:
                self._post(
                    {
                        "dataset": str(dataset),
                        "output": str(dataset / "reports"),
                    },
                    token=self.token,
                )
            self.assertEqual(caught.exception.code, 400)
            self.assertFalse((dataset / "reports").exists())

    def test_existing_report_is_not_replaced(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dataset = root / "dataset"
            dataset.mkdir()
            output = root / "reports"
            output.mkdir()
            existing = output / "audit.json"
            existing.write_text("keep me", encoding="utf-8")

            with self.assertRaises(HTTPError) as caught:
                self._post(
                    {"dataset": str(dataset), "output": str(output)},
                    token=self.token,
                )
            self.assertEqual(caught.exception.code, 500)
            self.assertEqual(existing.read_text(encoding="utf-8"), "keep me")
            self.assertFalse((output / "audit.md").exists())
            self.assertFalse((output / "audit.html").exists())


if __name__ == "__main__":
    unittest.main()
