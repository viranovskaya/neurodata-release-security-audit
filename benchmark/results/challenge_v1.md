# Leak-detection benchmark

This benchmark uses labelled synthetic cases. It does not prove that a dataset is anonymous or legally compliant.

## Summary

- Suite: challenge-v1
- Locked manifest: yes
- Case files: 1
- Cases: 14
- Expected findings matched: 23 / 25
- Unexpected findings: 0
- Duplicate findings: 0
- Target recall: 0.920
- Labelled precision: 1.000
- Clean controls: 6 / 6
- Expected references matched: 0 / 0
- Unexpected references: 0
- Expected archive members matched: 0 / 0
- Unexpected archive members: 0
- Expected coverage states matched: 0 / 0
- Masking failures: 0
- Integrity failures: 0
- Case file hashes: cases/challenge_v1.json=7825505c139c20f7b9b1370d93860ec5c979c141d9d14cfa74867418b9fa1060

## Cases

| Case | Split | Format | Expected matched | Unexpected | Duplicates | References | Archive | Coverage | Masking failures |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| challenge_v1_nested_participant_contact | challenge | json | 4/4 | 0 | 0 | 0/0 | 0/0 | 0/0 | 0 |
| challenge_v1_table_aliases | challenge | tsv | 3/3 | 0 | 0 | 0/0 | 0/0 | 0/0 | 0 |
| challenge_v1_runtime_identifiers | challenge | json | 4/4 | 0 | 0 | 0/0 | 0/0 | 0/0 | 0 |
| challenge_v1_acquisition_metadata | challenge | json | 3/3 | 0 | 0 | 0/0 | 0/0 | 0/0 | 0 |
| challenge_v1_namespaced_xml_attributes | challenge | xml | 3/3 | 0 | 0 | 0/0 | 0/0 | 0/0 | 0 |
| challenge_v1_mixed_text_identity | challenge | text | 5/5 | 0 | 0 | 0/0 | 0/0 | 0/0 | 0 |
| challenge_v1_known_term_boundary | challenge | text | 1/1 | 0 | 0 | 0/0 | 0/0 | 0/0 | 0 |
| challenge_v1_json_secret_aliases | challenge | json | 0/2 | 0 | 0 | 0/0 | 0/0 | 0/0 | 0 |
| challenge_v1_device_model_control | challenge | json_control | 0/0 | 0 | 0 | 0/0 | 0/0 | 0/0 | 0 |
| challenge_v1_bids_description_control | challenge | json_control | 0/0 | 0 | 0 | 0/0 | 0/0 | 0/0 | 0 |
| challenge_v1_participant_codes_control | challenge | tsv_control | 0/0 | 0 | 0 | 0/0 | 0/0 | 0/0 | 0 |
| challenge_v1_placeholder_fields_control | challenge | json_control | 0/0 | 0 | 0 | 0/0 | 0/0 | 0/0 | 0 |
| challenge_v1_technical_terms_control | challenge | json_control | 0/0 | 0 | 0 | 0/0 | 0/0 | 0/0 | 0 |
| challenge_v1_public_references_control | challenge | text_control | 0/0 | 0 | 0 | 0/0 | 0/0 | 0/0 | 0 |

## By format

| Format | Cases | Matched | Unexpected | Recall | Precision |
|---|---:|---:|---:|---:|---:|
| json | 8 | 11/13 | 0 | 0.846 | 1.000 |
| text | 3 | 6/6 | 0 | 1.000 | 1.000 |
| tsv | 2 | 3/3 | 0 | 1.000 | 1.000 |
| xml | 1 | 3/3 | 0 | 1.000 | 1.000 |

## By finding class

| Class | Matched | Unexpected | Recall | Precision |
|---|---:|---:|---:|---:|
| coverage_or_other | 4/4 | 0 | 1.000 | 1.000 |
| dates_and_demographics | 1/1 | 0 | 1.000 | 1.000 |
| linked_identity | 4/4 | 0 | 1.000 | 1.000 |
| personal_identity | 11/11 | 0 | 1.000 | 1.000 |
| secrets_and_paths | 1/3 | 0 | 0.333 | 1.000 |
| site_device_and_staff | 2/2 | 0 | 1.000 | 1.000 |
