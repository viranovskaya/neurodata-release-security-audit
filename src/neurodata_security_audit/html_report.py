"""Build a self-contained visual audit report."""

from __future__ import annotations

from html import escape
from typing import Callable, Iterable, Sequence

from .models import ScanReport

_STYLE = """
:root {
  color-scheme: light dark;
  --bg: #f6f7f9;
  --surface: #ffffff;
  --text: #17191d;
  --muted: #626874;
  --line: #dfe3e8;
  --high: #b42318;
  --high-soft: #fee4e2;
  --review: #b54708;
  --review-soft: #ffead5;
  --info: #175cd3;
  --info-soft: #dbeafe;
  --ok: #067647;
  --ok-soft: #d1fadf;
  --coverage-1: #2563eb;
  --coverage-2: #7c3aed;
  --coverage-3: #0891b2;
  --coverage-4: #d97706;
  --coverage-5: #64748b;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #111318;
    --surface: #1a1d24;
    --text: #f2f4f7;
    --muted: #a7afbd;
    --line: #343a46;
    --high: #f97066;
    --high-soft: #4a1d1d;
    --review: #fdb022;
    --review-soft: #472f13;
    --info: #84adff;
    --info-soft: #182d52;
    --ok: #47cd89;
    --ok-soft: #12372a;
    --coverage-1: #60a5fa;
    --coverage-2: #a78bfa;
    --coverage-3: #22d3ee;
    --coverage-4: #f59e0b;
    --coverage-5: #94a3b8;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont,
    "Segoe UI", sans-serif;
  line-height: 1.5;
}
main {
  width: min(1180px, calc(100% - 32px));
  margin: 32px auto 64px;
}
h1, h2 { line-height: 1.2; }
h1 { margin: 0; font-size: clamp(1.6rem, 4vw, 2.25rem); }
h2 { margin: 0 0 16px; font-size: 1.15rem; }
p { margin: 0; }
.top {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  align-items: flex-start;
  margin-bottom: 22px;
}
.subtitle { color: var(--muted); margin-top: 8px; max-width: 760px; }
.status {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 6px 10px;
  font-size: .86rem;
  font-weight: 650;
  white-space: nowrap;
}
.status.ok { color: var(--ok); background: var(--ok-soft); }
.status.failed { color: var(--high); background: var(--high-soft); }
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}
.card, section {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 14px;
}
.card { padding: 16px; }
.label { color: var(--muted); font-size: .84rem; }
.value { font-size: 1.75rem; font-weight: 700; margin-top: 2px; }
.context { color: var(--muted); font-size: .84rem; margin-top: 2px; }
section { margin-top: 16px; padding: 20px; }
.bars { display: grid; gap: 10px; }
.bar-row {
  display: grid;
  grid-template-columns: minmax(170px, .8fr) minmax(130px, 2fr) 44px;
  gap: 12px;
  align-items: center;
}
.track {
  height: 12px;
  border-radius: 999px;
  background: var(--line);
  overflow: hidden;
}
.fill { display: block; height: 100%; border-radius: 999px; }
.fill.high { background: var(--high); }
.fill.review { background: var(--review); }
.fill.info { background: var(--info); }
.fill.coverage-1 { background: var(--coverage-1); }
.fill.coverage-2 { background: var(--coverage-2); }
.fill.coverage-3 { background: var(--coverage-3); }
.fill.coverage-4 { background: var(--coverage-4); }
.fill.coverage-5 { background: var(--coverage-5); }
.count { text-align: right; font-variant-numeric: tabular-nums; }
.table-wrap { overflow-x: auto; }
table {
  width: 100%;
  border-collapse: collapse;
  font-size: .9rem;
}
th, td {
  padding: 10px 9px;
  border-bottom: 1px solid var(--line);
  text-align: left;
  vertical-align: top;
  overflow-wrap: anywhere;
}
th {
  color: var(--muted);
  font-size: .78rem;
  font-weight: 650;
  text-transform: uppercase;
  letter-spacing: .03em;
}
tbody tr:last-child td { border-bottom: 0; }
.number { text-align: right; font-variant-numeric: tabular-nums; }
code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: .86em;
  overflow-wrap: anywhere;
}
.severity {
  display: inline-block;
  border-radius: 999px;
  padding: 2px 7px;
  font-size: .78rem;
  font-weight: 650;
}
.severity.high { color: var(--high); background: var(--high-soft); }
.severity.review { color: var(--review); background: var(--review-soft); }
.severity.info { color: var(--info); background: var(--info-soft); }
.empty, .note { color: var(--muted); }
.note { margin-top: 12px; font-size: .86rem; }
footer {
  color: var(--muted);
  font-size: .82rem;
  margin-top: 18px;
  text-align: center;
}
@media (max-width: 640px) {
  main { width: min(100% - 20px, 1180px); margin-top: 18px; }
  .top { display: grid; }
  .bar-row { grid-template-columns: minmax(0, 1fr) 38px; }
  .track { grid-column: 1 / -1; grid-row: 2; }
  section { padding: 16px; }
}
@media print {
  :root {
    --bg: #ffffff;
    --surface: #ffffff;
    --text: #000000;
    --muted: #4b5563;
    --line: #d1d5db;
  }
  main { width: 100%; margin: 0; }
  .card, section { break-inside: avoid; }
}
"""


