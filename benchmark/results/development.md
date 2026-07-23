# Leak-detection benchmark

This benchmark uses labelled synthetic cases. It does not prove that a dataset is anonymous or legally compliant.

## Summary

- Cases: 37
- Expected findings matched: 51 / 51
- Unexpected findings: 0
- Duplicate findings: 1
- Target recall: 1.000
- Labelled precision: 1.000
- Clean controls: 9 / 9
- Expected references matched: 7 / 7
- Unexpected references: 0
- Expected archive members matched: 4 / 4
- Unexpected archive members: 0
- Expected coverage states matched: 16 / 16
- Masking failures: 0
- Integrity failures: 0

## Cases

| Case | Split | Format | Expected matched | Unexpected | Duplicates | References | Archive | Coverage | Masking failures |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| dev_json_subject_name | development | json | 1/1 | 0 | 0 | 0/0 | 0/0 | 0/0 | 0 |
| dev_json_birth_date | development | json | 1/1 | 0 | 0 | 0/0 | 0/0 | 0/0 | 0 |
| dev_json_participant_email | development | json | 1/1 | 0 | 0 | 0/0 | 0/0 | 0/0 | 0 |
| dev_json_local_path | development | json | 1/1 | 0 | 0 | 0/0 | 0/0 | 0/0 | 0 |
| dev_json_source_id | development | json | 1/1 | 0 | 0 | 0/0 | 0/0 | 0/0 | 0 |
| dev_known_source_id | development | text | 1/1 | 0 | 0 | 0/0 | 0/0 | 0/0 | 0 |
| dev_filename_email | development | path | 1/1 | 0 | 0 | 0/0 | 0/0 | 0/0 | 0 |
| dev_public_contact | development | json_control | 1/1 | 0 | 0 | 0/0 | 0/0 | 0/0 | 0 |
| dev_bids_subject_control | development | json_control | 0/0 | 0 | 0 | 0/0 | 0/0 | 0/0 | 0 |
| dev_public_url_control | development | text_control | 0/0 | 0 | 0 | 0/0 | 0/0 | 0/0 | 0 |
| dev_tsv_phone | development | tsv | 1/1 | 0 | 0 | 0/0 | 0/0 | 0/0 | 0 |
| dev_csv_passport | development | csv | 1/1 | 0 | 0 | 0/0 | 0/0 | 0/0 | 0 |
| dev_xml_subject_name | development | xml | 1/1 | 0 | 0 | 0/0 | 0/0 | 0/0 | 0 |
| dev_xml_device_serial | development | xml | 1/1 | 0 | 0 | 0/0 | 0/0 | 0/0 | 0 |
| dev_text_network_path | development | text | 1/1 | 0 | 0 | 0/0 | 0/0 | 0/0 | 0 |
| dev_config_secret | development | config | 2/2 | 0 | 1 | 0/0 | 0/0 | 0/0 | 0 |
| dev_empty_fields_control | development | json_control | 0/0 | 0 | 0 | 0/0 | 0/0 | 0/0 | 0 |
| dev_technical_placeholders_control | development | text_control | 0/0 | 0 | 0 | 0/0 | 0/0 | 0/0 | 0 |
| dev_xml_dynamic_personal_id | development | xml | 1/1 | 0 | 0 | 0/0 | 0/0 | 0/0 | 0 |
| dev_zip_traversal | development | zip | 2/2 | 0 | 0 | 0/0 | 1/1 | 1/1 | 0 |
| dev_zip_member_email | development | zip | 2/2 | 0 | 0 | 0/0 | 1/1 | 1/1 | 0 |
| dev_tar_unsafe_symlink | development | tar | 3/3 | 0 | 0 | 0/0 | 1/1 | 1/1 | 0 |
| dev_zip_clean_structure | development | zip_control | 1/1 | 0 | 0 | 0/0 | 1/1 | 1/1 | 0 |
| dev_bids_reference_valid | development | bids_reference_control | 0/0 | 0 | 0 | 1/1 | 0/0 | 0/0 | 0 |
| dev_bids_reference_missing | development | bids_reference | 1/1 | 0 | 0 | 1/1 | 0/0 | 0/0 | 0 |
| dev_bids_reference_external | development | bids_reference | 1/1 | 0 | 0 | 1/1 | 0/0 | 0/0 | 0 |
| dev_bids_reference_case_mismatch | development | bids_reference | 1/1 | 0 | 0 | 1/1 | 0/0 | 0/0 | 0 |
| dev_edf_patient_header | development | edf | 5/5 | 0 | 0 | 0/0 | 0/0 | 1/1 | 0 |
| dev_edf_placeholder_control | development | edf_control | 0/0 | 0 | 0 | 0/0 | 0/0 | 1/1 | 0 |
| dev_nifti_description | development | nifti | 2/2 | 0 | 0 | 0/0 | 0/0 | 1/1 | 0 |
| dev_nifti_empty_header_control | development | nifti_control | 0/0 | 0 | 0 | 0/0 | 0/0 | 1/1 | 0 |
| dev_dicom_identity_fields | development | dicom | 10/10 | 0 | 0 | 0/0 | 0/0 | 1/1 | 0 |
| dev_fif_subject_info | development | fif | 5/5 | 0 | 0 | 0/0 | 0/0 | 1/1 | 0 |
| dev_fif_empty_info_control | development | fif_control | 1/1 | 0 | 0 | 0/0 | 0/0 | 1/1 | 0 |
| dev_brainvision_valid_references_control | development | brainvision_control | 0/0 | 0 | 0 | 3/3 | 0/0 | 3/3 | 0 |
| dev_brainvision_marker_timestamp | development | brainvision | 1/1 | 0 | 0 | 0/0 | 0/0 | 1/1 | 0 |
| dev_bdf_placeholder_control | development | bdf_control | 0/0 | 0 | 0 | 0/0 | 0/0 | 1/1 | 0 |

