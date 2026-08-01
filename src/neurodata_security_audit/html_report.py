"""Build a self-contained visual audit report."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from html import escape

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
.report-actions { margin-top: 14px; }
.report-action {
  display: inline-block;
  border-radius: 9px;
  padding: 8px 12px;
  color: var(--surface);
  background: var(--high);
  font-size: .88rem;
  font-weight: 650;
  text-decoration: none;
}
.report-action.hold { background: var(--review); }
.decision {
  margin: 0 0 16px;
  padding: 14px 16px;
  border-left: 4px solid var(--line);
  border-radius: 8px;
}
.decision.high { border-color: var(--high); background: var(--high-soft); }
.decision.review { border-color: var(--review); background: var(--review-soft); }
.decision.ok { border-color: var(--ok); background: var(--ok-soft); }
.decision strong { display: block; margin-bottom: 3px; }
.privacy-warning {
  margin: 0 0 22px;
  padding: 12px 14px;
  border-left: 4px solid var(--review);
  background: var(--review-soft);
  color: var(--text);
}
.status {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 6px 10px;
  font-size: .86rem;
  font-weight: 650;
  white-space: nowrap;
}
.status-stack {
  display: grid;
  justify-items: end;
  gap: 7px;
}
.status.ok { color: var(--ok); background: var(--ok-soft); }
.status.hold { color: var(--review); background: var(--review-soft); }
.status.failed { color: var(--high); background: var(--high-soft); }
.integrity-note {
  color: var(--muted);
  max-width: 270px;
  font-size: .78rem;
  text-align: right;
}
.share-decision {
  display: grid;
  grid-template-columns: minmax(210px, .8fr) minmax(220px, 1fr)
    minmax(220px, 1fr);
  gap: 18px;
  margin: 0 0 16px;
  padding: 18px 20px;
  border: 1px solid var(--line);
  border-left: 5px solid var(--line);
  border-radius: 14px;
  background: var(--surface);
}
.share-decision.failed {
  border-left-color: var(--high);
  background: var(--high-soft);
}
.share-decision.hold {
  border-left-color: var(--review);
  background: var(--review-soft);
}
.share-decision.ok {
  border-left-color: var(--ok);
  background: var(--ok-soft);
}
.share-question {
  color: var(--muted);
  font-size: .82rem;
  font-weight: 650;
}
.share-answer {
  margin-top: 3px;
  font-size: 1.45rem;
  font-weight: 750;
  line-height: 1.2;
}
.share-detail {
  align-self: center;
  font-size: .92rem;
}
.share-detail strong {
  display: block;
  margin-bottom: 3px;
  font-size: .78rem;
  text-transform: uppercase;
  letter-spacing: .03em;
}
.finding-list-status {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 12px;
  margin: -4px 0 16px;
  padding: 12px 16px;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: var(--surface);
  font-size: .9rem;
}
.finding-list-status strong {
  color: var(--muted);
}
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
.card-link {
  display: block;
  color: inherit;
  text-decoration: none;
  transition: border-color .15s ease, transform .15s ease;
}
.card-link:hover { border-color: var(--info); transform: translateY(-1px); }
.card-link:focus-visible {
  outline: 2px solid var(--info);
  outline-offset: 3px;
}
.label { color: var(--muted); font-size: .84rem; }
.value { font-size: 1.75rem; font-weight: 700; margin-top: 2px; }
.context { color: var(--muted); font-size: .84rem; margin-top: 2px; }
section { margin-top: 16px; padding: 20px; }
.bars { display: grid; gap: 10px; }
.bar-row {
  display: grid;
  grid-template-columns: minmax(170px, .8fr) minmax(130px, 2fr) 76px;
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
.count {
  min-width: 70px;
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.table-wrap { overflow-x: auto; }
.table-wrap:focus-visible {
  outline: 2px solid var(--info);
  outline-offset: 3px;
}
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
table {
  width: 100%;
  min-width: 900px;
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
.fix-list { margin: 0; padding-left: 22px; }
.fix-list li + li { margin-top: 8px; }
.section-links {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 14px;
}
.section-links a {
  color: var(--text);
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 5px 9px;
  font-size: .84rem;
  text-decoration: none;
}
.finding-filters {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-bottom: 10px;
}
.finding-tools {
  display: grid;
  gap: 10px;
  margin-bottom: 14px;
}
.find-help {
  padding: 10px 12px;
  border-left: 4px solid var(--info);
  border-radius: 8px;
  background: var(--info-soft);
  font-size: .88rem;
}
kbd {
  display: inline-block;
  padding: 1px 6px;
  border: 1px solid var(--line);
  border-radius: 5px;
  background: var(--surface);
  font: inherit;
  font-size: .82rem;
  font-weight: 650;
}
.finding-filters input {
  position: absolute;
  opacity: 0;
  pointer-events: none;
}
.finding-filters label {
  cursor: pointer;
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 5px 10px;
  font-size: .84rem;
}
.finding-filters input:focus-visible + label {
  outline: 2px solid var(--info);
  outline-offset: 2px;
}
#findings-all:checked + label,
#findings-high:checked + label,
#findings-review:checked + label,
#findings-info:checked + label,
#findings-distinct:checked + label {
  color: var(--surface);
  background: var(--info);
  border-color: var(--info);
}
.finding-filter-shell:has(#findings-high:checked)
  .finding-row:not(.finding-high),
.finding-filter-shell:has(#findings-review:checked)
  .finding-row:not(.finding-review),
.finding-filter-shell:has(#findings-info:checked)
  .finding-row:not(.finding-info) {
  display: none;
}
.finding-filter-shell:has(#findings-distinct:checked)
  .finding-row:not(.finding-distinct) {
  display: none;
}
.filter-status span { display: none; }
.finding-filter-shell:has(#findings-all:checked) .filter-status-all,
.finding-filter-shell:has(#findings-high:checked) .filter-status-high,
.finding-filter-shell:has(#findings-review:checked) .filter-status-review,
.finding-filter-shell:has(#findings-info:checked) .filter-status-info,
.finding-filter-shell:has(#findings-distinct:checked) .filter-status-distinct {
  display: inline;
}
.provisional-section { border-color: var(--high); }
.provisional-section details { margin-top: 12px; }
.provisional-section summary {
  cursor: pointer;
  font-weight: 650;
}
details.review-queue {
  margin-top: 16px;
  border-top: 1px solid var(--line);
  padding-top: 12px;
}
details.review-queue summary {
  cursor: pointer;
  font-weight: 650;
  margin-bottom: 12px;
}
footer {
  color: var(--muted);
  font-size: .82rem;
  margin-top: 18px;
  text-align: center;
}
@media (max-width: 640px) {
  main { width: min(100% - 20px, 1180px); margin-top: 18px; }
  .top { display: grid; }
  .status-stack { justify-items: start; }
  .integrity-note { text-align: left; }
  .share-decision { grid-template-columns: 1fr; gap: 12px; }
  .bar-row { grid-template-columns: minmax(0, 1fr) 70px; }
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
  .finding-tools { display: none; }
  .finding-row { display: table-row !important; }
  .provisional-section details > * { display: block !important; }
  .provisional-section details > summary { display: none !important; }
  .table-wrap { overflow: visible; }
  table { min-width: 0; }
  thead { display: table-header-group; }
  .card, section { break-inside: auto; }
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
    table_label = "Table: " + ", ".join(str(header) for header in headers)
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
        f'<div class="table-wrap" role="region" tabindex="0" '
        f'aria-label="{_text(table_label)}"><table>'
        f'<caption class="sr-only">{_text(table_label)}</caption><thead><tr>'
        + head
        + "</tr></thead><tbody>"
        + "".join(body_rows)
        + "</tbody></table></div>"
    )


def _bar_rows(
    values: Sequence[tuple[str, int, str]],
    *,
    denominator: int,
) -> str:
    rows = []
    for label, value, css_class in values:
        width = 0 if denominator == 0 else 100 * value / denominator
        displayed_count = str(value) if denominator == 0 else f"{value} / {denominator}"
        rows.append(
            '<div class="bar-row">'
            f"<span>{_text(label)}</span>"
            '<span class="track">'
            f'<span class="fill {_text(css_class)}" style="width:{width:.3f}%"></span>'
            "</span>"
            f'<span class="count">{displayed_count}</span>'
            "</div>"
        )
    return '<div class="bars">' + "".join(rows) + "</div>"


def _severity(value: object) -> str:
    severity = str(value)
    css_class = severity if severity in {"high", "review", "info"} else "info"
    return f'<span class="severity {css_class}">{_text(severity)}</span>'


def _action_groups_table(
    findings: list[tuple[str, str, str, str, str, str]],
) -> tuple[str, int]:
    grouped: dict[tuple[str, str, str, str], set[str]] = {}
    for severity, code, path, location, _, message in findings:
        key = (severity, code, location, message)
        grouped.setdefault(key, set()).add(path)

    rows = []
    for (severity, code, location, message), paths in sorted(grouped.items()):
        ordered_paths = sorted(paths)
        examples = "; ".join(ordered_paths[:3])
        if len(ordered_paths) > 3:
            examples += f"; +{len(ordered_paths) - 3} more"
        rows.append(
            (
                severity,
                code,
                location,
                message,
                len(ordered_paths),
                examples,
            )
        )
    return (
        _table(
            (
                "Priority",
                "Code",
                "Field or location",
                "What to do",
                "Affected files",
                "Example files",
            ),
            rows,
            empty="No immediate remediation tasks.",
            numeric_columns=frozenset({4}),
            code_columns=frozenset({1, 5}),
            renderers={0: _severity},
        ),
        len(rows),
    )


def _filterable_findings_table(
    findings: list[tuple[str, str, str, str, str, str]],
) -> str:
    if not findings:
        return (
            '<p class="empty">No automated findings. Check Coverage and files '
            "needing manual review before release.</p>"
        )

    counts = {
        severity: sum(row[0] == severity for row in findings)
        for severity in ("high", "review", "info")
    }
    codes = sorted({row[1] for row in findings})
    code_classes = {code: f"finding-code-{index}" for index, code in enumerate(codes)}
    evidence_counts: dict[str, int] = {}
    for row in findings:
        evidence_counts[row[4]] = evidence_counts.get(row[4], 0) + 1
    distinct_count = sum(evidence_counts[row[4]] == 1 for row in findings)
    body = []
    for severity, code, path, location, evidence, message in findings:
        classes = ["finding-row", f"finding-{severity}", code_classes[code]]
        if evidence_counts[evidence] == 1:
            classes.append("finding-distinct")
        cells = (
            f"<td>{_severity(severity)}</td>",
            f"<td><code>{_text(code)}</code></td>",
            f"<td>{_text(path)}</td>",
            f"<td>{_text(location)}</td>",
            f"<td>{_text(evidence)}</td>",
            f"<td>{_text(message)}</td>",
        )
        body.append(
            f'<tr class="{" ".join(classes)}">'
            + "".join(cells)
            + "</tr>"
        )
    head = "".join(
        f"<th>{heading}</th>"
        for heading in (
            "Severity",
            "Code",
            "File",
            "Location",
            "Evidence",
            "What to check",
        )
    )
    code_filters = ""
    code_statuses = ""
    dynamic_css = ""
    if len(codes) <= 8:
        labels = []
        statuses = []
        rules = []
        for code in codes:
            css_class = code_classes[code]
            filter_id = css_class.replace("finding-", "findings-")
            count = sum(row[1] == code for row in findings)
            labels.append(
                f'<input type="radio" name="finding-filter" id="{filter_id}">'
                f'<label for="{filter_id}">{_text(code)} {count}</label>'
            )
            statuses.append(
                f'<span class="filter-status-{filter_id}">'
                f"{count} finding"
                f'{"s" if count != 1 else ""} shown for {_text(code)}.</span>'
            )
            rules.append(
                f".finding-filter-shell:has(#{filter_id}:checked) "
                f".finding-row:not(.{css_class}) {{ display: none; }}"
            )
            rules.append(
                f"#{filter_id}:checked + label {{ color: var(--surface); "
                "background: var(--info); border-color: var(--info); }"
            )
            rules.append(
                f".finding-filter-shell:has(#{filter_id}:checked) "
                f".filter-status-{filter_id} {{ display: inline; }}"
            )
        code_filters = "".join(labels)
        code_statuses = "".join(statuses)
        dynamic_css = "<style>" + "".join(rules) + "</style>"
    severity_filters = []
    severity_statuses = []
    for severity, label in (
        ("high", "High"),
        ("review", "Review"),
        ("info", "Info"),
    ):
        count = counts[severity]
        if not count:
            continue
        severity_filters.append(
            f'<input type="radio" name="finding-filter" '
            f'id="findings-{severity}">'
            f'<label for="findings-{severity}">{label} {count}</label>'
        )
        severity_statuses.append(
            f'<span class="filter-status-{severity}">{count} {label.lower()} '
            f'finding{"s" if count != 1 else ""} shown.</span>'
        )
    distinct_filter = (
        '<input type="radio" name="finding-filter" id="findings-distinct">'
        f'<label for="findings-distinct">Distinct evidence {distinct_count}</label>'
        if distinct_count
        else ""
    )
    return f"""
    {dynamic_css}
    <div class="finding-filter-shell">
      <div class="finding-tools">
        <div class="finding-filters" role="group" aria-label="Filter findings">
          <span class="label">Show</span>
          <input type="radio" name="finding-filter" id="findings-all" checked>
          <label for="findings-all">All {len(findings)}</label>
          {"".join(severity_filters)}
          {distinct_filter}
          {code_filters}
        </div>
        <div class="filter-status note" role="status" aria-live="polite">
          <span class="filter-status-all">{len(findings)}
          {"findings" if len(findings) != 1 else "finding"} shown.</span>
          {"".join(severity_statuses)}
          <span class="filter-status-distinct">{distinct_count}
          {"findings" if distinct_count != 1 else "finding"} with evidence
          seen once shown.</span>
          {code_statuses}
        </div>
        <div class="find-help"><strong>Find a file, field or value:</strong>
        press <kbd>⌘F</kbd> on Mac or <kbd>Ctrl+F</kbd> on Windows, then type
        part of the path, field, finding code or masked evidence.</div>
      </div>
      <div class="table-wrap" role="region" tabindex="0"
      aria-label="All findings table"><table>
      <caption class="sr-only">All findings</caption><thead><tr>{head}</tr></thead>
      <tbody>{"".join(body)}</tbody></table></div>
    </div>
