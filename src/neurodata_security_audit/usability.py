"""Score a small, precommitted report-usability benchmark."""

from __future__ import annotations

import hashlib
import json
import math
import re
import statistics
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path

_PARTICIPANT_ID = re.compile(r"reviewer-[0-9]{2,3}")
_TASK_ID = re.compile(r"task_[0-9]{2}")
_REPORT_PATH = re.compile(r"reports/report-[a-z]\.html")


def _load_json(path: Path) -> dict[str, object]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validate_spec(data: dict[str, object]) -> list[dict[str, object]]:
    allowed_top_level = {"schema_version", "suite_name", "thresholds", "tasks"}
    unexpected = set(data) - allowed_top_level
    if unexpected:
        raise ValueError(
            "Usability specification has unexpected fields: "
            + ", ".join(sorted(unexpected))
        )
    if data.get("schema_version") != "1":
        raise ValueError("Usability specification must use schema version 1")
    if not isinstance(data.get("suite_name"), str) or not data["suite_name"]:
        raise ValueError("Usability specification needs a suite_name")
    tasks = data.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        raise ValueError("Usability specification must contain tasks")

    seen: set[str] = set()
    validated: list[dict[str, object]] = []
    choice_groups: dict[str, list[dict[str, object]]] = defaultdict(list)
    for raw_task in tasks:
        if not isinstance(raw_task, dict):
            raise ValueError("Each usability task must be an object")
        allowed_task_fields = {
            "task_id",
            "report",
            "capability",
            "prompt",
            "choices",
            "expected",
            "critical",
            "choice_group",
        }
        unexpected = set(raw_task) - allowed_task_fields
        if unexpected:
            raise ValueError(
                "Usability task has unexpected fields: " + ", ".join(sorted(unexpected))
            )
        task_id = raw_task.get("task_id")
        if not isinstance(task_id, str) or not _TASK_ID.fullmatch(task_id):
            raise ValueError("Each usability task needs an opaque task_XX ID")
        if task_id in seen:
            raise ValueError(f"Duplicate usability task ID: {task_id}")
        seen.add(task_id)

        capability = raw_task.get("capability")
        if not isinstance(capability, str) or not capability:
            raise ValueError(f"{task_id} needs a capability")
        report = raw_task.get("report")
        if not isinstance(report, str) or not _REPORT_PATH.fullmatch(report):
            raise ValueError(f"{task_id} needs an opaque reports/report-x.html path")
        prompt = raw_task.get("prompt")
        if not isinstance(prompt, str) or not prompt:
            raise ValueError(f"{task_id} needs a prompt")
        choices = raw_task.get("choices")
        if not isinstance(choices, list) or len(choices) < 2:
            raise ValueError(f"{task_id} needs at least two choices")
        choice_values = []
        for choice in choices:
            if not isinstance(choice, dict):
                raise ValueError(f"{task_id} has an invalid choice")
            value = choice.get("value")
            label = choice.get("label")
            if not isinstance(value, str) or not value:
                raise ValueError(f"{task_id} has a choice without a value")
            if not isinstance(label, str) or not label:
                raise ValueError(f"{task_id} has a choice without a label")
            choice_values.append(value)
        if len(choice_values) != len(set(choice_values)):
            raise ValueError(f"{task_id} has duplicate choice values")
        expected = raw_task.get("expected")
        if expected not in choice_values:
            raise ValueError(f"{task_id} expected answer is not a choice")
        if not isinstance(raw_task.get("critical"), bool):
            raise ValueError(f"{task_id} must set critical to true or false")
        choice_group = raw_task.get("choice_group")
        if choice_group is not None and (
            not isinstance(choice_group, str) or not choice_group
        ):
            raise ValueError(f"{task_id} has an invalid choice_group")
        if bool(raw_task["critical"]) and choice_group is None:
            raise ValueError(f"{task_id} critical task needs a balanced choice_group")
        if isinstance(choice_group, str):
            choice_groups[choice_group].append(raw_task)
        validated.append(raw_task)

    for group_name, group_tasks in sorted(choice_groups.items()):
        if len(group_tasks) < 2:
            raise ValueError(f"{group_name} choice_group needs at least two tasks")
        prompts = {str(task["prompt"]) for task in group_tasks}
        choices = {
            tuple(
                (str(choice["value"]), str(choice["label"]))
                for choice in task["choices"]  # type: ignore[index]
            )
            for task in group_tasks
        }
        if len(prompts) != 1 or len(choices) != 1:
            raise ValueError(
                f"{group_name} choice_group must reuse one prompt and choice set"
            )
        choice_values = {value for value, _ in next(iter(choices))}
        expected_values = {str(task["expected"]) for task in group_tasks}
        if expected_values != choice_values:
            raise ValueError(
                f"{group_name} choice_group must use every choice as an expected answer"
            )

    critical_reports = [
        str(task["report"]) for task in validated if bool(task["critical"])
    ]
    if len(critical_reports) != len(set(critical_reports)):
        raise ValueError("Each critical task needs its own opaque report")
    noncritical_reports = {
        str(task["report"]) for task in validated if not bool(task["critical"])
    }
    overlap = sorted(set(critical_reports) & noncritical_reports)
    if overlap:
        raise ValueError(
            "Critical reports cannot be reused by noncritical tasks: "
            + ", ".join(overlap)
        )
    return validated