## By format

| Format | Cases | Matched | Unexpected | Recall | Precision |
|---|---:|---:|---:|---:|---:|
| bdf | 1 | 0/0 | 0 | — | — |
| bids_reference | 4 | 3/3 | 0 | 1.000 | 1.000 |
| brainvision | 2 | 1/1 | 0 | 1.000 | 1.000 |
| config | 1 | 2/2 | 0 | 1.000 | 1.000 |
| csv | 1 | 1/1 | 0 | 1.000 | 1.000 |
| dicom | 1 | 10/10 | 0 | 1.000 | 1.000 |
| edf | 2 | 5/5 | 0 | 1.000 | 1.000 |
| fif | 2 | 6/6 | 0 | 1.000 | 1.000 |
| json | 8 | 6/6 | 0 | 1.000 | 1.000 |
| nifti | 2 | 2/2 | 0 | 1.000 | 1.000 |
| path | 1 | 1/1 | 0 | 1.000 | 1.000 |
| tar | 1 | 3/3 | 0 | 1.000 | 1.000 |
| text | 4 | 2/2 | 0 | 1.000 | 1.000 |
| tsv | 1 | 1/1 | 0 | 1.000 | 1.000 |
| xml | 3 | 3/3 | 0 | 1.000 | 1.000 |
| zip | 3 | 5/5 | 0 | 1.000 | 1.000 |

## By finding class

| Class | Matched | Unexpected | Recall | Precision |
|---|---:|---:|---:|---:|
| dates_and_demographics | 3/3 | 0 | 1.000 | 1.000 |
| free_text_and_sources | 1/1 | 0 | 1.000 | 1.000 |
| linked_identity | 4/4 | 0 | 1.000 | 1.000 |
| personal_identity | 19/19 | 0 | 1.000 | 1.000 |
| release_structure | 10/10 | 0 | 1.000 | 1.000 |
| secrets_and_paths | 4/4 | 0 | 1.000 | 1.000 |
| site_device_and_staff | 10/10 | 0 | 1.000 | 1.000 |