"""


def _remediation_content(
    findings: list[tuple[str, str, str, str, str, str]],
    *,
    high_count: int,
    review_count: int,
    coverage_gap_count: int,
    manifest_recheck_passed: bool,
    release_tree_recheck_passed: bool,
) -> tuple[str, str]:
    integrity_ok = manifest_recheck_passed and release_tree_recheck_passed
    if not integrity_ok:
        selected = []
        secondary = []
        manifest_status = "passed" if manifest_recheck_passed else "failed"
        tree_status = "passed" if release_tree_recheck_passed else "failed"
        decision = (
            '<div class="decision high"><strong>Do not release or rely on this '
            "report yet.</strong> The release changed during the scan or could not "
            "be rechecked consistently. Restore or stabilize the working copy and "
            "rerun the audit before using the individual findings. "
            f"Manifest recheck: {_text(manifest_status)}. "
            f"Release-tree recheck: {_text(tree_status)}.</div>"
        )
        queue_note = (
            "The current finding list is provisional. Use it only after a new "
            "scan passes both integrity checks."
        )
        empty_message = "Individual remediation is deferred until integrity passes."
        correction_steps = """
    <h3>Restore a reliable scan</h3>
    <ol class="fix-list">
      <li>Stop any process that is writing to the release candidate.</li>
      <li>Restore the candidate from a known source or recreate it in a stable
      private working directory.</li>
      <li>Run the audit again without changing files during the scan.</li>
      <li>Continue to the finding list only after both integrity checks pass.</li>
    </ol>
