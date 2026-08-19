"""Serve a local browser interface for one-off dataset audits."""

from __future__ import annotations

import hmac
import json
import secrets
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .curator import write_texts_new
from .html_report import render_html
from .reporting import render_json, render_markdown
from .scanner import scan_dataset

_MAX_REQUEST_BYTES = 64 * 1024

_PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>NeuroData local audit</title>
  <style>
    :root { color-scheme: light; font-family: Inter, system-ui, sans-serif; }
    body { margin: 0; background: #f4f7f6; color: #172321; }
    main { max-width: 760px; margin: 0 auto; padding: 48px 20px 72px; }
    .eyebrow { color: #176b58; font-weight: 750; letter-spacing: .05em;
      text-transform: uppercase; font-size: .78rem; }
    h1 { font-size: clamp(2rem, 6vw, 3.7rem); line-height: 1.02;
      margin: 12px 0 16px; max-width: 700px; }
    .lead { font-size: 1.12rem; line-height: 1.6; max-width: 680px; }
    .local { display: flex; gap: 10px; align-items: flex-start; padding: 16px;
      border: 1px solid #a8c8bf; background: #eaf5f1; border-radius: 14px;
      margin: 26px 0; }
    .local strong { display: block; margin-bottom: 3px; }
    form { background: white; padding: 24px; border-radius: 18px;
      box-shadow: 0 12px 35px rgba(22, 55, 47, .09); }
    label { display: block; font-weight: 720; margin: 0 0 8px; }
    .hint { display: block; color: #53635f; font-size: .9rem; line-height: 1.45;
      margin: 7px 0 22px; }
    input { width: 100%; box-sizing: border-box; padding: 13px 14px;
      border: 1px solid #869b95; border-radius: 10px; font: inherit; }
    input:focus, button:focus, a:focus { outline: 3px solid #f1bd35;
      outline-offset: 3px; }
    button { border: 0; border-radius: 10px; padding: 13px 20px;
      background: #176b58; color: white; font: inherit; font-weight: 750;
      cursor: pointer; }
    button[disabled] { opacity: .55; cursor: wait; }
    #status { margin-top: 20px; padding: 15px 17px; border-radius: 12px;
      background: #eef1f0; min-height: 24px; line-height: 1.5; }
    #status.error { color: #8b241f; background: #fff0ee; }
    #status.success { color: #124c3e; background: #e8f5ef; }
    .summary { margin: 14px 0 0; padding-left: 20px; }
    .report-link { display: inline-block; margin-top: 14px; color: #0e5e4c;
      font-weight: 750; }
    footer { margin-top: 24px; color: #60716c; font-size: .88rem; }
  </style>
</head>
<body>
<main>
  <div class="eyebrow">Private beta · local interface</div>
  <h1>Check a dataset before sharing it</h1>
  <p class="lead">Choose a local dataset folder and a separate folder for the
    reports. The audit checks metadata, file structure and supported embedded
    formats, then creates JSON, Markdown and HTML reports.</p>
  <div class="local" role="note">
    <span aria-hidden="true">●</span>
    <div><strong>Your dataset stays on this computer.</strong>
      This page talks only to a temporary service on <code>127.0.0.1</code>.
      It does not upload dataset files or report contents.</div>
  </div>
  <form id="audit-form">
    <label for="dataset">Dataset folder</label>
    <input id="dataset" name="dataset" autocomplete="off" required
      placeholder="/Users/me/data/my-dataset">
    <span class="hint">Enter the full path to the folder you want to inspect.
      The scanner reads it without modifying it.</span>

    <label for="output">Report folder</label>
    <input id="output" name="output" autocomplete="off" required
      placeholder="/Users/me/Documents/audit-results">
    <span class="hint">Keep this outside the dataset. Existing report files
      are never replaced.</span>

    <button id="run" type="submit">Run local audit</button>
    <div id="status" role="status" aria-live="polite">Ready.</div>
  </form>
  <footer>Closing this browser tab does not publish or approve a dataset.</footer>
</main>
<script>
(() => {
  const fragmentToken = location.hash.slice(1);
  if (fragmentToken) sessionStorage.setItem("neurodata-local-token", fragmentToken);
  const token = sessionStorage.getItem("neurodata-local-token") || "";
  history.replaceState(null, "", location.pathname);
  const form = document.querySelector("#audit-form");
  const status = document.querySelector("#status");
  const button = document.querySelector("#run");

  const setStatus = (message, kind = "") => {
    status.className = kind;
    status.textContent = message;
  };

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!token) {
      setStatus("This local session is missing its access token. Restart the UI.",
        "error");
      return;
    }
    button.disabled = true;
    setStatus("Scanning. Large datasets and format readers may take a while.");
    try {
      const response = await fetch("/api/scan", {
        method: "POST",
        headers: {"Content-Type": "application/json", "X-Local-Token": token},
        body: JSON.stringify({
          dataset: document.querySelector("#dataset").value,
          output: document.querySelector("#output").value
        })
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "The scan failed.");
      status.className = "success";
      status.replaceChildren();
      const title = document.createElement("strong");
      title.textContent = result.release_message;
      status.append(title);
      const list = document.createElement("ul");
      list.className = "summary";
      for (const line of result.summary_lines) {
        const item = document.createElement("li");
        item.textContent = line;
        list.append(item);
      }
      status.append(list);
      const link = document.createElement("a");
      link.className = "report-link";
      link.href = result.report_url;
      link.target = "_blank";
      link.rel = "noopener";
      link.textContent = "Open the HTML report";
      status.append(link);
    } catch (error) {
      setStatus(error.message || "The scan failed.", "error");
    } finally {
      button.disabled = false;
    }
  });
})();
</script>
</body>
</html>
"""


def _is_inside(path: Path, directory: Path) -> bool:
    root = directory.expanduser().resolve(strict=True)
    candidate = path.expanduser().resolve(strict=False)
    return candidate == root or root in candidate.parents


def _error_text(error: Exception) -> str:
    if isinstance(error, FileNotFoundError):
        return "The dataset folder does not exist."
    if isinstance(error, NotADirectoryError):
        return "The dataset path is not a folder."
    if isinstance(error, FileExistsError):
        return "One or more report files already exist. Choose another folder."
    if isinstance(error, PermissionError):
        return "The audit could not read the dataset or write the reports."
    if isinstance(error, ValueError):
        return str(error)
    return f"The audit failed ({type(error).__name__})."


class _LocalAuditServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, port: int, token: str) -> None:
        super().__init__(("127.0.0.1", port), _LocalAuditHandler)
        self.token = token
        self.scan_lock = threading.Lock()
        self.reports: dict[str, str] = {}


class _LocalAuditHandler(BaseHTTPRequestHandler):
    server: _LocalAuditServer

    def log_message(self, format: str, *args: object) -> None:
        return

    def _headers(self, status: HTTPStatus, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", (
            "default-src 'none'; style-src 'unsafe-inline'; "
            "script-src 'unsafe-inline'; connect-src 'self'; "
            "img-src 'self'; base-uri 'none'; form-action 'self'; "
            "frame-ancestors 'none'"
        ))
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()

    def _write_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._headers(status, "application/json; charset=utf-8")
        self.wfile.write(body)

    def _authorized(self) -> bool:
        supplied = self.headers.get("X-Local-Token", "")
        return hmac.compare_digest(supplied, self.server.token)

    def _same_origin(self) -> bool:
        origin = self.headers.get("Origin", "")
        expected = f"http://127.0.0.1:{self.server.server_port}"
        return origin == expected

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/":
            body = _PAGE.encode("utf-8")
            self._headers(HTTPStatus.OK, "text/html; charset=utf-8")
            self.wfile.write(body)
            return
        if path.startswith("/report/"):
            run_id = path.removeprefix("/report/")
            report = self.server.reports.get(run_id)
            if report is None:
                self._write_json(HTTPStatus.NOT_FOUND, {"error": "Report not found."})
                return
            self._headers(HTTPStatus.OK, "text/html; charset=utf-8")
            self.wfile.write(report.encode("utf-8"))
            return
        self._write_json(HTTPStatus.NOT_FOUND, {"error": "Not found."})

    def do_POST(self) -> None:
        if urlsplit(self.path).path != "/api/scan":
            self._write_json(HTTPStatus.NOT_FOUND, {"error": "Not found."})
            return
        if not self._authorized() or not self._same_origin():
            self._write_json(HTTPStatus.FORBIDDEN, {"error": "Invalid session."})
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            size = -1
        if size <= 0 or size > _MAX_REQUEST_BYTES:
            self._write_json(HTTPStatus.BAD_REQUEST, {"error": "Invalid request."})
            return
        try:
            request = json.loads(self.rfile.read(size).decode("utf-8"))
            dataset = Path(str(request["dataset"])).expanduser()
            output = Path(str(request["output"])).expanduser()
            if (
                not str(request["dataset"]).strip()
                or not str(request["output"]).strip()
            ):
                raise ValueError("Both folder paths are required.")
            if _is_inside(output, dataset):
                raise ValueError("The report folder must be outside the dataset.")
        except (KeyError, TypeError, json.JSONDecodeError, UnicodeError):
            self._write_json(HTTPStatus.BAD_REQUEST, {"error": "Invalid request."})
            return
        except (OSError, RuntimeError, ValueError) as error:
            self._write_json(HTTPStatus.BAD_REQUEST, {"error": _error_text(error)})
            return

        if not self.server.scan_lock.acquire(blocking=False):
            self._write_json(
                HTTPStatus.CONFLICT,
                {"error": "Another local audit is already running."},
            )
            return
        try:
            report = scan_dataset(dataset)
            outputs = {
                output / "audit.json": render_json(report),
                output / "audit.md": render_markdown(report),
                output / "audit.html": render_html(report),
            }
            write_texts_new(outputs)
        except (OSError, RuntimeError, UnicodeError, ValueError) as error:
            self._write_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": _error_text(error)},
            )
            return
        finally:
            self.server.scan_lock.release()

        summary = report.to_dict()["summary"]
        integrity_ok = (
            summary["manifest_recheck_passed"]
            and summary["release_tree_recheck_passed"]
        )
        if not integrity_ok:
            release_message = "STOP: the dataset changed during the scan."
        elif summary["findings_high"]:
            release_message = "HOLD: resolve high-priority findings before release."
        else:
            release_message = "Review required: the audit does not approve release."
        run_id = secrets.token_urlsafe(24)
        self.server.reports.clear()
        self.server.reports[run_id] = outputs[output / "audit.html"]
        self._write_json(
            HTTPStatus.OK,
            {
                "release_message": release_message,
                "summary_lines": [
                    f"{summary['files_inspected']} files inspected",
                    f"{summary['findings_high']} high-priority findings",
                    f"{summary['findings_review']} review findings",
                    "Reports written to the folder you selected",
                ],
                "report_url": f"/report/{run_id}",
            },
        )


def start_local_ui(port: int = 0, *, open_browser: bool = True) -> None:
    """Run the local audit UI until interrupted."""
    token = secrets.token_urlsafe(32)
    server = _LocalAuditServer(port, token)
    base_address = f"http://127.0.0.1:{server.server_port}/"
    session_address = f"{base_address}#{token}"
    print(f"Local audit UI: {base_address}")
    print("Dataset files stay on this computer. Press Ctrl+C to stop.")
    if open_browser:
        webbrowser.open(session_address)
    else:
        print(f"Open this private session address: {session_address}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
