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


@dataclass(frozen=True)
class OwnedFile:
    device: int
    inode: int
    token: Path


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


def write_text_new_owned(path: Path, text: str) -> OwnedFile:
    """Create a file and retain a private hard link until rollback is settled."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
    )
    token = Path(temporary_name)
    linked = False
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        metadata = token.stat(follow_symlinks=False)
        os.link(token, path)
        linked = True
        return OwnedFile(metadata.st_dev, metadata.st_ino, token)
    finally:
        if not linked:
            token.unlink(missing_ok=True)


def release_owned_file(identity: OwnedFile) -> None:
    """Release the private ownership link after the operation succeeds."""
    identity.token.unlink(missing_ok=True)


def unlink_if_owned(path: Path, identity: OwnedFile) -> bool:
    """Remove a rollback file only while it shares the retained hard link."""
    try:
        metadata = path.stat(follow_symlinks=False)
        token_metadata = identity.token.stat(follow_symlinks=False)
    except FileNotFoundError:
        release_owned_file(identity)
        return False
    owned = (
        stat.S_ISREG(metadata.st_mode)
        and stat.S_ISREG(token_metadata.st_mode)
        and metadata.st_dev == identity.device == token_metadata.st_dev
        and metadata.st_ino == identity.inode == token_metadata.st_ino
    )
    try:
        if owned:
            path.unlink()
        return owned
    finally:
        release_owned_file(identity)