"""
    elif high_count:
        selected = [row for row in findings if row[0] == "high"]
        secondary = [row for row in findings if row[0] == "review"]
        decision = (
            '<div class="decision high"><strong>Do not release this copy yet.</strong> '
            f"Resolve the {high_count} high-priority "
            f'finding{"s" if high_count != 1 else ""} below first.</div>'
        )
        queue_note = (
            f"{review_count} additional review "
            f'item{"s" if review_count != 1 else ""} are grouped below.'
            if review_count
            else "No additional review findings remain."
        )
        empty_message = "No immediate remediation tasks."
        correction_steps = """
    <h3>After each correction</h3>
    <ol class="fix-list">
      <li>Work on a private copy. Keep the original dataset unchanged.</li>
      <li>Use a format-aware tool for FIF, EDF/BDF, DICOM, NIfTI and EEGLAB
      files. Edit JSON and TSV only when their schema permits it.</li>
      <li>Run the audit again and confirm the item is gone and both integrity
      checks pass.</li>
      <li>Verify that channels, sampling, annotations, duration and other
      scientific properties did not change unexpectedly.</li>
    </ol>
"""
    elif review_count:
        selected = [row for row in findings if row[0] == "review"]
        secondary = []
        decision = (
            '<div class="decision review"><strong>Review before release.</strong> '
            f"The scanner found {review_count} "
            f'item{"s" if review_count != 1 else ""} that need a curator decision.'
            "</div>"
        )
        queue_note = "Work through each item below before making the release decision."
        empty_message = "No immediate remediation tasks."
        correction_steps = """
    <h3>After each correction</h3>
    <ol class="fix-list">
      <li>Work on a private copy. Keep the original dataset unchanged.</li>
      <li>Use a format-aware tool for FIF, EDF/BDF, DICOM, NIfTI and EEGLAB
      files. Edit JSON and TSV only when their schema permits it.</li>
      <li>Run the audit again and confirm the item is gone and both integrity
      checks pass.</li>
      <li>Verify that channels, sampling, annotations, duration and other
      scientific properties did not change unexpectedly.</li>
    </ol>