def _text(value: object) -> str:
    return escape(str(value), quote=True)


def _table(
    headers: Sequence[str],
    rows: Iterable[Sequence[object]],
    *,
    empty: str,
    numeric_columns: frozenset[int] = frozenset(),
    code_columns: frozenset[int] = frozenset(),
    renderers: dict[int, Callable[[object], str]] | None = None,
) -> str:
    materialized = list(rows)
    if not materialized:
        return f'<p class="empty">{_text(empty)}</p>'
    head = "".join(f"<th>{_text(header)}</th>" for header in headers)
    body_rows = []
    for row in materialized:
        cells = []
        for index, value in enumerate(row):
            classes = ' class="number"' if index in numeric_columns else ""
            if renderers and index in renderers:
                rendered = renderers[index](value)
            elif index in code_columns:
                rendered = f"<code>{_text(value)}</code>"
            else:
                rendered = _text(value)
            if index in code_columns and renderers and index in renderers:
                rendered = f"<code>{rendered}</code>"
            cells.append(f"<td{classes}>{rendered}</td>")
        body_rows.append("<tr>" + "".join(cells) + "</tr>")
    return (
        '<div class="table-wrap"><table><thead><tr>'
        + head
        + "</tr></thead><tbody>"
        + "".join(body_rows)
        + "</tbody></table></div>"
    )


def _bar_rows(
    values: Sequence[tuple[str, int, str]],
) -> str:
    maximum = max((value for _, value, _ in values), default=0)
    rows = []
    for label, value, css_class in values:
        width = 0 if maximum == 0 else 100 * value / maximum
        rows.append(
            '<div class="bar-row">'
            f"<span>{_text(label)}</span>"
            '<span class="track">'
            f'<span class="fill {_text(css_class)}" style="width:{width:.3f}%"></span>'
            "</span>"
            f'<span class="count">{value}</span>'
            "</div>"
        )
    return '<div class="bars">' + "".join(rows) + "</div>"


def _severity(value: object) -> str:
    severity = str(value)
    css_class = severity if severity in {"high", "review", "info"} else "info"
    return f'<span class="severity {css_class}">{_text(severity)}</span>'