def _validate_thresholds(data: dict[str, object]) -> dict[str, int | float]:
    thresholds = data.get("thresholds")
    if not isinstance(thresholds, dict):
        raise ValueError("Usability specification needs thresholds")

    minimum_participants = thresholds.get("minimum_participants")
    if (
        isinstance(minimum_participants, bool)
        or not isinstance(minimum_participants, int)
        or minimum_participants < 1
    ):
        raise ValueError("minimum_participants must be a positive integer")

    validated: dict[str, int | float] = {"minimum_participants": minimum_participants}
    for name in ("overall_accuracy", "capability_accuracy", "critical_accuracy"):
        value = thresholds.get(name)
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not 0 <= value <= 1
        ):
            raise ValueError(f"{name} must be a number from 0 to 1")
        validated[name] = float(value)
    return validated


def _validate_responses(
    data: dict[str, object],
    tasks: dict[str, dict[str, object]],
) -> tuple[str, list[dict[str, object]]]:
    allowed_top_level = {"schema_version", "participant_id", "responses"}
    unexpected = set(data) - allowed_top_level
    if unexpected:
        raise ValueError(
            "Response file has unexpected fields: " + ", ".join(sorted(unexpected))
        )
    if data.get("schema_version") != "1":
        raise ValueError("Response file must use schema version 1")
    participant_id = data.get("participant_id")
    if not isinstance(participant_id, str) or not _PARTICIPANT_ID.fullmatch(
        participant_id
    ):
        raise ValueError(
            "Response file needs an administrator-assigned reviewer-XX participant_id"
        )
    responses = data.get("responses")
    if not isinstance(responses, list):
        raise ValueError(f"{participant_id} responses must be a list")

    seen: set[str] = set()
    validated: list[dict[str, object]] = []
    for response in responses:
        if not isinstance(response, dict):
            raise ValueError(f"{participant_id} has an invalid response")
        allowed_response_fields = {
            "task_id",
            "answer",
            "elapsed_seconds",
            "confidence",
        }
        unexpected = set(response) - allowed_response_fields
        if unexpected:
            raise ValueError(
                f"{participant_id} response has unexpected fields: "
                + ", ".join(sorted(unexpected))
            )
        task_id = response.get("task_id")
        if task_id not in tasks:
            raise ValueError(f"{participant_id} has unknown task {task_id}")
        if task_id in seen:
            raise ValueError(f"{participant_id} repeats task {task_id}")
        seen.add(str(task_id))

        task = tasks[str(task_id)]
        allowed = {
            str(choice["value"])
            for choice in task["choices"]  # type: ignore[index]
        }
        if response.get("answer") not in allowed:
            raise ValueError(f"{participant_id} has an invalid answer for {task_id}")
        elapsed = response.get("elapsed_seconds")
        if (
            isinstance(elapsed, bool)
            or not isinstance(elapsed, (int, float))
            or not math.isfinite(elapsed)
            or elapsed < 0
        ):
            raise ValueError(f"{participant_id} needs non-negative time for {task_id}")
        confidence = response.get("confidence")
        if (
            isinstance(confidence, bool)
            or not isinstance(confidence, int)
            or not 1 <= confidence <= 5
        ):
            raise ValueError(f"{participant_id} needs confidence 1-5 for {task_id}")
        validated.append(response)

    missing = sorted(set(tasks) - seen)
    if missing:
        raise ValueError(
            f"{participant_id} is missing responses for: {', '.join(missing)}"
        )
    return participant_id, validated