"""
    elif coverage_gap_count:
        selected = []
        secondary = []
        decision = (
            '<div class="decision review"><strong>No automated findings, but '
            "release remains on hold.</strong> "
            f"{coverage_gap_count} unsupported or untraversed "
            f'entr{"y" if coverage_gap_count == 1 else "ies"} still '
            f'{"needs" if coverage_gap_count == 1 else "need"} manual review.'
            "</div>"
        )
        queue_note = (
            "Open the manual-review table below and document a decision for "
            "every remaining entry."
        )
        empty_message = "No automated remediation tasks."
        correction_steps = """
    <h3>Before release</h3>
    <ol class="fix-list">
      <li>Review every unsupported or untraversed entry below.</li>
      <li>Use a suitable format-aware tool or document why the remaining
      coverage gap is acceptable.</li>
      <li>Run the audit again after any change and confirm both integrity
      checks still pass.</li>
    </ol>
"""
    else:
        selected = []
        secondary = []
        decision = (
            '<div class="decision ok"><strong>No high or review findings in the '
            "areas checked.</strong> This is not proof of anonymity. Check the "
            "coverage gaps and the stated format limits before release.</div>"
        )
        queue_note = "Complete the release checks below before sharing the dataset."
        empty_message = "No immediate remediation tasks."
        correction_steps = """
    <h3>Before release</h3>
    <ol class="fix-list">
      <li>Review the coverage gaps and format limits below.</li>
      <li>Confirm that both integrity checks passed.</li>
      <li>Document any remaining manual review decisions.</li>
    </ol>
