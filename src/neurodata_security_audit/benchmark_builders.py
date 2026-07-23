"""Create small synthetic files used by the benchmark."""

from __future__ import annotations

import io
from datetime import date
from pathlib import Path
import tarfile
import zipfile


def _output_path(root: Path, value: str) -> Path:
    relative = Path(value)
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise ValueError("Benchmark builder output must stay inside its case directory")
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _build_zip(root: Path, builder: dict[str, object]) -> None:
    path = _output_path(root, builder["path"])
    with zipfile.ZipFile(path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for member in builder["members"]:
            archive.writestr(member["path"], member.get("text", ""))


def _build_tar(root: Path, builder: dict[str, object]) -> None:
    path = _output_path(root, builder["path"])
    with tarfile.open(path, mode="w") as archive:
        for member in builder["members"]:
            info = tarfile.TarInfo(member["path"])
            member_type = member.get("type", "file")
            if member_type == "file":
                data = member.get("text", "").encode("utf-8")
                info.size = len(data)
                archive.addfile(info, io.BytesIO(data))
            elif member_type == "symlink":
                info.type = tarfile.SYMTYPE
                info.linkname = member["target"]
                archive.addfile(info)
            else:
                raise ValueError(f"Unsupported TAR benchmark member type: {member_type}")


def _padded_ascii(value: str, width: int) -> bytes:
    encoded = value.encode("ascii")
    if len(encoded) > width:
        raise ValueError(f"EDF benchmark field is longer than {width} bytes")
    return encoded.ljust(width, b" ")


def _build_edf(root: Path, builder: dict[str, object]) -> None:
    path = _output_path(root, builder["path"])
    header = b"".join(
        (
            _padded_ascii("0", 8),
            _padded_ascii(str(builder.get("patient", "X X X X")), 80),
            _padded_ascii(
                str(builder.get("recording", "Startdate X X X X")),
                80,
            ),
            _padded_ascii(str(builder.get("start_date", "01.01.85")), 8),
            _padded_ascii("00.00.00", 8),
            _padded_ascii("256", 8),
            _padded_ascii("", 44),
            _padded_ascii("0", 8),
            _padded_ascii("1", 8),
            _padded_ascii("0", 4),
        )
    )
    path.write_bytes(header)


def _build_nifti(root: Path, builder: dict[str, object]) -> None:
    import nibabel
    import numpy as np

    path = _output_path(root, builder["path"])
    image = nibabel.Nifti1Image(np.zeros((1, 1, 1), dtype=np.int16), np.eye(4))
    for field in ("descrip", "aux_file", "intent_name", "db_name"):
        if field in builder:
            image.header[field] = str(builder[field]).encode("utf-8")
    nibabel.save(image, str(path))


def _build_dicom(root: Path, builder: dict[str, object]) -> None:
    import pydicom
    from pydicom.dataset import FileDataset, FileMetaDataset
    from pydicom.uid import ExplicitVRLittleEndian

    path = _output_path(root, builder["path"])
    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.7"
    file_meta.MediaStorageSOPInstanceUID = "1.2.826.0.1.3680043.10.543.1"
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    file_meta.ImplementationClassUID = "1.2.826.0.1.3680043.10.543.2"
    dataset = FileDataset(
        str(path),
        {},
        file_meta=file_meta,
        preamble=b"\0" * 128,
    )
    dataset.SOPClassUID = file_meta.MediaStorageSOPClassUID
    dataset.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
    dataset.Modality = "OT"
    for field, value in builder.get("fields", {}).items():
        setattr(dataset, field, value)
    dataset.save_as(path, enforce_file_format=True)


def _build_fif(root: Path, builder: dict[str, object]) -> None:
    import mne
    import numpy as np

    path = _output_path(root, builder["path"])
    info = mne.create_info(["Fz"], sfreq=100.0, ch_types=["eeg"])
    subject = builder.get("subject_info")
    if subject is not None:
        subject_info = dict(subject)
        birthday = subject_info.get("birthday")
        if birthday is not None:
            subject_info["birthday"] = date.fromisoformat(str(birthday))
        info["subject_info"] = subject_info
    raw = mne.io.RawArray(
        np.zeros((1, 10), dtype=float),
        info,
        verbose="ERROR",
    )
    raw.save(path, overwrite=True, verbose="ERROR")


_BUILDERS = {
    "dicom": _build_dicom,
    "edf": _build_edf,
    "fif": _build_fif,
    "nifti": _build_nifti,
    "tar": _build_tar,
    "zip": _build_zip,
}


def build_case_data(root: Path, builder: dict[str, object]) -> None:
    name = builder.get("name")
    try:
        build = _BUILDERS[name]
    except (KeyError, TypeError) as error:
        raise ValueError(f"Unknown benchmark builder: {name}") from error
    build(root, builder)
