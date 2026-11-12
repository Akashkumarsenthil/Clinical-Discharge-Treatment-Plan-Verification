# Eligibility review of the 73 covered test cases

**Status:** reviewer named: **Shruthi (ST)**, who has taken the review (procedure in PR #18, below). Akash (AS, wrote Model A) and SS (rule author) cannot be the reviewer. The sheet in this repository is still blank and completion is not claimed. The assistant must not fill it.

This is step 1 in [adjudication_labels.md](adjudication_labels.md) and a hard requirement in [metrics.md](metrics.md). It has to be finished and frozen **before** Model A generates any test plan.

## The question for each case

> Does this admission record contain enough information for a clinician to judge whether a treatment plan for the case's reference diagnosis is clinically adequate and valid?

Answer **yes** or **no**. For **no**, write a short reason in your own words (for example "no imaging result in the record", "course of treatment not documented"). No patient text in the reason.

## Conditions (the manifest says `blind_to_plans: true`, so these must hold)

- Do not look at any generated plan, output from any model (including the earlier baseline), or verifier verdict for these 73 cases.
- Do not use the case facts or the rule coverage counts to decide. Judge from the record only.
- Do not choose cases because a rule can decide them. Every one of the 73 gets an answer, including the hard ones.
- The record text stays on the authorised machine. Only IDs, yes/no and short reasons go in the sheet.

## Who does what

**Shruthi (ST) is the blind reviewer.** She does the review as described in the sections below, on her own authorised machine.

**Akash (AS) coordinates. He is not the reviewer.**

1. Review this PR with a formal GitHub review (Approve or Request changes, not only a comment), then merge it.
2. When Shruthi has completed and verified all decisions and the manifest is built, check that: all 73 rows have an answer; every "no" has a short reason; no patient text is in the files; and the reviewer is not SS or AS.
3. Check that the manifest hash, date, reviewer and eligible count **E** are recorded in [metrics.md](metrics.md) (Open items table) and in the first box under "Before any test generation" in [model_a_freeze_checklist.md](model_a_freeze_checklist.md).
4. Do not generate any test plan until step 3 is done and the temperature decision (item 4 in the freeze checklist) is recorded.

**Sneha (SS)** has nothing to do here. She wrote the rules and cannot review.

## Steps

1. Copy [eligibility_review_sheet.csv](eligibility_review_sheet.csv) to a working file outside the repo. It lists the 73 covered case IDs (40 appendicitis, 22 pancreatitis and 11 diverticulitis are covered by catalog v2.1; the 27 cholecystitis cases are out of scope).
2. Fill `eligible_yes_no` (and `reason_if_no`) for every row.
3. Build and check the manifest. It refuses a blank or unclear row and checks the 73 against the frozen selection:
   `python scripts/build_eligibility_manifest.py --sheet <filled.csv> --reviewer <initials> --date YYYY-MM-DD --blind-to-plans`
4. The script prints the manifest's SHA-256. Record the hash, the date, the reviewer and the eligible count **E** in [metrics.md](metrics.md) (the Open items table) before generation starts.
5. Commit the manifest (IDs, yes/no, short reasons) so it is frozen. Do not edit it afterwards.

Report **E/73** with the reasons for each excluded case. The 73-case denominator is never replaced by E.

## Independence

The reviewer must not have written the rules (SS) or Model A (AS) and must not have seen any generated plan, model output or verifier verdict for these test cases. Earlier baseline outputs exist privately; see the disclosure below. Akash asked not to be the blind reviewer for that reason (PR 3 review).

## Plan labels come later and need a different person

After generation, each eligible plan needs an independent label (see [adjudication_labels.md](adjudication_labels.md); blank template: [plan_label_sheet_template.csv](plan_label_sheet_template.csv)). That reviewer must also be someone other than the rule author (SS) and the Model A author (AS). The eligibility reviewer and the label reviewer can be the same person or two of the three remaining members.

## Agreed record and decision procedure

Review only the Ext-CDM 1.1 tables `history_of_present_illness`, `physical_examination`, `laboratory_tests`, `microbiology`, and `radiology_reports`, shown in full, together with the reference diagnosis from the case list. Use the tables exactly as supplied, with no re-timing. Do not use discharge diagnosis, ICD diagnosis or procedure tables, discharge procedures, wider MIMIC-IV records, case-fact files, rule coverage counts, generated plans, model outputs or verifier verdicts.

Before starting, check the local files against the release's `SHA256SUMS.txt` and record the actual check date in the review PR. Patient text remains on the reviewer's own authorized machine; it must not be pasted into an AI tool. The assistant must not make eligibility decisions or prefill the sheet.

**Checksum verification record:** On November 3, 2026, Shruthi's local Ext-CDM 1.1 files were checked against the release `SHA256SUMS.txt`. All manifest entries passed, including the five permitted review tables. The check compared file hashes only; no patient records were displayed and no eligibility decisions were made. This date was recovered from the successful verification recorded in the review chat.

Decide once per case in sheet order. Answer yes only when confident that the allowed record is sufficient for a clinician to judge the adequacy and validity of a treatment plan for the reference diagnosis. If unsure, answer no and start the reason with `uncertain:` followed by what is missing, without patient text.

## Corrections before freeze

Corrections are allowed only for:

- `transcription`: the reviewer typed a different answer or case ID from the one intended;
- `viewer`: a loading or display problem meant the original decision used an incomplete record, such as a table that failed to load or text that was cut off.

A change of clinical judgment is not a correction. If re-reading changes the reviewer's opinion, the original decision stands.

Keep the original completed sheet unchanged. Append each correction to [eligibility_corrections_log.csv](eligibility_corrections_log.csv), with columns:

`case_id,original_answer,original_reason,corrected_answer,corrected_reason,correction_type,date,reviewer_initials`

Use `transcription` or `viewer` for `correction_type`, an ISO date (`YYYY-MM-DD`), and `ST` for Shruthi's initials. Never put patient text in any field. If a case ID was transcribed incorrectly, use the intended case ID in `case_id` and record the originally typed ID in the reason; preserve the original file. Keep every correction as a new row, including any later permitted correction to the same case, so the history remains visible.

Corrections must stop before the manifest is built and its hash recorded. They must also stop immediately if the reviewer sees any generated plan, model output or verifier verdict for these cases, regardless of the producing model. Accidental exposure must be reported to the team as a deviation; do not make further corrections after exposure.

After review, make a separate final input copy by applying only logged, permitted corrections to the preserved original sheet. Confirm that the final copy still contains exactly the frozen 73 case IDs, each once, in sheet order. Do not overwrite the original. Run the existing builder only after the reviewer has completed and verified all decisions:

```bash
python scripts/build_eligibility_manifest.py --sheet <final_filled.csv> --reviewer ST --date YYYY-MM-DD --blind-to-plans
```

The builder does not apply the correction log automatically. Pass `--blind-to-plans` only when the blindness conditions actually hold. Record the manifest hash, review date, ST, eligible count E and exclusion reasons in `docs/metrics.md`. After the hash is recorded, the manifest is frozen; later problems are documented deviations, not edits. Commit the corrections log with the manifest; a header-only log records zero corrections. Use the existing repository policy for committing the manifest, which is under the ignored `results/` directory; do not unignore that directory or any model outputs.

## Baseline overlap and reporting

Team disclosure: 14 of the 400 earlier Llama 3.1 8B Hager baseline cases fall within the 100-case test split; these same 14 are within the 73 covered cases (2 appendicitis, 9 diverticulitis, 3 pancreatitis). Akash reports that their outputs are private on his machine, have never been shown to Shruthi, and were not used to select cases, tune models or make eligibility decisions. No Model A test plans have been generated according to the team disclosure. Baseline generation predates the eligibility freeze; this must be disclosed in the report.

Shruthi must not see these baseline outputs, any new Model A test output or any verifier verdict for the 73 cases before the manifest hash is recorded. Blindness is about what the reviewer has seen, not the model that produced an output.

Report E out of 73, the reason for each exclusion, the number of exclusions whose reasons begin `uncertain:`, and the number of correction events of each type. E is not substituted for the fixed 73-case denominator. Record any accidental exposure and any post-freeze problem as a deviation.