"""

    if selected:
        table, group_count = _action_groups_table(selected)
        item_verb = "is" if len(selected) == 1 else "are"
        grouping_note = (
            f"{len(selected)} individual item"
            f"{'s' if len(selected) != 1 else ''} {item_verb} summarized in "
            f"{group_count} action group"
            f"{'s' if group_count != 1 else ''}. Grouping uses the finding "
            "code, field or location, and recommended action."
        )
    else:
        table = f'<p class="empty">{_text(empty_message)}</p>'
        grouping_note = ""
    if secondary:
        secondary_table, secondary_group_count = _action_groups_table(secondary)
        secondary_content = f"""
    <details class="review-queue" open>
      <summary>{review_count} review items in {secondary_group_count} action
      groups</summary>
      {secondary_table}
      <p class="note">Finish the high-priority corrections first. Then document
      a curator decision for each review group and use the full table for
      individual files.</p>
    </details>
"""
    else:
        secondary_content = ""
    content = f"""
    {decision}
    {table}
    {f'<p class="note">{_text(grouping_note)}</p>' if grouping_note else ''}
    <p class="note">{_text(queue_note)}</p>
    {secondary_content}
    {correction_steps}
    <p class="note">The audit never deletes or rewrites research data
    automatically.</p>
    <div class="section-links">
      <a href="#all-findings">Open the full findings table</a>
      <a href="#coverage-gaps">Check files needing manual review</a>
    </div>
