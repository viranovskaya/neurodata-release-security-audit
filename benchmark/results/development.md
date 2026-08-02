# Leak-detection benchmark

This benchmark uses labelled synthetic cases. It does not prove that a dataset is anonymous or legally compliant.

## Summary

- Suite: development
- Locked manifest: no
- Case files: 6
- Cases: 40
- Expected findings matched: 71 / 71
- Unexpected findings: 0
- Duplicate findings: 1
- Target recall: 1.000
- Labelled precision: 1.000
- Clean controls: 10 / 10
- Expected references matched: 10 / 10
- Unexpected references: 0
- Expected archive members matched: 4 / 4
- Unexpected archive members: 0
- Expected coverage states matched: 22 / 22
- Masking failures: 0
- Integrity failures: 0
- Case file hashes: cases/development_core.json=3df7e6b47529be2700df65bc43989267be9ca87d43583e016f0c31fa5b4b991b, cases/development_archives.json=58811fa4298a4fbff2329ecf641c26bea388e210d30bdc1631fd89829568853d, cases/development_references.json=00c7d1988331932db70dff35334e316640af528fa6fd3a6923fd3350c18d8ceb, cases/development_formats.json=44fe57ec8206514f24c9f46de8169e6ce356529dcc251d6695999914cd5d860d, cases/development_eeg_formats.json=277e89f44699ce1d605f1e26391bb85f65707fd03769777d7ab8596716eeb7c8, cases/development_realistic.json=7da1a51e5f85c18826166edba4ce487b5719734f9e8eb6d1a5776de73d529257

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
| dev_realistic_sleep_release | development | bids_sleep_release | 8/8 | 0 | 0 | 0/0 | 0/0 | 1/1 | 0 |
| dev_realistic_imaging_release | development | bids_imaging_release | 12/12 | 0 | 0 | 0/0 | 0/0 | 2/2 | 0 |
| dev_realistic_clean_brainvision_release | development | bids_eeg_release_control | 0/0 | 0 | 0 | 3/3 | 0/0 | 3/3 | 0 |

## By format

| Format | Cases | Matched | Unexpected | Recall | Precision |
|---|---:|---:|---:|---:|---:|
| bdf | 1 | 0/0 | 0 | — | — |
| bids_eeg_release | 1 | 0/0 | 0 | — | — |
| bids_imaging_release | 1 | 12/12 | 0 | 1.000 | 1.000 |
| bids_reference | 4 | 3/3 | 0 | 1.000 | 1.000 |
| bids_sleep_release | 1 | 8/8 | 0 | 1.000 | 1.000 |
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
| dates_and_demographics | 5/5 | 0 | 1.000 | 1.000 |
| free_text_and_sources | 2/2 | 0 | 1.000 | 1.000 |
| linked_identity | 5/5 | 0 | 1.000 | 1.000 |
| personal_identity | 27/27 | 0 | 1.000 | 1.000 |
| release_structure | 10/10 | 0 | 1.000 | 1.000 |
| secrets_and_paths | 5/5 | 0 | 1.000 | 1.000 |
| site_device_and_staff | 17/17 | 0 | 1.000 | 1.000 |
