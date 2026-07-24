"""Small fail-closed file helpers for the usability workflow."""

from __future__ import annotations

import os
import stat
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Iterator


@dataclass(frozen=True)
class FileIdentity:
    device: int
    inode: int


@contextmanager
def packaged_specification() -> Iterator[Path]:
    """Expose the administrator specification without copying it into a bundle."""
    resource = resources.files("usability").joinpath("spec.json")
    with resources.as_file(resource) as path:
        yield path


def write_text_new(path: Path, text: str) -> FileIdentity:
    """Atomically create one text file and refuse to replace an existing file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        metadata = temporary.stat(follow_symlinks=False)
        identity = FileIdentity(metadata.st_dev, metadata.st_ino)
        os.link(temporary, path)
        return identity
    finally:
        temporary.unlink(missing_ok=True)


def unlink_if_owned(path: Path, identity: FileIdentity) -> bool:
    """Remove a rollback file only while it still has the created inode."""
    try:
        metadata = path.stat(follow_symlinks=False)
    except FileNotFoundError:
        return False
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_dev != identity.device
        or metadata.st_ino != identity.inode
    ):
        return False
    path.unlink()
    return True