"""
    return content, "What to do next"


def render_html(report: ScanReport, *, report_label: str | None = None) -> str:
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
    coverage_gap_count = (
        summary["unsupported_manual_review"] + summary["not_traversed"]
    )
    entry_type_counts: dict[str, int] = {}
    for item in data["coverage"]:
        entry_type = item["entry_type"]
        entry_type_counts[entry_type] = entry_type_counts.get(entry_type, 0) + 1
    entry_type_labels = {
        "file": ("regular file", "regular files"),
        "directory": ("folder", "folders"),
        "symlink": ("symlink", "symlinks"),
    }
    entry_parts = []
    for entry_type in ("file", "directory", "symlink"):
        count = entry_type_counts.pop(entry_type, 0)
        if count:
            labels = entry_type_labels[entry_type]
            entry_parts.append(f"{count} {labels[0 if count == 1 else 1]}")
    other_count = sum(entry_type_counts.values())
    if other_count:
        entry_parts.append(
            f"{other_count} other entr{'y' if other_count == 1 else 'ies'}"
        )
    entry_breakdown = (
        f"{summary['entries_total']} total "
        f"entr{'y' if summary['entries_total'] == 1 else 'ies'} = "
        + " + ".join(entry_parts)
        if entry_parts
        else "Open the inventory to review the accounted entries."
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
    findings_table = _filterable_findings_table(findings)
    remediation_content, remediation_title = _remediation_content(
        findings,
        high_count=summary["findings_high"],
        review_count=summary["findings_review"],
        coverage_gap_count=coverage_gap_count,
        manifest_recheck_passed=summary["manifest_recheck_passed"],
        release_tree_recheck_passed=summary["release_tree_recheck_passed"],
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
        empty="No files or folders were recorded.",
        code_columns=frozenset({0}),
    )
    coverage_gap_table = _table(
        ("Status", "Entry", "Why manual review is needed"),
        (
            (item["status"], item["path"], item["reason"])
            for item in data["coverage"]
            if item["status"] in {"unsupported_manual_review", "not_traversed"}
        ),
        empty="No unsupported or untraversed files or folders.",
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
        ),
        denominator=finding_total,
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
        ),
        denominator=summary["entries_total"],
    )
    high_count = summary["findings_high"]
    if not integrity_ok:
        release_status_class = "failed"
        release_status_text = "STOP — scan integrity failed"
        integrity_text = "The dataset changed during this scan"
        share_answer = "No."
        share_reason = (
            "The dataset changed while it was being checked, so this report "
            "may be incomplete."
        )
        share_next = (
            "Do not use this report for a release decision. Keep the dataset "
            "unchanged and run the audit again."
        )
        finding_list_status = (
            "No. This finding list is provisional until a new scan passes "
            "both integrity checks."
        )
        high_action = (
            '<div class="report-actions"><a class="report-action" '
            'href="#what-to-do">Resolve integrity failure</a></div>'
        )
    elif high_count:
        release_status_class = "failed"
        release_status_text = (
            f"HOLD — fix {high_count} high-priority "
            f'finding{"s" if high_count != 1 else ""}'
        )
        integrity_text = (
            "The dataset stayed unchanged during this scan — not release clearance"
        )
        finding_list_status = (
            "Yes — for the next review step, with the stated coverage and format "
            "limits. This is not permission to share the dataset."
        )
        share_answer = "No."
        share_reason = (
            f"{high_count} high-priority "
            f'issue{"s" if high_count != 1 else ""} must be fixed first.'
        )
        share_next = (
            "Open What to do next, fix the "
            f'issue{"s" if high_count != 1 else ""} on a private copy, and '
            "run the audit again."
        )
        high_action = (
            '<div class="report-actions">'
            f'<a class="report-action" href="#what-to-do">Fix {high_count} '
            f'high-priority finding{"s" if high_count != 1 else ""}</a>'
            "</div>"
        )
    elif summary["findings_review"]:
        release_status_class = "hold"
        release_status_text = "HOLD — curator review required"
        integrity_text = (
            "The dataset stayed unchanged during this scan — not release clearance"
        )
        finding_list_status = (
            "Yes — for the next review step, with the stated coverage and format "
            "limits. This is not permission to share the dataset."
        )
        review_count = summary["findings_review"]
        share_answer = "Not yet."
        share_reason = (
            f"{review_count} "
            f'item{"s" if review_count != 1 else ""} still '
            f'{"needs" if review_count == 1 else "need"} a person to decide '
            f'whether {"it is" if review_count == 1 else "they are"} safe to '
            "share."
        )
        share_next = (
            "Review every item, record the decision, and run the audit again "
            "after any change."
        )
        high_action = (
            '<div class="report-actions">'
            f'<a class="report-action hold" href="#what-to-do">Review {review_count} '
            f'finding{"s" if review_count != 1 else ""}</a>'
            "</div>"
        )
    elif coverage_gap_count:
        release_status_class = "hold"
        release_status_text = (
            f"HOLD — manually review {coverage_gap_count} listed "
            f'entr{"ies" if coverage_gap_count != 1 else "y"}'
        )
        integrity_text = (
            "The dataset stayed unchanged during this scan — not release clearance"
        )
        share_answer = "Not yet."
        share_reason = (
            f"{coverage_gap_count} listed "
            f'entr{"ies were" if coverage_gap_count != 1 else "y was"} '
            "not fully checked by the scanner."
        )
        share_next = (
            "Open Files needing manual review and check every listed item before "
            "making a release decision."
        )
        finding_list_status = (
            "Yes — for the next review step, with the stated coverage and format "
            "limits. This is not permission to share the dataset."
        )
        high_action = (
            '<div class="report-actions"><a class="report-action hold" '
            f'href="#coverage-gaps">Open {coverage_gap_count} '
            f'entr{"ies" if coverage_gap_count != 1 else "y"} needing manual '
            "review</a></div>"
        )
    else:
        release_status_class = "ok"
        release_status_text = (
            "No listed file needs correction — release still unconfirmed"
        )
        integrity_text = (
            "The dataset stayed unchanged during this scan — not proof of anonymity"
        )
        share_answer = "Not confirmed yet."
        share_reason = (
            "The automated checks found no blocker, but the coverage and "
            "format limits still need review before sharing."
        )
        share_next = (
            "Review the coverage and format limits before release. This report "
            "is not approval to share."
        )
        finding_list_status = (
            "Yes — for the next review step, with the stated coverage and format "
            "limits. This is not permission to share the dataset."
        )
        high_action = ""
    if coverage_gap_count:
        coverage_card_context = (
            f"{coverage_gap_count} listed "
            f'entr{"ies need" if coverage_gap_count != 1 else "y needs"} '
            "manual review and "
            f'{"are" if coverage_gap_count != 1 else "is"} not counted as '
            "inspected. Open Coverage."
        )
    else:
        coverage_card_context = (
            f'{summary["files_skipped"]} '
            f'{"files" if summary["files_skipped"] != 1 else "file"} skipped. '
            "This count excludes "
            "folders and differs from the inventory total. Open Coverage."
        )
    reference_summary = (
        f"{summary['references_valid']} valid of "
        f"{summary['references_checked']} checked"
    )
    reference_card = (
        f"""
    <a class="card card-link" href="#cross-file-references">
      <div class="label">Valid cross-file references</div>
      <div class="value">{reference_summary}</div>
      <div class="context">{summary["container_members"]} archive members
      inventoried. Open reference details.</div>
    </a>