def render_html(report: ScanReport) -> str:
    """Render one deterministic standalone HTML report."""
    data = report.to_dict()
    summary = data["summary"]
    integrity_ok = (
        summary["manifest_recheck_passed"]
        and summary["release_tree_recheck_passed"]
    )
    finding_total = (
        summary["findings_high"]
        + summary["findings_review"]
        + summary["findings_info"]
    )

    findings = []
    for item in data["findings"]:
        findings.append(
            (
                item["severity"],
                item["code"],
                item["path"],
                item["location"],
                item["evidence"],
                item["message"],
            )
        )
    findings_table = _table(
        ("Severity", "Code", "File", "Location", "Evidence", "What to check"),
        findings,
        empty="No findings.",
        code_columns=frozenset({1}),
        renderers={0: _severity},
    )

    coverage_table = _table(
        ("Status", "Type", "Entry", "Reason"),
        (
            (
                item["status"],
                item["entry_type"],
                item["path"],
                item["reason"],
            )
            for item in data["coverage"]
        ),
        empty="No release entries were recorded.",
        code_columns=frozenset({0}),
    )
    references_table = _table(
        ("Source", "Location", "Target", "Status", "Reason"),
        (
            (
                item["source_path"],
                item["location"],
                item["target"],
                item["status"],
                item["reason"],
            )
            for item in data["references"]
        ),
        empty="No supported cross-file references were found.",
        code_columns=frozenset({3}),
    )
    members_table = _table(
        ("Archive", "Member", "Type", "Bytes", "Compressed", "Encrypted"),
        (
            (
                item["container_path"],
                item["member_path"],
                item["member_type"],
                item["size_bytes"],
                item["compressed_bytes"],
                "yes" if item["encrypted"] else "no",
            )
            for item in data["container_members"]
        ),
        empty="No supported archive members were inventoried.",
        numeric_columns=frozenset({3, 4}),
    )
    skipped_table = _table(
        ("Entry", "Reason"),
        ((item["path"], item["reason"]) for item in data["skipped_files"]),
        empty="No skipped files.",
    )
    manifest_table = _table(
        ("File", "Bytes", "SHA-256"),
        (
            (item["path"], item["size_bytes"], item["sha256"])
            for item in data["manifest"]
        ),
        empty="No regular files were added to the manifest.",
        numeric_columns=frozenset({1}),
        code_columns=frozenset({2}),
    )

    severity_bars = _bar_rows(
        (
            ("High severity", summary["findings_high"], "high"),
            ("Needs review", summary["findings_review"], "review"),
            ("Information", summary["findings_info"], "info"),
        )
    )
    coverage_bars = _bar_rows(
        (
            (
                "Fully inspected metadata",
                summary["fully_inspected_metadata"],
                "coverage-1",
            ),
            (
                "Header or structure only",
                summary["header_or_structure_only"],
                "coverage-2",
            ),
            (
                "Payload not opened",
                summary["payload_not_opened"],
                "coverage-3",
            ),
            (
                "Manual review",
                summary["unsupported_manual_review"],
                "coverage-4",
            ),
            (
                "Inventoried, not parsed",
                summary["not_traversed"],
                "coverage-5",
            ),
        )
    )
    status_class = "ok" if integrity_ok else "failed"
    status_text = "Integrity checks passed" if integrity_ok else "Integrity check failed"
    valid_references = (
        f"{summary['references_valid']} / {summary['references_checked']}"
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>NeuroData release security audit</title>
<style>{_STYLE}</style>
</head>
<body>
<main>
  <header class="top">
    <div>
      <h1>NeuroData release security audit</h1>
      <p class="subtitle">A local, read-only pre-release check. This report identifies
      items that need a decision; it does not certify anonymity or compliance.</p>
    </div>
    <span class="status {status_class}">{status_text}</span>
  </header>

  <div class="grid" aria-label="Audit summary">
    <div class="card">
      <div class="label">Release entries</div>
      <div class="value">{summary["entries_total"]}</div>
      <div class="context">{summary["manifest_files"]} regular files in the manifest</div>
    </div>
    <div class="card">
      <div class="label">Findings</div>
      <div class="value">{finding_total}</div>
      <div class="context">{summary["findings_high"]} high · {summary["findings_review"]} review</div>
    </div>
    <div class="card">
      <div class="label">Files inspected</div>
      <div class="value">{summary["files_inspected"]}</div>
      <div class="context">{summary["files_skipped"]} skipped or partially covered</div>
    </div>
    <div class="card">
      <div class="label">Valid references</div>
      <div class="value">{valid_references}</div>
      <div class="context">{summary["container_members"]} archive members inventoried</div>
    </div>
  </div>

  <section>
    <h2>Findings by severity</h2>
    {severity_bars}
  </section>

  <section>
    <h2>Coverage</h2>
    {coverage_bars}
    <p class="note">Coverage describes what was read. It is separate from privacy
    findings. Signal samples, image voxels and DICOM pixels are not interpreted.</p>
  </section>

  <section>
    <h2>Findings</h2>
    {findings_table}
  </section>

  <section>
    <h2>Release entries</h2>
    {coverage_table}
  </section>

  <section>
    <h2>Cross-file references</h2>
    {references_table}
  </section>

  <section>
    <h2>Archive members</h2>
    {members_table}
  </section>

  <section>
    <h2>Skipped files and directories</h2>
    {skipped_table}
  </section>

  <section>
    <h2>SHA-256 manifest</h2>
    {manifest_table}
    <p class="note">Hashes are consistency evidence, not proof of provenance or
    anonymity.</p>
  </section>

  <footer>Scanner {_text(data["scanner_version"])} · report schema {_text(data["schema_version"])}</footer>
</main>
</body>
</html>
"""