def score_usability(
    specification_path: str | Path,
    response_paths: Iterable[str | Path],
) -> dict[str, object]:
    """Score complete participant response files against a frozen task set."""
    spec_path = Path(specification_path)
    spec = _load_json(spec_path)
    task_list = _validate_spec(spec)
    thresholds = _validate_thresholds(spec)
    tasks = {str(task["task_id"]): task for task in task_list}

    participant_rows = []
    task_rows: dict[str, list[dict[str, object]]] = defaultdict(list)
    participant_ids: set[str] = set()
    response_hashes = []

    for raw_path in sorted(Path(path) for path in response_paths):
        data = _load_json(raw_path)
        participant_id, responses = _validate_responses(data, tasks)
        if participant_id in participant_ids:
            raise ValueError(f"Duplicate participant_id: {participant_id}")
        participant_ids.add(participant_id)

        correct = 0
        critical_errors = 0
        elapsed_total = 0.0
        for response in responses:
            task_id = str(response["task_id"])
            task = tasks[task_id]
            is_correct = response["answer"] == task["expected"]
            correct += int(is_correct)
            elapsed_total += float(response["elapsed_seconds"])
            if bool(task["critical"]) and not is_correct:
                critical_errors += 1
            task_rows[task_id].append(
                {
                    "participant_id": participant_id,
                    "correct": is_correct,
                    "elapsed_seconds": float(response["elapsed_seconds"]),
                    "confidence": int(response["confidence"]),
                }
            )
        participant_rows.append(
            {
                "participant_id": participant_id,
                "correct": correct,
                "tasks": len(tasks),
                "accuracy": correct / len(tasks),
                "critical_errors": critical_errors,
                "elapsed_seconds": elapsed_total,
            }
        )
        response_hashes.append(
            {
                "file": raw_path.name,
                "sha256": _sha256(raw_path),
            }
        )

    by_task = []
    by_capability_raw: dict[str, list[tuple[bool, float]]] = defaultdict(list)
    critical_correct = 0
    critical_total = 0
    for task in task_list:
        task_id = str(task["task_id"])
        rows = task_rows.get(task_id, [])
        correct = sum(bool(row["correct"]) for row in rows)
        times = [float(row["elapsed_seconds"]) for row in rows]
        capability = str(task["capability"])
        by_capability_raw[capability].extend(
            (bool(row["correct"]), float(row["elapsed_seconds"])) for row in rows
        )
        if bool(task["critical"]):
            critical_correct += correct
            critical_total += len(rows)
        by_task.append(
            {
                "task_id": task_id,
                "capability": capability,
                "critical": bool(task["critical"]),
                "correct": correct,
                "responses": len(rows),
                "accuracy": correct / len(rows) if rows else None,
                "median_elapsed_seconds": statistics.median(times) if times else None,
            }
        )

    by_capability = []
    for capability, rows in sorted(by_capability_raw.items()):
        correct = sum(is_correct for is_correct, _ in rows)
        times = [elapsed for _, elapsed in rows]
        by_capability.append(
            {
                "capability": capability,
                "correct": correct,
                "responses": len(rows),
                "accuracy": correct / len(rows) if rows else None,
                "median_elapsed_seconds": statistics.median(times) if times else None,
            }
        )

    participants = len(participant_rows)
    total_responses = participants * len(tasks)
    total_correct = sum(int(row["correct"]) for row in participant_rows)
    minimum_participants = int(thresholds["minimum_participants"])
    overall_threshold = float(thresholds["overall_accuracy"])
    capability_threshold = float(thresholds["capability_accuracy"])
    critical_threshold = float(thresholds["critical_accuracy"])
    overall_accuracy = total_correct / total_responses if total_responses else None
    critical_accuracy = critical_correct / critical_total if critical_total else None
    capability_gate = bool(by_capability) and all(
        row["accuracy"] is not None and float(row["accuracy"]) >= capability_threshold
        for row in by_capability
    )
    thresholds_met = (
        participants >= minimum_participants
        and overall_accuracy is not None
        and overall_accuracy >= overall_threshold
        and critical_accuracy is not None
        and critical_accuracy >= critical_threshold
        and capability_gate
    )

    return {
        "schema_version": "1",
        "suite_name": spec.get("suite_name"),
        "specification_sha256": _sha256(spec_path),
        "response_files": response_hashes,
        "summary": {
            "participants": participants,
            "minimum_participants": minimum_participants,
            "tasks_per_participant": len(tasks),
            "responses": total_responses,
            "correct": total_correct,
            "overall_accuracy": overall_accuracy,
            "critical_accuracy": critical_accuracy,
            "thresholds_met": thresholds_met,
            "status": (
                "complete"
                if participants >= minimum_participants
                else "pilot_incomplete"
            ),
        },
        "thresholds": thresholds,
        "participants": participant_rows,
        "by_capability": by_capability,
        "by_task": by_task,
    }