"""
        if summary["references_checked"]
        else ""
    )
    if integrity_ok:
        findings_card = f"""
    <a class="card card-link" href="#all-findings">
      <div class="label">Findings</div>
      <div class="value">{finding_total}</div>
      <div class="context">{summary["findings_high"]} high ·
      {summary["findings_review"]} review. Open the finding list.</div>
    </a>
"""
        severity_section = f"""
  <section>
    <h2>Findings by severity</h2>
    {severity_bars}
    <p class="note">Each bar uses the same denominator:
    {finding_total} total finding{"s" if finding_total != 1 else ""}.</p>
  </section>
"""
        findings_section = f"""
  <section id="all-findings">
    <h2>All findings</h2>
    {findings_table}
  </section>
"""
    else:
        findings_card = ""
        severity_section = ""
        findings_section = f"""
  <section id="all-findings" class="provisional-section">
    <h2>Provisional findings</h2>
    <div class="decision high"><strong>Do not act on individual findings
    yet.</strong> The candidate changed during the scan or could not be
    rechecked consistently. Stabilize it and rerun the audit first.</div>
    <details>
      <summary>View {finding_total} provisional
      finding{"s" if finding_total != 1 else ""}</summary>
      {findings_table}
    </details>
  </section>
"""

    report_title = "NeuroData release security audit"
    study_context = ""
    if report_label:
        report_title += f" — {_text(report_label)}"
        study_context = " This is a separate audit case in the study."

    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{report_title}</title>
<style>{_STYLE}</style>
</head>
<body>
<main>
  <header class="top">
    <div>
      <h1>{report_title}</h1>
      <p class="subtitle">A local, read-only pre-release check. This report identifies
      items that need a decision; it does not certify anonymity or
      compliance.{study_context}</p>
      {high_action}
    </div>
    <div class="status-stack">
      <span class="status {release_status_class}">{release_status_text}</span>
      <span class="integrity-note">{integrity_text}</span>
    </div>
  </header>

  <div class="share-decision {release_status_class}" role="region"
  aria-labelledby="share-decision-title">
    <div>
      <div class="share-question" id="share-decision-title">Can this dataset be
      shared now?</div>
      <div class="share-answer">{_text(share_answer)}</div>
    </div>
    <div class="share-detail"><strong>Why</strong>{_text(share_reason)}</div>
    <div class="share-detail"><strong>Next step</strong>{_text(share_next)}</div>
  </div>

  <div class="finding-list-status" role="note">
    <strong>Can this finding list be used for the next review step?</strong>
    <span>{_text(finding_list_status)}</span>
  </div>

  <p class="privacy-warning" role="note"><strong>Keep this report private.</strong>
  Detected values are masked, but unrecognized identifying text may remain in
  relative paths or locations. Review the report before sharing or publishing it.</p>

  <div class="grid" aria-label="Audit summary">
    <a class="card card-link" href="#inventory">
      <div class="label">Files and folders accounted for</div>
      <div class="value">{summary["entries_total"]}</div>
      <div class="context">{_text(entry_breakdown)}. Open the inventory.</div>
    </a>
    {findings_card}
    <a class="card card-link" href="#coverage">
      <div class="label">Files inspected by the scanner</div>
      <div class="value">{summary["files_inspected"]}</div>
      <div class="context">{_text(coverage_card_context)}</div>
    </a>
    {reference_card}
  </div>

  {severity_section}

  <section id="what-to-do">
    <h2>{remediation_title}</h2>
    {remediation_content}
  </section>

  <section id="coverage">
    <h2>Coverage</h2>
    {coverage_bars}
    <p class="note">Coverage categories are mutually exclusive and use the same
    denominator: {summary["entries_total"]} accounted
    entr{"y" if summary["entries_total"] == 1 else "ies"}. Coverage describes
    what was read and is separate from privacy findings. Signal samples, image
    voxels and DICOM pixels are not interpreted.</p>
  </section>

  <section id="coverage-gaps">
    <h2>Files needing manual review</h2>
    {coverage_gap_table}
    <p class="note">These entries were accounted for but not fully parsed. Review
    them with a suitable format-aware tool or document why the remaining coverage
    gap is acceptable for this release.</p>
  </section>

  {findings_section}

  <section id="inventory">
    <h2>Files and folders accounted for</h2>
    {coverage_table}
    <p class="note">This inventory includes files, folders, symlinks and
    unsupported filesystem entries. The manifest below contains regular files
    only.</p>
  </section>

  <section id="cross-file-references">
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
    return "\n".join(line.rstrip() for line in html.splitlines()) + "\n"
