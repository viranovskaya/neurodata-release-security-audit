# Check on real EDF files

I tested the scanner on four files from the public [Sleep-EDF Database Expanded](https://physionet.org/content/sleep-edfx/1.0.0/): two PSG recordings and their two hypnograms. The repository does not contain copies of these files.

The first run found a problem in the name rule. EDF+ reserves a position for a patient name, but these files use an alphanumeric subject code there. The rule treated any populated value in that position as a name. PhysioNet describes the headers as anonymised to gender and age, so a high-severity name finding was not justified.

The rule now separates the two cases:

- alphabetic name-like values such as `Jane_Doe` produce `SUBJECT_NAME_FIELD`;
- alphanumeric subject codes stay under the broader `SUBJECT_FIELD_POPULATED` review finding.

After the change, all four files scan without a high-severity name finding. Their populated patient field, recording information and original EDF date remain visible as review items. That is the intended behaviour for a release audit: the tool points to metadata that needs a decision without claiming that a public dataset is unsafe.