def render_usability_markdown(result: dict[str, object]) -> str:
    """Render a compact benchmark result without participant free text."""
    summary = result["summary"]
    assert isinstance(summary, dict)
    lines = [
        "# Report usability benchmark",
        "",
        (
            "This is an engineering usability check, not evidence that the "
            "scanner detects every privacy problem."
        ),
        "",
        "## Summary",
        "",
        (
            f"- Participants: {summary['participants']} / "
            f"{summary['minimum_participants']}"
        ),
        f"- Tasks per participant: {summary['tasks_per_participant']}",
        f"- Status: {summary['status']}",
        f"- Thresholds met: {'yes' if summary['thresholds_met'] else 'no'}",
    ]
    if summary["overall_accuracy"] is not None:
        lines.append(
            f"- Overall accuracy: {100 * float(summary['overall_accuracy']):.1f}%"
        )
    if summary["critical_accuracy"] is not None:
        lines.append(
            f"- Critical-task accuracy: "
            f"{100 * float(summary['critical_accuracy']):.1f}%"
        )

    lines.extend(
        [
            "",
            "## By capability",
            "",
            "| Capability | Correct | Responses | Accuracy | Median time |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for row in result["by_capability"]:  # type: ignore[union-attr]
        accuracy = (
            "—" if row["accuracy"] is None else f"{100 * float(row['accuracy']):.1f}%"
        )
        median = (
            "—"
            if row["median_elapsed_seconds"] is None
            else f"{float(row['median_elapsed_seconds']):.1f} s"
        )
        lines.append(
            f"| {row['capability']} | {row['correct']} | {row['responses']} | "
            f"{accuracy} | {median} |"
        )
    lines.extend(
        [
            "",
            (
                "A complete result still describes only this task set and these "
                "reviewers. It is not a general usability certification."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def render_reviewer_packet(specification_path: str | Path) -> str:
    """Render participant instructions without the answer key."""
    spec_path = Path(specification_path)
    spec = _load_json(spec_path)
    tasks = _validate_spec(spec)
    lines = [
        "# NeuroData report review",
        "",
        (
            "Please answer from the report alone. Do not inspect the source "
            "code, specification or answer key."
        ),
        "",
        "For each task:",
        "",
        "1. keep this file inside the supplied participant folder;",
        (
            "2. open it on a laptop or desktop in a Markdown editor with "
            "clickable links;"
        ),
        "3. start a timer before opening the report;",
        "4. mark one answer by replacing `[ ]` with `[x]`;",
        "5. record elapsed seconds and confidence from 1 to 5;",
        (
            "6. keep the report open while consecutive tasks use the same "
            "report; close it before opening a different report."
        ),
        "",
        (
            "Complete the tasks in the order shown. Every report file is "
            "different, but some related questions use the same report. "
            "Elapsed time is descriptive and is not part of the pass threshold."
        ),
        "",
        (
            "If a report link does not open, stop and tell the administrator. "
            "Do not move this file or browse the reports folder manually."
        ),
        "",
        (
            "This packet contains synthetic metadata only. Do not add your "
            "name, email or other personal details."
        ),
    ]
    current_report = None
    for task in tasks:
        report = str(task["report"])
        if report != current_report:
            current_report = report
            report_code = Path(report).stem.removeprefix("report-").upper()
            lines.extend(
                [
                    "",
                    f"## Report: [Report {report_code}]({report})",
                ]
            )
        lines.extend(
            [
                "",
                f"### {task['task_id']}",
                "",
                str(task["prompt"]),
                "",
            ]
        )
        for choice in task["choices"]:  # type: ignore[union-attr]
            lines.append(f"- [ ] `{choice['value']}` — {choice['label']}")
        lines.extend(
            [
                "",
                "- Elapsed seconds:",
                "- Confidence (1-5):",
            ]
        )
    lines.extend(
        [
            "",
            (
                "Save this file in the same folder and return the completed "
                "Markdown packet to the study administrator. The administrator "
                "records the answer code, elapsed seconds and confidence in a "
                "separate pseudonymous response file."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def build_response_template(
    specification_path: str | Path,
    participant_id: str,
) -> dict[str, object]:
    """Build a blank administrator response form without expected answers."""
    if not _PARTICIPANT_ID.fullmatch(participant_id):
        raise ValueError("participant_id must use the reviewer-XX format")
    spec = _load_json(Path(specification_path))
    tasks = _validate_spec(spec)
    return {
        "schema_version": "1",
        "participant_id": participant_id,
        "responses": [
            {
                "task_id": task["task_id"],
                "answer": "",
                "elapsed_seconds": 0,
                "confidence": 1,
            }
            for task in tasks
        ],
    }
