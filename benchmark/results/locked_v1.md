# Leak-detection benchmark

This benchmark uses labelled synthetic cases. It does not prove that a dataset is anonymous or legally compliant.

## Summary

- Suite: locked-v1
- Locked manifest: yes
- Case files: 1
- Cases: 10
- Expected findings matched: 21 / 21
- Unexpected findings: 0
- Duplicate findings: 0
- Target recall: 1.000
- Labelled precision: 1.000
- Clean controls: 2 / 2
- Expected references matched: 2 / 2
- Unexpected references: 0
- Expected archive members matched: 1 / 1
- Unexpected archive members: 0
- Expected coverage states matched: 8 / 8
- Masking failures: 0
- Integrity failures: 0
- Case file hashes: cases/locked_v1.json=57582aa0f1f57167dc9f9c82416781013f88dcd6deb39845e1f87e10742aa303

## Cases

| Case | Split | Format | Expected matched | Unexpected | Duplicates | References | Archive | Coverage | Masking failures |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| locked_json_mixed_identity | locked | json | 3/3 | 0 | 0 | 0/0 | 0/0 | 0/0 | 0 |
| locked_participants_control | locked | tsv_control | 0/0 | 0 | 0 | 0/0 | 0/0 | 0/0 | 0 |
| locked_public_contact | locked | text | 1/1 | 0 | 0 | 0/0 | 0/0 | 0/0 | 0 |
| locked_edf_known_identifier | locked | edf | 2/2 | 0 | 0 | 0/0 | 0/0 | 1/1 | 0 |
| locked_nifti_source_path | locked | nifti | 2/2 | 0 | 0 | 0/0 | 0/0 | 1/1 | 0 |
| locked_dicom_private_and_identity_status | locked | dicom | 6/6 | 0 | 0 | 0/0 | 0/0 | 1/1 | 0 |
| locked_fif_staff_and_device | locked | fif | 4/4 | 0 | 0 | 0/0 | 0/0 | 1/1 | 0 |
| locked_brainvision_missing_source | locked | brainvision | 2/2 | 0 | 0 | 2/2 | 0/0 | 2/2 | 0 |
| locked_tar_regular_member | locked | tar | 1/1 | 0 | 0 | 0/0 | 1/1 | 1/1 | 0 |
| locked_nifti_empty_control | locked | nifti_control | 0/0 | 0 | 0 | 0/0 | 0/0 | 1/1 | 0 |

## By format

| Format | Cases | Matched | Unexpected | Recall | Precision |
|---|---:|---:|---:|---:|---:|
| brainvision | 1 | 2/2 | 0 | 1.000 | 1.000 |
| dicom | 1 | 6/6 | 0 | 1.000 | 1.000 |
| edf | 1 | 2/2 | 0 | 1.000 | 1.000 |
| fif | 1 | 4/4 | 0 | 1.000 | 1.000 |
| json | 1 | 3/3 | 0 | 1.000 | 1.000 |
| nifti | 2 | 2/2 | 0 | 1.000 | 1.000 |
| tar | 1 | 1/1 | 0 | 1.000 | 1.000 |
| text | 1 | 1/1 | 0 | 1.000 | 1.000 |
| tsv | 1 | 0/0 | 0 | — | — |

## By finding class

| Class | Matched | Unexpected | Recall | Precision |
|---|---:|---:|---:|---:|
| dates_and_demographics | 1/1 | 0 | 1.000 | 1.000 |
| free_text_and_sources | 3/3 | 0 | 1.000 | 1.000 |
| linked_identity | 1/1 | 0 | 1.000 | 1.000 |
| personal_identity | 5/5 | 0 | 1.000 | 1.000 |
| release_structure | 2/2 | 0 | 1.000 | 1.000 |
| secrets_and_paths | 1/1 | 0 | 1.000 | 1.000 |
| site_device_and_staff | 8/8 | 0 | 1.000 | 1.000 |
