# Leak-detection benchmark

This benchmark uses labelled synthetic cases. It does not prove that a dataset is anonymous or legally compliant.

## Summary

- Suite: development_privacy_adversarial
- Locked manifest: no
- Case files: 0
- Cases: 10
- Expected findings matched: 32 / 32
- Unexpected findings: 0
- Duplicate findings: 0
- Target recall: 1.000
- Labelled precision: 1.000
- Clean controls: 2 / 2
- Expected references matched: 0 / 0
- Unexpected references: 0
- Expected archive members matched: 0 / 0
- Unexpected archive members: 0
- Expected coverage states matched: 0 / 0
- Masking failures: 0
- Integrity failures: 0

## Cases

| Case | Split | Format | Expected matched | Unexpected | Duplicates | References | Archive | Coverage | Masking failures |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| dev_privacy_compound_participant_record | development | json | 7/7 | 0 | 0 | 0/0 | 0/0 | 0/0 | 0 |
| dev_privacy_acquisition_trace | development | json | 8/8 | 0 | 0 | 0/0 | 0/0 | 0/0 | 0 |
| dev_privacy_short_credentials | development | json | 4/4 | 0 | 0 | 0/0 | 0/0 | 0/0 | 0 |
| dev_privacy_credential_placeholders_control | development | json_control | 0/0 | 0 | 0 | 0/0 | 0/0 | 0/0 | 0 |
| dev_privacy_public_and_participant_contacts | development | json | 2/2 | 0 | 0 | 0/0 | 0/0 | 0/0 | 0 |
| dev_privacy_structured_free_text_history | development | json | 6/6 | 0 | 0 | 0/0 | 0/0 | 0/0 | 0 |
| dev_privacy_subject_mapping_file | development | tsv | 2/2 | 0 | 0 | 0/0 | 0/0 | 0/0 | 0 |
| dev_privacy_sensitive_config_directory | development | config | 2/2 | 0 | 0 | 0/0 | 0/0 | 0/0 | 0 |
| dev_privacy_os_metadata_file | development | file_hygiene | 1/1 | 0 | 0 | 0/0 | 0/0 | 0/0 | 0 |
| dev_privacy_technical_placeholders_control | development | json_control | 0/0 | 0 | 0 | 0/0 | 0/0 | 0/0 | 0 |

## By format

| Format | Cases | Matched | Unexpected | Recall | Precision |
|---|---:|---:|---:|---:|---:|
| config | 1 | 2/2 | 0 | 1.000 | 1.000 |
| file_hygiene | 1 | 1/1 | 0 | 1.000 | 1.000 |
| json | 7 | 27/27 | 0 | 1.000 | 1.000 |
| tsv | 1 | 2/2 | 0 | 1.000 | 1.000 |

## By finding class

| Class | Matched | Unexpected | Recall | Precision |
|---|---:|---:|---:|---:|
| dates_and_demographics | 1/1 | 0 | 1.000 | 1.000 |
| free_text_and_sources | 1/1 | 0 | 1.000 | 1.000 |
| linked_identity | 3/3 | 0 | 1.000 | 1.000 |
| operational_metadata | 4/4 | 0 | 1.000 | 1.000 |
| personal_identity | 11/11 | 0 | 1.000 | 1.000 |
| release_structure | 1/1 | 0 | 1.000 | 1.000 |
| secrets_and_paths | 9/9 | 0 | 1.000 | 1.000 |
| site_device_and_staff | 2/2 | 0 | 1.000 | 1.000 |
